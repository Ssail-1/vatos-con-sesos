import { initialPlanItems } from "./data/mock-plan-items.js";
import { mockStatusOverrides } from "./data/mock-status-overrides.js";
import { createPlannerStore } from "./state/planner-store.js";
import { formatDateKey, formatMonth, formatSelectedDate, getMonthDates } from "./utils/date-time.js";
import { createPlanItemFormView } from "./views/plan-item-form.js";
import { createPlannerMatrixView } from "./views/planner-matrix.js";

const elements = {
    monthName: document.getElementById("monthName"),
    selectedDateLabel: document.getElementById("selectedDateLabel"),
    previousDayButton: document.getElementById("previousDayButton"),
    nextDayButton: document.getElementById("nextDayButton"),
    matrixHead: document.getElementById("matrixHead"),
    matrixBody: document.getElementById("matrixBody"),
    matrixFeedback: document.getElementById("matrixFeedback"),
    statusLegend: document.getElementById("statusLegend"),
    addActivityButton: document.getElementById("addActivityButton"),
    activityDialog: document.getElementById("activityDialog"),
    activityForm: document.getElementById("activityForm"),
    activityDialogTitle: document.getElementById("activityDialogTitle"),
    insertionReference: document.getElementById("insertionReference"),
    formErrors: document.getElementById("formErrors"),
    activityName: document.getElementById("activityName"),
    planItemKind: document.getElementById("planItemKind"),
    planItemType: document.getElementById("planItemType"),
    activitySubtypeField: document.getElementById("activitySubtypeField"),
    habitSubtypeField: document.getElementById("habitSubtypeField"),
    occurrenceDate: document.getElementById("occurrenceDate"),
    occurrenceStartTime: document.getElementById("occurrenceStartTime"),
    occurrenceEndTime: document.getElementById("occurrenceEndTime"),
    cancelActivityButton: document.getElementById("cancelActivityButton"),
};

const currentDate = new Date();
const currentYear = currentDate.getFullYear();
const currentMonth = currentDate.getMonth();
const monthDates = getMonthDates(currentYear, currentMonth);
const plannerStore = createPlannerStore(
    initialPlanItems,
    mockStatusOverrides,
    formatDateKey(currentDate),
);
let selectedDate = new Date(currentYear, currentMonth, currentDate.getDate());
let selectedPlanItemId = null;

function clearFeedback() {
    elements.matrixFeedback.hidden = true;
    elements.matrixFeedback.textContent = "";
}

function showFeedback(message) {
    elements.matrixFeedback.textContent = message;
    elements.matrixFeedback.hidden = false;
}

function renderMatrix() {
    matrixView.render({
        planItems: plannerStore.getPlanItems(),
        occurrences: plannerStore.getOccurrencesForMonth(currentYear, currentMonth),
        monthDates,
        currentDate,
        selectedDate,
        selectedPlanItemId,
    });
}

function getConflictError(conflict) {
    return conflict
        ? [{
              field: "startTime",
              message: `El horario se cruza con “${conflict.planItemName}” (${conflict.startTime}–${conflict.endTime}).`,
          }]
        : [];
}

