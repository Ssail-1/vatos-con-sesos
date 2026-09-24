"""Reglas puras de status y agregado de OccurrenceSegment."""

from datetime import date, datetime, timedelta


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
ALLOWED_STATUSES_BY_PHASE = {
    FUTURE: frozenset({"pending", "cancelled"}),
    CURRENT_DAY: SEGMENT_STATUSES,
    PREVIOUS_EDITABLE_DAY: frozenset(
        {"completed", "not_completed", "not_finished", "cancelled"}
    ),
}


class OccurrenceSegmentDomainError(ValueError):
    """El conjunto de segmentos no representa un agregado válido."""


class OccurrenceSegmentStatusError(OccurrenceSegmentDomainError):
    """Una mutación de status contradice la fase o el tiempo actual."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


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


def validate_segment_status_for_phase(
    status,
    temporal_phase,
    segment_end_datetime,
    current_datetime,
):
    """Valida una corrección de status sin consultar reloj ni persistencia."""
    if status not in SEGMENT_STATUSES:
        raise OccurrenceSegmentStatusError(
            "invalid_status", "El status del segmento no es válido."
        )
    if temporal_phase not in TEMPORAL_PHASES:
        raise OccurrenceSegmentStatusError(
            "invalid_temporal_phase", "La fase temporal no es válida."
        )
    if not isinstance(segment_end_datetime, datetime) or not isinstance(
        current_datetime, datetime
    ):
        raise TypeError("Los límites temporales deben ser datetime.")
    if segment_end_datetime.tzinfo != current_datetime.tzinfo:
        raise TypeError("Los valores temporales deben compartir timezone.")
    if temporal_phase == FROZEN_HISTORY:
        raise OccurrenceSegmentStatusError(
            "history_frozen", "El historial congelado es de solo lectura."
        )
    if status not in ALLOWED_STATUSES_BY_PHASE[temporal_phase]:
        raise OccurrenceSegmentStatusError(
            "segment_status_not_allowed",
            "El status no está permitido en la fase temporal actual.",
        )
    if status == "completed" and segment_end_datetime > current_datetime:
        raise OccurrenceSegmentStatusError(
            "segment_not_ended",
            "El segmento no puede completarse antes de su hora final.",
        )


def reconcile_segment_status(status):
    """Normaliza un status histórico; la función es pura e idempotente."""
    if status not in SEGMENT_STATUSES:
        raise OccurrenceSegmentDomainError(
            "El segmento contiene un status no reconocido."
        )
    return {
        "pending": "not_completed",
        "in_progress": "not_finished",
    }.get(status, status)
