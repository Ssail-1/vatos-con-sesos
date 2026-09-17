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
    const weekResult = store.applyWeeklyToWeek("scope-guard", "2026-09-14", config);
    assert.equal(weekResult.length, 2, "Apply week multi-slot conserva un estado idéntico");
    const futureResult = store.applyGenerationConfigFromDate("scope-guard", config);
    assert.deepEqual(futureResult.planItem.generationConfig, beforeItem.generationConfig, "Apply future conserva los GenerationSlots sin cambios");
    assert.equal(store.getOccurrenceById(first.id).status, "completed", "Apply future preserva la occurrence protegida");
    assert.equal(store.getOccurrencesForPlanItem("scope-guard").length, beforeOccurrences.length, "Apply future multi-slot no reduce N slots a uno");
}

{
    const original = weeklyConfig({ days: [1], startDate: "2026-09-14" });
    const multiCandidate = {
        ...cloneGenerationConfig(original),
        slots: [
            ...original.slots.map((slot) => ({ ...slot })),
            generationSlot({ isoWeekday: 1, startTime: "10:00", endTime: "11:00" }),
        ],
    };
    const store = createPlannerStore([activity("single-to-multi", original)], [], "2026-09-14");
    const before = store.getOccurrencesForPlanItem("single-to-multi")[0];
    const result = store.applyWeeklyToWeek("single-to-multi", "2026-09-14", multiCandidate);
    assert.equal(result.length, 2, "Apply week permite agregar un horario ad-hoc");
    assert.equal(store.getOccurrenceById(before.id).sourceGenerationSlotId, original.slots[0].id, "conserva la occurrence y procedencia existentes");
    assert.equal(result.filter(({ sourceGenerationSlotId }) => !sourceGenerationSlotId).length, 1, "el horario nuevo es ad-hoc");
    assert.deepEqual(store.getPlanItemById("single-to-multi").generationConfig, original, "el nuevo horario no crea GenerationSlot");
}

{
    const config = weeklyConfig({
        days: [1, 2, 3],
        startDate: "2026-09-14",
        extraSlots: [
            { isoWeekday: 1, startTime: "14:00", endTime: "17:00" },
            { isoWeekday: 2, startTime: "14:00", endTime: "17:00" },
            { isoWeekday: 3, startTime: "14:00", endTime: "17:00" },
        ],
    });
    const store = createPlannerStore([activity("week-batch", config)], [], "2026-09-14");
    const mondayAfternoon = store.getOccurrencesForDate("2026-09-14").find(({ startTime }) => startTime === "14:00");
    const tuesdayAfternoon = store.getOccurrencesForDate("2026-09-15").find(({ startTime }) => startTime === "14:00");
    const result = store.applyWeekOperations("week-batch", "2026-09-16", [
        { type: "update", occurrenceId: mondayAfternoon.id, date: "2026-09-14", startTime: "15:00", endTime: "18:00" },
        { type: "delete", occurrenceId: tuesdayAfternoon.id },
        { type: "create", date: "2026-09-16", startTime: "20:00", endTime: "21:00" },
    ]);
    assert.equal(result.weekStart, "2026-09-14");
    assert.equal(result.weekEnd, "2026-09-20");
    assert.equal(result.occurrences.length, 6);
    assert.equal(store.getOccurrenceById(mondayAfternoon.id).sourceGenerationSlotId, mondayAfternoon.sourceGenerationSlotId);
    assert.equal(store.getPlanItemById("week-batch").generationConfig.slots.find(({ id }) => id === mondayAfternoon.sourceGenerationSlotId).startTime, "14:00", "update no cambia el GenerationSlot");
    assert.deepEqual(
        store.getPlanItemById("week-batch").generationConfig.slots.find(({ id }) => id === tuesdayAfternoon.sourceGenerationSlotId).excludedDates,
        ["2026-09-15"],
        "delete persiste exclusión slot+fecha",
    );
    assert.equal(result.occurrences.find(({ startTime }) => startTime === "20:00").sourceGenerationSlotId, undefined, "create es ad-hoc");
}

{
    const config = weeklyConfig({
        days: [1],
        startDate: "2026-09-14",
        extraSlots: [{ isoWeekday: 1, startTime: "09:00", endTime: "10:00" }],
    });
    const store = createPlannerStore([activity("week-swap", config)], [], "2026-09-14");
    const [first, second] = store.getOccurrencesForDate("2026-09-14");
    store.applyWeekOperations("week-swap", "2026-09-14", [
        { type: "update", occurrenceId: first.id, date: first.date, startTime: "09:00", endTime: "10:00" },
        { type: "update", occurrenceId: second.id, date: second.date, startTime: "08:00", endTime: "09:00" },
    ]);
    assert.equal(store.getOccurrenceById(first.id).startTime, "09:00", "swap final válido no produce falso conflicto");
    const before = store.getOccurrencesForPlanItem("week-swap");
    assert.throws(
        () => store.applyWeekOperations("week-swap", "2026-09-14", [
            { type: "update", occurrenceId: first.id, date: first.date, startTime: "08:30", endTime: "09:30" },
        ]),
        (error) => error instanceof PlannerStoreError && error.code === "time_conflict",
    );
    assert.deepEqual(store.getOccurrencesForPlanItem("week-swap"), before, "conflicto final hace rollback local completo");
}

