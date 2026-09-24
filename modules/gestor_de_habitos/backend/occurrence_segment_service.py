"""Mutación de status y reconciliación persistente de OccurrenceSegments."""

from datetime import date, datetime, time
from uuid import UUID

import psycopg
from psycopg import IsolationLevel

import database
from occurrence_segment_domain import (
    PREVIOUS_EDITABLE_DAY,
    OccurrenceSegmentDomainError,
    OccurrenceSegmentStatusError,
    SEGMENT_STATUSES,
    derive_occurrence_status,
    reconcile_segment_status,
    temporal_phase_for_date,
    validate_segment_status_for_phase,
)
from repositories import occurrence_segment_repository
from scheduling_policy import BLOCKING_STATUSES, HISTORY_EDIT_WINDOW_DAYS


class OccurrenceSegmentServiceError(RuntimeError):
    """Error seguro compartido por status mutation y reconciliación."""


class OccurrenceSegmentValidationError(OccurrenceSegmentServiceError):
    """El identificador o payload no cumple el contrato HTTP."""


class OccurrenceSegmentNotFoundError(OccurrenceSegmentServiceError):
    """El segmento solicitado no existe."""


class OccurrenceSegmentConflictError(OccurrenceSegmentServiceError):
    """La operación contradice integridad temporal o de agenda."""

    def __init__(self, code, message, blockers=None):
        super().__init__(message)
        self.code = code
        self.blockers = blockers


class OccurrenceSegmentConsistencyError(OccurrenceSegmentServiceError):
    """El grafo persistido no cumple el contrato OccurrenceSegment."""


class OccurrenceSegmentUnavailableError(OccurrenceSegmentServiceError):
    """PostgreSQL no pudo completar la operación."""


def _now():
    # El proyecto trabaja con calendario local y TIME sin timezone.
    return datetime.now()


def _authoritative_now(value):
    current = value if value is not None else _now()
    if not isinstance(current, datetime) or current.tzinfo is not None:
        raise TypeError("now debe ser un datetime local sin timezone.")
    return current


def _invalid(message):
    raise OccurrenceSegmentValidationError(message)


def _segment_id(value):
    if not isinstance(value, str):
        _invalid("segment_id debe ser un UUID válido.")
    try:
        return UUID(value)
    except (ValueError, AttributeError):
        _invalid("segment_id debe ser un UUID válido.")


def validate_status_payload(payload):
    if not isinstance(payload, dict) or set(payload) != {"status"}:
        _invalid("El payload debe contener exactamente status.")
    status = payload["status"]
    if status not in SEGMENT_STATUSES:
        _invalid("status no pertenece al contrato de OccurrenceSegment.")
    return status


def validate_reconciliation_payload(payload):
    if payload is not None:
        _invalid("La reconciliación no acepta parámetros temporales del cliente.")


def _db_uuid(value, field_name):
    if not isinstance(value, UUID):
        raise OccurrenceSegmentConsistencyError(f"{field_name} no contiene UUID.")
    return value


def _db_date(value, field_name):
    if isinstance(value, datetime) or not isinstance(value, date):
        raise OccurrenceSegmentConsistencyError(f"{field_name} no contiene DATE.")
    return value


def _db_time(value, field_name):
    if not isinstance(value, time) or value.second != 0 or value.microsecond != 0:
        raise OccurrenceSegmentConsistencyError(
            f"{field_name} no puede representarse como HH:MM."
        )
    return value


def _validated_occurrence(row):
    occurrence = {
        "id": _db_uuid(row["id"], "occurrences.id"),
        "planItemId": _db_uuid(row["plan_item_id"], "occurrences.plan_item_id"),
        "date": _db_date(row["occurrence_date"], "occurrences.occurrence_date"),
        "startTime": _db_time(row["start_time"], "occurrences.start_time"),
        "endTime": _db_time(row["end_time"], "occurrences.end_time"),
        "status": row["status"],
    }
    if occurrence["startTime"] >= occurrence["endTime"]:
        raise OccurrenceSegmentConsistencyError(
            "La occurrence persistida tiene un intervalo inválido."
        )
    if occurrence["status"] not in SEGMENT_STATUSES:
        raise OccurrenceSegmentConsistencyError(
            "La occurrence persistida tiene un status inválido."
        )
    return occurrence


