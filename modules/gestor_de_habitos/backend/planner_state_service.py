"""Reconstrucción del contrato canónico que consume el planner frontend."""

from datetime import date, datetime, time
from uuid import UUID

from repositories import planner_state_repository


ACTIVITY_TYPES = frozenset({"anchor", "periodic", "event", "unexpected"})
HABIT_TYPES = frozenset({"scheduled"})
OCCURRENCE_STATUSES = frozenset(
    {
        "pending",
        "in_progress",
        "completed",
        "not_completed",
        "not_finished",
        "cancelled",
    }
)
PRIORITY_OVERRIDE_REASON = "priority_override"


class PlannerStateError(RuntimeError):
    """Error seguro compartido por la reconstrucción del planner."""


class PlannerStateUnavailableError(PlannerStateError):
    """PostgreSQL no pudo proporcionar las filas necesarias."""


class PlannerStateConsistencyError(PlannerStateError):
    """Las filas persistidas no forman un estado de dominio válido."""


def _inconsistent(message):
    raise PlannerStateConsistencyError(message)


def _uuid_string(value, field_name):
    if not isinstance(value, UUID):
        _inconsistent(f"{field_name} no contiene un UUID válido.")
    return str(value)


def _date_string(value, field_name):
    if isinstance(value, datetime) or not isinstance(value, date):
        _inconsistent(f"{field_name} no contiene una fecha válida.")
    return value.isoformat()


def _time_string(value, field_name):
    if not isinstance(value, time) or value.second != 0 or value.microsecond != 0:
        _inconsistent(f"{field_name} no puede representarse como HH:MM.")
    return value.strftime("%H:%M")


def _time_range(start_value, end_value, start_field, end_field):
    start_time = _time_string(start_value, start_field)
    end_time = _time_string(end_value, end_field)
    if start_time >= end_time:
        _inconsistent("Una hora final no puede ser anterior o igual a la inicial.")
    return start_time, end_time


def _rows_by_plan_item(rows):
    grouped = {}
    for row in rows:
        plan_item_id = _uuid_string(row["plan_item_id"], "plan_item_id")
        grouped.setdefault(plan_item_id, []).append(row)
    return grouped


def _recurring_date_range(config_row):
    indefinite = config_row["indefinite"]
    if not isinstance(indefinite, bool):
        _inconsistent("indefinite no contiene un booleano válido.")

    start_date = _date_string(config_row["start_date"], "start_date")
    end_value = config_row["end_date"]
    if indefinite:
        if end_value is not None:
            _inconsistent("Una configuración indefinida no puede tener endDate.")
        end_date = None
    else:
        if end_value is None:
            _inconsistent("Una configuración finita requiere endDate.")
        end_date = _date_string(end_value, "end_date")
        if end_date < start_date:
            _inconsistent("endDate no puede ser anterior a startDate.")
    return start_date, end_date, indefinite


def _generation_controls(config, config_row, excluded_rows):
    excluded_dates = [
        _date_string(row["excluded_date"], "excluded_date")
        for row in excluded_rows
    ]
    if len(set(excluded_dates)) != len(excluded_dates):
        _inconsistent("Una configuración contiene excludedDates duplicadas.")
    if excluded_dates:
        config["excludedDates"] = sorted(excluded_dates)

    stopped_from_date = config_row["stopped_from_date"]
    if stopped_from_date is not None:
        config["stoppedFromDate"] = _date_string(
            stopped_from_date, "stopped_from_date"
        )
    return config


def _weekly_config(config_row, weekday_rows, entry_rows):
    if entry_rows:
        _inconsistent("Una configuración weekly no puede tener entries manuales.")
    if not weekday_rows:
        _inconsistent("Una configuración weekly requiere al menos un weekday.")
    if config_row["interval_days"] is not None:
        _inconsistent("Una configuración weekly no puede tener intervalDays.")

    start_date, end_date, indefinite = _recurring_date_range(config_row)
    weekdays = []
    weekday_time_overrides = {}
    for row in weekday_rows:
        weekday = row["iso_weekday"]
        if isinstance(weekday, bool) or not isinstance(weekday, int):
            _inconsistent("iso_weekday no contiene un entero válido.")
        if weekday < 1 or weekday > 7 or weekday in weekdays:
            _inconsistent("Los weekdays deben ser únicos y estar entre 1 y 7.")
        weekdays.append(weekday)

        override_start = row["override_start_time"]
        override_end = row["override_end_time"]
        if (override_start is None) != (override_end is None):
            _inconsistent("Un override semanal requiere ambas horas.")
        if override_start is not None:
            start_time, end_time = _time_range(
                override_start,
                override_end,
                "override_start_time",
                "override_end_time",
            )
            weekday_time_overrides[str(weekday)] = {
                "startTime": start_time,
                "endTime": end_time,
            }

    default_start_time, default_end_time = _time_range(
        config_row["default_start_time"],
        config_row["default_end_time"],
        "default_start_time",
        "default_end_time",
    )
    return {
        "mode": "weekly",
        "startDate": start_date,
        "endDate": end_date,
        "indefinite": indefinite,
        "weekdays": sorted(weekdays),
        "defaultStartTime": default_start_time,
        "defaultEndTime": default_end_time,
        "weekdayTimeOverrides": weekday_time_overrides,
    }


