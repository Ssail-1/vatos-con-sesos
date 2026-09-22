"""Planificación pura de conflictos entre intervalos de OccurrenceSegments.

La confirmación HTTP se valida por separado: estas funciones solo describen el
resultado estructural de restar tiempo ocupante ya autorizado.
"""

from datetime import time
from uuid import UUID

from occurrence_structure_domain import validate_final_segments
from scheduling_policy import time_ranges_overlap


class SegmentConflictDomainError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def conflict_reason(source_priority, target_priority, target_status):
    """El tiempo realizado siempre requiere corrección forzada consciente."""
    if target_status in {"completed", "not_finished"}:
        return "user_forced_override"
    return (
        "priority_override"
        if source_priority > target_priority
        else "user_forced_override"
    )


def subtract_intervals(start, end, occupied):
    """Resta intervalos [start,end) ordenados; no altera sus argumentos."""
    fragments = [(start, end)]
    for source_start, source_end in sorted(occupied):
        next_fragments = []
        for left, right in fragments:
            if not time_ranges_overlap(left, right, source_start, source_end):
                next_fragments.append((left, right))
                continue
            if left < source_start:
                next_fragments.append((left, min(source_start, right)))
            if source_end < right:
                next_fragments.append((max(source_end, left), right))
        fragments = next_fragments
    return fragments


def resolution_kind(status, original_start, original_end, fragments):
    """Clasificación estable de la consecuencia concreta que muestra el 409."""
    if not fragments:
        return "cancel_segment" if status != "in_progress" else "undefined_in_progress"
    if len(fragments) > 1:
        return "split_segment" if status != "in_progress" else "undefined_in_progress"
    if fragments[0] == (original_start, original_end):
        return "unchanged"
    if status == "in_progress" and fragments[0][0] == original_start:
        return "interrupt_in_progress"
    return "trim_segment"


def resolve_target_segment(segment, occupied, temporal_phase, uuid_factory):
    """Devuelve fragmentos finales; los casos in_progress indefinidos se rechazan."""
    fragments = subtract_intervals(
        segment["startTime"], segment["endTime"], occupied
    )
    kind = resolution_kind(
        segment["status"], segment["startTime"], segment["endTime"], fragments
    )
    if kind == "undefined_in_progress":
        raise SegmentConflictDomainError(
            "segment_resolution_undefined",
            "La norma no define un resultado único para esta interrupción en progreso.",
        )
    if kind == "unchanged":
        return [dict(segment)]
    if not fragments:
        return [{**segment, "status": "cancelled"}]
    result = []
    for index, (start, end) in enumerate(fragments):
        status = segment["status"]
        if status == "in_progress" and start == segment["startTime"]:
            status = "not_finished"
        if status == "in_progress" and temporal_phase != "current_day":
            raise SegmentConflictDomainError(
                "segment_resolution_undefined",
                "El status in_progress no es válido en esta fase temporal.",
            )
        result.append({
            **segment,
            "id": segment["id"] if index == 0 else uuid_factory(),
            "startTime": start,
            "endTime": end,
            "status": status,
        })
    return result


def resolve_target_graph(parent, segments, occupied_by_segment, phase, uuid_factory):
    """Resuelve todos los children afectados y reutiliza el validador estructural."""
    candidates = []
    for segment in segments:
        occupied = occupied_by_segment.get(segment["id"], ())
        candidates.extend(
            resolve_target_segment(segment, occupied, phase, uuid_factory)
            if occupied else [dict(segment)]
        )
    return validate_final_segments(parent["startTime"], parent["endTime"], candidates)


def same_snapshot(snapshot, blocker):
    """La autorización caduca al cambiar cualquier campo de su segment."""
    try:
        return (
            UUID(snapshot["occurrenceId"]) == blocker["occurrenceId"]
            and UUID(snapshot["segmentId"]) == blocker["segmentId"]
            and time.fromisoformat(snapshot["startTime"]) == blocker["startTime"]
            and time.fromisoformat(snapshot["endTime"]) == blocker["endTime"]
            and snapshot["status"] == blocker["status"]
        )
    except (KeyError, ValueError, TypeError):
        return False
