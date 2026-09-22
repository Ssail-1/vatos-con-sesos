import assert from "node:assert/strict";
import test from "node:test";

import { PlannerApiError, updateSegmentStatus, validatePlannerStateResponse } from "../js/api/planner-api.js";
import { getSelectableSegmentStatuses } from "../js/domain/occurrence-status.js";
import { TEMPORAL_ZONES } from "../js/domain/temporal-integrity.js";
import {
    createOccurrenceMutationCoordinator,
    getSegmentStatusMutationErrorMessage,
} from "../js/mutations/occurrence-mutation.js";
import { createPlannerStore, PlannerStoreError } from "../js/state/planner-store.js";
import { deriveAggregateOccurrenceDisplay } from "../js/views/aggregate-occurrence-display.js";
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
        occurrence?.id === MULTI_ID && rowType === "occurrence-control"
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
            (error) => error instanceof PlannerStoreError && error.code === "legacy_conflict_writer_retired",
        );
    }
});

test("PATCH status usa el ID persistido del child y solo envía status", async () => {
    const calls = [];
    const payload = {
        status: "ok",
        occurrenceId: MULTI_ID,
        segmentId: SEGMENT_IDS.late,
        segmentStatus: "completed",
        occurrenceStatus: "completed",
    };
    const result = await updateSegmentStatus(SEGMENT_IDS.late, "completed", {
        baseUrl: "http://localhost:5000",
        fetchImpl: async (...args) => {
            calls.push(args);
            return { ok: true, status: 200, json: async () => payload };
        },
    });
    assert.deepEqual(result, payload);
    assert.equal(calls[0][0], `http://localhost:5000/api/occurrence-segments/${SEGMENT_IDS.late}/status`);
    assert.equal(calls[0][1].method, "PATCH");
    assert.deepEqual(JSON.parse(calls[0][1].body), { status: "completed" });
});

test("PATCH conserva error controlado, blockers y no inventa resolución", async () => {
    for (const code of [
        "segment_status_conflict", "segment_not_ended", "segment_status_not_allowed",
        "history_frozen", "temporal_reconciliation_required", "concurrent_conflict",
        "database_unavailable", "persisted_state_invalid", "segment_not_found", "invalid_payload",
    ]) {
        const calls = [];
        await assert.rejects(
            updateSegmentStatus(SEGMENT_IDS.late, "pending", {
                fetchImpl: async (...args) => {
                    calls.push(args);
                    return {
                        ok: false,
                        status: code === "database_unavailable" ? 503 : 409,
                        json: async () => ({
                            status: "error", code, message: "Error controlado.",
                            blockers: [{ segmentId: SEGMENT_IDS.early, startTime: "13:00", endTime: "14:00", status: "completed" }],
                        }),
                    };
                },
            }),
            (error) => error instanceof PlannerApiError
                && error.code === code
                && error.details.blockers[0].segmentId === SEGMENT_IDS.early,
        );
        assert.equal(calls.length, 1);
        assert.ok(getSegmentStatusMutationErrorMessage({ code }).length > 0);
    }
});

test("opciones de status UI respetan futuro, hoy y ayer sin autoridad backend duplicada", () => {
    assert.deepEqual(getSelectableSegmentStatuses("2026-09-21", "2026-09-20", TEMPORAL_ZONES.FUTURE),
        ["pending", "cancelled"]);
    assert.deepEqual(getSelectableSegmentStatuses("2026-09-20", "2026-09-20", TEMPORAL_ZONES.EDITABLE),
        ["pending", "in_progress", "completed", "not_completed", "not_finished", "cancelled"]);
    assert.deepEqual(getSelectableSegmentStatuses("2026-09-19", "2026-09-20", TEMPORAL_ZONES.EDITABLE),
        ["completed", "not_completed", "not_finished", "cancelled"]);
    assert.deepEqual(getSelectableSegmentStatuses("2026-09-18", "2026-09-20", TEMPORAL_ZONES.FROZEN), []);
});

test("PATCH child confirmado → GET → hydrate actualiza parent solo desde respuesta autoritativa", async () => {
    const store = createPlannerStore([], [], "2026-09-20");
    store.hydratePlannerState(persistedState());
    const events = [];
    const serverState = persistedState();
    const multi = serverState.occurrences.find(({ id }) => id === MULTI_ID);
    multi.segments.forEach((segment) => { segment.status = "completed"; });
    multi.status = "completed";
    let releasePatch;
    const patchPending = new Promise((resolve) => { releasePatch = resolve; });
    const coordinator = createOccurrenceMutationCoordinator({
        mutateOccurrence: async (id, status) => {
            events.push(["patch", id, status]);
            await patchPending;
            return { segmentId: id, segmentStatus: status };
        },
        loadPlannerState: async () => { events.push(["get"]); return serverState; },
        hydratePlannerState: (state) => { events.push(["hydrate"]); return store.hydratePlannerState(state); },
    });
    const first = coordinator.submit(SEGMENT_IDS.late, "completed");
    assert.equal(coordinator.submit(SEGMENT_IDS.late, "completed"), first);
    assert.equal(store.getOccurrenceById(MULTI_ID).status, "in_progress");
    assert.equal(store.getOccurrenceById(MULTI_ID).segments.find(({ id }) => id === SEGMENT_IDS.late).status, "pending");
    releasePatch();
    assert.equal((await first).status, "synced");
    assert.deepEqual(events.map(([name]) => name), ["patch", "get", "hydrate"]);
    assert.deepEqual(events[0], ["patch", SEGMENT_IDS.late, "completed"]);
    assert.equal(store.getOccurrenceById(MULTI_ID).status, "completed");
    assert.equal(store.getOccurrenceById(MULTI_ID).segments.find(({ id }) => id === SEGMENT_IDS.late).status, "completed");
    assert.equal(store.getOccurrenceById(MULTI_ID).originReason, "conflict_insertion");
    assert.equal(store.getOccurrenceById(MULTI_ID).sourceGenerationSlotId, SLOT_ID);
});

