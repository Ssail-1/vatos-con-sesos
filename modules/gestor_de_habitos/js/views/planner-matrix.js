import {
    getStatusPresentation,
    occurrenceStatuses,
    statusDefinitions,
} from "../domain/occurrence-status.js";
import { getClassificationLabel } from "../domain/plan-item-classification.js";
import {
    calculateDuration,
    formatDateKey,
    formatSelectedDate,
    getWeekdayLabels,
    isSameLocalDate,
} from "../utils/date-time.js";

function createTextCell(tagName, className, text) {
    const cell = document.createElement(tagName);
    cell.className = className;
    cell.textContent = text;
    return cell;
}

function updateStatusButton(button, occurrence, planItemName, date) {
    const presentation = getStatusPresentation(
        occurrence.status,
        planItemName,
        formatSelectedDate(date),
    );
    button.dataset.status = presentation.status;
    button.textContent = presentation.symbol;
    button.setAttribute("aria-label", presentation.accessibleLabel);
    button.title = presentation.accessibleLabel;
}

function createStatusButton(planItem, occurrence, date, onStatusChange) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "status-button";
    button.dataset.occurrenceId = occurrence.id;
    button.dataset.date = occurrence.date;
    updateStatusButton(button, occurrence, planItem.name, date);
    button.addEventListener("click", (event) => {
        event.stopPropagation();
        const updatedOccurrence = onStatusChange(occurrence.id);
        if (updatedOccurrence) updateStatusButton(button, updatedOccurrence, planItem.name, date);
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
    Array.from(row.children).forEach((header) => (header.scope = "col"));
    monthDates.forEach((date) => row.append(createDayHeader(date, currentDate, selectedDate)));
    matrixHead.replaceChildren(row);
}

function buildRows(planItems, occurrences, selectedDateKey) {
    const occurrencesByPlanItem = new Map();
    occurrences.forEach((occurrence) => {
        if (!occurrencesByPlanItem.has(occurrence.planItemId)) {
            occurrencesByPlanItem.set(occurrence.planItemId, []);
        }
        occurrencesByPlanItem.get(occurrence.planItemId).push(occurrence);
    });
    return planItems
        .map((planItem) => {
            const itemOccurrences = occurrencesByPlanItem.get(planItem.id) ?? [];
            const selectedOccurrence = itemOccurrences.find(
                (occurrence) => occurrence.date === selectedDateKey,
            );
            return { planItem, occurrences: itemOccurrences, selectedOccurrence };
        })
        .filter((row) => row.occurrences.length > 0)
        .sort((first, second) => {
            const firstTime = first.selectedOccurrence?.startTime ?? first.occurrences[0].startTime;
            const secondTime = second.selectedOccurrence?.startTime ?? second.occurrences[0].startTime;
            return firstTime.localeCompare(secondTime) || first.planItem.name.localeCompare(second.planItem.name);
        });
}

function createPlanItemRow(rowData, position, context) {
    const { planItem, occurrences, selectedOccurrence } = rowData;
    const row = document.createElement("tr");
    const nameCell = document.createElement("th");
    const nameContent = document.createElement("span");
    const nameText = document.createElement("span");
    nameCell.className = "name-column activity-name";
    nameCell.scope = "row";
    nameContent.className = "activity-name-content";
    nameText.className = "activity-name-text";
    nameText.textContent = planItem.name;
    nameText.title = `${planItem.name} — ${getClassificationLabel(planItem)}`;
    nameContent.append(nameText);
    nameCell.append(nameContent);
    row.dataset.planItemId = planItem.id;
    row.tabIndex = 0;
    row.setAttribute("aria-selected", String(planItem.id === context.selectedPlanItemId));

    if (planItem.id === context.selectedPlanItemId) {
        row.classList.add("is-selected");
        const insertButton = document.createElement("button");
        insertButton.type = "button";
        insertButton.className = "context-add-button";
        insertButton.textContent = "+";
        insertButton.disabled = !selectedOccurrence;
        insertButton.setAttribute(
            "aria-label",
            selectedOccurrence
                ? `Agregar un registro antes de ${planItem.name}`
                : `${planItem.name} no está programado en la fecha seleccionada`,
        );
        insertButton.title = insertButton.getAttribute("aria-label");
        insertButton.addEventListener("click", (event) => {
            event.stopPropagation();
            if (selectedOccurrence) context.onInsertBefore(planItem, selectedOccurrence, insertButton);
        });

        const actions = document.createElement("span");
        const editButton = document.createElement("button");
        const deleteButton = document.createElement("button");
        actions.className = "row-actions";
        editButton.type = "button";
        editButton.className = "row-action-button edit-activity-button";
        editButton.textContent = "✎";
        editButton.disabled = !selectedOccurrence;
        editButton.setAttribute(
            "aria-label",
            selectedOccurrence
                ? `Editar ${planItem.name} en la fecha seleccionada`
                : `${planItem.name} no está programado en la fecha seleccionada`,
        );
        editButton.title = editButton.getAttribute("aria-label");
        editButton.addEventListener("click", (event) => {
            event.stopPropagation();
            if (selectedOccurrence) context.onEdit(planItem, selectedOccurrence, editButton);
        });
        deleteButton.type = "button";
        deleteButton.className = "row-action-button delete-activity-button";
        deleteButton.textContent = "🗑";
        deleteButton.disabled = true;
        deleteButton.setAttribute("aria-label", `Eliminar ${planItem.name} — disponible próximamente`);
        deleteButton.title = `Eliminar ${planItem.name} — disponible próximamente`;
        actions.append(editButton, deleteButton);
        nameContent.prepend(insertButton);
        nameContent.append(actions);
    }

    row.addEventListener("click", (event) => {
        if (event.target.closest("button, a, input, select")) return;
        context.onRowSelect(planItem.id, false);
    });
    row.addEventListener("keydown", (event) => {
        if (event.target !== row || !["Enter", " "].includes(event.key)) return;
        event.preventDefault();
        context.onRowSelect(planItem.id, true);
    });

    row.append(
        createTextCell("td", "position-column activity-position", String(position)),
        createTextCell("td", "time-column activity-time", selectedOccurrence?.startTime ?? "—"),
        createTextCell(
            "td",
            "duration-column activity-duration",
            selectedOccurrence
                ? calculateDuration(selectedOccurrence.startTime, selectedOccurrence.endTime)
                : "—",
        ),
        nameCell,
    );

    const occurrencesByDate = new Map();
    occurrences.forEach((occurrence) => {
        if (!occurrencesByDate.has(occurrence.date)) occurrencesByDate.set(occurrence.date, []);
        occurrencesByDate.get(occurrence.date).push(occurrence);
    });
    context.monthDates.forEach((date) => {
        const dateKey = formatDateKey(date);
        const cell = document.createElement("td");
        const dailyOccurrences = occurrencesByDate.get(dateKey) ?? [];
        cell.className = "day-column";
        cell.dataset.date = dateKey;
        if (isSameLocalDate(date, context.currentDate)) cell.classList.add("today-column");
        if (isSameLocalDate(date, context.selectedDate)) cell.classList.add("selected-day-column");
        if (dailyOccurrences.length === 0) {
            const marker = document.createElement("span");
            cell.classList.add("not-scheduled-cell");
            marker.textContent = "—";
            marker.setAttribute("role", "img");
            marker.setAttribute("aria-label", `${planItem.name} no está programado para ${formatSelectedDate(date)}.`);
            marker.title = marker.getAttribute("aria-label");
            cell.append(marker);
        } else {
            const controls = document.createElement("span");
            controls.className = "occurrence-controls";
            dailyOccurrences.forEach((occurrence) =>
                controls.append(createStatusButton(planItem, occurrence, date, context.onStatusChange)),
            );
            cell.append(controls);
        }
        row.append(cell);
    });
    return row;
}

function renderLegend(statusLegend) {
    const fragment = document.createDocumentFragment();
    occurrenceStatuses.forEach((status) => {
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

export function createPlannerMatrixView(context) {
    return {
        render({ planItems, occurrences, monthDates, currentDate, selectedDate, selectedPlanItemId }) {
            renderHeader(context.matrixHead, monthDates, currentDate, selectedDate);
            const selectedDateKey = formatDateKey(selectedDate);
            const rows = buildRows(planItems, occurrences, selectedDateKey);
            const fragment = document.createDocumentFragment();
            rows.forEach((rowData, index) =>
                fragment.append(
                    createPlanItemRow(rowData, index + 1, {
                        ...context,
                        monthDates,
                        currentDate,
                        selectedDate,
                        selectedPlanItemId,
                    }),
                ),
            );
            context.matrixBody.replaceChildren(fragment);
        },

        renderLegend() {
            renderLegend(context.statusLegend);
        },

        focusPlanItemRow(planItemId) {
            const row = context.matrixBody.querySelector(
                `[data-plan-item-id="${CSS.escape(planItemId)}"]`,
            );
            row?.focus();
            return Boolean(row);
        },
    };
}
