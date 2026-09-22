import {
    applyFuture,
    applyWeek,
    createPlanItem,
    deleteOccurrence,
    fetchPlannerState,
    reconcilePlanner,
    replaceOccurrenceStructure,
    resetOccurrenceSegmentation,
    terminatePlanningAfter,
    translateOccurrence,
    updateSegmentStatus,
} from "./api/planner-api.js";
import { createPlannerBootstrap } from "./bootstrap/planner-bootstrap.js";
import {
    createOccurrenceMutationCoordinator,
    getOccurrenceMutationErrorMessage,
    getSegmentStatusMutationErrorMessage,
} from "./mutations/occurrence-mutation.js";
import { getOccurrenceStructureErrorMessage } from "./mutations/occurrence-structure-mutation.js";
import { createSegmentConflictMutationCoordinator } from "./mutations/segment-conflict-mutation.js";
import {
    buildApplyFuturePayload,
    createRecurringScheduleMutationCoordinator,
    getRecurringScheduleMutationErrorMessage,
} from "./mutations/recurring-schedule-mutation.js";
import { createPlannerStore } from "./state/planner-store.js";
import { getPersistentPlanningActions } from "./domain/deletion-policy.js";
import { createPlanningTerminationMutationCoordinator } from "./mutations/planning-termination-mutation.js";
import { getDateTemporalZone, TEMPORAL_ZONES } from "./domain/temporal-integrity.js";
import { dateKeyToLocalDate, formatDateKey, formatMonth, formatSelectedDate, getMonthDates } from "./utils/date-time.js";
import { createSegmentConflictDialogView } from "./views/segment-conflict-dialog.js";
import { createDeletionDialogView } from "./views/deletion-dialog.js";
import { createPlanItemFormView } from "./views/plan-item-form.js";
import { createPlannerMatrixView } from "./views/planner-matrix.js";
import { createOccurrenceStructureEditorView } from "./views/occurrence-structure-editor.js";

const byId = (id) => document.getElementById(id);
const elements = Object.fromEntries([
    "monthName", "monthPickerButton", "monthPicker", "selectedDateLabel", "datePickerButton", "datePicker",
    "previousDayButton", "nextDayButton", "previousMonthButton", "nextMonthButton", "compactPreviousMonthButton",
    "compactNextMonthButton", "toggleMonthRecordsButton",
    "matrixHead", "matrixBody", "matrixFeedback", "emptyState", "statusLegend", "addActivityButton",
    "plannerBootstrapState", "bootstrapMessage", "retryBootstrapButton", "matrixContainer",
    "activityDialog", "activityForm", "activityDialogTitle", "insertionReference", "formErrors", "activityName",
    "planItemKind", "planItemType", "activitySubtypeField", "habitSubtypeField", "occurrenceDate", "occurrenceDateLabel",
    "occurrenceStartTime", "occurrenceEndTime", "cancelActivityButton", "formSavingStatus", "scheduleMode", "weeklyFields",
    "scheduleStartDate", "weekdayChoices", "indefiniteSchedule", "scheduleEndDateField", "scheduleEndDate",
    "weekdayOverrides", "weekdayOverrideFields", "weeklyDefaultStartTime", "weeklyDefaultEndTime",
    "intervalFields", "intervalDays", "intervalAdditionalSlots", "addIntervalSlotButton", "manualDatesField",
    "manualDateEntries", "addManualDateButton", "explicitDateField",
    "occurrenceTimeAnchor", "occurrenceTimeFields", "recurrenceScopeField",
    "segmentConflictDialog", "segmentConflictTitle", "segmentConflictSummary", "segmentConflictList",
    "segmentConflictError", "segmentConflictBackButton", "segmentConflictConfirmButton",
    "deletionDialog", "deletionSummary", "deleteOccurrenceButton", "deleteOccurrenceDetails",
    "stopSlotButton", "stopSlotDetails", "stopPlanningButton", "stopPlanningDetails",
    "deleteFutureButton", "deleteFutureDetails", "deletionConfirmation", "deletionConfirmButton",
    "deletionRetryButton", "deletionError", "deletionBackButton",
    "structureDialog", "structureForm", "structureDialogTitle", "structureReference",
    "structureStartTime", "structureEndTime", "structureSegments", "structureDuration",
    "structureError", "structureSaving", "structureAddSegmentButton",
    "structureTranslateButton", "structureResetButton", "structureCancelButton",
    "structureRetryButton", "structureSaveButton",
].map((id) => [id, byId(id)]));

