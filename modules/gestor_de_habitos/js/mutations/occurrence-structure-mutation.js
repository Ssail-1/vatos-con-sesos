"use strict";

export function createOccurrenceStructureMutationCoordinator({
    translateOccurrence,
    replaceOccurrenceStructure,
    resetOccurrenceSegmentation,
    loadPlannerState,
    hydratePlannerState,
}) {
    const commands = {
        translate: translateOccurrence,
        structure: replaceOccurrenceStructure,
        reset: resetOccurrenceSegmentation,
    };
    if (Object.values(commands).some((command) => typeof command !== "function")
        || typeof loadPlannerState !== "function"
        || typeof hydratePlannerState !== "function") {
        throw new TypeError("La estructura requiere comandos, GET e hidratación.");
    }
    let activeRequest = null;
    let refreshPending = false;
    let commandConfirmed = false;

    async function refresh() {
        try {
            const state = hydratePlannerState(await loadPlannerState());
            const status = commandConfirmed ? "synced" : "review_required";
            refreshPending = false;
            commandConfirmed = false;
            return { status, state };
        } catch (error) {
            return { status: commandConfirmed ? "saved_refresh_error" : "unknown_result", error };
        }
    }

    async function execute(operation, occurrenceId, payload) {
        try {
            const command = commands[operation];
            if (!command) throw new TypeError("La operación estructural no es válida.");
            await command(occurrenceId, payload);
            commandConfirmed = true;
            refreshPending = true;
        } catch (error) {
            if (error?.details?.mutationConfirmed) {
                commandConfirmed = true;
                refreshPending = true;
            } else if (error?.code === "network_error") {
                // Una respuesta de red perdida no demuestra que el comando falló.
                commandConfirmed = false;
                refreshPending = true;
                return { status: "unknown_result", error };
            } else {
                return { status: "mutation_error", error };
            }
        }
        return refresh();
    }

    function submit(operation, occurrenceId, payload) {
        if (activeRequest) return activeRequest;
        if (refreshPending) return retryRefresh();
        activeRequest = execute(operation, occurrenceId, payload).finally(() => {
            activeRequest = null;
        });
        return activeRequest;
    }

    function retryRefresh() {
        if (activeRequest) return activeRequest;
        if (!refreshPending) return Promise.resolve({ status: "nothing_to_refresh" });
        activeRequest = refresh().finally(() => { activeRequest = null; });
        return activeRequest;
    }

    return {
        submit,
        retryRefresh,
        isSubmitting: () => activeRequest !== null,
        hasPendingRefresh: () => refreshPending,
    };
}

const ERROR_MESSAGES = Object.freeze({
    occurrence_structure_conflict: "La estructura ocupa horarios de otros segments. Ajusta esta aparición y vuelve a guardar.",
    occurrence_translate_duration_mismatch: "Mover toda la aparición requiere conservar su duración. Para cambiarla usa Guardar estructura.",
    history_frozen: "Esta aparición pertenece al historial congelado y es de solo lectura.",
    temporal_reconciliation_required: "El historial requiere reconciliación. Recarga el planner, revisa la aparición y vuelve a intentarlo.",
    concurrent_conflict: "La agenda cambió mientras editabas. Revisa o actualiza el planner antes de preparar otro cambio.",
    occurrence_not_found: "La aparición ya no existe. Actualiza el planner.",
    persisted_state_invalid: "El estado persistido no es válido. No se intentó repararlo localmente.",
    database_unavailable: "PostgreSQL no pudo guardar la estructura. Se conserva tu borrador.",
});

export function getOccurrenceStructureErrorMessage(error) {
    return ERROR_MESSAGES[error?.code]
        ?? error?.message
        ?? "No se pudo guardar la estructura. Se conserva tu borrador.";
}
