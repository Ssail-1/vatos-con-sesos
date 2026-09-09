import assert from "node:assert/strict";
import { blocksSchedule } from "../js/domain/occurrence-status.js";
import { materializeOccurrenceDrafts, validateGenerationConfig } from "../js/scheduling/materializer.js";
import { createPlannerStore, PlannerStoreError } from "../js/state/planner-store.js";

function activity(id, generationConfig, activityType = "periodic") {
    return { id, name: id, kind: "activity", activityType, generationConfig };
}

function single(date, startTime, endTime) {
    return { mode: "single_date", date, startTime, endTime };
}

function weekly(overrides = {}) {
    return {
        mode: "weekly",
        startDate: "2026-08-01",
        endDate: null,
        indefinite: true,
        weekdays: [1, 3, 5],
        defaultStartTime: "08:00",
        defaultEndTime: "09:00",
        weekdayTimeOverrides: {},
        ...overrides,
    };
}

function expectStoreError(action, code) {
    assert.throws(action, (error) => error instanceof PlannerStoreError && error.code === code);
}

{
    const planItem = activity(
        "weekly",
        weekly({ weekdayTimeOverrides: { "5": { startTime: "10:00", endTime: "11:30" } } }),
    );
    const drafts = materializeOccurrenceDrafts(planItem, "2026-08-03", "2026-08-09");
    assert.deepEqual(
        drafts.map(({ date, startTime, endTime }) => ({ date, startTime, endTime })),
        [
            { date: "2026-08-03", startTime: "08:00", endTime: "09:00" },
            { date: "2026-08-05", startTime: "08:00", endTime: "09:00" },
            { date: "2026-08-07", startTime: "10:00", endTime: "11:30" },
        ],
    );
}

{
    const planItem = activity("interval", {
        mode: "interval_days",
        startDate: "2026-08-20",
        endDate: null,
        indefinite: true,
        intervalDays: 20,
        defaultStartTime: "12:00",
        defaultEndTime: "13:00",
    });
    assert.deepEqual(
        materializeOccurrenceDrafts(planItem, "2026-08-01", "2026-10-01").map(({ date }) => date),
        ["2026-08-20", "2026-09-09", "2026-09-29"],
    );
}

{
    const manual = activity("manual", {
        mode: "manual_dates",
        entries: [
            { date: "2026-09-01", startTime: "10:00", endTime: "11:00" },
            { date: "2026-11-20", startTime: "16:00", endTime: "17:30" },
        ],
    });
    const singleItem = activity("single", single("2027-07-10", "09:00", "23:00"), "event");
    assert.equal(materializeOccurrenceDrafts(manual, "2026-01-01", "2026-12-31").length, 2);
    assert.equal(materializeOccurrenceDrafts(singleItem, "2027-01-01", "2027-12-31").length, 1);
    assert.equal(materializeOccurrenceDrafts(singleItem, "2026-01-01", "2026-12-31").length, 0);
}

assert.throws(() => validateGenerationConfig(weekly({ weekdays: [1, 1, 3] })));
assert.throws(() => validateGenerationConfig(weekly({ weekdays: [] })));
assert.throws(() => validateGenerationConfig(weekly({ weekdays: [1, 8] })));
assert.throws(() => validateGenerationConfig(weekly({ weekdayTimeOverrides: { "2": { startTime: "08:00", endTime: "09:00" } } })));
assert.throws(() => validateGenerationConfig(weekly({ endDate: "2026-12-31", indefinite: true })));
assert.throws(() => validateGenerationConfig(weekly({ indefinite: undefined })));
assert.throws(() => validateGenerationConfig({ mode: "manual_dates", entries: [] }));

{
    const finite = activity(
        "finite",
        weekly({ startDate: "2026-08-05", endDate: "2026-08-10", indefinite: false }),
    );
    assert.deepEqual(
        materializeOccurrenceDrafts(finite, "2026-08-01", "2026-08-31").map(({ date }) => date),
        ["2026-08-05", "2026-08-07", "2026-08-10"],
    );
}

{
    const store = createPlannerStore([activity("repeat", weekly())], [], "2026-08-23");
    const before = store.getOccurrences().length;
    const created = store.materializePlanItem("repeat", "2026-08-01", "2026-09-30");
    assert.equal(created.length, 0);
    assert.equal(store.getOccurrences().length, before);
    assert.equal(store.getMaterializedThrough(), "2026-09-30");
}

{
    const store = createPlannerStore([], [], "2026-08-24", { historyEditWindowDays: 365 });
    const historical = store.addPlanItem({
        name: "Fecha histórica explícita",
        kind: "activity",
        activityType: "event",
        generationConfig: single("2026-01-15", "10:00", "11:00"),
    });
    assert.equal(historical.occurrences[0].date, "2026-01-15");
}

