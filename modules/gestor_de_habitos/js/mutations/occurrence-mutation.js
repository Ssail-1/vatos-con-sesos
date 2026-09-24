export function createOccurrenceMutationCoordinator({
    mutateOccurrence,
    loadPlannerState,
    hydratePlannerState,
    refreshAfterMutationError = false,
}) {
    if (
        typeof mutateOccurrence !== "function" ||
        typeof loadPlannerState !== "function" ||
        typeof hydratePlannerState !== "function"
    ) {
        throw new TypeError("La mutación persistente requiere mutation, GET e hidratación.");
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

    async function execute(...args) {
        let mutation;
        try {
            mutation = await mutateOccurrence(...args);
        } catch (error) {
            if (error?.details?.mutationConfirmed) {
                return refreshAfterConfirmedMutation();
            }
            if (!refreshAfterMutationError) return { status: "mutation_error", error };
            try {
                const serverState = await loadPlannerState();
                const state = hydratePlannerState(serverState);
                return { status: "mutation_error", error, state };
            } catch (refreshError) {
                return {
                    status: "mutation_error_refresh_error",
                    error,
                    refreshError,
                };
            }
        }
        return refreshAfterConfirmedMutation(mutation);
    }

    function submit(...args) {
        if (activeRequest) return activeRequest;
        if (refreshPending) return retryRefresh();
        activeRequest = execute(...args).finally(() => {
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

const OCCURRENCE_ERROR_MESSAGES = Object.freeze({
    invalid_payload: "La fecha o el horario enviados no son válidos.",
    occurrence_not_found: "La aparición ya no existe. Actualiza el planner para ver el estado actual.",
    history_frozen: "Esta aparición pertenece al historial congelado y es de solo lectura.",
    last_manual_entry: "No se puede eliminar la última fecha manual del registro.",
    status_context_locked: "La aparición está vinculada al contexto de prioridad de otro registro y no puede modificarse.",
    deletion_status_locked: "El estado o contexto de esta aparición no permite eliminarla.",
    concurrent_conflict: "El planner cambió durante la operación. Actualiza la vista antes de intentarlo nuevamente.",
    concurrent_modification: "El planner cambió durante la operación. Actualiza la vista antes de intentarlo nuevamente.",
    priority_override_required: "La edición requiere resolver un conflicto de prioridad. La confirmación persistente para PATCH aún no está disponible.",
    priority_conflict: "La prioridad de esta aparición no permite desplazar el registro en conflicto.",
    completed_conflict: "El horario contiene un registro completado y protegido.",
    slot_date_conflict: "Ese horario o slot ya tiene una aparición en la fecha destino.",
    planning_stopped: "La planificación está detenida para la fecha solicitada.",
    persisted_state_invalid: "El estado persistido no es válido. Actualiza el planner antes de continuar.",
    database_unavailable: "No fue posible completar la operación en PostgreSQL.",
});

export function getOccurrenceMutationErrorMessage(error, operation = "update") {
    if (error?.code === "network_error") {
        return "No se pudo conectar con el backend. La aparición no se modificó en la vista.";
    }
    if (OCCURRENCE_ERROR_MESSAGES[error?.code]) {
        return OCCURRENCE_ERROR_MESSAGES[error.code];
    }
    return operation === "delete"
        ? "No se pudo eliminar la aparición. Inténtalo nuevamente."
        : "No se pudo guardar la aparición. Inténtalo nuevamente.";
}

const SEGMENT_ERROR_MESSAGES = Object.freeze({
    invalid_payload: "El estado enviado no es válido. Actualiza el planner.",
    segment_not_found: "El segment ya no existe. Actualiza el planner.",
    history_frozen: "Este segment pertenece al historial congelado y es de solo lectura.",
    segment_status_not_allowed: "Ese estado no está permitido en la fecha del segment.",
    segment_not_ended: "El segment todavía no termina; no puede marcarse como completado.",
    temporal_reconciliation_required: "El historial requiere reconciliación. Recarga el planner y vuelve a intentar el cambio; no se modificaron otros segments.",
    segment_status_conflict: "El estado solicitado ocuparía un horario ya reservado por otro segment. No se modificó ningún registro.",
    concurrent_conflict: "La agenda cambió durante la operación. Recarga el planner antes de volver a intentarlo.",
    persisted_state_invalid: "El estado persistido no es válido. No se guardó el cambio.",
    database_unavailable: "No fue posible completar el cambio en PostgreSQL.",
});

export function getSegmentStatusMutationErrorMessage(error) {
    if (error?.code === "network_error") {
        return "No se pudo conectar con el backend. El estado visible no se modificó.";
    }
    return SEGMENT_ERROR_MESSAGES[error?.code]
        ?? "No se pudo cambiar el estado del segment. Inténtalo nuevamente.";
}
