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
CONFLICT_REASONS = frozenset({"priority_override", "user_forced_override"})
ORIGIN_REASONS = frozenset({"conflict_insertion"})
LAST_CONFLICT_ACTIONS = frozenset({"conflict_insertion", "conflict_move"})
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


def _slot_uuid_string(value, field_name):
    slot_id = _uuid_string(value, field_name)
    if value.version != 4:
        _inconsistent(f"{field_name} no contiene un UUID v4.")
    return slot_id


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


def _rows_by_slot(rows):
    grouped = {}
    for row in rows:
        slot_id = _slot_uuid_string(row["slot_id"], "slot_id")
        grouped.setdefault(slot_id, []).append(row)
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
    if config["mode"] == "manual_dates" and excluded_rows:
        _inconsistent("manual_dates no puede representar excludedDates globales.")
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


def _ranges_overlap(first, second):
    return (
        first["startTime"] < second["endTime"]
        and first["endTime"] > second["startTime"]
    )


def _validate_slot_overlaps(items, group_key):
    grouped = {}
    for item in items:
        group = grouped.setdefault(group_key(item), [])
        if any(_ranges_overlap(item, candidate) for candidate in group):
            _inconsistent("La configuración contiene GenerationSlots solapados.")
        group.append(item)


def _base_slot(row):
    start_time, end_time = _time_range(
        row["start_time"], row["end_time"], "start_time", "end_time"
    )
    return {
        "id": _slot_uuid_string(row["id"], "generation_slots.id"),
        "startTime": start_time,
        "endTime": end_time,
    }


def _add_slot_exclusions(slot, excluded_rows_by_slot, allow):
    rows = excluded_rows_by_slot.get(slot["id"], [])
    if rows and not allow:
        _inconsistent("manual_dates no puede representar exclusiones por slot.")
    excluded_dates = [
        _date_string(row["excluded_date"], "excluded_date") for row in rows
    ]
    if len(set(excluded_dates)) != len(excluded_dates):
        _inconsistent("Un GenerationSlot contiene excludedDates duplicadas.")
    if excluded_dates:
        slot["excludedDates"] = sorted(excluded_dates)
    return slot


def _weekly_config(
    config_row,
    slot_rows,
    weekday_rows_by_slot,
    date_rows_by_slot,
    excluded_rows_by_slot,
):
    if not slot_rows:
        _inconsistent("Una configuración weekly requiere al menos un slot.")
    if config_row["interval_days"] is not None:
        _inconsistent("Una configuración weekly no puede tener intervalDays.")

    start_date, end_date, indefinite = _recurring_date_range(config_row)
    slots = []
    for slot_row in slot_rows:
        slot = _add_slot_exclusions(
            _base_slot(slot_row), excluded_rows_by_slot, True
        )
        weekday_rows = weekday_rows_by_slot.get(slot["id"], [])
        date_rows = date_rows_by_slot.get(slot["id"], [])
        if len(weekday_rows) != 1:
            _inconsistent("Cada slot weekly requiere exactamente un weekday.")
        if date_rows:
            _inconsistent("Un slot weekly no puede tener date detail.")
        row = weekday_rows[0]
        weekday = row["iso_weekday"]
        if isinstance(weekday, bool) or not isinstance(weekday, int):
            _inconsistent("iso_weekday no contiene un entero válido.")
        if weekday < 1 or weekday > 7:
            _inconsistent("iso_weekday debe estar entre 1 y 7.")
        slot["isoWeekday"] = weekday
        slots.append(slot)
    _validate_slot_overlaps(slots, lambda slot: slot["isoWeekday"])
    slots.sort(
        key=lambda slot: (
            slot["isoWeekday"],
            slot["startTime"],
            slot["endTime"],
            slot["id"],
        )
    )
    return {
        "mode": "weekly",
        "startDate": start_date,
        "endDate": end_date,
        "indefinite": indefinite,
        "slots": slots,
    }


def _interval_days_config(
    config_row,
    slot_rows,
    weekday_rows_by_slot,
    date_rows_by_slot,
    excluded_rows_by_slot,
):
    if not slot_rows:
        _inconsistent("Una configuración interval_days requiere al menos un slot.")
    interval_days = config_row["interval_days"]
    if (
        isinstance(interval_days, bool)
        or not isinstance(interval_days, int)
        or interval_days < 1
    ):
        _inconsistent("intervalDays debe ser un entero positivo.")
    start_date, end_date, indefinite = _recurring_date_range(config_row)
    slots = []
    for row in slot_rows:
        slot = _add_slot_exclusions(
            _base_slot(row), excluded_rows_by_slot, True
        )
        if weekday_rows_by_slot.get(slot["id"]) or date_rows_by_slot.get(slot["id"]):
            _inconsistent("Un slot interval_days no puede tener detalles de fecha.")
        slots.append(slot)
    _validate_slot_overlaps(slots, lambda _slot: "interval_days")
    slots.sort(key=lambda slot: (slot["startTime"], slot["endTime"], slot["id"]))
    return {
        "mode": "interval_days",
        "startDate": start_date,
        "endDate": end_date,
        "indefinite": indefinite,
        "intervalDays": interval_days,
        "slots": slots,
    }


