import assert from "node:assert/strict";
import test from "node:test";

import {
    applyFuture,
    applyWeek,
    PlannerApiError,
} from "../js/api/planner-api.js";
import {
    buildApplyFuturePayload,
    createRecurringScheduleMutationCoordinator,
    getRecurringScheduleMutationErrorMessage,
} from "../js/mutations/recurring-schedule-mutation.js";
import { createPlannerStore } from "../js/state/planner-store.js";

const PLAN_ITEM_ID = "00000000-0000-4000-8000-000000000010";
const SLOT_1 = "00000000-0000-4000-8000-000000000001";
const SLOT_2 = "00000000-0000-4000-8000-000000000002";
const SLOT_3 = "00000000-0000-4000-8000-000000000003";

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

function weeklyConfig() {
    return {
        mode: "weekly",
        startDate: "2026-09-01",
        endDate: null,
        indefinite: true,
        excludedDates: ["2026-09-08"],
        slots: [
            { id: SLOT_1, isoWeekday: 1, startTime: "08:00", endTime: "11:00", excludedDates: ["2026-09-07"] },
            { id: SLOT_2, isoWeekday: 1, startTime: "14:00", endTime: "17:00" },
            { id: SLOT_3, isoWeekday: 1, startTime: "20:00", endTime: "22:00" },
        ],
    };
}

function intervalConfig() {
    return {
        mode: "interval_days",
        startDate: "2026-09-01",
        endDate: null,
        indefinite: true,
        intervalDays: 3,
        slots: [
            { id: SLOT_1, startTime: "08:00", endTime: "09:00", excludedDates: ["2026-09-10"] },
            { id: SLOT_2, startTime: "18:00", endTime: "19:00" },
        ],
    };
}

test("planner-api usa los endpoints y payloads reales de Apply Week/Future", async () => {
    const calls = [];
    const options = {
        baseUrl: "http://localhost:5000",
        fetchImpl: async (...args) => {
            calls.push(args);
            return args[0].endsWith("apply-week")
                ? response(200, {
                    weekStart: "2026-09-21",
                    weekEnd: "2026-09-27",
                    occurrences: [],
                })
                : response(200, {
                    planItem: { id: PLAN_ITEM_ID },
                    occurrences: [],
                });
        },
    };
    const weekPayload = {
        anchorDate: "2026-09-21",
        operations: [{
            type: "create",
            date: "2026-09-21",
            startTime: "08:00",
            endTime: "09:00",
        }],
    };
    const futurePayload = buildApplyFuturePayload(weeklyConfig(), "2026-09-21");

    await applyWeek(PLAN_ITEM_ID, weekPayload, options);
    await applyFuture(PLAN_ITEM_ID, futurePayload, options);

    assert.equal(calls[0][0], `http://localhost:5000/api/plan-items/${PLAN_ITEM_ID}/apply-week`);
    assert.equal(calls[1][0], `http://localhost:5000/api/plan-items/${PLAN_ITEM_ID}/apply-future`);
    assert.equal(calls[0][1].method, "POST");
    assert.equal(calls[1][1].method, "POST");
    assert.deepEqual(JSON.parse(calls[0][1].body), weekPayload);
    assert.deepEqual(JSON.parse(calls[1][1].body), futurePayload);
});

