import assert from "node:assert/strict";
import test from "node:test";

import {
    addDraftSegment,
    buildOccurrenceStructurePayload,
    canTranslateOccurrenceDraft,
    createOccurrenceStructureDraft,
    draftStructuralDuration,
    removeDraftSegment,
    validateOccurrenceStructureDraft,
} from "../js/domain/occurrence-structure-draft.js";
import {
    PlannerApiError,
    replaceOccurrenceStructure,
    resetOccurrenceSegmentation,
    translateOccurrence,
} from "../js/api/planner-api.js";
import { createOccurrenceStructureMutationCoordinator } from "../js/mutations/occurrence-structure-mutation.js";

const OCCURRENCE_ID = "00000000-0000-4000-8000-000000000101";
const FIRST_ID = "00000000-0000-4000-8000-000000000201";
const SECOND_ID = "00000000-0000-4000-8000-000000000202";
const REAL_NEW_ID = "00000000-0000-4000-8000-000000000203";

function occurrence() {
    return {
        id: OCCURRENCE_ID, date: "2026-09-20", startTime: "13:00", endTime: "17:00",
        status: "in_progress",
        segments: [
            { id: FIRST_ID, startTime: "13:00", endTime: "14:00", status: "completed" },
            { id: SECOND_ID, startTime: "16:00", endTime: "17:00", status: "pending" },
        ],
    };
}

function response(status, payload) {
    return { ok: status >= 200 && status < 300, status, json: async () => payload };
}

const COMMAND_RESPONSE = {
    status: "ok", occurrenceId: OCCURRENCE_ID, occurrenceStatus: "in_progress",
    segmentIds: [FIRST_ID, REAL_NEW_ID],
};

test("draft clona el estado; agregar/quitar no cambia lo persistido ni crea ID falso", () => {
    const persisted = occurrence();
    const draft = createOccurrenceStructureDraft(persisted);
    draft.startTime = "12:00";
    draft.segments[0].endTime = "13:45";
    const added = addDraftSegment(draft);
    added.startTime = "14:30";
    added.endTime = "15:30";
    added.status = "pending";
    assert.equal(added.id, undefined);
    assert.ok(added.draftKey);
    assert.equal(persisted.startTime, "13:00");
    assert.equal(persisted.segments[0].endTime, "14:00");
    assert.equal(removeDraftSegment(draft, `persisted-${SECOND_ID}`), true);
    assert.equal(persisted.segments.length, 2);
    const payload = buildOccurrenceStructurePayload(draft);
    assert.deepEqual(payload, {
        startTime: "12:00", endTime: "17:00",
        segments: [
            { id: FIRST_ID, startTime: "13:00", endTime: "13:45" },
            { startTime: "14:30", endTime: "15:30", status: "pending" },
        ],
    });
    assert.equal(JSON.stringify(payload).includes("draftKey"), false);
});

test("trim/split/resize son set final; el parent no escala children y no se elimina el último", () => {
    const draft = createOccurrenceStructureDraft(occurrence());
    draft.endTime = "16:00";
    assert.equal(draft.segments[1].endTime, "17:00");
    assert.match(validateOccurrenceStructureDraft(draft), /caber/);
    draft.segments[1].startTime = "15:00";
    draft.segments[1].endTime = "16:00";
    draft.segments[0].endTime = "13:30";
    const split = addDraftSegment(draft);
    Object.assign(split, { startTime: "14:00", endTime: "15:00", status: "not_finished" });
    assert.equal(validateOccurrenceStructureDraft(draft), null);
    assert.equal(draftStructuralDuration(draft), "2h 30min");
    assert.deepEqual(buildOccurrenceStructurePayload(draft).segments[0], {
        id: FIRST_ID, startTime: "13:00", endTime: "13:30",
    });
    draft.segments[1].startTime = "14:30";
    assert.match(validateOccurrenceStructureDraft(draft), /superponerse/);
    draft.segments[1].startTime = "15:00";
    assert.equal(validateOccurrenceStructureDraft(draft), null);
    removeDraftSegment(draft, split.draftKey);
    removeDraftSegment(draft, `persisted-${SECOND_ID}`);
    assert.equal(removeDraftSegment(draft, `persisted-${FIRST_ID}`), false);
});

test("translate solo se permite para intención pura sin tocar children", () => {
    const draft = createOccurrenceStructureDraft(occurrence());
    draft.startTime = "14:00";
    draft.endTime = "18:00";
    assert.equal(canTranslateOccurrenceDraft(draft), true);
    draft.endTime = "19:00";
    assert.equal(canTranslateOccurrenceDraft(draft), false);
    draft.endTime = "18:00";
    draft.segments[0].endTime = "14:15";
    assert.equal(canTranslateOccurrenceDraft(draft), false);
});

