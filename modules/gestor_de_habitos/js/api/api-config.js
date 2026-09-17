const API_BASE_URL_PARAMETER = "apiBaseUrl";

function normalizeApiBaseUrl(value) {
    const url = new URL(value);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) {
        throw new TypeError("La URL base de la API no es válida.");
    }
    if (url.search || url.hash) {
        throw new TypeError("La URL base de la API no puede contener query ni fragmento.");
    }
    return url.href.replace(/\/$/, "");
}

export function getApiBaseUrl(locationRef = globalThis.location) {
    if (!locationRef?.href) return "";
    const pageUrl = new URL(locationRef.href);
    const override = pageUrl.searchParams.get(API_BASE_URL_PARAMETER)?.trim();
    return override ? normalizeApiBaseUrl(override) : "";
}

export function buildApiUrl(path, baseUrl = getApiBaseUrl()) {
    if (typeof path !== "string" || !path.startsWith("/")) {
        throw new TypeError("La ruta de API debe ser absoluta respecto del origen.");
    }
    return `${baseUrl}${path}`;
}