const matrixView = createPlannerMatrixView({
    matrixHead: elements.matrixHead,
    matrixBody: elements.matrixBody,
    statusLegend: elements.statusLegend,
    onStatusChange: (occurrenceId) => {
        clearFeedback();
        try {
            return plannerStore.advanceOccurrenceStatus(occurrenceId);
        } catch (error) {
            const conflict = error.details?.conflictingOccurrence;
            showFeedback(
                conflict
                    ? `No se cambió el estado: el horario está ocupado por “${conflict.planItemName}” (${conflict.startTime}–${conflict.endTime}).`
                    : error.message,
            );
            return null;
        }
    },
    onRowSelect: (planItemId, shouldRestoreRowFocus) => {
        selectedPlanItemId = selectedPlanItemId === planItemId ? null : planItemId;
        clearFeedback();
        renderMatrix();
        if (shouldRestoreRowFocus && selectedPlanItemId) matrixView.focusPlanItemRow(selectedPlanItemId);
    },
    onInsertBefore: (planItem, referenceOccurrence, opener) => {
        const dailyOccurrences = plannerStore.getOccurrencesForDate(referenceOccurrence.date);
        const referenceIndex = dailyOccurrences.findIndex(
            (occurrence) => occurrence.id === referenceOccurrence.id,
        );
        const previousOccurrence = referenceIndex > 0 ? dailyOccurrences[referenceIndex - 1] : null;
        planItemFormView.openInsertBefore(
            planItem,
            referenceOccurrence,
            previousOccurrence?.endTime || "",
            opener,
        );
    },
    onEdit: (planItem, occurrence, opener) => {
        planItemFormView.openEdit(planItem, occurrence, opener);
    },
});

const planItemFormView = createPlanItemFormView({
    dialog: elements.activityDialog,
    form: elements.activityForm,
    title: elements.activityDialogTitle,
    referenceMessage: elements.insertionReference,
    errorsRegion: elements.formErrors,
    nameInput: elements.activityName,
    kindInput: elements.planItemKind,
    itemTypeInput: elements.planItemType,
    activityTypeField: elements.activitySubtypeField,
    habitTypeField: elements.habitSubtypeField,
    dateInput: elements.occurrenceDate,
    startTimeInput: elements.occurrenceStartTime,
    endTimeInput: elements.occurrenceEndTime,
    cancelButton: elements.cancelActivityButton,
    fallbackFocusElement: elements.addActivityButton,
    onValidate: (result, context) => {
        const ignoredOccurrenceId = context.mode === "edit" ? context.occurrenceId : null;
        return getConflictError(
            plannerStore.findTimeConflict(
                result.occurrence.date,
                result.occurrence.startTime,
                result.occurrence.endTime,
                ignoredOccurrenceId,
            ),
        );
    },
    onSubmit: (result, context) => {
        clearFeedback();
        if (context.mode === "edit") {
            plannerStore.updatePlanItemAndOccurrence(
                context.planItemId,
                result.planItem,
                context.occurrenceId,
                result.occurrence,
            );
            selectedPlanItemId = context.planItemId;
        } else {
            const creationResult = plannerStore.addPlanItem({
                ...result.planItem,
                generationConfig: {
                    mode: "single_date",
                    date: result.occurrence.date,
                    startTime: result.occurrence.startTime,
                    endTime: result.occurrence.endTime,
                },
            });
            selectedPlanItemId = creationResult.planItem.id;
        }
        renderMatrix();
    },
    onFallbackFocus: (planItemId) => {
        if (!matrixView.focusPlanItemRow(planItemId)) elements.addActivityButton.focus();
    },
});

function updateSelectedDatePresentation() {
    elements.selectedDateLabel.textContent = formatSelectedDate(selectedDate);
    elements.previousDayButton.disabled = selectedDate.getDate() === 1;
    elements.nextDayButton.disabled = selectedDate.getDate() === monthDates.length;
    clearFeedback();
    renderMatrix();
}

function moveSelectedDate(dayDifference) {
    const candidate = new Date(currentYear, currentMonth, selectedDate.getDate() + dayDifference);
    if (candidate.getMonth() !== currentMonth) return;
    selectedDate = candidate;
    selectedPlanItemId = null;
    updateSelectedDatePresentation();
}

function initializeApplication() {
    elements.monthName.textContent = formatMonth(currentDate);
    matrixView.renderLegend();
    updateSelectedDatePresentation();
    elements.previousDayButton.addEventListener("click", () => moveSelectedDate(-1));
    elements.nextDayButton.addEventListener("click", () => moveSelectedDate(1));
    elements.addActivityButton.addEventListener("click", () => {
        planItemFormView.openCreate(formatDateKey(selectedDate), elements.addActivityButton);
    });
}

initializeApplication();
