import assert from "node:assert/strict";
import test from "node:test";

import {
    deleteOccurrence,
    PlannerApiError,
    updateOccurrence,
} from "../js/api/planner-api.js";
import {
    createOccurrenceMutationCoordinator,
    getOccurrenceMutationErrorMessage,
} from "../js/mutations/occurrence-mutation.js";

const OCCURRENCE_ID = "00000000-0000-4000-8000-000000000101";
const PATCH_PAYLOAD = {
    date: "2026-09-22",
    startTime: "14:30",
    endTime: "17:30",
};

function response(status, payload) {
    return {
        ok: status >= 200 && status < 300,
        status,
        json: async () => payload,
    };
}

function deferred() {
    let resolve;
    const promise = new Promise((resolver) => { resolve = resolver; });
    return { promise, resolve };
}

test("planner-api usa el Occurrence.id exacto para PATCH y DELETE", async () => {
    const calls = [];
    const options = {
        baseUrl: "http://localhost:5000",
        fetchImpl: async (...args) => {
            calls.push(args);
            return args[1].method === "PATCH"
                ? response(200, { occurrence: { id: OCCURRENCE_ID } })
                : response(200, { deletedOccurrenceId: OCCURRENCE_ID });
        },
    };

    await updateOccurrence(OCCURRENCE_ID, PATCH_PAYLOAD, options);
    await deleteOccurrence(OCCURRENCE_ID, options);

    assert.equal(calls[0][0], `http://localhost:5000/api/occurrences/${OCCURRENCE_ID}`);
    assert.equal(calls[0][1].method, "PATCH");
    assert.deepEqual(JSON.parse(calls[0][1].body), PATCH_PAYLOAD);
    assert.equal(calls[1][0], `http://localhost:5000/api/occurrences/${OCCURRENCE_ID}`);
    assert.equal(calls[1][1].method, "DELETE");
    assert.equal("body" in calls[1][1], false);
});

test("planner-api conserva códigos 404/409 y sanitiza fallos de red", async () => {
    await assert.rejects(
        updateOccurrence(OCCURRENCE_ID, PATCH_PAYLOAD, {
            fetchImpl: async () => { throw new Error("private transport detail"); },
        }),
        (error) => error instanceof PlannerApiError && error.code === "network_error",
    );
    for (const [status, code] of [
        [404, "occurrence_not_found"],
        [409, "history_frozen"],
        [409, "last_manual_entry"],
        [409, "status_context_locked"],
        [409, "concurrent_conflict"],
        [409, "priority_override_required"],
    ]) {
        await assert.rejects(
            deleteOccurrence(OCCURRENCE_ID, {
                fetchImpl: async () => response(status, {
                    status: "error",
                    code,
                    message: "Mensaje controlado.",
                }),
            }),
            (error) => error.code === code && error.details.status === status,
        );
    }
});

test("PATCH exitoso ejecuta GET e hydrate sin tocar otra occurrence", async () => {
    const untouchedId = "00000000-0000-4000-8000-000000000102";
    const state = {
        planItems: [],
        occurrences: [
            { id: OCCURRENCE_ID, ...PATCH_PAYLOAD },
            { id: untouchedId, date: "2026-09-22", startTime: "20:00", endTime: "22:00" },
        ],
    };
    const events = [];
    const coordinator = createOccurrenceMutationCoordinator({
        mutateOccurrence: async (...args) => {
            events.push(["patch", ...args]);
            return { occurrence: state.occurrences[0] };
        },
        loadPlannerState: async () => { events.push(["get"]); return state; },
        hydratePlannerState: (serverState) => { events.push(["hydrate", serverState]); return serverState; },
    });

    const outcome = await coordinator.submit(OCCURRENCE_ID, PATCH_PAYLOAD);
    assert.equal(outcome.status, "synced");
    assert.deepEqual(events.map(([name]) => name), ["patch", "get", "hydrate"]);
    assert.equal(events[0][1], OCCURRENCE_ID);
    assert.deepEqual(events[0][2], PATCH_PAYLOAD);
    assert.equal(outcome.state.occurrences[1].id, untouchedId);
});

test("double PATCH y double DELETE comparten una sola mutation activa", async () => {
    for (const operation of ["patch", "delete"]) {
        const pendingMutation = deferred();
        let mutationCount = 0;
        const coordinator = createOccurrenceMutationCoordinator({
            mutateOccurrence: async () => {
                mutationCount += 1;
                return pendingMutation.promise;
            },
            loadPlannerState: async () => ({ planItems: [], occurrences: [] }),
            hydratePlannerState: (state) => state,
        });
        const args = operation === "patch" ? [OCCURRENCE_ID, PATCH_PAYLOAD] : [OCCURRENCE_ID];
        const first = coordinator.submit(...args);
        const second = coordinator.submit(...args);
        assert.equal(first, second);
        assert.equal(mutationCount, 1);
        pendingMutation.resolve(operation === "patch"
            ? { occurrence: { id: OCCURRENCE_ID } }
            : { deletedOccurrenceId: OCCURRENCE_ID });
        assert.equal((await first).status, "synced");
    }
});

test("mutation confirmada + GET fallido reintenta solo GET", async () => {
    let mutationCount = 0;
    let getCount = 0;
    const coordinator = createOccurrenceMutationCoordinator({
        mutateOccurrence: async () => {
            mutationCount += 1;
            return { deletedOccurrenceId: OCCURRENCE_ID };
        },
        loadPlannerState: async () => {
            getCount += 1;
            if (getCount === 1) throw new Error("refresh unavailable");
            return { planItems: [], occurrences: [] };
        },
        hydratePlannerState: (state) => state,
    });

    assert.equal((await coordinator.submit(OCCURRENCE_ID)).status, "saved_refresh_error");
    assert.equal((await coordinator.submit(OCCURRENCE_ID)).status, "synced");
    assert.equal(mutationCount, 1, "el retry no repite DELETE");
    assert.equal(getCount, 2);
});

test("success inválido recupera con GET y los códigos tienen mensajes diferenciados", async () => {
    let patchCount = 0;
    const coordinator = createOccurrenceMutationCoordinator({
        mutateOccurrence: () => updateOccurrence(OCCURRENCE_ID, PATCH_PAYLOAD, {
            fetchImpl: async () => {
                patchCount += 1;
                return response(200, { unexpected: true });
            },
        }),
        loadPlannerState: async () => ({ planItems: [], occurrences: [] }),
        hydratePlannerState: (state) => state,
    });
    assert.equal((await coordinator.submit()).status, "synced");
    assert.equal(patchCount, 1);

    const messages = new Set([
        "occurrence_not_found",
        "history_frozen",
        "last_manual_entry",
        "status_context_locked",
        "concurrent_modification",
        "priority_override_required",
    ].map((code) => getOccurrenceMutationErrorMessage({ code })));
    assert.equal(messages.size, 6);
});
