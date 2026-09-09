import assert from "node:assert/strict";
import { createPlannerStore, PlannerStoreError } from "../js/state/planner-store.js";
import { buildPlannerRows } from "../js/views/planner-matrix.js";

const weekly = (overrides = {}) => ({
    mode: "weekly", startDate: "2026-08-01", endDate: null, indefinite: true,
    weekdays: [1, 3, 5], defaultStartTime: "08:00", defaultEndTime: "09:00",
    weekdayTimeOverrides: {}, ...overrides,
});
const item = (id, config = weekly()) => ({ id, name: id, kind: "activity", activityType: "periodic", generationConfig: config });
const expectError = (action, code) => assert.throws(action, (error) => error instanceof PlannerStoreError && error.code === code);

{
    const store = createPlannerStore([item("weekly")], [], "2026-08-24");
    const occurrence = store.getOccurrencesForDate("2026-08-24")[0];
    expectError(() => store.updatePlanItemAndOccurrence("weekly", { name: "weekly", kind: "activity", activityType: "periodic" }, occurrence.id, { date: "2026-08-26", startTime: "07:00", endTime: "08:00" }), "date_locked");
    const updated = store.updatePlanItemAndOccurrence("weekly", { name: "weekly", kind: "activity", activityType: "periodic" }, occurrence.id, { date: occurrence.date, startTime: "07:00", endTime: "08:00" });
    assert.equal(updated.occurrence.date, occurrence.date);
    assert.equal(updated.occurrence.id, occurrence.id);
    assert.equal(updated.occurrence.planItemId, occurrence.planItemId);
    assert.equal(updated.occurrence.status, occurrence.status);
}

{
    const store = createPlannerStore([item("weekly")], [], "2026-08-24");
    const originalConfig = store.getPlanItemById("weekly").generationConfig;
    const added = store.addOccurrenceForPlanItem("weekly", { date: "2026-08-27", startTime: "10:00", endTime: "11:00" });
    assert.equal(added.planItemId, "weekly");
    assert.equal(added.date, "2026-08-27");
    assert.equal(added.status, "pending");
    assert.deepEqual(store.getPlanItemById("weekly").generationConfig, originalConfig);
    store.addOccurrenceForPlanItem("weekly", { date: "2026-08-27", startTime: "12:00", endTime: "13:00" });
    assert.equal(
        store.getOccurrencesForDate("2026-08-27").filter(({ planItemId }) => planItemId === "weekly").length,
        2,
        "el store permite múltiples occurrences no solapadas del mismo PlanItem/fecha",
    );
}

{
    const store = createPlannerStore([
        item("weekly"),
        item("blocker", { mode: "single_date", date: "2026-08-27", startTime: "10:30", endTime: "11:30" }),
    ], [], "2026-08-24");
    const before = store.getOccurrences();
    expectError(() => store.addOccurrenceForPlanItem("weekly", { date: "2026-08-27", startTime: "10:00", endTime: "11:00" }), "time_conflict");
    assert.deepEqual(store.getOccurrences(), before);
}

{
    const store = createPlannerStore([item("weekly")], [], "2026-08-24");
    const originalConfig = store.getPlanItemById("weekly").generationConfig;
    const withThursday = weekly({ weekdays: [1, 3, 4, 5] });
    store.applyWeeklyToWeek("weekly", "2026-08-27", withThursday);
    store.applyWeeklyToWeek("weekly", "2026-08-27", withThursday);
    assert.equal(store.getOccurrencesForDate("2026-08-27").filter(({ planItemId }) => planItemId === "weekly").length, 1, "Apply week repetido no duplica PlanItem/date");
    assert.deepEqual(store.getPlanItemById("weekly").generationConfig, originalConfig);
}

{
    const store = createPlannerStore([item("ambiguous", {
        mode: "manual_dates",
        entries: [
            { date: "2026-08-27", startTime: "08:00", endTime: "09:00" },
            { date: "2026-08-27", startTime: "10:00", endTime: "11:00" },
        ],
    })], [], "2026-08-24");
    const beforeItems = store.getPlanItems();
    const beforeOccurrences = store.getOccurrences();
    expectError(
        () => store.applyGenerationConfigFromDate("ambiguous", "2026-08-27", weekly({ weekdays: [4] })),
        "ambiguous_future",
    );
    assert.deepEqual(store.getPlanItems(), beforeItems, "Apply future ambiguo no cambia generationConfig");
    assert.deepEqual(store.getOccurrences(), beforeOccurrences, "Apply future ambiguo no destruye occurrences");
}

{
    const store = createPlannerStore([item("weekly")], [], "2026-08-24");
    store.applyGenerationConfigFromDate("weekly", "2026-08-27", weekly({ weekdays: [4, 6] }));
    assert.deepEqual(store.getPlanItemById("weekly").generationConfig.weekdays, [4, 6]);
    assert.equal(store.getPlanItemById("weekly").generationConfig.startDate, "2026-08-27");
    assert.equal(store.getOccurrencesForDate("2026-08-27").filter(({ planItemId }) => planItemId === "weekly").length, 1);
}

{
    const planItems = [item("weekly")];
    const occurrences = [{ id: "one", planItemId: "weekly", date: "2026-08-24", startTime: "08:00", endTime: "09:00", status: "pending" }];
    const rows = buildPlannerRows(planItems, occurrences, "2026-08-27", true);
    assert.equal(rows.length, 1, "Vista mensual conserva PlanItem sin occurrence en selectedDate");
    assert.equal(rows[0].selectedOccurrence, null);
    const ambiguous = buildPlannerRows(planItems, [...occurrences, { ...occurrences[0], id: "two" }], "2026-08-24", true);
    assert.equal(ambiguous[0].selectedDateAmbiguous, true);
    assert.equal(ambiguous[0].selectedOccurrence, null);
}

console.log("editor-matrix-coherence.test.mjs: todas las pruebas pasaron");
