import assert from "node:assert/strict";
import test from "node:test";

import { createPlanItem, PlannerApiError } from "../js/api/planner-api.js";
import {
    buildConflictResolution, createSegmentConflictMutationCoordinator,
} from "../js/mutations/segment-conflict-mutation.js";

const SLOT_ID = "00000000-0000-4000-8000-000000000001";
const SOURCE_ID = "00000000-0000-4000-8000-000000000010";
const TARGET_ID = "00000000-0000-4000-8000-000000000020";
const SEGMENT_ID = "00000000-0000-4000-8000-000000000021";

function payload() {
    return {
        name: "Evento persistente", kind: "activity", activityType: "event",
        generationConfig: { mode: "manual_dates", entries: [{
            id: SLOT_ID, date: "2026-09-25", startTime: "10:00", endTime: "11:00",
        }] },
    };
}

function conflict(status = "pending", realized = false) {
    return {
        blocker: {
            occurrenceId: TARGET_ID, segmentId: SEGMENT_ID,
            planItemId: SOURCE_ID, date: "2026-09-25",
            startTime: "10:30", endTime: "11:30", status,
        },
        requiredAuthorization: realized ? "user_forced_override" : "priority_override",
        resolutionKind: "trim_segment",
        requiresRealizedTimeConfirmation: realized,
    };
}

function response(status, body) {
    return { ok: status >= 200 && status < 300, status, json: async () => body };
}

test("API create conserva payload y UUID de slot y lee el 409 segmentario completo", async () => {
    const original = payload();
    const calls = [];
    await createPlanItem(original, {
        fetchImpl: async (...args) => { calls.push(args); return response(201, {
            planItem: { id: SOURCE_ID }, occurrences: [],
        }); },
    });
    assert.deepEqual(JSON.parse(calls[0][1].body), original);
    await assert.rejects(createPlanItem(original, {
        fetchImpl: async () => response(409, {
            code: "segment_conflict_resolution_required", conflicts: [conflict()],
        }),
    }), (error) => error instanceof PlannerApiError
        && error.code === "segment_conflict_resolution_required"
        && error.details.conflicts[0].blocker.segmentId === SEGMENT_ID);
    await assert.rejects(createPlanItem(original, {
        fetchImpl: async () => response(400, { code: "invalid_payload" }),
    }), (error) => error.code === "invalid_payload");
});

test("confirmación liga snapshot exacto y tiempo realizado por blocker", () => {
    const regular = conflict();
    const completed = { ...conflict("completed", true), blocker: {
        ...conflict().blocker, segmentId: "00000000-0000-4000-8000-000000000022", status: "completed",
    } };
    assert.throws(() => buildConflictResolution([regular, completed]), /explícita/);
    const confirmation = buildConflictResolution([regular, completed], new Set([
        `${TARGET_ID}:${completed.blocker.segmentId}`,
    ]));
    assert.deepEqual(confirmation.confirmations[0], {
        blocker: {
            occurrenceId: TARGET_ID, segmentId: SEGMENT_ID,
            startTime: "10:30", endTime: "11:30", status: "pending",
        }, confirmed: true,
    });
    assert.equal(confirmation.confirmations[1].confirmRealizedTimeCorrection, true);
});

test("crear → 409 → confirmar reutiliza source y después hidrata; cancelar no reenvía", async () => {
    const calls = [];
    const events = [];
    const coordinator = createSegmentConflictMutationCoordinator({
        executeCommand: async (command, confirmation) => {
            calls.push({ command, confirmation });
            if (!confirmation) throw new PlannerApiError("segment_conflict_resolution_required", "Conflicto", {
                conflicts: [conflict()], status: 409,
            });
            return { planItem: { id: SOURCE_ID } };
        },
        loadPlannerState: async () => { events.push("GET"); return { planItems: [], occurrences: [] }; },
        hydratePlannerState: (state) => { events.push("hydrate"); return state; },
    });
    const command = { kind: "create", payload: payload() };
    assert.equal((await coordinator.submit(command)).status, "conflict_required");
    command.payload.name = "Cambio local posterior";
    coordinator.cancel();
    assert.equal(calls.length, 1);
    assert.equal((await coordinator.submit({ kind: "create", payload: payload() })).status, "conflict_required");
    assert.equal((await coordinator.confirm()).status, "synced");
    assert.deepEqual(calls[2].command.payload, payload());
    assert.equal(calls[2].confirmation.confirmations[0].blocker.segmentId, SEGMENT_ID);
    assert.deepEqual(events, ["GET", "hydrate"]);
});

test("POST confirmado + GET fallido reintenta solo GET", async () => {
    let posts = 0;
    let gets = 0;
    const coordinator = createSegmentConflictMutationCoordinator({
        executeCommand: async () => { posts += 1; return { planItem: { id: SOURCE_ID } }; },
        loadPlannerState: async () => {
            gets += 1;
            if (gets === 1) throw new Error("GET falló");
            return { planItems: [], occurrences: [] };
        },
        hydratePlannerState: (state) => state,
    });
    assert.equal((await coordinator.submit({ kind: "create", payload: payload() })).status, "saved_refresh_error");
    assert.equal((await coordinator.submit({ kind: "create", payload: payload() })).status, "synced");
    assert.equal(posts, 1);
    assert.equal(gets, 2);
});
