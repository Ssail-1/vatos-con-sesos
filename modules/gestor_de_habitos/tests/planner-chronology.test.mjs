import assert from "node:assert/strict";
import test from "node:test";

import { buildPlannerRows, getPlannerRowSelection } from "../js/views/planner-matrix.js";

const DATE = "2026-09-25";
const plans = [
    { id: "a", name: "Estudiar", kind: "activity", activityType: "periodic" },
    { id: "b", name: "Comer", kind: "activity", activityType: "periodic" },
];
const occurrences = [
    { id: "a-occ", planItemId: "a", date: DATE, startTime: "13:00", endTime: "17:00",
        status: "pending", segments: [
            { id: "a1", startTime: "13:00", endTime: "14:00", status: "pending" },
            { id: "a2", startTime: "16:00", endTime: "17:00", status: "pending" },
        ] },
    { id: "b-occ", planItemId: "b", date: DATE, startTime: "14:30", endTime: "15:30",
        status: "pending", segments: [
            { id: "b1", startTime: "14:30", endTime: "15:30", status: "pending" },
        ] },
];

test("compact mantiene parent; expandido intercala A1, B, A2 sin duplicar identidad", () => {
    const compact = buildPlannerRows(plans, occurrences, DATE);
    assert.deepEqual(compact.map(({ occurrence }) => occurrence.id), ["a-occ", "b-occ"]);
    const expanded = buildPlannerRows(plans, occurrences, DATE, new Set(["a-occ"]));
    assert.deepEqual(expanded.map(({ rowType, segment, occurrence }) => (
        rowType === "segment" ? segment.id : rowType === "occurrence-control" ? "a-controls" : occurrence.id
    )), ["a-controls", "a1", "b-occ", "a2"]);
    assert.deepEqual(expanded.filter(({ rowType }) => rowType === "segment")
        .map(({ startTime, endTime }) => [startTime, endTime]), [
        ["13:00", "14:00"], ["16:00", "17:00"],
    ]);
    const control = expanded[0];
    assert.equal(control.startTime, null, "la fila de controles no aparenta ocupar la ventana general");
    assert.equal(control.occurrence.startTime, "13:00", "el parent conserva su ventana general");
    assert.equal(expanded[1].segmentCount, 2);
    assert.equal(expanded[3].segmentOrdinal, 2);
    assert.deepEqual(getPlannerRowSelection(expanded[3], {
        selectedOccurrenceId: "a-occ", selectedSegmentId: "a2",
    }), { groupSelected: true, rowSelected: true });
});

test("empates temporales se ordenan determinísticamente por identidad estable", () => {
    const extra = { id: "b-zero", planItemId: "b", date: DATE,
        startTime: "13:00", endTime: "14:00", status: "pending",
        segments: [{ id: "bz", startTime: "13:00", endTime: "14:00", status: "pending" }] };
    const expected = buildPlannerRows(plans, [...occurrences, extra], DATE, new Set(["a-occ"]))
        .map(({ rowType, segment, occurrence }) => segment?.id ?? `${rowType}:${occurrence.id}`);
    const shuffled = buildPlannerRows(plans, [extra, occurrences[1], occurrences[0]], DATE,
        new Set(["a-occ"]))
        .map(({ rowType, segment, occurrence }) => segment?.id ?? `${rowType}:${occurrence.id}`);
    assert.deepEqual(shuffled, expected);
});

test("split recibido tras GET participa sin lógica especial y conserva selección por ID", () => {
    const split = structuredClone(occurrences);
    split[0].segments[0].endTime = "13:30";
    split[0].segments.splice(1, 0, { id: "new-right", startTime: "14:00", endTime: "14:30", status: "pending" });
    const rows = buildPlannerRows(plans, split, DATE, new Set(["a-occ"]));
    assert.deepEqual(rows.filter(({ rowType }) => rowType === "segment").map(({ segment }) => segment.id),
        ["a1", "new-right", "a2"]);
    assert.equal(getPlannerRowSelection(rows.find(({ segment }) => segment?.id === "a1"), {
        selectedOccurrenceId: "a-occ", selectedSegmentId: "a1",
    }).rowSelected, true);
});