{
    const store = createPlannerStore([], [], "2026-08-24");
    const first = store.addPlanItem({
        name: "Primera",
        kind: "activity",
        activityType: "periodic",
        generationConfig: single("2026-08-24", "08:00", "10:00"),
    });
    const firstOccurrence = first.occurrences[0];
    store.setOccurrenceStatus(firstOccurrence.id, "completed");
    expectStoreError(
        () =>
            store.addPlanItem({
                name: "Superpuesta",
                kind: "activity",
                activityType: "periodic",
                generationConfig: single("2026-08-24", "09:00", "09:30"),
            }),
        "time_conflict",
    );
    assert.equal(store.getPlanItems().length, 1, "Una creación fallida debe ser atómica");
    store.setOccurrenceStatus(firstOccurrence.id, "in_progress");
    expectStoreError(
        () =>
            store.addPlanItem({
                name: "También superpuesta",
                kind: "activity",
                activityType: "periodic",
                generationConfig: single("2026-08-24", "09:15", "09:45"),
            }),
        "time_conflict",
    );
    store.setOccurrenceStatus(firstOccurrence.id, "not_completed");
    const second = store.addPlanItem({
        name: "Segunda",
        kind: "activity",
        activityType: "periodic",
        generationConfig: single("2026-08-24", "09:00", "09:30"),
    });
    assert.equal(second.occurrences.length, 1);
    expectStoreError(() => store.setOccurrenceStatus(firstOccurrence.id, "pending"), "time_conflict");
    assert.equal(store.getOccurrenceById(firstOccurrence.id).status, "not_completed");
    store.setOccurrenceStatus(second.occurrences[0].id, "cancelled");
    assert.equal(blocksSchedule(store.getOccurrenceById(second.occurrences[0].id)), false);
    store.setOccurrenceStatus(firstOccurrence.id, "pending");
}

{
    const store = createPlannerStore([], [], "2026-08-25");
    const released = store.addPlanItem({
        name: "Occurrence A",
        kind: "activity",
        activityType: "periodic",
        generationConfig: single("2026-08-24", "05:30", "07:30"),
    }).occurrences[0];
    store.setOccurrenceStatus(released.id, "not_completed");

    const occupant = store.addPlanItem({
        name: "Occurrence B",
        kind: "activity",
        activityType: "periodic",
        generationConfig: single("2026-08-24", "06:00", "06:30"),
    }).occurrences[0];

    assert.equal(store.advanceOccurrenceStatus(released.id).status, "not_finished");
    assert.equal(store.advanceOccurrenceStatus(released.id).status, "cancelled");
    assert.equal(store.advanceOccurrenceStatus(released.id).status, "not_completed");
    assert.equal(store.getOccurrenceById(occupant.id).status, "pending");

    expectStoreError(() => store.setOccurrenceStatus(released.id, "pending"), "time_conflict");
    assert.equal(store.getOccurrenceById(released.id).status, "not_completed");
    assert.equal(store.getOccurrenceById(occupant.id).status, "pending");

    store.setOccurrenceStatus(occupant.id, "cancelled");
    assert.equal(store.advanceOccurrenceStatus(released.id).status, "not_finished");
    assert.equal(store.advanceOccurrenceStatus(released.id).status, "cancelled");
    assert.equal(store.advanceOccurrenceStatus(released.id).status, "pending");
    assert.equal(store.getOccurrenceById(occupant.id).status, "cancelled");
}

{
    const store = createPlannerStore([], [], "2026-08-25");
    const result = store.addPlanItem({
        name: "Dos veces",
        kind: "activity",
        activityType: "periodic",
        generationConfig: {
            mode: "manual_dates",
            entries: [
                { date: "2026-08-25", startTime: "08:00", endTime: "09:00" },
                { date: "2026-08-25", startTime: "20:00", endTime: "21:00" },
            ],
        },
    });
    assert.equal(result.occurrences.length, 2);
    const occurrence = result.occurrences[0];
    store.setOccurrenceStatus(occurrence.id, "cancelled");
    const updated = store.updateOccurrence(occurrence.id, {
        date: "2026-08-26",
        startTime: "09:00",
        endTime: "10:30",
    });
    assert.equal(updated.id, occurrence.id);
    assert.equal(updated.planItemId, occurrence.planItemId);
    assert.equal(updated.status, "cancelled");
}

{
    const store = createPlannerStore([activity("recurring", weekly())], [], "2026-08-23");
    store.addPlanItem({
        name: "Evento futuro",
        kind: "activity",
        activityType: "event",
        generationConfig: single("2027-07-10", "15:00", "16:00"),
    });
    assert.equal(store.getMaterializedThrough(), "2027-07-31");
    assert.ok(store.getOccurrencesForPlanItem("recurring").some(({ date }) => date.startsWith("2027-07")));
}

{
    const store = createPlannerStore([], [], "2026-08-23");
    const result = store.addPlanItem({
        name: "Contrato",
        kind: "habit",
        habitType: "scheduled",
        generationConfig: single("2026-08-23", "12:00", "12:15"),
    });
    assert.deepEqual(Object.keys(result.planItem).sort(), ["generationConfig", "habitType", "id", "kind", "name"]);
    assert.deepEqual(
        Object.keys(result.occurrences[0]).sort(),
        ["date", "endTime", "id", "planItemId", "startTime", "status"],
    );
    const renamed = store.updatePlanItemAndOccurrence(
        result.planItem.id,
        { name: "Contrato renombrado", kind: "activity", activityType: "event" },
        result.occurrences[0].id,
        { date: "2026-08-23", startTime: "12:00", endTime: "12:15" },
    );
    assert.equal(renamed.planItem.id, result.planItem.id);
    assert.equal(renamed.occurrence.id, result.occurrences[0].id);
    assert.equal("habitType" in renamed.planItem, false);
    assert.equal(renamed.planItem.activityType, "event");
}

console.log("planner-engine.test.mjs: todas las pruebas pasaron");
