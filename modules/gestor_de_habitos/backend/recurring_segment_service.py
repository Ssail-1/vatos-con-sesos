"""Grafo candidato y conflicto batch compartidos por Apply Week/Future."""

from uuid import uuid4

from occurrence_segment_service import (
    OccurrenceSegmentConsistencyError,
    _serialize_blockers,
    _validated_occurrence,
    _validated_segments,
)
from occurrence_segment_domain import (
    OccurrenceSegmentDomainError,
    PREVIOUS_EDITABLE_DAY,
    derive_occurrence_status,
    temporal_phase_for_date,
)
from occurrence_structure_domain import OccurrenceStructureDomainError, validate_final_segments
from recurring_segment_policy import (
    RecurringSegmentError,
    default_recurring_segment,
    transform_recurring_segments,
)
from repositories import occurrence_segment_repository, recurring_segment_repository
from scheduling_policy import BLOCKING_STATUSES, time_ranges_overlap
from scheduling_policy import HISTORY_EDIT_WINDOW_DAYS


class RecurringGraphError(RuntimeError):
    def __init__(self, code, message, *, occurrences=None, blockers=None):
        super().__init__(message)
        self.code = code
        self.occurrences = occurrences
        self.blockers = blockers


def load_segment_graphs(connection, rows, now):
    """Los parents ya están bloqueados; bloquear children en orden estable."""
    ids = sorted((row["id"] for row in rows), key=str)
    segment_rows = occurrence_segment_repository.lock_segments_for_occurrences(connection, ids)
    grouped = {identifier: [] for identifier in ids}
    for segment in segment_rows:
        if segment["occurrence_id"] not in grouped:
            raise OccurrenceSegmentConsistencyError("Un segment pertenece a otro batch.")
        grouped[segment["occurrence_id"]].append(segment)
    graphs = {}
    for row in rows:
        parent = _validated_occurrence(row)
        segments = _validated_segments(grouped[row["id"]], parent)
        try:
            graphs[row["id"]] = validate_final_segments(
                row["start_time"], row["end_time"], segments
            )
        except OccurrenceStructureDomainError as error:
            raise OccurrenceSegmentConsistencyError(str(error)) from None
        phase = temporal_phase_for_date(
            row["occurrence_date"], now.date(), HISTORY_EDIT_WINDOW_DAYS
        )
        try:
            aggregate = derive_occurrence_status(graphs[row["id"]], phase)
        except OccurrenceSegmentDomainError as error:
            if phase == PREVIOUS_EDITABLE_DAY and any(
                item["status"] in {"pending", "in_progress"}
                for item in graphs[row["id"]]
            ):
                raise RecurringGraphError(
                    "temporal_reconciliation_required",
                    "La aparición histórica requiere reconciliación previa.",
                ) from None
            raise OccurrenceSegmentConsistencyError(str(error)) from None
        if row["status"] != aggregate:
            raise OccurrenceSegmentConsistencyError(
                "El aggregate persistido no coincide con sus segments."
            )
    return graphs


def _resize_description(original, requested):
    return {
        "occurrenceId": str(original["id"]),
        "planItemId": str(original["plan_item_id"]),
        "date": original["occurrence_date"].isoformat(),
        "startTime": original["start_time"].strftime("%H:%M"),
        "endTime": original["end_time"].strftime("%H:%M"),
        "requestedStartTime": requested["start_time"].strftime("%H:%M"),
        "requestedEndTime": requested["end_time"].strftime("%H:%M"),
    }


def build_candidate_graphs(original_rows, final_rows, persisted_graphs, now, segment_uuid_factory=uuid4):
    originals = {row["id"]: row for row in original_rows}
    graphs = {}
    incompatible = []
    for row in final_rows:
        old = originals.get(row["id"])
        if old is None:
            try:
                segment, aggregate = default_recurring_segment(row, segment_uuid_factory(), now)
            except RecurringSegmentError as error:
                raise RecurringGraphError(error.code, str(error)) from None
            graphs[row["id"]] = [segment]
            row["status"] = aggregate
            continue
        previous = persisted_graphs[row["id"]]
        if (
            row["occurrence_date"], row["start_time"], row["end_time"]
        ) == (
            old["occurrence_date"], old["start_time"], old["end_time"]
        ):
            graphs[row["id"]] = previous
            continue
        try:
            segments, aggregate = transform_recurring_segments(old, previous, row, now)
        except RecurringSegmentError as error:
            if error.code == "segmented_recurring_resize_requires_resolution":
                incompatible.append(_resize_description(old, row))
                continue
            raise RecurringGraphError(error.code, str(error)) from None
        graphs[row["id"]] = segments
        row["status"] = aggregate
    if incompatible:
        incompatible.sort(key=lambda item: (item["date"], item["occurrenceId"]))
        raise RecurringGraphError(
            "segmented_recurring_resize_requires_resolution",
            "Una o más apariciones segmentadas requieren resolución estructural explícita.",
            occurrences=incompatible,
        )
    return graphs


