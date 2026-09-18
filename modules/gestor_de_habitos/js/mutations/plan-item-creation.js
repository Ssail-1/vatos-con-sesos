export function addPriorityOverride(planItemPayload, conflicts) {
    return {
        ...planItemPayload,
        priorityOverride: {
            confirmedOccurrenceIds: conflicts.map(({ occurrenceId }) => occurrenceId),
        },
    };
}

export function createPlanItemMutationCoordinator({
    postPlanItem,
    loadPlannerState,
    hydratePlannerState,
}) {
    if (
        typeof postPlanItem !== "function" ||
        typeof loadPlannerState !== "function" ||
        typeof hydratePlannerState !== "function"
    ) {
        throw new TypeError("La creación persistente requiere POST, GET e hidratación.");
    }

    let activeRequest = null;
    let refreshPending = false;

    async function refreshAfterConfirmedPost(creation = null) {
        try {
            const serverState = await loadPlannerState();
            const state = hydratePlannerState(serverState);
            refreshPending = false;
            return { status: "synced", creation, state };
        } catch (error) {
            refreshPending = true;
            return { status: "saved_refresh_error", creation, error };
        }
    }

    async function execute(payload) {
        let creation;
        try {
            creation = await postPlanItem(payload);
        } catch (error) {
            if (error?.details?.mutationConfirmed) {
                return refreshAfterConfirmedPost();
            }
            if (error?.code === "priority_override_required") {
                return {
                    status: "override_required",
                    conflicts: error.details?.conflicts ?? [],
                    error,
                };
            }
            return { status: "post_error", error };
        }
        return refreshAfterConfirmedPost(creation);
    }

    function submit(payload) {
        if (activeRequest) return activeRequest;
        if (refreshPending) return retryRefresh();
        activeRequest = execute(payload).finally(() => {
            activeRequest = null;
        });
        return activeRequest;
    }

    function retryRefresh() {
        if (activeRequest) return activeRequest;
        if (!refreshPending) {
            return Promise.resolve({ status: "nothing_to_refresh" });
        }
        activeRequest = refreshAfterConfirmedPost().finally(() => {
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
