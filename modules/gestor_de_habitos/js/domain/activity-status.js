export const activityStates = [
    "pending",
    "in_progress",
    "completed",
    "not_completed",
    "cancelled",
];

export const statusDefinitions = {
    pending: { symbol: "□", label: "Pendiente", color: "var(--pending)" },
    in_progress: { symbol: "◷", label: "En progreso", color: "var(--in-progress)" },
    completed: { symbol: "✓", label: "Completada", color: "var(--completed)" },
    not_completed: { symbol: "✕", label: "No realizada", color: "var(--not-completed)" },
    cancelled: { symbol: "⚠", label: "Cancelada", color: "var(--cancelled)" },
};

export function getNextStatus(currentStatus) {
    const currentIndex = activityStates.indexOf(currentStatus);
    const safeIndex = currentIndex === -1 ? 0 : currentIndex;
    return activityStates[(safeIndex + 1) % activityStates.length];
}

export function getStatusPresentation(status, activityName, dateLabel) {
    const safeStatus = statusDefinitions[status] ? status : "pending";
    const definition = statusDefinitions[safeStatus];

    return {
        status: safeStatus,
        ...definition,
        accessibleLabel: `${activityName}, ${dateLabel}: ${definition.label}. Activar para cambiar estado.`,
    };
}