def _manual_dates_config(
    config_row,
    slot_rows,
    weekday_rows_by_slot,
    date_rows_by_slot,
    excluded_rows_by_slot,
):
    if not slot_rows:
        _inconsistent("Una configuración manual_dates requiere al menos una entry.")
    if any(
        config_row[field] is not None
        for field in ("start_date", "end_date", "interval_days")
    ) or config_row["indefinite"] is not False:
        _inconsistent("La fila manual_dates contiene controles recurrentes.")

    entries = []
    for slot_row in slot_rows:
        entry = _add_slot_exclusions(
            _base_slot(slot_row), excluded_rows_by_slot, False
        )
        weekday_rows = weekday_rows_by_slot.get(entry["id"], [])
        date_rows = date_rows_by_slot.get(entry["id"], [])
        if weekday_rows:
            _inconsistent("Un slot manual_dates no puede tener weekday detail.")
        if len(date_rows) != 1:
            _inconsistent("Cada slot manual_dates requiere exactamente una fecha.")
        entry["date"] = _date_string(date_rows[0]["entry_date"], "entry_date")
        entries.append(entry)
    _validate_slot_overlaps(entries, lambda entry: entry["date"])
    entries.sort(
        key=lambda entry: (
            entry["date"], entry["startTime"], entry["endTime"], entry["id"]
        )
    )
    return {"mode": "manual_dates", "entries": entries}


def _build_generation_config(
    config_row,
    slot_rows,
    weekday_rows_by_slot,
    date_rows_by_slot,
    slot_excluded_rows_by_slot,
    excluded_rows,
):
    mode = config_row["mode"]
    if mode == "weekly":
        config = _weekly_config(
            config_row,
            slot_rows,
            weekday_rows_by_slot,
            date_rows_by_slot,
            slot_excluded_rows_by_slot,
        )
    elif mode == "interval_days":
        config = _interval_days_config(
            config_row,
            slot_rows,
            weekday_rows_by_slot,
            date_rows_by_slot,
            slot_excluded_rows_by_slot,
        )
    elif mode == "manual_dates":
        config = _manual_dates_config(
            config_row,
            slot_rows,
            weekday_rows_by_slot,
            date_rows_by_slot,
            slot_excluded_rows_by_slot,
        )
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


def _build_segments(rows, occurrences_by_id):
    segments_by_occurrence = {
        occurrence_id: [] for occurrence_id in occurrences_by_id
    }
    segment_ids = set()

    for row in rows:
        segment_id = _uuid_string(row["id"], "occurrence_segments.id")
        if segment_id in segment_ids:
            _inconsistent("Existen IDs de OccurrenceSegment duplicados.")
        segment_ids.add(segment_id)

        occurrence_id = _uuid_string(
            row["occurrence_id"], "occurrence_segments.occurrence_id"
        )
        parent = occurrences_by_id.get(occurrence_id)
        if parent is None:
            _inconsistent(
                "Un OccurrenceSegment referencia una Occurrence inexistente."
            )

        status = row["status"]
        if status not in OCCURRENCE_STATUSES:
            _inconsistent("Un OccurrenceSegment contiene un status no válido.")
        start_time, end_time = _time_range(
            row["start_time"],
            row["end_time"],
            "occurrence_segments.start_time",
            "occurrence_segments.end_time",
        )
        if start_time < parent["startTime"] or end_time > parent["endTime"]:
            _inconsistent(
                "Un OccurrenceSegment queda fuera del rango de su Occurrence."
            )
        segments_by_occurrence[occurrence_id].append(
            {
                "id": segment_id,
                "startTime": start_time,
                "endTime": end_time,
                "status": status,
            }
        )

    for occurrence_id, segments in segments_by_occurrence.items():
        if not segments:
            _inconsistent("Una Occurrence no tiene OccurrenceSegments persistidos.")
        segments.sort(
            key=lambda segment: (
                segment["startTime"],
                segment["endTime"],
                segment["id"],
            )
        )
        occurrences_by_id[occurrence_id]["segments"] = segments


