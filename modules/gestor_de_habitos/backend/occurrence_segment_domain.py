"""Reglas puras del agregado de estado de OccurrenceSegment."""

from datetime import date, timedelta


FUTURE = "future"
CURRENT_DAY = "current_day"
PREVIOUS_EDITABLE_DAY = "previous_editable_day"
FROZEN_HISTORY = "frozen_history"

TEMPORAL_PHASES = frozenset(
    {FUTURE, CURRENT_DAY, PREVIOUS_EDITABLE_DAY, FROZEN_HISTORY}
)
SEGMENT_STATUSES = frozenset(
    {
        "pending",
        "in_progress",
        "completed",
        "not_completed",
        "not_finished",
        "cancelled",
    }
)


class OccurrenceSegmentDomainError(ValueError):
    """El conjunto de segmentos no representa un agregado válido."""


def temporal_phase_for_date(
    occurrence_date,
    reference_date,
    history_edit_window_days,
):
    """Clasifica una fecha local sin consultar reloj, base de datos o Flask."""
    if not isinstance(occurrence_date, date) or not isinstance(reference_date, date):
        raise TypeError("occurrence_date y reference_date deben ser date.")
    if (
        not isinstance(history_edit_window_days, int)
        or isinstance(history_edit_window_days, bool)
        or history_edit_window_days < 0
    ):
        raise ValueError("history_edit_window_days debe ser un entero no negativo.")
    if occurrence_date > reference_date:
        return FUTURE
    if occurrence_date == reference_date:
        return CURRENT_DAY
    if occurrence_date >= reference_date - timedelta(days=history_edit_window_days):
        return PREVIOUS_EDITABLE_DAY
    return FROZEN_HISTORY


def _validated_statuses(segments):
    if not isinstance(segments, (list, tuple)) or not segments:
        raise OccurrenceSegmentDomainError(
            "Una occurrence requiere al menos un segmento."
        )

    statuses = []
    for segment in segments:
        if not isinstance(segment, dict):
            raise OccurrenceSegmentDomainError("Cada segmento debe ser un objeto.")
        status = segment.get("status")
        if status not in SEGMENT_STATUSES:
            raise OccurrenceSegmentDomainError(
                "El segmento contiene un status no reconocido."
            )
        statuses.append(status)
    return tuple(statuses)


def derive_occurrence_status(segments, temporal_phase):
    """Deriva el status del parent sin mutar ni reconciliar sus segmentos."""
    if temporal_phase not in TEMPORAL_PHASES:
        raise OccurrenceSegmentDomainError("La fase temporal no es válida.")

    statuses = _validated_statuses(segments)
    unique_statuses = set(statuses)
    if len(unique_statuses) == 1:
        return statuses[0]

    if temporal_phase == FUTURE:
        if not unique_statuses.issubset({"pending", "cancelled"}):
            raise OccurrenceSegmentDomainError(
                "Una occurrence futura mixta contiene estados realizados."
            )
        return "pending"

    if temporal_phase == CURRENT_DAY:
        if unique_statuses & {"completed", "in_progress", "not_finished"}:
            return "in_progress"
        if "pending" in unique_statuses:
            return "pending"
        if "not_completed" in unique_statuses:
            return "not_completed"
        return "cancelled"

    if unique_statuses & {"pending", "in_progress"}:
        raise OccurrenceSegmentDomainError(
            "Una occurrence histórica mixta requiere reconciliación previa."
        )
    if unique_statuses & {"completed", "not_finished"}:
        return "not_finished"
    if "not_completed" in unique_statuses:
        return "not_completed"
    return "cancelled"
