import assert from "node:assert/strict";
import { createPlannerStore, PlannerStoreError } from "../js/state/planner-store.js";
import { manualConfig, weeklyConfig as weekly } from "./helpers/generation-configs.mjs";

const item = (id, config = weekly()) => ({ id, name: id, kind: "activity", activityType: "periodic", generationConfig: config });
const classifiedItem = (id, kind, type) => ({
    id,
    name: id,
    kind,
    ...(kind === "habit" ? { habitType: type } : { activityType: type }),
    generationConfig: weekly(),
});

function expectError(action, code) {
    assert.throws(action, (error) => error instanceof PlannerStoreError && error.code === code);
}

const revisedWeekly = weekly({ startTime: "10:00", endTime: "11:00" });

for (const [kind, type] of [
    ["habit", "scheduled"],
    ["activity", "anchor"],
    ["activity", "periodic"],
]) {
    const id = `${kind}-${type}-pending`;
    const store = createPlannerStore([classifiedItem(id, kind, type)], [], "2026-08-24");
    const result = store.applyGenerationConfigFromDate(id, { ...revisedWeekly, startDate: "2026-08-24" });
    const effectiveOccurrence = store.getOccurrencesForDate("2026-08-24")[0];
    assert.equal(effectiveOccurrence.status, "pending", `${id}: effectiveDate permanece pending`);
    assert.equal(effectiveOccurrence.startTime, "10:00", `${id}: effectiveDate adopta el horario nuevo`);
    assert.deepEqual(result.preservedEffectiveDateOccurrences, [], `${id}: no reporta historial preservado`);
}

for (const [kind, type] of [
    ["habit", "scheduled"],
    ["activity", "periodic"],
]) {
    for (const status of ["in_progress", "completed", "not_completed", "cancelled"]) {
        const id = `${kind}-${type}-${status}`;
        const store = createPlannerStore([classifiedItem(id, kind, type)], [], "2026-08-24");
        const effectiveOccurrence = store.getOccurrencesForDate("2026-08-24")[0];
        store.setOccurrenceStatus(effectiveOccurrence.id, status);
        const result = store.applyGenerationConfigFromDate(id, { ...revisedWeekly, startDate: "2026-08-24" });
        const preserved = store.getOccurrenceById(effectiveOccurrence.id);
        assert.equal(preserved.status, status, `${id}: conserva status histórico`);
        assert.equal(preserved.startTime, "08:00", `${id}: conserva horario histórico`);
        assert.deepEqual(
            result.preservedEffectiveDateOccurrences.map(({ id: occurrenceId }) => occurrenceId),
            [effectiveOccurrence.id],
            `${id}: informa la occurrence preservada`,
        );
    }
}

{
    const store = createPlannerStore([item("weekly")], [
        { planItemId: "weekly", date: "2026-08-24", status: "completed" },
        { planItemId: "weekly", date: "2026-08-26", status: "not_completed" },
        { planItemId: "weekly", date: "2026-08-28", status: "cancelled" },
    ], "2026-08-24");
    const originalConfig = store.getPlanItemById("weekly").generationConfig;
    const monday = store.getOccurrencesForDate("2026-08-24")[0];
    const wednesday = store.getOccurrencesForDate("2026-08-26")[0];
    const friday = store.getOccurrencesForDate("2026-08-28")[0];
    store.applyWeeklyToWeek("weekly", "2026-08-26", weekly({
        days: [1, 2, 3, 5],
        perDayTimes: { "2": { startTime: "10:00", endTime: "11:00" } },
    }));
    assert.deepEqual(store.getPlanItemById("weekly").generationConfig, originalConfig, "Apply week no cambia generationConfig");
    assert.equal(store.getOccurrencesForDate("2026-08-25")[0].startTime, "10:00", "añade weekday con override");
    assert.equal(store.getOccurrenceById(monday.id).status, "completed");
    assert.equal(store.getOccurrenceById(wednesday.id).status, "not_completed");
    assert.equal(store.getOccurrenceById(friday.id).status, "cancelled");
}

{
    const store = createPlannerStore([item("weekly")], [], "2026-08-24");
    store.applyWeeklyToWeek("weekly", "2026-08-24", weekly({ days: [1, 5], startTime: "07:00", endTime: "08:00" }));
    assert.equal(store.getOccurrencesForDate("2026-08-26").length, 0, "retira weekday pending");
    assert.equal(store.getOccurrencesForDate("2026-08-24")[0].startTime, "07:00", "cambia horario semanal");
}

{
    const store = createPlannerStore([
        item("weekly"),
        item("blocker", manualConfig([{ date: "2026-08-25", startTime: "10:30", endTime: "11:30" }])),
    ], [], "2026-08-24");
    const before = store.getOccurrences();
    expectError(() => store.applyWeeklyToWeek("weekly", "2026-08-24", weekly({ days: [1, 2, 3, 5], perDayTimes: { "2": { startTime: "10:00", endTime: "11:00" } } })), "priority_conflict");
    assert.deepEqual(store.getOccurrences(), before, "Apply week debe ser atómico");
}

