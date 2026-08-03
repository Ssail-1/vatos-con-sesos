const activityStates = ["pending", "in_progress", "completed", "not_completed", "cancelled"];

const statusDefinitions = {
    pending: {
        symbol: "□",
        label: "Pendiente",
        color: "var(--pending)",
    },
    in_progress: {
        symbol: "◷",
        label: "En progreso",
        color: "var(--in-progress)",
    },
    completed: {
        symbol: "✓",
        label: "Completada",
        color: "var(--completed)",
    },
    not_completed: {
        symbol: "✕",
        label: "No realizada",
        color: "var(--not-completed)",
    },
    cancelled: {
        symbol: "⚠",
        label: "Cancelada",
        color: "var(--cancelled)",
    },
};

function getNextStatus(currentStatus) {
    const currentIndex = activityStates.indexOf(currentStatus);
    const safeIndex = currentIndex === -1 ? 0 : currentIndex;
    return activityStates[(safeIndex + 1) % activityStates.length];
}

// Sincroniza todas las pistas visuales y accesibles cada vez que cambia un estado.
function updateStatusControl(button, status, activityName, dateLabel) {
    const safeStatus = statusDefinitions[status] ? status : "pending";
    const definition = statusDefinitions[safeStatus];
    const accessibleLabel = `${activityName}, ${dateLabel}: ${definition.label}. Activar para cambiar estado.`;

    button.dataset.status = safeStatus;
    button.textContent = definition.symbol;
    button.setAttribute("aria-label", accessibleLabel);
    button.title = accessibleLabel;
}
