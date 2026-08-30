import { addDays, isValidDateKey } from "../utils/date-time.js";

export const HISTORY_EDIT_WINDOW_DAYS = 1;

export const TEMPORAL_ZONES = Object.freeze({
    EDITABLE: "editable",
    FROZEN: "frozen",
    FUTURE: "future",
});

function validateWindowDays(windowDays) {
    if (!Number.isInteger(windowDays) || windowDays < 0) {
        throw new RangeError("La ventana histórica debe expresarse en días calendario no negativos.");
    }
}

export function getHistoryCutoff(referenceDate, windowDays = HISTORY_EDIT_WINDOW_DAYS) {
    if (!isValidDateKey(referenceDate)) throw new TypeError("La fecha de referencia no es válida.");
    validateWindowDays(windowDays);
    return addDays(referenceDate, -windowDays);
}

export function getDateTemporalZone(date, referenceDate, windowDays = HISTORY_EDIT_WINDOW_DAYS) {
    if (!isValidDateKey(date)) throw new TypeError("La fecha de la occurrence no es válida.");
    if (!isValidDateKey(referenceDate)) throw new TypeError("La fecha de referencia no es válida.");
    if (date > referenceDate) return TEMPORAL_ZONES.FUTURE;
    return date < getHistoryCutoff(referenceDate, windowDays)
        ? TEMPORAL_ZONES.FROZEN
        : TEMPORAL_ZONES.EDITABLE;
}

export function reconcileFrozenStatus(status) {
    if (status === "pending") return "not_completed";
    if (status === "in_progress") return "not_finished";
    return status;
}

export function getOccurrenceTemporalPolicy(occurrence, referenceDate, windowDays = HISTORY_EDIT_WINDOW_DAYS) {
    const zone = getDateTemporalZone(occurrence.date, referenceDate, windowDays);
    return {
        zone,
        canEditSchedule: zone !== TEMPORAL_ZONES.FROZEN,
        canChangeStatus:
            zone === TEMPORAL_ZONES.EDITABLE ||
            zone === TEMPORAL_ZONES.FUTURE && ["pending", "cancelled"].includes(occurrence.status),
    };
}
