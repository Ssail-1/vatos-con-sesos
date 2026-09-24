import assert from "node:assert/strict";
import { materializeOccurrenceDrafts } from "../js/scheduling/materializer.js";
import { createPlannerStore, PlannerStoreError } from "../js/state/planner-store.js";
import { explicitDate, intervalConfig, manualConfig, weeklyConfig } from "./helpers/generation-configs.mjs";

const REFERENCE_DATE = "2026-09-29";
function planItem(id, generationConfig = weeklyConfig({ startDate: "2026-09-20", days: [1, 2, 3, 4, 5, 6, 7] }), activityType = "periodic") {
    return { id, name: id, kind: "activity", activityType, generationConfig };
}

function explicitDateConfig(date, startTime = "08:00", endTime = "09:00", controls = {}) {
    return explicitDate(date, startTime, endTime, controls);
}

function expectCode(action, code) {
    assert.throws(action, (error) => error instanceof PlannerStoreError && error.code === code);
}

function occurrenceFor(store, planItemId, date) {
    return store.getOccurrencesForPlanItem(planItemId).find((occurrence) => occurrence.date === date);
}

function sourceSlotFor(store, planItemId, occurrence) {
    return store.getPlanItemById(planItemId).generationConfig.slots.find(
        ({ id }) => id === occurrence.sourceGenerationSlotId,
    );
}

// Delete individual: presente, ayer, frozen y matriz completa de estados.
for (const date of [REFERENCE_DATE, "2026-09-28"]) {
    const store = createPlannerStore([planItem(`deletable-${date}`)], [], REFERENCE_DATE);
    const occurrence = occurrenceFor(store, `deletable-${date}`, date);
    const result = store.deleteOccurrenceForDate(occurrence.id);
    assert.equal(result.deletedOccurrence.id, occurrence.id);
    assert.equal(store.getOccurrenceById(occurrence.id), null);
    assert.deepEqual(sourceSlotFor(store, `deletable-${date}`, occurrence).excludedDates, [date]);
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
    assert.deepEqual(sourceSlotFor(store, "future-cancelled", occurrence).excludedDates, ["2026-09-30"]);
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
    assert.deepEqual(sourceSlotFor(store, "restorable", deleted).excludedDates, []);
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
    assert.deepEqual(sourceSlotFor(store, "restore-conflict", deleted).excludedDates, [REFERENCE_DATE]);
    expectCode(
        () => store.prepareOccurrenceAddition("restore-conflict", {
            date: REFERENCE_DATE,
            startTime: "09:00",
            endTime: "08:00",
        }),
        "invalid_occurrence",
    );
    assert.deepEqual(sourceSlotFor(store, "restore-conflict", deleted).excludedDates, [REFERENCE_DATE]);
}

// La reconciliación limpia exclusiones frozen sin reconstruir historia.
{
    const config = weeklyConfig({ excludedDates: ["2026-09-27", "2026-09-28"] });
    config.slots[0].excludedDates = ["2026-09-27", "2026-09-28"];
    const store = createPlannerStore([planItem("cleanup", config)], [], REFERENCE_DATE);
    assert.deepEqual(store.getPlanItemById("cleanup").generationConfig.excludedDates, ["2026-09-28"]);
    assert.deepEqual(store.getPlanItemById("cleanup").generationConfig.slots[0].excludedDates, ["2026-09-28"]);
    assert.deepEqual(store.reconcileTemporalState(), []);
    assert.deepEqual(store.getPlanItemById("cleanup").generationConfig.excludedDates, ["2026-09-28"]);
    assert.deepEqual(store.materializePlanItem("cleanup", "2026-09-27", "2026-09-27"), []);
    assert.equal(occurrenceFor(store, "cleanup", "2026-09-27"), undefined);
}

const modeCases = [
    ["weekly", weeklyConfig()],
    ["interval", intervalConfig({ startDate: "2026-09-29", intervalDays: 2 })],
    ["manual", manualConfig([
            { date: "2026-09-29", startTime: "08:00", endTime: "09:00" },
            { date: "2026-10-03", startTime: "08:00", endTime: "09:00" },
    ])],
    ["explicit", explicitDateConfig("2026-10-03")],
];

