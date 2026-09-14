import assert from "node:assert/strict";
import { getSchedulingPriority, SCHEDULING_PRIORITY } from "../js/domain/scheduling-priority.js";
import { createPlannerStore, PlannerStoreError } from "../js/state/planner-store.js";
import { explicitDate, manualConfig } from "./helpers/generation-configs.mjs";

const plan = (id, type, startTime = "08:00", endTime = "10:00", date = "2026-08-27") => ({
    id, name: id, kind: "activity", activityType: type, generationConfig: explicitDate(date, startTime, endTime),
});
const draft = (name, type, startTime = "09:00", endTime = "09:30", date = "2026-08-27") => ({
    name, kind: "activity", activityType: type, generationConfig: explicitDate(date, startTime, endTime),
});
const expectCode = (action, code) => assert.throws(action, (error) => error instanceof PlannerStoreError && error.code === code);

function preparedAgainst(existingType, candidateType) {
    const store = createPlannerStore([plan("existing", existingType)], [], "2026-08-27");
    return { store, prepared: store.preparePlanItemCreation(draft("candidate", candidateType)) };
}

assert.deepEqual(SCHEDULING_PRIORITY, { NORMAL: 100, EVENT: 200, UNEXPECTED: 300 });
assert.equal(getSchedulingPriority({ kind: "habit", habitType: "scheduled" }), 100);
assert.equal(getSchedulingPriority({ kind: "activity", activityType: "anchor" }), 100);
assert.equal(getSchedulingPriority({ kind: "activity", activityType: "periodic" }), 100);
assert.equal(getSchedulingPriority({ kind: "activity", activityType: "event" }), 200);
assert.equal(getSchedulingPriority({ kind: "activity", activityType: "unexpected" }), 300);

expectCode(() => preparedAgainst("periodic", "periodic"), "priority_conflict");
assert.equal(preparedAgainst("periodic", "event").prepared.type, "override_required");
expectCode(() => preparedAgainst("event", "event"), "priority_conflict");
expectCode(() => preparedAgainst("unexpected", "event"), "priority_conflict");
assert.equal(preparedAgainst("periodic", "unexpected").prepared.type, "override_required");
assert.equal(preparedAgainst("event", "unexpected").prepared.type, "override_required");
expectCode(() => preparedAgainst("unexpected", "unexpected"), "priority_conflict");
expectCode(() => preparedAgainst("event", "periodic"), "priority_conflict");

{
    const { store } = preparedAgainst("periodic", "unexpected");
    const existing = store.getOccurrences()[0];
    store.setOccurrenceStatus(existing.id, "completed");
    expectCode(() => store.preparePlanItemCreation(draft("protected", "unexpected")), "completed_conflict");
    assert.equal(store.getOccurrenceById(existing.id).status, "completed");
}

for (const status of ["cancelled", "not_completed"]) {
    const { store } = preparedAgainst("periodic", "event");
    const existing = store.getOccurrences()[0];
    store.setOccurrenceStatus(existing.id, status);
    assert.equal(store.preparePlanItemCreation(draft(`free-${status}`, "event")).type, "ready");
}

{
    const store = createPlannerStore([
        plan("normal-a", "periodic", "08:00", "10:00"),
        plan("normal-b", "anchor", "10:00", "12:00"),
        plan("normal-c", "periodic", "12:00", "14:00"),
    ], [], "2026-08-27");
    const prepared = store.preparePlanItemCreation(draft("broad-event", "event", "09:00", "13:00"));
    assert.equal(prepared.type, "override_required");
    assert.deepEqual(prepared.conflicts.map(({ planItemName }) => planItemName).sort(), ["normal-a", "normal-b", "normal-c"]);
    const result = store.commitPreparedScheduleChange(prepared);
    assert.equal(result.occurrences.length, 1);
    assert.ok(prepared.conflicts.every(({ id }) => store.getOccurrenceById(id).status === "cancelled"));
}

{
    const store = createPlannerStore([
        plan("normal", "periodic", "08:00", "10:00"),
        plan("event", "event", "10:00", "12:00"),
    ], [], "2026-08-27");
    expectCode(() => store.preparePlanItemCreation(draft("mixed-event", "event", "09:00", "11:00")), "priority_conflict");
    assert.ok(store.getOccurrences().every(({ status }) => status === "pending"));
}

{
    const store = createPlannerStore([
        plan("normal", "periodic", "08:00", "10:00"),
        plan("completed", "periodic", "10:00", "12:00"),
    ], [], "2026-08-27");
    const completed = store.getOccurrencesForPlanItem("completed")[0];
    store.setOccurrenceStatus(completed.id, "completed");
    expectCode(() => store.preparePlanItemCreation(draft("mixed-unexpected", "unexpected", "09:00", "11:00")), "completed_conflict");
    assert.equal(store.getOccurrencesForPlanItem("normal")[0].status, "pending");
}

