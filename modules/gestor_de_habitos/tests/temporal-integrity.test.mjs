import assert from "node:assert/strict";
import { blocksSchedule, getStatusPresentation, occurrenceStatuses } from "../js/domain/occurrence-status.js";
import { wasDisplacedByPriorityOverride } from "../js/domain/scheduling-priority.js";
import {
    getDateTemporalZone,
    getHistoryCutoff,
    HISTORY_EDIT_WINDOW_DAYS,
    TEMPORAL_ZONES,
} from "../js/domain/temporal-integrity.js";
import { createPlannerStore, PlannerStoreError } from "../js/state/planner-store.js";
import { buildPlannerRows } from "../js/views/planner-matrix.js";

const explicitDate = (date, startTime = "08:00", endTime = "09:00") => ({ mode: "manual_dates", entries: [{ date, startTime, endTime }] });
const activity = (id, date, startTime = "08:00", endTime = "09:00", activityType = "periodic") => ({
    id,
    name: id,
    kind: "activity",
    activityType,
    generationConfig: explicitDate(date, startTime, endTime),
});
const habit = (id, date, startTime, endTime) => ({
    id,
    name: id,
    kind: "habit",
    habitType: "scheduled",
    generationConfig: explicitDate(date, startTime, endTime),
});
const expectCode = (action, code) => assert.throws(
    action,
    (error) => error instanceof PlannerStoreError && error.code === code,
);

assert.equal(HISTORY_EDIT_WINDOW_DAYS, 1);
assert.equal(getHistoryCutoff("2026-09-29", 1), "2026-09-28");
assert.equal(getDateTemporalZone("2026-09-29", "2026-09-29", 1), TEMPORAL_ZONES.EDITABLE);
assert.equal(getDateTemporalZone("2026-09-28", "2026-09-29", 1), TEMPORAL_ZONES.EDITABLE);
assert.equal(getDateTemporalZone("2026-09-27", "2026-09-29", 1), TEMPORAL_ZONES.FROZEN);
assert.equal(getDateTemporalZone("2026-09-30", "2026-09-29", 1), TEMPORAL_ZONES.FUTURE);
assert.equal(getHistoryCutoff("2026-09-29", 0), "2026-09-29");
assert.equal(getHistoryCutoff("2026-09-29", 3), "2026-09-26");
assert.equal(getDateTemporalZone("2026-09-27", "2026-09-29", 3), TEMPORAL_ZONES.EDITABLE);

{
    const wideWindow = createPlannerStore(
        [activity("wide-window", "2026-09-27")],
        [],
        "2026-09-29",
        { historyEditWindowDays: 3 },
    );
    const closedWindow = createPlannerStore(
        [activity("closed-window", "2026-09-28")],
        [],
        "2026-09-29",
        { historyEditWindowDays: 0 },
    );
    assert.equal(wideWindow.getOccurrencesForPlanItem("wide-window")[0].status, "pending");
    assert.equal(closedWindow.getOccurrencesForPlanItem("closed-window")[0].status, "not_completed");
}

{
    const statuses = ["pending", "in_progress", "completed", "not_completed", "not_finished", "cancelled"];
    const items = statuses.map((status, index) => activity(`frozen-${status}`, "2026-09-27", `${String(8 + index).padStart(2, "0")}:00`, `${String(9 + index).padStart(2, "0")}:00`));
    const overrides = statuses.map((status, index) => ({ planItemId: items[index].id, date: "2026-09-27", status }));
    const store = createPlannerStore(items, overrides, "2026-09-29");
    const expected = {
        pending: "not_completed",
        in_progress: "not_finished",
        completed: "completed",
        not_completed: "not_completed",
        not_finished: "not_finished",
        cancelled: "cancelled",
    };
    statuses.forEach((originalStatus) => {
        const occurrence = store.getOccurrencesForPlanItem(`frozen-${originalStatus}`)[0];
        assert.equal(occurrence.status, expected[originalStatus], `${originalStatus} se reconcilia correctamente`);
        assert.equal(occurrence.planItemId, `frozen-${originalStatus}`);
        assert.equal(occurrence.date, "2026-09-27");
    });
    assert.deepEqual(store.reconcileTemporalState("2026-09-29"), [], "reconciliar dos veces es idempotente");
}

