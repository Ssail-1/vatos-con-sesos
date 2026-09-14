import { createGenerationSlotId } from "../../js/domain/generation-slots.js";

export function generationSlot(fields) {
    return { id: createGenerationSlotId(), ...fields };
}

export function weeklyConfig({
    days = [1, 3, 5],
    startTime = "08:00",
    endTime = "09:00",
    perDayTimes = {},
    extraSlots = [],
    startDate = "2026-08-01",
    endDate = null,
    indefinite = true,
    ...controls
} = {}) {
    const slots = days.map((isoWeekday) => generationSlot({
        isoWeekday,
        startTime: perDayTimes[String(isoWeekday)]?.startTime ?? startTime,
        endTime: perDayTimes[String(isoWeekday)]?.endTime ?? endTime,
    }));
    return {
        mode: "weekly",
        startDate,
        endDate,
        indefinite,
        slots: [...slots, ...extraSlots.map((slot) => generationSlot(slot))],
        ...controls,
    };
}

export function intervalConfig({
    intervalDays = 2,
    times = [{ startTime: "08:00", endTime: "09:00" }],
    startDate = "2026-08-01",
    endDate = null,
    indefinite = true,
    ...controls
} = {}) {
    return {
        mode: "interval_days",
        startDate,
        endDate,
        indefinite,
        intervalDays,
        slots: times.map((time) => generationSlot(time)),
        ...controls,
    };
}

export function manualConfig(entries, controls = {}) {
    return {
        mode: "manual_dates",
        entries: entries.map((entry) => ({
            ...entry,
            id: entry.id ?? createGenerationSlotId(),
        })),
        ...controls,
    };
}

export function explicitDate(date, startTime = "08:00", endTime = "09:00", controls = {}) {
    return manualConfig([{ date, startTime, endTime }], controls);
}
