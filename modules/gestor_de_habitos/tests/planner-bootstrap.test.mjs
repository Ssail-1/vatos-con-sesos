import assert from "node:assert/strict";
import test from "node:test";

import { getApiBaseUrl } from "../js/api/api-config.js";
import {
    fetchPlannerState,
    PlannerApiError,
    validatePlannerStateResponse,
} from "../js/api/planner-api.js";
import { createPlannerBootstrap } from "../js/bootstrap/planner-bootstrap.js";
import { createPlannerStore } from "../js/state/planner-store.js";

const PLAN_ITEM_ID = "00000000-0000-4000-8000-000000000101";
const SLOT_IDS = [1, 2, 3].map(
    (number) => `00000000-0000-4000-8000-${String(number).padStart(12, "0")}`,
);
const OCCURRENCE_IDS = [11, 12, 13].map(
    (number) => `00000000-0000-4000-8000-${String(number).padStart(12, "0")}`,
);
const SEGMENT_IDS = [21, 22, 23].map(
    (number) => `00000000-0000-4000-8000-${String(number).padStart(12, "0")}`,
);

function persistedState() {
    return {
        planItems: [
            {
                id: PLAN_ITEM_ID,
                name: "Medicamento persistido",
                kind: "habit",
                habitType: "scheduled",
                generationConfig: {
                    mode: "manual_dates",
                    entries: SLOT_IDS.map((id, index) => ({
                        id,
                        date: "2026-09-17",
                        startTime: ["08:00", "14:00", "22:00"][index],
                        endTime: ["08:05", "14:05", "22:05"][index],
                    })),
                },
            },
        ],
        occurrences: OCCURRENCE_IDS.map((id, index) => ({
            id,
            planItemId: PLAN_ITEM_ID,
            date: "2026-09-17",
            startTime: ["08:00", "14:00", "22:00"][index],
            endTime: ["08:05", "14:05", "22:05"][index],
            status: ["pending", "completed", "cancelled"][index],
            sourceGenerationSlotId: SLOT_IDS[index],
            segments: [{
                id: SEGMENT_IDS[index],
                startTime: ["08:00", "14:00", "22:00"][index],
                endTime: ["08:05", "14:05", "22:05"][index],
                status: ["pending", "completed", "cancelled"][index],
            }],
            ...(index === 2 ? {
                conflictContext: {
                    reason: "priority_override",
                    sourceOccurrenceId: OCCURRENCE_IDS[0],
                },
            } : {}),
        })),
    };
}

function successfulResponse(payload) {
    return { ok: true, status: 200, json: async () => payload };
}

test("API base URL usa same-origin y permite override local explícito", () => {
    assert.equal(getApiBaseUrl({ href: "http://127.0.0.1:8000/index.html" }), "");
    assert.equal(
        getApiBaseUrl({
            href: "http://127.0.0.1:8000/index.html?apiBaseUrl=http%3A%2F%2Flocalhost%3A5000%2F",
        }),
        "http://localhost:5000",
    );
});

test("API client conserva el contrato canónico y usa únicamente GET planner-state", async () => {
    const state = persistedState();
    const calls = [];
    const result = await fetchPlannerState({
        baseUrl: "http://localhost:5000",
        fetchImpl: async (...args) => {
            calls.push(args);
            return successfulResponse(state);
        },
    });

    assert.equal(result, state);
    assert.equal(calls.length, 1);
    assert.equal(calls[0][0], "http://localhost:5000/api/planner-state");
    assert.deepEqual(calls[0][1], {
        method: "GET",
        headers: { Accept: "application/json" },
    });
});

test("API client distingue network, HTTP y response inválida", async () => {
    await assert.rejects(
        fetchPlannerState({ fetchImpl: async () => { throw new Error("private"); } }),
        (error) => error instanceof PlannerApiError && error.code === "network_error",
    );
    await assert.rejects(
        fetchPlannerState({ fetchImpl: async () => ({ ok: false, status: 503 }) }),
        (error) => error instanceof PlannerApiError && error.code === "http_error" && error.details.status === 503,
    );
    await assert.rejects(
        fetchPlannerState({ fetchImpl: async () => ({ ok: true, json: async () => { throw new Error("bad json"); } }) }),
        (error) => error instanceof PlannerApiError && error.code === "invalid_response",
    );
    for (const payload of [null, {}, { planItems: {}, occurrences: [] }, { planItems: [], occurrences: [null] }]) {
        assert.throws(
            () => validatePlannerStateResponse(payload),
            (error) => error instanceof PlannerApiError && error.code === "invalid_response",
        );
    }
});

test("hydration reemplaza el grafo atómicamente sin rematerializar ni cambiar IDs", () => {
    const state = persistedState();
    const store = createPlannerStore([], [], "2026-09-17");
    const hydrated = store.hydratePlannerState(state);

    assert.deepEqual(hydrated, state);
    assert.deepEqual(store.getPlanItems(), state.planItems);
    assert.deepEqual(store.getOccurrences(), state.occurrences);
    assert.equal(store.getPlanItems().length, 1);
    assert.equal(store.getOccurrences().length, 3);
    assert.deepEqual(store.getOccurrences().map(({ id }) => id), OCCURRENCE_IDS);
    assert.deepEqual(
        store.getOccurrences().map(({ status }) => status),
        ["pending", "completed", "cancelled"],
    );
});

test("hydration acepta DB vacía y no introduce mocks", () => {
    const store = createPlannerStore([], [], "2026-09-17");
    assert.deepEqual(
        store.hydratePlannerState({ planItems: [], occurrences: [] }),
        { planItems: [], occurrences: [] },
    );
    assert.deepEqual(store.getPlanItems(), []);
    assert.deepEqual(store.getOccurrences(), []);
});

test("hydration inválida conserva completo el estado anterior", () => {
    const store = createPlannerStore([], [], "2026-09-17");
    const state = persistedState();
    store.hydratePlannerState(state);
    const before = {
        planItems: store.getPlanItems(),
        occurrences: store.getOccurrences(),
    };
    const invalid = persistedState();
    invalid.occurrences[0].planItemId = "missing-plan-item";

    assert.throws(() => store.hydratePlannerState(invalid));
    assert.deepEqual(store.getPlanItems(), before.planItems);
    assert.deepEqual(store.getOccurrences(), before.occurrences);
});

test("bootstrap controla error y retry sin duplicar carga concurrente", async () => {
    const store = createPlannerStore([], [], "2026-09-17");
    const events = [];
    let attempts = 0;
    let releaseFirstRequest;
    const firstRequest = new Promise((resolve) => { releaseFirstRequest = resolve; });
    const bootstrap = createPlannerBootstrap({
        loadPlannerState: async () => {
            attempts += 1;
            if (attempts === 1) {
                await firstRequest;
                throw new Error("backend unavailable");
            }
            return persistedState();
        },
        hydratePlannerState: (state) => store.hydratePlannerState(state),
        onLoading: () => events.push("loading"),
        onReady: () => events.push("ready"),
        onError: () => events.push("error"),
    });

    const first = bootstrap.start();
    assert.equal(bootstrap.retry(), first, "un retry durante loading reutiliza el request activo");
    releaseFirstRequest();
    assert.equal((await first).status, "error");
    assert.equal((await bootstrap.retry()).status, "ready");

    assert.equal(attempts, 2);
    assert.deepEqual(events, ["loading", "error", "loading", "ready"]);
    assert.equal(store.getOccurrences().length, 3);
});
