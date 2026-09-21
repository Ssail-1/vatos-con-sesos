"""Comandos estructurales atómicos para una occurrence y sus segments."""

import re
from datetime import datetime, time
from uuid import UUID, uuid4

import psycopg
from psycopg import IsolationLevel

import database
from occurrence_segment_domain import (
    FROZEN_HISTORY,
    PREVIOUS_EDITABLE_DAY,
    SEGMENT_STATUSES,
    OccurrenceSegmentDomainError,
    OccurrenceSegmentStatusError,
    derive_occurrence_status,
    temporal_phase_for_date,
    validate_segment_status_for_phase,
)
from occurrence_segment_service import (
    OccurrenceSegmentConsistencyError,
    _authoritative_now,
    _serialize_blockers,
    _validated_occurrence,
    _validated_segments,
)
from occurrence_structure_domain import (
    OccurrenceStructureDomainError,
    translate_segments,
    validate_final_segments,
)
from repositories import occurrence_segment_repository as repository
from scheduling_policy import BLOCKING_STATUSES, HISTORY_EDIT_WINDOW_DAYS


class OccurrenceStructureError(RuntimeError):
    pass


class OccurrenceStructureValidationError(OccurrenceStructureError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class OccurrenceStructureNotFoundError(OccurrenceStructureError):
    pass


class OccurrenceStructureConflictError(OccurrenceStructureError):
    def __init__(self, code, message, blockers=None):
        super().__init__(message)
        self.code = code
        self.blockers = blockers


class OccurrenceStructureConsistencyError(OccurrenceStructureError):
    pass


class OccurrenceStructureUnavailableError(OccurrenceStructureError):
    pass


def _invalid(message, code="invalid_payload"):
    raise OccurrenceStructureValidationError(code, message)


def _uuid(value):
    if not isinstance(value, str):
        _invalid("El identificador debe ser un UUID.")
    try:
        return UUID(value)
    except ValueError:
        _invalid("El identificador debe ser un UUID.")


def _time(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-2][0-9]:[0-5][0-9]", value) is None:
        _invalid("El horario debe usar HH:MM.")
    try:
        return time.fromisoformat(value)
    except ValueError:
        _invalid("El horario debe usar HH:MM válido.")


def _envelope(payload, structure=False):
    keys = {"startTime", "endTime", "segments"} if structure else {"startTime", "endTime"}
    if not isinstance(payload, dict) or set(payload) != keys:
        _invalid("El payload no contiene exactamente los campos requeridos.")
    return _time(payload["startTime"]), _time(payload["endTime"])


def _candidate_structure(entries, persisted):
    if not isinstance(entries, list) or not entries:
        _invalid("Una occurrence requiere al menos un segment.", "occurrence_requires_segment")
    existing = {segment["id"]: segment for segment in persisted}
    seen = set()
    candidates = []
    for entry in entries:
        if not isinstance(entry, dict):
            _invalid("Cada segment debe ser un objeto.")
        if "id" in entry:
            if set(entry) != {"id", "startTime", "endTime"}:
                _invalid("Un segment existente no permite editar status ni otros campos.")
            segment_id = _uuid(entry["id"])
            if segment_id not in existing:
                _invalid("El segment no pertenece a esta occurrence.", "segment_not_owned")
            if segment_id in seen:
                _invalid("El segment aparece más de una vez.", "duplicate_segment_id")
            status = existing[segment_id]["status"]
        else:
            if set(entry) != {"startTime", "endTime", "status"}:
                _invalid("Un segment nuevo requiere horarios y status explícito.")
            status = entry["status"]
            if not isinstance(status, str) or status not in SEGMENT_STATUSES:
                _invalid("El status del segment no es canónico.")
            segment_id = uuid4()
        seen.add(segment_id)
        candidates.append({
            "id": segment_id,
            "startTime": _time(entry["startTime"]),
            "endTime": _time(entry["endTime"]),
            "status": status,
        })
    return candidates


def _final_state(operation, payload, occurrence, persisted):
    start, end = _envelope(payload, structure=operation == "structure")
    if operation == "translate":
        candidates = translate_segments(
            occurrence["startTime"], occurrence["endTime"], start, end, persisted
        )
    elif operation == "structure":
        candidates = validate_final_segments(
            start, end, _candidate_structure(payload["segments"], persisted)
        )
    else:
        candidates = validate_final_segments(start, end, [{
            "id": uuid4(), "startTime": start, "endTime": end,
            "status": occurrence["status"],
        }])
    return start, end, candidates


def _validate_temporal(occurrence, persisted, candidates, now):
    phase = temporal_phase_for_date(
        occurrence["date"], now.date(), HISTORY_EDIT_WINDOW_DAYS
    )
    if phase == FROZEN_HISTORY:
        raise OccurrenceStructureConflictError(
            "history_frozen", "El historial congelado es de solo lectura."
        )
    if phase == PREVIOUS_EDITABLE_DAY and any(
        segment["status"] in {"pending", "in_progress"} for segment in persisted
    ):
        raise OccurrenceStructureConflictError(
            "temporal_reconciliation_required",
            "La occurrence histórica requiere reconciliación previa.",
        )
    for segment in candidates:
        try:
            validate_segment_status_for_phase(
                segment["status"], phase,
                datetime.combine(occurrence["date"], segment["endTime"]), now,
            )
        except OccurrenceSegmentStatusError as error:
            raise OccurrenceStructureConflictError(error.code, str(error)) from None
    try:
        return derive_occurrence_status(candidates, phase)
    except OccurrenceSegmentDomainError:
        raise OccurrenceStructureConsistencyError(
            "El estado final no permite derivar un aggregate."
        ) from None


def _persist(connection, occurrence, persisted, candidates, start, end, aggregate):
    old = {segment["id"]: segment for segment in persisted}
    final_ids = {segment["id"] for segment in candidates}
    # La exclusión de siblings es diferida; el set final se validó antes de escribir.
    for segment in candidates:
        if segment["id"] in old:
            if (segment["startTime"], segment["endTime"]) != (
                old[segment["id"]]["startTime"], old[segment["id"]]["endTime"]
            ) and repository.update_segment_times(
                connection, segment["id"], occurrence["id"],
                segment["startTime"], segment["endTime"]
            ) != 1:
                raise OccurrenceStructureConsistencyError("No se actualizó un segment bloqueado.")
        elif repository.insert_segment(connection, segment, occurrence["id"]) != 1:
            raise OccurrenceStructureConsistencyError("No se insertó un segment.")
    deleted = list(old.keys() - final_ids)
    if repository.delete_segments(connection, occurrence["id"], deleted) != len(deleted):
        raise OccurrenceStructureConsistencyError("No se eliminaron todos los segments omitidos.")
    if repository.update_occurrence_structure(
        connection, occurrence["id"], start, end, aggregate
    ) != 1:
        raise OccurrenceStructureConsistencyError("No se actualizó el parent bloqueado.")


def _execute(operation, occurrence_id, payload, now=None):
    parsed_id = _uuid(occurrence_id)
    # La validación de forma ocurre antes de abrir conexión; las identidades se
    # validan contra children bloqueados dentro de la transacción.
    _envelope(payload, structure=operation == "structure")
    current = _authoritative_now(now)
    try:
        with database.get_connection() as connection:
            connection.isolation_level = IsolationLevel.SERIALIZABLE
            with connection.transaction():
                row = repository.lock_occurrence(connection, parsed_id)
                if row is None:
                    raise OccurrenceStructureNotFoundError("La occurrence no existe.")
                occurrence = _validated_occurrence(row)
                persisted = _validated_segments(
                    repository.lock_occurrence_segments(connection, parsed_id),
                    occurrence,
                )
                start, end, candidates = _final_state(
                    operation, payload, occurrence, persisted
                )
                aggregate = _validate_temporal(occurrence, persisted, candidates, current)
                blockers = repository.lock_external_blockers_for_candidates(
                    connection, parsed_id, occurrence["date"],
                    [segment for segment in candidates if segment["status"] in BLOCKING_STATUSES],
                    BLOCKING_STATUSES,
                )
                if blockers:
                    raise OccurrenceStructureConflictError(
                        "occurrence_structure_conflict",
                        "La estructura solicitada solapa otros segments ocupantes.",
                        _serialize_blockers(blockers),
                    )
                _persist(connection, occurrence, persisted, candidates, start, end, aggregate)
    except (OccurrenceStructureError,):
        raise
    except OccurrenceStructureDomainError as error:
        raise OccurrenceStructureValidationError(error.code, str(error)) from None
    except OccurrenceSegmentConsistencyError as error:
        raise OccurrenceStructureConsistencyError(str(error)) from None
    except database.DatabaseConnectionError:
        raise OccurrenceStructureUnavailableError("PostgreSQL no pudo completar la operación.") from None
    except (psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected):
        raise OccurrenceStructureConflictError(
            "concurrent_conflict", "El estado cambió durante la operación; vuelve a intentarlo."
        ) from None
    except psycopg.Error:
        raise OccurrenceStructureUnavailableError("PostgreSQL no pudo completar la operación.") from None
    return {
        "status": "ok",
        "occurrenceId": str(parsed_id),
        "occurrenceStatus": aggregate,
        "segmentIds": [str(segment["id"]) for segment in candidates],
    }


def translate_occurrence(occurrence_id, payload, now=None):
    return _execute("translate", occurrence_id, payload, now)


def replace_occurrence_structure(occurrence_id, payload, now=None):
    return _execute("structure", occurrence_id, payload, now)


def reset_occurrence_segmentation(occurrence_id, payload, now=None):
    return _execute("reset", occurrence_id, payload, now)
