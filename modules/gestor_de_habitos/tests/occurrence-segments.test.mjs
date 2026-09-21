import assert from "node:assert/strict";
import test from "node:test";

import { PlannerApiError, validatePlannerStateResponse } from "../js/api/planner-api.js";
import { createPlannerStore, PlannerStoreError } from "../js/state/planner-store.js";
import {
    buildPlannerRows,
    getPlannerCellModel,
    getPlannerRowSelection,
} from "../js/views/planner-matrix.js";

const PLAN_ITEM_ID = "00000000-0000-4000-8000-000000000101";
const SLOT_ID = "00000000-0000-4000-8000-000000000102";
const SOURCE_ID = "00000000-0000-4000-8000-000000000201";
const MULTI_ID = "00000000-0000-4000-8000-000000000202";
const PRIORITY_ID = "00000000-0000-4000-8000-000000000203";
const SEGMENT_IDS = {
    source: "00000000-0000-4000-8000-000000000301",
    early: "00000000-0000-4000-8000-000000000302",
    late: "00000000-0000-4000-8000-000000000303",
    priority: "00000000-0000-4000-8000-000000000304",
};

function planItem() {
    return {
        id: PLAN_ITEM_ID,
        name: "Estudiar",
        kind: "activity",
        activityType: "event",
        generationConfig: {
            mode: "manual_dates",
            entries: [{
                id: SLOT_ID,
                date: "2026-09-20",
                startTime: "13:00",
                endTime: "17:00",
            }],
        },
    };
}

function persistedState() {
    return {
        planItems: [planItem()],
        occurrences: [
            {
                id: SOURCE_ID,
                planItemId: PLAN_ITEM_ID,
                date: "2026-09-20",
                startTime: "12:00",
                endTime: "12:30",
                status: "completed",
                segments: [{
                    id: SEGMENT_IDS.source,
                    startTime: "12:00",
                    endTime: "12:30",
                    status: "completed",
                }],
            },
            {
                id: MULTI_ID,
                planItemId: PLAN_ITEM_ID,
                date: "2026-09-20",
                startTime: "13:00",
                endTime: "17:00",
                status: "in_progress",
                sourceGenerationSlotId: SLOT_ID,
                segments: [
                    {
                        id: SEGMENT_IDS.late,
                        startTime: "14:30",
                        endTime: "16:00",
                        status: "pending",
                    },
                    {
                        id: SEGMENT_IDS.early,
                        startTime: "13:00",
                        endTime: "14:00",
                        status: "completed",
                    },
                ],
                conflictContext: {
                    reason: "user_forced_override",
                    sourceOccurrenceId: SOURCE_ID,
                },
                originReason: "conflict_insertion",
                lastConflictAction: "conflict_move",
            },
            {
                id: PRIORITY_ID,
                planItemId: PLAN_ITEM_ID,
                date: "2026-09-21",
                startTime: "09:00",
                endTime: "10:00",
                status: "cancelled",
                segments: [{
                    id: SEGMENT_IDS.priority,
                    startTime: "09:00",
                    endTime: "10:00",
                    status: "cancelled",
                }],
                conflictContext: {
                    reason: "priority_override",
                    sourceOccurrenceId: SOURCE_ID,
                },
                statusContext: {
                    reason: "priority_override",
                    sourceOccurrenceId: SOURCE_ID,
                },
            },
        ],
    };
}

function invalidResponse(mutator) {
    const state = structuredClone(persistedState());
    mutator(state);
    assert.throws(
        () => validatePlannerStateResponse(state),
        (error) => error instanceof PlannerApiError && error.code === "invalid_response",
    );
}