{
    const interval = intervalConfig({
        intervalDays: 1,
        startDate: "2026-09-14",
        times: [{ startTime: "08:00", endTime: "09:00" }, { startTime: "10:00", endTime: "11:00" }],
    });
    const store = createPlannerStore([activity("week-interval", interval)], [], "2026-09-14");
    const target = store.getOccurrencesForDate("2026-09-15")[1];
    store.applyWeekOperations("week-interval", "2026-09-15", [
        { type: "update", occurrenceId: target.id, date: target.date, startTime: "12:00", endTime: "13:00" },
    ]);
    assert.equal(store.getOccurrenceById(target.id).startTime, "12:00", "Apply Week local soporta interval_days");
    const intervalCandidate = cloneGenerationConfig(interval);
    intervalCandidate.slots[1].startTime = "14:00";
    intervalCandidate.slots[1].endTime = "15:00";
    store.applyWeeklyToWeek("week-interval", "2026-09-15", intervalCandidate);
    assert.equal(
        store.getOccurrenceById(target.id).startTime,
        "14:00",
        "el adaptador usado por la UI habilita Apply Week para interval_days",
    );
    assert.equal(
        store.getPlanItemById("week-interval").generationConfig.slots[1].startTime,
        "10:00",
        "la UI tampoco modifica el GenerationSlot interval_days",
    );

    const manual = createPlannerStore([activity("week-manual", manualConfig([{ date: "2026-09-15", startTime: "08:00", endTime: "09:00" }]))], [], "2026-09-14");
    assert.throws(
        () => manual.applyWeekOperations("week-manual", "2026-09-15", [{ type: "create", date: "2026-09-15", startTime: "10:00", endTime: "11:00" }]),
        (error) => error instanceof PlannerStoreError && error.code === "unsupported_mode",
    );
}

{
    const original = weeklyConfig({
        days: [1, 2],
        startDate: "2026-09-14",
        endDate: "2026-10-05",
        indefinite: false,
        perDayTimes: {
            "1": { startTime: "08:00", endTime: "11:00" },
            "2": { startTime: "14:00", endTime: "17:00" },
        },
    });
    const [mondaySlot, tuesdaySlot] = original.slots;
    const store = createPlannerStore([activity("future-weekly", original)], [], "2026-09-14");
    const history = store.getOccurrencesForPlanItem("future-weekly")
        .filter(({ date }) => date < "2026-09-21")
        .map(({ id, date, startTime, endTime, status }) => ({ id, date, startTime, endTime, status }));
    const override = store.getOccurrencesForDate("2026-09-22")
        .find(({ sourceGenerationSlotId }) => sourceGenerationSlotId === tuesdaySlot.id);
    store.updateOccurrence(override.id, { date: override.date, startTime: "15:00", endTime: "18:00" });
    const excluded = store.getOccurrencesForDate("2026-09-28")
        .find(({ sourceGenerationSlotId }) => sourceGenerationSlotId === mondaySlot.id);
    store.applyWeekOperations("future-weekly", "2026-09-28", [
        { type: "delete", occurrenceId: excluded.id },
    ]);
    store.applyWeekOperations("future-weekly", "2026-09-25", [
        { type: "create", date: "2026-09-25", startTime: "20:00", endTime: "21:00" },
    ]);
    const newSlot = generationSlot({ isoWeekday: 3, startTime: "20:00", endTime: "22:00" });
    const result = store.applyGenerationConfigFromDate("future-weekly", {
        mode: "weekly",
        startDate: "2026-09-21",
        endDate: original.endDate,
        indefinite: false,
        slots: [
            { ...mondaySlot, startTime: "09:00", endTime: "12:00" },
            newSlot,
        ],
    });
    assert.equal(result.planItem.generationConfig.startDate, "2026-09-21", "startDate es la frontera futura");
    assert.deepEqual(
        result.planItem.generationConfig.slots.map(({ id }) => id).sort(),
        [mondaySlot.id, newSlot.id].sort(),
        "conserva el UUID existente, agrega el nuevo y elimina el omitido",
    );
    assert.deepEqual(
        result.planItem.generationConfig.slots.find(({ id }) => id === mondaySlot.id).excludedDates,
        ["2026-09-28"],
        "preserva slot exclusions del slot sobreviviente",
    );
    const preservedOverride = store.getOccurrenceById(override.id);
    assert.equal(preservedOverride.startTime, "15:00", "preserva el override explícito futuro");
    assert.equal(preservedOverride.sourceGenerationSlotId, undefined, "el override del slot eliminado queda ad-hoc");
    assert.equal(
        store.getOccurrencesForDate("2026-09-23").find(({ planItemId }) => planItemId === "future-weekly").sourceGenerationSlotId,
        newSlot.id,
        "el slot nuevo materializa desde la frontera",
    );
    assert.equal(
        store.getOccurrencesForDate("2026-09-16").some(({ sourceGenerationSlotId }) => sourceGenerationSlotId === newSlot.id),
        false,
        "el slot nuevo nunca aparece antes de startDate",
    );
    assert.deepEqual(
        store.getOccurrencesForPlanItem("future-weekly")
            .filter(({ date }) => date < "2026-09-21")
            .map(({ id, date, startTime, endTime, status }) => ({ id, date, startTime, endTime, status })),
        history,
        "Apply Future conserva íntegros los datos históricos",
    );
}