{
    const frozenWeekly = {
        id: "frozen-weekly",
        name: "frozen-weekly",
        kind: "activity",
        activityType: "periodic",
        generationConfig: {
            mode: "weekly",
            startDate: "2026-09-01",
            endDate: null,
            indefinite: true,
            weekdays: [7],
            defaultStartTime: "08:00",
            defaultEndTime: "09:00",
            weekdayTimeOverrides: {},
        },
    };
    const store = createPlannerStore([frozenWeekly], [], "2026-09-29");
    const occurrence = store.getOccurrencesForDate("2026-09-27")[0];
    const before = store.getOccurrenceById(occurrence.id);
    expectCode(() => store.setOccurrenceStatus(occurrence.id, "cancelled"), "history_frozen");
    expectCode(() => store.updateOccurrence(occurrence.id, { date: occurrence.date, startTime: "10:00", endTime: "11:00" }), "history_frozen");
    expectCode(() => store.prepareOccurrenceUpdate(frozenWeekly.id, { name: frozenWeekly.name, kind: "activity", activityType: "periodic" }, occurrence.id, { date: occurrence.date, startTime: "10:00", endTime: "11:00" }), "history_frozen");
    expectCode(() => store.applyWeeklyToWeek(frozenWeekly.id, occurrence.date, frozenWeekly.generationConfig), "history_frozen");
    expectCode(() => store.applyGenerationConfigFromDate(frozenWeekly.id, occurrence.date, frozenWeekly.generationConfig), "history_frozen");
    expectCode(() => store.prepareOccurrenceAddition(frozenWeekly.id, { date: occurrence.date, startTime: "12:00", endTime: "13:00" }), "history_frozen");
    expectCode(
        () => store.preparePlanItemCreation(activity("prepared-in-frozen-history", occurrence.date)),
        "history_frozen",
    );
    expectCode(
        () => store.addPlanItem(activity("added-in-frozen-history", occurrence.date)),
        "history_frozen",
    );
    assert.deepEqual(store.getOccurrenceById(occurrence.id), before, "las operaciones frozen no mutan la occurrence");
}

{
    const store = createPlannerStore([activity("future", "2026-09-30")], [], "2026-09-29");
    const occurrence = store.getOccurrencesForPlanItem("future")[0];
    assert.equal(store.advanceOccurrenceStatus(occurrence.id).status, "cancelled");
    assert.equal(store.advanceOccurrenceStatus(occurrence.id).status, "pending");
    for (const status of ["in_progress", "completed", "not_completed", "not_finished"]) {
        expectCode(() => store.setOccurrenceStatus(occurrence.id, status), "future_status_locked");
        assert.equal(store.getOccurrenceById(occurrence.id).status, "pending");
    }
}

{
    const statuses = ["in_progress", "completed", "not_completed", "not_finished"];
    const items = statuses.map((status, index) => activity(`future-${status}`, "2026-09-30", `${String(8 + index).padStart(2, "0")}:00`, `${String(9 + index).padStart(2, "0")}:00`));
    const store = createPlannerStore(
        items,
        statuses.map((status, index) => ({ planItemId: items[index].id, date: "2026-09-30", status })),
        "2026-09-29",
    );
    statuses.forEach((status) => {
        const occurrence = store.getOccurrencesForPlanItem(`future-${status}`)[0];
        expectCode(() => store.advanceOccurrenceStatus(occurrence.id), "future_status_locked");
        assert.equal(store.getOccurrenceById(occurrence.id).status, status);
    });
}

{
    const store = createPlannerStore([activity("released-future", "2026-09-30", "08:00", "10:00")], [], "2026-09-29");
    const released = store.getOccurrencesForPlanItem("released-future")[0];
    store.setOccurrenceStatus(released.id, "cancelled");
    store.addPlanItem({ name: "occupant", kind: "activity", activityType: "periodic", generationConfig: explicitDate("2026-09-30", "09:00", "09:30") });
    expectCode(() => store.advanceOccurrenceStatus(released.id), "time_conflict");
    assert.equal(store.getOccurrenceById(released.id).status, "cancelled", "el futuro no usa fallback histórico");
}

{
    const store = createPlannerStore([activity("lower-pending", "2026-09-29", "08:00", "10:00")], [], "2026-09-29");
    const lower = store.getOccurrencesForPlanItem("lower-pending")[0];
    const prepared = store.preparePlanItemCreation({ name: "higher-event", kind: "activity", activityType: "event", generationConfig: explicitDate("2026-09-29", "09:00", "09:30") });
    const result = store.commitPreparedScheduleChange(prepared);
    const displaced = store.getOccurrenceById(lower.id);
    assert.equal(displaced.status, "cancelled", "la geometría no inventa que pending había comenzado");
    assert.equal(displaced.statusContext.reason, "priority_override");
    assert.equal(displaced.statusContext.sourceOccurrenceId, result.occurrences.find(({ planItemId }) => planItemId === result.planItem.id).id);
    assert.equal(wasDisplacedByPriorityOverride(displaced), true);
}

