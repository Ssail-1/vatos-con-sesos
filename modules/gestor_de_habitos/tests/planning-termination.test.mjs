import assert from "node:assert/strict";
import test from "node:test";

import { terminatePlanningAfter, PlannerApiError } from "../js/api/planner-api.js";
import { getPersistentPlanningActions } from "../js/domain/deletion-policy.js";
import { createPlanningTerminationMutationCoordinator } from "../js/mutations/planning-termination-mutation.js";
import { materializeOccurrenceDrafts } from "../js/scheduling/materializer.js";

const occurrenceId = "00000000-0000-4000-8000-000000000001";
const slotId = "00000000-0000-4000-8000-000000000002";
const planItemId = "00000000-0000-4000-8000-000000000003";

test("acciones siguen occurrence y provenance, no segmento ni horario", () => {
    const config = { mode: "weekly" };
    const occurrence = { id: occurrenceId, date: "2026-09-22", sourceGenerationSlotId: slotId };
    assert.deepEqual(getPersistentPlanningActions({ occurrence, generationConfig: config, referenceDate: "2026-09-22" }),
        { slot: true, recurring: true, future: true });
    assert.deepEqual(getPersistentPlanningActions({ occurrence: { ...occurrence, sourceGenerationSlotId: undefined }, generationConfig: config, referenceDate: "2026-09-22" }),
        { slot: false, recurring: true, future: true });
    assert.deepEqual(getPersistentPlanningActions({ occurrence, generationConfig: { mode: "manual_dates" }, referenceDate: "2026-09-22" }),
        { slot: false, recurring: false, future: true });
    assert.deepEqual(getPersistentPlanningActions({ occurrence, generationConfig: config, referenceDate: "2026-09-23" }),
        { slot: false, recurring: false, future: false });
});

test("acciones no ofrecen detener una recurrencia que ya termina en D", () => {
    const occurrence = { id: occurrenceId, date: "2026-09-22", sourceGenerationSlotId: slotId };
    const stoppedSlot = {
        mode: "weekly", indefinite: true,
        slots: [{ id: slotId, lastGenerationDate: "2026-09-22" }],
    };
    assert.deepEqual(getPersistentPlanningActions({
        occurrence, generationConfig: stoppedSlot, referenceDate: "2026-09-22",
    }), { slot: false, recurring: false, future: true });

    const globallyStopped = {
        mode: "weekly", indefinite: true, stoppedFromDate: "2026-09-23",
        slots: [{ id: slotId }],
    };
    assert.deepEqual(getPersistentPlanningActions({
        occurrence, generationConfig: globallyStopped, referenceDate: "2026-09-22",
    }), { slot: false, recurring: false, future: true });
});

test("API usa tres endpoints explícitos y nunca envía scope desde cliente", async () => {
    const calls = [];
    for (const [scope, suffix] of [
        ["slot", "stop-slot-after"], ["recurring", "stop-recurring-after"], ["future", "delete-future-after"],
    ]) {
        const result = await terminatePlanningAfter(occurrenceId, scope, {
            baseUrl: "http://127.0.0.1:5000",
            fetchImpl: async (url, options) => {
                calls.push({ url, options });
                return { ok: true, status: 200, json: async () => ({
                    status: "ok", scope, selectedOccurrenceId: occurrenceId,
                    planItemId, cutoffDate: "2026-09-22", deletedOccurrenceIds: [],
                }) };
            },
        });
        assert.equal(result.scope, scope);
        assert.ok(calls.at(-1).url.endsWith(`/api/occurrences/${occurrenceId}/${suffix}`));
        assert.equal(calls.at(-1).options.method, "POST");
        assert.equal(calls.at(-1).options.body, undefined);
    }
});

