import {
    addDays,
    getIsoWeekday,
    isDateInRange,
    isValidDateKey,
    isValidTimeRange,
    timeRangesOverlap,
} from "../utils/date-time.js";
import { isGenerationSlotId } from "../domain/generation-slots.js";

export class MaterializationError extends Error {
    constructor(message) {
        super(message);
        this.name = "MaterializationError";
    }
}

function assertDateRange(startDate, endDate, indefinite) {
    if (!isValidDateKey(startDate)) throw new MaterializationError("La fecha inicial no es válida.");
    if (typeof indefinite !== "boolean") {
        throw new MaterializationError("indefinite debe ser un booleano.");
    }
    if (indefinite === true && endDate !== null) {
        throw new MaterializationError("Una repetición indefinida no puede tener fecha final.");
    }
    if (indefinite === false && (!isValidDateKey(endDate) || endDate < startDate)) {
        throw new MaterializationError("La fecha final no es válida.");
    }
}

function assertTimeRange(startTime, endTime) {
    if (!isValidTimeRange(startTime, endTime)) {
        throw new MaterializationError("La hora final debe ser posterior a la inicial.");
    }
}

function assertGenerationControls(config) {
    if (config.excludedDates !== undefined) {
        if (
            !Array.isArray(config.excludedDates) ||
            config.excludedDates.some((date) => !isValidDateKey(date)) ||
            new Set(config.excludedDates).size !== config.excludedDates.length
        ) {
            throw new MaterializationError("excludedDates debe contener fechas válidas y únicas.");
        }
    }
    if (config.stoppedFromDate !== undefined && !isValidDateKey(config.stoppedFromDate)) {
        throw new MaterializationError("stoppedFromDate debe ser una fecha válida.");
    }
}

function assertSlotExcludedDates(slot) {
    if (slot.excludedDates === undefined) return;
    if (
        !Array.isArray(slot.excludedDates) ||
        slot.excludedDates.some((date) => !isValidDateKey(date)) ||
        new Set(slot.excludedDates).size !== slot.excludedDates.length
    ) {
        throw new MaterializationError(
            "GenerationSlot.excludedDates debe contener fechas válidas y únicas.",
        );
    }
}

function assertSlotCollection(slots, groupValue, groupLabel) {
    if (!Array.isArray(slots) || slots.length === 0) {
        throw new MaterializationError("La configuración requiere al menos un GenerationSlot.");
    }
    const ids = new Set();
    const groupedSlots = new Map();
    slots.forEach((slot) => {
        if (!slot || !isGenerationSlotId(slot.id) || ids.has(slot.id)) {
            throw new MaterializationError("Cada GenerationSlot requiere un UUID v4 único.");
        }
        ids.add(slot.id);
        assertTimeRange(slot.startTime, slot.endTime);
        assertSlotExcludedDates(slot);
        const key = groupValue(slot);
        const group = groupedSlots.get(key) ?? [];
        const overlaps = group.some((candidate) =>
            timeRangesOverlap(slot.startTime, slot.endTime, candidate.startTime, candidate.endTime)
        );
        if (overlaps) {
            throw new MaterializationError(`Los horarios de ${groupLabel} no pueden solaparse.`);
        }
        group.push(slot);
        groupedSlots.set(key, group);
    });
}

function assertLegacyFieldsAbsent(config, fieldNames) {
    if (fieldNames.some((fieldName) => Object.hasOwn(config, fieldName))) {
        throw new MaterializationError("La configuración debe utilizar GenerationSlots canónicos.");
    }
}

