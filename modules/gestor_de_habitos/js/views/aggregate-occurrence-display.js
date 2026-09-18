import { statusDefinitions } from "../domain/occurrence-status.js";
import { getDateTemporalZone, TEMPORAL_ZONES } from "../domain/temporal-integrity.js";

const STATUS_PLURAL_LABELS = Object.freeze({
    pending: "pendientes",
    in_progress: "en progreso",
    completed: "completadas",
    not_completed: "no realizadas",
    not_finished: "no terminadas",
    cancelled: "canceladas",
});

function uniformStatusDisplay(status, count) {
    const definition = statusDefinitions[status];
    return {
        count,
        type: "uniform",
        status,
        temporalContext: null,
        symbol: definition.symbol,
        modifier: definition.modifier ?? null,
        ariaLabel: `${count} occurrences ${STATUS_PLURAL_LABELS[status]}`,
        interactive: false,
    };
}

function temporalDisplay(count, type, temporalContext, symbol, ariaLabel, modifier = null) {
    return {
        count,
        type,
        status: null,
        temporalContext,
        symbol,
        modifier,
        ariaLabel,
        interactive: false,
    };
}

export function deriveAggregateOccurrenceDisplay(occurrences, date, currentDate) {
    if (!Array.isArray(occurrences)) {
        throw new TypeError("Las occurrences agregadas deben proporcionarse como una lista.");
    }
    if (occurrences.length < 2) return null;

    const count = occurrences.length;
    const statuses = new Set(occurrences.map(({ status }) => status));
    const uniformStatus = statuses.size === 1 ? occurrences[0].status : null;
    const temporalZone = getDateTemporalZone(date, currentDate);
    const isCurrentDay = date === currentDate;
    const validUniformStatus = uniformStatus !== null && statusDefinitions[uniformStatus];

    // Frozen pending/in_progress indicates unreconciled persisted input. The renderer
    // reports it safely without mutating domain state or pretending it is historical truth.
    if (
        temporalZone === TEMPORAL_ZONES.FROZEN
        && uniformStatus !== null
        && (!validUniformStatus || ["pending", "in_progress"].includes(uniformStatus))
    ) {
        return temporalDisplay(
            count,
            "frozen-inconsistent",
            "frozen",
            "!",
            `${count} occurrences con estado inconsistente; historial congelado`,
        );
    }

    if (validUniformStatus) {
        if (uniformStatus === "pending" && isCurrentDay) {
            return temporalDisplay(
                count,
                "today-pending",
                "current-day",
                statusDefinitions.in_progress.symbol,
                `${count} occurrences programadas para hoy`,
            );
        }
        return uniformStatusDisplay(uniformStatus, count);
    }

    if (isCurrentDay) {
        return temporalDisplay(
            count,
            "today-mixed",
            "current-day",
            statusDefinitions.in_progress.symbol,
            `${count} occurrences para hoy con estados diferentes`,
        );
    }
    if (temporalZone === TEMPORAL_ZONES.FUTURE) {
        return temporalDisplay(
            count,
            "future-mixed",
            "future",
            "◐",
            `${count} occurrences con estados diferentes`,
        );
    }
    if (temporalZone === TEMPORAL_ZONES.FROZEN) {
        return temporalDisplay(
            count,
            "frozen-mixed",
            "frozen",
            "!",
            `${count} occurrences con estados diferentes; historial congelado`,
        );
    }
    return temporalDisplay(
        count,
        "editable-past-mixed",
        "editable-past",
        statusDefinitions.cancelled.symbol,
        `${count} occurrences con estados diferentes; fecha todavía editable`,
        "!",
    );
}
