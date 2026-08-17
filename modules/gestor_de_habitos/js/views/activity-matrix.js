import {
    activityStates,
    getStatusPresentation,
    statusDefinitions,
} from "../domain/activity-status.js";
import {
    calculateDuration,
    formatDateKey,
    formatSelectedDate,
    getWeekdayLabels,
    isSameLocalDate,
} from "../utils/date-time.js";
import { getClassificationLabel } from "../domain/activity-classification.js";

function createTextCell(tagName, className, text) {
    const cell = document.createElement(tagName);
    cell.className = className;
    cell.textContent = text;
    return cell;
}

function updateStatusButton(button, status, activityName, date) {
    const presentation = getStatusPresentation(status, activityName, formatSelectedDate(date));
    button.dataset.status = presentation.status;
    button.textContent = presentation.symbol;
    button.setAttribute("aria-label", presentation.accessibleLabel);
    button.title = presentation.accessibleLabel;
}

function createStatusButton(activity, date, onStatusChange) {
    const dateKey = formatDateKey(date);
    const button = document.createElement("button");
    const status = activity.statesByDate[dateKey] || "pending";

    button.type = "button";
    button.className = "status-button";
    button.dataset.activityId = activity.id;
    button.dataset.date = dateKey;
    updateStatusButton(button, status, activity.name, date);

    button.addEventListener("click", (event) => {
        event.stopPropagation();
        const nextStatus = onStatusChange(activity.id, dateKey);
        if (nextStatus) updateStatusButton(button, nextStatus, activity.name, date);
    });
    return button;
}

function createDayHeader(date, currentDate, selectedDate) {
    const header = document.createElement("th");
    const heading = document.createElement("span");
    const weekday = document.createElement("abbr");
    const dayNumber = document.createElement("span");
    const weekdayLabels = getWeekdayLabels(date);

    header.scope = "col";
    header.className = "day-column";
    header.dataset.date = formatDateKey(date);
    heading.className = "day-heading";
    weekday.textContent = weekdayLabels.short;
    weekday.title = weekdayLabels.long;
    dayNumber.textContent = String(date.getDate());

    if (isSameLocalDate(date, currentDate)) header.classList.add("today-column");
    if (isSameLocalDate(date, selectedDate)) header.classList.add("selected-day-column");
    heading.append(weekday, dayNumber);
    header.append(heading);
    return header;
}

function renderHeader(matrixHead, monthDates, currentDate, selectedDate) {
    const row = document.createElement("tr");
    row.append(
        createTextCell("th", "position-column", "#"),
        createTextCell("th", "time-column", "Inicio"),
        createTextCell("th", "duration-column", "Duración"),
        createTextCell("th", "name-column", "Actividad"),
    );
    Array.from(row.children).forEach((header) => {
        header.scope = "col";
    });
    monthDates.forEach((date) => row.append(createDayHeader(date, currentDate, selectedDate)));
    matrixHead.replaceChildren(row);
}

