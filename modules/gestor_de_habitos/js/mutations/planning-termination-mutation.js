export function createPlanningTerminationMutationCoordinator({
    terminatePlanning,
    loadPlannerState,
    hydratePlannerState,
}) {
    let activeRequest = null;
    let refreshPending = false;

    async function refresh(mutation = null, uncertain = false) {
        try {
            const state = hydratePlannerState(await loadPlannerState());
            refreshPending = false;
            return { status: uncertain ? "review_required" : "synced", mutation, state };
        } catch (error) {
            refreshPending = true;
            return { status: uncertain ? "unknown_result" : "saved_refresh_error", error, mutation };
        }
    }

    async function execute(occurrenceId, scope) {
        try {
            return await refresh(await terminatePlanning(occurrenceId, scope));
        } catch (error) {
            if (error?.details?.mutationConfirmed) return refresh();
            if (error?.code === "network_error") return refresh(null, true);
            return { status: "mutation_error", error };
        }
    }

    function submit(occurrenceId, scope) {
        if (activeRequest) return activeRequest;
        if (refreshPending) return retryRefresh();
        activeRequest = execute(occurrenceId, scope).finally(() => { activeRequest = null; });
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
        hasPendingRefresh: () => refreshPending,
        isSubmitting: () => activeRequest !== null,
    };
}
