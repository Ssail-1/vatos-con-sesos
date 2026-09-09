import assert from "node:assert/strict";
import { normalizeWeekdayOverride, validateFormValues } from "../js/views/plan-item-form.js";

const base = {
    name: "Registro", kind: "activity", itemType: "periodic", date: "2026-08-24",
    startDate: "2026-08-24", endDate: "", indefinite: true, weekdays: [1, 3, 5],
    weekdayTimeOverrides: {}, intervalDays: "3", manualDateEntries: [
        { date: "2026-08-24", startTime: "08:00", endTime: "09:00" },
        { date: "2026-08-28", startTime: "16:00", endTime: "17:30" },
    ],
    startTime: "08:00", endTime: "09:00", defaultStartTime: "08:00", defaultEndTime: "09:00",
};

assert.deepEqual(validateFormValues({ ...base, scheduleMode: "weekly" }).generationConfig.weekdays, [1, 3, 5]);
assert.equal(validateFormValues({ ...base, scheduleMode: "interval_days" }).generationConfig.intervalDays, 3);
assert.equal(validateFormValues({ ...base, scheduleMode: "manual_dates" }).generationConfig.entries.length, 2);
assert.equal(validateFormValues({ ...base, scheduleMode: "single_date", itemType: "event" }).generationConfig.mode, "single_date");
assert.equal(validateFormValues({ ...base, scheduleMode: "weekly", weekdays: [] }).errors[0].field, "scheduleMode");
assert.deepEqual(normalizeWeekdayOverride("08:00", "09:00", "10:00", "11:00"), { startTime: "10:00", endTime: "11:00" });
assert.deepEqual(normalizeWeekdayOverride("08:00", "09:00", "10:30", "11:30"), { startTime: "10:30", endTime: "11:30" });
assert.equal(normalizeWeekdayOverride("08:00", "09:00", "08:00", "09:00"), null);

console.log("frontend-form.test.mjs: todas las pruebas pasaron");
