"""Atomic planning cutoffs anchored to a persisted owning occurrence."""

from datetime import date, datetime, timedelta
from uuid import UUID

import psycopg

import database
from repositories import occurrence_repository, planning_termination_repository as repository


SCOPES = frozenset({"slot", "recurring", "future"})


class PlanningTerminationError(RuntimeError):
    pass


class PlanningTerminationValidationError(PlanningTerminationError):
    pass


class PlanningTerminationNotFoundError(PlanningTerminationError):
    pass


class PlanningTerminationConflictError(PlanningTerminationError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class PlanningTerminationConsistencyError(PlanningTerminationError):
    pass


class PlanningTerminationUnavailableError(PlanningTerminationError):
    pass


def _identifier(value):
    try:
        return UUID(value) if isinstance(value, str) else None
    except (ValueError, AttributeError):
        return None


def _next_date(value):
    # PostgreSQL DATE has no representable calendar successor after date.max.
    return value + timedelta(days=1) if value < date.max else None


def terminate_after_occurrence(occurrence_id, scope, reference_date=None):
    """Stop one slot, every recurring slot, or every future appearance.

    One SERIALIZABLE transaction owns both the recurrence cutoff and cleanup.
    The client supplies only the selected occurrence ID; all scope is derived
    from locked database rows and the server's local calendar date.
    """
    parsed_id = _identifier(occurrence_id)
    if parsed_id is None or scope not in SCOPES:
        raise PlanningTerminationValidationError("La acción o el ID no es válido.")
    current_date = reference_date if reference_date is not None else datetime.now().date()
    if isinstance(current_date, datetime) or not isinstance(current_date, date):
        raise TypeError("reference_date debe ser date.")

    try:
        with database.get_connection() as connection:
            with connection.transaction():
                occurrence_repository.set_serializable_transaction(connection)
                owner = occurrence_repository.find_occurrence_owner(connection, parsed_id)
                if owner is None:
                    raise PlanningTerminationNotFoundError("La aparición no existe.")
                plan_item_id = owner["plan_item_id"]
                if occurrence_repository.lock_plan_item_identity(connection, plan_item_id) is None:
                    raise PlanningTerminationConsistencyError("El PlanItem no existe.")
                config = occurrence_repository.lock_plan_item_context(connection, plan_item_id)
                if config is None:
                    raise PlanningTerminationConsistencyError("El PlanItem no tiene configuración.")
                slots = repository.lock_slots(connection, plan_item_id)
                selected = occurrence_repository.lock_occurrence_for_delete(connection, parsed_id)
                if selected is None or selected["plan_item_id"] != plan_item_id:
                    raise PlanningTerminationConflictError(
                        "concurrent_conflict", "La aparición cambió durante la acción."
                    )
                cutoff = selected["occurrence_date"]
                if not isinstance(cutoff, date) or isinstance(cutoff, datetime):
                    raise PlanningTerminationConsistencyError("La fecha persistida no es válida.")
                if cutoff < current_date:
                    raise PlanningTerminationConflictError(
                        "history_frozen", "No se puede detener planificación desde una fecha histórica."
                    )
                source_slot = selected["source_generation_slot_id"]
                slot_ids = {row["id"] for row in slots}
                if source_slot is not None and source_slot not in slot_ids:
                    raise PlanningTerminationConsistencyError("La procedencia del horario no es válida.")
                if scope == "slot" and (source_slot is None or config["mode"] == "manual_dates"):
                    raise PlanningTerminationConflictError(
                        "slot_not_applicable", "La aparición no procede de un horario recurrente."
                    )
                if scope == "recurring" and config["mode"] == "manual_dates":
                    raise PlanningTerminationConflictError(
                        "recurring_not_applicable", "Este PlanItem no tiene planificación recurrente."
                    )

                future = repository.lock_future_occurrences(connection, plan_item_id, cutoff)
                targets = [
                    row for row in future
                    if scope == "future"
                    or (scope == "slot" and row["source_generation_slot_id"] == source_slot)
                    or (scope == "recurring" and row["source_generation_slot_id"] is not None)
                ]
                target_ids = [row["id"] for row in targets]
                if repository.external_source_dependents(connection, target_ids):
                    raise PlanningTerminationConflictError(
                        "source_provenance_locked",
                        "Una aparición futura conserva referencias históricas externas.",
                    )

                if scope == "slot":
                    if repository.shorten_slot(connection, source_slot, cutoff) != 1:
                        raise PlanningTerminationConsistencyError("No se pudo detener el horario.")
                else:
                    if config["mode"] in {"weekly", "interval_days"}:
                        for slot in slots:
                            if repository.shorten_slot(connection, slot["id"], cutoff) != 1:
                                raise PlanningTerminationConsistencyError("No se pudo detener un horario.")
                    next_date = _next_date(cutoff)
                    if next_date is not None and repository.shorten_schedule(
                        connection, plan_item_id, next_date
                    ) != 1:
                        raise PlanningTerminationConsistencyError("No se pudo detener la planificación.")
                if repository.delete_occurrences(connection, target_ids) != len(target_ids):
                    raise PlanningTerminationConsistencyError("No se pudieron retirar las apariciones futuras.")
                return {
                    "status": "ok",
                    "scope": scope,
                    "selectedOccurrenceId": str(parsed_id),
                    "planItemId": str(plan_item_id),
                    "cutoffDate": cutoff.isoformat(),
                    "deletedOccurrenceIds": [str(value) for value in target_ids],
                }
    except PlanningTerminationError:
        raise
    except database.DatabaseConnectionError:
        raise PlanningTerminationUnavailableError("PostgreSQL no pudo completar la acción.") from None
    except (psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected):
        raise PlanningTerminationConflictError(
            "concurrent_conflict", "La planificación cambió; actualiza e inténtalo de nuevo."
        ) from None
    except psycopg.errors.ForeignKeyViolation:
        raise PlanningTerminationConflictError(
            "source_provenance_locked", "Una aparición futura conserva referencias históricas."
        ) from None
    except psycopg.Error:
        raise PlanningTerminationUnavailableError("PostgreSQL no pudo completar la acción.") from None
