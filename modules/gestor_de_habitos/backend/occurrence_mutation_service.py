"""Edición y eliminación atómicas de una sola Occurrence persistida."""

from datetime import date, datetime, time
import re
from uuid import UUID

import psycopg

import database
from occurrence_segment_domain import (
    OccurrenceSegmentDomainError, derive_occurrence_status, temporal_phase_for_date,
)
from occurrence_segment_service import (
    OccurrenceSegmentConsistencyError, _validated_occurrence, _validated_segments,
)
from occurrence_structure_domain import OccurrenceStructureDomainError, validate_final_segments
from repositories import occurrence_repository
from repositories import occurrence_segment_repository
from scheduling_policy import (
    BLOCKING_STATUSES,
    can_delete_occurrence,
    is_frozen_date,
    scheduling_priority,
    time_ranges_overlap,
    HISTORY_EDIT_WINDOW_DAYS,
)


GENERATION_MODES = frozenset({"weekly", "interval_days", "manual_dates"})
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
ACTIVITY_TYPES = frozenset({"anchor", "periodic", "event", "unexpected"})
HABIT_TYPES = frozenset({"scheduled"})
PRIORITY_OVERRIDE_REASON = "priority_override"
_TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class OccurrenceMutationError(RuntimeError):
    """Error seguro compartido por PATCH y DELETE."""


class OccurrenceValidationError(OccurrenceMutationError):
    """El identificador o JSON no cumple el contrato HTTP."""


class OccurrenceNotFoundError(OccurrenceMutationError):
    """La Occurrence solicitada no existe."""


