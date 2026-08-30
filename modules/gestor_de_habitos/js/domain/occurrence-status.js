export const occurrenceStatuses = Object.freeze([
    "pending",
    "in_progress",
    "completed",
    "not_completed",
    "not_finished",
    "cancelled",
]);

export const statusDefinitions = Object.freeze({
    pending: { symbol: "□", label: "Pendiente", color: "var(--pending)" },
    in_progress: { symbol: "◷", label: "En progreso", color: "var(--in-progress)" },
    completed: { symbol: "✓", label: "Completada", color: "var(--completed)" },
    not_completed: { symbol: "✕", label: "No realizada", color: "var(--not-completed)" },
    not_finished: { symbol: "◷", modifier: "!", label: "No terminada", color: "var(--in-progress)" },
    cancelled: { symbol: "⚠", label: "Cancelada", color: "var(--cancelled)" },
});

export function isValidOccurrenceStatus(status) {
    return occurrenceStatuses.includes(status);
}

export function blocksSchedule(occurrence) {
    return ["pending", "in_progress", "completed"].includes(occurrence.status);
}

export function getNextStatus(currentStatus) {
    const currentIndex = occurrenceStatuses.indexOf(currentStatus);
    const safeIndex = currentIndex === -1 ? 0 : currentIndex;
    return occurrenceStatuses[(safeIndex + 1) % occurrenceStatuses.length];
}

export function getStatusPresentation(status, planItemName, dateLabel, actionDescription = "Activar para cambiar estado.") {
    const safeStatus = statusDefinitions[status] ? status : "pending";
    const definition = statusDefinitions[safeStatus];
    return {
        status: safeStatus,
        ...definition,
        accessibleLabel: `${planItemName}, ${dateLabel}: ${definition.label}. ${actionDescription}`,
    };
}