test("futureConfig conserva UUID y omite controles que backend preserva", () => {
    assert.deepEqual(
        buildApplyFuturePayload(weeklyConfig(), "2026-09-21"),
        {
            futureConfig: {
                mode: "weekly",
                startDate: "2026-09-21",
                endDate: null,
                indefinite: true,
                slots: [
                    { id: SLOT_1, isoWeekday: 1, startTime: "08:00", endTime: "11:00" },
                    { id: SLOT_2, isoWeekday: 1, startTime: "14:00", endTime: "17:00" },
                    { id: SLOT_3, isoWeekday: 1, startTime: "20:00", endTime: "22:00" },
                ],
            },
        },
    );
    const interval = buildApplyFuturePayload(intervalConfig(), "2026-09-22");
    assert.equal(interval.futureConfig.intervalDays, 3);
    assert.deepEqual(interval.futureConfig.slots.map(({ id }) => id), [SLOT_1, SLOT_2]);
    assert.equal("excludedDates" in interval.futureConfig, false);
    assert.equal("excludedDates" in interval.futureConfig.slots[0], false);

    const manual = buildApplyFuturePayload({
        mode: "manual_dates",
        entries: [{ id: SLOT_1, date: "2026-09-22", startTime: "08:00", endTime: "09:00" }],
    }, "2026-09-22");
    assert.deepEqual(manual, {
        futureConfig: {
            mode: "manual_dates",
            entries: [{ id: SLOT_1, date: "2026-09-22", startTime: "08:00", endTime: "09:00" }],
        },
    });
});

test("prepareApplyWeekPayload deriva multi-slot sin mutar el store", () => {
    const store = createPlannerStore([], [], "2026-09-18");
    const originalConfig = weeklyConfig();
    const occurrences = [
        ["00000000-0000-4000-8000-000000000101", SLOT_1, "08:00", "11:00"],
        ["00000000-0000-4000-8000-000000000102", SLOT_2, "14:00", "17:00"],
        ["00000000-0000-4000-8000-000000000103", SLOT_3, "20:00", "22:00"],
    ].map(([id, sourceGenerationSlotId, startTime, endTime]) => ({
        id,
        planItemId: PLAN_ITEM_ID,
        date: "2026-09-21",
        startTime,
        endTime,
        status: "pending",
        sourceGenerationSlotId,
    }));
    store.hydratePlannerState({
        planItems: [{
            id: PLAN_ITEM_ID,
            name: "Uber",
            kind: "activity",
            activityType: "periodic",
            generationConfig: originalConfig,
        }],
        occurrences,
    });
    const before = store.getOccurrences();
    const candidate = {
        ...originalConfig,
        slots: [
            { id: SLOT_1, isoWeekday: 1, startTime: "09:00", endTime: "12:00" },
            { id: SLOT_3, isoWeekday: 1, startTime: "20:00", endTime: "21:00" },
        ],
    };

    const payload = store.prepareApplyWeekPayload(
        PLAN_ITEM_ID,
        "2026-09-21",
        candidate,
    );

    assert.equal(payload.anchorDate, "2026-09-21");
    assert.deepEqual(payload.operations, [
        { type: "update", occurrenceId: occurrences[0].id, date: "2026-09-21", startTime: "09:00", endTime: "12:00" },
        { type: "delete", occurrenceId: occurrences[1].id },
        { type: "update", occurrenceId: occurrences[2].id, date: "2026-09-21", startTime: "20:00", endTime: "21:00" },
    ]);
    assert.deepEqual(store.getOccurrences(), before, "preparar el POST no hace optimistic mutation");
});

test("coordinador ejecuta POST → GET → hydrate para ambos alcances", async () => {
    for (const scope of ["week", "future"]) {
        const events = [];
        const serverState = { planItems: [], occurrences: [] };
        const coordinator = createRecurringScheduleMutationCoordinator({
            applyWeek: async (...args) => { events.push(["week", ...args]); return { weekStart: "2026-09-21" }; },
            applyFuture: async (...args) => { events.push(["future", ...args]); return { planItem: { id: PLAN_ITEM_ID } }; },
            loadPlannerState: async () => { events.push(["get"]); return serverState; },
            hydratePlannerState: (state) => { events.push(["hydrate", state]); return state; },
        });
        const outcome = await coordinator.submit(scope, PLAN_ITEM_ID, { payload: scope });
        assert.equal(outcome.status, "synced");
        assert.deepEqual(events.map(([name]) => name), [scope, "get", "hydrate"]);
    }
});

