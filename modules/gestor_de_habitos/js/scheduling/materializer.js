import {
    addDays,
    getIsoWeekday,
    isDateInRange,
    isValidDateKey,
    isValidTimeRange,
} from "../utils/date-time.js";

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

export function validateGenerationConfig(config) {
    if (config === null) return;
    if (!config || typeof config !== "object") {
        throw new MaterializationError("La configuración de generación es obligatoria.");
    }

    if (config.mode === "weekly") {
        assertDateRange(config.startDate, config.endDate, config.indefinite);
        if (!Array.isArray(config.weekdays) || config.weekdays.length === 0) {
            throw new MaterializationError("Weekly requiere al menos un día.");
        }
        const normalizedWeekdays = [...new Set(config.weekdays)].sort((a, b) => a - b);
        if (
            normalizedWeekdays.length !== config.weekdays.length ||
            normalizedWeekdays.some((weekday) => !Number.isInteger(weekday) || weekday < 1 || weekday > 7)
        ) {
            throw new MaterializationError("Los weekdays deben ser valores ISO únicos entre 1 y 7.");
        }
        assertTimeRange(config.defaultStartTime, config.defaultEndTime);
        const overrides = config.weekdayTimeOverrides;
        if (!overrides || typeof overrides !== "object" || Array.isArray(overrides)) {
            throw new MaterializationError("weekdayTimeOverrides debe ser un objeto.");
        }
        Object.entries(overrides).forEach(([weekdayKey, timeRange]) => {
            const weekday = Number(weekdayKey);
            if (!normalizedWeekdays.includes(weekday)) {
                throw new MaterializationError("Un override solo puede pertenecer a un weekday activo.");
            }
            assertTimeRange(timeRange?.startTime, timeRange?.endTime);
        });
        return;
    }

    if (config.mode === "interval_days") {
        assertDateRange(config.startDate, config.endDate, config.indefinite);
        if (!Number.isInteger(config.intervalDays) || config.intervalDays < 1) {
            throw new MaterializationError("intervalDays debe ser un entero mayor o igual a 1.");
        }
        assertTimeRange(config.defaultStartTime, config.defaultEndTime);
        return;
    }

    if (config.mode === "manual_dates") {
        if (!Array.isArray(config.entries) || config.entries.length === 0) {
            throw new MaterializationError("manual_dates requiere al menos una entrada.");
        }
        config.entries.forEach((entry) => {
            if (!isValidDateKey(entry?.date)) throw new MaterializationError("Una fecha manual no es válida.");
            assertTimeRange(entry.startTime, entry.endTime);
        });
        return;
    }

    if (config.mode === "single_date") {
        if (!isValidDateKey(config.date)) throw new MaterializationError("La fecha única no es válida.");
        assertTimeRange(config.startTime, config.endTime);
        return;
    }

    throw new MaterializationError("El modo de generación no es válido.");
}

function makeDraft(planItemId, date, startTime, endTime) {
    return { planItemId, date, startTime, endTime, status: "pending" };
}

function materializeWeekly(planItem, rangeStart, rangeEnd) {
    const config = planItem.generationConfig;
    const effectiveStart = config.startDate > rangeStart ? config.startDate : rangeStart;
    const effectiveEnd = !config.indefinite && config.endDate < rangeEnd ? config.endDate : rangeEnd;
    if (effectiveStart > effectiveEnd) return [];
    const drafts = [];
    for (let date = effectiveStart; date <= effectiveEnd; date = addDays(date, 1)) {
        const weekday = getIsoWeekday(date);
        if (!config.weekdays.includes(weekday)) continue;
        const override = config.weekdayTimeOverrides[String(weekday)];
        drafts.push(
            makeDraft(
                planItem.id,
                date,
                override?.startTime ?? config.defaultStartTime,
                override?.endTime ?? config.defaultEndTime,
            ),
        );
    }
    return drafts;
}

function materializeIntervalDays(planItem, rangeStart, rangeEnd) {
    const config = planItem.generationConfig;
    const effectiveEnd = !config.indefinite && config.endDate < rangeEnd ? config.endDate : rangeEnd;
    const drafts = [];
    for (let date = config.startDate; date <= effectiveEnd; date = addDays(date, config.intervalDays)) {
        if (date >= rangeStart) {
            drafts.push(makeDraft(planItem.id, date, config.defaultStartTime, config.defaultEndTime));
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
    if (config.mode === "weekly") return materializeWeekly(planItem, rangeStart, rangeEnd);
    if (config.mode === "interval_days") return materializeIntervalDays(planItem, rangeStart, rangeEnd);
    if (config.mode === "manual_dates") {
        return config.entries
            .filter((entry) => isDateInRange(entry.date, rangeStart, rangeEnd))
            .map((entry) => makeDraft(planItem.id, entry.date, entry.startTime, entry.endTime));
    }
    if (config.mode === "single_date" && isDateInRange(config.date, rangeStart, rangeEnd)) {
        return [makeDraft(planItem.id, config.date, config.startTime, config.endTime)];
    }
    return [];
}

export function getLatestExplicitDate(planItems) {
    const dates = planItems.flatMap((planItem) => {
        const config = planItem.generationConfig;
        if (config?.mode === "single_date") return [config.date];
        if (config?.mode === "manual_dates") return config.entries.map((entry) => entry.date);
        return [];
    });
    return dates.sort().at(-1) ?? null;
}
