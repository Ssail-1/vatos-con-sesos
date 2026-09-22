import { blockerKey } from "../mutations/segment-conflict-mutation.js";

export const SEGMENT_CONFLICT_EFFECTS = Object.freeze({
    trim_segment: "Se ajustará el tramo ocupado; el segmento superviviente conservará su identidad.",
    split_segment: "El tramo ocupado se separará en dos segmentos de la misma aparición.",
    cancel_segment: "El segmento afectado quedará cancelado.",
    interrupt_in_progress: "La actividad en progreso se interrumpirá y el tramo realizado quedará como no finalizado.",
    undefined_in_progress: "Este caso en progreso todavía no tiene una resolución aprobada.",
});

export function getSegmentConflictEffect(resolutionKind) {
    return SEGMENT_CONFLICT_EFFECTS[resolutionKind] ?? "El backend no describió un resultado admitido.";
}

function statusLabel(status) {
    return ({
        pending: "pendiente", in_progress: "en progreso", completed: "completado",
        not_finished: "no finalizado", not_completed: "no completado", cancelled: "cancelado",
    })[status] ?? status;
}

export function createSegmentConflictDialogView({
    dialog, title, list, summary, errorRegion, backButton, confirmButton,
    getPlanItemName = () => null,
}) {
    let conflicts = [];
    let onConfirm = null;
    let onCancel = null;
    let onComplete = null;
    let opener = null;
    let busy = false;
    const acknowledgements = new Set();

    function canConfirm() {
        return conflicts.length > 0
            && conflicts.every(({ resolutionKind, blocker, requiresRealizedTimeConfirmation }) => (
                Object.hasOwn(SEGMENT_CONFLICT_EFFECTS, resolutionKind)
                && resolutionKind !== "undefined_in_progress"
                && (!requiresRealizedTimeConfirmation || acknowledgements.has(blockerKey(blocker)))
            ));
    }

    function updateControls() {
        confirmButton.disabled = busy || !canConfirm();
        backButton.disabled = busy;
        confirmButton.hidden = conflicts.some(({ resolutionKind }) => (
            !Object.hasOwn(SEGMENT_CONFLICT_EFFECTS, resolutionKind)
            || resolutionKind === "undefined_in_progress"
        ));
    }

    function renderConflicts() {
        acknowledgements.clear();
        const fragment = document.createDocumentFragment();
        conflicts.forEach(({ blocker, resolutionKind, requiredAuthorization, requiresRealizedTimeConfirmation }) => {
            const item = document.createElement("li");
            const heading = document.createElement("strong");
            const schedule = document.createElement("span");
            const effect = document.createElement("p");
            const authorization = document.createElement("p");
            const name = getPlanItemName(blocker.planItemId) || "Actividad no disponible";
            item.className = "segment-conflict-item";
            heading.textContent = name;
            schedule.textContent = `${blocker.date} · ${blocker.startTime}–${blocker.endTime} · ${statusLabel(blocker.status)}`;
            effect.textContent = getSegmentConflictEffect(resolutionKind);
            authorization.textContent = requiredAuthorization === "priority_override"
                ? "La prioridad favorece el cambio, pero debes autorizar su efecto sobre esta actividad."
                : "La prioridad no autoriza este cambio automáticamente; confirma que deseas modificar el tiempo ocupado.";
            item.append(heading, schedule, effect, authorization);
            if (requiresRealizedTimeConfirmation) {
                const label = document.createElement("label");
                const checkbox = document.createElement("input");
                label.className = "segment-conflict-realized";
                checkbox.type = "checkbox";
                label.append(checkbox, " Entiendo que esta acción corregirá tiempo ya registrado en esta actividad.");
                checkbox.addEventListener("change", () => {
                    const key = blockerKey(blocker);
                    if (checkbox.checked) acknowledgements.add(key);
                    else acknowledgements.delete(key);
                    updateControls();
                });
                item.append(label);
            }
            fragment.append(item);
        });
        list.replaceChildren(fragment);
        summary.textContent = conflicts.length === 1
            ? "Revisa el segmento afectado antes de continuar."
            : `Revisa los ${conflicts.length} segmentos afectados antes de continuar.`;
        errorRegion.hidden = true;
        errorRegion.textContent = "";
        confirmButton.textContent = conflicts.length === 1
            ? ({ split_segment: "Segmentar y continuar", trim_segment: "Ajustar y continuar",
                cancel_segment: "Cancelar segmento y continuar", interrupt_in_progress: "Interrumpir y continuar" })[conflicts[0].resolutionKind]
                ?? "Confirmar cambios y continuar"
            : "Confirmar cambios y continuar";
        updateControls();
    }

    function close() {
        if (dialog.open) dialog.close();
        if (opener?.isConnected) opener.focus();
        onConfirm = null;
        onCancel = null;
        onComplete = null;
        opener = null;
        conflicts = [];
        acknowledgements.clear();
    }

    function cancel() {
        if (busy || !dialog.open) return;
        const callback = onCancel;
        close();
        callback?.();
    }

    backButton.addEventListener("click", cancel);
    dialog.addEventListener("cancel", (event) => { event.preventDefault(); cancel(); });
    confirmButton.addEventListener("click", async () => {
        if (busy || !canConfirm()) return;
        busy = true;
        updateControls();
        try {
            const outcome = await onConfirm(new Set(acknowledgements));
            if (outcome?.status === "conflict_required") {
                conflicts = structuredClone(outcome.conflicts);
                renderConflicts();
                errorRegion.textContent = "La agenda cambió. Revisa de nuevo todos los conflictos actuales.";
                errorRegion.hidden = false;
            } else if (outcome?.status === "confirmation_invalid") {
                errorRegion.textContent = outcome.error.message;
                errorRegion.hidden = false;
            } else {
                const callback = onComplete;
                close();
                callback?.(outcome);
            }
        } catch (error) {
            errorRegion.textContent = error?.message ?? "No se pudo revisar el conflicto.";
            errorRegion.hidden = false;
        } finally {
            busy = false;
            updateControls();
        }
    });

    return {
        open({ intent, currentConflicts, focusElement, confirm, cancel: cancelCallback, complete }) {
            if (dialog.open) throw new Error("Ya existe una confirmación abierta.");
            conflicts = structuredClone(currentConflicts);
            opener = focusElement ?? document.activeElement;
            onConfirm = confirm;
            onCancel = cancelCallback;
            onComplete = complete;
            title.textContent = intent;
            renderConflicts();
            dialog.showModal();
            backButton.focus();
        },
        close,
        isOpen: () => dialog.open,
    };
}
