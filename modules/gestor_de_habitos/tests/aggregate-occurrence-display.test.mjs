import assert from "node:assert/strict";
import test from "node:test";

import { deriveAggregateOccurrenceDisplay } from "../js/views/aggregate-occurrence-display.js";

const CURRENT_DAY = "2026-09-18";
const occurrences = (...statuses) => statuses.map((status, index) => ({
    id: `occurrence-${index}`,
    planItemId: "plan-item",
    date: "2026-09-20",
    startTime: `${String(8 + index).padStart(2, "0")}:00`,
    endTime: `${String(9 + index).padStart(2, "0")}:00`,
    status,
    sourceGenerationSlotId: index === statuses.length - 1 ? null : `slot-${index}`,
}));

test("N=0 y N=1 no producen aggregate badge", () => {
    assert.equal(deriveAggregateOccurrenceDisplay([], "2026-09-20", CURRENT_DAY), null);
    assert.equal(
        deriveAggregateOccurrenceDisplay(occurrences("pending"), "2026-09-20", CURRENT_DAY),
        null,
    );
});

test("statuses uniformes conservan su presentación y prioridad temporal", () => {
    const cases = [
        ["pending", "2026-09-20", "□", null, "3 occurrences pendientes"],
        ["in_progress", "2026-09-20", "◷", null, "3 occurrences en progreso"],
        ["completed", "2026-09-15", "✓", null, "3 occurrences completadas"],
        ["not_completed", "2026-09-15", "✕", null, "3 occurrences no realizadas"],
        ["not_finished", "2026-09-15", "◷", "!", "3 occurrences no terminadas"],
        ["cancelled", "2026-09-17", "⚠", null, "3 occurrences canceladas"],
    ];
    cases.forEach(([status, date, symbol, modifier, ariaLabel]) => {
        const result = deriveAggregateOccurrenceDisplay(
            occurrences(status, status, status),
            date,
            CURRENT_DAY,
        );
        assert.equal(result.type, "uniform");
        assert.equal(result.status, status);
        assert.equal(result.symbol, symbol);
        assert.equal(result.modifier, modifier);
        assert.equal(result.ariaLabel, ariaLabel);
        assert.equal(result.interactive, false);
    });
});

test("pending de hoy es temporal muted y se distingue de in_progress real", () => {
    const pendingToday = deriveAggregateOccurrenceDisplay(
        occurrences("pending", "pending", "pending"),
        CURRENT_DAY,
        CURRENT_DAY,
    );
    const inProgressToday = deriveAggregateOccurrenceDisplay(
        occurrences("in_progress", "in_progress", "in_progress"),
        CURRENT_DAY,
        CURRENT_DAY,
    );
    assert.deepEqual(
        [pendingToday.symbol, pendingToday.type, pendingToday.status, pendingToday.ariaLabel],
        ["◷", "today-pending", null, "3 occurrences programadas para hoy"],
    );
    assert.deepEqual(
        [inProgressToday.symbol, inProgressToday.type, inProgressToday.status, inProgressToday.ariaLabel],
        ["◷", "uniform", "in_progress", "3 occurrences en progreso"],
    );
});

test("grupos mixtos usan el contexto temporal sin majority voting", () => {
    const group = occurrences("completed", "completed", "cancelled");
    const cases = [
        ["2026-09-20", "future-mixed", "◐", null, "3 occurrences con estados diferentes"],
        [CURRENT_DAY, "today-mixed", "◷", null, "3 occurrences para hoy con estados diferentes"],
        ["2026-09-17", "editable-past-mixed", "⚠", "!", "3 occurrences con estados diferentes; fecha todavía editable"],
        ["2026-09-15", "frozen-mixed", "!", null, "3 occurrences con estados diferentes; historial congelado"],
    ];
    cases.forEach(([date, type, symbol, modifier, ariaLabel]) => {
        const result = deriveAggregateOccurrenceDisplay(group, date, CURRENT_DAY);
        assert.deepEqual(
            [result.type, result.symbol, result.modifier, result.ariaLabel],
            [type, symbol, modifier, ariaLabel],
        );
        assert.equal(result.status, null);
    });
});

test("frozen uniforme significativo prevalece y frozen pendiente usa fallback informativo", () => {
    const completed = deriveAggregateOccurrenceDisplay(
        occurrences("completed", "completed", "completed"),
        "2026-09-15",
        CURRENT_DAY,
    );
    const pending = deriveAggregateOccurrenceDisplay(
        occurrences("pending", "pending", "pending"),
        "2026-09-15",
        CURRENT_DAY,
    );
    assert.deepEqual([completed.type, completed.symbol], ["uniform", "✓"]);
    assert.deepEqual(
        [pending.type, pending.symbol, pending.ariaLabel],
        ["frozen-inconsistent", "!", "3 occurrences con estado inconsistente; historial congelado"],
    );
});

test("count usa el tamaño real, admite más de nueve e incluye ad-hoc sin distinción", () => {
    const group = occurrences(...Array(12).fill("completed"));
    assert.equal(group.at(-1).sourceGenerationSlotId, null);
    const result = deriveAggregateOccurrenceDisplay(group, "2026-09-20", CURRENT_DAY);
    assert.equal(result.count, 12);
    assert.equal(result.ariaLabel, "12 occurrences completadas");
});

test("un cambio local de status recalcula uniforme → mixto sin mutar el grupo previo", () => {
    const pendingGroup = occurrences("pending", "pending", "pending");
    const pendingDisplay = deriveAggregateOccurrenceDisplay(
        pendingGroup,
        "2026-09-20",
        CURRENT_DAY,
    );
    const locallyChangedGroup = pendingGroup.map((occurrence, index) => (
        index === 0 ? { ...occurrence, status: "completed" } : occurrence
    ));
    const mixedDisplay = deriveAggregateOccurrenceDisplay(
        locallyChangedGroup,
        "2026-09-20",
        CURRENT_DAY,
    );
    assert.equal(pendingDisplay.type, "uniform");
    assert.equal(mixedDisplay.type, "future-mixed");
    assert.deepEqual(pendingGroup.map(({ status }) => status), ["pending", "pending", "pending"]);
});
