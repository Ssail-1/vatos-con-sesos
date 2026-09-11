"""Validación y creación atómica de un PlanItem persistente."""

from datetime import date, datetime, time, timedelta
import re
from uuid import UUID, uuid4

import psycopg

import database
from plan_item_materializer import (
    get_materialization_range,
    materialize_occurrence_drafts,
)
from repositories import plan_item_repository


ACTIVITY_TYPES = frozenset({"anchor", "periodic", "event", "unexpected"})
HABIT_TYPES = frozenset({"scheduled"})
GENERATION_MODES = frozenset({"weekly", "interval_days", "manual_dates"})
HISTORY_EDIT_WINDOW_DAYS = 1
_TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class PlanItemCreationError(RuntimeError):
    """Error seguro de creación."""


class PlanItemValidationError(PlanItemCreationError):
    """El JSON no cumple el contrato canónico."""


class PlanItemConflictError(PlanItemCreationError):
    """La creación contradice el estado vigente del planner."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class PlanItemCreationUnavailableError(PlanItemCreationError):
    """PostgreSQL no pudo completar la creación."""


def _invalid(message):
    raise PlanItemValidationError(message)


def _require_exact_fields(value, required, optional, field_name):
    if not isinstance(value, dict):
        _invalid(f"{field_name} debe ser un objeto.")
    keys = set(value)
    missing = required - keys
    unexpected = keys - required - optional
    if missing:
        _invalid(f"{field_name} no contiene todos los campos obligatorios.")
    if unexpected:
        _invalid(f"{field_name} contiene campos no admitidos.")


def _date_string(value, field_name):
    if not isinstance(value, str):
        _invalid(f"{field_name} debe usar YYYY-MM-DD.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        _invalid(f"{field_name} debe ser una fecha válida.")
    if parsed.isoformat() != value:
        _invalid(f"{field_name} debe usar YYYY-MM-DD.")
    return value


def _time_string(value, field_name):
    if not isinstance(value, str) or _TIME_PATTERN.fullmatch(value) is None:
        _invalid(f"{field_name} debe usar HH:MM.")
    return value


def _time_range(start_value, end_value, start_field, end_field):
    start_time = _time_string(start_value, start_field)
    end_time = _time_string(end_value, end_field)
    if start_time >= end_time:
        _invalid("La hora final debe ser posterior a la inicial.")
    return start_time, end_time


def _generation_controls(config, normalized):
    if "excludedDates" in config:
        excluded_dates = config["excludedDates"]
        if not isinstance(excluded_dates, list):
            _invalid("excludedDates debe ser una lista.")
        normalized_dates = [
            _date_string(value, "excludedDates") for value in excluded_dates
        ]
        if len(set(normalized_dates)) != len(normalized_dates):
            _invalid("excludedDates debe contener fechas únicas.")
        if normalized_dates:
            normalized["excludedDates"] = sorted(normalized_dates)
    if "stoppedFromDate" in config:
        normalized["stoppedFromDate"] = _date_string(
            config["stoppedFromDate"], "stoppedFromDate"
        )
    return normalized


def _recurring_range(config, normalized):
    start_date = _date_string(config["startDate"], "startDate")
    indefinite = config["indefinite"]
    if not isinstance(indefinite, bool):
        _invalid("indefinite debe ser un booleano.")
    end_value = config["endDate"]
    if indefinite:
        if end_value is not None:
            _invalid("Una repetición indefinida no puede tener endDate.")
        end_date = None
    else:
        end_date = _date_string(end_value, "endDate")
        if end_date < start_date:
            _invalid("endDate no puede ser anterior a startDate.")
    normalized.update(
        {"startDate": start_date, "endDate": end_date, "indefinite": indefinite}
    )


def _weekly_config(config):
    required = {
        "mode",
        "startDate",
        "endDate",
        "indefinite",
        "weekdays",
        "defaultStartTime",
        "defaultEndTime",
        "weekdayTimeOverrides",
    }
    _require_exact_fields(
        config, required, {"excludedDates", "stoppedFromDate"}, "generationConfig"
    )
    normalized = {"mode": "weekly"}
    _recurring_range(config, normalized)

    weekdays = config["weekdays"]
    if not isinstance(weekdays, list) or not weekdays:
        _invalid("weekly requiere al menos un weekday.")
    if any(
        isinstance(weekday, bool)
        or not isinstance(weekday, int)
        or weekday < 1
        or weekday > 7
        for weekday in weekdays
    ) or len(set(weekdays)) != len(weekdays):
        _invalid("Los weekdays deben ser enteros ISO únicos entre 1 y 7.")
    normalized["weekdays"] = sorted(weekdays)
    default_start, default_end = _time_range(
        config["defaultStartTime"],
        config["defaultEndTime"],
        "defaultStartTime",
        "defaultEndTime",
    )
    normalized["defaultStartTime"] = default_start
    normalized["defaultEndTime"] = default_end

    overrides = config["weekdayTimeOverrides"]
    if not isinstance(overrides, dict):
        _invalid("weekdayTimeOverrides debe ser un objeto.")
    normalized_overrides = {}
    for weekday_key, override in overrides.items():
        if weekday_key not in {str(weekday) for weekday in weekdays}:
            _invalid("Un override solo puede pertenecer a un weekday activo.")
        _require_exact_fields(
            override,
            {"startTime", "endTime"},
            set(),
            "weekdayTimeOverrides",
        )
        start_time, end_time = _time_range(
            override["startTime"],
            override["endTime"],
            "weekday override startTime",
            "weekday override endTime",
        )
        normalized_overrides[weekday_key] = {
            "startTime": start_time,
            "endTime": end_time,
        }
    normalized["weekdayTimeOverrides"] = dict(
        sorted(normalized_overrides.items(), key=lambda pair: int(pair[0]))
    )
    return _generation_controls(config, normalized)


def _interval_config(config):
    required = {
        "mode",
        "startDate",
        "endDate",
        "indefinite",
        "intervalDays",
        "defaultStartTime",
        "defaultEndTime",
    }
    _require_exact_fields(
        config, required, {"excludedDates", "stoppedFromDate"}, "generationConfig"
    )
    normalized = {"mode": "interval_days"}
    _recurring_range(config, normalized)
    interval_days = config["intervalDays"]
    if (
        isinstance(interval_days, bool)
        or not isinstance(interval_days, int)
        or interval_days < 1
    ):
        _invalid("intervalDays debe ser un entero mayor o igual a 1.")
    normalized["intervalDays"] = interval_days
    start_time, end_time = _time_range(
        config["defaultStartTime"],
        config["defaultEndTime"],
        "defaultStartTime",
        "defaultEndTime",
    )
    normalized["defaultStartTime"] = start_time
    normalized["defaultEndTime"] = end_time
    return _generation_controls(config, normalized)


def _manual_dates_config(config):
    _require_exact_fields(
        config,
        {"mode", "entries"},
        {"excludedDates", "stoppedFromDate"},
        "generationConfig",
    )
    entries = config["entries"]
    if not isinstance(entries, list) or not entries:
        _invalid("manual_dates requiere al menos una entry.")
    normalized_entries = []
    for entry in entries:
        _require_exact_fields(
            entry, {"date", "startTime", "endTime"}, set(), "entry"
        )
        start_time, end_time = _time_range(
            entry["startTime"], entry["endTime"], "startTime", "endTime"
        )
        normalized_entries.append(
            {
                "date": _date_string(entry["date"], "entry.date"),
                "startTime": start_time,
                "endTime": end_time,
            }
        )
    entry_keys = [
        (entry["date"], entry["startTime"], entry["endTime"])
        for entry in normalized_entries
    ]
    if len(set(entry_keys)) != len(entry_keys):
        _invalid("manual_dates no admite entries idénticas duplicadas.")
    normalized = {
        "mode": "manual_dates",
        "entries": sorted(
            normalized_entries,
            key=lambda entry: (entry["date"], entry["startTime"], entry["endTime"]),
        ),
    }
    return _generation_controls(config, normalized)


def _normalize_generation_config(config):
    if not isinstance(config, dict) or config.get("mode") not in GENERATION_MODES:
        _invalid("generationConfig.mode no es válido.")
    if config["mode"] == "weekly":
        return _weekly_config(config)
    if config["mode"] == "interval_days":
        return _interval_config(config)
    return _manual_dates_config(config)


def validate_plan_item_payload(payload):
    """Valida y normaliza el draft exacto producido por el frontend."""
    if not isinstance(payload, dict):
        _invalid("El cuerpo JSON debe ser un objeto.")
    kind = payload.get("kind")
    if kind == "activity":
        required = {"name", "kind", "activityType", "generationConfig"}
        subtype_field = "activityType"
        valid_subtypes = ACTIVITY_TYPES
    elif kind == "habit":
        required = {"name", "kind", "habitType", "generationConfig"}
        subtype_field = "habitType"
        valid_subtypes = HABIT_TYPES
    else:
        _invalid("kind debe ser activity o habit.")
    _require_exact_fields(payload, required, set(), "PlanItem")

    name = payload["name"]
    if not isinstance(name, str):
        _invalid("name debe ser texto.")
    name = name.strip()
    if not name or len(name) > 80:
        _invalid("name debe contener entre 1 y 80 caracteres.")
    subtype = payload[subtype_field]
    if subtype not in valid_subtypes:
        _invalid("La clasificación del PlanItem no es válida.")

    return {
        "name": name,
        "kind": kind,
        subtype_field: subtype,
        "generationConfig": _normalize_generation_config(
            payload["generationConfig"]
        ),
    }


def _time_to_minutes(value):
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def _overlaps(first, second):
    return (
        first["date"] == second["date"]
        and _time_to_minutes(first["startTime"])
        < _time_to_minutes(second["endTime"])
        and _time_to_minutes(first["endTime"])
        > _time_to_minutes(second["startTime"])
    )


def _validate_internal_conflicts(drafts):
    accepted = []
    for draft in drafts:
        if any(_overlaps(draft, other) for other in accepted):
            raise PlanItemConflictError(
                "candidate_internal_conflict",
                "La creación contiene horarios que se superponen entre sí.",
            )
        accepted.append(draft)


def _existing_occurrence(row):
    occurrence_date = row["occurrence_date"]
    if isinstance(occurrence_date, datetime) or not isinstance(
        occurrence_date, date
    ):
        raise PlanItemCreationUnavailableError(
            "PostgreSQL devolvió una occurrence no válida."
        )
    start_time = row["start_time"]
    end_time = row["end_time"]
    if (
        not isinstance(start_time, time)
        or not isinstance(end_time, time)
        or start_time.second != 0
        or start_time.microsecond != 0
        or end_time.second != 0
        or end_time.microsecond != 0
    ):
        raise PlanItemCreationUnavailableError(
            "PostgreSQL devolvió una occurrence no válida."
        )
    return {
        "date": occurrence_date.isoformat(),
        "startTime": start_time.strftime("%H:%M"),
        "endTime": end_time.strftime("%H:%M"),
    }


def _priority(kind, subtype):
    if kind == "activity" and subtype == "unexpected":
        return 300
    if kind == "activity" and subtype == "event":
        return 200
    return 100


def _validate_existing_conflicts(plan_item, drafts, rows):
    conflicts = [
        row
        for row in rows
        if any(_overlaps(draft, _existing_occurrence(row)) for draft in drafts)
    ]
    if not conflicts:
        return
    if any(row["status"] == "completed" for row in conflicts):
        raise PlanItemConflictError(
            "completed_conflict",
            "El intervalo contiene un registro completado y protegido.",
        )
    subtype = plan_item.get("activityType") or plan_item.get("habitType")
    candidate_priority = _priority(plan_item["kind"], subtype)
    if any(
        candidate_priority <= _priority(row["kind"], row["subtype"])
        for row in conflicts
    ):
        raise PlanItemConflictError(
            "priority_conflict",
            "La prioridad del PlanItem no permite desplazar los conflictos.",
        )
    # El frontend exige una confirmación antes de hacer este desplazamiento.
    # El POST canónico todavía no incluye una señal de confirmación.
    raise PlanItemConflictError(
        "priority_override_required",
        "La creación requiere confirmar un desplazamiento por prioridad.",
    )


def _assign_ids(plan_item, drafts, uuid_factory):
    plan_item_id = str(uuid_factory())
    persisted_plan_item = {"id": plan_item_id, **plan_item}
    occurrences = [
        {"id": str(uuid_factory()), **draft, "planItemId": plan_item_id}
        for draft in drafts
    ]
    entry_ids = [
        str(uuid_factory())
        for _ in persisted_plan_item["generationConfig"].get("entries", [])
    ]
    return persisted_plan_item, occurrences, entry_ids


def _validate_generated_ids(plan_item, occurrences, entry_ids):
    # Defensa local para factories inyectadas en pruebas; PostgreSQL recibe UUID reales.
    ids = [plan_item["id"], *entry_ids, *(item["id"] for item in occurrences)]
    try:
        parsed = [UUID(value) for value in ids]
    except (ValueError, TypeError, AttributeError):
        raise PlanItemCreationUnavailableError(
            "No se pudieron generar identificadores válidos."
        ) from None
    if len(set(parsed)) != len(parsed):
        raise PlanItemCreationUnavailableError(
            "No se pudieron generar identificadores únicos."
        )


def create_plan_item(payload, reference_date=None, uuid_factory=uuid4):
    """Valida, materializa y persiste todo o nada en una transacción."""
    normalized = validate_plan_item_payload(payload)
    current_date = reference_date or date.today()
    if isinstance(current_date, datetime) or not isinstance(current_date, date):
        raise TypeError("reference_date debe ser date.")

    preview = {"id": "__candidate_plan_item__", **normalized}
    range_start, range_end = get_materialization_range(preview, current_date)
    drafts = materialize_occurrence_drafts(preview, range_start, range_end)
    frozen_before = current_date - timedelta(days=HISTORY_EDIT_WINDOW_DAYS)
    if any(date.fromisoformat(draft["date"]) < frozen_before for draft in drafts):
        raise PlanItemConflictError(
            "history_frozen",
            "No se pueden crear occurrences dentro del historial congelado.",
        )
    _validate_internal_conflicts(drafts)
    plan_item, occurrences, entry_ids = _assign_ids(
        normalized, drafts, uuid_factory
    )
    _validate_generated_ids(plan_item, occurrences, entry_ids)

    try:
        with database.get_connection() as connection:
            with connection.transaction():
                blocking_rows = plan_item_repository.list_blocking_occurrences(
                    connection,
                    sorted({draft["date"] for draft in drafts}),
                )
                _validate_existing_conflicts(plan_item, drafts, blocking_rows)
                plan_item_repository.insert_plan_item_graph(
                    connection, plan_item, occurrences, entry_ids
                )
    except PlanItemConflictError:
        raise
    except (database.DatabaseConnectionError, psycopg.Error):
        raise PlanItemCreationUnavailableError(
            "No se pudo crear el PlanItem persistente."
        ) from None

    return {"planItem": plan_item, "occurrences": occurrences}