{
    const original = intervalConfig({
        intervalDays: 2,
        startDate: "2026-09-14",
        endDate: "2026-09-30",
        indefinite: false,
        times: [
            { startTime: "08:00", endTime: "09:00" },
            { startTime: "18:00", endTime: "19:00" },
        ],
    });
    const [survivingSlot] = original.slots;
    const newSlot = generationSlot({ startTime: "20:00", endTime: "21:00" });
    const store = createPlannerStore([activity("future-interval", original)], [], "2026-09-14");
    const result = store.applyGenerationConfigFromDate("future-interval", {
        mode: "interval_days",
        startDate: "2026-09-21",
        endDate: original.endDate,
        indefinite: false,
        intervalDays: 3,
        slots: [
            { ...survivingSlot, startTime: "09:00", endTime: "10:00" },
            newSlot,
        ],
    });
    assert.deepEqual(
        [...new Set(result.occurrences.map(({ date }) => date))],
        ["2026-09-21", "2026-09-24", "2026-09-27", "2026-09-30"],
        "interval_days reinicia su fase desde el nuevo startDate",
    );
    assert.equal(result.occurrences.length, 8, "cada fecha de la nueva fase contiene ambos slots");
}

{
    const date = "2026-09-21";
    const lower = activity("future-dependent", explicitDate(date, "08:00", "10:00"));
    const store = createPlannerStore([lower], [], "2026-09-17");
    const sourceConfig = weeklyConfig({
        days: [1],
        startDate: date,
        endDate: date,
        indefinite: false,
        startTime: "09:00",
        endTime: "09:30",
    });
    const prepared = store.preparePlanItemCreation({
        name: "future-source",
        kind: "activity",
        activityType: "event",
        generationConfig: sourceConfig,
    });
    const created = store.commitPreparedScheduleChange(prepared);
    const sourceOccurrence = created.occurrences[0];
    const dependent = store.getOccurrencesForPlanItem("future-dependent")[0];
    assert.equal(dependent.statusContext.sourceOccurrenceId, sourceOccurrence.id);
    const beforeItems = store.getPlanItems();
    const beforeOccurrences = store.getOccurrences();

    for (const mutate of [
        () => store.updateOccurrence(sourceOccurrence.id, {
            date,
            startTime: "10:00",
            endTime: "10:30",
        }),
        () => store.deleteOccurrenceForDate(sourceOccurrence.id),
        () => store.applyWeekOperations(created.planItem.id, date, [{
            type: "update",
            occurrenceId: sourceOccurrence.id,
            date,
            startTime: "10:00",
            endTime: "10:30",
        }]),
    ]) {
        assert.throws(
            mutate,
            (error) => error instanceof PlannerStoreError && error.code === "status_context_locked",
        );
    }
    assert.throws(
        () => store.applyGenerationConfigFromDate(created.planItem.id, {
            ...sourceConfig,
            slots: sourceConfig.slots.map((slot) => ({
                ...slot,
                startTime: "10:00",
                endTime: "10:30",
            })),
        }),
        (error) => error instanceof PlannerStoreError && error.code === "status_context_locked",
    );
    assert.deepEqual(store.getPlanItems(), beforeItems, "Apply Future conserva el motor si statusContext bloquea la mutación");
    assert.deepEqual(store.getOccurrences(), beforeOccurrences, "Apply Future conserva occurrences si statusContext bloquea la mutación");
}

console.log("multi-slot-scheduling.test.mjs: todas las pruebas pasaron");
