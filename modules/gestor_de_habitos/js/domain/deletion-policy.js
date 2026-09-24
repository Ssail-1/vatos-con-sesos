import { getDateTemporalZone, TEMPORAL_ZONES } from "./temporal-integrity.js";
import { addDays } from "../utils/date-time.js";

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

export function getPersistentPlanningActions({ occurrence, generationConfig, referenceDate }) {
    const eligible = Boolean(occurrence && generationConfig && occurrence.date >= referenceDate);
    const recurringMode = eligible && ["weekly", "interval_days"].includes(generationConfig.mode);
    const firstStoppedDate = occurrence ? addDays(occurrence.date, 1) : null;
    const withinScheduleEnd = recurringMode && (
        generationConfig.indefinite !== false
        || !generationConfig.endDate
        || generationConfig.endDate >= firstStoppedDate
    );
    const globallyActiveAfterSelection = recurringMode && (
        !generationConfig.stoppedFromDate
        || generationConfig.stoppedFromDate > firstStoppedDate
    );
    const slots = Array.isArray(generationConfig?.slots) ? generationConfig.slots : null;
    const canGenerateAfter = (slot) => (
        !slot?.lastGenerationDate || slot.lastGenerationDate > occurrence.date
    );
    const recurring = Boolean(
        withinScheduleEnd
        && globallyActiveAfterSelection
        && (!slots || slots.some(canGenerateAfter))
    );
    const sourceSlot = slots?.find(({ id }) => id === occurrence?.sourceGenerationSlotId);
    return {
        slot: recurring
            && Boolean(occurrence.sourceGenerationSlotId)
            && (!sourceSlot || canGenerateAfter(sourceSlot)),
        recurring,
        future: eligible,
    };
}
