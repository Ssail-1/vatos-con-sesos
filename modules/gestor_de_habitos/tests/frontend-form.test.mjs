import assert from "node:assert/strict";
import { normalizeWeekdayOverride, validateFormValues } from "../js/views/plan-item-form.js";
import { generationSlot } from "./helpers/generation-configs.mjs";

const weeklySlots = [1, 3, 5].map((isoWeekday) => generationSlot({
    isoWeekday,
    startTime: "08:00",
    endTime: "09:00",
}));
const intervalSlots = [generationSlot({ startTime: "08:00", endTime: "09:00" })];
const manualDateEntries = [
    generationSlot({ date: "2026-08-24", startTime: "08:00", endTime: "09:00" }),
    generationSlot({ date: "2026-08-28", startTime: "16:00", endTime: "17:30" }),
];
const explicitDateSlotId = generationSlot({}).id;

const base = {
    name: "Registro", kind: "activity", itemType: "periodic", date: "2026-08-24",
    startDate: "2026-08-24", endDate: "", indefinite: true, weeklySlots,
    intervalDays: "3", intervalSlots, manualDateEntries, explicitDateSlotId,
    startTime: "08:00", endTime: "09:00",
};

assert.deepEqual(validateFormValues({ ...base, scheduleMode: "weekly" }).generationConfig.slots, weeklySlots);
assert.equal(validateFormValues({ ...base, scheduleMode: "interval_days" }).generationConfig.intervalDays, 3);
assert.equal(validateFormValues({ ...base, scheduleMode: "manual_dates" }).generationConfig.entries.length, 2);
assert.deepEqual(
    validateFormValues({ ...base, scheduleMode: "explicit_date", itemType: "event" }).generationConfig,
    {
        mode: "manual_dates",
        entries: [{ id: explicitDateSlotId, date: "2026-08-24", startTime: "08:00", endTime: "09:00" }],
    },
);
assert.equal(validateFormValues({ ...base, scheduleMode: "weekly", weeklySlots: [] }).errors[0].field, "scheduleMode");
assert.deepEqual(normalizeWeekdayOverride("08:00", "09:00", "10:00", "11:00"), { startTime: "10:00", endTime: "11:00" });
assert.deepEqual(normalizeWeekdayOverride("08:00", "09:00", "10:30", "11:30"), { startTime: "10:30", endTime: "11:30" });
assert.equal(normalizeWeekdayOverride("08:00", "09:00", "08:00", "09:00"), null);

console.log("frontend-form.test.mjs: todas las pruebas pasaron");
