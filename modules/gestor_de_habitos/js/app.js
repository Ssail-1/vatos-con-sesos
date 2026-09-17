import { initialPlanItems } from "./data/mock-plan-items.js";
import { mockStatusOverrides } from "./data/mock-status-overrides.js";
import { createPlannerStore } from "./state/planner-store.js";
import { getDateTemporalZone, TEMPORAL_ZONES } from "./domain/temporal-integrity.js";
import { dateKeyToLocalDate, formatDateKey, formatMonth, formatSelectedDate, getMonthDates } from "./utils/date-time.js";
import { createOverrideConfirmationView } from "./views/override-confirmation.js";
import { createDeletionDialogView } from "./views/deletion-dialog.js";
import { createPlanItemFormView } from "./views/plan-item-form.js";
import { createPlannerMatrixView } from "./views/planner-matrix.js";

const byId = (id) => document.getElementById(id);
const elements = Object.fromEntries([
    "monthName", "monthPickerButton", "monthPicker", "selectedDateLabel", "datePickerButton", "datePicker",
    "previousDayButton", "nextDayButton", "previousMonthButton", "nextMonthButton", "compactPreviousMonthButton",
    "compactNextMonthButton", "toggleMonthRecordsButton",
    "matrixHead", "matrixBody", "matrixFeedback", "emptyState", "statusLegend", "addActivityButton",
    "activityDialog", "activityForm", "activityDialogTitle", "insertionReference", "formErrors", "activityName",
    "planItemKind", "planItemType", "activitySubtypeField", "habitSubtypeField", "occurrenceDate", "occurrenceDateLabel",
    "occurrenceStartTime", "occurrenceEndTime", "cancelActivityButton", "scheduleMode", "weeklyFields",
    "scheduleStartDate", "weekdayChoices", "indefiniteSchedule", "scheduleEndDateField", "scheduleEndDate",
    "weekdayOverrides", "weekdayOverrideFields", "weeklyDefaultStartTime", "weeklyDefaultEndTime",
    "intervalFields", "intervalDays", "intervalAdditionalSlots", "addIntervalSlotButton", "manualDatesField",
    "manualDateEntries", "addManualDateButton", "explicitDateField",
    "occurrenceTimeAnchor", "occurrenceTimeFields", "recurrenceScopeField", "overrideDialog", "overrideCandidateSummary",
    "overrideCandidateOccurrences", "overrideConflictList", "overrideConsequence", "overrideError",
    "overrideBackButton", "overrideContinueButton",
    "deletionDialog", "deletionSummary", "deleteOccurrenceButton", "deleteOccurrenceDetails",
    "stopPlanningButton", "stopPlanningDetails", "deletionError", "deletionBackButton",
].map((id) => [id, byId(id)]));

function getCurrentLocalDate() {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

const initialCurrentDate = getCurrentLocalDate();
const plannerStore = createPlannerStore(
    initialPlanItems,
    mockStatusOverrides,
    formatDateKey(initialCurrentDate),
    { getCurrentDateKey: () => formatDateKey(getCurrentLocalDate()) },
);
let selectedDate = new Date(initialCurrentDate);
let visibleMonth = new Date(selectedDate.getFullYear(), selectedDate.getMonth(), 1);
let showAllMonthRecords = false;
let selectedPlanItemId = null;

const PRESERVED_HISTORY_NOTICE = "La planificación futura fue actualizada. La aparición del día seleccionado se conservó porque ya contiene historial.";

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
    plannerStore.reconcileTemporalState(currentDateKey);
    const year = visibleMonth.getFullYear();
    const month = visibleMonth.getMonth();
    plannerStore.ensureMaterializedThrough(formatDateKey(new Date(year, month + 1, 0)));
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
    const count = matrixView.render({
        planItems: plannerStore.getPlanItems(), occurrences: plannerStore.getOccurrencesForMonth(year, month),
        monthDates: getMonthDates(year, month), currentDate, selectedDate, selectedPlanItemId, showAllMonthRecords,
    });
    elements.emptyState.hidden = count > 0;
}