def _interval_days_config(config_row, weekday_rows, entry_rows):
    if weekday_rows or entry_rows:
        _inconsistent(
            "Una configuración interval_days no puede tener weekdays ni entries."
        )
    interval_days = config_row["interval_days"]
    if (
        isinstance(interval_days, bool)
        or not isinstance(interval_days, int)
        or interval_days < 1
    ):
        _inconsistent("intervalDays debe ser un entero positivo.")
    start_date, end_date, indefinite = _recurring_date_range(config_row)
    default_start_time, default_end_time = _time_range(
        config_row["default_start_time"],
        config_row["default_end_time"],
        "default_start_time",
        "default_end_time",
    )
    return {
        "mode": "interval_days",
        "startDate": start_date,
        "endDate": end_date,
        "indefinite": indefinite,
        "intervalDays": interval_days,
        "defaultStartTime": default_start_time,
        "defaultEndTime": default_end_time,
    }


def _manual_dates_config(config_row, weekday_rows, entry_rows):
    if weekday_rows:
        _inconsistent("Una configuración manual_dates no puede tener weekdays.")
    if not entry_rows:
        _inconsistent("Una configuración manual_dates requiere al menos una entry.")
    if any(
        config_row[field] is not None
        for field in (
            "start_date",
            "end_date",
            "default_start_time",
            "default_end_time",
            "interval_days",
        )
    ) or config_row["indefinite"] is not False:
        _inconsistent("La fila manual_dates contiene controles recurrentes.")

    entries = []
    for row in entry_rows:
        start_time, end_time = _time_range(
            row["start_time"], row["end_time"], "start_time", "end_time"
        )
        entries.append(
            {
                "date": _date_string(row["entry_date"], "entry_date"),
                "startTime": start_time,
                "endTime": end_time,
            }
        )
    entries.sort(key=lambda entry: (entry["date"], entry["startTime"], entry["endTime"]))
    return {"mode": "manual_dates", "entries": entries}


def _build_generation_config(config_row, weekday_rows, entry_rows, excluded_rows):
    mode = config_row["mode"]
    if mode == "weekly":
        config = _weekly_config(config_row, weekday_rows, entry_rows)
    elif mode == "interval_days":
        config = _interval_days_config(config_row, weekday_rows, entry_rows)
    elif mode == "manual_dates":
        config = _manual_dates_config(config_row, weekday_rows, entry_rows)
    else:
        _inconsistent("La configuración tiene un mode no soportado.")
    return _generation_controls(config, config_row, excluded_rows)


def _build_plan_item(row, generation_config):
    name = row["name"]
    if not isinstance(name, str) or not name.strip() or len(name) > 80:
        _inconsistent("Un PlanItem contiene un nombre no válido.")
    plan_item = {
        "id": _uuid_string(row["id"], "plan_items.id"),
        "name": name,
        "kind": row["kind"],
        "generationConfig": generation_config,
    }
    subtype = row["subtype"]
    if row["kind"] == "activity" and subtype in ACTIVITY_TYPES:
        plan_item["activityType"] = subtype
    elif row["kind"] == "habit" and subtype in HABIT_TYPES:
        plan_item["habitType"] = subtype
    else:
        _inconsistent("Un PlanItem contiene una clasificación no válida.")
    return plan_item


