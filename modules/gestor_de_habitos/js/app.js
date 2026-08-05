import { initialActivities } from "./data/mock-activities.js";
import { createActivityStore } from "./state/activity-store.js";
import {
    formatMonth,
    formatSelectedDate,
    getMonthDates,
} from "./utils/date-time.js";
import { createActivityMatrixView } from "./views/activity-matrix.js";
import { createActivityFormView } from "./views/activity-form.js";

const elements = {
    monthName: document.getElementById("monthName"),
    selectedDateLabel: document.getElementById("selectedDateLabel"),
    previousDayButton: document.getElementById("previousDayButton"),
    nextDayButton: document.getElementById("nextDayButton"),
    matrixHead: document.getElementById("matrixHead"),
    matrixBody: document.getElementById("matrixBody"),
    statusLegend: document.getElementById("statusLegend"),
    addActivityButton: document.getElementById("addActivityButton"),
    activityDialog: document.getElementById("activityDialog"),
    activityForm: document.getElementById("activityForm"),
    activityDialogTitle: document.getElementById("activityDialogTitle"),
    insertionReference: document.getElementById("insertionReference"),
    formErrors: document.getElementById("formErrors"),
    activityName: document.getElementById("activityName"),
    plannedStartTime: document.getElementById("plannedStartTime"),
    plannedEndTime: document.getElementById("plannedEndTime"),
    cancelActivityButton: document.getElementById("cancelActivityButton"),
};

const currentDate = new Date();
const currentYear = currentDate.getFullYear();
const currentMonth = currentDate.getMonth();
const monthDates = getMonthDates(currentYear, currentMonth);
const activityStore = createActivityStore(initialActivities);
let selectedDate = new Date(currentYear, currentMonth, currentDate.getDate());
let selectedActivityId = null;

function renderMatrix() {
    matrixView.render({
        activities: activityStore.getActivities(),
        monthDates,
        currentDate,
        selectedDate,
        selectedActivityId,
    });
}

const matrixView = createActivityMatrixView({
    matrixHead: elements.matrixHead,
    matrixBody: elements.matrixBody,
    statusLegend: elements.statusLegend,
    onStatusChange: (activityId, dateKey) =>
        activityStore.advanceActivityStatus(activityId, dateKey),
    onRowSelect: (activityId, shouldRestoreRowFocus) => {
        selectedActivityId = selectedActivityId === activityId ? null : activityId;
        renderMatrix();
        if (shouldRestoreRowFocus && selectedActivityId) {
            matrixView.focusActivityRow(selectedActivityId);
        }
    },
    onInsertBefore: (activityId, opener) => {
        const referenceActivity = activityStore.getActivityById(activityId);
        if (referenceActivity) activityFormView.openInsertBefore(referenceActivity, opener);
    },
});

const activityFormView = createActivityFormView({
    dialog: elements.activityDialog,
    form: elements.activityForm,
    title: elements.activityDialogTitle,
    referenceMessage: elements.insertionReference,
    errorsRegion: elements.formErrors,
    nameInput: elements.activityName,
    startTimeInput: elements.plannedStartTime,
    endTimeInput: elements.plannedEndTime,
    cancelButton: elements.cancelActivityButton,
    fallbackFocusElement: elements.addActivityButton,
    onSubmit: (activityDraft, context) => {
        if (context.mode === "insert_before") {
            activityStore.insertActivityBefore(activityDraft, context.referenceActivityId);
        } else {
            activityStore.addActivity(activityDraft);
        }
        selectedActivityId = null;
        renderMatrix();
    },
});

function updateSelectedDatePresentation() {
    matrixView.updateSelectedDate(selectedDate);
    elements.selectedDateLabel.textContent = formatSelectedDate(selectedDate);
    elements.previousDayButton.disabled = selectedDate.getDate() === 1;
    elements.nextDayButton.disabled = selectedDate.getDate() === monthDates.length;
}

function moveSelectedDate(dayDifference) {
    const candidate = new Date(currentYear, currentMonth, selectedDate.getDate() + dayDifference);
    if (candidate.getMonth() !== currentMonth) return;
    selectedDate = candidate;
    updateSelectedDatePresentation();
}

function initializeApplication() {
    elements.monthName.textContent = formatMonth(currentDate);
    renderMatrix();
    matrixView.renderLegend();
    updateSelectedDatePresentation();

    elements.previousDayButton.addEventListener("click", () => moveSelectedDate(-1));
    elements.nextDayButton.addEventListener("click", () => moveSelectedDate(1));
    elements.addActivityButton.addEventListener("click", () => {
        activityFormView.openAppend(elements.addActivityButton);
    });
}

initializeApplication();
