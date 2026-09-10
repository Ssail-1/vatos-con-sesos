import assert from "node:assert/strict";
import { materializeOccurrenceDrafts } from "../js/scheduling/materializer.js";
import { createPlannerStore, PlannerStoreError } from "../js/state/planner-store.js";

const REFERENCE_DATE = "2026-09-29";
const allWeekdays = [1, 2, 3, 4, 5, 6, 7];

function weeklyConfig(overrides = {}) {
    return {
        mode: "weekly",
        startDate: "2026-09-20",
        endDate: null,
        indefinite: true,
        weekdays: allWeekdays,
        defaultStartTime: "08:00",
        defaultEndTime: "09:00",
        weekdayTimeOverrides: {},
        ...overrides,
    };
}

function planItem(id, generationConfig = weeklyConfig(), activityType = "periodic") {
    return { id, name: id, kind: "activity", activityType, generationConfig };
}

function explicitDateConfig(date, startTime = "08:00", endTime = "09:00", controls = {}) {
    return { mode: "manual_dates", entries: [{ date, startTime, endTime }], ...controls };
}

function expectCode(action, code) {
    assert.throws(action, (error) => error instanceof PlannerStoreError && error.code === code);
}

function occurrenceFor(store, planItemId, date) {
    return store.getOccurrencesForPlanItem(planItemId).find((occurrence) => occurrence.date === date);
}

// Delete individual: presente, ayer, frozen y matriz completa de estados.
for (const date of [REFERENCE_DATE, "2026-09-28"]) {
    const store = createPlannerStore([planItem(`deletable-${date}`)], [], REFERENCE_DATE);
    const occurrence = occurrenceFor(store, `deletable-${date}`, date);
    const result = store.deleteOccurrenceForDate(occurrence.id);
    assert.equal(result.deletedOccurrence.id, occurrence.id);
    assert.equal(store.getOccurrenceById(occurrence.id), null);
    assert.deepEqual(store.getPlanItemById(`deletable-${date}`).generationConfig.excludedDates, [date]);
}

{
    const store = createPlannerStore([planItem("frozen-delete")], [], REFERENCE_DATE);
    const frozen = occurrenceFor(store, "frozen-delete", "2026-09-27");
    const before = store.getPlanItemById("frozen-delete");
    expectCode(() => store.deleteOccurrenceForDate(frozen.id), "history_frozen");
    assert.deepEqual(store.getPlanItemById("frozen-delete"), before);
    assert.ok(store.getOccurrenceById(frozen.id));
}

for (const status of ["cancelled", "in_progress", "completed", "not_completed", "not_finished"]) {
    const store = createPlannerStore([planItem(`protected-${status}`)], [], REFERENCE_DATE);
    const occurrence = occurrenceFor(store, `protected-${status}`, REFERENCE_DATE);
    store.setOccurrenceStatus(occurrence.id, status);
    const before = store.getOccurrencesForPlanItem(`protected-${status}`);
    expectCode(() => store.deleteOccurrenceForDate(occurrence.id), "deletion_status_locked");
    assert.deepEqual(store.getOccurrencesForPlanItem(`protected-${status}`), before);
    assert.equal(store.getPlanItemById(`protected-${status}`).generationConfig.excludedDates, undefined);
}

{
    const store = createPlannerStore([planItem("future-cancelled")], [], REFERENCE_DATE);
    const occurrence = occurrenceFor(store, "future-cancelled", "2026-09-30");
    store.setOccurrenceStatus(occurrence.id, "cancelled");
    store.deleteOccurrenceForDate(occurrence.id);
    assert.equal(store.getOccurrenceById(occurrence.id), null);
    assert.deepEqual(store.getPlanItemById("future-cancelled").generationConfig.excludedDates, ["2026-09-30"]);
}

// La exclusión evita regenerar, conserva otras fechas y puede restaurarse atómicamente.
{
    const store = createPlannerStore([planItem("restorable")], [], REFERENCE_DATE);
    const deleted = occurrenceFor(store, "restorable", REFERENCE_DATE);
    store.deleteOccurrenceForDate(deleted.id);
    assert.deepEqual(store.materializePlanItem("restorable", REFERENCE_DATE, "2026-09-30"), []);
    assert.ok(occurrenceFor(store, "restorable", "2026-09-30"));

    const prepared = store.prepareOccurrenceAddition("restorable", {
        date: REFERENCE_DATE,
        startTime: deleted.startTime,
        endTime: deleted.endTime,
    });
    const restored = store.commitPreparedScheduleChange(prepared);
    assert.equal(restored.date, REFERENCE_DATE);
    assert.deepEqual(store.getPlanItemById("restorable").generationConfig.excludedDates, []);
    const countBefore = store.getOccurrencesForPlanItem("restorable").length;
    store.materializePlanItem("restorable", REFERENCE_DATE, "2026-09-30");
    assert.equal(store.getOccurrencesForPlanItem("restorable").length, countBefore);
}

