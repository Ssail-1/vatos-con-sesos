import assert from "node:assert/strict";
import test from "node:test";

import {
    createPlanItem,
    PlannerApiError,
} from "../js/api/planner-api.js";
import {
    addPriorityOverride,
    createPlanItemMutationCoordinator,
} from "../js/mutations/plan-item-creation.js";

const SLOT_ID = "00000000-0000-4000-8000-000000000001";
const PLAN_ITEM_ID = "00000000-0000-4000-8000-000000000010";
const OCCURRENCE_ID = "00000000-0000-4000-8000-000000000011";
const CONFLICT_ID = "00000000-0000-4000-8000-000000000020";

function manualPayload() {
    return {
        name: "Evento persistente",
        kind: "activity",
        activityType: "event",
        generationConfig: {
            mode: "manual_dates",
            entries: [{
                id: SLOT_ID,
                date: "2026-09-17",
                startTime: "10:00",
                endTime: "11:00",
            }],
        },
    };
}

function createdGraph(payload = manualPayload()) {
    return {
        planItem: { id: PLAN_ITEM_ID, ...payload },
        occurrences: [{
            id: OCCURRENCE_ID,
            planItemId: PLAN_ITEM_ID,
            date: "2026-09-17",
            startTime: "10:00",
            endTime: "11:00",
            status: "pending",
            sourceGenerationSlotId: SLOT_ID,
        }],
    };
}

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

test("API client POST conserva el payload y los UUID GenerationSlot", async () => {
    const payloads = [
        {
            ...manualPayload(),
            generationConfig: {
                mode: "weekly",
                startDate: "2026-09-17",
                endDate: null,
                indefinite: true,
                slots: [
                    { id: SLOT_ID, isoWeekday: 4, startTime: "08:00", endTime: "09:00" },
                    { id: "00000000-0000-4000-8000-000000000002", isoWeekday: 4, startTime: "18:00", endTime: "19:00" },
                ],
            },
        },
        {
            ...manualPayload(),
            generationConfig: {
                mode: "interval_days",
                startDate: "2026-09-17",
                endDate: null,
                indefinite: true,
                intervalDays: 3,
                slots: [
                    { id: SLOT_ID, startTime: "08:00", endTime: "09:00" },
                    { id: "00000000-0000-4000-8000-000000000002", startTime: "18:00", endTime: "19:00" },
                ],
            },
        },
        manualPayload(),
    ];

    for (const payload of payloads) {
        const calls = [];
        const result = await createPlanItem(payload, {
            baseUrl: "http://localhost:5000",
            fetchImpl: async (...args) => {
                calls.push(args);
                return response(201, createdGraph(payload));
            },
        });
        assert.equal(result.planItem.id, PLAN_ITEM_ID);
        assert.equal(calls.length, 1);
        assert.equal(calls[0][0], "http://localhost:5000/api/plan-items");
        assert.equal(calls[0][1].method, "POST");
        assert.deepEqual(JSON.parse(calls[0][1].body), payload);
    }
});

test("API client distingue red, 400 y 409 con conflictos confirmables", async () => {
    await assert.rejects(
        createPlanItem(manualPayload(), { fetchImpl: async () => { throw new Error("private"); } }),
        (error) => error instanceof PlannerApiError && error.code === "network_error",
    );
    await assert.rejects(
        createPlanItem(manualPayload(), {
            fetchImpl: async () => response(400, {
                status: "error",
                code: "invalid_payload",
                message: "Payload inválido.",
            }),
        }),
        (error) => error.code === "invalid_payload" && error.details.status === 400,
    );
    const conflicts = [{
        occurrenceId: CONFLICT_ID,
        planItemId: PLAN_ITEM_ID,
        date: "2026-09-17",
        startTime: "10:30",
        endTime: "11:30",
        status: "pending",
    }];
    await assert.rejects(
        createPlanItem(manualPayload(), {
            fetchImpl: async () => response(409, {
                status: "error",
                code: "priority_override_required",
                message: "Confirma el desplazamiento.",
                conflicts,
            }),
        }),
        (error) => error.code === "priority_override_required" &&
            error.details.status === 409 &&
            JSON.stringify(error.details.conflicts) === JSON.stringify(conflicts),
    );
});

test("POST exitoso hace GET e hidrata exactamente una vez", async () => {
    const graph = createdGraph();
    const serverState = { planItems: [graph.planItem], occurrences: graph.occurrences };
    const events = [];
    const coordinator = createPlanItemMutationCoordinator({
        postPlanItem: async (payload) => { events.push(["post", payload]); return graph; },
        loadPlannerState: async () => { events.push(["get"]); return serverState; },
        hydratePlannerState: (state) => { events.push(["hydrate", state]); return state; },
    });

    const outcome = await coordinator.submit(manualPayload());
    assert.equal(outcome.status, "synced");
    assert.equal(outcome.creation.planItem.id, PLAN_ITEM_ID);
    assert.equal(outcome.state.occurrences.length, 1);
    assert.deepEqual(events.map(([name]) => name), ["post", "get", "hydrate"]);
});