def _validated_segments(rows, occurrence):
    if not rows:
        raise OccurrenceSegmentConsistencyError(
            "La occurrence persistida no contiene segmentos."
        )
    segments = []
    segment_ids = set()
    for row in rows:
        segment_id = _db_uuid(row["id"], "occurrence_segments.id")
        if segment_id in segment_ids:
            raise OccurrenceSegmentConsistencyError(
                "La occurrence contiene IDs de segmento duplicados."
            )
        segment_ids.add(segment_id)
        if (
            _db_uuid(row["occurrence_id"], "occurrence_segments.occurrence_id")
            != occurrence["id"]
        ):
            raise OccurrenceSegmentConsistencyError(
                "Un segmento pertenece a otra occurrence."
            )
        start_time = _db_time(row["start_time"], "occurrence_segments.start_time")
        end_time = _db_time(row["end_time"], "occurrence_segments.end_time")
        status = row["status"]
        if start_time >= end_time:
            raise OccurrenceSegmentConsistencyError(
                "Un segmento persistido tiene un intervalo inválido."
            )
        if (
            start_time < occurrence["startTime"]
            or end_time > occurrence["endTime"]
        ):
            raise OccurrenceSegmentConsistencyError(
                "Un segmento queda fuera del envelope de su occurrence."
            )
        if status not in SEGMENT_STATUSES:
            raise OccurrenceSegmentConsistencyError(
                "Un segmento persistido tiene un status inválido."
            )
        segments.append(
            {
                "id": segment_id,
                "startTime": start_time,
                "endTime": end_time,
                "status": status,
            }
        )
    return segments


def _domain_status_validation(status, phase, occurrence_date, end_time, now):
    try:
        validate_segment_status_for_phase(
            status,
            phase,
            datetime.combine(occurrence_date, end_time),
            now,
        )
    except OccurrenceSegmentStatusError as error:
        raise OccurrenceSegmentConflictError(error.code, str(error)) from None


def _derive_status(segments, phase):
    try:
        return derive_occurrence_status(segments, phase)
    except OccurrenceSegmentDomainError:
        raise OccurrenceSegmentConsistencyError(
            "Los segmentos no permiten derivar un aggregate válido."
        ) from None


def _serialize_blockers(rows):
    blockers = []
    for row in rows:
        status = row["status"]
        if status not in BLOCKING_STATUSES:
            raise OccurrenceSegmentConsistencyError(
                "PostgreSQL devolvió un blocker con status no ocupante."
            )
        blockers.append(
            {
                "occurrenceId": str(
                    _db_uuid(row["occurrence_id"], "blocker.occurrence_id")
                ),
                "segmentId": str(_db_uuid(row["segment_id"], "blocker.segment_id")),
                "planItemId": str(
                    _db_uuid(row["plan_item_id"], "blocker.plan_item_id")
                ),
                "date": _db_date(
                    row["occurrence_date"], "blocker.occurrence_date"
                ).isoformat(),
                "startTime": _db_time(
                    row["start_time"], "blocker.start_time"
                ).strftime("%H:%M"),
                "endTime": _db_time(
                    row["end_time"], "blocker.end_time"
                ).strftime("%H:%M"),
                "status": status,
            }
        )
    return blockers


def _raise_database_error(error):
    if isinstance(
        error, (psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected)
    ):
        raise OccurrenceSegmentConflictError(
            "concurrent_conflict",
            "El estado cambió durante la operación; vuelve a intentarlo.",
        ) from None
    raise OccurrenceSegmentUnavailableError(
        "PostgreSQL no pudo completar la operación de segmentos."
    ) from None


def mutate_segment_status(segment_id, payload, now=None):
    """Cambia un child y deriva su parent dentro de una sola transacción."""
    parsed_segment_id = _segment_id(segment_id)
    requested_status = validate_status_payload(payload)
    current_datetime = _authoritative_now(now)

    try:
        with database.get_connection() as connection:
            connection.isolation_level = IsolationLevel.SERIALIZABLE
            with connection.transaction():
                owner = occurrence_segment_repository.find_segment_owner(
                    connection, parsed_segment_id
                )
                if owner is None:
                    raise OccurrenceSegmentNotFoundError("El segmento no existe.")
                occurrence_id = _db_uuid(
                    owner["occurrence_id"], "occurrence_segments.occurrence_id"
                )
                occurrence_row = occurrence_segment_repository.lock_occurrence(
                    connection, occurrence_id
                )
                if occurrence_row is None:
                    raise OccurrenceSegmentNotFoundError("El segmento no existe.")
                occurrence = _validated_occurrence(occurrence_row)
                segment_rows = occurrence_segment_repository.lock_occurrence_segments(
                    connection, occurrence_id
                )
                segments = _validated_segments(segment_rows, occurrence)
                target = next(
                    (
                        segment
                        for segment in segments
                        if segment["id"] == parsed_segment_id
                    ),
                    None,
                )
                if target is None:
                    raise OccurrenceSegmentNotFoundError("El segmento no existe.")

                phase = temporal_phase_for_date(
                    occurrence["date"],
                    current_datetime.date(),
                    HISTORY_EDIT_WINDOW_DAYS,
                )
                _domain_status_validation(
                    requested_status,
                    phase,
                    occurrence["date"],
                    target["endTime"],
                    current_datetime,
                )
                candidates = [
                    {
                        **segment,
                        "status": (
                            requested_status
                            if segment["id"] == parsed_segment_id
                            else segment["status"]
                        ),
                    }
                    for segment in segments
                ]
                if phase == PREVIOUS_EDITABLE_DAY and any(
                    segment["status"] in {"pending", "in_progress"}
                    for segment in candidates
                ):
                    raise OccurrenceSegmentConflictError(
                        "temporal_reconciliation_required",
                        "La occurrence histórica requiere reconciliación previa.",
                    )
                aggregate = _derive_status(candidates, phase)

                if requested_status in BLOCKING_STATUSES:
                    blocker_rows = occurrence_segment_repository.list_blocking_overlaps(
                        connection,
                        occurrence_id,
                        occurrence["date"],
                        target["startTime"],
                        target["endTime"],
                        BLOCKING_STATUSES,
                    )
                    if blocker_rows:
                        raise OccurrenceSegmentConflictError(
                            "segment_status_conflict",
                            "El status solicitado solapa otro segmento ocupante.",
                            _serialize_blockers(blocker_rows),
                        )

                if occurrence_segment_repository.update_segment_status(
                    connection, parsed_segment_id, requested_status
                ) != 1:
                    raise OccurrenceSegmentConsistencyError(
                        "No se pudo actualizar el segmento bloqueado."
                    )
                if occurrence_segment_repository.update_occurrence_status(
                    connection, occurrence_id, aggregate
                ) != 1:
                    raise OccurrenceSegmentConsistencyError(
                        "No se pudo actualizar el aggregate bloqueado."
                    )
    except (
        OccurrenceSegmentValidationError,
        OccurrenceSegmentNotFoundError,
        OccurrenceSegmentConflictError,
        OccurrenceSegmentConsistencyError,
    ):
        raise
    except database.DatabaseConnectionError as error:
        _raise_database_error(error)
    except psycopg.Error as error:
        _raise_database_error(error)

    return {
        "status": "ok",
        "occurrenceId": str(occurrence_id),
        "segmentId": str(parsed_segment_id),
        "segmentStatus": requested_status,
        "occurrenceStatus": aggregate,
    }