class OccurrenceConflictError(OccurrenceMutationError):
    """La mutación contradice una regla vigente del dominio."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class OccurrenceConsistencyError(OccurrenceMutationError):
    """Las filas relacionadas no forman un estado canónico."""


class OccurrenceUnavailableError(OccurrenceMutationError):
    """PostgreSQL no pudo completar la transacción."""


def _invalid(message):
    raise OccurrenceValidationError(message)


def _today():
    return date.today()


def _occurrence_id(value):
    if not isinstance(value, str):
        _invalid("occurrence_id debe ser un UUID válido.")
    try:
        return UUID(value)
    except (ValueError, AttributeError):
        _invalid("occurrence_id debe ser un UUID válido.")


def _date_value(value, field_name="date"):
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


def validate_patch_payload(payload):
    if not isinstance(payload, dict) or set(payload) != {
        "date",
        "startTime",
        "endTime",
    }:
        _invalid("El payload debe contener exactamente date, startTime y endTime.")
    start_time = _time_value(payload["startTime"], "startTime")
    end_time = _time_value(payload["endTime"], "endTime")
    if start_time >= end_time:
        _invalid("endTime debe ser posterior a startTime.")
    return {
        "date": _date_value(payload["date"]),
        "startTime": start_time,
        "endTime": end_time,
    }


def _db_uuid(value, field_name):
    if not isinstance(value, UUID):
        raise OccurrenceConsistencyError(f"{field_name} no contiene un UUID.")
    return value


def _db_slot_uuid(value, field_name):
    slot_id = _db_uuid(value, field_name)
    if slot_id.version != 4:
        raise OccurrenceConsistencyError(f"{field_name} no contiene un UUID v4.")
    return slot_id


def _db_date(value, field_name):
    if isinstance(value, datetime) or not isinstance(value, date):
        raise OccurrenceConsistencyError(f"{field_name} no contiene una fecha.")
    return value


def _db_time(value, field_name):
    if not isinstance(value, time) or value.second != 0 or value.microsecond != 0:
        raise OccurrenceConsistencyError(
            f"{field_name} no puede representarse como HH:MM."
        )
    return value.strftime("%H:%M")


def _validate_plan_item_context(context):
    _db_uuid(context["id"], "plan_items.id")
    mode = context["mode"]
    if mode not in GENERATION_MODES:
        raise OccurrenceConsistencyError(
            "El PlanItem no tiene una generationConfig válida."
        )
    if context["slot_count"] < 1:
        raise OccurrenceConsistencyError(
            "La generationConfig no contiene GenerationSlots."
        )
    if mode == "manual_dates" and context["global_exclusion_count"] != 0:
        raise OccurrenceConsistencyError(
            "manual_dates no puede contener exclusiones globales."
        )
    kind = context["kind"]
    subtype = context["subtype"]
    if not (
        kind == "activity" and subtype in ACTIVITY_TYPES
        or kind == "habit" and subtype in HABIT_TYPES
    ):
        raise OccurrenceConsistencyError("El PlanItem tiene clasificación inválida.")


def _validate_slot_shape(mode, slot):
    if mode == "weekly":
        valid = slot["weekday_count"] == 1 and slot["date_count"] == 0
    elif mode == "interval_days":
        valid = slot["weekday_count"] == 0 and slot["date_count"] == 0
    else:
        valid = (
            slot["weekday_count"] == 0
            and slot["date_count"] == 1
            and slot["excluded_date_count"] == 0
        )
    if not valid:
        raise OccurrenceConsistencyError(
            "El GenerationSlot no corresponde al mode persistido."
        )


def _validate_manual_slots(rows, plan_item_id):
    accepted = []
    for row in rows:
        _db_slot_uuid(row["id"], "generation_slots.id")
        if _db_uuid(row["plan_item_id"], "generation_slots.plan_item_id") != plan_item_id:
            raise OccurrenceConsistencyError(
                "Una entry manual pertenece a otro PlanItem."
            )
        _validate_slot_shape("manual_dates", row)
        candidate = {
            "date": _db_date(row["entry_date"], "entry_date"),
            "startTime": _db_time(row["start_time"], "start_time"),
            "endTime": _db_time(row["end_time"], "end_time"),
        }
        if candidate["startTime"] >= candidate["endTime"]:
            raise OccurrenceConsistencyError("Una entry manual tiene horario inválido.")
        if any(
            candidate["date"] == other["date"]
            and time_ranges_overlap(
                candidate["startTime"],
                candidate["endTime"],
                other["startTime"],
                other["endTime"],
            )
            for other in accepted
        ):
            raise OccurrenceConsistencyError(
                "La configuración manual contiene horarios solapados."
            )
        accepted.append(candidate)


def _load_locked_context(connection, occurrence_id, *, schema004_delete=False, reference_date=None):
    owner = occurrence_repository.find_occurrence_owner(connection, occurrence_id)
    if owner is None:
        raise OccurrenceNotFoundError("La occurrence no existe.")
    plan_item_id = _db_uuid(owner["plan_item_id"], "plan_item_id")
    plan_item = occurrence_repository.lock_plan_item_context(
        connection, plan_item_id
    )
    occurrence = (
        occurrence_repository.lock_occurrence_for_delete(connection, occurrence_id)
        if schema004_delete else occurrence_repository.lock_occurrence(connection, occurrence_id)
    )
    if occurrence is None:
        # Puede ocurrir después de esperar a un DELETE concurrente.
        raise OccurrenceNotFoundError("La occurrence no existe.")
    if (
        plan_item is None
        or _db_uuid(occurrence["plan_item_id"], "occurrences.plan_item_id")
        != plan_item_id
    ):
        raise OccurrenceConsistencyError("La occurrence no tiene un PlanItem válido.")
    _validate_plan_item_context(plan_item)
    if schema004_delete:
        try:
            parent = _validated_occurrence(occurrence)
            segments = _validated_segments(
                occurrence_segment_repository.lock_occurrence_segments(connection, occurrence_id),
                parent,
            )
            segments = validate_final_segments(parent["startTime"], parent["endTime"], segments)
            phase = temporal_phase_for_date(parent["date"], reference_date, HISTORY_EDIT_WINDOW_DAYS)
            if derive_occurrence_status(segments, phase) != parent["status"]:
                raise OccurrenceConsistencyError("El status parent no coincide con sus segments.")
        except (OccurrenceSegmentConsistencyError, OccurrenceSegmentDomainError,
                OccurrenceStructureDomainError) as error:
            raise OccurrenceConsistencyError("La occurrence no contiene un grafo de segments válido.") from error
    else:
        _serialize_occurrence(occurrence)

    source_slot_id = occurrence["source_generation_slot_id"]
    slot = None
    manual_slots = None
    manual_slot_date = None
    if source_slot_id is not None:
        source_slot_id = _db_slot_uuid(
            source_slot_id, "source_generation_slot_id"
        )
        slot = occurrence_repository.lock_generation_slot(connection, source_slot_id)
        if (
            slot is None
            or _db_slot_uuid(slot["id"], "generation_slots.id") != source_slot_id
            or _db_uuid(slot["plan_item_id"], "generation_slots.plan_item_id")
            != plan_item_id
        ):
            raise OccurrenceConsistencyError(
                "La occurrence referencia un GenerationSlot inválido."
            )
        _validate_slot_shape(plan_item["mode"], slot)
        if plan_item["mode"] == "manual_dates":
            manual_slots = occurrence_repository.lock_plan_item_slots(
                connection, plan_item_id
            )
            _validate_manual_slots(manual_slots, plan_item_id)
            manual_slot_date = occurrence_repository.lock_manual_slot_date(
                connection, source_slot_id
            )
            if manual_slot_date is None:
                raise OccurrenceConsistencyError(
                    "La entry manual no tiene una fecha persistida."
                )
            source_manual_slot = next(
                (row for row in manual_slots if row["id"] == source_slot_id),
                None,
            )
            if (
                source_manual_slot is None
                or (not schema004_delete and (
                    _db_date(manual_slot_date["entry_date"], "entry_date")
                    != _db_date(occurrence["occurrence_date"], "occurrence_date")
                    or _db_time(source_manual_slot["start_time"], "start_time")
                    != _db_time(occurrence["start_time"], "start_time")
                    or _db_time(source_manual_slot["end_time"], "end_time")
                    != _db_time(occurrence["end_time"], "end_time")
                ))
            ):
                raise OccurrenceConsistencyError(
                    "La entry manual y su occurrence no están sincronizadas."
                )
            linked = occurrence_repository.lock_occurrences_for_slot(
                connection, source_slot_id
            )
            if [row["id"] for row in linked] != [occurrence["id"]]:
                raise OccurrenceConsistencyError(
                    "Una entry manual no corresponde a una sola occurrence."
                )
    return {
        "planItem": plan_item,
        "occurrence": occurrence,
        "slot": slot,
        "manualSlots": manual_slots,
        "manualSlotDate": manual_slot_date,
    }


def _validate_mutable_dates(original_date, target_date, reference_date):
    if is_frozen_date(original_date, reference_date) or is_frozen_date(
        target_date, reference_date
    ):
        raise OccurrenceConflictError(
            "history_frozen",
            "El historial congelado es de solo lectura.",
        )


def _validate_occurrence_conflicts(connection, context, candidate):
    occurrence = context["occurrence"]
    if occurrence["status"] not in BLOCKING_STATUSES:
        return
    rows = occurrence_repository.lock_blocking_occurrences(
        connection, candidate["date"], occurrence["id"]
    )
    conflicts = []
    for row in rows:
        start_time = _db_time(row["start_time"], "start_time")
        end_time = _db_time(row["end_time"], "end_time")
        if time_ranges_overlap(
            candidate["startTime"], candidate["endTime"], start_time, end_time
        ):
            conflicts.append(row)
    if not conflicts:
        return
    if any(row["status"] == "completed" for row in conflicts):
        raise OccurrenceConflictError(
            "completed_conflict",
            "El intervalo contiene un registro completado y protegido.",
        )
    plan_item = context["planItem"]
    candidate_priority = scheduling_priority(
        plan_item["kind"], plan_item["subtype"]
    )
    if any(
        candidate_priority <= scheduling_priority(row["kind"], row["subtype"])
        for row in conflicts
    ):
        raise OccurrenceConflictError(
            "priority_conflict",
            "La prioridad del registro no permite desplazar los conflictos.",
        )
    # PATCH no incluye todavía la confirmación necesaria para desplazar filas.
    raise OccurrenceConflictError(
        "priority_override_required",
        "La edición requiere confirmar un desplazamiento por prioridad.",
    )


def _validate_manual_slot_conflicts(connection, context, candidate):
    slot = context["slot"]
    siblings = occurrence_repository.lock_manual_sibling_slots_on_date(
        connection,
        context["occurrence"]["plan_item_id"],
        candidate["date"],
        slot["id"],
    )
    for sibling in siblings:
        if time_ranges_overlap(
            candidate["startTime"],
            candidate["endTime"],
            _db_time(sibling["start_time"], "start_time"),
            _db_time(sibling["end_time"], "end_time"),
        ):
            raise OccurrenceConflictError(
                "slot_date_conflict",
                "La entry manual se solapa con otro horario de la fecha.",
            )


def _serialize_occurrence(row):
    occurrence_id = str(_db_uuid(row["id"], "occurrences.id"))
    plan_item_id = str(_db_uuid(row["plan_item_id"], "plan_item_id"))
    status = row["status"]
    if status not in OCCURRENCE_STATUSES:
        raise OccurrenceConsistencyError("La occurrence tiene un status inválido.")
    result = {
        "id": occurrence_id,
        "planItemId": plan_item_id,
        "date": _db_date(row["occurrence_date"], "occurrence_date").isoformat(),
        "startTime": _db_time(row["start_time"], "start_time"),
        "endTime": _db_time(row["end_time"], "end_time"),
        "status": status,
    }
    if result["startTime"] >= result["endTime"]:
        raise OccurrenceConsistencyError("La occurrence tiene un horario inválido.")
    source_slot = row["source_generation_slot_id"]
    if source_slot is not None:
        result["sourceGenerationSlotId"] = str(
            _db_slot_uuid(source_slot, "source_generation_slot_id")
        )
    reason = row["status_reason"]
    source_occurrence = row["source_occurrence_id"]
    if reason is None and source_occurrence is None:
        return result
    if (
        reason != PRIORITY_OVERRIDE_REASON
        or source_occurrence is None
        or status not in {"cancelled", "not_finished"}
    ):
        raise OccurrenceConsistencyError(
            "La occurrence tiene un statusContext inválido."
        )
    result["statusContext"] = {
        "reason": PRIORITY_OVERRIDE_REASON,
        "sourceOccurrenceId": str(
            _db_uuid(source_occurrence, "source_occurrence_id")
        ),
    }
    return result


def _raise_database_error(error):
    if isinstance(
        error, (psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected)
    ):
        raise OccurrenceConflictError(
            "concurrent_conflict",
            "El estado cambió durante la operación; vuelve a intentarlo.",
        ) from None
    if isinstance(error, psycopg.errors.UniqueViolation):
        raise OccurrenceConflictError(
            "slot_date_conflict",
            "El GenerationSlot ya tiene una occurrence en la fecha destino.",
        ) from None
    if isinstance(error, psycopg.errors.ForeignKeyViolation):
        raise OccurrenceConflictError(
            "deletion_status_locked",
            "La occurrence conserva dependientes de procedencia y no puede eliminarse.",
        ) from None
    raise OccurrenceUnavailableError(
        "PostgreSQL no pudo completar la mutación."
    ) from None


def patch_occurrence(occurrence_id, payload, reference_date=None):
    """Edita fecha/horario y conserva identidad, status y procedencia."""
    parsed_id = _occurrence_id(occurrence_id)
    candidate = validate_patch_payload(payload)
    current_date = reference_date or _today()
    if isinstance(current_date, datetime) or not isinstance(current_date, date):
        raise TypeError("reference_date debe ser date.")

    try:
        with database.get_connection() as connection:
            with connection.transaction():
                occurrence_repository.set_serializable_transaction(connection)
                context = _load_locked_context(connection, parsed_id)
                occurrence = context["occurrence"]
                original_date = _db_date(
                    occurrence["occurrence_date"], "occurrence_date"
                )
                _validate_mutable_dates(
                    original_date, candidate["date"], current_date
                )
                schedule_changed = (
                    candidate["date"] != original_date
                    or candidate["startTime"]
                    != _db_time(occurrence["start_time"], "start_time")
                    or candidate["endTime"]
                    != _db_time(occurrence["end_time"], "end_time")
                )
                if schedule_changed and occurrence_repository.lock_status_context_dependents(
                    connection, occurrence["id"]
                ):
                    raise OccurrenceConflictError(
                        "status_context_locked",
                        "La occurrence conserva contexto de prioridad dependiente.",
                    )

                source_slot = occurrence["source_generation_slot_id"]
                mode = context["planItem"]["mode"]
                if source_slot is not None and candidate["date"] != original_date:
                    duplicate = occurrence_repository.lock_source_occurrence_on_date(
                        connection, source_slot, candidate["date"], occurrence["id"]
                    )
                    if duplicate is not None:
                        raise OccurrenceConflictError(
                            "slot_date_conflict",
                            "El GenerationSlot ya tiene una occurrence en la fecha destino.",
                        )

                if source_slot is not None and mode == "manual_dates":
                    _validate_manual_slot_conflicts(connection, context, candidate)
                _validate_occurrence_conflicts(connection, context, candidate)

                if source_slot is not None and mode in {
                    "weekly",
                    "interval_days",
                }:
                    if candidate["date"] != original_date:
                        occurrence_repository.insert_slot_exclusion(
                            connection, source_slot, original_date
                        )
                elif source_slot is not None and mode == "manual_dates":
                    if occurrence_repository.update_generation_slot_schedule(
                        connection,
                        source_slot,
                        candidate["startTime"],
                        candidate["endTime"],
                    ) != 1:
                        raise OccurrenceConsistencyError(
                            "No se pudo actualizar la entry manual."
                        )
                    if occurrence_repository.update_manual_slot_date(
                        connection, source_slot, candidate["date"]
                    ) != 1:
                        raise OccurrenceConsistencyError(
                            "No se pudo actualizar la fecha manual."
                        )

                if occurrence_repository.update_occurrence_schedule(
                    connection,
                    occurrence["id"],
                    candidate["date"],
                    candidate["startTime"],
                    candidate["endTime"],
                ) != 1:
                    raise OccurrenceConsistencyError(
                        "No se pudo actualizar la occurrence bloqueada."
                    )
                updated = {
                    **occurrence,
                    "occurrence_date": candidate["date"],
                    "start_time": time.fromisoformat(candidate["startTime"]),
                    "end_time": time.fromisoformat(candidate["endTime"]),
                }
                result = {"occurrence": _serialize_occurrence(updated)}
    except (
        OccurrenceValidationError,
        OccurrenceNotFoundError,
        OccurrenceConflictError,
        OccurrenceConsistencyError,
    ):
        raise
    except database.DatabaseConnectionError as error:
        _raise_database_error(error)
    except psycopg.Error as error:
        _raise_database_error(error)
    return result


def delete_occurrence(occurrence_id, reference_date=None):
    """Elimina solo la occurrence seleccionada según su procedencia."""
    parsed_id = _occurrence_id(occurrence_id)
    current_date = reference_date or _today()
    if isinstance(current_date, datetime) or not isinstance(current_date, date):
        raise TypeError("reference_date debe ser date.")

    try:
        with database.get_connection() as connection:
            with connection.transaction():
                occurrence_repository.set_serializable_transaction(connection)
                context = _load_locked_context(
                    connection, parsed_id, schema004_delete=True, reference_date=current_date
                )
                occurrence = context["occurrence"]
                occurrence_date = _db_date(
                    occurrence["occurrence_date"], "occurrence_date"
                )
                if is_frozen_date(occurrence_date, current_date):
                    raise OccurrenceConflictError(
                        "history_frozen",
                        "El historial congelado es de solo lectura.",
                    )
                if not can_delete_occurrence(
                    occurrence_date, occurrence["status"], current_date
                ):
                    raise OccurrenceConflictError(
                        "deletion_status_locked",
                        "El status conserva historia y no permite esta eliminación.",
                    )
                source_slot = occurrence["source_generation_slot_id"]
                mode = context["planItem"]["mode"]
                if (
                    source_slot is not None
                    and mode == "manual_dates"
                    and len(context["manualSlots"]) == 1
                ):
                    raise OccurrenceConflictError(
                        "last_manual_entry",
                        "No se puede eliminar la última entry manual.",
                    )
                if occurrence_repository.lock_status_context_dependents(
                    connection, occurrence["id"]
                ):
                    raise OccurrenceConflictError(
                        "deletion_status_locked",
                        "La occurrence conserva contexto de prioridad dependiente.",
                    )

                if source_slot is not None and mode in {
                    "weekly",
                    "interval_days",
                }:
                    # Idempotente: la PK slot+date protege la misma decisión.
                    occurrence_repository.insert_slot_exclusion(
                        connection, source_slot, occurrence_date
                    )
                    if occurrence_repository.delete_occurrence(
                        connection, occurrence["id"]
                    ) != 1:
                        raise OccurrenceConsistencyError(
                            "No se pudo eliminar la occurrence bloqueada."
                        )
                elif source_slot is not None and mode == "manual_dates":
                    manual_slots = context["manualSlots"]
                    if not any(row["id"] == source_slot for row in manual_slots):
                        raise OccurrenceConsistencyError(
                            "La entry manual no pertenece al PlanItem."
                        )
                    if occurrence_repository.delete_occurrence(
                        connection, occurrence["id"]
                    ) != 1:
                        raise OccurrenceConsistencyError(
                            "No se pudo eliminar la occurrence bloqueada."
                        )
                    if occurrence_repository.delete_generation_slot(
                        connection, source_slot
                    ) != 1:
                        raise OccurrenceConsistencyError(
                            "No se pudo eliminar la entry manual."
                        )
                else:
                    if occurrence_repository.delete_occurrence(
                        connection, occurrence["id"]
                    ) != 1:
                        raise OccurrenceConsistencyError(
                            "No se pudo eliminar la occurrence bloqueada."
                        )
                result = {"deletedOccurrenceId": str(occurrence["id"])}
    except (
        OccurrenceValidationError,
        OccurrenceNotFoundError,
        OccurrenceConflictError,
        OccurrenceConsistencyError,
    ):
        raise
    except database.DatabaseConnectionError as error:
        _raise_database_error(error)
    except psycopg.Error as error:
        _raise_database_error(error)
    return result