// La terminación de planificación es exclusivamente persistente. El store no
// conserva el writer local anterior, que podía divergir del estado autoritativo.
{
    const store = createPlannerStore([planItem("persistent-stop-only")], [], REFERENCE_DATE);
    assert.equal("stopPlanItemFromDate" in store, false);
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
        weeklyConfig({ startDate: REFERENCE_DATE, startTime: "10:00", endTime: "11:00" }),
    );
    const updated = store.getPlanItemById("preserved-controls").generationConfig;
    assert.deepEqual(updated.excludedDates, ["2026-09-30"]);
    assert.equal(updated.stoppedFromDate, "2026-10-05");
    assert.equal(occurrenceFor(store, "preserved-controls", "2026-09-30"), undefined);
    assert.equal(occurrenceFor(store, "preserved-controls", "2026-10-05"), undefined);
}

// Un ID exacto elimina solo su occurrence aunque el PlanItem tenga otra el mismo día.
{
    const store = createPlannerStore([planItem("ambiguous")], [], REFERENCE_DATE);
    const first = occurrenceFor(store, "ambiguous", REFERENCE_DATE);
    const adHoc = store.addOccurrenceForPlanItem("ambiguous", { date: REFERENCE_DATE, startTime: "10:00", endTime: "11:00" });
    const exactOptions = store.getDeletionOptions("ambiguous", REFERENCE_DATE, adHoc.id);
    assert.equal(exactOptions.individual.allowed, true);
    assert.equal(exactOptions.individual.occurrence.id, adHoc.id, "la UI resuelve la occurrence por ID, no por fecha");
    store.deleteOccurrenceForDate(first.id);
    assert.equal(store.getOccurrenceById(first.id), null);
    assert.ok(store.getOccurrenceById(adHoc.id));
    assert.deepEqual(sourceSlotFor(store, "ambiguous", first).excludedDates, [REFERENCE_DATE]);

}

// En multi-slot recurrente la exclusión pertenece solo al slot eliminado.
{
    const config = weeklyConfig({
        days: [2],
        startDate: REFERENCE_DATE,
        extraSlots: [{ isoWeekday: 2, startTime: "10:00", endTime: "11:00" }],
    });
    const store = createPlannerStore([planItem("recurring-multi-delete", config)], [], REFERENCE_DATE);
    const [first, second] = store.getOccurrencesForDate(REFERENCE_DATE);
    store.deleteOccurrenceForDate(second.id);
    assert.ok(store.getOccurrenceById(first.id));
    assert.equal(store.getOccurrenceById(second.id), null);
    assert.equal(sourceSlotFor(store, "recurring-multi-delete", first).excludedDates, undefined);
    assert.deepEqual(sourceSlotFor(store, "recurring-multi-delete", second).excludedDates, [REFERENCE_DATE]);
    assert.deepEqual(store.materializePlanItem("recurring-multi-delete", REFERENCE_DATE, REFERENCE_DATE), []);
}

// manual_dates elimina solamente la entry elegida y protege la última.
{
    const config = manualConfig([
        { date: REFERENCE_DATE, startTime: "08:00", endTime: "09:00" },
        { date: REFERENCE_DATE, startTime: "10:00", endTime: "11:00" },
    ]);
    const store = createPlannerStore([planItem("manual-delete", config)], [], REFERENCE_DATE);
    const second = store.getOccurrencesForPlanItem("manual-delete")[1];
    store.deleteOccurrenceForDate(second.id);
    assert.equal(store.getOccurrenceById(second.id), null);
    assert.equal(store.getPlanItemById("manual-delete").generationConfig.entries.length, 1);
    const last = store.getOccurrencesForPlanItem("manual-delete")[0];
    expectCode(() => store.deleteOccurrenceForDate(last.id), "last_manual_entry");
    assert.ok(store.getOccurrenceById(last.id));
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

console.log("deletion-management.test.mjs: todas las pruebas pasaron");