test("API envía métodos, URLs y payloads exactos, sin draftKey", async () => {
    const calls = [];
    const options = {
        baseUrl: "http://localhost:5000",
        fetchImpl: async (...args) => { calls.push(args); return response(200, COMMAND_RESPONSE); },
    };
    await translateOccurrence(OCCURRENCE_ID, "14:00", "18:00", options);
    await replaceOccurrenceStructure(OCCURRENCE_ID, {
        startTime: "13:00", endTime: "17:00",
        segments: [{ id: FIRST_ID, startTime: "13:00", endTime: "14:00" }],
    }, options);
    await resetOccurrenceSegmentation(OCCURRENCE_ID, "13:00", "17:00", options);
    assert.deepEqual(calls.map(([url, init]) => [url.split("/").at(-1), init.method]), [
        ["translate", "POST"], ["structure", "PUT"], ["reset-segmentation", "POST"],
    ]);
    assert.deepEqual(JSON.parse(calls[0][1].body), { startTime: "14:00", endTime: "18:00" });
    assert.deepEqual(JSON.parse(calls[2][1].body), { startTime: "13:00", endTime: "17:00" });
});

test("API preserva blockers 409 y marca respuesta exitosa inválida como confirmada", async () => {
    const blocker = { occurrenceId: "blocker", segmentId: "segment", startTime: "14:00", endTime: "15:00" };
    await assert.rejects(
        replaceOccurrenceStructure(OCCURRENCE_ID, {}, {
            fetchImpl: async () => response(409, { code: "occurrence_structure_conflict", message: "Conflicto", blockers: [blocker] }),
        }),
        (error) => error instanceof PlannerApiError && error.code === "occurrence_structure_conflict"
            && error.details.blockers[0].segmentId === "segment",
    );
    await assert.rejects(
        translateOccurrence(OCCURRENCE_ID, "14:00", "18:00", {
            fetchImpl: async () => response(200, { status: "ok" }),
        }),
        (error) => error.code === "invalid_response" && error.details.mutationConfirmed,
    );
});

test("coordinador: comando → GET → hydrate, doble envío y refresh-only tras GET fallido", async () => {
    let resolveCommand;
    let commands = 0;
    let gets = 0;
    let hydrates = 0;
    const coordinator = createOccurrenceStructureMutationCoordinator({
        translateOccurrence: async () => {},
        replaceOccurrenceStructure: () => {
            commands += 1;
            return new Promise((resolve) => { resolveCommand = resolve; });
        },
        resetOccurrenceSegmentation: async () => {},
        loadPlannerState: async () => {
            gets += 1;
            if (gets === 1) throw new Error("GET falló");
            return { occurrences: [{ id: OCCURRENCE_ID, segments: [{ id: REAL_NEW_ID }] }] };
        },
        hydratePlannerState: (state) => { hydrates += 1; return state; },
    });
    const first = coordinator.submit("structure", OCCURRENCE_ID, {});
    const duplicate = coordinator.submit("structure", OCCURRENCE_ID, {});
    assert.equal(first, duplicate);
    resolveCommand();
    assert.equal((await first).status, "saved_refresh_error");
    assert.equal(coordinator.hasPendingRefresh(), true);
    const recovered = await coordinator.submit("structure", OCCURRENCE_ID, {});
    assert.equal(recovered.status, "synced");
    assert.equal(recovered.state.occurrences[0].segments[0].id, REAL_NEW_ID);
    assert.deepEqual([commands, gets, hydrates], [1, 2, 1]);
});

test("409, reconciliación y concurrencia no reenvían; red incierta solo permite GET", async () => {
    for (const code of ["occurrence_structure_conflict", "temporal_reconciliation_required", "concurrent_conflict"]) {
        let calls = 0;
        const coordinator = createOccurrenceStructureMutationCoordinator({
            translateOccurrence: async () => {},
            replaceOccurrenceStructure: async () => { calls += 1; throw new PlannerApiError(code, code); },
            resetOccurrenceSegmentation: async () => {},
            loadPlannerState: async () => { throw new Error("No debe ejecutar GET automático"); },
            hydratePlannerState: (state) => state,
        });
        assert.equal((await coordinator.submit("structure", OCCURRENCE_ID, {})).status, "mutation_error");
        assert.equal(calls, 1);
    }
    let calls = 0;
    const uncertain = createOccurrenceStructureMutationCoordinator({
        translateOccurrence: async () => {},
        replaceOccurrenceStructure: async () => { calls += 1; throw new PlannerApiError("network_error", "Sin red"); },
        resetOccurrenceSegmentation: async () => {},
        loadPlannerState: async () => ({ occurrences: [] }),
        hydratePlannerState: (state) => state,
    });
    assert.equal((await uncertain.submit("structure", OCCURRENCE_ID, {})).status, "unknown_result");
    assert.equal((await uncertain.retryRefresh()).status, "review_required");
    assert.equal(calls, 1);
});