function getCurrentLocalDate() {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

const initialCurrentDate = getCurrentLocalDate();
const plannerStore = createPlannerStore(
    [],
    [],
    formatDateKey(initialCurrentDate),
    { getCurrentDateKey: () => formatDateKey(getCurrentLocalDate()) },
);
let selectedDate = new Date(initialCurrentDate);
let visibleMonth = new Date(selectedDate.getFullYear(), selectedDate.getMonth(), 1);
let showAllMonthRecords = true;
let selectedPlanItemId = null;
let selectedOccurrenceId = null;
let selectedSegmentId = null;
const expandedOccurrenceIds = new Set();
let statusMutationPending = false;

function clearPlannerSelection() {
    selectedPlanItemId = null;
    selectedOccurrenceId = null;
    selectedSegmentId = null;
}

function selectPlanItemSummary(planItemId) {
    selectedPlanItemId = planItemId;
    selectedOccurrenceId = null;
    selectedSegmentId = null;
}

function clearFeedback() {
    elements.matrixFeedback.hidden = true;
    elements.matrixFeedback.textContent = "";
    delete elements.matrixFeedback.dataset.tone;
}
function showFeedback(message, tone = "error") {
    elements.matrixFeedback.textContent = message;
    elements.matrixFeedback.dataset.tone = tone;
    elements.matrixFeedback.setAttribute("role", tone === "notice" ? "status" : "alert");
    elements.matrixFeedback.setAttribute("aria-live", tone === "notice" ? "polite" : "assertive");
    elements.matrixFeedback.hidden = false;
}
function monthValue(date) { return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`; }
function showNativePicker(input) { if (typeof input.showPicker === "function") input.showPicker(); else { input.focus(); input.click(); } }

function render() {
    const currentDate = getCurrentLocalDate();
    const currentDateKey = formatDateKey(currentDate);
    const selectedDateKey = formatDateKey(selectedDate);
    const year = visibleMonth.getFullYear();
    const month = visibleMonth.getMonth();
    elements.monthName.textContent = formatMonth(visibleMonth);
    elements.monthPicker.value = monthValue(visibleMonth);
    elements.datePicker.value = formatDateKey(selectedDate);
    elements.selectedDateLabel.textContent = formatSelectedDate(selectedDate);
    const selectedDateFrozen = getDateTemporalZone(selectedDateKey, currentDateKey) === TEMPORAL_ZONES.FROZEN;
    elements.addActivityButton.disabled = selectedDateFrozen;
    elements.addActivityButton.title = selectedDateFrozen
        ? "El historial congelado es de solo lectura"
        : "Agregar registro";
    elements.toggleMonthRecordsButton.textContent = showAllMonthRecords ? "👁" : "⊝";
    elements.toggleMonthRecordsButton.setAttribute("aria-pressed", String(showAllMonthRecords));
    elements.toggleMonthRecordsButton.setAttribute("aria-label", showAllMonthRecords ? "Mostrar solo el Plan del día" : "Mostrar todos los registros del mes");
    const visibleOccurrences = plannerStore.getOccurrencesForMonth(year, month);
    const existingOccurrenceIds = new Set(plannerStore.getOccurrences().map(({ id }) => id));
    expandedOccurrenceIds.forEach((id) => {
        if (!existingOccurrenceIds.has(id)) expandedOccurrenceIds.delete(id);
    });
    const selectedOccurrence = selectedOccurrenceId
        ? visibleOccurrences.find(({ id }) => id === selectedOccurrenceId)
        : null;
    if (selectedOccurrenceId && !selectedOccurrence) clearPlannerSelection();
    if (
        selectedSegmentId
        && !selectedOccurrence?.segments?.some(({ id }) => id === selectedSegmentId)
    ) {
        selectedSegmentId = null;
    }
    const count = matrixView.render({
        planItems: plannerStore.getPlanItems(), occurrences: visibleOccurrences,
        monthDates: getMonthDates(year, month), currentDate, selectedDate,
        selectedPlanItemId, selectedOccurrenceId, selectedSegmentId,
        expandedOccurrenceIds, showAllMonthRecords,
        statusMutationPending,
    });
    elements.emptyState.hidden = count > 0;
}

function selectDate(dateKey) {
    const date = dateKeyToLocalDate(dateKey);
    if (!date) return;
    selectedDate = date;
    visibleMonth = new Date(date.getFullYear(), date.getMonth(), 1);
    clearPlannerSelection();
    clearFeedback();
    render();
}
function moveDay(offset) { const date = new Date(selectedDate); date.setDate(date.getDate() + offset); selectDate(formatDateKey(date)); }
function synchronizeMonth(year, month, preference) {
    const monthEnd = new Date(year, month + 1, 0);
    const occurrences = plannerStore.getOccurrencesForMonth(year, month);
    const selectedDateKey = occurrences.length
        ? (preference === "last" ? occurrences.at(-1).date : occurrences[0].date)
        : formatDateKey(preference === "last" ? monthEnd : new Date(year, month, 1));
    visibleMonth = new Date(year, month, 1);
    selectedDate = dateKeyToLocalDate(selectedDateKey);
    clearPlannerSelection();
    clearFeedback();
    render();
}

function moveMonth(offset) {
    const destination = new Date(visibleMonth.getFullYear(), visibleMonth.getMonth() + offset, 1);
    synchronizeMonth(destination.getFullYear(), destination.getMonth(), offset < 0 ? "last" : "first");
}

const matrixView = createPlannerMatrixView({
    matrixHead: elements.matrixHead, matrixBody: elements.matrixBody, statusLegend: elements.statusLegend,
    onDateSelect: selectDate,
    onStatusChange: (request) => { void persistSegmentStatus(request); },
    onRowSelect: (selection, restore) => {
        const sameSelection = selectedPlanItemId === selection.planItemId
            && selectedOccurrenceId === selection.occurrenceId
            && selectedSegmentId === selection.segmentId;
        if (sameSelection) {
            clearPlannerSelection();
        } else {
            selectedPlanItemId = selection.planItemId;
            selectedOccurrenceId = selection.occurrenceId;
            selectedSegmentId = selection.segmentId;
        }
        render();
        if (restore && !sameSelection) matrixView.focusPlannerRow(selection);
    },
    onToggleOccurrence: (occurrenceId) => {
        if (expandedOccurrenceIds.has(occurrenceId)) {
            expandedOccurrenceIds.delete(occurrenceId);
            if (selectedOccurrenceId === occurrenceId && selectedSegmentId !== null) {
                selectedSegmentId = null;
            }
        } else {
            expandedOccurrenceIds.add(occurrenceId);
        }
        render();
    },
    onInsertBefore: (item, occurrence, opener) => {
        const daily = plannerStore.getOccurrencesForDate(occurrence.date);
        const index = daily.findIndex(({ id }) => id === occurrence.id);
        planItemFormView.openInsertBefore(item, occurrence, index > 0 ? daily[index - 1].endTime : "", opener);
    },
    onEdit: (item, occurrence, opener, selectedDateKey, scheduleOnly) => occurrence
        ? structureEditorView.open(occurrence, item.name, opener)
        : planItemFormView.openEdit(item, occurrence, selectedDateKey, opener, scheduleOnly),
    onDelete: (item, occurrence, opener, selectedDateKey) => {
        const options = plannerStore.getDeletionOptions(
            item.id,
            selectedDateKey,
            occurrence?.id ?? null,
        );
        options.selectedOccurrence = occurrence
            ? plannerStore.getOccurrenceById(occurrence.id)
            : options.individual.occurrence;
        options.selectedSegmentId = selectedOccurrenceId === occurrence?.id ? selectedSegmentId : null;
        options.actions = getPersistentPlanningActions({
            occurrence: options.selectedOccurrence,
            generationConfig: options.planItem.generationConfig,
            referenceDate: formatDateKey(getCurrentLocalDate()),
        });
        deletionDialogView.open(options, {
            onDeleteOccurrence: async (occurrenceId) => {
                const outcome = await occurrenceDeleteMutation.submit(occurrenceId);
                return settlePersistentOccurrenceMutation(outcome, {
                    operation: "delete",
                    planItemId: item.id,
                });
            },
            onTerminate: async (occurrenceId, scope) => settlePersistentTermination(
                await planningTerminationMutation.submit(occurrenceId, scope), scope,
            ),
            onRetryRefresh: async () => occurrenceDeleteMutation.hasPendingRefresh()
                ? settlePersistentOccurrenceMutation(
                    await occurrenceDeleteMutation.retryRefresh(),
                    { operation: "delete", planItemId: item.id },
                )
                : settlePersistentTermination(
                    await planningTerminationMutation.retryRefresh(), "recovered",
                ),
            onComplete: (result, operation) => {
                render();
                showFeedback(
                    result?.status === "review_required"
                        ? "Se actualizó el planner tras un resultado de red incierto. Revisa si el cambio se aplicó antes de repetirlo."
                        : operation === "individual"
                            ? "La aparición se eliminó solo para esta fecha."
                            : "La planificación se actualizó y sincronizó desde PostgreSQL.",
                    "notice",
                );
            },
        });
    },
    onAmbiguity: (message) => showFeedback(message),
});

const segmentConflictDialogView = createSegmentConflictDialogView({
    dialog: elements.segmentConflictDialog,
    title: elements.segmentConflictTitle,
    summary: elements.segmentConflictSummary,
    list: elements.segmentConflictList,
    errorRegion: elements.segmentConflictError,
    backButton: elements.segmentConflictBackButton,
    confirmButton: elements.segmentConflictConfirmButton,
    getPlanItemName: (id) => plannerStore.getPlanItemById(id)?.name ?? null,
});

const deletionDialogView = createDeletionDialogView({
    dialog: elements.deletionDialog,
    summary: elements.deletionSummary,
    deleteOccurrenceButton: elements.deleteOccurrenceButton,
    deleteOccurrenceDetails: elements.deleteOccurrenceDetails,
    stopPlanningButton: elements.stopPlanningButton,
    stopPlanningDetails: elements.stopPlanningDetails,
    stopSlotButton: elements.stopSlotButton,
    stopSlotDetails: elements.stopSlotDetails,
    deleteFutureButton: elements.deleteFutureButton,
    deleteFutureDetails: elements.deleteFutureDetails,
    confirmationRegion: elements.deletionConfirmation,
    confirmButton: elements.deletionConfirmButton,
    retryButton: elements.deletionRetryButton,
    errorRegion: elements.deletionError,
    backButton: elements.deletionBackButton,
    fallbackFocusElement: elements.addActivityButton,
});

const segmentConflictMutation = createSegmentConflictMutationCoordinator({
    executeCommand: ({ kind, occurrenceId, payload }, conflictResolution) => {
        const body = conflictResolution ? { ...payload, conflictResolution } : payload;
        if (kind === "create") return createPlanItem(body);
        if (kind === "translate") return translateOccurrence(
            occurrenceId, payload.startTime, payload.endTime,
            conflictResolution ? { conflictResolution } : {},
        );
        if (kind === "structure") return replaceOccurrenceStructure(occurrenceId, body);
        if (kind === "reset") return resetOccurrenceSegmentation(
            occurrenceId, payload.startTime, payload.endTime,
            conflictResolution ? { conflictResolution } : {},
        );
        throw new TypeError("El comando de conflicto no está soportado.");
    },
    loadPlannerState: fetchPlannerState,
    hydratePlannerState: (serverState) => plannerStore.hydratePlannerState(serverState),
});

const occurrenceDeleteMutation = createPlanningTerminationMutationCoordinator({
    terminatePlanning: (occurrenceId) => deleteOccurrence(occurrenceId),
    loadPlannerState: fetchPlannerState,
    hydratePlannerState: (serverState) => plannerStore.hydratePlannerState(serverState),
});

const planningTerminationMutation = createPlanningTerminationMutationCoordinator({
    terminatePlanning: terminatePlanningAfter,
    loadPlannerState: fetchPlannerState,
    hydratePlannerState: (serverState) => plannerStore.hydratePlannerState(serverState),
});

const segmentStatusMutation = createOccurrenceMutationCoordinator({
    mutateOccurrence: updateSegmentStatus,
    loadPlannerState: fetchPlannerState,
    hydratePlannerState: (serverState) => plannerStore.hydratePlannerState(serverState),
});

function reviewSegmentConflict(outcome, intent) {
    if (outcome.status !== "conflict_required") return Promise.resolve(outcome);
    return new Promise((resolve) => {
        segmentConflictDialogView.open({
            intent,
            currentConflicts: outcome.conflicts,
            focusElement: document.activeElement,
            confirm: (acknowledgements) => segmentConflictMutation.confirm(acknowledgements),
            cancel: () => {
                segmentConflictMutation.cancel();
                resolve({ status: "cancelled" });
            },
            complete: resolve,
        });
    });
}

async function submitStructureCommand(operation, occurrenceId, payload) {
    const intent = ({ translate: "Mover actividad", structure: "Modificar estructura",
        reset: "Restablecer segmentación" })[operation];
    const initial = await segmentConflictMutation.submit({ kind: operation, occurrenceId, payload });
    const outcome = await reviewSegmentConflict(initial, intent);
    if (outcome.status === "synced") {
        render();
        showFeedback("La estructura se guardó y el planner quedó sincronizado.", "notice");
        return outcome;
    }
    if (outcome.status === "review_required") {
        render();
        showFeedback("El planner se actualizó. Revisa si el cambio se guardó antes de editar de nuevo.", "notice");
        return outcome;
    }
    if (outcome.status === "stale") {
        render();
        showFeedback("El segmento en conflicto cambió. Revisa el planner actualizado antes de volver a guardar.");
        return structureEditorView.isSourceCurrent(plannerStore.getOccurrenceById(occurrenceId))
            ? { status: "stale", error: outcome.error }
            : { status: "invalidated" };
    }
    if (outcome.status === "unsupported") {
        return { status: "mutation_error", error: outcome.error };
    }
    if (outcome.status !== "mutation_error") return outcome;
    const code = outcome.error?.code;
    if (["occurrence_not_found", "concurrent_conflict", "history_frozen", "temporal_reconciliation_required"].includes(code)) {
        if (["occurrence_not_found", "concurrent_conflict"].includes(code)) {
            if (code === "occurrence_not_found") clearPlannerSelection();
            try { plannerStore.hydratePlannerState(await fetchPlannerState()); }
            catch { /* El mensaje visible pide actualizar el planner. */ }
        }
        render();
        showFeedback(getOccurrenceStructureErrorMessage(outcome.error));
        return { status: "invalidated" };
    }
    return outcome;
}

const structureEditorView = createOccurrenceStructureEditorView({
    dialog: elements.structureDialog,
    form: elements.structureForm,
    title: elements.structureDialogTitle,
    reference: elements.structureReference,
    startInput: elements.structureStartTime,
    endInput: elements.structureEndTime,
    segmentsContainer: elements.structureSegments,
    duration: elements.structureDuration,
    errorRegion: elements.structureError,
    savingStatus: elements.structureSaving,
    addButton: elements.structureAddSegmentButton,
    translateButton: elements.structureTranslateButton,
    resetButton: elements.structureResetButton,
    cancelButton: elements.structureCancelButton,
    retryButton: elements.structureRetryButton,
    saveButton: elements.structureSaveButton,
    onCommand: submitStructureCommand,
    onRetryRefresh: async () => {
        const outcome = await segmentConflictMutation.retryRefresh();
        if (["synced", "review_required"].includes(outcome.status)) {
            render();
            showFeedback(outcome.status === "synced"
                ? "La estructura guardada se cargó desde el backend."
                : "El planner se actualizó. Revisa el resultado antes de editar de nuevo.", "notice");
        }
        return outcome;
    },
    getCurrentDateKey: () => formatDateKey(getCurrentLocalDate()),
    onRestoreFocus: (occurrenceId) => matrixView.focusPlannerRow({ occurrenceId }),
});

async function persistSegmentStatus({ segmentId, status }) {
    if (statusMutationPending) return;
    statusMutationPending = true;
    showFeedback("Guardando estado del segment…", "notice");
    render();
    const outcome = await segmentStatusMutation.submit(segmentId, status);
    statusMutationPending = false;
    render();
    matrixView.focusSegmentStatusControl(segmentId);
    if (outcome.status === "synced") {
        showFeedback("El estado del segment se guardó y el planner quedó sincronizado.", "notice");
    } else if (outcome.status === "saved_refresh_error") {
        showFeedback(
            "El estado se guardó, pero no se pudo actualizar la vista. Activa de nuevo el control para reintentar solo la lectura; no se repetirá el cambio.",
        );
    } else {
        showFeedback(getSegmentStatusMutationErrorMessage(outcome.error));
    }
}

const recurringScheduleMutation = createRecurringScheduleMutationCoordinator({
    applyWeek,
    applyFuture,
    loadPlannerState: fetchPlannerState,
    hydratePlannerState: (serverState) => plannerStore.hydratePlannerState(serverState),
});

function settlePersistentOccurrenceMutation(outcome, { operation, planItemId }) {
    if (outcome.status === "synced") {
        selectPlanItemSummary(planItemId);
        render();
        showFeedback(
            operation === "delete"
                ? "La aparición fue eliminada y el planner quedó sincronizado."
                : "La aparición fue actualizada y el planner quedó sincronizado.",
            "notice",
        );
        return { status: "synced" };
    }
    if (outcome.status === "saved_refresh_error") {
        return {
            status: "saved_refresh_error",
            keepOpen: true,
            retryRefresh: true,
            message: operation === "delete"
                ? "La aparición se eliminó, pero no se pudo actualizar la vista. Reintenta la actualización; no se volverá a eliminar."
                : "La aparición se guardó, pero no se pudo actualizar la vista. Reintenta la actualización; no se volverá a modificar.",
        };
    }
    if (outcome.status === "unknown_result") {
        return {
            status: "unknown_result",
            keepOpen: true,
            retryRefresh: true,
            message: "No se conoce el resultado de la eliminación y falló la actualización. Reintenta solo la lectura; no se repetirá el DELETE.",
        };
    }
    if (outcome.status === "review_required") {
        render();
        return { status: "review_required" };
    }
    if (outcome.status === "mutation_error") {
        outcome.error.message = getOccurrenceMutationErrorMessage(outcome.error, operation);
        throw outcome.error;
    }
    throw new Error("No se pudo completar la mutación persistente.");
}

function settlePersistentTermination(outcome, scope) {
    if (outcome.status === "synced") {
        // render() drops only IDs that no longer exist. A surviving cutoff-day
        // occurrence and its selected segment/expansion remain selected.
        render();
        return { status: "synced" };
    }
    if (outcome.status === "saved_refresh_error" || outcome.status === "unknown_result") {
        return {
            keepOpen: true,
            retryRefresh: true,
            message: outcome.status === "unknown_result"
                ? "No se conoce el resultado de la red y falló la actualización. Reintenta solo la lectura; no se repetirá la acción."
                : "La acción se guardó, pero falló la actualización. Reintenta solo la lectura; no se repetirá la acción.",
        };
    }
    if (outcome.status === "review_required") {
        render();
        return { status: "review_required" };
    }
    if (outcome.status === "mutation_error") {
        throw new Error(outcome.error?.message || `No se pudo completar la acción ${scope}.`);
    }
    throw new Error("No se pudo completar la acción de planificación.");
}

function settlePersistentRecurringMutation(outcome, { scope, planItemId }) {
    if (outcome.status === "synced") {
        if (selectedPlanItemId !== planItemId) selectPlanItemSummary(planItemId);
        render();
        showFeedback(
            scope === "week"
                ? "La planificación de la semana se guardó y sincronizó correctamente."
                : "La planificación futura se guardó y sincronizó correctamente.",
            "notice",
        );
        return { status: "synced" };
    }
    if (outcome.status === "saved_refresh_error") {
        return {
            status: "saved_refresh_error",
            keepOpen: true,
            retryRefresh: true,
            message: scope === "week"
                ? "La semana se guardó, pero no se pudo actualizar la vista. Reintenta la actualización; no se volverá a aplicar."
                : "La planificación futura se guardó, pero no se pudo actualizar la vista. Reintenta la actualización; no se volverá a aplicar.",
        };
    }
    if (outcome.status === "review_required") {
        render();
        return {
            status: "review_required",
            keepOpen: true,
            retryRefresh: false,
            message: getRecurringScheduleMutationErrorMessage(outcome.error, scope),
        };
    }
    if (outcome.status === "mutation_error") {
        outcome.error.message = getRecurringScheduleMutationErrorMessage(
            outcome.error,
            scope,
        );
        throw outcome.error;
    }
    throw new Error("No se pudo completar la planificación persistente.");
}

async function persistRecurringSchedule(scope, planItemId, effectiveDate, generationConfig) {
    const payload = scope === "week"
        ? plannerStore.prepareApplyWeekPayload(
            planItemId,
            effectiveDate,
            generationConfig,
        )
        : buildApplyFuturePayload(generationConfig, effectiveDate);
    if (scope === "week" && payload.operations.length === 0) {
        selectPlanItemSummary(planItemId);
        render();
        showFeedback("La semana ya coincide con la planificación indicada.", "notice");
        return { status: "synced" };
    }
    const outcome = await recurringScheduleMutation.submit(
        scope,
        planItemId,
        payload,
    );
    return settlePersistentRecurringMutation(outcome, { scope, planItemId });
}

function persistentCreationErrorMessage(error) {
    if (error?.code === "network_error") {
        return "No se pudo conectar con el backend. Revisa la conexión e inténtalo nuevamente.";
    }
    if (error?.details?.status === 400 || error?.code === "invalid_payload") {
        return "El backend rechazó los datos del registro. Revisa el formulario.";
    }
    if (error?.details?.status === 409) {
        return error.message || "La agenda cambió y el registro entra en conflicto.";
    }
    return "No se pudo guardar el registro. Inténtalo nuevamente.";
}

function settlePersistentCreation(outcome) {
    if (outcome.status === "synced") {
        selectPlanItemSummary(outcome.mutation?.planItem?.id ?? null);
        render();
        showFeedback("El registro se guardó correctamente.", "notice");
        return { status: "synced" };
    }
    if (outcome.status === "saved_refresh_error") {
        return {
            status: "saved_refresh_error",
            keepOpen: true,
            retryRefresh: true,
            message: "El registro se guardó, pero no se pudo actualizar la vista. Reintenta la actualización; no se volverá a crear.",
        };
    }
    if (outcome.status === "stale") {
        render();
        return { keepOpen: true, message: "El conflicto cambió. Se actualizó el planner; revisa el formulario y vuelve a enviar para obtener conflictos nuevos." };
    }
    if (outcome.status === "review_required") {
        render();
        return { keepOpen: true, message: "No se conoce con certeza el resultado del envío. Se actualizó el planner; revisa si el registro se guardó antes de intentarlo de nuevo." };
    }
    if (outcome.status === "unknown_result") {
        return { keepOpen: true, retryRefresh: true, message: "No se conoce el resultado del envío y falló la actualización. Reintenta solo la lectura; no se repetirá la creación." };
    }
    if (outcome.status === "cancelled") {
        return { keepOpen: true, message: "No se confirmó el conflicto. El formulario permanece disponible." };
    }
    if (["mutation_error", "unsupported"].includes(outcome.status)) {
        throw new Error(persistentCreationErrorMessage(outcome.error));
    }
    throw new Error("No se pudo completar la creación persistente.");
}

const planItemFormView = createPlanItemFormView({
    ...elements, dialog: elements.activityDialog, form: elements.activityForm, title: elements.activityDialogTitle,
    referenceMessage: elements.insertionReference, errorsRegion: elements.formErrors, nameInput: elements.activityName,
    kindInput: elements.planItemKind, itemTypeInput: elements.planItemType, activityTypeField: elements.activitySubtypeField,
    habitTypeField: elements.habitSubtypeField, dateInput: elements.occurrenceDate, startTimeInput: elements.occurrenceStartTime,
    endTimeInput: elements.occurrenceEndTime, cancelButton: elements.cancelActivityButton,
    savingStatus: elements.formSavingStatus,
    fallbackFocusElement: elements.addActivityButton, onValidate: () => [],
    onSubmit: async (result, context) => {
        if (segmentConflictMutation.hasPendingRefresh()) {
            return settlePersistentCreation(await segmentConflictMutation.retryRefresh());
        }
        if (
            ["edit", "edit_schedule", "edit_without_occurrence"].includes(context.mode) &&
            result.recurrenceChanged &&
            ["week", "future"].includes(result.scope)
        ) {
            const effectiveDate = context.mode === "edit"
                ? result.occurrence.date
                : context.selectedDate;
            return persistRecurringSchedule(
                result.scope,
                context.planItemId,
                effectiveDate,
                result.generationConfig,
            );
        }
        if (context.mode === "edit") {
            throw new Error("La edición de una aparición utiliza el editor estructural; el PATCH parent-level está retirado.");
        } else if (context.mode === "edit_schedule") {
            selectPlanItemSummary(context.planItemId);
        } else if (context.mode === "edit_without_occurrence") {
            // Aún no existe el flujo persistente ad-hoc/UX segmentario. El
            // escritor local legacy modificaría el status del parent.
            throw new Error("Agregar una occurrence a un PlanItem existente requiere la próxima integración persistente de conflictos.");
        } else {
            const payload = {
                ...result.planItem,
                generationConfig: result.generationConfig,
            };
            const initial = await segmentConflictMutation.submit({ kind: "create", payload });
            const outcome = await reviewSegmentConflict(initial, "Crear actividad");
            return settlePersistentCreation(outcome);
        }

        render();
    },
    onFallbackFocus: (id) => { if (!matrixView.focusPlanItemRow(id)) elements.addActivityButton.focus(); },
});

const plannerControls = [
    elements.previousDayButton,
    elements.nextDayButton,
    elements.previousMonthButton,
    elements.nextMonthButton,
    elements.compactPreviousMonthButton,
    elements.compactNextMonthButton,
    elements.toggleMonthRecordsButton,
    elements.datePickerButton,
    elements.monthPickerButton,
    elements.datePicker,
    elements.monthPicker,
    elements.addActivityButton,
];

function setPlannerControlsDisabled(disabled) {
    plannerControls.forEach((control) => { control.disabled = disabled; });
}

function showBootstrapLoading() {
    setPlannerControlsDisabled(true);
    elements.matrixContainer.hidden = true;
    elements.emptyState.hidden = true;
    clearFeedback();
    elements.bootstrapMessage.textContent = "Cargando planner…";
    elements.retryBootstrapButton.hidden = true;
    elements.plannerBootstrapState.setAttribute("role", "status");
    elements.plannerBootstrapState.hidden = false;
}

function showBootstrapError(error) {
    console.error("No se pudo completar el bootstrap del planner.", error);
    setPlannerControlsDisabled(true);
    elements.matrixContainer.hidden = true;
    elements.emptyState.hidden = true;
    elements.bootstrapMessage.textContent = "No se pudo cargar el planner.";
    elements.retryBootstrapButton.hidden = false;
    elements.plannerBootstrapState.setAttribute("role", "alert");
    elements.plannerBootstrapState.hidden = false;
}

function showHydratedPlanner() {
    setPlannerControlsDisabled(false);
    elements.plannerBootstrapState.hidden = true;
    elements.matrixContainer.hidden = false;
    render();
}

matrixView.renderLegend();
elements.previousDayButton.addEventListener("click", () => moveDay(-1));
elements.nextDayButton.addEventListener("click", () => moveDay(1));
elements.previousMonthButton.addEventListener("click", () => moveMonth(-1));
elements.nextMonthButton.addEventListener("click", () => moveMonth(1));
elements.compactPreviousMonthButton.addEventListener("click", () => moveMonth(-1));
elements.compactNextMonthButton.addEventListener("click", () => moveMonth(1));
elements.toggleMonthRecordsButton.addEventListener("click", () => {
    showAllMonthRecords = !showAllMonthRecords;
    clearPlannerSelection();
    render();
});
elements.datePickerButton.addEventListener("click", () => showNativePicker(elements.datePicker));
elements.monthPickerButton.addEventListener("click", () => showNativePicker(elements.monthPicker));
elements.datePicker.addEventListener("change", () => selectDate(elements.datePicker.value));
elements.monthPicker.addEventListener("change", () => {
    const [year, month] = elements.monthPicker.value.split("-").map(Number);
    if (year && month) synchronizeMonth(year, month - 1, "first");
});
elements.addActivityButton.addEventListener("click", () => planItemFormView.openCreate(formatDateKey(selectedDate), elements.addActivityButton));

const plannerBootstrap = createPlannerBootstrap({
    reconcilePlanner,
    loadPlannerState: fetchPlannerState,
    hydratePlannerState: (serverState) => plannerStore.hydratePlannerState(serverState),
    onLoading: showBootstrapLoading,
    onReady: showHydratedPlanner,
    onError: showBootstrapError,
});
elements.retryBootstrapButton.addEventListener("click", () => plannerBootstrap.retry());
void plannerBootstrap.start();