test("double submit comparte un único POST", async () => {
    const pendingPost = deferred();
    let postCount = 0;
    const coordinator = createPlanItemMutationCoordinator({
        postPlanItem: async () => { postCount += 1; return pendingPost.promise; },
        loadPlannerState: async () => ({ planItems: [], occurrences: [] }),
        hydratePlannerState: (state) => state,
    });

    const first = coordinator.submit(manualPayload());
    const second = coordinator.submit(manualPayload());
    assert.equal(first, second);
    assert.equal(postCount, 1);
    pendingPost.resolve(createdGraph());
    assert.equal((await first).status, "synced");
});

test("fallo de POST conserva estado y permite un nuevo POST manual", async () => {
    let postCount = 0;
    let getCount = 0;
    const coordinator = createPlanItemMutationCoordinator({
        postPlanItem: async () => {
            postCount += 1;
            if (postCount === 1) throw new PlannerApiError("network_error", "Sin red.");
            return createdGraph();
        },
        loadPlannerState: async () => { getCount += 1; return { planItems: [], occurrences: [] }; },
        hydratePlannerState: (state) => state,
    });

    assert.equal((await coordinator.submit(manualPayload())).status, "post_error");
    assert.equal(getCount, 0);
    assert.equal((await coordinator.submit(manualPayload())).status, "synced");
    assert.equal(postCount, 2);
});

test("POST confirmado + GET fallido reintenta únicamente GET", async () => {
    let postCount = 0;
    let getCount = 0;
    const coordinator = createPlanItemMutationCoordinator({
        postPlanItem: async () => { postCount += 1; return createdGraph(); },
        loadPlannerState: async () => {
            getCount += 1;
            if (getCount === 1) throw new Error("refresh unavailable");
            const graph = createdGraph();
            return { planItems: [graph.planItem], occurrences: graph.occurrences };
        },
        hydratePlannerState: (state) => state,
    });

    assert.equal((await coordinator.submit(manualPayload())).status, "saved_refresh_error");
    assert.equal(coordinator.hasPendingRefresh(), true);
    assert.equal((await coordinator.submit(manualPayload())).status, "synced");
    assert.equal(postCount, 1, "el retry no repite POST");
    assert.equal(getCount, 2);
});

test("respuesta 201 inválida también recupera con GET sin repetir POST", async () => {
    let postCount = 0;
    let getCount = 0;
    const apiPost = () => createPlanItem(manualPayload(), {
        fetchImpl: async () => { postCount += 1; return response(201, { unexpected: true }); },
    });
    const coordinator = createPlanItemMutationCoordinator({
        postPlanItem: apiPost,
        loadPlannerState: async () => { getCount += 1; return { planItems: [], occurrences: [] }; },
        hydratePlannerState: (state) => state,
    });

    assert.equal((await coordinator.submit(manualPayload())).status, "synced");
    assert.equal(postCount, 1);
    assert.equal(getCount, 1);
});

test("priority override cancela sin segundo POST o confirma con metadata exacta", async () => {
    const conflict = {
        occurrenceId: CONFLICT_ID,
        planItemId: PLAN_ITEM_ID,
        date: "2026-09-17",
        startTime: "10:30",
        endTime: "11:30",
        status: "pending",
    };
    const calls = [];
    const coordinator = createPlanItemMutationCoordinator({
        postPlanItem: async (payload) => {
            calls.push(payload);
            if (calls.length === 1) {
                throw new PlannerApiError(
                    "priority_override_required",
                    "Confirma.",
                    { status: 409, conflicts: [conflict] },
                );
            }
            return createdGraph();
        },
        loadPlannerState: async () => ({ planItems: [], occurrences: [] }),
        hydratePlannerState: (state) => state,
    });

    const first = await coordinator.submit(manualPayload());
    assert.equal(first.status, "override_required");
    assert.equal(calls.length, 1, "cancelar no dispara ninguna operación automática");

    const confirmedPayload = addPriorityOverride(manualPayload(), first.conflicts);
    assert.equal((await coordinator.submit(confirmedPayload)).status, "synced");
    assert.deepEqual(calls[1].priorityOverride, {
        confirmedOccurrenceIds: [CONFLICT_ID],
    });
    assert.deepEqual(calls[1].generationConfig, manualPayload().generationConfig);
});
