export function createPlannerBootstrap({
    reconcilePlanner,
    loadPlannerState,
    hydratePlannerState,
    onLoading = () => {},
    onReady = () => {},
    onError = () => {},
}) {
    if (typeof reconcilePlanner !== "function" || typeof loadPlannerState !== "function" || typeof hydratePlannerState !== "function") {
        throw new TypeError("El bootstrap requiere reconciliación, carga e hidratación del planner.");
    }

    let inFlight = null;

    function load() {
        if (inFlight) return inFlight;
        onLoading();
        inFlight = (async () => {
            try {
                await reconcilePlanner();
                const serverState = await loadPlannerState();
                const hydratedState = hydratePlannerState(serverState);
                onReady(hydratedState);
                return { status: "ready", state: hydratedState };
            } catch (error) {
                onError(error);
                return { status: "error", error };
            } finally {
                inFlight = null;
            }
        })();
        return inFlight;
    }

    return {
        start: load,
        retry: load,
    };
}
