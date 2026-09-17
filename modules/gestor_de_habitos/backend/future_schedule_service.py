"""Reemplazo atómico del motor recurrente desde una nueva fecha inicial."""

from datetime import date, datetime, time
from uuid import UUID, uuid4

import psycopg

import database
import occurrence_mutation_service as occurrence_service
import plan_item_creation_service as creation_service
import planner_state_service
import week_mutation_service as week_service
from plan_item_materializer import get_materialization_range, materialize_occurrence_drafts
from repositories import future_schedule_repository, occurrence_repository
from scheduling_policy import BLOCKING_STATUSES, can_delete_occurrence, is_frozen_date


SUPPORTED_MODES = frozenset({"weekly", "interval_days"})


class FutureScheduleError(RuntimeError):
    """Error seguro común para Apply Future."""


class FutureValidationError(FutureScheduleError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class FuturePlanItemNotFoundError(FutureScheduleError):
    """El PlanItem solicitado no existe."""


class FutureConflictError(FutureScheduleError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class FutureConsistencyError(FutureScheduleError):
    """Las filas persistidas no forman un estado canónico."""


class FutureUnavailableError(FutureScheduleError):
    """PostgreSQL no pudo completar la transacción."""


def _invalid(message, code="invalid_payload"):
    raise FutureValidationError(code, message)


def _today():
    return date.today()


def _identifier(value):
    if not isinstance(value, str):
        _invalid("plan_item_id debe ser un UUID válido.", "invalid_identifier")
    try:
        return UUID(value)
    except (ValueError, AttributeError):
        _invalid("plan_item_id debe ser un UUID válido.", "invalid_identifier")


def validate_apply_future_payload(payload):
    if not isinstance(payload, dict) or set(payload) != {"futureConfig"}:
        _invalid("El payload debe contener exactamente futureConfig.")
    config = payload["futureConfig"]
    if not isinstance(config, dict):
        _invalid("futureConfig debe ser un objeto.")
    if config.get("mode") == "weekly":
        if set(config) != {
            "mode",
            "startDate",
            "endDate",
            "indefinite",
            "slots",
        }:
            _invalid("futureConfig weekly no cumple el contrato exacto.")
        if not isinstance(config.get("slots"), list) or any(
            not isinstance(slot, dict)
            or set(slot) != {"id", "isoWeekday", "startTime", "endTime"}
            for slot in config["slots"]
        ):
            _invalid("Un GenerationSlot weekly no cumple el contrato exacto.")
    elif config.get("mode") == "interval_days":
        if set(config) != {
            "mode",
            "startDate",
            "endDate",
            "indefinite",
            "intervalDays",
            "slots",
        }:
            _invalid("futureConfig interval_days no cumple el contrato exacto.")
        if not isinstance(config.get("slots"), list) or any(
            not isinstance(slot, dict)
            or set(slot) != {"id", "startTime", "endTime"}
            for slot in config["slots"]
        ):
            _invalid("Un GenerationSlot interval_days no cumple el contrato exacto.")
    try:
        normalized = creation_service._normalize_generation_config(config)
    except creation_service.PlanItemValidationError as error:
        _invalid(str(error))
    if normalized["mode"] not in SUPPORTED_MODES:
        raise FutureConflictError(
            "unsupported_mode",
            "Apply Future no está disponible para manual_dates.",
        )
    return normalized


def _db_date(value, field_name):
    if isinstance(value, datetime) or not isinstance(value, date):
        raise FutureConsistencyError(f"{field_name} no contiene una fecha válida.")
    return value


def _db_time_string(value, field_name):
    if not isinstance(value, time) or value.second != 0 or value.microsecond != 0:
        raise FutureConsistencyError(f"{field_name} no puede representarse como HH:MM.")
    return value.strftime("%H:%M")


def _snapshot_domain(snapshot):
    try:
        weekdays = planner_state_service._rows_by_slot(snapshot["weekdays"])
        slot_dates = planner_state_service._rows_by_slot(snapshot["slot_dates"])
        slot_exclusions = planner_state_service._rows_by_slot(
            snapshot["slot_exclusions"]
        )
        config = planner_state_service._build_generation_config(
            snapshot["schedule"],
            snapshot["slots"],
            weekdays,
            slot_dates,
            slot_exclusions,
            snapshot["global_exclusions"],
        )
        plan_item = planner_state_service._build_plan_item(
            snapshot["schedule"], config
        )
    except planner_state_service.PlannerStateConsistencyError as error:
        raise FutureConsistencyError(str(error)) from None
    return plan_item


def _load_snapshot(connection, plan_item_id):
    schedule = future_schedule_repository.lock_plan_item_schedule(
        connection, plan_item_id
    )
    if schedule is None:
        raise FutureConsistencyError(
            "El PlanItem no tiene generationConfig persistida."
        )
    slots = future_schedule_repository.lock_generation_slots(
        connection, plan_item_id
    )
    slot_ids = [slot["id"] for slot in slots]
    return {
        "schedule": schedule,
        "slots": slots,
        "weekdays": future_schedule_repository.lock_slot_weekdays(
            connection, slot_ids
        ),
        "slot_dates": future_schedule_repository.lock_slot_dates(
            connection, slot_ids
        ),
        "slot_exclusions": future_schedule_repository.lock_slot_exclusions(
            connection, slot_ids
        ),
        "global_exclusions": future_schedule_repository.lock_global_exclusions(
            connection, plan_item_id
        ),
        "occurrences": future_schedule_repository.lock_plan_item_occurrences(
            connection, plan_item_id
        ),
    }


def _preserve_generation_controls(old_config, future_config):
    candidate = {
        **future_config,
        "slots": [{**slot} for slot in future_config["slots"]],
    }
    if old_config.get("excludedDates"):
        candidate["excludedDates"] = [*old_config["excludedDates"]]
    if old_config.get("stoppedFromDate") is not None:
        candidate["stoppedFromDate"] = old_config["stoppedFromDate"]

    exclusions_by_slot = {
        slot["id"]: slot.get("excludedDates", []) for slot in old_config["slots"]
    }
    candidate["slots"] = [
        {
            **slot,
            **(
                {"excludedDates": [*exclusions_by_slot[slot["id"]]]}
                if exclusions_by_slot.get(slot["id"])
                else {}
            ),
        }
        for slot in candidate["slots"]
    ]
    return candidate


def _validate_snapshot_occurrences(rows, old_config):
    slot_ids = {slot["id"] for slot in old_config["slots"]}
    occurrence_ids = set()
    source_dates = set()
    for row in rows:
        try:
            occurrence_service._serialize_occurrence(row)
        except occurrence_service.OccurrenceConsistencyError as error:
            raise FutureConsistencyError(str(error)) from None
        if row["id"] in occurrence_ids:
            raise FutureConsistencyError("Existen IDs de occurrence duplicados.")
        occurrence_ids.add(row["id"])
        source_value = row["source_generation_slot_id"]
        if source_value is None:
            continue
        source_id = str(source_value)
        if source_id not in slot_ids:
            raise FutureConsistencyError(
                "Una occurrence referencia un GenerationSlot ajeno al PlanItem."
            )
        key = (source_id, row["occurrence_date"])
        if key in source_dates:
            raise FutureConsistencyError(
                "Un GenerationSlot tiene occurrences duplicadas en una fecha."
            )
        source_dates.add(key)


def _is_old_baseline(row, old_config):
    source_value = row["source_generation_slot_id"]
    if source_value is None:
        return False
    source_id = str(source_value)
    slot = next((item for item in old_config["slots"] if item["id"] == source_id), None)
    if slot is None:
        raise FutureConsistencyError(
            "Una occurrence referencia un GenerationSlot ajeno al PlanItem."
        )

    occurrence_date = _db_date(row["occurrence_date"], "occurrence_date")
    date_key = occurrence_date.isoformat()
    if (
        _db_time_string(row["start_time"], "start_time") != slot["startTime"]
        or _db_time_string(row["end_time"], "end_time") != slot["endTime"]
        or date_key in set(old_config.get("excludedDates", []))
        or date_key in set(slot.get("excludedDates", []))
        or old_config.get("stoppedFromDate") is not None
        and date_key >= old_config["stoppedFromDate"]
    ):
        return False

    start_date = date.fromisoformat(old_config["startDate"])
    if occurrence_date < start_date:
        return False
    if not old_config["indefinite"] and occurrence_date > date.fromisoformat(
        old_config["endDate"]
    ):
        return False
    if old_config["mode"] == "weekly":
        return occurrence_date.isoweekday() == slot["isoWeekday"]
    return (occurrence_date - start_date).days % old_config["intervalDays"] == 0


def _new_occurrence_id(uuid_factory):
    value = uuid_factory()
    if not isinstance(value, UUID) or value.version != 4:
        raise FutureConsistencyError(
            "No se pudo generar un UUID v4 para una occurrence."
        )
    return value


def _draft_row(draft, occurrence_id):
    return {
        "id": occurrence_id,
        "plan_item_id": UUID(draft["planItemId"]),
        "occurrence_date": date.fromisoformat(draft["date"]),
        "start_time": time.fromisoformat(draft["startTime"]),
        "end_time": time.fromisoformat(draft["endTime"]),
        "status": "pending",
        "status_reason": None,
        "source_occurrence_id": None,
        "source_generation_slot_id": UUID(draft["sourceGenerationSlotId"]),
    }


def _is_reconcilable(row, reference_date):
    occurrence_date = _db_date(row["occurrence_date"], "occurrence_date")
    return row["status"] == "pending" and can_delete_occurrence(
        occurrence_date, row["status"], reference_date
    )


def _candidate_state(
    snapshot,
    old_plan_item,
    candidate_plan_item,
    effective_date,
    reference_date,
    uuid_factory,
):
    future_rows = [
        dict(row)
        for row in snapshot["occurrences"]
        if _db_date(row["occurrence_date"], "occurrence_date") >= effective_date
    ]
    baseline_by_key = {}
    preserved = []
    for row in future_rows:
        if row["source_generation_slot_id"] is None:
            preserved.append(row)
            continue
        key = (str(row["source_generation_slot_id"]), row["occurrence_date"])
        if _is_old_baseline(row, old_plan_item["generationConfig"]):
            if key in baseline_by_key:
                raise FutureConsistencyError(
                    "Un GenerationSlot tiene occurrences duplicadas en una fecha."
                )
            baseline_by_key[key] = row
        else:
            preserved.append(row)

    _range_start, policy_end = get_materialization_range(
        candidate_plan_item, reference_date
    )
    persisted_end = max(
        (row["occurrence_date"] for row in future_rows),
        default=effective_date,
    )
    horizon_end = max(policy_end, persisted_end)
    desired_drafts = (
        materialize_occurrence_drafts(
            candidate_plan_item, effective_date, horizon_end
        )
        if effective_date <= horizon_end
        else []
    )

    preserved_keys = {
        (str(row["source_generation_slot_id"]), row["occurrence_date"])
        for row in preserved
        if row["source_generation_slot_id"] is not None
    }
    desired_keys = set()
    reconciled = []
    updates = []
    creates = []
    changed_for_conflicts = []
    for draft in desired_drafts:
        key = (
            draft["sourceGenerationSlotId"],
            date.fromisoformat(draft["date"]),
        )
        if key in desired_keys:
            raise FutureConsistencyError(
                "El nuevo motor produciría dos occurrences para slot + fecha."
            )
        desired_keys.add(key)
        if key in preserved_keys:
            continue
        existing = baseline_by_key.get(key)
        if existing is None:
            created = _draft_row(draft, _new_occurrence_id(uuid_factory))
            creates.append(created)
            reconciled.append(created)
            changed_for_conflicts.append(created)
            continue
        updated = {
            **existing,
            "start_time": time.fromisoformat(draft["startTime"]),
            "end_time": time.fromisoformat(draft["endTime"]),
        }
        if (
            updated["start_time"] != existing["start_time"]
            or updated["end_time"] != existing["end_time"]
        ):
            if not _is_reconcilable(existing, reference_date):
                # El status es autoridad de la aparición concreta. Conservarla
                # evita reescribir historia editable sin reactivar su baseline.
                preserved.append(existing)
                continue
            updates.append(updated)
            changed_for_conflicts.append(updated)
        reconciled.append(updated)

    deletes = [
        row
        for key, row in baseline_by_key.items()
        if key not in desired_keys and _is_reconcilable(row, reference_date)
    ]
    preserved.extend(
        row
        for key, row in baseline_by_key.items()
        if key not in desired_keys and not _is_reconcilable(row, reference_date)
    )

    removed_slot_ids = {
        slot["id"] for slot in old_plan_item["generationConfig"]["slots"]
    } - {
        slot["id"] for slot in candidate_plan_item["generationConfig"]["slots"]
    }
    for row in preserved:
        if str(row["source_generation_slot_id"]) in removed_slot_ids:
            row["source_generation_slot_id"] = None

    final_rows = [*preserved, *reconciled]
    return {
        "final_rows": final_rows,
        "updates": updates,
        "deletes": deletes,
        "creates": creates,
        "changed_for_conflicts": changed_for_conflicts,
        "horizon_end": horizon_end,
        "removed_slot_ids": removed_slot_ids,
    }


def _validate_final_state(plan_item_context, candidate, external_rows):
    try:
        week_service._validate_final_internal_state(candidate["final_rows"])
        week_service._validate_external_conflicts(
            plan_item_context,
            candidate["changed_for_conflicts"],
            external_rows,
        )
    except week_service.WeekConflictError as error:
        raise FutureConflictError(error.code, str(error)) from None
    except week_service.WeekConsistencyError as error:
        raise FutureConsistencyError(str(error)) from None


def _serialize_sorted(rows):
    try:
        return week_service._serialize_sorted(rows)
    except week_service.WeekConsistencyError as error:
        raise FutureConsistencyError(str(error)) from None


def _raise_database_error(error):
    if isinstance(
        error, (psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected)
    ):
        raise FutureConflictError(
            "concurrent_modification",
            "La planificación cambió durante Apply Future; vuelve a intentarlo.",
        ) from None
    if isinstance(error, psycopg.errors.UniqueViolation):
        constraint = getattr(error.diag, "constraint_name", None)
        if constraint == "generation_slots_pkey":
            raise FutureConflictError(
                "slot_identity_conflict",
                "Un UUID de GenerationSlot ya pertenece a otra configuración.",
            ) from None
        if constraint == "uq_occurrences_source_generation_slot_date":
            raise FutureConflictError(
                "slot_date_conflict",
                "Un GenerationSlot ya tiene una occurrence en esa fecha.",
            ) from None
    raise FutureUnavailableError("PostgreSQL no pudo completar Apply Future.") from None


def apply_future(plan_item_id, payload, reference_date=None, uuid_factory=uuid4):
    parsed_plan_item_id = _identifier(plan_item_id)
    future_config = validate_apply_future_payload(payload)
    effective_date = date.fromisoformat(future_config["startDate"])
    current_date = reference_date or _today()
    if isinstance(current_date, datetime) or not isinstance(current_date, date):
        raise TypeError("reference_date debe ser date.")
    if is_frozen_date(effective_date, current_date):
        raise FutureConflictError(
            "history_frozen", "La fecha efectiva pertenece al historial congelado."
        )

    try:
        with database.get_connection() as connection:
            with connection.transaction():
                occurrence_repository.set_serializable_transaction(connection)
                if occurrence_repository.lock_plan_item_identity(
                    connection, parsed_plan_item_id
                ) is None:
                    raise FuturePlanItemNotFoundError("El PlanItem no existe.")

                snapshot = _load_snapshot(connection, parsed_plan_item_id)
                old_plan_item = _snapshot_domain(snapshot)
                old_config = old_plan_item["generationConfig"]
                if old_config["mode"] == "manual_dates":
                    raise FutureConflictError(
                        "unsupported_mode",
                        "Apply Future no está disponible para manual_dates.",
                    )
                _validate_snapshot_occurrences(snapshot["occurrences"], old_config)
                if future_config["mode"] != old_config["mode"]:
                    raise FutureConflictError(
                        "mode_change_not_supported",
                        "Apply Future debe conservar el modo recurrente actual.",
                    )

                candidate_config = _preserve_generation_controls(
                    old_config, future_config
                )
                stopped_from_date = candidate_config.get("stoppedFromDate")
                if stopped_from_date is not None and future_config["startDate"] >= stopped_from_date:
                    raise FutureConflictError(
                        "planning_stopped",
                        "La fecha efectiva no puede reactivar una planificación detenida.",
                    )
                candidate_plan_item = {
                    **old_plan_item,
                    "generationConfig": candidate_config,
                }

                requested_ids = [UUID(slot["id"]) for slot in future_config["slots"]]
                occupied = future_schedule_repository.lock_requested_slot_identities(
                    connection, requested_ids
                )
                if any(row["plan_item_id"] != parsed_plan_item_id for row in occupied):
                    raise FutureConflictError(
                        "slot_identity_conflict",
                        "Un UUID de GenerationSlot ya pertenece a otra configuración.",
                    )

                candidate = _candidate_state(
                    snapshot,
                    old_plan_item,
                    candidate_plan_item,
                    effective_date,
                    current_date,
                    uuid_factory,
                )
                delete_ids = [row["id"] for row in candidate["deletes"]]
                update_ids = [row["id"] for row in candidate["updates"]]
                if occurrence_repository.lock_status_context_dependents_for_sources(
                    connection, [*delete_ids, *update_ids]
                ):
                    raise FutureConflictError(
                        "status_context_locked",
                        "Una occurrence que cambiaría conserva contexto de prioridad dependiente.",
                    )

                changed_dates = sorted(
                    {
                        row["occurrence_date"]
                        for row in candidate["changed_for_conflicts"]
                        if row["status"] in BLOCKING_STATUSES
                    }
                )
                external_rows = occurrence_repository.lock_external_blocking_occurrences(
                    connection, parsed_plan_item_id, changed_dates
                )
                _validate_final_state(snapshot["schedule"], candidate, external_rows)

                if future_schedule_repository.delete_occurrences(
                    connection, delete_ids
                ) != len(delete_ids):
                    raise FutureConsistencyError(
                        "No se pudieron eliminar las baseline occurrences bloqueadas."
                    )
                if future_schedule_repository.update_generation_config(
                    connection, parsed_plan_item_id, future_config
                ) != 1:
                    raise FutureConsistencyError(
                        "No se pudo actualizar la generationConfig bloqueada."
                    )

                old_slot_ids = {
                    slot["id"] for slot in old_plan_item["generationConfig"]["slots"]
                }
                surviving_slots = [
                    slot for slot in future_config["slots"] if slot["id"] in old_slot_ids
                ]
                new_slots = [
                    slot for slot in future_config["slots"] if slot["id"] not in old_slot_ids
                ]
                for slot in surviving_slots:
                    if future_schedule_repository.update_generation_slot(
                        connection, slot
                    ) != 1:
                        raise FutureConsistencyError(
                            "No se pudo actualizar un GenerationSlot bloqueado."
                        )
                    if future_config["mode"] == "weekly" and (
                        future_schedule_repository.update_slot_weekday(
                            connection, slot["id"], slot["isoWeekday"]
                        )
                        != 1
                    ):
                        raise FutureConsistencyError(
                            "No se pudo actualizar el weekday de un GenerationSlot."
                        )
                future_schedule_repository.insert_generation_slots(
                    connection,
                    parsed_plan_item_id,
                    new_slots,
                    future_config["mode"],
                )
                removed_ids = [UUID(value) for value in candidate["removed_slot_ids"]]
                if future_schedule_repository.delete_generation_slots(
                    connection, removed_ids
                ) != len(removed_ids):
                    raise FutureConsistencyError(
                        "No se pudieron eliminar los GenerationSlots omitidos."
                    )

                try:
                    future_schedule_repository.update_occurrence_schedules(
                        connection, candidate["updates"]
                    )
                except RuntimeError as error:
                    raise FutureConsistencyError(str(error)) from None
                future_schedule_repository.insert_occurrences(
                    connection, candidate["creates"]
                )

                persisted_rows = future_schedule_repository.list_occurrences_from(
                    connection, parsed_plan_item_id, effective_date
                )
                persisted = _serialize_sorted(persisted_rows)
                expected = _serialize_sorted(candidate["final_rows"])
                if persisted != expected:
                    raise FutureConsistencyError(
                        "El estado persistido no coincide con la reconciliación validada."
                    )
                result = {
                    "planItem": candidate_plan_item,
                    "occurrences": persisted,
                }
    except (
        FutureValidationError,
        FuturePlanItemNotFoundError,
        FutureConflictError,
        FutureConsistencyError,
    ):
        raise
    except database.DatabaseConnectionError as error:
        _raise_database_error(error)
    except psycopg.Error as error:
        _raise_database_error(error)
    return result
