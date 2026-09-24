export function buildApplyFuturePayload(generationConfig, effectiveDate) {
    const common = {
        mode: generationConfig?.mode,
        startDate: effectiveDate,
        endDate: generationConfig?.endDate ?? null,
        indefinite: generationConfig?.indefinite,
    };
    if (generationConfig?.mode === "weekly") {
        return {
            futureConfig: {
                ...common,
                slots: generationConfig.slots.map(({ id, isoWeekday, startTime, endTime }) => ({
                    id,
                    isoWeekday,
                    startTime,
                    endTime,
                })),
            },
        };
    }
    if (generationConfig?.mode === "interval_days") {
        return {
            futureConfig: {
                ...common,
                intervalDays: generationConfig.intervalDays,
                slots: generationConfig.slots.map(({ id, startTime, endTime }) => ({
                    id,
                    startTime,
                    endTime,
                })),
            },
        };
    }
    if (generationConfig?.mode === "manual_dates") {
        return {
            futureConfig: {
                mode: "manual_dates",
                entries: generationConfig.entries.map(({ id, date, startTime, endTime }) => ({
                    id,
                    date,
                    startTime,
                    endTime,
                })),
            },
        };
    }
    throw new TypeError("Apply Future requiere una generationConfig soportada.");
}

export function createRecurringScheduleMutationCoordinator({
    applyWeek,
    applyFuture,
    loadPlannerState,
    hydratePlannerState,
}) {
    if (
        typeof applyWeek !== "function" ||
        typeof applyFuture !== "function" ||
        typeof loadPlannerState !== "function" ||
        typeof hydratePlannerState !== "function"
    ) {
        throw new TypeError("La planificación persistente requiere POST, GET e hidratación.");
    }

    let activeRequest = null;
    let refreshPending = false;

    async function refreshAfterConfirmedMutation(mutation = null) {
        try {
            const serverState = await loadPlannerState();
            const state = hydratePlannerState(serverState);
            refreshPending = false;
            return { status: "synced", mutation, state };
        } catch (error) {
            refreshPending = true;
            return { status: "saved_refresh_error", mutation, error };
        }
    }

    async function execute(scope, planItemId, payload) {
        let mutation;
        try {
            const mutate = scope === "week" ? applyWeek : applyFuture;
            mutation = await mutate(planItemId, payload);
        } catch (error) {
            if (error?.details?.mutationConfirmed) {
                return refreshAfterConfirmedMutation();
            }
            if (error?.code === "concurrent_conflict") {
                // El POST fue rechazado: leer el estado nuevo, sin reenviar el comando.
                try {
                    const state = hydratePlannerState(await loadPlannerState());
                    return { status: "review_required", error, state };
                } catch {
                    return { status: "mutation_error", error };
                }
            }
            return { status: "mutation_error", error };
        }
        return refreshAfterConfirmedMutation(mutation);
    }

    function submit(scope, planItemId, payload) {
        if (activeRequest) return activeRequest;
        if (refreshPending) return retryRefresh();
        if (!["week", "future"].includes(scope)) {
            return Promise.resolve({
                status: "mutation_error",
                error: new TypeError("El alcance de planificación no es válido."),
            });
        }
        activeRequest = execute(scope, planItemId, payload).finally(() => {
            activeRequest = null;
        });
        return activeRequest;
    }

    function retryRefresh() {
        if (activeRequest) return activeRequest;
        if (!refreshPending) {
            return Promise.resolve({ status: "nothing_to_refresh" });
        }
        activeRequest = refreshAfterConfirmedMutation().finally(() => {
            activeRequest = null;
        });
        return activeRequest;
    }

    return {
        submit,
        retryRefresh,
        hasPendingRefresh: () => refreshPending,
        isSubmitting: () => activeRequest !== null,
    };
}

const ERROR_MESSAGES = Object.freeze({
    invalid_identifier: "El identificador del registro no es válido.",
    invalid_payload: "La planificación enviada no es válida.",
    plan_item_not_found: "El registro ya no existe. Actualiza el planner antes de continuar.",
    occurrence_not_found: "Una aparición de la semana ya no existe. Actualiza el planner antes de continuar.",
    history_frozen: "La fecha seleccionada pertenece al historial congelado.",
    planning_stopped: "La planificación está detenida para la fecha solicitada.",
    deletion_status_locked: "El estado de una aparición impide modificar esa semana.",
    status_context_locked: "Una aparición está vinculada al contexto de prioridad y no puede modificarse.",
    schedule_conflict: "El estado final contiene horarios que se superponen.",
    slot_date_conflict: "Un GenerationSlot ya tiene una aparición en la fecha destino.",
    slot_identity_conflict: "Un UUID de GenerationSlot ya pertenece a otra configuración.",
    completed_conflict: "El horario contiene un registro completado y protegido.",
    priority_conflict: "La prioridad del registro no permite desplazar el conflicto.",
    priority_override_required: "La planificación requiere resolver un conflicto de prioridad. Esta mutación todavía no ofrece confirmación persistente.",
    concurrent_modification: "La planificación cambió durante la operación. Actualiza la vista e inténtalo nuevamente.",
    concurrent_conflict: "La agenda cambió durante la operación. Revisa el planner actualizado antes de intentarlo de nuevo.",
    segmented_recurring_date_move_requires_resolution: "La aparición segmentada no puede cambiar de fecha automáticamente. Conserva sus fragmentos y resuelve el cambio explícitamente.",
    temporal_reconciliation_required: "Una aparición histórica requiere reconciliación antes de cambiar su planificación.",
    mode_change_not_supported: "Apply Future debe conservar el modo recurrente actual.",
    unsupported_mode: "Apply Future no está disponible para fechas manuales.",
    persisted_state_invalid: "El estado persistido no es válido. Actualiza el planner antes de continuar.",
    database_unavailable: "No fue posible completar la operación en PostgreSQL.",
});

export function getRecurringScheduleMutationErrorMessage(error, scope) {
    if (error?.code === "network_error") {
        return "No se pudo conectar con el backend. La planificación no cambió en la vista.";
    }
    if (error?.code === "segmented_recurring_resize_requires_resolution") {
        const affected = error.details?.occurrences ?? [];
        const ranges = affected.map((item) =>
            `${item.date} ${item.startTime}–${item.endTime} → ${item.requestedStartTime}–${item.requestedEndTime}`);
        return `La segmentación existente requiere resolución estructural; no se escaló ni reinició. ${ranges.join("; ")}`.trim();
    }
    if (error?.code === "recurring_schedule_conflict") {
        const blockers = error.details?.blockers ?? [];
        const ranges = blockers.map((item) =>
            `${item.date} ${item.startTime}–${item.endTime} (${item.status})`);
        return `La planificación se cruza con segments ocupantes; no se modificó ningún blocker. ${ranges.join("; ")}`.trim();
    }
    if (ERROR_MESSAGES[error?.code]) return ERROR_MESSAGES[error.code];
    return scope === "week"
        ? "No se pudo aplicar la planificación a esta semana."
        : "No se pudo aplicar la planificación futura.";
}
