const RESOLUTION_REQUIRED = "segment_conflict_resolution_required";
const CONFIRMABLE_EFFECTS = new Set([
    "trim_segment", "split_segment", "cancel_segment", "interrupt_in_progress",
]);
const UNSUPPORTED = new Set([
    "segment_resolution_undefined",
    "multiple_source_resolution_unavailable",
    "conflict_resolution_frozen",
    "history_frozen",
]);

export function blockerKey(blocker) {
    return `${blocker.occurrenceId}:${blocker.segmentId}`;
}

export function buildConflictResolution(conflicts, realizedAcknowledgements = new Set()) {
    if (!Array.isArray(conflicts) || conflicts.length === 0
        || conflicts.some(({ resolutionKind }) => !CONFIRMABLE_EFFECTS.has(resolutionKind))) {
        throw new TypeError("No hay una resolución confirmable.");
    }
    return {
        confirmations: conflicts.map(({ blocker, requiresRealizedTimeConfirmation }) => {
            if (requiresRealizedTimeConfirmation && !realizedAcknowledgements.has(blockerKey(blocker))) {
                throw new TypeError("Cada corrección de tiempo realizado requiere aceptación explícita.");
            }
            return {
                blocker: {
                    occurrenceId: blocker.occurrenceId,
                    segmentId: blocker.segmentId,
                    startTime: blocker.startTime,
                    endTime: blocker.endTime,
                    status: blocker.status,
                },
                confirmed: true,
                ...(requiresRealizedTimeConfirmation ? { confirmRealizedTimeCorrection: true } : {}),
            };
        }),
    };
}

export function createSegmentConflictMutationCoordinator({
    executeCommand, loadPlannerState, hydratePlannerState,
}) {
    if ([executeCommand, loadPlannerState, hydratePlannerState].some((method) => typeof method !== "function")) {
        throw new TypeError("La mutación requiere comando, GET e hidratación.");
    }
    let activeRequest = null;
    let pending = null;
    let refreshPending = null;

    async function refresh(kind, mutation = null, error = null) {
        try {
            const state = hydratePlannerState(await loadPlannerState());
            refreshPending = null;
            return { status: kind === "confirmed" ? "synced" : "review_required", state, mutation, error };
        } catch (refreshError) {
            refreshPending = kind;
            return {
                status: kind === "confirmed" ? "saved_refresh_error" : "unknown_result",
                error: refreshError,
            };
        }
    }

    async function execute(command, conflictResolution = null) {
        try {
            const mutation = await executeCommand(command, conflictResolution);
            pending = null;
            return refresh("confirmed", mutation);
        } catch (error) {
            if (error?.details?.mutationConfirmed) {
                pending = null;
                return refresh("confirmed");
            }
            if (error?.code === RESOLUTION_REQUIRED && error?.details?.conflicts?.length) {
                pending = { command, conflicts: structuredClone(error.details.conflicts) };
                return { status: "conflict_required", conflicts: structuredClone(pending.conflicts), error };
            }
            if (error?.code === "conflict_resolution_stale") {
                pending = null;
                const refreshed = await refresh("review", null, error);
                return refreshed.status === "review_required"
                    ? { ...refreshed, status: "stale" } : refreshed;
            }
            if (error?.code === "network_error") {
                pending = null;
                return refresh("review", null, error);
            }
            if (UNSUPPORTED.has(error?.code)) {
                pending = null;
                return { status: "unsupported", error };
            }
            return { status: "mutation_error", error };
        }
    }

    function run(work) {
        if (activeRequest) return activeRequest;
        activeRequest = work().finally(() => { activeRequest = null; });
        return activeRequest;
    }

    return {
        submit(command) {
            if (activeRequest) return activeRequest;
            if (refreshPending) return this.retryRefresh();
            if (pending) return Promise.resolve({ status: "conflict_required", conflicts: structuredClone(pending.conflicts) });
            // This copy is the source command for every confirmed retry; hydration cannot rewrite it.
            return run(() => execute(structuredClone(command)));
        },
        confirm(realizedAcknowledgements = new Set()) {
            if (activeRequest) return activeRequest;
            if (!pending) return Promise.resolve({ status: "nothing_to_confirm" });
            const current = pending;
            let confirmation;
            try {
                confirmation = buildConflictResolution(current.conflicts, realizedAcknowledgements);
            } catch (error) {
                return Promise.resolve({ status: "confirmation_invalid", error });
            }
            pending = null;
            return run(() => execute(current.command, confirmation));
        },
        cancel() { if (!activeRequest) pending = null; },
        retryRefresh() {
            if (activeRequest) return activeRequest;
            if (!refreshPending) return Promise.resolve({ status: "nothing_to_refresh" });
            return run(() => refresh(refreshPending));
        },
        isSubmitting: () => activeRequest !== null,
        hasPendingConflict: () => pending !== null,
        hasPendingRefresh: () => refreshPending !== null,
    };
}