{
    const store = createPlannerStore([activity("correctable-interruption", "2026-09-29", "08:00", "10:00")], [], "2026-09-29");
    const lower = store.getOccurrencesForPlanItem("correctable-interruption")[0];
    const prepared = store.preparePlanItemCreation({ name: "interrupting-event", kind: "activity", activityType: "event", generationConfig: explicitDate("2026-09-29", "09:00", "09:30") });
    store.commitPreparedScheduleChange(prepared);
    assert.equal(store.advanceOccurrenceStatus(lower.id).status, "not_completed");
    assert.equal(store.advanceOccurrenceStatus(lower.id).status, "not_finished");
    const corrected = store.advanceOccurrenceStatus(lower.id);
    assert.equal(corrected.status, "cancelled");
    assert.equal(wasDisplacedByPriorityOverride(corrected), true, "la corrección conserva la procedencia del override");
}

{
    const store = createPlannerStore([activity("lower-progress", "2026-09-29", "08:00", "10:00")], [], "2026-09-29");
    const lower = store.getOccurrencesForPlanItem("lower-progress")[0];
    store.setOccurrenceStatus(lower.id, "in_progress");
    const prepared = store.preparePlanItemCreation({ name: "higher-unexpected", kind: "activity", activityType: "unexpected", generationConfig: explicitDate("2026-09-29", "09:00", "09:30") });
    store.commitPreparedScheduleChange(prepared);
    const displaced = store.getOccurrenceById(lower.id);
    assert.equal(displaced.status, "not_finished");
    assert.equal(wasDisplacedByPriorityOverride(displaced), true);
    assert.equal(blocksSchedule(displaced), false);
}

{
    const store = createPlannerStore([activity("manual-cancel", "2026-09-29")], [], "2026-09-29");
    const occurrence = store.getOccurrencesForPlanItem("manual-cancel")[0];
    const cancelled = store.setOccurrenceStatus(occurrence.id, "cancelled");
    assert.equal("statusContext" in cancelled, false);
    assert.equal(wasDisplacedByPriorityOverride(cancelled), false);
}

{
    const store = createPlannerStore([activity("protected", "2026-09-29", "08:00", "10:00")], [], "2026-09-29");
    const completed = store.getOccurrencesForPlanItem("protected")[0];
    store.setOccurrenceStatus(completed.id, "completed");
    expectCode(
        () => store.preparePlanItemCreation({ name: "unexpected", kind: "activity", activityType: "unexpected", generationConfig: explicitDate("2026-09-29", "09:00", "09:30") }),
        "completed_conflict",
    );
    assert.equal(store.getOccurrenceById(completed.id).status, "completed");
}

{
    const store = createPlannerStore([
        activity("activity-not-finished", "2026-09-29", "08:00", "09:00"),
        habit("habit-not-finished", "2026-09-29", "10:00", "11:00"),
    ], [], "2026-09-29");
    for (const planItemId of ["activity-not-finished", "habit-not-finished"]) {
        const occurrence = store.getOccurrencesForPlanItem(planItemId)[0];
        const updated = store.setOccurrenceStatus(occurrence.id, "not_finished");
        assert.equal(updated.status, "not_finished");
        assert.equal(blocksSchedule(updated), false);
    }
    assert.equal(buildPlannerRows(store.getPlanItems(), store.getOccurrences(), "2026-09-29", false).length, 2);
    store.addPlanItem({ name: "uses-released-time", kind: "activity", activityType: "periodic", generationConfig: explicitDate("2026-09-29", "08:15", "08:45") });
}

{
    let currentDate = "2026-09-28";
    const store = createPlannerStore(
        [activity("day-change", "2026-09-27")],
        [],
        currentDate,
        { getCurrentDateKey: () => currentDate },
    );
    const occurrence = store.getOccurrencesForPlanItem("day-change")[0];
    assert.equal(occurrence.status, "pending");
    currentDate = "2026-09-29";
    assert.equal(store.reconcileTemporalState()[0].status, "not_completed");
    assert.deepEqual(store.reconcileTemporalState(), []);
}

assert.ok(occurrenceStatuses.includes("not_finished"));
assert.deepEqual(
    getStatusPresentation("not_finished", "Actividad", "29 de septiembre"),
    {
        status: "not_finished",
        symbol: "◷",
        modifier: "!",
        label: "No terminada",
        color: "var(--in-progress)",
        accessibleLabel: "Actividad, 29 de septiembre: No terminada. Activar para cambiar estado.",
    },
);

console.log("temporal-integrity.test.mjs: todas las pruebas pasaron");
