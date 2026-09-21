import { buildApiUrl, getApiBaseUrl } from "./api-config.js";
import {
    CONFLICT_REASONS,
    getSegmentValidationError,
    LAST_CONFLICT_ACTIONS,
    ORIGIN_REASONS,
} from "../domain/occurrence-segments.js";
import { isGenerationSlotId } from "../domain/generation-slots.js";
import { isValidOccurrenceStatus } from "../domain/occurrence-status.js";
import { isValidDateKey, isValidTimeRange } from "../utils/date-time.js";

export class PlannerApiError extends Error {
    constructor(code, message, details = {}) {
        super(message);
        this.name = "PlannerApiError";
        this.code = code;
        this.details = details;
    }
}

function isRecord(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isConflict(value) {
    return isRecord(value) &&
        typeof value.occurrenceId === "string" &&
        typeof value.planItemId === "string" &&
        typeof value.date === "string" &&
        typeof value.startTime === "string" &&
        typeof value.endTime === "string" &&
        typeof value.status === "string";
}

function isOptionalEnum(value, allowedValues) {
    return value === undefined || allowedValues.includes(value);
}

function isValidConflictContext(value) {
    return value === undefined || (
        isRecord(value)
        && CONFLICT_REASONS.includes(value.reason)
        && typeof value.sourceOccurrenceId === "string"
        && Boolean(value.sourceOccurrenceId)
    );
}

function isPersistedOccurrence(value) {
    return isRecord(value)
        && typeof value.id === "string"
        && Boolean(value.id)
        && typeof value.planItemId === "string"
        && Boolean(value.planItemId)
        && isValidDateKey(value.date)
        && isValidTimeRange(value.startTime, value.endTime)
        && isValidOccurrenceStatus(value.status)
        && (
            value.sourceGenerationSlotId === undefined
            || isGenerationSlotId(value.sourceGenerationSlotId)
        )
        && isValidConflictContext(value.conflictContext)
        && isOptionalEnum(value.originReason, ORIGIN_REASONS)
        && isOptionalEnum(value.lastConflictAction, LAST_CONFLICT_ACTIONS)
        && getSegmentValidationError(value) === null;
}

async function readJson(response) {
    try {
        return await response.json();
    } catch {
        throw new PlannerApiError("invalid_response", "El backend devolvió JSON inválido.");
    }
}

export function validatePlannerStateResponse(payload) {
    if (
        !isRecord(payload) ||
        !Array.isArray(payload.planItems) ||
        !Array.isArray(payload.occurrences) ||
        !payload.planItems.every(isRecord) ||
        !payload.occurrences.every(isPersistedOccurrence)
    ) {
        throw new PlannerApiError(
            "invalid_response",
            "La respuesta del planner no cumple el contrato esperado.",
        );
    }
    const occurrenceIds = new Set(payload.occurrences.map(({ id }) => id));
    const segmentIds = payload.occurrences.flatMap(
        ({ segments }) => segments.map(({ id }) => id),
    );
    const contextsAreResolvable = payload.occurrences.every(({ id, conflictContext }) => (
        !conflictContext || (
            conflictContext.sourceOccurrenceId !== id
            && occurrenceIds.has(conflictContext.sourceOccurrenceId)
        )
    ));
    if (
        occurrenceIds.size !== payload.occurrences.length
        || new Set(segmentIds).size !== segmentIds.length
        || !contextsAreResolvable
    ) {
        throw new PlannerApiError(
            "invalid_response",
            "La respuesta del planner no cumple el contrato esperado.",
        );
    }
    return payload;
}

export async function fetchPlannerState({
    fetchImpl = globalThis.fetch,
    baseUrl = getApiBaseUrl(),
} = {}) {
    if (typeof fetchImpl !== "function") {
        throw new PlannerApiError("network_error", "No existe un cliente HTTP disponible.");
    }

    let response;
    try {
        response = await fetchImpl(buildApiUrl("/api/planner-state", baseUrl), {
            method: "GET",
            headers: { Accept: "application/json" },
        });
    } catch {
        throw new PlannerApiError("network_error", "No fue posible conectar con el backend.");
    }

    if (!response?.ok) {
        throw new PlannerApiError(
            "http_error",
            "El backend no pudo cargar el planner.",
            { status: Number.isInteger(response?.status) ? response.status : null },
        );
    }

    const payload = await readJson(response);
    return validatePlannerStateResponse(payload);
}

export async function createPlanItem(payload, {
    fetchImpl = globalThis.fetch,
    baseUrl = getApiBaseUrl(),
} = {}) {
    if (typeof fetchImpl !== "function") {
        throw new PlannerApiError("network_error", "No existe un cliente HTTP disponible.");
    }

    let response;
    try {
        response = await fetchImpl(buildApiUrl("/api/plan-items", baseUrl), {
            method: "POST",
            headers: {
                Accept: "application/json",
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });
    } catch {
        throw new PlannerApiError("network_error", "No fue posible conectar con el backend.");
    }

    let responsePayload;
    try {
        responsePayload = await readJson(response);
    } catch (error) {
        if (response?.ok) error.details.mutationConfirmed = true;
        throw error;
    }

    if (!response?.ok) {
        const serverCode = isRecord(responsePayload) && typeof responsePayload.code === "string"
            ? responsePayload.code
            : "http_error";
        const conflicts = isRecord(responsePayload) && Array.isArray(responsePayload.conflicts)
            && responsePayload.conflicts.every(isConflict)
            ? responsePayload.conflicts.map((conflict) => ({ ...conflict }))
            : [];
        throw new PlannerApiError(
            serverCode,
            isRecord(responsePayload) && typeof responsePayload.message === "string"
                ? responsePayload.message
                : "El backend no pudo crear el registro.",
            {
                status: Number.isInteger(response?.status) ? response.status : null,
                conflicts,
            },
        );
    }

    if (
        !isRecord(responsePayload) ||
        !isRecord(responsePayload.planItem) ||
        !Array.isArray(responsePayload.occurrences) ||
        !responsePayload.occurrences.every(isRecord)
    ) {
        throw new PlannerApiError(
            "invalid_response",
            "La creación fue aceptada, pero su respuesta no cumple el contrato esperado.",
            { mutationConfirmed: true, status: response.status },
        );
    }
    return responsePayload;
}

async function mutateOccurrence(method, occurrenceId, payload, {
    fetchImpl = globalThis.fetch,
    baseUrl = getApiBaseUrl(),
} = {}) {
    if (typeof fetchImpl !== "function") {
        throw new PlannerApiError("network_error", "No existe un cliente HTTP disponible.");
    }

    let response;
    try {
        response = await fetchImpl(
            buildApiUrl(`/api/occurrences/${encodeURIComponent(occurrenceId)}`, baseUrl),
            {
                method,
                headers: {
                    Accept: "application/json",
                    ...(payload === undefined ? {} : { "Content-Type": "application/json" }),
                },
                ...(payload === undefined ? {} : { body: JSON.stringify(payload) }),
            },
        );
    } catch {
        throw new PlannerApiError("network_error", "No fue posible conectar con el backend.");
    }

    let responsePayload;
    try {
        responsePayload = await readJson(response);
    } catch (error) {
        if (response?.ok) error.details.mutationConfirmed = true;
        throw error;
    }

    if (!response?.ok) {
        const serverCode = isRecord(responsePayload) && typeof responsePayload.code === "string"
            ? responsePayload.code
            : "http_error";
        throw new PlannerApiError(
            serverCode,
            isRecord(responsePayload) && typeof responsePayload.message === "string"
                ? responsePayload.message
                : "El backend no pudo modificar la occurrence.",
            { status: Number.isInteger(response?.status) ? response.status : null },
        );
    }

    const validPatch = method === "PATCH"
        && isRecord(responsePayload)
        && isRecord(responsePayload.occurrence)
        && typeof responsePayload.occurrence.id === "string";
    const validDelete = method === "DELETE"
        && isRecord(responsePayload)
        && typeof responsePayload.deletedOccurrenceId === "string";
    if (!validPatch && !validDelete) {
        throw new PlannerApiError(
            "invalid_response",
            "La mutación fue aceptada, pero su respuesta no cumple el contrato esperado.",
            { mutationConfirmed: true, status: response.status },
        );
    }
    return responsePayload;
}

export function updateOccurrence(occurrenceId, payload, options = {}) {
    return mutateOccurrence("PATCH", occurrenceId, payload, options);
}

export function deleteOccurrence(occurrenceId, options = {}) {
    return mutateOccurrence("DELETE", occurrenceId, undefined, options);
}

async function mutateRecurringSchedule(operation, planItemId, payload, {
    fetchImpl = globalThis.fetch,
    baseUrl = getApiBaseUrl(),
} = {}) {
    if (typeof fetchImpl !== "function") {
        throw new PlannerApiError("network_error", "No existe un cliente HTTP disponible.");
    }

    const endpoint = operation === "week" ? "apply-week" : "apply-future";
    let response;
    try {
        response = await fetchImpl(
            buildApiUrl(`/api/plan-items/${encodeURIComponent(planItemId)}/${endpoint}`, baseUrl),
            {
                method: "POST",
                headers: {
                    Accept: "application/json",
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(payload),
            },
        );
    } catch {
        throw new PlannerApiError("network_error", "No fue posible conectar con el backend.");
    }

    let responsePayload;
    try {
        responsePayload = await readJson(response);
    } catch (error) {
        if (response?.ok) error.details.mutationConfirmed = true;
        throw error;
    }

    if (!response?.ok) {
        const serverCode = isRecord(responsePayload) && typeof responsePayload.code === "string"
            ? responsePayload.code
            : "http_error";
        throw new PlannerApiError(
            serverCode,
            isRecord(responsePayload) && typeof responsePayload.message === "string"
                ? responsePayload.message
                : "El backend no pudo aplicar la planificación.",
            { status: Number.isInteger(response?.status) ? response.status : null },
        );
    }

    const validWeek = operation === "week"
        && isRecord(responsePayload)
        && typeof responsePayload.weekStart === "string"
        && typeof responsePayload.weekEnd === "string"
        && Array.isArray(responsePayload.occurrences)
        && responsePayload.occurrences.every(isRecord);
    const validFuture = operation === "future"
        && isRecord(responsePayload)
        && isRecord(responsePayload.planItem)
        && typeof responsePayload.planItem.id === "string"
        && Array.isArray(responsePayload.occurrences)
        && responsePayload.occurrences.every(isRecord);
    if (!validWeek && !validFuture) {
        throw new PlannerApiError(
            "invalid_response",
            "La planificación fue aceptada, pero su respuesta no cumple el contrato esperado.",
            { mutationConfirmed: true, status: response.status },
        );
    }
    return responsePayload;
}

export function applyWeek(planItemId, payload, options = {}) {
    return mutateRecurringSchedule("week", planItemId, payload, options);
}

export function applyFuture(planItemId, payload, options = {}) {
    return mutateRecurringSchedule("future", planItemId, payload, options);
}
