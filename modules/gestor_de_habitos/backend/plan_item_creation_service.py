"""Validación y creación atómica de un PlanItem persistente."""

from datetime import date, datetime, time, timedelta
import re
from uuid import UUID, uuid4

import psycopg
from psycopg import IsolationLevel

import database
from occurrence_segment_domain import (
    derive_occurrence_status,
    temporal_phase_for_date,
)
from plan_item_materializer import (
    get_materialization_range,
    materialize_occurrence_drafts,
)
from repositories import plan_item_repository
from scheduling_policy import (
    HISTORY_EDIT_WINDOW_DAYS,
    occurrence_items_overlap,
    scheduling_priority,
)


ACTIVITY_TYPES = frozenset({"anchor", "periodic", "event", "unexpected"})
HABIT_TYPES = frozenset({"scheduled"})
GENERATION_MODES = frozenset({"weekly", "interval_days", "manual_dates"})
_TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class PlanItemCreationError(RuntimeError):
    """Error seguro de creación."""


class PlanItemValidationError(PlanItemCreationError):
    """El JSON no cumple el contrato canónico."""


class PlanItemConflictError(PlanItemCreationError):
    """La creación contradice el estado vigente del planner."""

    def __init__(self, code, message, conflicts=None):
        super().__init__(message)
        self.code = code
        self.conflicts = conflicts


class PlanItemCreationUnavailableError(PlanItemCreationError):
    """PostgreSQL no pudo completar la creación."""


def _invalid(message):
    raise PlanItemValidationError(message)


def _today():
    return date.today()


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


def _slot_id(value):
    if not isinstance(value, str):
        _invalid("Cada GenerationSlot requiere un UUID v4 válido.")
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError):
        _invalid("Cada GenerationSlot requiere un UUID v4 válido.")
    if parsed.version != 4 or str(parsed) != value:
        _invalid("Cada GenerationSlot requiere un UUID v4 canónico.")
    return value


def _time_ranges_overlap(first, second):
    return (
        first["startTime"] < second["endTime"]
        and first["endTime"] > second["startTime"]
    )


def _reject_group_overlaps(items, group_key):
    grouped = {}
    for item in items:
        group = grouped.setdefault(group_key(item), [])
        if any(_time_ranges_overlap(item, candidate) for candidate in group):
            _invalid("Los horarios de una misma fecha de generación no pueden solaparse.")
        group.append(item)


def _validate_unique_slot_ids(items):
    slot_ids = [item["id"] for item in items]
    if len(set(slot_ids)) != len(slot_ids):
        _invalid("Los UUID de GenerationSlot deben ser únicos en el payload.")


def _normalize_excluded_dates(values, field_name):
    if not isinstance(values, list):
        _invalid(f"{field_name} debe ser una lista.")
    normalized = [_date_string(value, field_name) for value in values]
    if len(set(normalized)) != len(normalized):
        _invalid(f"{field_name} debe contener fechas únicas.")
    return sorted(normalized)


def _generation_controls(config, normalized):
    if "excludedDates" in config:
        normalized_dates = _normalize_excluded_dates(
            config["excludedDates"], "excludedDates"
        )
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
        "slots",
    }
    _require_exact_fields(
        config, required, {"excludedDates", "stoppedFromDate"}, "generationConfig"
    )
    normalized = {"mode": "weekly"}
    _recurring_range(config, normalized)

    slots = config["slots"]
    if not isinstance(slots, list) or not slots:
        _invalid("weekly requiere al menos un GenerationSlot.")
    normalized_slots = []
    for slot in slots:
        _require_exact_fields(
            slot,
            {"id", "isoWeekday", "startTime", "endTime"},
            {"excludedDates"},
            "GenerationSlot weekly",
        )
        weekday = slot["isoWeekday"]
        if (
            isinstance(weekday, bool)
            or not isinstance(weekday, int)
            or weekday < 1
            or weekday > 7
        ):
            _invalid("Cada slot weekly requiere isoWeekday entre 1 y 7.")
        start_time, end_time = _time_range(
            slot["startTime"], slot["endTime"], "startTime", "endTime"
        )
        normalized_slot = {
            "id": _slot_id(slot["id"]),
            "isoWeekday": weekday,
            "startTime": start_time,
            "endTime": end_time,
        }
        if "excludedDates" in slot:
            excluded_dates = _normalize_excluded_dates(
                slot["excludedDates"], "GenerationSlot.excludedDates"
            )
            if excluded_dates:
                normalized_slot["excludedDates"] = excluded_dates
        normalized_slots.append(normalized_slot)
    _validate_unique_slot_ids(normalized_slots)
    _reject_group_overlaps(normalized_slots, lambda slot: slot["isoWeekday"])
    normalized["slots"] = sorted(
        normalized_slots,
        key=lambda slot: (
            slot["isoWeekday"],
            slot["startTime"],
            slot["endTime"],
            slot["id"],
        ),
    )
    return _generation_controls(config, normalized)