function createActivityRow(activity, context) {
    const row = document.createElement("tr");
    const nameCell = document.createElement("th");
    const nameContent = document.createElement("span");
    const nameText = document.createElement("span");

    nameCell.className = "name-column activity-name";
    nameCell.scope = "row";
    nameContent.className = "activity-name-content";
    nameText.className = "activity-name-text";
    nameText.textContent = activity.name;
    nameText.title = `${activity.name} — ${getClassificationLabel(activity.recordKind, activity.recordSubtype)}`;
    nameContent.append(nameText);
    nameCell.append(nameContent);

    row.dataset.activityId = activity.id;
    row.tabIndex = 0;
    row.setAttribute("aria-selected", String(activity.id === context.selectedActivityId));
    if (activity.id === context.selectedActivityId) {
        row.classList.add("is-selected");
        const insertButton = document.createElement("button");
        insertButton.type = "button";
        insertButton.className = "context-add-button";
        insertButton.textContent = "+";
        insertButton.setAttribute("aria-label", `Agregar un registro antes de ${activity.name}`);
        insertButton.title = `Agregar un registro antes de ${activity.name}`;
        insertButton.addEventListener("click", (event) => {
            event.stopPropagation();
            context.onInsertBefore(activity.id, insertButton);
        });

        const actions = document.createElement("span");
        const editButton = document.createElement("button");
        const deleteButton = document.createElement("button");
        actions.className = "row-actions";
        editButton.type = "button";
        editButton.className = "row-action-button edit-activity-button";
        editButton.textContent = "✎";
        editButton.setAttribute("aria-label", `Editar ${activity.name}`);
        editButton.title = `Editar ${activity.name}`;
        editButton.addEventListener("click", (event) => {
            event.stopPropagation();
            context.onEdit(activity.id, editButton);
        });

        deleteButton.type = "button";
        deleteButton.className = "row-action-button delete-activity-button";
        deleteButton.textContent = "🗑";
        deleteButton.disabled = true;
        deleteButton.setAttribute(
            "aria-label",
            `Eliminar ${activity.name} — disponible próximamente`,
        );
        deleteButton.title = `Eliminar ${activity.name} — disponible próximamente`;
        actions.append(editButton, deleteButton);
        nameContent.prepend(insertButton);
        nameContent.append(actions);
    }

    row.addEventListener("click", (event) => {
        if (event.target.closest("button, a, input, select")) return;
        context.onRowSelect(activity.id, false);
    });
    row.addEventListener("keydown", (event) => {
        if (event.target !== row) return;
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        context.onRowSelect(activity.id, true);
    });

    row.append(
        createTextCell("td", "position-column activity-position", activity.position),
        createTextCell("td", "time-column activity-time", activity.plannedStartTime),
        createTextCell(
            "td",
            "duration-column activity-duration",
            calculateDuration(activity.plannedStartTime, activity.plannedEndTime),
        ),
        nameCell,
    );

    context.monthDates.forEach((date) => {
        const cell = document.createElement("td");
        cell.className = "day-column";
        cell.dataset.date = formatDateKey(date);
        if (isSameLocalDate(date, context.currentDate)) cell.classList.add("today-column");
        if (isSameLocalDate(date, context.selectedDate)) cell.classList.add("selected-day-column");
        cell.append(createStatusButton(activity, date, context.onStatusChange));
        row.append(cell);
    });
    return row;
}

function renderLegend(statusLegend) {
    const fragment = document.createDocumentFragment();
    activityStates.forEach((status) => {
        const item = document.createElement("li");
        const symbol = document.createElement("span");
        const label = document.createElement("span");
        const definition = statusDefinitions[status];

        item.className = "legend-item";
        symbol.className = "legend-symbol";
        symbol.style.setProperty("--legend-color", definition.color);
        symbol.textContent = definition.symbol;
        symbol.setAttribute("aria-hidden", "true");
        label.textContent = definition.label;
        item.append(symbol, label);
        fragment.append(item);
    });
    statusLegend.replaceChildren(fragment);
}

export function createActivityMatrixView({
    matrixHead,
    matrixBody,
    statusLegend,
    onStatusChange,
    onRowSelect,
    onInsertBefore,
    onEdit,
}) {
    return {
        render({ activities, monthDates, currentDate, selectedDate, selectedActivityId }) {
            renderHeader(matrixHead, monthDates, currentDate, selectedDate);
            const fragment = document.createDocumentFragment();
            activities.forEach((activity) => {
                fragment.append(
                    createActivityRow(activity, {
                        monthDates,
                        currentDate,
                        selectedDate,
                        selectedActivityId,
                        onStatusChange,
                        onRowSelect,
                        onInsertBefore,
                        onEdit,
                    }),
                );
            });
            matrixBody.replaceChildren(fragment);
        },

        renderLegend() {
            renderLegend(statusLegend);
        },

        updateSelectedDate(selectedDate) {
            const selectedDateKey = formatDateKey(selectedDate);
            document.querySelectorAll(".selected-day-column").forEach((element) => {
                element.classList.remove("selected-day-column");
            });
            document.querySelectorAll(`[data-date="${selectedDateKey}"]`).forEach((element) => {
                element.classList.add("selected-day-column");
            });
        },

        focusActivityRow(activityId) {
            matrixBody.querySelector(`[data-activity-id="${CSS.escape(activityId)}"]`)?.focus();
        },
    };
}