{
    const store = createPlannerStore([item("ambiguous", manualConfig([
            { date: "2026-08-24", startTime: "08:00", endTime: "09:00" },
            { date: "2026-08-24", startTime: "10:00", endTime: "11:00" },
    ]))], [], "2026-08-24");
    const before = store.getOccurrences();
    expectError(() => store.applyWeeklyToWeek("ambiguous", "2026-08-24", weekly()), "unsupported_mode");
    assert.deepEqual(store.getOccurrences(), before, "manual_dates no modifica occurrences mediante Apply Week");
}

{
    const store = createPlannerStore([item("weekly")], [
        { planItemId: "weekly", date: "2026-08-26", status: "completed" },
        { planItemId: "weekly", date: "2026-08-28", status: "not_completed" },
        { planItemId: "weekly", date: "2026-08-31", status: "in_progress" },
        { planItemId: "weekly", date: "2026-09-02", status: "cancelled" },
    ], "2026-08-24");
    const past = store.getOccurrencesForDate("2026-08-24")[0];
    const completed = store.getOccurrencesForDate("2026-08-26")[0];
    const notCompleted = store.getOccurrencesForDate("2026-08-28")[0];
    const inProgress = store.getOccurrencesForDate("2026-08-31")[0];
    const cancelled = store.getOccurrencesForDate("2026-09-02")[0];
    const horizon = store.getMaterializedThrough();
    const result = store.applyGenerationConfigFromDate("weekly", weekly({
        days: [2, 4], startDate: "2026-08-25", startTime: "10:00", endTime: "11:00",
        perDayTimes: { "4": { startTime: "12:00", endTime: "13:00" } },
    }));
    assert.equal(result.planItem.generationConfig.startDate, "2026-08-25");
    assert.deepEqual([...new Set(result.planItem.generationConfig.slots.map(({ isoWeekday }) => isoWeekday))], [2, 4]);
    assert.equal(store.getOccurrenceById(past.id).date, "2026-08-24", "preserva pasado");
    for (const [occurrence, status] of [[completed, "completed"], [notCompleted, "not_completed"], [inProgress, "in_progress"], [cancelled, "cancelled"]]) {
        assert.equal(store.getOccurrenceById(occurrence.id).status, status, `preserva ${status}`);
    }
    assert.equal(store.getMaterializedThrough(), horizon, "mantiene horizonte");
    assert.equal(store.getOccurrencesForDate("2026-09-03")[0].startTime, "12:00", "regenera pending con override");
    const count = store.getOccurrences().length;
    store.materializePlanItem("weekly", "2026-08-25", horizon);
    assert.equal(store.getOccurrences().length, count, "materialización posterior idempotente");
}

{
    const store = createPlannerStore([
        item("weekly"),
        item("blocker", manualConfig([{ date: "2026-08-27", startTime: "10:30", endTime: "11:30" }])),
    ], [], "2026-08-24");
    const beforeItems = store.getPlanItems();
    const beforeOccurrences = store.getOccurrences();
    expectError(() => store.applyGenerationConfigFromDate("weekly", weekly({ days: [2, 4], startDate: "2026-08-25", startTime: "10:00", endTime: "11:00" })), "priority_conflict");
    assert.deepEqual(store.getPlanItems(), beforeItems, "Apply future no cambia config si falla");
    assert.deepEqual(store.getOccurrences(), beforeOccurrences, "Apply future no retira pending si falla");
}

{
    const store = createPlannerStore([item("weekly")], [], "2026-08-24");
    store.applyGenerationConfigFromDate("weekly", weekly({ startDate: "2026-08-24", perDayTimes: { "5": { startTime: "09:00", endTime: "10:00" } } }));
    assert.equal(store.getPlanItemById("weekly").generationConfig.slots.find(({ isoWeekday }) => isoWeekday === 5).startTime, "09:00", "crea horario diferente");
    store.applyGenerationConfigFromDate("weekly", weekly({ startDate: "2026-08-24", perDayTimes: { "5": { startTime: "10:00", endTime: "11:00" } } }));
    assert.equal(store.getPlanItemById("weekly").generationConfig.slots.find(({ isoWeekday }) => isoWeekday === 5).startTime, "10:00", "actualiza horario diferente");
    store.applyGenerationConfigFromDate("weekly", weekly({ startDate: "2026-08-24" }));
    assert.equal(store.getPlanItemById("weekly").generationConfig.slots.find(({ isoWeekday }) => isoWeekday === 5).startTime, "08:00", "restaura el horario general visual");
}

console.log("recurrence-editor.test.mjs: todas las pruebas pasaron");
