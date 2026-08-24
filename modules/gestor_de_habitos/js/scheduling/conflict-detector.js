import { blocksSchedule } from "../domain/occurrence-status.js";
import { timeRangesOverlap } from "../utils/date-time.js";

export function findOccurrenceConflict(candidate, occurrences, ignoredOccurrenceId = null) {
    if (!blocksSchedule(candidate)) return null;
    return (
        occurrences.find(
            (occurrence) =>
                occurrence.id !== ignoredOccurrenceId &&
                occurrence.date === candidate.date &&
                blocksSchedule(occurrence) &&
                timeRangesOverlap(
                    candidate.startTime,
                    candidate.endTime,
                    occurrence.startTime,
                    occurrence.endTime,
                ),
        ) ?? null
    );
}

export function findConflictInDraftSet(drafts, existingOccurrences = []) {
    const acceptedDrafts = [];
    for (const draft of drafts) {
        const conflict = findOccurrenceConflict(draft, [...existingOccurrences, ...acceptedDrafts]);
        if (conflict) return { draft, conflict };
        acceptedDrafts.push(draft);
    }
    return null;
}