{
    const { store, prepared } = preparedAgainst("periodic", "event");
    const beforeItems = store.getPlanItems();
    const beforeOccurrences = store.getOccurrences();
    // Volver equivale a descartar el objeto preparado sin ejecutar commit.
    assert.equal(prepared.type, "override_required");
    assert.deepEqual(store.getPlanItems(), beforeItems);
    assert.deepEqual(store.getOccurrences(), beforeOccurrences);
}

{
    const { store, prepared } = preparedAgainst("periodic", "event");
    store.setOccurrenceStatus(store.getOccurrences()[0].id, "cancelled");
    const before = store.getOccurrences();
    expectCode(() => store.commitPreparedScheduleChange(prepared), "stale_override");
    assert.deepEqual(store.getOccurrences(), before);
}

{
    const { store, prepared } = preparedAgainst("periodic", "event");
    assert.equal(prepared.type, "override_required");
    const normal = store.getOccurrencesForPlanItem("existing")[0];
    const beforeItems = store.getPlanItems();
    const beforeOccurrences = store.getOccurrences();
    const originalAddPlanItem = store.addPlanItem;
    store.addPlanItem = () => {
        throw new PlannerStoreError("forced_failure", "Fallo controlado posterior a la preparación.");
    };
    expectCode(() => store.commitPreparedScheduleChange(prepared), "forced_failure");
    store.addPlanItem = originalAddPlanItem;
    assert.equal(store.getOccurrenceById(normal.id).status, "pending");
    assert.deepEqual(store.getPlanItems(), beforeItems);
    assert.deepEqual(store.getOccurrences(), beforeOccurrences);
}

{
    const store = createPlannerStore([
        plan("normal", "periodic", "08:00", "10:00"),
        plan("event-edit", "event", "12:00", "13:00"),
    ], [], "2026-08-27");
    const eventOccurrence = store.getOccurrencesForPlanItem("event-edit")[0];
    const prepared = store.prepareOccurrenceUpdate("event-edit", { name: "event-edit", kind: "activity", activityType: "event" }, eventOccurrence.id, { date: eventOccurrence.date, startTime: "09:00", endTime: "09:30" });
    assert.equal(prepared.type, "override_required");
    store.commitPreparedScheduleChange(prepared);
    assert.equal(store.getOccurrencesForPlanItem("normal")[0].status, "cancelled");
    assert.equal(store.getOccurrenceById(eventOccurrence.id).startTime, "09:00");
}

{
    const store = createPlannerStore([
        plan("event", "event", "08:00", "10:00"),
        plan("unexpected-edit", "unexpected", "12:00", "13:00"),
    ], [], "2026-08-27");
    const occurrence = store.getOccurrencesForPlanItem("unexpected-edit")[0];
    const prepared = store.prepareOccurrenceUpdate("unexpected-edit", { name: "unexpected-edit", kind: "activity", activityType: "unexpected" }, occurrence.id, { date: occurrence.date, startTime: "09:00", endTime: "09:30" });
    assert.equal(prepared.type, "override_required");
    store.commitPreparedScheduleChange(prepared);
    assert.equal(store.getOccurrencesForPlanItem("event")[0].status, "cancelled");
}

{
    const store = createPlannerStore([
        plan("normal-26", "periodic", "08:00", "10:00", "2026-08-26"),
        plan("normal-27", "periodic", "08:00", "10:00", "2026-08-27"),
    ], [], "2026-08-27");
    const manual = {
        name: "multi-event", kind: "activity", activityType: "event",
        generationConfig: manualConfig([
            { date: "2026-08-26", startTime: "09:00", endTime: "09:30" },
            { date: "2026-08-27", startTime: "09:00", endTime: "09:30" },
        ]),
    };
    const prepared = store.preparePlanItemCreation(manual);
    assert.equal(prepared.conflicts.length, 2);
    store.commitPreparedScheduleChange(prepared);
    assert.equal(store.getOccurrencesForPlanItem(store.getPlanItems().find(({ name }) => name === "multi-event").id).length, 2);
    assert.ok(store.getOccurrences().filter(({ planItemId }) => planItemId.startsWith("normal-")).every(({ status }) => status === "cancelled"));
}

{
    const store = createPlannerStore([], [], "2026-08-27");
    assert.throws(() => store.preparePlanItemCreation({
        name: "invalid", kind: "activity", activityType: "event",
        generationConfig: manualConfig([
            { date: "2026-08-27", startTime: "09:00", endTime: "10:00" },
            { date: "invalid", startTime: "09:00", endTime: "10:00" },
        ]),
    }));
    assert.equal(store.getPlanItems().length, 0);
    assert.equal(store.getOccurrences().length, 0);
}

console.log("scheduling-priority.test.mjs: todas las pruebas pasaron");
