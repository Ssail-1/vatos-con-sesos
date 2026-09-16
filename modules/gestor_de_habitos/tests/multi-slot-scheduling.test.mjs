import assert from "node:assert/strict";
import {
    cloneGenerationConfig,
    createGenerationSlotId,
    isGenerationSlotId,
    preserveSlotExcludedDates,
} from "../js/domain/generation-slots.js";
import { materializeOccurrenceDrafts, validateGenerationConfig } from "../js/scheduling/materializer.js";
import { createPlannerStore, PlannerStoreError } from "../js/state/planner-store.js";
import {
    addManualDateDraftEntry,
    createManualDateDraft,
    removeManualDateDraftEntry,
    reconstructWeeklySlotDraft,
    updateManualDateDraftEntry,
    validateFormValues,
} from "../js/views/plan-item-form.js";
import {
    explicitDate,
    generationSlot,
    intervalConfig,
    manualConfig,
    weeklyConfig,
} from "./helpers/generation-configs.mjs";

const activity = (id, generationConfig, activityType = "periodic") => ({
    id,
    name: id,
    kind: "activity",
    activityType,
    generationConfig,
});

{
    const config = weeklyConfig({ days: [1] });
    const drafts = materializeOccurrenceDrafts(activity("weekly-one", config), "2026-09-14", "2026-09-20");
    assert.equal(drafts.length, 1, "weekly materializa un único slot en su weekday");
    assert.equal(drafts[0].sourceGenerationSlotId, config.slots[0].id);
}

{
    const first = generationSlot({ isoWeekday: 1, startTime: "08:00", endTime: "09:00" });
    const excluded = generationSlot({ isoWeekday: 1, startTime: "10:00", endTime: "11:00" });
    excluded.excludedDates = ["2026-09-14"];
    const third = generationSlot({ isoWeekday: 1, startTime: "12:00", endTime: "13:00" });
    const config = weeklyConfig({
        days: [],
        startDate: "2026-09-14",
        endDate: "2026-09-14",
        indefinite: false,
        slots: [first, excluded, third],
    });
    const drafts = materializeOccurrenceDrafts(activity("slot-exclusion", config), "2026-09-14", "2026-09-14");
    assert.deepEqual(
        drafts.map(({ sourceGenerationSlotId }) => sourceGenerationSlotId),
        [first.id, third.id],
        "slot.excludedDates omite solamente el slot seleccionado",
    );
    const cloned = cloneGenerationConfig(config);
    cloned.slots[1].excludedDates.push("2026-09-21");
    assert.deepEqual(excluded.excludedDates, ["2026-09-14"], "el clone no comparte el array de exclusiones");
    const editedConfig = preserveSlotExcludedDates(
        config,
        { ...config, slots: config.slots.map(({ excludedDates: _excludedDates, ...slot }) => ({ ...slot })) },
    );
    assert.deepEqual(
        editedConfig.slots[1].excludedDates,
        ["2026-09-14"],
        "el editor conserva exclusiones ocultas por identidad de slot",
    );
}

{
    const slots = [];
    for (const isoWeekday of [1, 2, 3, 4, 5]) {
        slots.push(
            generationSlot({ isoWeekday, startTime: "08:00", endTime: "11:00" }),
            generationSlot({ isoWeekday, startTime: "14:00", endTime: "17:00" }),
            generationSlot({ isoWeekday, startTime: "20:00", endTime: "22:00" }),
        );
    }
    for (const isoWeekday of [6, 7]) {
        slots.push(generationSlot({ isoWeekday, startTime: "08:00", endTime: "21:00" }));
    }
    const config = {
        mode: "weekly",
        startDate: "2026-09-14",
        endDate: "2026-09-20",
        indefinite: false,
        slots,
    };
    const store = createPlannerStore([activity("uber", config)], [], "2026-09-14");
    const occurrences = store.getOccurrencesForPlanItem("uber");
    assert.equal(occurrences.length, 17, "un único PlanItem Uber genera todos sus horarios semanales");
    assert.equal(store.getOccurrencesForDate("2026-09-14").length, 3);
    assert.equal(store.getOccurrencesForDate("2026-09-19").length, 1);
    assert.ok(occurrences.every((occurrence) => (
        slots.some((slot) => slot.id === occurrence.sourceGenerationSlotId)
    )), "cada occurrence conserva el slot que la generó");
    assert.deepEqual(
        store.materializePlanItem("uber", "2026-09-14", "2026-09-20"),
        [],
        "rematerializar no duplica sourceGenerationSlotId + date",
    );
}

{
    const config = intervalConfig({
        intervalDays: 1,
        startDate: "2026-09-14",
        endDate: "2026-09-15",
        indefinite: false,
        times: [
            { startTime: "08:00", endTime: "08:05" },
            { startTime: "14:00", endTime: "14:05" },
            { startTime: "22:00", endTime: "22:05" },
        ],
    });
    const drafts = materializeOccurrenceDrafts(activity("medicine", config), "2026-09-14", "2026-09-15");
    assert.equal(drafts.length, 6, "cada slot interval_days se aplica en cada fecha válida");
    assert.equal(new Set(drafts.map(({ sourceGenerationSlotId }) => sourceGenerationSlotId)).size, 3);
}