def _build_occurrences(rows, plan_item_ids):
    occurrence_ids = []
    for row in rows:
        occurrence_id = _uuid_string(row["id"], "occurrences.id")
        if occurrence_id in occurrence_ids:
            _inconsistent("Existen IDs de Occurrence duplicados.")
        occurrence_ids.append(occurrence_id)
    known_occurrence_ids = set(occurrence_ids)

    occurrences = []
    for row, occurrence_id in zip(rows, occurrence_ids):
        plan_item_id = _uuid_string(
            row["plan_item_id"], "occurrences.plan_item_id"
        )
        if plan_item_id not in plan_item_ids:
            _inconsistent("Una Occurrence referencia un PlanItem inexistente.")
        status = row["status"]
        if status not in OCCURRENCE_STATUSES:
            _inconsistent("Una Occurrence contiene un status no válido.")

        start_time, end_time = _time_range(
            row["start_time"], row["end_time"], "start_time", "end_time"
        )
        occurrence = {
            "id": occurrence_id,
            "planItemId": plan_item_id,
            "date": _date_string(row["occurrence_date"], "occurrence_date"),
            "startTime": start_time,
            "endTime": end_time,
            "status": status,
        }
        reason = row["status_reason"]
        source_value = row["source_occurrence_id"]
        if reason is None and source_value is None:
            pass
        elif reason == PRIORITY_OVERRIDE_REASON and source_value is not None:
            if status not in {"cancelled", "not_finished"}:
                _inconsistent("Un statusContext requiere un status desplazado.")
            source_id = _uuid_string(
                source_value, "occurrences.source_occurrence_id"
            )
            if source_id == occurrence_id or source_id not in known_occurrence_ids:
                _inconsistent("Una Occurrence tiene un statusContext inválido.")
            occurrence["statusContext"] = {
                "reason": PRIORITY_OVERRIDE_REASON,
                "sourceOccurrenceId": source_id,
            }
        else:
            _inconsistent("Una Occurrence tiene un statusContext incompleto.")
        occurrences.append(occurrence)

    occurrences.sort(
        key=lambda occurrence: (
            occurrence["date"],
            occurrence["startTime"],
            occurrence["endTime"],
            occurrence["id"],
        )
    )
    return occurrences


def build_planner_state(rows):
    """Convierte filas PostgreSQL en el estado exacto esperado por el frontend."""
    config_by_plan_item = {}
    for config_row in rows["generation_configs"]:
        plan_item_id = _uuid_string(
            config_row["plan_item_id"], "generation_configs.plan_item_id"
        )
        if plan_item_id in config_by_plan_item:
            _inconsistent("Un PlanItem tiene varias generationConfig.")
        config_by_plan_item[plan_item_id] = config_row

    weekdays_by_plan_item = _rows_by_plan_item(rows["generation_weekdays"])
    entries_by_plan_item = _rows_by_plan_item(rows["generation_date_entries"])
    excluded_by_plan_item = _rows_by_plan_item(rows["generation_excluded_dates"])

    plan_items = []
    plan_item_ids = set()
    for plan_item_row in rows["plan_items"]:
        plan_item_id = _uuid_string(plan_item_row["id"], "plan_items.id")
        if plan_item_id in plan_item_ids:
            _inconsistent("Existen IDs de PlanItem duplicados.")
        plan_item_ids.add(plan_item_id)
        config_row = config_by_plan_item.get(plan_item_id)
        if config_row is None:
            _inconsistent("Un PlanItem no tiene generationConfig persistida.")
        generation_config = _build_generation_config(
            config_row,
            weekdays_by_plan_item.get(plan_item_id, []),
            entries_by_plan_item.get(plan_item_id, []),
            excluded_by_plan_item.get(plan_item_id, []),
        )
        plan_items.append(_build_plan_item(plan_item_row, generation_config))

    related_ids = (
        set(config_by_plan_item)
        | set(weekdays_by_plan_item)
        | set(entries_by_plan_item)
        | set(excluded_by_plan_item)
    )
    if related_ids - plan_item_ids:
        _inconsistent("Existen datos de generación sin un PlanItem correspondiente.")

    return {
        "planItems": plan_items,
        "occurrences": _build_occurrences(rows["occurrences"], plan_item_ids),
    }


def get_planner_state():
    """Lee y reconstruye el estado, ocultando detalles privados del repository."""
    try:
        rows = planner_state_repository.read_planner_state_rows()
    except planner_state_repository.PlannerStateRepositoryError:
        raise PlannerStateUnavailableError(
            "No se pudo cargar el estado persistido."
        ) from None
    return build_planner_state(rows)
