"""Confirmación y resolución transaccional de un source contra segments reales."""

from datetime import datetime, time
import re
from uuid import UUID, uuid4

from occurrence_segment_domain import (
    FROZEN_HISTORY,
    OccurrenceSegmentDomainError,
    OccurrenceSegmentStatusError,
    derive_occurrence_status,
    temporal_phase_for_date,
    validate_segment_status_for_phase,
)
from occurrence_segment_service import _db_time, _validated_occurrence, _validated_segments
from occurrence_structure_domain import OccurrenceStructureDomainError
from repositories import segment_conflict_repository as repository
from scheduling_policy import BLOCKING_STATUSES, HISTORY_EDIT_WINDOW_DAYS, scheduling_priority
from segment_conflict_domain import (
    SegmentConflictDomainError,
    conflict_reason,
    resolution_kind,
    resolve_target_graph,
    same_snapshot,
    subtract_intervals,
)


class SegmentConflictError(RuntimeError):
    def __init__(self, code, message, conflicts=None):
        super().__init__(message)
        self.code = code
        self.conflicts = conflicts


class SegmentConflictValidationError(ValueError):
    pass


def _uuid(value):
    if not isinstance(value, str):
        raise SegmentConflictValidationError("La confirmación requiere UUID canónicos.")
    try:
        parsed = UUID(value)
    except ValueError:
        raise SegmentConflictValidationError("La confirmación requiere UUID canónicos.") from None
    if str(parsed) != value:
        raise SegmentConflictValidationError("La confirmación requiere UUID canónicos.")
    return parsed


def _time(value):
    if not isinstance(value, str) or re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value) is None:
        raise SegmentConflictValidationError("La confirmación requiere horarios HH:MM.")
    return time.fromisoformat(value)


def validate_confirmations(value):
    """None significa primera request; una lista expresa snapshots autorizados."""
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {"confirmations"}:
        raise SegmentConflictValidationError("conflictResolution no es válido.")
    entries = value["confirmations"]
    if not isinstance(entries, list):
        raise SegmentConflictValidationError("confirmations debe ser una lista.")
    result = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) not in (
            {"blocker", "confirmed"},
            {"blocker", "confirmed", "confirmRealizedTimeCorrection"},
        ) or entry["confirmed"] is not True:
            raise SegmentConflictValidationError("Cada confirmación debe ser explícita.")
        if "confirmRealizedTimeCorrection" in entry and entry["confirmRealizedTimeCorrection"] is not True:
            raise SegmentConflictValidationError("La confirmación fuerte debe ser true.")
        snapshot = entry["blocker"]
        if not isinstance(snapshot, dict) or set(snapshot) != {
            "occurrenceId", "segmentId", "startTime", "endTime", "status"
        }:
            raise SegmentConflictValidationError("El snapshot del blocker no es válido.")
        occurrence_id = _uuid(snapshot["occurrenceId"])
        segment_id = _uuid(snapshot["segmentId"])
        start, end = _time(snapshot["startTime"]), _time(snapshot["endTime"])
        if start >= end or snapshot["status"] not in BLOCKING_STATUSES:
            raise SegmentConflictValidationError("El snapshot del blocker no es válido.")
        key = (occurrence_id, segment_id)
        if key in result:
            raise SegmentConflictValidationError("Hay confirmaciones duplicadas.")
        result[key] = entry
    return result


def _blocker_payload(row):
    return {
        "occurrenceId": str(row["occurrence_id"]),
        "segmentId": str(row["segment_id"]),
        "planItemId": str(row["plan_item_id"]),
        "date": row["occurrence_date"].isoformat(),
        "startTime": _db_time(row["start_time"], "blocker.start_time").strftime("%H:%M"),
        "endTime": _db_time(row["end_time"], "blocker.end_time").strftime("%H:%M"),
        "status": row["status"],
    }


def _conflict_payload(rows, source_priority, source_segments):
    conflicts = []
    for row in rows:
        target_priority = scheduling_priority(row["kind"], row["subtype"])
        occupied = [
            (segment["startTime"], segment["endTime"])
            for segment in source_segments
            if segment["status"] in BLOCKING_STATUSES
        ]
        fragments = subtract_intervals(row["start_time"], row["end_time"], occupied)
        conflicts.append({
            "blocker": _blocker_payload(row),
            "requiredAuthorization": conflict_reason(
                source_priority, target_priority, row["status"]
            ),
            "resolutionKind": resolution_kind(
                row["status"], row["start_time"], row["end_time"], fragments
            ),
            "requiresRealizedTimeConfirmation": row["status"] in {
                "completed", "not_finished"
            },
        })
    return conflicts


def _keys(rows):
    return {(row["occurrence_id"], row["segment_id"]) for row in rows}