{
    const config = weeklyConfig({
        days: [1],
        startDate: "2026-09-14",
        endDate: "2026-09-14",
        indefinite: false,
        startTime: "08:00",
        endTime: "09:00",
        extraSlots: [{ isoWeekday: 1, startTime: "14:00", endTime: "17:00" }],
    });
    const store = createPlannerStore([activity("local-patch", config)], [], "2026-09-14");
    const second = store.getOccurrencesForPlanItem("local-patch")[1];
    const sourceSlot = config.slots.find(({ id }) => id === second.sourceGenerationSlotId);
    store.updateOccurrence(second.id, {
        date: second.date,
        startTime: "15:00",
        endTime: "18:00",
    });
    assert.deepEqual(
        store.getPlanItemById("local-patch").generationConfig.slots.find(({ id }) => id === sourceSlot.id),
        sourceSlot,
        "editar horario de una occurrence recurrente no modifica su slot",
    );
    store.updateOccurrence(second.id, {
        date: "2026-09-15",
        startTime: "15:00",
        endTime: "18:00",
    });
    const movedSlot = store.getPlanItemById("local-patch").generationConfig.slots.find(({ id }) => id === sourceSlot.id);
    assert.deepEqual(movedSlot.excludedDates, ["2026-09-14"]);
    assert.deepEqual(store.materializePlanItem("local-patch", "2026-09-14", "2026-09-14"), []);
}

{
    const config = manualConfig([
        { date: "2026-09-15", startTime: "08:00", endTime: "11:00" },
        { date: "2026-09-15", startTime: "14:00", endTime: "17:00" },
    ]);
    const drafts = materializeOccurrenceDrafts(activity("manual", config), "2026-09-15", "2026-09-15");
    assert.equal(drafts.length, 2, "manual_dates admite varios horarios en la misma fecha");
    assert.deepEqual(drafts.map(({ sourceGenerationSlotId }) => sourceGenerationSlotId), config.entries.map(({ id }) => id));
}

{
    const config = manualConfig([
        { date: "2026-09-15", startTime: "08:00", endTime: "09:00" },
        { date: "2026-09-16", startTime: "14:00", endTime: "17:00" },
    ]);
    const store = createPlannerStore([activity("manual-local-patch", config)], [], "2026-09-15");
    const second = store.getOccurrencesForPlanItem("manual-local-patch")[1];
    store.updateOccurrence(second.id, {
        date: "2026-09-17",
        startTime: "15:00",
        endTime: "18:00",
    });
    const entry = store.getPlanItemById("manual-local-patch").generationConfig.entries.find(
        ({ id }) => id === second.sourceGenerationSlotId,
    );
    assert.deepEqual(
        entry,
        {
            id: second.sourceGenerationSlotId,
            date: "2026-09-17",
            startTime: "15:00",
            endTime: "18:00",
        },
        "editar manual_dates sincroniza entry y occurrence preservando IDs",
    );
}

{
    const adjacent = weeklyConfig({
        days: [1],
        startTime: "08:00",
        endTime: "09:00",
        extraSlots: [{ isoWeekday: 1, startTime: "09:00", endTime: "10:00" }],
    });
    assert.doesNotThrow(() => validateGenerationConfig(adjacent), "los intervalos contiguos son válidos");

    const overlappingWeekly = weeklyConfig({
        days: [1],
        startTime: "08:00",
        endTime: "10:00",
        extraSlots: [{ isoWeekday: 1, startTime: "09:00", endTime: "11:00" }],
    });
    const overlappingInterval = intervalConfig({ times: [
        { startTime: "08:00", endTime: "10:00" },
        { startTime: "09:00", endTime: "11:00" },
    ] });
    const overlappingManual = manualConfig([
        { date: "2026-09-15", startTime: "08:00", endTime: "10:00" },
        { date: "2026-09-15", startTime: "09:00", endTime: "11:00" },
    ]);
    for (const invalid of [overlappingWeekly, overlappingInterval, overlappingManual]) {
        assert.throws(() => validateGenerationConfig(invalid), /no pueden solaparse/);
    }
}