test("PATCH confirmado + GET fallido reintenta únicamente GET", async () => {
    let patchCount = 0;
    let getCount = 0;
    const coordinator = createOccurrenceMutationCoordinator({
        mutateOccurrence: async () => { patchCount += 1; return { status: "ok" }; },
        loadPlannerState: async () => {
            getCount += 1;
            if (getCount === 1) throw new Error("GET unavailable");
            return persistedState();
        },
        hydratePlannerState: (state) => state,
    });
    assert.equal((await coordinator.submit(SEGMENT_IDS.source, "cancelled")).status, "saved_refresh_error");
    assert.equal((await coordinator.submit(SEGMENT_IDS.source, "cancelled")).status, "synced");
    assert.equal(patchCount, 1);
    assert.equal(getCount, 2);
});

test("single-segment PATCH usa su ID y solo GET actualiza su parent aggregate", async () => {
    const store = createPlannerStore([], [], "2026-09-20");
    store.hydratePlannerState(persistedState());
    const serverState = persistedState();
    const single = serverState.occurrences.find(({ id }) => id === SOURCE_ID);
    single.segments[0].status = "cancelled";
    single.status = "cancelled";
    const calls = [];
    const coordinator = createOccurrenceMutationCoordinator({
        mutateOccurrence: async (...args) => {
            calls.push(["patch", ...args]);
            assert.equal(store.getOccurrenceById(SOURCE_ID).status, "completed");
            return { status: "ok" };
        },
        loadPlannerState: async () => { calls.push(["get"]); return serverState; },
        hydratePlannerState: (state) => {
            calls.push(["hydrate"]);
            return store.hydratePlannerState(state);
        },
    });
    assert.equal((await coordinator.submit(SEGMENT_IDS.source, "cancelled")).status, "synced");
    assert.deepEqual(calls, [["patch", SEGMENT_IDS.source, "cancelled"], ["get"], ["hydrate"]]);
    assert.equal(store.getOccurrenceById(SOURCE_ID).segments[0].status, "cancelled");
    assert.equal(store.getOccurrenceById(SOURCE_ID).status, "cancelled");
});

test("409 de status no muta el planner local ni dispara GET o resolución de conflicto", async () => {
    for (const code of ["segment_status_conflict", "concurrent_conflict", "temporal_reconciliation_required"]) {
        const store = createPlannerStore([], [], "2026-09-20");
        store.hydratePlannerState(persistedState());
        const calls = [];
        const coordinator = createOccurrenceMutationCoordinator({
            mutateOccurrence: async () => {
                calls.push("patch");
                throw new PlannerApiError(code, "Conflicto controlado.", {
                    blockers: [{ segmentId: SEGMENT_IDS.early }],
                });
            },
            loadPlannerState: async () => { calls.push("get"); return persistedState(); },
            hydratePlannerState: () => { calls.push("hydrate"); },
        });
        const outcome = await coordinator.submit(SEGMENT_IDS.late, "completed");
        assert.equal(outcome.status, "mutation_error");
        assert.equal(outcome.error.code, code);
        assert.deepEqual(calls, ["patch"]);
        assert.equal(store.getOccurrenceById(MULTI_ID).status, "in_progress");
        assert.equal(store.getOccurrenceById(MULTI_ID).segments.find(({ id }) => id === SEGMENT_IDS.late).status, "pending");
    }
});

test("monthly aggregate se deriva de los parents recibidos después de hydrate", () => {
    const store = createPlannerStore([], [], "2026-09-20");
    store.hydratePlannerState(persistedState());
    const display = () => deriveAggregateOccurrenceDisplay(
        store.getOccurrencesForDate("2026-09-20"), "2026-09-20", "2026-09-20",
    );
    assert.equal(display().type, "today-mixed");
    const refreshed = persistedState();
    const multi = refreshed.occurrences.find(({ id }) => id === MULTI_ID);
    multi.status = "completed";
    multi.segments.forEach((segment) => { segment.status = "completed"; });
    store.hydratePlannerState(refreshed);
    assert.equal(display().type, "uniform");
    assert.equal(display().status, "completed");
    assert.equal(display().count, 2);
});
