"""Apply Week atómico para occurrences persistidas de un PlanItem recurrente."""

from datetime import date, datetime, time, timedelta
import re
from uuid import UUID, uuid4

import psycopg

import database
import occurrence_mutation_service as occurrence_service
import recurring_segment_service as segment_service
from repositories import occurrence_repository
from scheduling_policy import (
    BLOCKING_STATUSES,
    can_delete_occurrence,
    is_frozen_date,
    scheduling_priority,
    time_ranges_overlap,
)


SUPPORTED_MODES = frozenset({"weekly", "interval_days"})
_TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class WeekMutationError(RuntimeError):
    """Error seguro común para la mutación semanal."""


class WeekValidationError(WeekMutationError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class WeekPlanItemNotFoundError(WeekMutationError):
    """El PlanItem solicitado no existe."""


class WeekOccurrenceNotFoundError(WeekMutationError):
    """Una occurrence no existe en el PlanItem y semana solicitados."""


class WeekConflictError(WeekMutationError):
    def __init__(self, code, message, occurrences=None, blockers=None):
        super().__init__(message)
        self.code = code
        self.occurrences = occurrences
        self.blockers = blockers


class WeekConsistencyError(WeekMutationError):
    """Las filas persistidas no forman un estado canónico."""


class WeekUnavailableError(WeekMutationError):
    """PostgreSQL no pudo completar la transacción."""


def _invalid(message, code="invalid_payload"):
    raise WeekValidationError(code, message)


def _today():
    return date.today()


def _identifier(value, field_name):
    if not isinstance(value, str):
        _invalid(f"{field_name} debe ser un UUID válido.", "invalid_identifier")
    try:
        return UUID(value)
    except (ValueError, AttributeError):
        _invalid(f"{field_name} debe ser un UUID válido.", "invalid_identifier")


def _date_value(value, field_name):
    if not isinstance(value, str):
        _invalid(f"{field_name} debe usar YYYY-MM-DD.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        _invalid(f"{field_name} debe ser una fecha válida.")
    if parsed.isoformat() != value:
        _invalid(f"{field_name} debe usar YYYY-MM-DD.")
    return parsed


def _time_value(value, field_name):
    if not isinstance(value, str) or _TIME_PATTERN.fullmatch(value) is None:
        _invalid(f"{field_name} debe usar HH:MM.")
    return value


def _schedule_fields(operation):
    start_time = _time_value(operation["startTime"], "startTime")
    end_time = _time_value(operation["endTime"], "endTime")
    if start_time >= end_time:
        _invalid("endTime debe ser posterior a startTime.")
    return {
        "date": _date_value(operation["date"], "date"),
        "startTime": start_time,
        "endTime": end_time,
    }


def validate_apply_week_payload(payload):
    if not isinstance(payload, dict) or set(payload) != {"anchorDate", "operations"}:
        _invalid("El payload debe contener exactamente anchorDate y operations.")
    anchor_date = _date_value(payload["anchorDate"], "anchorDate")
    operations = payload["operations"]
    if not isinstance(operations, list) or not operations:
        _invalid("operations debe contener al menos una operación.")

    normalized = []
    seen_occurrence_ids = set()
    for operation in operations:
        if not isinstance(operation, dict) or operation.get("type") not in {
            "update",
            "delete",
            "create",
        }:
            _invalid("Cada operación debe tener un type soportado.")
        operation_type = operation["type"]
        if operation_type == "update":
            expected = {"type", "occurrenceId", "date", "startTime", "endTime"}
        elif operation_type == "delete":
            expected = {"type", "occurrenceId"}
        else:
            expected = {"type", "date", "startTime", "endTime"}
        if set(operation) != expected:
            _invalid(f"La operación {operation_type} no cumple el contrato.")

        candidate = {"type": operation_type}
        if operation_type in {"update", "delete"}:
            occurrence_id = _identifier(operation["occurrenceId"], "occurrenceId")
            if occurrence_id in seen_occurrence_ids:
                _invalid("Un occurrenceId solo puede aparecer una vez.")
            seen_occurrence_ids.add(occurrence_id)
            candidate["occurrenceId"] = occurrence_id
        if operation_type in {"update", "create"}:
            candidate.update(_schedule_fields(operation))
        normalized.append(candidate)
    return anchor_date, normalized


def _db_uuid(value, field_name, *, slot=False):
    if not isinstance(value, UUID) or slot and value.version != 4:
        raise WeekConsistencyError(f"{field_name} no contiene un UUID válido.")
    return value


def _db_date(value, field_name):
    if isinstance(value, datetime) or not isinstance(value, date):
        raise WeekConsistencyError(f"{field_name} no contiene una fecha válida.")
    return value


def _db_time(value, field_name):
    if not isinstance(value, time) or value.second != 0 or value.microsecond != 0:
        raise WeekConsistencyError(f"{field_name} no puede representarse como HH:MM.")
    return value.strftime("%H:%M")


def _serialize_occurrence(row, segments):
    try:
        return segment_service.serialize_occurrence(row, segments)
    except segment_service.OccurrenceSegmentConsistencyError as error:
        raise WeekConsistencyError(str(error)) from None


def _validate_plan_item_context(context):
    try:
        occurrence_service._validate_plan_item_context(context)
    except occurrence_service.OccurrenceConsistencyError as error:
        raise WeekConsistencyError(str(error)) from None

    mode = context["mode"]
    if mode == "manual_dates":
        raise WeekConflictError(
            "unsupported_mode",
            "Apply Week no está disponible para manual_dates.",
        )
    if mode not in SUPPORTED_MODES:
        raise WeekConsistencyError("El mode persistido no es válido para Apply Week.")

    start_date = _db_date(context["start_date"], "start_date")
    indefinite = context["indefinite"]
    end_date = context["end_date"]
    if not isinstance(indefinite, bool):
        raise WeekConsistencyError("indefinite no contiene un booleano.")
    if indefinite:
        if end_date is not None:
            raise WeekConsistencyError("Una configuración indefinida contiene end_date.")
    else:
        end_date = _db_date(end_date, "end_date")
        if end_date < start_date:
            raise WeekConsistencyError("La configuración contiene un rango inválido.")
    interval_days = context["interval_days"]
    if mode == "weekly" and interval_days is not None:
        raise WeekConsistencyError("weekly no puede contener interval_days.")
    if mode == "interval_days" and (
        isinstance(interval_days, bool)
        or not isinstance(interval_days, int)
        or interval_days < 1
    ):
        raise WeekConsistencyError("interval_days no contiene un intervalo válido.")
    if context["stopped_from_date"] is not None:
        _db_date(context["stopped_from_date"], "stopped_from_date")


def _validate_slots(mode, slots, plan_item_id, expected_count):
    if len(slots) != expected_count:
        raise WeekConsistencyError("El conteo de GenerationSlots no es coherente.")
    slot_ids = set()
    for slot in slots:
        slot_id = _db_uuid(slot["id"], "generation_slots.id", slot=True)
        if slot_id in slot_ids:
            raise WeekConsistencyError("Existen GenerationSlots duplicados.")
        slot_ids.add(slot_id)
        if _db_uuid(slot["plan_item_id"], "generation_slots.plan_item_id") != plan_item_id:
            raise WeekConsistencyError("Un GenerationSlot pertenece a otro PlanItem.")
        try:
            occurrence_service._validate_slot_shape(mode, slot)
        except occurrence_service.OccurrenceConsistencyError as error:
            raise WeekConsistencyError(str(error)) from None
        start_time = _db_time(slot["start_time"], "generation_slots.start_time")
        end_time = _db_time(slot["end_time"], "generation_slots.end_time")
        if start_time >= end_time:
            raise WeekConsistencyError("Un GenerationSlot tiene horario inválido.")
    return slot_ids


def _validate_week_rows(rows, plan_item_id, slot_ids):
    occurrence_ids = set()
    for row in rows:
        occurrence_id = _db_uuid(row["id"], "occurrences.id")
        if occurrence_id in occurrence_ids:
            raise WeekConsistencyError("Existen IDs de occurrence duplicados.")
        occurrence_ids.add(occurrence_id)
        if _db_uuid(row["plan_item_id"], "occurrences.plan_item_id") != plan_item_id:
            raise WeekConsistencyError("Una occurrence pertenece a otro PlanItem.")
        source_slot_id = row["source_generation_slot_id"]
        if source_slot_id is not None:
            source_slot_id = _db_uuid(
                source_slot_id, "source_generation_slot_id", slot=True
            )
            if source_slot_id not in slot_ids:
                raise WeekConsistencyError(
                    "Una occurrence referencia un GenerationSlot inválido."
                )
        segment_service._validated_occurrence(row)


def _require_in_week(value, week_start, week_end):
    if value < week_start or value > week_end:
        _invalid("La operación debe permanecer dentro de la semana objetivo.")


def _require_mutable(value, reference_date):
    if is_frozen_date(value, reference_date):
        raise WeekConflictError(
            "history_frozen", "El historial congelado es de solo lectura."
        )


def _new_occurrence_id(uuid_factory):
    value = uuid_factory()
    if not isinstance(value, UUID) or value.version != 4:
        raise WeekConsistencyError("No se pudo generar un UUID v4 para la occurrence.")
    return value


def _candidate_state(
    rows,
    operations,
    plan_item_id,
    week_start,
    week_end,
    reference_date,
    stopped_from_date,
    uuid_factory,
):
    by_id = {row["id"]: dict(row) for row in rows}
    updates = []
    deletes = []
    creates = []
    exclusions = set()

    for operation in operations:
        if operation["type"] == "create":
            _require_in_week(operation["date"], week_start, week_end)
            _require_mutable(operation["date"], reference_date)
            if stopped_from_date is not None and operation["date"] >= stopped_from_date:
                raise WeekConflictError(
                    "planning_stopped",
                    "La planificación está detenida en la fecha solicitada.",
                )
            occurrence = {
                "id": _new_occurrence_id(uuid_factory),
                "plan_item_id": plan_item_id,
                "occurrence_date": operation["date"],
                "start_time": time.fromisoformat(operation["startTime"]),
                "end_time": time.fromisoformat(operation["endTime"]),
                "status": "pending",
                "conflict_reason": None,
                "source_occurrence_id": None,
                "source_generation_slot_id": None,
                "origin_reason": None,
                "last_conflict_action": None,
            }
            creates.append(occurrence)
            continue

        occurrence = by_id.get(operation["occurrenceId"])
        if occurrence is None:
            raise WeekOccurrenceNotFoundError(
                "La occurrence no existe en la semana del PlanItem."
            )
        original_date = _db_date(occurrence["occurrence_date"], "occurrence_date")
        _require_in_week(original_date, week_start, week_end)
        _require_mutable(original_date, reference_date)

        if operation["type"] == "delete":
            if not can_delete_occurrence(
                original_date, occurrence["status"], reference_date
            ):
                raise WeekConflictError(
                    "deletion_status_locked",
                    "El status conserva historia y no permite esta eliminación.",
                )
            deletes.append(occurrence)
            if occurrence["source_generation_slot_id"] is not None:
                exclusions.add(
                    (occurrence["source_generation_slot_id"], original_date)
                )
            continue

        _require_in_week(operation["date"], week_start, week_end)
        _require_mutable(operation["date"], reference_date)
        updated = {
            **occurrence,
            "occurrence_date": operation["date"],
            "start_time": time.fromisoformat(operation["startTime"]),
            "end_time": time.fromisoformat(operation["endTime"]),
        }
        by_id[operation["occurrenceId"]] = updated
        updates.append((occurrence, updated))
        if (
            occurrence["source_generation_slot_id"] is not None
            and operation["date"] != original_date
        ):
            exclusions.add((occurrence["source_generation_slot_id"], original_date))

    deleted_ids = {row["id"] for row in deletes}
    final_rows = [row for row in by_id.values() if row["id"] not in deleted_ids]
    final_rows.extend(creates)
    return final_rows, updates, deletes, creates, sorted(exclusions)


def _validate_final_internal_state(rows, graphs=None):
    occurrence_ids = set()
    source_dates = set()
    blocking_rows = []
    for row in rows:
        occurrence_id = _db_uuid(row["id"], "occurrences.id")
        if occurrence_id in occurrence_ids:
            raise WeekConsistencyError("Existen IDs de occurrence duplicados.")
        occurrence_ids.add(occurrence_id)
        source_slot_id = row["source_generation_slot_id"]
        if source_slot_id is not None:
            key = (source_slot_id, row["occurrence_date"])
            if key in source_dates:
                raise WeekConflictError(
                    "slot_date_conflict",
                    "Un GenerationSlot tendría dos occurrences en la misma fecha.",
                )
            source_dates.add(key)
        if graphs is None and row["status"] in BLOCKING_STATUSES:
            blocking_rows.append(row)

    accepted = []
    for row in sorted(
        blocking_rows,
        key=lambda item: (
            item["occurrence_date"], item["start_time"], item["end_time"], item["id"]
        ),
    ):
        if any(
            row["occurrence_date"] == other["occurrence_date"]
            and time_ranges_overlap(
                _db_time(row["start_time"], "start_time"),
                _db_time(row["end_time"], "end_time"),
                _db_time(other["start_time"], "start_time"),
                _db_time(other["end_time"], "end_time"),
            )
            for other in accepted
        ):
            raise WeekConflictError(
                "schedule_conflict",
                "El estado final de la semana contiene horarios solapados.",
            )
        accepted.append(row)


def _validate_external_conflicts(plan_item, final_rows, external_rows):
    conflicts = []
    for external in external_rows:
        _db_uuid(external["id"], "occurrences.id")
        _db_uuid(external["plan_item_id"], "occurrences.plan_item_id")
        _db_date(external["occurrence_date"], "occurrence_date")
        _db_time(external["start_time"], "start_time")
        _db_time(external["end_time"], "end_time")
        if external["status"] not in BLOCKING_STATUSES:
            raise WeekConsistencyError("Una occurrence externa tiene status inválido.")
        if not (
            external["kind"] == "activity"
            and external["subtype"] in occurrence_service.ACTIVITY_TYPES
            or external["kind"] == "habit"
            and external["subtype"] in occurrence_service.HABIT_TYPES
        ):
            raise WeekConsistencyError("Un PlanItem externo tiene clasificación inválida.")
    for candidate in final_rows:
        if candidate["status"] not in BLOCKING_STATUSES:
            continue
        for external in external_rows:
            if (
                candidate["occurrence_date"] == external["occurrence_date"]
                and time_ranges_overlap(
                    _db_time(candidate["start_time"], "start_time"),
                    _db_time(candidate["end_time"], "end_time"),
                    _db_time(external["start_time"], "start_time"),
                    _db_time(external["end_time"], "end_time"),
                )
            ):
                conflicts.append(external)
    if not conflicts:
        return
    if any(row["status"] == "completed" for row in conflicts):
        raise WeekConflictError(
            "completed_conflict",
            "El intervalo contiene un registro completado y protegido.",
        )
    candidate_priority = scheduling_priority(plan_item["kind"], plan_item["subtype"])
    if any(
        candidate_priority <= scheduling_priority(row["kind"], row["subtype"])
        for row in conflicts
    ):
        raise WeekConflictError(
            "priority_conflict",
            "La prioridad del PlanItem no permite desplazar los conflictos.",
        )
    raise WeekConflictError(
        "priority_override_required",
        "Apply Week requiere confirmar un desplazamiento por prioridad.",
    )


def _temporary_dates(locked_rows, updates):
    moved = [
        (original, updated)
        for original, updated in updates
        if original["source_generation_slot_id"] is not None
        and original["occurrence_date"] != updated["occurrence_date"]
    ]
    occupied = {}
    for row in locked_rows:
        slot_id = _db_uuid(
            row["source_generation_slot_id"], "source_generation_slot_id", slot=True
        )
        occupied.setdefault(slot_id, set()).add(
            _db_date(row["occurrence_date"], "occurrence_date")
        )
    staged = []
    next_candidate = date.min
    for original, _updated in moved:
        slot_id = original["source_generation_slot_id"]
        slot_dates = occupied.setdefault(slot_id, set())
        while next_candidate in slot_dates:
            next_candidate += timedelta(days=1)
        staged.append((original["id"], next_candidate))
        slot_dates.add(next_candidate)
        next_candidate += timedelta(days=1)
    return staged


def _serialize_sorted(rows, graphs):
    result = [_serialize_occurrence(row, graphs[row["id"]]) for row in rows]
    result.sort(
        key=lambda item: (
            item["date"], item["startTime"], item["endTime"], item["id"]
        )
    )
    return result


def _raise_database_error(error):
    if isinstance(
        error, (psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected)
    ):
        raise WeekConflictError(
            "concurrent_conflict",
            "La semana cambió durante la operación; vuelve a intentarlo.",
        ) from None
    if isinstance(error, psycopg.errors.UniqueViolation) and (
        getattr(error.diag, "constraint_name", None)
        == "uq_occurrences_source_generation_slot_date"
    ):
        raise WeekConflictError(
            "slot_date_conflict",
            "Un GenerationSlot ya tiene una occurrence en la fecha destino.",
        ) from None
    raise WeekUnavailableError("PostgreSQL no pudo completar Apply Week.") from None


def apply_week(plan_item_id, payload, reference_date=None, uuid_factory=uuid4):
    parsed_plan_item_id = _identifier(plan_item_id, "plan_item_id")
    anchor_date, operations = validate_apply_week_payload(payload)
    authoritative_now = (
        datetime.combine(reference_date, time.max)
        if reference_date is not None else datetime.now()
    )
    current_date = authoritative_now.date()
    if isinstance(current_date, datetime) or not isinstance(current_date, date):
        raise TypeError("reference_date debe ser date.")
    week_start = anchor_date - timedelta(days=anchor_date.isoweekday() - 1)
    week_end = week_start + timedelta(days=6)

    try:
        with database.get_connection() as connection:
            with connection.transaction():
                occurrence_repository.set_serializable_transaction(connection)
                if occurrence_repository.lock_plan_item_identity(
                    connection, parsed_plan_item_id
                ) is None:
                    raise WeekPlanItemNotFoundError("El PlanItem no existe.")
                plan_item = occurrence_repository.lock_plan_item_context(
                    connection, parsed_plan_item_id
                )
                if plan_item is None:
                    raise WeekConsistencyError(
                        "El PlanItem no tiene generationConfig persistida."
                    )
                _validate_plan_item_context(plan_item)
                slots = occurrence_repository.lock_plan_item_slots(
                    connection, parsed_plan_item_id
                )
                slot_ids = _validate_slots(
                    plan_item["mode"],
                    slots,
                    parsed_plan_item_id,
                    plan_item["slot_count"],
                )
                rows = occurrence_repository.lock_plan_item_week_occurrences(
                    connection, parsed_plan_item_id, week_start, week_end
                )
                _validate_week_rows(rows, parsed_plan_item_id, slot_ids)
                persisted_graphs = segment_service.load_segment_graphs(connection, rows, authoritative_now)

                final_rows, updates, deletes, creates, exclusions = _candidate_state(
                    rows,
                    operations,
                    parsed_plan_item_id,
                    week_start,
                    week_end,
                    current_date,
                    plan_item["stopped_from_date"],
                    uuid_factory,
                )
                delete_ids = [row["id"] for row in deletes]
                if occurrence_repository.lock_status_context_dependents_for_sources(
                    connection, delete_ids
                ):
                    raise WeekConflictError(
                        "status_context_locked",
                        "No se puede borrar una occurrence referenciada por otra.",
                    )

                try:
                    graphs = segment_service.build_candidate_graphs(
                        rows, final_rows, persisted_graphs, authoritative_now,
                    )
                    _validate_final_internal_state(final_rows, graphs)
                    segment_service.validate_batch_conflicts(
                        connection, rows, final_rows, graphs
                    )
                except segment_service.RecurringGraphError as error:
                    raise WeekConflictError(
                        error.code, str(error), error.occurrences, error.blockers
                    ) from None
                except segment_service.OccurrenceSegmentConsistencyError as error:
                    raise WeekConsistencyError(str(error)) from None

                moved_slot_ids = sorted(
                    {
                        original["source_generation_slot_id"]
                        for original, updated in updates
                        if original["source_generation_slot_id"] is not None
                        and original["occurrence_date"] != updated["occurrence_date"]
                    },
                    key=str,
                )
                locked_slot_occurrences = occurrence_repository.lock_occurrences_for_slots(
                    connection, moved_slot_ids
                )
                staged_dates = _temporary_dates(locked_slot_occurrences, updates)
                if staged_dates and not occurrence_repository.stage_occurrence_dates(
                    connection, staged_dates
                ):
                    raise WeekConsistencyError(
                        "No se pudieron preparar los movimientos de la semana."
                    )

                occurrence_repository.insert_slot_exclusions(connection, exclusions)
                for row in deletes:
                    if occurrence_repository.delete_occurrence(
                        connection, row["id"]
                    ) != 1:
                        raise WeekConsistencyError(
                            "No se pudo eliminar una occurrence bloqueada."
                        )
                for _original, updated in updates:
                    if occurrence_repository.update_occurrence_schedule(
                        connection,
                        updated["id"],
                        updated["occurrence_date"],
                        _db_time(updated["start_time"], "start_time"),
                        _db_time(updated["end_time"], "end_time"),
                    ) != 1:
                        raise WeekConsistencyError(
                            "No se pudo actualizar una occurrence bloqueada."
                        )
                segment_service.persist_segments_for_updates(
                    connection, updates, graphs, persisted_graphs
                )
                occurrence_repository.insert_ad_hoc_occurrences(connection, creates)
                segment_service.persist_segments_for_creates(connection, creates, graphs)

                persisted_rows = occurrence_repository.list_plan_item_week_occurrences(
                    connection, parsed_plan_item_id, week_start, week_end
                )
                final_graphs = segment_service.load_segment_graphs(connection, persisted_rows, authoritative_now)
                persisted = _serialize_sorted(persisted_rows, final_graphs)
                if persisted != _serialize_sorted(final_rows, graphs):
                    raise WeekConsistencyError(
                        "El estado persistido final no coincide con el batch validado."
                    )
                result = {
                    "weekStart": week_start.isoformat(),
                    "weekEnd": week_end.isoformat(),
                    "occurrences": persisted,
                }
    except (
        WeekValidationError,
        WeekPlanItemNotFoundError,
        WeekOccurrenceNotFoundError,
        WeekConflictError,
        WeekConsistencyError,
    ):
        raise
    except database.DatabaseConnectionError as error:
        _raise_database_error(error)
    except segment_service.RecurringGraphError as error:
        raise WeekConflictError(
            error.code, str(error), error.occurrences, error.blockers,
        ) from None
    except segment_service.OccurrenceSegmentConsistencyError as error:
        raise WeekConsistencyError(str(error)) from None
    except psycopg.Error as error:
        _raise_database_error(error)
    return result
