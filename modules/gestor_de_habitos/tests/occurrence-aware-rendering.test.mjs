import assert from "node:assert/strict";
import {
    buildPlannerRows,
    getPlannerCellModel,
} from "../js/views/planner-matrix.js";

const selectedDate = "2026-09-22";
const item = (id, name = id, mode = "weekly") => ({
    id,
    name,
    kind: "activity",
    activityType: "periodic",
    generationConfig: { mode },
});
const occurrence = (
    id,
    planItemId,
    date,
    startTime,
    endTime,
    status = "pending",
    sourceGenerationSlotId = `${id}-slot`,
) => ({
    id,
    planItemId,
    date,
    startTime,
    endTime,
    status,
    sourceGenerationSlotId,
});

{
    const planItems = [
        item("wake", "Despertar"),
        item("a", "A"),
        item("uber", "Uber"),
        item("study", "Estudiar"),
        item("english", "Inglés"),
        item("absent", "Ausente"),
    ];
    const occurrences = [
        occurrence("uber-3", "uber", selectedDate, "20:00", "22:00", "completed"),
        occurrence("a-2", "a", selectedDate, "12:00", "13:00", "in_progress"),
        occurrence("wake-1", "wake", selectedDate, "04:25", "04:30"),
        occurrence("uber-1", "uber", selectedDate, "08:00", "11:00"),
        occurrence("study-1", "study", selectedDate, "10:00", "11:00"),
        occurrence("a-1", "a", selectedDate, "06:30", "07:30"),
        occurrence("english-1", "english", selectedDate, "16:00", "17:00"),
        occurrence("uber-2", "uber", selectedDate, "14:00", "17:00", "cancelled"),
        occurrence("uber-other-1", "uber", "2026-09-23", "08:00", "11:00"),
        occurrence("uber-other-2", "uber", "2026-09-23", "14:00", "17:00"),
        occurrence("uber-other-3", "uber", "2026-09-23", "20:00", "22:00"),
        occurrence("wake-other", "wake", "2026-09-23", "04:25", "04:30", "completed"),
        occurrence("absent-other", "absent", "2026-09-24", "09:00", "10:00"),
    ];
    const rows = buildPlannerRows(planItems, occurrences, selectedDate);

    assert.deepEqual(
        rows.map(({ startTime, planItem }) => [startTime ?? "—", planItem.name]),
        [
            ["04:25", "Despertar"],
            ["06:30", "A"],
            ["08:00", "Uber"],
            ["10:00", "Estudiar"],
            ["12:00", "A"],
            ["14:00", "Uber"],
            ["16:00", "Inglés"],
            ["20:00", "Uber"],
            ["—", "Ausente"],
        ],
        "las occurrence rows se intercalan globalmente y los summaries quedan al final",
    );
    assert.equal(rows[0].duration, "5min", "la duración procede del horario de la occurrence concreta");
    assert.equal(rows.at(-1).duration, null, "un PlanItem ausente usa Inicio/Duración vacíos");

    const aRows = rows.filter(({ planItem }) => planItem.id === "a");
    const uberRows = rows.filter(({ planItem }) => planItem.id === "uber");
    assert.deepEqual(aRows.map(({ occurrenceOrdinal }) => occurrenceOrdinal), [1, 2]);
    assert.deepEqual(uberRows.map(({ occurrenceOrdinal }) => occurrenceOrdinal), [1, 2, 3]);
    assert.equal(rows[0].occurrenceCount, 1, "una occurrence única no requiere ordinal visible");

    assert.deepEqual(
        getPlannerCellModel(uberRows[0], "2026-09-23", selectedDate, "2026-09-22"),
        {
            type: "aggregate",
            display: {
                count: 3,
                type: "uniform",
                status: "pending",
                temporalContext: null,
                symbol: "□",
                modifier: null,
                ariaLabel: "3 occurrences pendientes",
                interactive: false,
            },
        },
        "N occurrences no seleccionadas producen un badge derivado",
    );
    assert.equal(getPlannerCellModel(uberRows[1], "2026-09-23", selectedDate).type, "duplicate-summary");
    assert.equal(getPlannerCellModel(uberRows[2], "2026-09-23", selectedDate).type, "duplicate-summary");
    assert.equal(getPlannerCellModel(uberRows[0], "2026-09-25", selectedDate).type, "empty");
    assert.equal(getPlannerCellModel(rows[0], "2026-09-23", selectedDate).type, "occurrence");

    const firstUberSelectedCell = getPlannerCellModel(uberRows[0], selectedDate, selectedDate);
    assert.equal(firstUberSelectedCell.ordinal, 1);
    assert.equal(firstUberSelectedCell.total, 3);
    assert.equal(firstUberSelectedCell.occurrence.id, "uber-1");
    assert.equal(getPlannerCellModel(rows[0], selectedDate, selectedDate).ordinal, null);

    assert.deepEqual(
        uberRows.map(({ occurrence }) => [occurrence.id, occurrence.status]),
        [["uber-1", "pending"], ["uber-2", "cancelled"], ["uber-3", "completed"]],
        "cada fila conserva el status de su propia occurrence",
    );

    const absentRow = rows.at(-1);
    assert.equal(absentRow.rowType, "summary");
    assert.equal(getPlannerCellModel(absentRow, selectedDate, selectedDate).type, "empty");
    assert.equal(getPlannerCellModel(absentRow, "2026-09-24", selectedDate).occurrence.id, "absent-other");

    const twoOccurrences = occurrences.filter(({ id }) => id !== "uber-other-3");
    const oneOccurrence = occurrences.filter(({ id }) => !["uber-other-2", "uber-other-3"].includes(id));
    const twoRows = buildPlannerRows(planItems, twoOccurrences, selectedDate);
    const oneRows = buildPlannerRows(planItems, oneOccurrence, selectedDate);
    const twoUber = twoRows.find(({ planItem }) => planItem.id === "uber");
    const oneUber = oneRows.find(({ planItem }) => planItem.id === "uber");
    assert.equal(
        getPlannerCellModel(twoUber, "2026-09-23", selectedDate, "2026-09-22").display.count,
        2,
        "el aggregate recalcula 3 → 2 tras eliminar una occurrence",
    );
    assert.equal(
        getPlannerCellModel(oneUber, "2026-09-23", selectedDate, "2026-09-22").type,
        "occurrence",
        "con una occurrence vuelve al control individual sin superíndice",
    );
}