def _candidate_segments(final_rows, graphs):
    result = []
    for row in final_rows:
        for segment in graphs[row["id"]]:
            if segment["status"] in BLOCKING_STATUSES:
                result.append({
                    "occurrence_id": row["id"],
                    "plan_item_id": row["plan_item_id"],
                    "occurrence_date": row["occurrence_date"],
                    "segment_id": segment["id"],
                    "start_time": segment["startTime"],
                    "end_time": segment["endTime"],
                    "status": segment["status"],
                })
    return result


def _conflicts(first, second):
    return first["occurrence_date"] == second["occurrence_date"] and time_ranges_overlap(
        first["start_time"], first["end_time"], second["start_time"], second["end_time"]
    )


def validate_batch_conflicts(connection, original_rows, final_rows, graphs):
    candidates = _candidate_segments(final_rows, graphs)
    blockers = {}
    for index, first in enumerate(candidates):
        for second in candidates[index + 1:]:
            if first["occurrence_id"] != second["occurrence_id"] and _conflicts(first, second):
                blockers[first["segment_id"]] = first
                blockers[second["segment_id"]] = second
    dates = sorted({item["occurrence_date"] for item in candidates})
    external = recurring_segment_repository.lock_external_blocking_segments(
        connection, sorted((row["id"] for row in original_rows), key=str), dates,
        BLOCKING_STATUSES,
    )
    for item in external:
        if any(_conflicts(item, candidate) for candidate in candidates):
            blockers[item["segment_id"]] = item
    if blockers:
        ordered = sorted(blockers.values(), key=lambda row: (
            row["occurrence_date"], row["start_time"], row["end_time"],
            str(row["occurrence_id"]), str(row["segment_id"]),
        ))
        raise RecurringGraphError(
            "recurring_schedule_conflict",
            "La planificación recurrente solapa segments ocupantes.",
            blockers=_serialize_blockers(ordered),
        )


def persist_segments_for_updates(connection, updates, graphs, persisted_graphs):
    for old, updated in updates:
        old_by_id = {segment["id"]: segment for segment in persisted_graphs[old["id"]]}
        for segment in graphs[updated["id"]]:
            previous = old_by_id[segment["id"]]
            if (segment["startTime"], segment["endTime"]) != (
                previous["startTime"], previous["endTime"]
            ) and occurrence_segment_repository.update_segment_times(
                connection, segment["id"], updated["id"],
                segment["startTime"], segment["endTime"],
            ) != 1:
                raise OccurrenceSegmentConsistencyError("No se actualizó un segment recurrente.")
        if occurrence_segment_repository.update_occurrence_status(
            connection, updated["id"], updated["status"]
        ) != 1:
            raise OccurrenceSegmentConsistencyError("No se actualizó el aggregate recurrente.")


def persist_segments_for_creates(connection, creates, graphs):
    for row in creates:
        for segment in graphs[row["id"]]:
            if occurrence_segment_repository.insert_segment(
                connection, segment, row["id"]
            ) != 1:
                raise OccurrenceSegmentConsistencyError("No se creó el segment recurrente.")


def serialize_occurrence(row, segments):
    """Respuesta de mutación; el GET posterior sigue siendo autoridad completa."""
    parent = _validated_occurrence(row)
    result = {
        "id": str(parent["id"]),
        "planItemId": str(parent["planItemId"]),
        "date": parent["date"].isoformat(),
        "startTime": parent["startTime"].strftime("%H:%M"),
        "endTime": parent["endTime"].strftime("%H:%M"),
        "status": parent["status"],
        "segments": [
            {
                "id": str(item["id"]),
                "startTime": item["startTime"].strftime("%H:%M"),
                "endTime": item["endTime"].strftime("%H:%M"),
                "status": item["status"],
            }
            for item in segments
        ],
    }
    if row["source_generation_slot_id"] is not None:
        result["sourceGenerationSlotId"] = str(row["source_generation_slot_id"])
    reason = row.get("conflict_reason")
    source = row.get("source_occurrence_id")
    if (reason is None) != (source is None):
        raise OccurrenceSegmentConsistencyError("El contexto de conflicto está incompleto.")
    if reason is not None:
        result["conflictContext"] = {"reason": reason, "sourceOccurrenceId": str(source)}
    if row.get("origin_reason") is not None:
        result["originReason"] = row["origin_reason"]
    if row.get("last_conflict_action") is not None:
        result["lastConflictAction"] = row["last_conflict_action"]
    return result
