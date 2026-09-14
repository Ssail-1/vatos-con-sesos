const UUID_V4_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function isGenerationSlotId(value) {
    return typeof value === "string" && UUID_V4_PATTERN.test(value);
}

export function createGenerationSlotId() {
    if (typeof globalThis.crypto?.randomUUID === "function") {
        return globalThis.crypto.randomUUID();
    }

    const bytes = new Uint8Array(16);
    if (typeof globalThis.crypto?.getRandomValues === "function") {
        globalThis.crypto.getRandomValues(bytes);
    } else {
        for (let index = 0; index < bytes.length; index += 1) {
            bytes[index] = Math.floor(Math.random() * 256);
        }
    }
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hexadecimal = [...bytes].map((value) => value.toString(16).padStart(2, "0")).join("");
    return [
        hexadecimal.slice(0, 8),
        hexadecimal.slice(8, 12),
        hexadecimal.slice(12, 16),
        hexadecimal.slice(16, 20),
        hexadecimal.slice(20),
    ].join("-");
}

export function compareGenerationSlots(first, second) {
    return (
        (first.isoWeekday ?? 0) - (second.isoWeekday ?? 0) ||
        (first.date ?? "").localeCompare(second.date ?? "") ||
        String(first.startTime ?? "").localeCompare(String(second.startTime ?? "")) ||
        String(first.endTime ?? "").localeCompare(String(second.endTime ?? "")) ||
        String(first.id ?? "").localeCompare(String(second.id ?? ""))
    );
}

export function cloneGenerationConfig(config) {
    if (config === null) return null;
    const controls = {
        ...(config.excludedDates ? { excludedDates: [...config.excludedDates] } : {}),
        ...(config.stoppedFromDate ? { stoppedFromDate: config.stoppedFromDate } : {}),
    };
    if (config.mode === "manual_dates") {
        return {
            ...config,
            ...controls,
            entries: Array.isArray(config.entries)
                ? config.entries.map((entry) => ({ ...entry }))
                : config.entries,
        };
    }
    return {
        ...config,
        ...controls,
        slots: Array.isArray(config.slots)
            ? config.slots.map((slot) => ({ ...slot }))
            : config.slots,
    };
}