def _interval_config(config):
    required = {
        "mode",
        "startDate",
        "endDate",
        "indefinite",
        "intervalDays",
        "slots",
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
    slots = config["slots"]
    if not isinstance(slots, list) or not slots:
        _invalid("interval_days requiere al menos un GenerationSlot.")
    normalized_slots = []
    for slot in slots:
        _require_exact_fields(
            slot,
            {"id", "startTime", "endTime"},
            {"excludedDates"},
            "GenerationSlot interval_days",
        )
        start_time, end_time = _time_range(
            slot["startTime"], slot["endTime"], "startTime", "endTime"
        )
        normalized_slot = {
            "id": _slot_id(slot["id"]),
            "startTime": start_time,
            "endTime": end_time,
        }
        if "excludedDates" in slot:
            excluded_dates = _normalize_excluded_dates(
                slot["excludedDates"], "GenerationSlot.excludedDates"
            )
            if excluded_dates:
                normalized_slot["excludedDates"] = excluded_dates
        normalized_slots.append(normalized_slot)
    _validate_unique_slot_ids(normalized_slots)
    _reject_group_overlaps(normalized_slots, lambda _slot: "interval_days")
    normalized["slots"] = sorted(
        normalized_slots,
        key=lambda slot: (slot["startTime"], slot["endTime"], slot["id"]),
    )
    return _generation_controls(config, normalized)


def _manual_dates_config(config):
    _require_exact_fields(
        config,
        {"mode", "entries"},
        {"stoppedFromDate"},
        "generationConfig",
    )
    entries = config["entries"]
    if not isinstance(entries, list) or not entries:
        _invalid("manual_dates requiere al menos una entry.")
    normalized_entries = []
    for entry in entries:
        _require_exact_fields(
            entry, {"id", "date", "startTime", "endTime"}, set(), "entry"
        )
        start_time, end_time = _time_range(
            entry["startTime"], entry["endTime"], "startTime", "endTime"
        )
        normalized_entries.append(
            {
                "id": _slot_id(entry["id"]),
                "date": _date_string(entry["date"], "entry.date"),
                "startTime": start_time,
                "endTime": end_time,
            }
        )
    _validate_unique_slot_ids(normalized_entries)
    _reject_group_overlaps(normalized_entries, lambda entry: entry["date"])
    normalized = {
        "mode": "manual_dates",
        "entries": sorted(
            normalized_entries,
            key=lambda entry: (
                entry["date"],
                entry["startTime"],
                entry["endTime"],
                entry["id"],
            ),
        ),
    }
    if "stoppedFromDate" in config:
        normalized["stoppedFromDate"] = _date_string(
            config["stoppedFromDate"], "stoppedFromDate"
        )
    return normalized


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


def _normalize_priority_override(value):
    _require_exact_fields(
        value,
        {"confirmedOccurrenceIds"},
        set(),
        "priorityOverride",
    )
    occurrence_ids = value["confirmedOccurrenceIds"]
    if not isinstance(occurrence_ids, list):
        _invalid("confirmedOccurrenceIds debe ser una lista.")
    normalized = []
    for occurrence_id in occurrence_ids:
        if not isinstance(occurrence_id, str):
            _invalid("Cada confirmedOccurrenceId debe ser un UUID válido.")
        try:
            parsed = UUID(occurrence_id)
        except (ValueError, AttributeError):
            _invalid("Cada confirmedOccurrenceId debe ser un UUID válido.")
        if str(parsed) != occurrence_id:
            _invalid("Cada confirmedOccurrenceId debe ser un UUID canónico.")
        normalized.append(occurrence_id)
    if len(set(normalized)) != len(normalized):
        _invalid("confirmedOccurrenceIds no admite IDs duplicados.")
    return frozenset(normalized)


def validate_plan_item_command(payload):
    """Separa el PlanItem canónico de la metadata opcional de la request."""
    if not isinstance(payload, dict):
        _invalid("El cuerpo JSON debe ser un objeto.")
    plan_item_payload = dict(payload)
    priority_override = plan_item_payload.pop("priorityOverride", None)
    normalized = validate_plan_item_payload(plan_item_payload)
    confirmed_ids = (
        None
        if priority_override is None
        else _normalize_priority_override(priority_override)
    )
    return normalized, confirmed_ids


def _overlaps(first, second):
    return occurrence_items_overlap(first, second)


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
        "id": str(row["id"]),
        "planItemId": str(row["plan_item_id"]),
        "date": occurrence_date.isoformat(),
        "startTime": start_time.strftime("%H:%M"),
        "endTime": end_time.strftime("%H:%M"),
        "status": row["status"],
    }