{
    const store = createPlannerStore([planItem("restore-conflict")], [], REFERENCE_DATE);
    const deleted = occurrenceFor(store, "restore-conflict", REFERENCE_DATE);
    store.deleteOccurrenceForDate(deleted.id);
    store.addPlanItem(planItem("occupant", explicitDateConfig(REFERENCE_DATE)));
    expectCode(
        () => store.prepareOccurrenceAddition("restore-conflict", {
            date: REFERENCE_DATE,
            startTime: "08:00",
            endTime: "09:00",
        }),
        "priority_conflict",
    );
    assert.deepEqual(store.getPlanItemById("restore-conflict").generationConfig.excludedDates, [REFERENCE_DATE]);
    expectCode(
        () => store.prepareOccurrenceAddition("restore-conflict", {
            date: REFERENCE_DATE,
            startTime: "09:00",
            endTime: "08:00",
        }),
        "invalid_occurrence",
    );
    assert.deepEqual(store.getPlanItemById("restore-conflict").generationConfig.excludedDates, [REFERENCE_DATE]);
}

// La reconciliación limpia exclusiones frozen sin reconstruir historia.
{
    const config = weeklyConfig({ excludedDates: ["2026-09-27", "2026-09-28"] });
    const store = createPlannerStore([planItem("cleanup", config)], [], REFERENCE_DATE);
    assert.deepEqual(store.getPlanItemById("cleanup").generationConfig.excludedDates, ["2026-09-28"]);
    assert.deepEqual(store.reconcileTemporalState(), []);
    assert.deepEqual(store.getPlanItemById("cleanup").generationConfig.excludedDates, ["2026-09-28"]);
    assert.deepEqual(store.materializePlanItem("cleanup", "2026-09-27", "2026-09-27"), []);
    assert.equal(occurrenceFor(store, "cleanup", "2026-09-27"), undefined);
}

// Stop preserva historia y retira solo pending y cancelled futuro desde la frontera.
{
    const entries = [
        ["2026-09-27", "07:00", "08:00"],
        ["2026-09-28", "08:00", "09:00"],
        ["2026-09-29", "09:00", "10:00"],
        ["2026-09-30", "10:00", "11:00"],
        ["2026-10-01", "11:00", "12:00"],
        ["2026-10-02", "12:00", "13:00"],
        ["2026-10-03", "13:00", "14:00"],
        ["2026-10-04", "14:00", "15:00"],
        ["2026-10-05", "15:00", "16:00"],
    ].map(([date, startTime, endTime]) => ({ date, startTime, endTime }));
    const config = { mode: "manual_dates", entries, excludedDates: ["2026-10-06"] };
    const statuses = new Map([
        ["2026-09-27", "completed"],
        ["2026-09-28", "completed"],
        ["2026-09-29", "cancelled"],
        ["2026-09-30", "cancelled"],
        ["2026-10-01", "pending"],
        ["2026-10-02", "completed"],
        ["2026-10-03", "not_completed"],
        ["2026-10-04", "not_finished"],
        ["2026-10-05", "in_progress"],
    ]);
    const store = createPlannerStore(
        [planItem("stop-statuses", config)],
        [...statuses].map(([date, status]) => ({ planItemId: "stop-statuses", date, status })),
        REFERENCE_DATE,
    );
    const beforeByDate = new Map(store.getOccurrencesForPlanItem("stop-statuses").map((occurrence) => [occurrence.date, occurrence]));
    const result = store.stopPlanItemFromDate("stop-statuses", "2026-09-28");
    assert.equal(result.planItem.generationConfig.stoppedFromDate, "2026-09-28");
    assert.deepEqual(result.planItem.generationConfig.excludedDates, []);
    assert.deepEqual(result.removedOccurrences.map(({ date }) => date), ["2026-09-30", "2026-10-01"]);
    for (const date of ["2026-09-27", "2026-09-28", "2026-09-29", "2026-10-02", "2026-10-03", "2026-10-04", "2026-10-05"]) {
        assert.deepEqual(occurrenceFor(store, "stop-statuses", date), beforeByDate.get(date));
    }
    assert.equal(occurrenceFor(store, "stop-statuses", "2026-09-30"), undefined);
    assert.equal(occurrenceFor(store, "stop-statuses", "2026-10-01"), undefined);
    assert.deepEqual(store.materializePlanItem("stop-statuses", "2026-09-28", "2026-10-31"), []);
}