def resolve_source_conflicts(
    connection, *, source_id, source_date, source_segments, source_priority,
    confirmations, action, now, uuid_factory=uuid4,
):
    """Se invoca dentro de SERIALIZABLE; escribe solo después de revalidar todo."""
    occupying = [segment for segment in source_segments if segment["status"] in BLOCKING_STATUSES]
    rows = repository.list_blockers(connection, source_id, source_date, occupying)
    if not rows:
        if confirmations:
            raise SegmentConflictError(
                "conflict_resolution_stale", "Los blockers confirmados ya no existen.", []
            )
        return False
    conflicts = _conflict_payload(rows, source_priority, occupying)
    if confirmations is None:
        raise SegmentConflictError(
            "segment_conflict_resolution_required",
            "La operación requiere resolver conflictos de horario.", conflicts,
        )

    # El snapshot desbloqueado solo sirve para descubrir IDs. Los parents y sus
    # children se bloquean y después se descubre de nuevo bajo SERIALIZABLE.
    parents = {}
    children = {}
    for target_id in sorted({row["occurrence_id"] for row in rows}):
        parent = repository.lock_target_parent(connection, target_id)
        if parent is None:
            raise SegmentConflictError(
                "conflict_resolution_stale", "Un blocker cambió antes de confirmar.", conflicts
            )
        parents[target_id] = _validated_occurrence(parent)
        children[target_id] = _validated_segments(
            repository.lock_target_segments(connection, target_id), parents[target_id]
        )
    current_rows = repository.list_blockers(connection, source_id, source_date, occupying)
    current_conflicts = _conflict_payload(current_rows, source_priority, occupying)
    current_keys = _keys(current_rows)
    confirmed_keys = set(confirmations)
    if confirmed_keys - current_keys:
        raise SegmentConflictError(
            "conflict_resolution_stale", "Un blocker confirmado cambió o desapareció.", current_conflicts
        )
    if current_keys - confirmed_keys:
        raise SegmentConflictError(
            "segment_conflict_resolution_required",
            "Aparecieron blockers sin confirmar.", current_conflicts,
        )
    for row in current_rows:
        entry = confirmations[(row["occurrence_id"], row["segment_id"])]
        if not same_snapshot(entry["blocker"], {
            "occurrenceId": row["occurrence_id"],
            "segmentId": row["segment_id"],
            "startTime": row["start_time"],
            "endTime": row["end_time"],
            "status": row["status"],
        }):
            raise SegmentConflictError(
                "conflict_resolution_stale", "El blocker confirmado cambió.", current_conflicts
            )
        if row["status"] in {"completed", "not_finished"} and entry.get(
            "confirmRealizedTimeCorrection"
        ) is not True:
            raise SegmentConflictError(
                "segment_conflict_resolution_required",
                "Corregir tiempo realizado requiere confirmación explícita adicional.",
                current_conflicts,
            )

    planned = []
    for target_id in sorted(parents):
        parent = parents[target_id]
        phase = temporal_phase_for_date(
            parent["date"], now.date(), HISTORY_EDIT_WINDOW_DAYS
        )
        if phase == FROZEN_HISTORY:
            raise SegmentConflictError(
                "conflict_resolution_frozen",
                "No se puede modificar historia congelada; ajusta el source.",
                current_conflicts,
            )
        target_rows = [row for row in current_rows if row["occurrence_id"] == target_id]
        occupied_by_segment = {
            row["segment_id"]: [
                (item["startTime"], item["endTime"])
                for item in occupying
                if item["startTime"] < row["end_time"]
                and item["endTime"] > row["start_time"]
            ] for row in target_rows
        }
        try:
            candidate = resolve_target_graph(
                parent, children[target_id], occupied_by_segment, phase, uuid_factory
            )
            for segment in candidate:
                validate_segment_status_for_phase(
                    segment["status"], phase,
                    datetime.combine(parent["date"], segment["endTime"]), now,
                )
            aggregate = derive_occurrence_status(candidate, phase)
        except SegmentConflictDomainError as error:
            raise SegmentConflictError(error.code, str(error), current_conflicts) from None
        except (OccurrenceStructureDomainError, OccurrenceSegmentStatusError,
                OccurrenceSegmentDomainError) as error:
            raise SegmentConflictError(
                "conflict_resolution_invalid_target",
                "El estado final del blocker no cumple la integridad temporal.",
                current_conflicts,
            ) from None
        reason = (
            "user_forced_override"
            if any(row["status"] in {"completed", "not_finished"} for row in target_rows)
            else conflict_reason(
                source_priority,
                scheduling_priority(target_rows[0]["kind"], target_rows[0]["subtype"]),
                target_rows[0]["status"],
            )
        )
        planned.append((target_id, children[target_id], candidate, aggregate, reason))

    # No SQL de escritura ocurre antes de que TODOS los targets sean válidos.
    for target_id, before, after, aggregate, reason in planned:
        old = {segment["id"]: segment for segment in before}
        for segment in after:
            if segment["id"] in old:
                if segment != old[segment["id"]] and repository.update_target_segment(
                    connection, target_id, segment["id"], segment
                ) != 1:
                    raise SegmentConflictError("conflict_resolution_stale", "Un segment cambió.")
            elif repository.insert_target_segment(connection, target_id, segment) != 1:
                raise SegmentConflictError("conflict_resolution_stale", "No se insertó un fragmento.")
        if repository.update_target_context(
            connection, target_id, aggregate, reason, source_id
        ) != 1:
            raise SegmentConflictError("conflict_resolution_stale", "Un parent cambió.")
    if repository.update_source_context(connection, source_id, action) != 1:
        raise SegmentConflictError("conflict_resolution_stale", "El source cambió.")
    return True
