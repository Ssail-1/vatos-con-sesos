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

function isSegmentConflict(value) {
    const blocker = value?.blocker;
    return isRecord(value) && isRecord(blocker)
        && ["occurrenceId", "segmentId", "planItemId"].every(
            (key) => typeof blocker[key] === "string" && Boolean(blocker[key]),
        )
        && isValidDateKey(blocker.date)
        && isValidTimeRange(blocker.startTime, blocker.endTime)
        && isValidOccurrenceStatus(blocker.status)
        && ["priority_override", "user_forced_override"].includes(value.requiredAuthorization)
        && typeof value.resolutionKind === "string"
        && typeof value.requiresRealizedTimeConfirmation === "boolean";
}

function conflictDetails(payload) {
    return isRecord(payload) && Array.isArray(payload.conflicts)
        && payload.conflicts.every(isSegmentConflict)
        ? payload.conflicts.map((conflict) => ({ ...conflict, blocker: { ...conflict.blocker } }))
        : [];
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
        const conflicts = conflictDetails(responsePayload);
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

const TERMINATION_PATHS = Object.freeze({
    slot: "stop-slot-after",
    recurring: "stop-recurring-after",
    future: "delete-future-after",
});

export async function terminatePlanningAfter(occurrenceId, scope, {
    fetchImpl = globalThis.fetch,
    baseUrl = getApiBaseUrl(),
} = {}) {
    if (!TERMINATION_PATHS[scope] || typeof occurrenceId !== "string" || !occurrenceId) {
        throw new PlannerApiError("invalid_payload", "La acción de planificación no es válida.");
    }
    if (typeof fetchImpl !== "function") {
        throw new PlannerApiError("network_error", "No existe un cliente HTTP disponible.");
    }
    let response;
    try {
        response = await fetchImpl(
            buildApiUrl(`/api/occurrences/${encodeURIComponent(occurrenceId)}/${TERMINATION_PATHS[scope]}`, baseUrl),
            { method: "POST", headers: { Accept: "application/json" } },
        );
    } catch {
        throw new PlannerApiError("network_error", "No fue posible conectar con el backend.");
    }
    let payload;
    try { payload = await readJson(response); }
    catch (error) {
        if (response?.ok) error.details.mutationConfirmed = true;
        throw error;
    }
    if (!response.ok) {
        throw new PlannerApiError(
            typeof payload?.code === "string" ? payload.code : "http_error",
            typeof payload?.message === "string" ? payload.message : "No se pudo completar la acción.",
            { status: response.status },
        );
    }
    if (
        !isRecord(payload) || payload.status !== "ok" || payload.scope !== scope
        || payload.selectedOccurrenceId !== occurrenceId
        || !isValidDateKey(payload.cutoffDate)
        || typeof payload.planItemId !== "string"
        || !Array.isArray(payload.deletedOccurrenceIds)
        || !payload.deletedOccurrenceIds.every((id) => typeof id === "string")
    ) {
        throw new PlannerApiError("invalid_response", "La acción se aceptó, pero la respuesta no es válida.",
            { mutationConfirmed: true, status: response.status });
    }
    return payload;
}

export async function updateSegmentStatus(segmentId, status, {
    fetchImpl = globalThis.fetch,
    baseUrl = getApiBaseUrl(),
} = {}) {
    if (typeof fetchImpl !== "function") {
        throw new PlannerApiError("network_error", "No existe un cliente HTTP disponible.");
    }
    let response;
    try {
        response = await fetchImpl(
            buildApiUrl(`/api/occurrence-segments/${encodeURIComponent(segmentId)}/status`, baseUrl),
            {
                method: "PATCH",
                headers: { Accept: "application/json", "Content-Type": "application/json" },
                body: JSON.stringify({ status }),
            },
        );
    } catch {
        throw new PlannerApiError("network_error", "No fue posible conectar con el backend.");
    }
    let payload;
    try {
        payload = await readJson(response);
    } catch (error) {
        if (response?.ok) error.details.mutationConfirmed = true;
        throw error;
    }
    if (!response?.ok) {
        throw new PlannerApiError(
            isRecord(payload) && typeof payload.code === "string" ? payload.code : "http_error",
            isRecord(payload) && typeof payload.message === "string"
                ? payload.message : "No se pudo cambiar el estado del segment.",
            {
                status: Number.isInteger(response?.status) ? response.status : null,
                blockers: isRecord(payload) && Array.isArray(payload.blockers)
                    ? payload.blockers.map((blocker) => ({ ...blocker })) : [],
            },
        );
    }
    if (
        !isRecord(payload) || payload.status !== "ok" ||
        typeof payload.segmentId !== "string" || payload.segmentId !== segmentId ||
        typeof payload.occurrenceId !== "string" ||
        payload.segmentStatus !== status || !isValidOccurrenceStatus(payload.occurrenceStatus)
    ) {
        throw new PlannerApiError(
            "invalid_response",
            "El cambio fue aceptado, pero su respuesta no cumple el contrato esperado.",
            { mutationConfirmed: true, status: response.status },
        );
    }
    return payload;
}

async function structuralCommand(occurrenceId, action, method, body, {
    fetchImpl = globalThis.fetch,
    baseUrl = getApiBaseUrl(),
} = {}) {
    if (typeof fetchImpl !== "function") {
        throw new PlannerApiError("network_error", "No existe un cliente HTTP disponible.");
    }
    let response;
    try {
        response = await fetchImpl(
            buildApiUrl(`/api/occurrences/${encodeURIComponent(occurrenceId)}/${action}`, baseUrl),
            {
                method,
                headers: { Accept: "application/json", "Content-Type": "application/json" },
                body: JSON.stringify(body),
            },
        );
    } catch {
        throw new PlannerApiError("network_error", "No fue posible conectar con el backend.");
    }
    let payload;
    try {
        payload = await readJson(response);
    } catch (error) {
        if (response?.ok) error.details.mutationConfirmed = true;
        throw error;
    }
    if (!response?.ok) {
        throw new PlannerApiError(
            isRecord(payload) && typeof payload.code === "string" ? payload.code : "http_error",
            isRecord(payload) && typeof payload.message === "string"
                ? payload.message : "No se pudo guardar la estructura de la aparición.",
            {
                status: Number.isInteger(response?.status) ? response.status : null,
                conflicts: conflictDetails(payload),
                blockers: isRecord(payload) && Array.isArray(payload.blockers)
                    ? payload.blockers.filter(isRecord).map((blocker) => ({ ...blocker })) : [],
            },
        );
    }
    if (
        !isRecord(payload) || payload.status !== "ok"
        || payload.occurrenceId !== occurrenceId
        || !isValidOccurrenceStatus(payload.occurrenceStatus)
        || !Array.isArray(payload.segmentIds)
        || !payload.segmentIds.length
        || !payload.segmentIds.every((id) => typeof id === "string" && Boolean(id))
    ) {
        throw new PlannerApiError(
            "invalid_response",
            "El comando fue aceptado, pero su respuesta no cumple el contrato esperado.",
            { mutationConfirmed: true, status: response.status },
        );
    }
    return payload;
}

export function translateOccurrence(occurrenceId, startTime, endTime, options = {}) {
    const { conflictResolution, ...requestOptions } = options;
    return structuralCommand(occurrenceId, "translate", "POST", {
        startTime, endTime,
        ...(conflictResolution ? { conflictResolution } : {}),
    }, requestOptions);
}

export function replaceOccurrenceStructure(occurrenceId, payload, options = {}) {
    return structuralCommand(occurrenceId, "structure", "PUT", payload, options);
}

export function resetOccurrenceSegmentation(occurrenceId, startTime, endTime, options = {}) {
    const { conflictResolution, ...requestOptions } = options;
    return structuralCommand(occurrenceId, "reset-segmentation", "POST", {
        startTime, endTime,
        ...(conflictResolution ? { conflictResolution } : {}),
    }, requestOptions);
}

export async function reconcilePlanner({
    fetchImpl = globalThis.fetch,
    baseUrl = getApiBaseUrl(),
} = {}) {
    if (typeof fetchImpl !== "function") {
        throw new PlannerApiError("network_error", "No existe un cliente HTTP disponible.");
    }
    let response;
    try {
        response = await fetchImpl(buildApiUrl("/api/planner/reconcile", baseUrl), {
            method: "POST",
            headers: { Accept: "application/json" },
        });
    } catch {
        throw new PlannerApiError("network_error", "No fue posible conectar con el backend.");
    }
    const payload = await readJson(response);
    if (!response?.ok) {
        throw new PlannerApiError(
            isRecord(payload) && typeof payload.code === "string" ? payload.code : "http_error",
            isRecord(payload) && typeof payload.message === "string"
                ? payload.message : "No se pudo reconciliar el planner.",
            { status: Number.isInteger(response?.status) ? response.status : null },
        );
    }
    if (
        !isRecord(payload) || payload.status !== "ok" ||
        !Number.isInteger(payload.updatedOccurrences) || payload.updatedOccurrences < 0 ||
        !Number.isInteger(payload.updatedSegments) || payload.updatedSegments < 0
    ) {
        throw new PlannerApiError("invalid_response", "La reconciliación devolvió una respuesta inválida.");
    }
    return payload;
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
        const details = { status: Number.isInteger(response?.status) ? response.status : null };
        if (serverCode === "segmented_recurring_resize_requires_resolution" && Array.isArray(responsePayload?.occurrences)) {
            details.occurrences = responsePayload.occurrences.filter((item) =>
                isRecord(item) && typeof item.occurrenceId === "string"
                && isValidDateKey(item.date)
                && isValidTimeRange(item.startTime, item.endTime)
                && isValidTimeRange(item.requestedStartTime, item.requestedEndTime));
        }
        if (serverCode === "recurring_schedule_conflict" && Array.isArray(responsePayload?.blockers)) {
            details.blockers = responsePayload.blockers.filter((item) =>
                isRecord(item) && typeof item.occurrenceId === "string"
                && typeof item.segmentId === "string" && typeof item.planItemId === "string"
                && isValidDateKey(item.date) && isValidTimeRange(item.startTime, item.endTime)
                && isValidOccurrenceStatus(item.status));
        }
        throw new PlannerApiError(
            serverCode,
            isRecord(responsePayload) && typeof responsePayload.message === "string"
                ? responsePayload.message
                : "El backend no pudo aplicar la planificación.",
            details,
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