function selectDate(dateKey) {
    const date = dateKeyToLocalDate(dateKey);
    if (!date) return;
    selectedDate = date;
    visibleMonth = new Date(date.getFullYear(), date.getMonth(), 1);
    selectedPlanItemId = null;
    clearFeedback();
    render();
}
function moveDay(offset) { const date = new Date(selectedDate); date.setDate(date.getDate() + offset); selectDate(formatDateKey(date)); }
function synchronizeMonth(year, month, preference) {
    const monthEnd = new Date(year, month + 1, 0);
    plannerStore.ensureMaterializedThrough(formatDateKey(monthEnd));
    const occurrences = plannerStore.getOccurrencesForMonth(year, month);
    const selectedDateKey = occurrences.length
        ? (preference === "last" ? occurrences.at(-1).date : occurrences[0].date)
        : formatDateKey(preference === "last" ? monthEnd : new Date(year, month, 1));
    visibleMonth = new Date(year, month, 1);
    selectedDate = dateKeyToLocalDate(selectedDateKey);
    selectedPlanItemId = null;
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
    onStatusChange: (id) => {
        try {
            clearFeedback();
            const updated = plannerStore.advanceOccurrenceStatus(id);
            render();
            return updated;
        } catch (error) {
            showFeedback(error.message);
            render();
            return null;
        }
    },
    onRowSelect: (id, restore) => { selectedPlanItemId = selectedPlanItemId === id ? null : id; render(); if (restore && selectedPlanItemId) matrixView.focusPlanItemRow(id); },
    onInsertBefore: (item, occurrence, opener) => {
        const daily = plannerStore.getOccurrencesForDate(occurrence.date);
        const index = daily.findIndex(({ id }) => id === occurrence.id);
        planItemFormView.openInsertBefore(item, occurrence, index > 0 ? daily[index - 1].endTime : "", opener);
    },
    onEdit: (item, occurrence, opener, selectedDateKey, scheduleOnly) => (
        planItemFormView.openEdit(item, occurrence, selectedDateKey, opener, scheduleOnly)
    ),
    onDelete: (item, opener, selectedDateKey) => {
        const options = plannerStore.getDeletionOptions(item.id, selectedDateKey);
        deletionDialogView.open(options, {
            onDeleteOccurrence: (occurrenceId) => plannerStore.deleteOccurrenceForDate(occurrenceId),
            onStopPlanning: (planItemId, date) => plannerStore.stopPlanItemFromDate(planItemId, date),
            onComplete: (result, operation) => {
                selectedPlanItemId = result.planItem.id;
                render();
                showFeedback(
                    operation === "deleted_occurrence"
                        ? "La aparición fue eliminada únicamente para esta fecha."
                        : "La planificación futura fue detenida; el historial se conservó.",
                    "notice",
                );
            },
        });
    },
    onAmbiguity: (message) => showFeedback(message),
});

const overrideConfirmationView = createOverrideConfirmationView({
    dialog: elements.overrideDialog,
    candidateSummary: elements.overrideCandidateSummary,
    candidateOccurrences: elements.overrideCandidateOccurrences,
    conflictList: elements.overrideConflictList,
    consequence: elements.overrideConsequence,
    errorRegion: elements.overrideError,
    backButton: elements.overrideBackButton,
    continueButton: elements.overrideContinueButton,
});

const deletionDialogView = createDeletionDialogView({
    dialog: elements.deletionDialog,
    summary: elements.deletionSummary,
    deleteOccurrenceButton: elements.deleteOccurrenceButton,
    deleteOccurrenceDetails: elements.deleteOccurrenceDetails,
    stopPlanningButton: elements.stopPlanningButton,
    stopPlanningDetails: elements.stopPlanningDetails,
    errorRegion: elements.deletionError,
    backButton: elements.deletionBackButton,
    fallbackFocusElement: elements.addActivityButton,
});

function commitPreparedChange(prepared, context) {
    const result = plannerStore.commitPreparedScheduleChange(prepared);
    selectedPlanItemId = result.planItem?.id ?? context.planItemId;
    render();
    return result;
}

function applyFuturePlanning(planItemId, effectiveDate, generationConfig) {
    const result = plannerStore.applyGenerationConfigFromDate(planItemId, {
        ...generationConfig,
        startDate: effectiveDate,
    });
    return result.preservedEffectiveDateOccurrences.length ? PRESERVED_HISTORY_NOTICE : null;
}