// Stop es válido sin occurrence exacta, desde futuro, y universal para todos los modos.
{
    const config = {
        mode: "manual_dates",
        entries: [
            { date: REFERENCE_DATE, startTime: "08:00", endTime: "09:00" },
            { date: "2026-09-30", startTime: "08:00", endTime: "09:00" },
        ],
    };
    const store = createPlannerStore(
        [planItem("stop-current", config)],
        [{ planItemId: "stop-current", date: "2026-09-30", status: "cancelled" }],
        REFERENCE_DATE,
    );
    const currentPending = occurrenceFor(store, "stop-current", REFERENCE_DATE);
    const futureCancelled = occurrenceFor(store, "stop-current", "2026-09-30");
    const currentCancelled = store.addOccurrenceForPlanItem("stop-current", {
        date: REFERENCE_DATE,
        startTime: "10:00",
        endTime: "11:00",
    });
    store.setOccurrenceStatus(currentCancelled.id, "cancelled");
    store.stopPlanItemFromDate("stop-current", REFERENCE_DATE);
    assert.equal(store.getOccurrenceById(currentPending.id), null);
    assert.equal(store.getOccurrenceById(futureCancelled.id), null);
    assert.equal(store.getOccurrenceById(currentCancelled.id).status, "cancelled");
}

{
    const config = {
        mode: "manual_dates",
        entries: [
            { date: "2026-09-28", startTime: "08:00", endTime: "09:00" },
            { date: "2026-09-30", startTime: "08:00", endTime: "09:00" },
        ],
    };
    const store = createPlannerStore(
        [planItem("stop-yesterday", config)],
        [{ planItemId: "stop-yesterday", date: "2026-09-28", status: "cancelled" }],
        REFERENCE_DATE,
    );
    const yesterdayCancelled = occurrenceFor(store, "stop-yesterday", "2026-09-28");
    store.stopPlanItemFromDate("stop-yesterday", "2026-09-28");
    assert.equal(store.getOccurrenceById(yesterdayCancelled.id).status, "cancelled");
    assert.equal(occurrenceFor(store, "stop-yesterday", "2026-09-30"), undefined);
}

const modeCases = [
    ["weekly", weeklyConfig()],
    ["interval", {
        mode: "interval_days", startDate: "2026-09-29", endDate: null, indefinite: true,
        intervalDays: 2, defaultStartTime: "08:00", defaultEndTime: "09:00",
    }],
    ["manual", {
        mode: "manual_dates",
        entries: [
            { date: "2026-09-29", startTime: "08:00", endTime: "09:00" },
            { date: "2026-10-03", startTime: "08:00", endTime: "09:00" },
        ],
    }],
    ["explicit", explicitDateConfig("2026-10-03")],
];
for (const [id, config] of modeCases) {
    const store = createPlannerStore([planItem(`mode-${id}`, config)], [], REFERENCE_DATE);
    const result = store.stopPlanItemFromDate(`mode-${id}`, "2026-10-01");
    assert.equal(result.planItem.generationConfig.stoppedFromDate, "2026-10-01", `${id} guarda frontera`);
    assert.ok(store.getOccurrencesForPlanItem(`mode-${id}`).every(({ date, status }) => date < "2026-10-01" || status !== "pending"));
    assert.deepEqual(store.materializePlanItem(`mode-${id}`, "2026-10-01", "2026-12-31"), [], `${id} no reaparece`);
}

// Monotonía: adelanta la frontera, nunca la mueve hacia adelante ni reanuda.
{
    const config = weeklyConfig({ stoppedFromDate: "2026-10-10" });
    const store = createPlannerStore([planItem("monotonic", config)], [], REFERENCE_DATE);
    store.stopPlanItemFromDate("monotonic", "2026-10-05");
    assert.equal(store.getPlanItemById("monotonic").generationConfig.stoppedFromDate, "2026-10-05");
    const before = store.getOccurrencesForPlanItem("monotonic");
    expectCode(() => store.stopPlanItemFromDate("monotonic", "2026-10-08"), "already_stopped");
    assert.equal(store.getPlanItemById("monotonic").generationConfig.stoppedFromDate, "2026-10-05");
    assert.deepEqual(store.getOccurrencesForPlanItem("monotonic"), before);
    expectCode(
        () => store.prepareOccurrenceAddition("monotonic", { date: "2026-10-08", startTime: "10:00", endTime: "11:00" }),
        "planning_stopped",
    );
}