def reconcile_planner(payload=None, now=None):
    """Normaliza todos los segmentos históricos en una transacción idempotente."""
    validate_reconciliation_payload(payload)
    current_datetime = _authoritative_now(now)
    updated_occurrences = 0
    updated_segments = 0

    try:
        with database.get_connection() as connection:
            connection.isolation_level = IsolationLevel.SERIALIZABLE
            with connection.transaction():
                occurrence_rows = (
                    occurrence_segment_repository.lock_historical_occurrences(
                        connection, current_datetime.date()
                    )
                )
                occurrence_ids = [
                    _db_uuid(row["id"], "occurrences.id")
                    for row in occurrence_rows
                ]
                segment_rows = (
                    occurrence_segment_repository.lock_segments_for_occurrences(
                        connection, occurrence_ids
                    )
                )
                rows_by_occurrence = {occurrence_id: [] for occurrence_id in occurrence_ids}
                for row in segment_rows:
                    parent_id = _db_uuid(
                        row["occurrence_id"], "occurrence_segments.occurrence_id"
                    )
                    if parent_id not in rows_by_occurrence:
                        raise OccurrenceSegmentConsistencyError(
                            "Un segmento histórico no tiene parent bloqueado."
                        )
                    rows_by_occurrence[parent_id].append(row)

                for occurrence_row in occurrence_rows:
                    occurrence = _validated_occurrence(occurrence_row)
                    segments = _validated_segments(
                        rows_by_occurrence[occurrence["id"]], occurrence
                    )
                    phase = temporal_phase_for_date(
                        occurrence["date"],
                        current_datetime.date(),
                        HISTORY_EDIT_WINDOW_DAYS,
                    )
                    candidates = [
                        {
                            **segment,
                            "status": reconcile_segment_status(segment["status"]),
                        }
                        for segment in segments
                    ]
                    aggregate = _derive_status(candidates, phase)
                    graph_changed = False
                    for persisted, candidate in zip(
                        segments, candidates, strict=True
                    ):
                        if persisted["status"] == candidate["status"]:
                            continue
                        if occurrence_segment_repository.update_segment_status(
                            connection, persisted["id"], candidate["status"]
                        ) != 1:
                            raise OccurrenceSegmentConsistencyError(
                                "No se pudo reconciliar un segmento bloqueado."
                            )
                        updated_segments += 1
                        graph_changed = True
                    if occurrence["status"] != aggregate:
                        if occurrence_segment_repository.update_occurrence_status(
                            connection, occurrence["id"], aggregate
                        ) != 1:
                            raise OccurrenceSegmentConsistencyError(
                                "No se pudo reconciliar un aggregate bloqueado."
                            )
                        graph_changed = True
                    if graph_changed:
                        updated_occurrences += 1
    except (
        OccurrenceSegmentValidationError,
        OccurrenceSegmentConflictError,
        OccurrenceSegmentConsistencyError,
    ):
        raise
    except database.DatabaseConnectionError as error:
        _raise_database_error(error)
    except psycopg.Error as error:
        _raise_database_error(error)

    return {
        "status": "ok",
        "updatedOccurrences": updated_occurrences,
        "updatedSegments": updated_segments,
    }