def _current_conflicts(drafts, occurrences, rows):
    conflicts = []
    for row in rows:
        existing = _existing_occurrence(row)
        source = next(
            (
                occurrence
                for draft, occurrence in zip(drafts, occurrences, strict=True)
                if _overlaps(draft, existing)
            ),
            None,
        )
        if source is not None:
            conflicts.append((row, existing, source))
    return conflicts


def _public_conflicts(conflicts):
    return [
        {
            "occurrenceId": existing["id"],
            "planItemId": existing["planItemId"],
            "date": existing["date"],
            "startTime": existing["startTime"],
            "endTime": existing["endTime"],
            "status": existing["status"],
        }
        for _row, existing, _source in conflicts
    ]


def _validate_existing_conflicts(
    plan_item,
    drafts,
    occurrences,
    rows,
    confirmed_occurrence_ids,
):
    conflicts = _current_conflicts(drafts, occurrences, rows)
    if not conflicts:
        return []
    if any(row["status"] == "completed" for row, _existing, _source in conflicts):
        raise PlanItemConflictError(
            "completed_conflict",
            "El intervalo contiene un registro completado y protegido.",
        )
    subtype = plan_item.get("activityType") or plan_item.get("habitType")
    candidate_priority = scheduling_priority(plan_item["kind"], subtype)
    if any(
        candidate_priority <= scheduling_priority(row["kind"], row["subtype"])
        for row, _existing, _source in conflicts
    ):
        raise PlanItemConflictError(
            "priority_conflict",
            "La prioridad del PlanItem no permite desplazar los conflictos.",
        )
    current_ids = {existing["id"] for _row, existing, _source in conflicts}
    if (
        confirmed_occurrence_ids is None
        or not current_ids.issubset(confirmed_occurrence_ids)
    ):
        raise PlanItemConflictError(
            "priority_override_required",
            "La creación requiere confirmar un desplazamiento por prioridad.",
            _public_conflicts(conflicts),
        )
    raise PlanItemConflictError(
        "segment_conflict_resolution_unavailable",
        "El conflicto requiere la futura resolución basada en segmentos.",
        _public_conflicts(conflicts),
    )


def _assign_ids(plan_item, drafts, current_date, uuid_factory):
    plan_item_id = str(uuid_factory())
    persisted_plan_item = {"id": plan_item_id, **plan_item}
    occurrences = []
    for draft in drafts:
        occurrence_id = str(uuid_factory())
        segment = {
            "id": str(uuid_factory()),
            "occurrenceId": occurrence_id,
            "startTime": draft["startTime"],
            "endTime": draft["endTime"],
            "status": draft["status"],
        }
        temporal_phase = temporal_phase_for_date(
            date.fromisoformat(draft["date"]),
            current_date,
            HISTORY_EDIT_WINDOW_DAYS,
        )
        occurrences.append(
            {
                "id": occurrence_id,
                **draft,
                "status": derive_occurrence_status([segment], temporal_phase),
                "planItemId": plan_item_id,
                "segments": [segment],
            }
        )
    return persisted_plan_item, occurrences


def _validate_generated_ids(plan_item, occurrences):
    # Defensa local para factories inyectadas en pruebas; PostgreSQL recibe UUID reales.
    ids = [
        plan_item["id"],
        *(item["id"] for item in occurrences),
        *(
            segment["id"]
            for occurrence in occurrences
            for segment in occurrence["segments"]
        ),
    ]
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
    normalized, confirmed_occurrence_ids = validate_plan_item_command(payload)
    current_date = reference_date or _today()
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
    plan_item, occurrences = _assign_ids(
        normalized, drafts, current_date, uuid_factory
    )
    _validate_generated_ids(plan_item, occurrences)

    try:
        with database.get_connection() as connection:
            connection.isolation_level = IsolationLevel.SERIALIZABLE
            with connection.transaction():
                blocking_rows = plan_item_repository.list_blocking_occurrences(
                    connection,
                    sorted({draft["date"] for draft in drafts}),
                )
                _validate_existing_conflicts(
                    plan_item,
                    drafts,
                    occurrences,
                    blocking_rows,
                    confirmed_occurrence_ids,
                )
                plan_item_repository.insert_plan_item_graph(
                    connection, plan_item, occurrences
                )
    except PlanItemConflictError:
        raise
    except (
        database.DatabaseConnectionError,
        plan_item_repository.PlanItemRepositoryError,
        psycopg.Error,
    ):
        raise PlanItemCreationUnavailableError(
            "No se pudo crear el PlanItem persistente."
        ) from None

    return {"planItem": plan_item, "occurrences": occurrences}
