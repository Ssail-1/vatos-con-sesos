"""Validación pura del estado temporal final de una Occurrence segmentada."""

from datetime import time
from uuid import UUID

from occurrence_segment_domain import SEGMENT_STATUSES
from scheduling_policy import time_ranges_overlap


class OccurrenceStructureDomainError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _minutes(value):
    if not isinstance(value, time) or value.tzinfo is not None:
        raise OccurrenceStructureDomainError(
            "invalid_payload", "El horario debe ser TIME local."
        )
    if value.second or value.microsecond:
        raise OccurrenceStructureDomainError(
            "invalid_payload", "El horario debe tener precisión HH:MM."
        )
    return value.hour * 60 + value.minute


def _time_at(minutes):
    if not 0 <= minutes < 24 * 60:
        raise OccurrenceStructureDomainError(
            "occurrence_time_wrap", "La traslación no puede cruzar medianoche."
        )
    return time(minutes // 60, minutes % 60)


def validate_final_segments(start_time, end_time, segments):
    """Devuelve una copia ordenada; nunca modifica el draft del caller."""
    if not isinstance(segments, (list, tuple)) or not segments:
        raise OccurrenceStructureDomainError(
            "occurrence_requires_segment",
            "Una occurrence requiere al menos un segment.",
        )
    parent_start = _minutes(start_time)
    parent_end = _minutes(end_time)
    if parent_start >= parent_end:
        raise OccurrenceStructureDomainError(
            "invalid_payload", "El rango general debe tener duración positiva."
        )
    candidates = []
    ids = set()
    for segment in segments:
        if not isinstance(segment, dict):
            raise OccurrenceStructureDomainError(
                "invalid_payload", "Cada segment debe ser un objeto."
            )
        segment_id = segment.get("id")
        if not isinstance(segment_id, UUID):
            raise OccurrenceStructureDomainError(
                "invalid_payload", "Cada segment final requiere un UUID interno."
            )
        if segment_id in ids:
            raise OccurrenceStructureDomainError(
                "duplicate_segment_id", "Un segment aparece más de una vez."
            )
        ids.add(segment_id)
        start = _minutes(segment.get("startTime"))
        end = _minutes(segment.get("endTime"))
        if start >= end:
            raise OccurrenceStructureDomainError(
                "segment_time_invalid", "El segment requiere duración positiva."
            )
        if start < parent_start or end > parent_end:
            raise OccurrenceStructureDomainError(
                "segment_outside_occurrence",
                "El segment queda fuera del rango general.",
            )
        status = segment.get("status")
        if not isinstance(status, str) or status not in SEGMENT_STATUSES:
            raise OccurrenceStructureDomainError(
                "invalid_status", "El status del segment no es canónico."
            )
        candidates.append(dict(segment))
    candidates.sort(
        key=lambda segment: (
            segment["startTime"],
            segment["endTime"],
            str(segment["id"]),
        )
    )
    for previous, current in zip(candidates, candidates[1:]):
        if time_ranges_overlap(
            previous["startTime"],
            previous["endTime"],
            current["startTime"],
            current["endTime"],
        ):
            raise OccurrenceStructureDomainError(
                "segment_sibling_overlap",
                "Los segments hermanos no pueden superponerse.",
            )
    return candidates


def translate_segments(
    old_start_time,
    old_end_time,
    new_start_time,
    new_end_time,
    segments,
):
    """Traslada todos los children por un único delta, conservando su identidad."""
    old_start = _minutes(old_start_time)
    old_end = _minutes(old_end_time)
    new_start = _minutes(new_start_time)
    new_end = _minutes(new_end_time)
    if old_start >= old_end or new_start >= new_end:
        raise OccurrenceStructureDomainError(
            "invalid_payload", "El rango general debe tener duración positiva."
        )
    if new_end - new_start != old_end - old_start:
        raise OccurrenceStructureDomainError(
            "occurrence_translate_duration_mismatch",
            "Translate no puede cambiar la duración general.",
        )
    delta = new_start - old_start
    translated = [
        {
            **segment,
            "startTime": _time_at(_minutes(segment["startTime"]) + delta),
            "endTime": _time_at(_minutes(segment["endTime"]) + delta),
        }
        for segment in segments
    ]
    return validate_final_segments(new_start_time, new_end_time, translated)