const planItemFormView = createPlanItemFormView({
    ...elements, dialog: elements.activityDialog, form: elements.activityForm, title: elements.activityDialogTitle,
    referenceMessage: elements.insertionReference, errorsRegion: elements.formErrors, nameInput: elements.activityName,
    kindInput: elements.planItemKind, itemTypeInput: elements.planItemType, activityTypeField: elements.activitySubtypeField,
    habitTypeField: elements.habitSubtypeField, dateInput: elements.occurrenceDate, startTimeInput: elements.occurrenceStartTime,
    endTimeInput: elements.occurrenceEndTime, cancelButton: elements.cancelActivityButton,
    fallbackFocusElement: elements.addActivityButton, onValidate: () => [],
    onSubmit: (result, context) => {
        let prepared;
        let futureFeedback;
        if (context.mode === "edit") {
            if (result.recurrenceChanged && result.scope === "week") {
                plannerStore.applyWeeklyToWeek(context.planItemId, result.occurrence.date, result.generationConfig);
            } else if (result.recurrenceChanged && result.scope === "future") {
                futureFeedback = applyFuturePlanning(
                    context.planItemId,
                    result.occurrence.date,
                    result.generationConfig,
                );
            } else {
                prepared = plannerStore.prepareOccurrenceUpdate(
                    context.planItemId,
                    result.planItem,
                    context.occurrenceId,
                    result.occurrence,
                );
            }
            selectedPlanItemId = context.planItemId;
        } else if (context.mode === "edit_schedule") {
            if (result.recurrenceChanged && result.scope === "week") {
                plannerStore.applyWeeklyToWeek(context.planItemId, context.selectedDate, result.generationConfig);
            } else if (result.recurrenceChanged && result.scope === "future") {
                futureFeedback = applyFuturePlanning(
                    context.planItemId,
                    context.selectedDate,
                    result.generationConfig,
                );
            }
            selectedPlanItemId = context.planItemId;
        } else if (context.mode === "edit_without_occurrence") {
            if (result.recurrenceChanged && result.scope === "week") {
                plannerStore.applyWeeklyToWeek(context.planItemId, context.selectedDate, result.generationConfig);
            } else if (result.recurrenceChanged && result.scope === "future") {
                futureFeedback = applyFuturePlanning(
                    context.planItemId,
                    context.selectedDate,
                    result.generationConfig,
                );
            } else {
                prepared = plannerStore.prepareOccurrenceAddition(context.planItemId, result.occurrence);
            }
            selectedPlanItemId = context.planItemId;
        } else {
            prepared = plannerStore.preparePlanItemCreation({
                ...result.planItem,
                generationConfig: result.generationConfig,
            });
        }

        if (prepared?.type === "ready") {
            commitPreparedChange(prepared, context);
            return;
        }
        if (prepared?.type === "override_required") {
            overrideConfirmationView.open(prepared, {
                onConfirm: () => commitPreparedChange(prepared, context),
                onComplete: () => planItemFormView.completePendingSubmission(),
            });
            return { pendingConfirmation: true };
        }

        render();
        if (futureFeedback) showFeedback(futureFeedback, "notice");
        else if (futureFeedback === null) clearFeedback();
    },
    onFallbackFocus: (id) => { if (!matrixView.focusPlanItemRow(id)) elements.addActivityButton.focus(); },
});

matrixView.renderLegend();
render();
elements.previousDayButton.addEventListener("click", () => moveDay(-1));
elements.nextDayButton.addEventListener("click", () => moveDay(1));
elements.previousMonthButton.addEventListener("click", () => moveMonth(-1));
elements.nextMonthButton.addEventListener("click", () => moveMonth(1));
elements.compactPreviousMonthButton.addEventListener("click", () => moveMonth(-1));
elements.compactNextMonthButton.addEventListener("click", () => moveMonth(1));
elements.toggleMonthRecordsButton.addEventListener("click", () => { showAllMonthRecords = !showAllMonthRecords; selectedPlanItemId = null; render(); });
elements.datePickerButton.addEventListener("click", () => showNativePicker(elements.datePicker));
elements.monthPickerButton.addEventListener("click", () => showNativePicker(elements.monthPicker));
elements.datePicker.addEventListener("change", () => selectDate(elements.datePicker.value));
elements.monthPicker.addEventListener("change", () => {
    const [year, month] = elements.monthPicker.value.split("-").map(Number);
    if (year && month) synchronizeMonth(year, month - 1, "first");
});
elements.addActivityButton.addEventListener("click", () => planItemFormView.openCreate(formatDateKey(selectedDate), elements.addActivityButton));