export function validateGenerationConfig(config) {
    if (config === null) return;
    if (!config || typeof config !== "object") {
        throw new MaterializationError("La configuración de generación es obligatoria.");
    }
    assertGenerationControls(config);

    if (config.mode === "weekly") {
        assertDateRange(config.startDate, config.endDate, config.indefinite);
        assertLegacyFieldsAbsent(config, ["weekdays", "defaultStartTime", "defaultEndTime", "weekdayTimeOverrides"]);
        assertSlotCollection(config.slots, (slot) => slot.isoWeekday, "un mismo weekday");
        config.slots.forEach((slot) => {
            if (!Number.isInteger(slot.isoWeekday) || slot.isoWeekday < 1 || slot.isoWeekday > 7) {
                throw new MaterializationError("Cada slot weekly requiere un isoWeekday entre 1 y 7.");
            }
        });
        return;
    }

    if (config.mode === "interval_days") {
        assertDateRange(config.startDate, config.endDate, config.indefinite);
        if (!Number.isInteger(config.intervalDays) || config.intervalDays < 1) {
            throw new MaterializationError("intervalDays debe ser un entero mayor o igual a 1.");
        }
        assertLegacyFieldsAbsent(config, ["defaultStartTime", "defaultEndTime"]);
        assertSlotCollection(config.slots, () => "interval", "interval_days");
        return;
    }

    if (config.mode === "manual_dates") {
        if (!Array.isArray(config.entries) || config.entries.length === 0) {
            throw new MaterializationError("manual_dates requiere al menos una entrada.");
        }
        assertSlotCollection(config.entries, (entry) => entry.date, "una misma fecha");
        config.entries.forEach((entry) => {
            if (!isValidDateKey(entry?.date)) throw new MaterializationError("Una fecha manual no es válida.");
            if (entry.excludedDates !== undefined) {
                throw new MaterializationError("manual_dates no utiliza exclusiones por slot.");
            }
        });
        return;
    }

    throw new MaterializationError("El modo de generación no es válido.");
}

function makeDraft(planItemId, sourceGenerationSlotId, date, startTime, endTime) {
    return { planItemId, sourceGenerationSlotId, date, startTime, endTime, status: "pending" };
}

function materializeWeekly(planItem, rangeStart, rangeEnd) {
    const config = planItem.generationConfig;
    const effectiveStart = config.startDate > rangeStart ? config.startDate : rangeStart;
    const effectiveEnd = !config.indefinite && config.endDate < rangeEnd ? config.endDate : rangeEnd;
    if (effectiveStart > effectiveEnd) return [];
    const drafts = [];
    for (let date = effectiveStart; date <= effectiveEnd; date = addDays(date, 1)) {
        const weekday = getIsoWeekday(date);
        config.slots
            .filter((slot) => slot.isoWeekday === weekday)
            .forEach((slot) => drafts.push(
                makeDraft(planItem.id, slot.id, date, slot.startTime, slot.endTime),
            ));
    }
    return drafts;
}

function materializeIntervalDays(planItem, rangeStart, rangeEnd) {
    const config = planItem.generationConfig;
    const effectiveEnd = !config.indefinite && config.endDate < rangeEnd ? config.endDate : rangeEnd;
    const drafts = [];
    for (let date = config.startDate; date <= effectiveEnd; date = addDays(date, config.intervalDays)) {
        if (date >= rangeStart) {
            config.slots.forEach((slot) => drafts.push(
                makeDraft(planItem.id, slot.id, date, slot.startTime, slot.endTime),
            ));
        }
    }
    return drafts;
}

export function materializeOccurrenceDrafts(planItem, rangeStart, rangeEnd) {
    if (!isValidDateKey(rangeStart) || !isValidDateKey(rangeEnd) || rangeStart > rangeEnd) {
        throw new MaterializationError("El rango de materialización no es válido.");
    }
    validateGenerationConfig(planItem.generationConfig);
    const config = planItem.generationConfig;
    if (config === null) return [];
    let drafts = [];
    if (config.mode === "weekly") drafts = materializeWeekly(planItem, rangeStart, rangeEnd);
    else if (config.mode === "interval_days") drafts = materializeIntervalDays(planItem, rangeStart, rangeEnd);
    if (config.mode === "manual_dates") {
        drafts = config.entries
            .filter((entry) => isDateInRange(entry.date, rangeStart, rangeEnd))
            .map((entry) => makeDraft(planItem.id, entry.id, entry.date, entry.startTime, entry.endTime));
    }
    const excludedDates = new Set(config.excludedDates ?? []);
    const slotExcludedDates = new Map(
        (config.slots ?? []).map((slot) => [slot.id, new Set(slot.excludedDates ?? [])]),
    );
    return drafts.filter(({ date, sourceGenerationSlotId }) =>
        !excludedDates.has(date) &&
        !slotExcludedDates.get(sourceGenerationSlotId)?.has(date) &&
        (!config.stoppedFromDate || date < config.stoppedFromDate)
    );
}

export function getLatestExplicitDate(planItems) {
    const dates = planItems.flatMap((planItem) => {
        const config = planItem.generationConfig;
        if (config?.mode === "manual_dates") return config.entries.map((entry) => entry.date);
        return [];
    });
    return dates.sort().at(-1) ?? null;
}
