import assert from "node:assert/strict";
import {
    addManualDateDraftEntry,
    createManualDateDraft,
    removeManualDateDraftEntry,
    updateManualDateDraftEntry,
    validateFormValues,
} from "../js/views/plan-item-form.js";
import { createPlannerStore, PlannerStoreError } from "../js/state/planner-store.js";
import { generationSlot, manualConfig } from "./helpers/generation-configs.mjs";

const entryA = generationSlot({ date: "2026-09-01", startTime: "10:00", endTime: "11:00" });
const entryB = generationSlot({ date: "2026-11-20", startTime: "16:00", endTime: "17:30" });
const formValues = (itemType, manualDateEntries) => ({
    name: `Manual ${itemType}`,
    kind: "activity",
    itemType,
    scheduleMode: "manual_dates",
    manualDateEntries,
    date: entryA.date,
    startTime: entryA.startTime,
    endTime: entryA.endTime,
});

{
    const reconstructed = createManualDateDraft([entryA, entryB]);
    assert.deepEqual(reconstructed, [entryA, entryB], "reconstruye todas las entries y sus horarios");
    assert.notEqual(reconstructed[0], entryA, "el draft no comparte objetos con la configuración guardada");

    const edited = updateManualDateDraftEntry(reconstructed, 1, { startTime: "18:00", endTime: "19:00" });
    assert.deepEqual(edited[0], entryA, "editar una entry no modifica las demás");
    assert.deepEqual(edited[1], { ...entryB, startTime: "18:00", endTime: "19:00" });

    const added = addManualDateDraftEntry(edited, { date: "2026-12-02", startTime: "07:00", endTime: "08:00" });
    assert.equal(added.length, 3, "agrega una entry al draft");
    const removed = removeManualDateDraftEntry(added, 1);
    assert.deepEqual(removed, [edited[0], added[2]], "quita únicamente la entry indicada del draft");
}

{
    const result = validateFormValues(formValues("periodic", [entryA, entryB]));
    assert.deepEqual(result.errors, []);
    assert.deepEqual(result.generationConfig, { mode: "manual_dates", entries: [entryA, entryB] });
}

{
    const sameDateEntries = [
        generationSlot({ date: "2026-09-01", startTime: "08:00", endTime: "09:00" }),
        generationSlot({ date: "2026-09-01", startTime: "20:00", endTime: "21:00" }),
    ];
    const result = validateFormValues(formValues("periodic", sameDateEntries));
    assert.deepEqual(result.errors, [], "el formulario permite la misma fecha con horarios distintos válidos");
    const store = createPlannerStore([], [], "2026-08-28");
    const prepared = store.preparePlanItemCreation({ ...result.planItem, generationConfig: result.generationConfig });
    store.commitPreparedScheduleChange(prepared);
    assert.deepEqual(
        store.getOccurrencesForDate("2026-09-01").map(({ startTime, endTime }) => ({ startTime, endTime })),
        sameDateEntries.map(({ startTime, endTime }) => ({ startTime, endTime })),
    );
}

for (const invalidEntries of [
    [],
    [{ ...entryA, date: "fecha-inválida" }],
    [{ ...entryA, startTime: "11:00", endTime: "10:00" }],
]) {
    assert.ok(validateFormValues(formValues("periodic", invalidEntries)).errors.length > 0, "una entry inválida impide guardar");
}

for (const itemType of ["event", "periodic"]) {
    const result = validateFormValues(formValues(itemType, [entryA, entryB]));
    const store = createPlannerStore([], [], "2026-08-28");
    const prepared = store.preparePlanItemCreation({ ...result.planItem, generationConfig: result.generationConfig });
    const created = store.commitPreparedScheduleChange(prepared);
    assert.deepEqual(
        created.occurrences.map(({ date, startTime, endTime }) => ({ date, startTime, endTime })),
        [entryA, entryB].map(({ date, startTime, endTime }) => ({ date, startTime, endTime })),
        `crea ${itemType} con horarios manuales independientes`,
    );
}

{
    const existingEvent = {
        id: "existing-event",
        name: "Evento existente",
        kind: "activity",
        activityType: "event",
        generationConfig: manualConfig([{ date: entryB.date, startTime: "16:30", endTime: "17:00" }]),
    };
    const store = createPlannerStore([existingEvent], [], "2026-08-28");
    const beforeItems = store.getPlanItems();
    const beforeOccurrences = store.getOccurrences();
    const candidate = validateFormValues(formValues("event", [entryA, entryB]));
    assert.throws(
        () => store.preparePlanItemCreation({ ...candidate.planItem, generationConfig: candidate.generationConfig }),
        (error) => error instanceof PlannerStoreError && error.code === "priority_conflict",
    );
    assert.deepEqual(store.getPlanItems(), beforeItems, "un conflicto no desplazable no crea parcialmente el Event");
    assert.deepEqual(store.getOccurrences(), beforeOccurrences, "la preparación fallida conserva todas las occurrences");
}

{
    const original = {
        id: "manual-future",
        name: "Manual future",
        kind: "activity",
        activityType: "periodic",
        generationConfig: { mode: "manual_dates", entries: [entryA, entryB] },
    };
    const store = createPlannerStore([original], [], entryA.date);
    const historical = store.getOccurrencesForDate(entryA.date)[0];
    store.setOccurrenceStatus(historical.id, "completed");
    const revisedEntryB = { ...entryB, startTime: "18:00", endTime: "19:00" };
    store.applyGenerationConfigFromDate(original.id, entryA.date, {
        mode: "manual_dates",
        entries: [{ ...entryA, startTime: "12:00", endTime: "13:00" }, revisedEntryB],
    });
    assert.equal(store.getOccurrenceById(historical.id).startTime, entryA.startTime, "Apply future conserva historial manual");
    assert.deepEqual(
        store.getOccurrencesForDate(entryB.date).map(({ date, startTime, endTime }) => ({ date, startTime, endTime })),
        [revisedEntryB].map(({ date, startTime, endTime }) => ({ date, startTime, endTime })),
        "Apply future genera cada entry con su propio horario",
    );
}

console.log("manual-dates-form.test.mjs: todas las pruebas pasaron");