test("API conserva 409 sanitizado y success inválido como mutación confirmada", async () => {
    await assert.rejects(terminatePlanningAfter(occurrenceId, "slot", {
        fetchImpl: async () => ({ ok: false, status: 409, json: async () => ({ code: "source_provenance_locked", message: "Protegido" }) }),
    }), (error) => error instanceof PlannerApiError && error.code === "source_provenance_locked");
    await assert.rejects(terminatePlanningAfter(occurrenceId, "slot", {
        fetchImpl: async () => ({ ok: true, status: 200, json: async () => ({ status: "ok" }) }),
    }), (error) => error.details.mutationConfirmed === true);
});

test("coordinador hace POST → GET → hydrate y bloquea double submit", async () => {
    let resolvePost;
    let posts = 0;
    let reads = 0;
    let hydrates = 0;
    const coordinator = createPlanningTerminationMutationCoordinator({
        terminatePlanning: () => { posts += 1; return new Promise((resolve) => { resolvePost = resolve; }); },
        loadPlannerState: async () => { reads += 1; return { planItems: [], occurrences: [] }; },
        hydratePlannerState: (state) => { hydrates += 1; return state; },
    });
    const first = coordinator.submit(occurrenceId, "slot");
    const second = coordinator.submit(occurrenceId, "slot");
    assert.equal(first, second);
    assert.equal(posts, 1);
    resolvePost({ status: "ok" });
    assert.equal((await first).status, "synced");
    assert.equal(reads, 1);
    assert.equal(hydrates, 1);
});

test("Commands 2–4: POST confirmado + GET fallido reintenta únicamente GET", async () => {
    for (const scope of ["slot", "recurring", "future"]) {
        let posts = 0;
        let reads = 0;
        const coordinator = createPlanningTerminationMutationCoordinator({
            terminatePlanning: async () => { posts += 1; return { status: "ok" }; },
            loadPlannerState: async () => { reads += 1; if (reads === 1) throw new Error("GET"); return {}; },
            hydratePlannerState: (state) => state,
        });
        assert.equal((await coordinator.submit(occurrenceId, scope)).status, "saved_refresh_error");
        assert.equal((await coordinator.submit(occurrenceId, scope)).status, "synced");
        assert.equal(posts, 1, scope);
        assert.equal(reads, 2, scope);
    }
});

test("Commands 2–4: fallo ambiguo lee primero y nunca reenvía el comando", async () => {
    for (const scope of ["slot", "recurring", "future"]) {
        let posts = 0;
        let reads = 0;
        const coordinator = createPlanningTerminationMutationCoordinator({
            terminatePlanning: async () => { posts += 1; throw new PlannerApiError("network_error", "Red"); },
            loadPlannerState: async () => { reads += 1; return {}; },
            hydratePlannerState: (state) => state,
        });
        assert.equal((await coordinator.submit(occurrenceId, scope)).status, "review_required");
        assert.equal(posts, 1, scope);
        assert.equal(reads, 1, scope);
    }
});

test("fallo ambiguo + GET fallido conserva recuperación GET-only", async () => {
    let posts = 0;
    let reads = 0;
    const coordinator = createPlanningTerminationMutationCoordinator({
        terminatePlanning: async () => { posts += 1; throw new PlannerApiError("network_error", "Red"); },
        loadPlannerState: async () => { reads += 1; if (reads === 1) throw new Error("GET"); return {}; },
        hydratePlannerState: (state) => state,
    });
    assert.equal((await coordinator.submit(occurrenceId, "future")).status, "unknown_result");
    assert.equal((await coordinator.retryRefresh()).status, "synced");
    assert.equal(posts, 1);
    assert.equal(reads, 2);
});

test("materializadores no regeneran un slot tras su fecha final inclusiva", () => {
    const item = { id: planItemId, generationConfig: {
        mode: "weekly", startDate: "2026-09-22", endDate: "2026-10-06", indefinite: false,
        slots: [{ id: slotId, isoWeekday: 2, startTime: "08:00", endTime: "09:00",
            lastGenerationDate: "2026-09-29" }],
    } };
    assert.deepEqual(materializeOccurrenceDrafts(item, "2026-09-22", "2026-10-06").map(({ date }) => date),
        ["2026-09-22", "2026-09-29"]);
});