test("planner-state valida segments y metadata opcional del contrato schema 004", () => {
    const state = persistedState();
    assert.equal(validatePlannerStateResponse(state), state);

    invalidResponse((candidate) => { delete candidate.occurrences[0].segments; });
    invalidResponse((candidate) => { candidate.occurrences[0].segments = []; });
    invalidResponse((candidate) => {
        candidate.occurrences[1].segments[1].id = candidate.occurrences[1].segments[0].id;
    });
    invalidResponse((candidate) => {
        candidate.occurrences[1].segments[0].id = candidate.occurrences[0].segments[0].id;
    });
    invalidResponse((candidate) => { candidate.occurrences[0].segments[0].status = "unknown"; });
    invalidResponse((candidate) => { candidate.occurrences[0].segments[0].endTime = "12:00"; });
    invalidResponse((candidate) => { candidate.occurrences[1].segments[0].endTime = "17:30"; });
    invalidResponse((candidate) => { candidate.occurrences[1].conflictContext = null; });
    invalidResponse((candidate) => { candidate.occurrences[1].originReason = null; });
    invalidResponse((candidate) => { candidate.occurrences[1].lastConflictAction = "other"; });
    invalidResponse((candidate) => { candidate.occurrences[1].sourceGenerationSlotId = null; });
    invalidResponse((candidate) => {
        candidate.occurrences[1].conflictContext.sourceOccurrenceId = MULTI_ID;
    });
    invalidResponse((candidate) => {
        candidate.occurrences[1].conflictContext.sourceOccurrenceId = "missing";
    });
});

test("hydrate preserva IDs/metadata, ordena y clona profundamente los segments", () => {
    const state = persistedState();
    const store = createPlannerStore([], [], "2026-09-20");
    const hydrated = store.hydratePlannerState(state);
    const multi = hydrated.occurrences.find(({ id }) => id === MULTI_ID);
    const priority = hydrated.occurrences.find(({ id }) => id === PRIORITY_ID);

    assert.deepEqual(
        multi.segments.map(({ id }) => id),
        [SEGMENT_IDS.early, SEGMENT_IDS.late],
        "el ordinal visual no reemplaza los IDs persistidos",
    );
    assert.deepEqual(multi.conflictContext, {
        reason: "user_forced_override",
        sourceOccurrenceId: SOURCE_ID,
    });
    assert.equal(multi.originReason, "conflict_insertion");
    assert.equal(multi.lastConflictAction, "conflict_move");
    assert.equal(multi.sourceGenerationSlotId, SLOT_ID);
    assert.equal(priority.conflictContext.reason, "priority_override");
    assert.equal("statusContext" in priority, false, "el alias legacy no entra al estado frontend");

    state.occurrences[1].segments[0].startTime = "15:00";
    state.occurrences[1].conflictContext.reason = "priority_override";
    multi.segments[0].status = "cancelled";
    multi.conflictContext.reason = "priority_override";

    const stored = store.getOccurrenceById(MULTI_ID);
    assert.equal(stored.segments[0].startTime, "13:00");
    assert.equal(stored.segments[0].status, "completed");
    assert.equal(stored.conflictContext.reason, "user_forced_override");
});

test("hydrate rechaza segments mal tipados y metadata null sin reemplazarlos", () => {
    const store = createPlannerStore([], [], "2026-09-20");
    const malformedSegments = persistedState();
    malformedSegments.occurrences[0].segments = {};
    assert.throws(
        () => store.hydratePlannerState(malformedSegments),
        (error) => error instanceof PlannerStoreError
            && error.code === "invalid_occurrence_segments",
    );

    const nullSlot = persistedState();
    nullSlot.occurrences[0].sourceGenerationSlotId = null;
    assert.throws(
        () => store.hydratePlannerState(nullSlot),
        (error) => error instanceof PlannerStoreError
            && error.code === "invalid_occurrence_segments",
    );

    const nullContext = persistedState();
    nullContext.occurrences[1].conflictContext = null;
    assert.throws(
        () => store.hydratePlannerState(nullContext),
        (error) => error instanceof PlannerStoreError && error.code === "invalid_occurrence",
    );
});

