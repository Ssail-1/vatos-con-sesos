import { buildApiUrl, getApiBaseUrl } from "./api-config.js";

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

export function validatePlannerStateResponse(payload) {
    if (
        !isRecord(payload) ||
        !Array.isArray(payload.planItems) ||
        !Array.isArray(payload.occurrences) ||
        !payload.planItems.every(isRecord) ||
        !payload.occurrences.every(isRecord)
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

    let payload;
    try {
        payload = await response.json();
    } catch {
        throw new PlannerApiError("invalid_response", "El backend devolvió JSON inválido.");
    }
    return validatePlannerStateResponse(payload);
}
