import {
    addDraftSegment,
    buildOccurrenceStructurePayload,
    canTranslateOccurrenceDraft,
    createOccurrenceStructureDraft,
    draftStructuralDuration,
    orderedDraftSegments,
    removeDraftSegment,
    validateOccurrenceStructureDraft,
} from "../domain/occurrence-structure-draft.js";
import { getSelectableSegmentStatuses, statusDefinitions } from "../domain/occurrence-status.js";
import { getDateTemporalZone, TEMPORAL_ZONES } from "../domain/temporal-integrity.js";
import { calculateDuration } from "../utils/date-time.js";
import { getOccurrenceStructureErrorMessage } from "../mutations/occurrence-structure-mutation.js";

function timeField(labelText, value, onInput) {
    const label = document.createElement("label");
    const input = document.createElement("input");
    label.className = "form-field";
    label.textContent = labelText;
    input.type = "time";
    input.value = value;
    input.required = true;
    input.addEventListener("input", () => onInput(input.value));
    label.append(input);
    return { label, input };
}

export function createOccurrenceStructureEditorView({
    dialog, form, title, reference, startInput, endInput, segmentsContainer,
    duration, errorRegion, savingStatus, addButton, translateButton, resetButton,
    cancelButton, retryButton, saveButton, onCommand, onRetryRefresh,
    getCurrentDateKey, confirmReset = (message) => window.confirm(message),
    onRestoreFocus = () => {},
}) {
    let draft = null;
    let planItemName = "";
    let opener = null;
    let pending = false;
    let refreshPending = false;

    function showError(message, blockers = []) {
        const blockerText = blockers.length
            ? ` Bloqueos: ${blockers.map((blocker) => `${blocker.startTime}–${blocker.endTime} (${blocker.status})`).join(", ")}.`
            : "";
        errorRegion.textContent = message + blockerText;
        errorRegion.hidden = false;
    }

    function clearError() {
        errorRegion.textContent = "";
        errorRegion.hidden = true;
    }

    function updateControls() {
        const locked = pending || refreshPending;
        form.querySelectorAll("input, select").forEach((control) => { control.disabled = locked; });
        addButton.disabled = locked;
        saveButton.disabled = locked;
        translateButton.disabled = locked || !draft || !canTranslateOccurrenceDraft(draft);
        resetButton.disabled = locked;
        cancelButton.disabled = locked;
        retryButton.hidden = !refreshPending;
        retryButton.disabled = pending;
        savingStatus.hidden = !pending;
        segmentsContainer.querySelectorAll(".structure-remove-button").forEach((button) => {
            button.disabled = locked || draft.segments.length <= 1;
        });
        duration.textContent = `Duración de los segments: ${draftStructuralDuration(draft)}`;
    }

    function renderSegments(focusKey = null) {
        const fragment = document.createDocumentFragment();
        const today = getCurrentDateKey();
        const zone = getDateTemporalZone(draft.date, today);
        const allowed = getSelectableSegmentStatuses(draft.date, today, zone);
        orderedDraftSegments(draft).forEach((segment, index) => {
            const row = document.createElement("div");
            const heading = document.createElement("strong");
            const fields = document.createElement("div");
            const status = document.createElement("div");
            const remove = document.createElement("button");
            const segmentDuration = document.createElement("span");
            row.className = "structure-segment-row";
            row.dataset.draftKey = segment.draftKey;
            heading.textContent = `Seg ${index + 1}${segment.id ? " · existente" : " · nuevo"}`;
            fields.className = "structure-segment-times";
            const start = timeField(`Inicio Seg ${index + 1}`, segment.startTime, (value) => {
                segment.startTime = value;
                clearError();
                updateControls();
                segmentDuration.textContent = `Duración: ${calculateDuration(segment.startTime, segment.endTime)}`;
            });
            const end = timeField(`Final Seg ${index + 1}`, segment.endTime, (value) => {
                segment.endTime = value;
                clearError();
                updateControls();
                segmentDuration.textContent = `Duración: ${calculateDuration(segment.startTime, segment.endTime)}`;
            });
            start.input.addEventListener("change", () => renderSegments(segment.draftKey));
            end.input.addEventListener("change", () => renderSegments(segment.draftKey));
            fields.append(start.label, end.label);
            status.className = "structure-segment-status";
            if (segment.id) {
                status.textContent = `Estado: ${statusDefinitions[segment.status].label} · solo lectura`;
            } else {
                const label = document.createElement("label");
                const select = document.createElement("select");
                label.className = "form-field";
                label.textContent = `Estado Seg ${index + 1}`;
                const placeholder = document.createElement("option");
                placeholder.value = "";
                placeholder.textContent = "Selecciona un estado";
                select.append(placeholder);
                allowed.forEach((value) => {
                    const option = document.createElement("option");
                    option.value = value;
                    option.textContent = statusDefinitions[value].label;
                    select.append(option);
                });
                select.value = segment.status;
                select.addEventListener("change", () => {
                    segment.status = select.value;
                    clearError();
                });
                label.append(select);
                status.append(label);
            }
            segmentDuration.className = "structure-segment-duration";
            segmentDuration.textContent = `Duración: ${calculateDuration(segment.startTime, segment.endTime)}`;
            remove.type = "button";
            remove.className = "secondary-button structure-remove-button";
            remove.textContent = "Eliminar segmento";
            remove.setAttribute("aria-label", `Eliminar Seg ${index + 1} del borrador`);
            remove.addEventListener("click", () => {
                removeDraftSegment(draft, segment.draftKey);
                clearError();
                renderSegments();
            });
            row.append(heading, fields, status, segmentDuration, remove);
            fragment.append(row);
        });
        segmentsContainer.replaceChildren(fragment);
        updateControls();
        if (focusKey) {
            const row = [...segmentsContainer.children].find((child) => child.dataset.draftKey === focusKey);
            row?.querySelector("input")?.focus();
        }
    }

    function close() {
        if (!draft) return;
        const target = opener;
        const occurrenceId = draft.occurrenceId;
        draft = null;
        pending = false;
        refreshPending = false;
        dialog.close();
        if (target?.isConnected) target.focus();
        else onRestoreFocus(occurrenceId);
    }

    async function dispatch(operation, payload) {
        if (!draft || pending || refreshPending) return;
        pending = true;
        clearError();
        updateControls();
        let outcome;
        try {
            outcome = await onCommand(operation, draft.occurrenceId, payload);
        } catch (error) {
            outcome = { status: "mutation_error", error };
        }
        pending = false;
        if (["synced", "review_required", "invalidated"].includes(outcome.status)) {
            close();
            return;
        }
        if (["saved_refresh_error", "unknown_result"].includes(outcome.status)) {
            refreshPending = true;
            showError(outcome.status === "saved_refresh_error"
                ? "Se guardó, pero falló la actualización. Reintenta solo la lectura; no se repetirá el cambio."
                : "No se conoce el resultado del comando. Actualiza el planner antes de editar de nuevo; no se repetirá automáticamente.");
        } else {
            showError(getOccurrenceStructureErrorMessage(outcome.error), outcome.error?.details?.blockers);
        }
        updateControls();
    }

    form.addEventListener("submit", (event) => {
        event.preventDefault();
        if (!draft || pending || refreshPending) return;
        const error = validateOccurrenceStructureDraft(draft);
        if (error) { showError(error); return; }
        void dispatch("structure", buildOccurrenceStructurePayload(draft));
    });
    startInput.addEventListener("input", () => {
        if (!draft) return;
        draft.startTime = startInput.value;
        clearError();
        updateControls();
    });
    endInput.addEventListener("input", () => {
        if (!draft) return;
        draft.endTime = endInput.value;
        clearError();
        updateControls();
    });
    addButton.addEventListener("click", () => {
        if (!draft || pending || refreshPending) return;
        const segment = addDraftSegment(draft);
        clearError();
        renderSegments(segment.draftKey);
    });
    translateButton.addEventListener("click", () => {
        if (!draft || !canTranslateOccurrenceDraft(draft)) return;
        void dispatch("translate", { startTime: draft.startTime, endTime: draft.endTime });
    });
    resetButton.addEventListener("click", () => {
        if (!draft || pending || refreshPending) return;
        if (!confirmReset("¿Restablecer la segmentación? Se reemplazarán todos los segments de esta aparición.")) return;
        if (!draft.startTime || !draft.endTime) {
            showError("Indica Inicio general y Final general para restablecer.");
            return;
        }
        void dispatch("reset", { startTime: draft.startTime, endTime: draft.endTime });
    });
    cancelButton.addEventListener("click", () => { if (!pending && !refreshPending) close(); });
    dialog.addEventListener("cancel", (event) => {
        event.preventDefault();
        if (!pending && !refreshPending) close();
    });
    retryButton.addEventListener("click", async () => {
        if (!draft || pending || !refreshPending) return;
        pending = true;
        updateControls();
        const outcome = await onRetryRefresh();
        pending = false;
        if (["synced", "review_required"].includes(outcome.status)) { close(); return; }
        showError("La actualización sigue sin estar disponible. Reintenta solo la lectura.");
        updateControls();
    });

    return {
        open(occurrence, name, focusElement) {
            if (getDateTemporalZone(occurrence.date, getCurrentDateKey()) === TEMPORAL_ZONES.FROZEN) return false;
            draft = createOccurrenceStructureDraft(occurrence);
            planItemName = name;
            opener = focusElement;
            pending = false;
            refreshPending = false;
            title.textContent = `Editar horario · ${planItemName}`;
            reference.textContent = `${draft.date} · solo esta aparición; la planificación recurrente no cambia.`;
            startInput.value = draft.startTime;
            endInput.value = draft.endTime;
            clearError();
            renderSegments();
            dialog.showModal();
            startInput.focus();
            return true;
        },
        close,
        isOpen: () => Boolean(draft),
        getDraftSnapshot: () => draft ? structuredClone(draft) : null,
    };
}
