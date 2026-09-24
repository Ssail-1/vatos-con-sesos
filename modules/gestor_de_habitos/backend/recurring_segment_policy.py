"""Política pura compartida para cambios recurrentes sobre segments runtime."""

from datetime import datetime
from uuid import UUID

from occurrence_segment_domain import (
    FROZEN_HISTORY,
    PREVIOUS_EDITABLE_DAY,
    OccurrenceSegmentDomainError,
    OccurrenceSegmentStatusError,
    derive_occurrence_status,
    temporal_phase_for_date,
    validate_segment_status_for_phase,
)
from occurrence_structure_domain import (
    OccurrenceStructureDomainError,
    translate_segments,
    validate_final_segments,
)
from scheduling_policy import HISTORY_EDIT_WINDOW_DAYS


class RecurringSegmentError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def is_simple_occurrence(parent, segments):
    return (
        len(segments) == 1
        and segments[0]["startTime"] == parent["start_time"]
        and segments[0]["endTime"] == parent["end_time"]
    )


def transform_recurring_segments(parent, segments, candidate, now):
    """Devuelve (segments finales, aggregate); nunca muta el grafo recibido."""
    if not isinstance(now, datetime) or now.tzinfo is not None:
        raise TypeError("now debe ser un datetime local sin timezone.")
    old_date = parent["occurrence_date"]
    new_date = candidate["occurrence_date"]
    old_phase = temporal_phase_for_date(old_date, now.date(), HISTORY_EDIT_WINDOW_DAYS)
    new_phase = temporal_phase_for_date(new_date, now.date(), HISTORY_EDIT_WINDOW_DAYS)
    if old_phase == FROZEN_HISTORY or new_phase == FROZEN_HISTORY:
        raise RecurringSegmentError("history_frozen", "El historial congelado es de solo lectura.")
    if old_phase == PREVIOUS_EDITABLE_DAY and any(
        item["status"] in {"pending", "in_progress"} for item in segments
    ):
        raise RecurringSegmentError(
            "temporal_reconciliation_required",
            "La aparición histórica requiere reconciliación previa.",
        )
    start, end = candidate["start_time"], candidate["end_time"]
    try:
        if is_simple_occurrence(parent, segments):
            transformed = [
                {**segments[0], "startTime": start, "endTime": end}
            ]
            transformed = validate_final_segments(start, end, transformed)
        elif old_date != new_date:
            # El contrato v1 no define cómo trasladar custom history entre días.
            raise RecurringSegmentError(
                "segmented_recurring_date_move_requires_resolution",
                "Una aparición segmentada no puede cambiar de fecha automáticamente.",
            )
        elif end.hour * 60 + end.minute - start.hour * 60 - start.minute != (
            parent["end_time"].hour * 60 + parent["end_time"].minute
            - parent["start_time"].hour * 60 - parent["start_time"].minute
        ):
            raise RecurringSegmentError(
                "segmented_recurring_resize_requires_resolution",
                "Una aparición segmentada requiere resolver manualmente el cambio de duración.",
            )
        else:
            transformed = translate_segments(
                parent["start_time"], parent["end_time"], start, end, segments
            )
        for item in transformed:
            validate_segment_status_for_phase(
                item["status"], new_phase,
                datetime.combine(new_date, item["endTime"]), now,
            )
        aggregate = derive_occurrence_status(transformed, new_phase)
    except OccurrenceStructureDomainError as error:
        raise RecurringSegmentError(error.code, str(error)) from None
    except OccurrenceSegmentStatusError as error:
        raise RecurringSegmentError(error.code, str(error)) from None
    except OccurrenceSegmentDomainError as error:
        raise RecurringSegmentError("persisted_state_invalid", str(error)) from None
    return transformed, aggregate


def default_recurring_segment(occurrence, segment_id, now):
    if not isinstance(segment_id, UUID) or segment_id.version != 4:
        raise RecurringSegmentError("invalid_segment_id", "El segment requiere UUID v4.")
    candidate = {
        "id": segment_id,
        "startTime": occurrence["start_time"],
        "endTime": occurrence["end_time"],
        "status": occurrence["status"],
    }
    parent = {**occurrence}
    segments, aggregate = transform_recurring_segments(parent, [candidate], occurrence, now)
    return segments[0], aggregate
