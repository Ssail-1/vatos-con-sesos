import { DELETION_REASONS } from "../domain/deletion-policy.js";
import { statusDefinitions } from "../domain/occurrence-status.js";
import { dateKeyToLocalDate, formatSelectedDate } from "../utils/date-time.js";

function formatDate(dateKey) {
    const date = dateKeyToLocalDate(dateKey);
    return date ? formatSelectedDate(date) : dateKey;
}

function individualReason(decision) {
    if (decision.reason === DELETION_REASONS.FROZEN) return "El historial congelado es de solo lectura.";
    if (decision.reason === DELETION_REASONS.AMBIGUOUS) return "Selecciona una aparición concreta.";
    if (decision.reason === DELETION_REASONS.MISSING_OCCURRENCE) return "La aparición ya no existe.";
    if (decision.reason === DELETION_REASONS.PROTECTED_STATUS) {
        return `El estado ${statusDefinitions[decision.occurrence?.status]?.label ?? "histórico"} protege esta aparición.`;
    }
    return "La eliminación individual no está disponible.";
}

export function createDeletionDialogView({
    dialog, summary, deleteOccurrenceButton, deleteOccurrenceDetails,
    stopSlotButton, stopSlotDetails, stopPlanningButton, stopPlanningDetails,
    deleteFutureButton, deleteFutureDetails, confirmationRegion, confirmButton,
    retryButton, errorRegion, backButton, fallbackFocusElement,
}) {
    const scopedButtons = { slot: stopSlotButton, recurring: stopPlanningButton, future: deleteFutureButton };
    const initialLabels = new Map(
        [deleteOccurrenceButton, ...Object.values(scopedButtons)].map((button) => [button, button.textContent]),
    );
    let currentOptions = null;
    let callbacks = null;
    let opener = null;
    let selectedScope = null;
    let running = false;
    let recoveryOnly = false;
    let completedResult = null;

    function clearMessages() {
        errorRegion.hidden = true;
        errorRegion.textContent = "";
        confirmationRegion.hidden = true;
        confirmationRegion.textContent = "";
    }

    function setRunning(value) {
        running = value;
        deleteOccurrenceButton.disabled = value || recoveryOnly || !currentOptions?.individual.allowed;
        for (const [scope, button] of Object.entries(scopedButtons)) {
            button.disabled = value || recoveryOnly || !currentOptions?.actions[scope];
            button.textContent = value && selectedScope === scope ? "Aplicando…" : initialLabels.get(button);
        }
        deleteOccurrenceButton.textContent = value && selectedScope === "individual"
            ? "Eliminando…" : initialLabels.get(deleteOccurrenceButton);
        confirmButton.disabled = value;
        confirmButton.hidden = !selectedScope || selectedScope === "individual" || recoveryOnly;
        retryButton.hidden = !recoveryOnly;
        retryButton.disabled = value;
        backButton.disabled = value;
    }

    async function run(action, resultName) {
        if (running || recoveryOnly) return;
        errorRegion.hidden = true;
        setRunning(true);
        try {
            completedResult = await action();
            if (completedResult?.keepOpen) {
                errorRegion.textContent = completedResult.message;
                errorRegion.hidden = false;
                recoveryOnly = Boolean(completedResult.retryRefresh);
                selectedScope = null;
                return;
            }
            dialog.close(resultName);
        } catch (error) {
            errorRegion.textContent = error.message;
            errorRegion.hidden = false;
            selectedScope = null;
        } finally {
            if (dialog.open) {
                setRunning(false);
                (recoveryOnly ? retryButton : backButton).focus();
            }
        }
    }

    deleteOccurrenceButton.addEventListener("click", () => {
        if (!currentOptions?.individual.allowed) return;
        selectedScope = "individual";
        void run(() => callbacks.onDeleteOccurrence(currentOptions.individual.occurrence.id), "individual");
    });

    for (const [scope, button] of Object.entries(scopedButtons)) {
        button.addEventListener("click", () => {
            if (!currentOptions?.actions[scope] || running || recoveryOnly) return;
            selectedScope = scope;
            confirmationRegion.textContent = {
                slot: "Confirma: se conserva este día y los otros horarios; solo se retiran fechas posteriores de este mismo horario. Las apariciones manuales permanecen.",
                recurring: "Confirma: se conserva este día; se detienen todos los horarios recurrentes posteriores. Las apariciones manuales permanecen.",
                future: "Confirma la acción más amplia: se conserva este día; se detiene la recurrencia y se eliminan todas las apariciones posteriores, incluso las manuales.",
            }[scope];
            confirmationRegion.hidden = false;
            setRunning(false);
            confirmButton.focus();
        });
    }

    confirmButton.addEventListener("click", () => {
        if (!selectedScope || selectedScope === "individual" || running) return;
        const scope = selectedScope;
        void run(() => callbacks.onTerminate(currentOptions.selectedOccurrence.id, scope), scope);
    });
    retryButton.addEventListener("click", async () => {
        if (running || !recoveryOnly) return;
        setRunning(true);
        try {
            completedResult = await callbacks.onRetryRefresh();
            if (completedResult?.keepOpen) {
                errorRegion.textContent = completedResult.message;
                errorRegion.hidden = false;
            } else {
                dialog.close("recovered");
            }
        } catch (error) {
            errorRegion.textContent = error.message;
            errorRegion.hidden = false;
        } finally {
            if (dialog.open) setRunning(false);
        }
    });
    backButton.addEventListener("click", () => dialog.close("back"));

    dialog.addEventListener("keydown", (event) => {
        if (event.key !== "Tab") return;
        const focusable = [
            deleteOccurrenceButton,
            ...Object.values(scopedButtons),
            backButton,
            retryButton,
            confirmButton,
        ].filter((button) => !button.disabled && !button.hidden);
        const first = focusable[0];
        const last = focusable.at(-1);
        if (!first || !last) return;
        const wrapsBackward = event.shiftKey && document.activeElement === first;
        const wrapsForward = !event.shiftKey && document.activeElement === last;
        if (!wrapsBackward && !wrapsForward) return;
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
    });

    dialog.addEventListener("close", () => {
        const result = completedResult;
        const operation = dialog.returnValue;
        const onComplete = callbacks?.onComplete;
        const focusTarget = opener;
        currentOptions = null;
        callbacks = null;
        opener = null;
        selectedScope = null;
        completedResult = null;
        recoveryOnly = false;
        running = false;
        setRunning(false);
        clearMessages();
        if (!["back", ""].includes(operation)) onComplete?.(result, operation);
        queueMicrotask(() => (focusTarget?.isConnected ? focusTarget : fallbackFocusElement).focus());
    });

    return {
        open(options, actions) {
            currentOptions = options;
            callbacks = actions;
            opener = document.activeElement;
            selectedScope = null;
            recoveryOnly = false;
            completedResult = null;
            clearMessages();
            summary.textContent = `${options.planItem.name} · ${formatDate(options.selectedDate)} · aparición completa${options.selectedSegmentId ? " (segment seleccionado)" : ""}`;
            deleteOccurrenceDetails.textContent = options.individual.allowed
                ? "Solo se elimina esta aparición; el resto de la planificación permanece."
                : individualReason(options.individual);
            stopSlotDetails.textContent = options.actions.slot
                ? "Este día permanece; se detienen fechas posteriores de este horario, no los otros horarios ni las apariciones manuales."
                : "Solo disponible para una aparición de un horario recurrente.";
            stopPlanningDetails.textContent = options.actions.recurring
                ? "Este día permanece; se detienen todos los horarios recurrentes posteriores, no las apariciones manuales."
                : "No hay planificación recurrente aplicable desde este día.";
            deleteFutureDetails.textContent = options.actions.future
                ? "Este día permanece; se eliminan todas las apariciones posteriores, incluso las manuales."
                : "Selecciona una aparición de hoy o futura.";
            setRunning(false);
            dialog.returnValue = "";
            dialog.showModal();
            dialog.querySelector("#deletionDialogTitle").focus();
            dialog.scrollTop = 0;
        },
    };
}