def _optional_metadata(occurrence, row):
    origin_reason = row["origin_reason"]
    if origin_reason is not None:
        if origin_reason not in ORIGIN_REASONS:
            _inconsistent("Una Occurrence contiene un originReason no válido.")
        occurrence["originReason"] = origin_reason

    last_conflict_action = row["last_conflict_action"]
    if last_conflict_action is not None:
        if last_conflict_action not in LAST_CONFLICT_ACTIONS:
            _inconsistent(
                "Una Occurrence contiene un lastConflictAction no válido."
            )
        occurrence["lastConflictAction"] = last_conflict_action


def _build_occurrences(rows, segment_rows, plan_item_ids, slot_owners):
    occurrence_ids = []
    for row in rows:
        occurrence_id = _uuid_string(row["id"], "occurrences.id")
        if occurrence_id in occurrence_ids:
            _inconsistent("Existen IDs de Occurrence duplicados.")
        occurrence_ids.append(occurrence_id)
    known_occurrence_ids = set(occurrence_ids)

    occurrences = []
    occurrences_by_id = {}
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
        generation_slot_value = row["source_generation_slot_id"]
        if generation_slot_value is not None:
            generation_slot_id = _slot_uuid_string(
                generation_slot_value,
                "occurrences.source_generation_slot_id",
            )
            if slot_owners.get(generation_slot_id) != plan_item_id:
                _inconsistent(
                    "Una Occurrence referencia un GenerationSlot de otro PlanItem."
                )
            occurrence["sourceGenerationSlotId"] = generation_slot_id
        reason = row["conflict_reason"]
        source_value = row["source_occurrence_id"]
        if reason is None and source_value is None:
            pass
        elif reason in CONFLICT_REASONS and source_value is not None:
            source_id = _uuid_string(
                source_value, "occurrences.source_occurrence_id"
            )
            if source_id == occurrence_id or source_id not in known_occurrence_ids:
                _inconsistent("Una Occurrence tiene un conflictContext inválido.")
            conflict_context = {
                "reason": reason,
                "sourceOccurrenceId": source_id,
            }
            occurrence["conflictContext"] = conflict_context
            if reason == PRIORITY_OVERRIDE_REASON:
                # Alias transitorio para el frontend pre-OccurrenceSegment. La
                # única fuente canónica es conflictContext y el alias desaparece
                # cuando ese consumidor migre al contrato nuevo.
                occurrence["statusContext"] = dict(conflict_context)
        else:
            _inconsistent("Una Occurrence tiene un conflictContext incompleto.")
        _optional_metadata(occurrence, row)
        occurrences.append(occurrence)
        occurrences_by_id[occurrence_id] = occurrence

    _build_segments(segment_rows, occurrences_by_id)

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

    slots_by_plan_item = {}
    slot_owners = {}
    for slot_row in rows["generation_slots"]:
        slot_id = _slot_uuid_string(slot_row["id"], "generation_slots.id")
        if slot_id in slot_owners:
            _inconsistent("Existen IDs de GenerationSlot duplicados.")
        plan_item_id = _uuid_string(
            slot_row["plan_item_id"], "generation_slots.plan_item_id"
        )
        slot_owners[slot_id] = plan_item_id
        slots_by_plan_item.setdefault(plan_item_id, []).append(slot_row)

    weekdays_by_slot = _rows_by_slot(rows["generation_slot_weekdays"])
    dates_by_slot = _rows_by_slot(rows["generation_slot_dates"])
    slot_exclusions_by_slot = _rows_by_slot(
        rows["generation_slot_excluded_dates"]
    )
    detail_slot_ids = (
        set(weekdays_by_slot)
        | set(dates_by_slot)
        | set(slot_exclusions_by_slot)
    )
    if detail_slot_ids - set(slot_owners):
        _inconsistent("Existen detalles asociados a un GenerationSlot inexistente.")

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
            slots_by_plan_item.get(plan_item_id, []),
            weekdays_by_slot,
            dates_by_slot,
            slot_exclusions_by_slot,
            excluded_by_plan_item.get(plan_item_id, []),
        )
        plan_items.append(_build_plan_item(plan_item_row, generation_config))

    related_ids = (
        set(config_by_plan_item)
        | set(slots_by_plan_item)
        | set(excluded_by_plan_item)
    )
    if related_ids - plan_item_ids:
        _inconsistent("Existen datos de generación sin un PlanItem correspondiente.")

    return {
        "planItems": plan_items,
        "occurrences": _build_occurrences(
            rows["occurrences"],
            rows["occurrence_segments"],
            plan_item_ids,
            slot_owners,
        ),
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