{
    const primary = generationSlot({ isoWeekday: 1, startTime: "08:00", endTime: "11:00" });
    const additional = generationSlot({ isoWeekday: 1, startTime: "14:00", endTime: "17:00" });
    const tuesday = generationSlot({ isoWeekday: 2, startTime: "09:00", endTime: "12:00" });
    const reconstructed = reconstructWeeklySlotDraft([additional, tuesday, primary]);
    assert.equal(reconstructed.weekdays[0].primarySlot.id, primary.id, "la reconstrucción elige el principal determinísticamente");
    assert.equal(reconstructed.weekdays[0].additionalSlots[0].id, additional.id);
    reconstructed.weekdays[0].additionalSlots[0].startTime = "15:00";
    assert.equal(reconstructed.weekdays[0].additionalSlots[0].id, additional.id, "editar conserva el UUID lógico");

    const manualDraft = createManualDateDraft([generationSlot({
        date: "2026-09-15",
        startTime: "14:00",
        endTime: "17:00",
    })]);
    const originalId = manualDraft[0].id;
    const edited = updateManualDateDraftEntry(manualDraft, 0, { startTime: "15:00", endTime: "18:00" });
    assert.equal(edited[0].id, originalId, "editar una entry manual conserva su UUID");
    const recreated = addManualDateDraftEntry(
        removeManualDateDraftEntry(edited, 0),
        { date: "2026-09-15", startTime: "14:00", endTime: "17:00" },
    );
    assert.notEqual(recreated[0].id, originalId, "eliminar y recrear produce UUID nuevo");
    assert.ok(isGenerationSlotId(recreated[0].id));
    assert.notEqual(createGenerationSlotId(), createGenerationSlotId(), "cada alta genera una identidad nueva");
}

{
    const explicit = explicitDate("2026-09-15", "08:00", "09:00");
    const [entry] = explicit.entries;
    const result = validateFormValues({
        name: "Una fecha",
        kind: "activity",
        itemType: "event",
        scheduleMode: "explicit_date",
        date: entry.date,
        startTime: entry.startTime,
        endTime: entry.endTime,
        explicitDateSlotId: entry.id,
    });
    assert.deepEqual(result.errors, []);
    assert.equal(result.generationConfig.mode, "manual_dates");
    assert.equal(result.generationConfig.entries[0].id, entry.id);
}

{
    const config = weeklyConfig({
        days: [1],
        extraSlots: [{ isoWeekday: 1, startTime: "10:00", endTime: "11:00" }],
        startDate: "2026-09-14",
        excludedDates: ["2026-09-14"],
        stoppedFromDate: "2026-09-21",
    });
    assert.deepEqual(
        materializeOccurrenceDrafts(activity("controlled", config), "2026-09-14", "2026-09-28"),
        [],
        "excludedDates y stoppedFromDate se aplican globalmente a todos los slots",
    );
}

{
    const blocker = activity("blocker", explicitDate("2026-09-14", "09:00", "09:30"));
    const store = createPlannerStore([blocker], [], "2026-09-14");
    const candidate = activity("candidate", weeklyConfig({
        days: [1],
        startDate: "2026-09-14",
        startTime: "08:00",
        endTime: "10:00",
        extraSlots: [{ isoWeekday: 1, startTime: "14:00", endTime: "15:00" }],
    }));
    assert.throws(
        () => store.preparePlanItemCreation(candidate),
        (error) => error instanceof PlannerStoreError && error.code === "priority_conflict",
        "cada occurrence candidata sigue pasando por conflictos y prioridad",
    );
    assert.equal(store.getPlanItemById("candidate"), null, "el rechazo multi-slot no deja creación parcial");
}

{
    const config = weeklyConfig({
        days: [1],
        startDate: "2026-09-14",
        extraSlots: [{ isoWeekday: 1, startTime: "10:00", endTime: "11:00" }],
    });
    const store = createPlannerStore([activity("scope-guard", config)], [], "2026-09-14");
    const first = store.getOccurrencesForDate("2026-09-14")[0];
    store.setOccurrenceStatus(first.id, "completed");
    const beforeItem = store.getPlanItemById("scope-guard");
    const beforeOccurrences = store.getOccurrencesForPlanItem("scope-guard");
    assert.throws(
        () => store.applyWeeklyToWeek("scope-guard", "2026-09-14", config),
        (error) => error instanceof PlannerStoreError && error.code === "ambiguous_week",
    );
    assert.throws(
        () => store.applyGenerationConfigFromDate("scope-guard", "2026-09-14", config),
        (error) => error instanceof PlannerStoreError && error.code === "ambiguous_future",
    );
    assert.deepEqual(store.getPlanItemById("scope-guard"), beforeItem, "el alcance aplazado no altera el config multi-slot");
    assert.deepEqual(store.getOccurrencesForPlanItem("scope-guard"), beforeOccurrences, "el alcance aplazado no reduce N slots a uno");
}

{
    const original = weeklyConfig({ days: [1], startDate: "2026-09-14" });
    const multiCandidate = weeklyConfig({
        days: [1],
        startDate: "2026-09-14",
        extraSlots: [{ isoWeekday: 1, startTime: "10:00", endTime: "11:00" }],
    });
    const store = createPlannerStore([activity("single-to-multi", original)], [], "2026-09-14");
    const before = store.getOccurrencesForPlanItem("single-to-multi");
    assert.throws(
        () => store.applyWeeklyToWeek("single-to-multi", "2026-09-14", multiCandidate),
        (error) => error instanceof PlannerStoreError && error.code === "ambiguous_week",
    );
    assert.deepEqual(store.getOccurrencesForPlanItem("single-to-multi"), before, "Apply week no crea IDs de occurrence duplicados");
}

console.log("multi-slot-scheduling.test.mjs: todas las pruebas pasaron");