test("un coordinador compartido bloquea double-submit Week/Future", async () => {
    const pending = deferred();
    let weekCount = 0;
    let futureCount = 0;
    const coordinator = createRecurringScheduleMutationCoordinator({
        applyWeek: async () => { weekCount += 1; return pending.promise; },
        applyFuture: async () => { futureCount += 1; return pending.promise; },
        loadPlannerState: async () => ({ planItems: [], occurrences: [] }),
        hydratePlannerState: (state) => state,
    });

    const first = coordinator.submit("week", PLAN_ITEM_ID, {});
    const duplicate = coordinator.submit("week", PLAN_ITEM_ID, {});
    const competingFuture = coordinator.submit("future", PLAN_ITEM_ID, {});
    assert.equal(first, duplicate);
    assert.equal(first, competingFuture);
    assert.equal(weekCount, 1);
    assert.equal(futureCount, 0);
    pending.resolve({ weekStart: "2026-09-21" });
    assert.equal((await first).status, "synced");
});

test("POST confirmado + GET fallido reintenta solo GET", async () => {
    let postCount = 0;
    let getCount = 0;
    const coordinator = createRecurringScheduleMutationCoordinator({
        applyWeek: async () => { postCount += 1; return { weekStart: "2026-09-21" }; },
        applyFuture: async () => { postCount += 1; return { planItem: { id: PLAN_ITEM_ID } }; },
        loadPlannerState: async () => {
            getCount += 1;
            if (getCount === 1) throw new Error("refresh unavailable");
            return { planItems: [], occurrences: [] };
        },
        hydratePlannerState: (state) => state,
    });

    assert.equal((await coordinator.submit("future", PLAN_ITEM_ID, {})).status, "saved_refresh_error");
    assert.equal(coordinator.hasPendingRefresh(), true);
    assert.equal((await coordinator.submit("future", PLAN_ITEM_ID, {})).status, "synced");
    assert.equal(postCount, 1);
    assert.equal(getCount, 2);
});

test("success inválido se considera confirmado y recupera con GET", async () => {
    let postCount = 0;
    let getCount = 0;
    const apiMutation = () => applyFuture(PLAN_ITEM_ID, {}, {
        fetchImpl: async () => {
            postCount += 1;
            return response(200, { unexpected: true });
        },
    });
    const coordinator = createRecurringScheduleMutationCoordinator({
        applyWeek: apiMutation,
        applyFuture: apiMutation,
        loadPlannerState: async () => { getCount += 1; return { planItems: [], occurrences: [] }; },
        hydratePlannerState: (state) => state,
    });
    assert.equal((await coordinator.submit("future", PLAN_ITEM_ID, {})).status, "synced");
    assert.equal(postCount, 1);
    assert.equal(getCount, 1);
});

test("network, 400, 404 y 409 conservan códigos y feedback controlado", async () => {
    await assert.rejects(
        applyWeek(PLAN_ITEM_ID, {}, { fetchImpl: async () => { throw new Error("private"); } }),
        (error) => error instanceof PlannerApiError && error.code === "network_error",
    );
    for (const [status, code] of [
        [400, "invalid_payload"],
        [404, "plan_item_not_found"],
        [409, "history_frozen"],
        [409, "planning_stopped"],
        [409, "slot_date_conflict"],
        [409, "completed_conflict"],
        [409, "status_context_locked"],
        [409, "concurrent_modification"],
        [409, "priority_override_required"],
        [409, "unsupported_mode"],
    ]) {
        await assert.rejects(
            applyFuture(PLAN_ITEM_ID, {}, {
                fetchImpl: async () => response(status, {
                    status: "error",
                    code,
                    message: "Mensaje controlado.",
                }),
            }),
            (error) => error.code === code && error.details.status === status,
        );
        assert.notEqual(getRecurringScheduleMutationErrorMessage({ code }, "future"), "");
    }
});
