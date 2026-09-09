import { DELETION_REASONS } from "../domain/deletion-policy.js";
import { statusDefinitions } from "../domain/occurrence-status.js";
import { dateKeyToLocalDate, formatSelectedDate } from "../utils/date-time.js";

function formatDate(dateKey) {
    const date = dateKeyToLocalDate(dateKey);
    return date ? formatSelectedDate(date) : dateKey;
}

function getReasonMessage(decision) {
    if (decision.reason === DELETION_REASONS.FROZEN) {
        return "El historial congelado es de solo lectura.";
    }
    if (decision.reason === DELETION_REASONS.AMBIGUOUS) {
        return "Hay varias occurrences para este registro y fecha; seleccionarlas por fecha sería ambiguo.";
    }
    if (decision.reason === DELETION_REASONS.MISSING_OCCURRENCE) {
        return "No existe una aparición en esta fecha.";
    }
    if (decision.reason === DELETION_REASONS.MISSING_GENERATION_CONFIG) {
        return "Este registro no tiene una configuración de planificación que pueda modificarse.";
    }
    if (decision.reason === DELETION_REASONS.ALREADY_STOPPED) {
        return `La planificación ya está detenida desde ${formatDate(decision.stoppedFromDate)}; no se reactivará ni se extenderá.`;
    }
    if (decision.reason === DELETION_REASONS.PROTECTED_STATUS) {
        const statusLabel = statusDefinitions[decision.occurrence?.status]?.label ?? "histórico";
        return `El estado ${statusLabel} conserva historia y no permite eliminar esta aparición.`;
    }
    return "La operación no está disponible.";
}

export function createDeletionDialogView({
    dialog,
    summary,
    deleteOccurrenceButton,
    deleteOccurrenceDetails,
    stopPlanningButton,
    stopPlanningDetails,
    errorRegion,
    backButton,
    fallbackFocusElement,
}) {
    let currentOptions = null;
    let openerElement = null;
    let deleteOccurrence = null;
    let stopPlanning = null;
    let completeOperation = null;
    let completedResult = null;

    function clearError() {
        errorRegion.hidden = true;
        errorRegion.textContent = "";
    }

    function render(options) {
        const dateLabel = formatDate(options.selectedDate);
        summary.textContent = `${options.planItem.name} · ${dateLabel}`;

        deleteOccurrenceButton.disabled = !options.individual.allowed;
        if (options.individual.allowed) {
            const occurrence = options.individual.occurrence;
            deleteOccurrenceDetails.textContent =
                `Horario ${occurrence.startTime}–${occurrence.endTime}. Esta aparición desaparecerá; el resto de la planificación permanecerá.`;
        } else {
            deleteOccurrenceDetails.textContent = getReasonMessage(options.individual);
        }

        stopPlanningButton.disabled = !options.stop.allowed;
        stopPlanningDetails.textContent = options.stop.allowed
            ? `Dejará de planificarse desde ${dateLabel}. El historial existente permanecerá y se retirarán las apariciones futuras elegibles.`
            : getReasonMessage(options.stop);
    }

    function run(action, returnValue) {
        clearError();
        try {
            completedResult = action();
            dialog.close(returnValue);
        } catch (error) {
            errorRegion.textContent = error.message;
            errorRegion.hidden = false;
            backButton.focus();
        }
    }

    deleteOccurrenceButton.addEventListener("click", () => {
        if (currentOptions?.individual.allowed) run(
            () => deleteOccurrence(currentOptions.individual.occurrence.id),
            "deleted_occurrence",
        );
    });
    stopPlanningButton.addEventListener("click", () => {
        if (currentOptions?.stop.allowed) run(
            () => stopPlanning(currentOptions.planItem.id, currentOptions.selectedDate),
            "stopped_planning",
        );
    });
    backButton.addEventListener("click", () => dialog.close("back"));

    dialog.addEventListener("keydown", (event) => {
        if (event.key !== "Tab") return;
        const focusableButtons = [deleteOccurrenceButton, stopPlanningButton, backButton]
            .filter((button) => !button.disabled);
        const firstButton = focusableButtons[0];
        const lastButton = focusableButtons.at(-1);
        const movingBeforeFirst = event.shiftKey && document.activeElement === firstButton;
        const movingAfterLast = !event.shiftKey && document.activeElement === lastButton;
        if (!movingBeforeFirst && !movingAfterLast) return;
        event.preventDefault();
        (event.shiftKey ? lastButton : firstButton).focus();
    });

    dialog.addEventListener("close", () => {
        const result = completedResult;
        const returnValue = dialog.returnValue;
        const onComplete = completeOperation;
        const opener = openerElement;
        currentOptions = null;
        openerElement = null;
        deleteOccurrence = null;
        stopPlanning = null;
        completeOperation = null;
        completedResult = null;
        clearError();

        if (["deleted_occurrence", "stopped_planning"].includes(returnValue)) {
            onComplete?.(result, returnValue);
        }
        queueMicrotask(() => {
            if (opener?.isConnected) opener.focus();
            else fallbackFocusElement.focus();
        });
    });

    return {
        open(options, { onDeleteOccurrence, onStopPlanning, onComplete }) {
            currentOptions = options;
            openerElement = document.activeElement;
            deleteOccurrence = onDeleteOccurrence;
            stopPlanning = onStopPlanning;
            completeOperation = onComplete;
            completedResult = null;
            clearError();
            render(options);
            dialog.returnValue = "";
            dialog.showModal();
            backButton.focus();
        },
    };
}
