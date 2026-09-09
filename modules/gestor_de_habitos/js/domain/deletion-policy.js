import { getDateTemporalZone, TEMPORAL_ZONES } from "./temporal-integrity.js";

export const DELETION_REASONS = Object.freeze({
    ALLOWED: "allowed",
    AMBIGUOUS: "ambiguous",
    FROZEN: "frozen",
    MISSING_OCCURRENCE: "missing_occurrence",
    MISSING_GENERATION_CONFIG: "missing_generation_config",
    PROTECTED_STATUS: "protected_status",
    ALREADY_STOPPED: "already_stopped",
});

export function getIndividualDeletionPolicy({
    occurrences,
    referenceDate,
    historyEditWindowDays,
    hasGenerationConfig,
}) {
    if (occurrences.length === 0) {
        return { allowed: false, reason: DELETION_REASONS.MISSING_OCCURRENCE, occurrence: null };
    }
    if (occurrences.length > 1) {
        return { allowed: false, reason: DELETION_REASONS.AMBIGUOUS, occurrence: null };
    }
    const occurrence = occurrences[0];
    const zone = getDateTemporalZone(occurrence.date, referenceDate, historyEditWindowDays);
    if (zone === TEMPORAL_ZONES.FROZEN) {
        return { allowed: false, reason: DELETION_REASONS.FROZEN, occurrence };
    }
    if (!hasGenerationConfig) {
        return { allowed: false, reason: DELETION_REASONS.MISSING_GENERATION_CONFIG, occurrence };
    }
    const allowedStatuses = zone === TEMPORAL_ZONES.FUTURE
        ? ["pending", "cancelled"]
        : ["pending"];
    return allowedStatuses.includes(occurrence.status)
        ? { allowed: true, reason: DELETION_REASONS.ALLOWED, occurrence }
        : { allowed: false, reason: DELETION_REASONS.PROTECTED_STATUS, occurrence };
}

export function getStopPlanningPolicy({
    generationConfig,
    selectedDate,
    referenceDate,
    historyEditWindowDays,
}) {
    const zone = getDateTemporalZone(selectedDate, referenceDate, historyEditWindowDays);
    if (zone === TEMPORAL_ZONES.FROZEN) {
        return { allowed: false, reason: DELETION_REASONS.FROZEN };
    }
    if (generationConfig === null) {
        return { allowed: false, reason: DELETION_REASONS.MISSING_GENERATION_CONFIG };
    }
    if (generationConfig.stoppedFromDate && generationConfig.stoppedFromDate <= selectedDate) {
        return {
            allowed: false,
            reason: DELETION_REASONS.ALREADY_STOPPED,
            stoppedFromDate: generationConfig.stoppedFromDate,
        };
    }
    return { allowed: true, reason: DELETION_REASONS.ALLOWED };
}

export function getEarlierStoppedFromDate(existingStoppedFromDate, selectedDate) {
    return existingStoppedFromDate && existingStoppedFromDate < selectedDate
        ? existingStoppedFromDate
        : selectedDate;
}

export function shouldRemoveOccurrenceWhenStopping(occurrence, selectedDate, referenceDate) {
    if (occurrence.date < selectedDate) return false;
    if (occurrence.status === "pending") return true;
    return occurrence.status === "cancelled" && occurrence.date > referenceDate;
}