test("render model mantiene parent, suma duración y expande rows temporales", () => {
    const store = createPlannerStore([], [], "2026-09-20");
    const state = store.hydratePlannerState(persistedState());
    const collapsed = buildPlannerRows(
        state.planItems,
        state.occurrences,
        "2026-09-20",
    );
    const multiParent = collapsed.find(({ occurrence }) => occurrence?.id === MULTI_ID);
    assert.equal(collapsed.filter(({ rowType }) => rowType === "segment").length, 0);
    assert.equal(multiParent.startTime, "13:00");
    assert.equal(multiParent.endTime, "17:00");
    assert.equal(multiParent.duration, "2h 30min");
    const singleParent = collapsed.find(({ occurrence }) => occurrence?.id === SOURCE_ID);
    assert.equal(singleParent.duration, "30min");
    assert.equal(singleParent.occurrence.segments.length, 1);

    const expanded = buildPlannerRows(
        state.planItems,
        state.occurrences,
        "2026-09-20",
        new Set([MULTI_ID]),
    );
    const segmentRows = expanded.filter(({ rowType }) => rowType === "segment");
    assert.deepEqual(
        segmentRows.map(({ segment, segmentOrdinal, duration }) => [
            segment.id,
            `Seg ${segmentOrdinal}`,
            duration,
        ]),
        [
            [SEGMENT_IDS.early, "Seg 1", "1h"],
            [SEGMENT_IDS.late, "Seg 2", "1h 30min"],
        ],
        "las etiquetas derivadas siguen el orden cronológico hidratado sin sustituir identidad",
    );
    assert.equal(
        getPlannerCellModel(segmentRows[0], "2026-09-21", "2026-09-20").type,
        "duplicate-summary",
        "los child rows no reemplazan el aggregate mensual",
    );
    assert.equal(
        getPlannerCellModel(collapsed[0], "2026-09-21", "2026-09-20", "2026-09-20").type,
        "occurrence",
        "una sola occurrence del otro día sigue siendo el modelo mensual normal",
    );
});

test("selection usa occurrenceId y segmentId estable y resalta el grupo", () => {
    const store = createPlannerStore([], [], "2026-09-20");
    const hydrated = store.hydratePlannerState(persistedState());
    const expanded = buildPlannerRows(
        hydrated.planItems,
        hydrated.occurrences,
        "2026-09-20",
        new Set([MULTI_ID]),
    );
    const parent = expanded.find(({ occurrence, rowType }) => (
        occurrence?.id === MULTI_ID && rowType === "occurrence"
    ));
    const segment = expanded.find(({ segment: candidate }) => candidate?.id === SEGMENT_IDS.late);

    assert.deepEqual(
        getPlannerRowSelection(parent, {
            selectedOccurrenceId: MULTI_ID,
            selectedSegmentId: null,
        }),
        { groupSelected: true, rowSelected: true },
    );
    assert.deepEqual(
        getPlannerRowSelection(parent, {
            selectedOccurrenceId: MULTI_ID,
            selectedSegmentId: SEGMENT_IDS.late,
        }),
        { groupSelected: true, rowSelected: false },
    );
    assert.deepEqual(
        getPlannerRowSelection(segment, {
            selectedOccurrenceId: MULTI_ID,
            selectedSegmentId: SEGMENT_IDS.late,
        }),
        { groupSelected: true, rowSelected: true },
    );
});

test("multi-segment bloquea escrituras legacy de status y horario", () => {
    const store = createPlannerStore([], [], "2026-09-20");
    store.hydratePlannerState(persistedState());
    for (const operation of [
        () => store.advanceOccurrenceStatus(MULTI_ID),
        () => store.setOccurrenceStatus(MULTI_ID, "completed"),
        () => store.updateOccurrence(MULTI_ID, {
            date: "2026-09-20",
            startTime: "13:00",
            endTime: "16:30",
        }),
    ]) {
        assert.throws(
            operation,
            (error) => error instanceof PlannerStoreError && error.code === "segment_write_required",
        );
    }
});