// Los editores de recurrencia conservan los controles de eliminación ajenos al formulario.
{
    const config = weeklyConfig({
        excludedDates: ["2026-09-30"],
        stoppedFromDate: "2026-10-05",
    });
    const store = createPlannerStore([planItem("preserved-controls", config)], [], REFERENCE_DATE);
    store.applyGenerationConfigFromDate(
        "preserved-controls",
        REFERENCE_DATE,
        weeklyConfig({ defaultStartTime: "10:00", defaultEndTime: "11:00" }),
    );
    const updated = store.getPlanItemById("preserved-controls").generationConfig;
    assert.deepEqual(updated.excludedDates, ["2026-09-30"]);
    assert.equal(updated.stoppedFromDate, "2026-10-05");
    assert.equal(occurrenceFor(store, "preserved-controls", "2026-09-30"), undefined);
    assert.equal(occurrenceFor(store, "preserved-controls", "2026-10-05"), undefined);
}

// Fallos y ambigüedad no dejan mutaciones parciales.
{
    const store = createPlannerStore([planItem("ambiguous")], [], REFERENCE_DATE);
    const first = occurrenceFor(store, "ambiguous", REFERENCE_DATE);
    store.addOccurrenceForPlanItem("ambiguous", { date: REFERENCE_DATE, startTime: "10:00", endTime: "11:00" });
    const beforeItem = store.getPlanItemById("ambiguous");
    const beforeOccurrences = store.getOccurrencesForPlanItem("ambiguous");
    expectCode(() => store.deleteOccurrenceForDate(first.id), "ambiguous_occurrence");
    assert.deepEqual(store.getPlanItemById("ambiguous"), beforeItem);
    assert.deepEqual(store.getOccurrencesForPlanItem("ambiguous"), beforeOccurrences);

    expectCode(() => store.stopPlanItemFromDate("ambiguous", "2026-09-27"), "history_frozen");
    assert.deepEqual(store.getPlanItemById("ambiguous"), beforeItem);
    assert.deepEqual(store.getOccurrencesForPlanItem("ambiguous"), beforeOccurrences);
}

// El materializador aplica controles comunes sin modificar entries/configuración histórica.
for (const [id, config] of modeCases) {
    const controlled = {
        ...config,
        excludedDates: ["2026-10-03"],
        stoppedFromDate: "2026-10-05",
    };
    const drafts = materializeOccurrenceDrafts(planItem(`materializer-${id}`, controlled), "2026-09-29", "2026-10-31");
    assert.ok(drafts.every(({ date }) => date !== "2026-10-03" && date < "2026-10-05"));
}

// La procedencia de prioridad se preserva en historia retenida y la occurrence superior no se toca.
{
    const store = createPlannerStore(
        [planItem("lower", explicitDateConfig(REFERENCE_DATE, "08:00", "10:00"))],
        [],
        REFERENCE_DATE,
    );
    const lower = occurrenceFor(store, "lower", REFERENCE_DATE);
    store.setOccurrenceStatus(lower.id, "in_progress");
    const prepared = store.preparePlanItemCreation(
        planItem("higher", explicitDateConfig(REFERENCE_DATE, "09:00", "09:30"), "event"),
    );
    const higherResult = store.commitPreparedScheduleChange(prepared);
    const interrupted = store.getOccurrenceById(lower.id);
    const contextBefore = { ...interrupted.statusContext };
    store.stopPlanItemFromDate("lower", REFERENCE_DATE);
    assert.equal(store.getOccurrenceById(lower.id).status, "not_finished");
    assert.deepEqual(store.getOccurrenceById(lower.id).statusContext, contextBefore);
    assert.ok(store.getOccurrenceById(higherResult.occurrences[0].id));
}

{
    const futureDate = "2026-09-30";
    const store = createPlannerStore(
        [planItem("future-lower", explicitDateConfig(futureDate, "08:00", "10:00"))],
        [],
        REFERENCE_DATE,
    );
    const lower = occurrenceFor(store, "future-lower", futureDate);
    const prepared = store.preparePlanItemCreation(
        planItem("future-higher", explicitDateConfig(futureDate, "09:00", "09:30"), "event"),
    );
    const higherResult = store.commitPreparedScheduleChange(prepared);
    assert.equal(store.getOccurrenceById(lower.id).status, "cancelled");
    assert.equal(store.getOccurrenceById(lower.id).statusContext.reason, "priority_override");
    store.stopPlanItemFromDate("future-lower", REFERENCE_DATE);
    assert.equal(store.getOccurrenceById(lower.id), null, "la cancelación futura desplazada se retira completa");
    assert.ok(store.getOccurrenceById(higherResult.occurrences[0].id), "la occurrence superior permanece intacta");
}

console.log("deletion-management.test.mjs: todas las pruebas pasaron");
