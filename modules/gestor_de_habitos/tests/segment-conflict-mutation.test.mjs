import assert from "node:assert/strict";
import test from "node:test";

import { PlannerApiError, replaceOccurrenceStructure, resetOccurrenceSegmentation, translateOccurrence } from "../js/api/planner-api.js";
import { createSegmentConflictMutationCoordinator } from "../js/mutations/segment-conflict-mutation.js";
import { getSegmentConflictEffect } from "../js/views/segment-conflict-dialog.js";

const OCCURRENCE = "00000000-0000-4000-8000-000000000101";
const SEGMENT = "00000000-0000-4000-8000-000000000201";
const PLAN = "00000000-0000-4000-8000-000000000301";

function conflict(segmentId = SEGMENT, status = "pending") {
    return {
        blocker: { occurrenceId: OCCURRENCE, segmentId, planItemId: PLAN,
            date: "2026-09-25", startTime: "08:00", endTime: "10:00", status },
        requiredAuthorization: "user_forced_override",
        resolutionKind: "split_segment",
        requiresRealizedTimeConfirmation: false,
    };
}

function fail(code, conflicts = []) {
    return new PlannerApiError(code, code, { status: 409, conflicts });
}

function coordinator(executeCommand, loadPlannerState = async () => ({ planItems: [], occurrences: [] })) {
    return createSegmentConflictMutationCoordinator({
        executeCommand, loadPlannerState, hydratePlannerState: (state) => state,
    });
}

test("confirmación nueva reemplaza blocker anterior y no hereda aceptación", async () => {
    const next = "00000000-0000-4000-8000-000000000202";
    const calls = [];
    const mutation = coordinator(async (command, confirmation) => {
        calls.push({ command, confirmation });
        if (calls.length === 1) throw fail("segment_conflict_resolution_required", [conflict()]);
        if (calls.length === 2) throw fail("segment_conflict_resolution_required", [conflict(next)]);
        return { status: "ok" };
    });
    const source = { kind: "structure", occurrenceId: OCCURRENCE, payload: {
        startTime: "08:00", endTime: "12:00", segments: [{ id: SEGMENT, startTime: "08:00", endTime: "12:00" }],
    } };
    assert.equal((await mutation.submit(source)).status, "conflict_required");
    source.payload.segments[0].endTime = "15:00";
    const fresh = await mutation.confirm();
    assert.equal(fresh.status, "conflict_required");
    assert.equal(fresh.conflicts[0].blocker.segmentId, next);
    assert.equal((await mutation.confirm()).status, "synced");
    assert.equal(calls[1].command.payload.segments[0].endTime, "12:00");
    assert.equal(calls[1].confirmation.confirmations[0].blocker.segmentId, SEGMENT);
    assert.equal(calls[2].confirmation.confirmations[0].blocker.segmentId, next);
});

test("stale descarta confirmación y solo lee estado autoritativo", async () => {
    let mutations = 0;
    let reads = 0;
    const mutation = coordinator(async () => {
        mutations += 1;
        throw mutations === 1
            ? fail("segment_conflict_resolution_required", [conflict()])
            : fail("conflict_resolution_stale");
    }, async () => { reads += 1; return { planItems: [], occurrences: [] }; });
    await mutation.submit({ kind: "translate", occurrenceId: OCCURRENCE, payload: {
        startTime: "10:00", endTime: "12:00",
    } });
    assert.equal((await mutation.confirm()).status, "stale");
    assert.equal(mutation.hasPendingConflict(), false);
    assert.equal(mutations, 2);
    assert.equal(reads, 1);
});

test("fallo de transporte ambiguo no repite comando; GET fallido reintenta solo GET", async () => {
    let mutations = 0;
    let reads = 0;
    const mutation = coordinator(async () => {
        mutations += 1;
        throw fail("network_error");
    }, async () => {
        reads += 1;
        if (reads === 1) throw new Error("offline");
        return { planItems: [], occurrences: [] };
    });
    assert.equal((await mutation.submit({ kind: "create", payload: {} })).status, "unknown_result");
    assert.equal((await mutation.submit({ kind: "create", payload: {} })).status, "review_required");
    assert.equal(mutations, 1);
    assert.equal(reads, 2);
});

test("casos no definidos, múltiples sources e historia congelada no reciben force", async () => {
    for (const code of ["segment_resolution_undefined", "multiple_source_resolution_unavailable", "conflict_resolution_frozen"]) {
        const mutation = coordinator(async () => { throw fail(code); });
        assert.equal((await mutation.submit({ kind: "create", payload: {} })).status, "unsupported");
        assert.equal(mutation.hasPendingConflict(), false);
    }
    assert.match(getSegmentConflictEffect("undefined_in_progress"), /no tiene una resolución/);
    assert.match(getSegmentConflictEffect("unknown"), /no describió/);
});

test("translate, PUT structure y reset aceptan metadata sin alterar source payload", async () => {
    const resolution = { confirmations: [{ blocker: {
        occurrenceId: OCCURRENCE, segmentId: SEGMENT, startTime: "08:00", endTime: "10:00", status: "pending",
    }, confirmed: true }] };
    const calls = [];
    const options = { conflictResolution: resolution, fetchImpl: async (...args) => {
        calls.push(args);
        return { ok: true, status: 200, json: async () => ({
            status: "ok", occurrenceId: OCCURRENCE, occurrenceStatus: "pending", segmentIds: [SEGMENT],
        }) };
    } };
    await translateOccurrence(OCCURRENCE, "09:00", "11:00", options);
    const structure = { startTime: "09:00", endTime: "11:00", segments: [{
        id: SEGMENT, startTime: "09:00", endTime: "11:00",
    }], conflictResolution: resolution };
    await replaceOccurrenceStructure(OCCURRENCE, structure, options);
    await resetOccurrenceSegmentation(OCCURRENCE, "09:00", "11:00", options);
    assert.deepEqual(calls.map(([, init]) => init.method), ["POST", "PUT", "POST"]);
    calls.forEach(([, init]) => {
        const body = JSON.parse(init.body);
        assert.equal(body.startTime, "09:00");
        assert.equal(body.endTime, "11:00");
        assert.deepEqual(body.conflictResolution, resolution);
    });
    assert.deepEqual(structure.segments, [{ id: SEGMENT, startTime: "09:00", endTime: "11:00" }]);
});

test("double submit y double confirm comparten un único request activo", async () => {
    let resolve;
    let calls = 0;
    const pending = new Promise((done) => { resolve = done; });
    const mutation = coordinator(async () => {
        calls += 1;
        return pending;
    });
    const command = { kind: "reset", occurrenceId: OCCURRENCE, payload: {
        startTime: "08:00", endTime: "10:00",
    } };
    const first = mutation.submit(command);
    const second = mutation.submit(command);
    assert.equal(first, second);
    assert.equal(calls, 1);
    resolve({ status: "ok" });
    assert.equal((await first).status, "synced");
});