{
    const planItems = [
        item("manual", "Manual", "manual_dates"),
        item("weekly", "Weekly", "weekly"),
        item("interval", "Interval", "interval_days"),
        item("adhoc", "Ad hoc", "weekly"),
    ];
    const occurrences = [
        occurrence("manual-1", "manual", selectedDate, "08:00", "09:00"),
        occurrence("manual-2", "manual", selectedDate, "10:00", "11:00"),
        occurrence("weekly-1", "weekly", selectedDate, "12:00", "13:00"),
        occurrence("weekly-2", "weekly", selectedDate, "14:00", "15:00"),
        occurrence("interval-1", "interval", selectedDate, "16:00", "17:00"),
        occurrence("interval-2", "interval", selectedDate, "18:00", "19:00"),
        occurrence("adhoc-1", "adhoc", selectedDate, "20:00", "21:00", "pending", null),
    ];
    const rows = buildPlannerRows(planItems, occurrences, selectedDate);

    assert.deepEqual(
        rows.map(({ occurrence: current }) => current.id),
        ["manual-1", "manual-2", "weekly-1", "weekly-2", "interval-1", "interval-2", "adhoc-1"],
        "manual, weekly, interval y ad-hoc usan el mismo rendering occurrence-aware",
    );
    assert.equal(rows.at(-1).occurrence.sourceGenerationSlotId, null);
}

{
    const planItems = [item("uber", "Uber"), item("medicine", "Medicamento")];
    const occurrences = [
        occurrence("uber-a-1", "uber", "2026-09-20", "08:00", "09:00", "completed"),
        occurrence("uber-a-2", "uber", "2026-09-20", "10:00", "11:00", "completed"),
        occurrence("uber-a-3", "uber", "2026-09-20", "12:00", "13:00", "completed"),
        occurrence("uber-b-1", "uber", "2026-09-21", "08:00", "09:00"),
        occurrence("uber-b-2", "uber", "2026-09-21", "10:00", "11:00"),
        occurrence("uber-b-3", "uber", "2026-09-21", "12:00", "13:00"),
        occurrence("medicine-1", "medicine", "2026-09-21", "07:00", "07:05"),
        occurrence("medicine-2", "medicine", "2026-09-21", "19:00", "19:05"),
    ];
    const selectedA = buildPlannerRows(planItems, occurrences, "2026-09-20");
    const selectedB = buildPlannerRows(planItems, occurrences, "2026-09-21");
    const uberOnA = selectedA.filter(({ planItem }) => planItem.id === "uber");
    const uberOnB = selectedB.filter(({ planItem }) => planItem.id === "uber");
    const medicineOnA = selectedA.find(({ planItem }) => planItem.id === "medicine");

    assert.equal(uberOnA.length, 3, "el día seleccionado conserva una fila por occurrence");
    assert.equal(
        getPlannerCellModel(uberOnA[0], "2026-09-21", "2026-09-20", "2026-09-18").display.count,
        3,
        "la fecha no seleccionada se agrega",
    );
    assert.equal(uberOnB.length, 3, "cambiar selectedDate expande el grupo antes agregado");
    assert.equal(
        getPlannerCellModel(uberOnB[0], "2026-09-20", "2026-09-21", "2026-09-18").display.symbol,
        "✓",
        "la fecha anterior vuelve a aggregate derivado",
    );
    assert.equal(
        getPlannerCellModel(medicineOnA, "2026-09-21", "2026-09-20", "2026-09-18").display.count,
        2,
        "cada PlanItem calcula su grupo independientemente",
    );
}

console.log("occurrence-aware-rendering.test.mjs: todas las pruebas pasaron");
