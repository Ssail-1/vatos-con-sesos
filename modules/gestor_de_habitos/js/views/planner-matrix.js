import {
    getStatusPresentation,
    occurrenceStatuses,
    statusDefinitions,
} from "../domain/occurrence-status.js";
import { getClassificationLabel } from "../domain/plan-item-classification.js";
import { getDateTemporalZone, getOccurrenceTemporalPolicy, TEMPORAL_ZONES } from "../domain/temporal-integrity.js";
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

function updateStatusButton(button, occurrence, planItemName, date, currentDate, ordinal = null) {
    const referenceDate = formatDateKey(currentDate);
    const policy = getOccurrenceTemporalPolicy(occurrence, referenceDate);
    const readOnlyMessage = policy.zone === TEMPORAL_ZONES.FROZEN
        ? "Historial congelado, solo lectura."
        : "En el futuro solo Pendiente y Cancelada pueden modificarse.";
    const presentation = getStatusPresentation(
        occurrence.status,
        planItemName,
        formatSelectedDate(date),
        policy.canChangeStatus ? "Activar para cambiar estado." : readOnlyMessage,
    );
    button.dataset.status = presentation.status;
    button.textContent = presentation.symbol;
    button.disabled = !policy.canChangeStatus;
    const occurrencePosition = ordinal
        ? ` Horario ${ordinal.position} de ${ordinal.total}.`
        : "";
    const accessibleLabel = `${presentation.accessibleLabel}${occurrencePosition}`;
    button.setAttribute("aria-label", accessibleLabel);
    button.title = accessibleLabel;
}

function createStatusButton(planItem, occurrence, date, currentDate, onStatusChange, ordinal = null) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "status-button";
    button.dataset.occurrenceId = occurrence.id;
    button.dataset.date = occurrence.date;
    updateStatusButton(button, occurrence, planItem.name, date, currentDate, ordinal);
    button.addEventListener("click", (event) => {
        event.stopPropagation();
        const updatedOccurrence = onStatusChange(occurrence.id);
        if (updatedOccurrence) {
            updateStatusButton(button, updatedOccurrence, planItem.name, date, currentDate, ordinal);
        }
    });
    return button;
}

function createDayHeader(date, selectedDate, onDateSelect) {
    const header = document.createElement("th");
    const heading = document.createElement("button");
    const weekday = document.createElement("abbr");
    const dayNumber = document.createElement("span");
    const weekdayLabels = getWeekdayLabels(date);
    header.scope = "col";
    header.className = "day-column";
    header.dataset.date = formatDateKey(date);
    heading.type = "button";
    heading.className = "day-heading";
    heading.setAttribute("aria-label", `Ver planificación del ${formatSelectedDate(date)}`);
    heading.setAttribute("aria-pressed", String(isSameLocalDate(date, selectedDate)));
    heading.addEventListener("click", () => onDateSelect(formatDateKey(date)));
    weekday.textContent = weekdayLabels.short;
    weekday.title = weekdayLabels.long;
    dayNumber.textContent = String(date.getDate());
    if (isSameLocalDate(date, selectedDate)) header.classList.add("selected-day-column");
    heading.append(weekday, dayNumber);
    header.append(heading);
    return header;
}

function renderHeader(matrixHead, monthDates, selectedDate, onDateSelect) {
    const row = document.createElement("tr");
    row.append(
        createTextCell("th", "position-column", "#"),
        createTextCell("th", "time-column", "Inicio"),
        createTextCell("th", "duration-column", "Duración"),
        createTextCell("th", "name-column", "Actividad"),
    );
    Array.from(row.children).forEach((header) => (header.scope = "col"));
    monthDates.forEach((date) => row.append(createDayHeader(date, selectedDate, onDateSelect)));
    matrixHead.replaceChildren(row);
}

function compareOccurrences(first, second, planItemsById) {
    const firstPlanItem = planItemsById.get(first.planItemId);
    const secondPlanItem = planItemsById.get(second.planItemId);
    return first.startTime.localeCompare(second.startTime)
        || first.endTime.localeCompare(second.endTime)
        || (firstPlanItem?.name ?? "").localeCompare(secondPlanItem?.name ?? "")
        || first.planItemId.localeCompare(second.planItemId)
        || first.id.localeCompare(second.id);
}

function groupOccurrencesByDate(occurrences) {
    const byDate = new Map();
    occurrences.forEach((occurrence) => {
        if (!byDate.has(occurrence.date)) byDate.set(occurrence.date, []);
        byDate.get(occurrence.date).push(occurrence);
    });
    byDate.forEach((dailyOccurrences) => dailyOccurrences.sort(
        (first, second) => first.startTime.localeCompare(second.startTime)
            || first.endTime.localeCompare(second.endTime)
            || first.id.localeCompare(second.id),
    ));
    return byDate;
}

export function buildPlannerRows(planItems, occurrences, selectedDateKey) {
    const planItemsById = new Map(planItems.map((planItem) => [planItem.id, planItem]));
    const occurrencesByPlanItem = new Map();
    occurrences.forEach((occurrence) => {
        if (!planItemsById.has(occurrence.planItemId)) return;
        if (!occurrencesByPlanItem.has(occurrence.planItemId)) {
            occurrencesByPlanItem.set(occurrence.planItemId, []);
        }
        occurrencesByPlanItem.get(occurrence.planItemId).push(occurrence);
    });
    const itemModels = planItems.map((planItem) => {
        const itemOccurrences = occurrencesByPlanItem.get(planItem.id) ?? [];
        const occurrencesByDate = groupOccurrencesByDate(itemOccurrences);
        return {
            planItem,
            occurrences: itemOccurrences,
            occurrencesByDate,
            selectedOccurrences: occurrencesByDate.get(selectedDateKey) ?? [],
        };
    }).filter(({ occurrences: itemOccurrences }) => itemOccurrences.length > 0);

    const modelsByPlanItem = new Map(itemModels.map((model) => [model.planItem.id, model]));
    const ordinalByOccurrenceId = new Map();
    itemModels.forEach(({ selectedOccurrences }) => {
        selectedOccurrences.forEach((occurrence, index) => {
            ordinalByOccurrenceId.set(occurrence.id, index + 1);
        });
    });

    const carrierPlanItemIds = new Set();
    const occurrenceRows = occurrences
        .filter((occurrence) => occurrence.date === selectedDateKey && modelsByPlanItem.has(occurrence.planItemId))
        .sort((first, second) => compareOccurrences(first, second, planItemsById))
        .map((occurrence) => {
            const model = modelsByPlanItem.get(occurrence.planItemId);
            const carriesMonthlySummary = !carrierPlanItemIds.has(occurrence.planItemId);
            carrierPlanItemIds.add(occurrence.planItemId);
            return {
                rowType: "occurrence",
                ...model,
                occurrence,
                startTime: occurrence.startTime,
                duration: calculateDuration(occurrence.startTime, occurrence.endTime),
                selectedOccurrence: occurrence,
                selectedDateAmbiguous: model.selectedOccurrences.length > 1,
                occurrenceOrdinal: ordinalByOccurrenceId.get(occurrence.id),
                occurrenceCount: model.selectedOccurrences.length,
                carriesMonthlySummary,
            };
        });

    const summaryRows = itemModels
        .filter(({ selectedOccurrences }) => selectedOccurrences.length === 0)
        .map((model) => ({
            rowType: "summary",
            ...model,
            occurrence: null,
            startTime: null,
            duration: null,
            selectedOccurrence: null,
            selectedDateAmbiguous: false,
            occurrenceOrdinal: null,
            occurrenceCount: 0,
            carriesMonthlySummary: true,
        }));

    return [...occurrenceRows, ...summaryRows];
}

export function getPlannerCellModel(rowData, dateKey, selectedDateKey) {
    if (dateKey === selectedDateKey) {
        if (rowData.rowType === "occurrence") {
            return {
                type: "occurrence",
                occurrence: rowData.occurrence,
                ordinal: rowData.occurrenceCount > 1 ? rowData.occurrenceOrdinal : null,
                total: rowData.occurrenceCount,
            };
        }
        return { type: "empty" };
    }
    if (!rowData.carriesMonthlySummary) return { type: "duplicate-summary" };
    const dailyOccurrences = rowData.occurrencesByDate.get(dateKey) ?? [];
    if (dailyOccurrences.length === 0) return { type: "empty" };
    if (dailyOccurrences.length === 1) {
        return { type: "occurrence", occurrence: dailyOccurrences[0], ordinal: null, total: 1 };
    }
    return { type: "compact-count", count: dailyOccurrences.length };
}

function createPlanItemRow(rowData, position, context) {
    const {
        planItem,
        occurrence,
        selectedOccurrence,
        selectedDateAmbiguous,
    } = rowData;
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
    row.dataset.rowType = rowData.rowType;
    if (occurrence) row.dataset.occurrenceId = occurrence.id;
    row.tabIndex = 0;
    row.setAttribute("aria-selected", String(planItem.id === context.selectedPlanItemId));

    if (planItem.id === context.selectedPlanItemId) {
        const referenceDate = formatDateKey(context.currentDate);
        const selectedDateKey = formatDateKey(context.selectedDate);
        const selectedDateFrozen = getDateTemporalZone(selectedDateKey, referenceDate) === TEMPORAL_ZONES.FROZEN;
        const selectedOccurrencePolicy = selectedOccurrence
            ? getOccurrenceTemporalPolicy(selectedOccurrence, referenceDate)
            : null;
        row.classList.add("is-selected");
        const insertButton = document.createElement("button");
        insertButton.type = "button";
        insertButton.className = "context-add-button";
        insertButton.textContent = "+";
        insertButton.disabled = !selectedOccurrence || !selectedOccurrencePolicy.canEditSchedule;
        insertButton.setAttribute(
            "aria-label",
            selectedDateFrozen
                ? `${planItem.name}: historial congelado, no se puede agregar desde esta fecha`
                : selectedOccurrence
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
        editButton.setAttribute(
            "aria-label",
            selectedDateFrozen
                ? `${planItem.name}: historial congelado, solo lectura`
                : selectedDateAmbiguous
                ? `Editar planificación completa de ${planItem.name}; la fecha seleccionada tiene varios horarios`
                : selectedOccurrence
                ? `Editar ${planItem.name} en la fecha seleccionada`
                : `Editar planificación de ${planItem.name} desde la fecha seleccionada`,
        );
        editButton.disabled = selectedDateFrozen;
        editButton.title = editButton.getAttribute("aria-label");
        editButton.addEventListener("click", (event) => {
            event.stopPropagation();
            if (!editButton.disabled) {
                context.onEdit(
                    planItem,
                    selectedOccurrence,
                    editButton,
                    formatDateKey(context.selectedDate),
                    selectedDateAmbiguous,
                );
            }
        });
        deleteButton.type = "button";
        deleteButton.className = "row-action-button delete-activity-button";
        deleteButton.textContent = "🗑";
        deleteButton.setAttribute(
            "aria-label",
            selectedDateFrozen
                ? `Consultar eliminación de ${planItem.name}: historial congelado`
                : `Gestionar eliminación de ${planItem.name} desde la fecha seleccionada`,
        );
        deleteButton.title = deleteButton.getAttribute("aria-label");
        deleteButton.addEventListener("click", (event) => {
            event.stopPropagation();
            context.onDelete(planItem, deleteButton, selectedDateKey);
        });
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
        createTextCell(
            "td",
            "time-column activity-time",
            rowData.startTime ?? "—",
        ),
        createTextCell(
            "td",
            "duration-column activity-duration",
            rowData.duration ?? "—",
        ),
        nameCell,
    );

    const selectedDateKey = formatDateKey(context.selectedDate);
    context.monthDates.forEach((date) => {
        const dateKey = formatDateKey(date);
        const cell = document.createElement("td");
        const cellModel = getPlannerCellModel(rowData, dateKey, selectedDateKey);
        cell.className = "day-column";
        cell.dataset.date = dateKey;
        if (isSameLocalDate(date, context.selectedDate)) cell.classList.add("selected-day-column");
        if (date.getDay() === 1 && date.getDate() !== 1) cell.classList.add("week-boundary-column");
        if (cellModel.type === "duplicate-summary") {
            cell.classList.add("duplicate-summary-cell");
            cell.setAttribute("aria-hidden", "true");
        } else if (cellModel.type === "empty") {
            const marker = document.createElement("span");
            cell.classList.add("not-scheduled-cell");
            marker.textContent = "—";
            marker.setAttribute("role", "img");
            marker.setAttribute("aria-label", `${planItem.name} no está programado para ${formatSelectedDate(date)}.`);
            marker.title = marker.getAttribute("aria-label");
            cell.append(marker);
        } else if (cellModel.type === "compact-count") {
            const marker = document.createElement("span");
            const count = document.createElement("sup");
            const accessibleLabel = `${cellModel.count} occurrences de ${planItem.name} para ${formatSelectedDate(date)}.`;
            cell.classList.add("compact-occurrence-cell");
            marker.className = "compact-occurrence-count";
            marker.setAttribute("role", "img");
            marker.setAttribute("aria-label", accessibleLabel);
            marker.title = accessibleLabel;
            marker.append(document.createTextNode("—"));
            count.textContent = String(cellModel.count);
            count.setAttribute("aria-hidden", "true");
            marker.append(count);
            cell.append(marker);
        } else {
            const controls = document.createElement("span");
            controls.className = "occurrence-controls";
            controls.append(
                createStatusButton(
                    planItem,
                    cellModel.occurrence,
                    date,
                    context.currentDate,
                    context.onStatusChange,
                    cellModel.ordinal ? { position: cellModel.ordinal, total: cellModel.total } : null,
                ),
            );
            if (cellModel.ordinal) {
                const ordinal = document.createElement("sup");
                ordinal.className = "occurrence-ordinal";
                ordinal.textContent = String(cellModel.ordinal);
                ordinal.setAttribute("aria-hidden", "true");
                controls.append(ordinal);
            }
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
        symbol.dataset.status = status;
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
        render({ planItems, occurrences, monthDates, currentDate, selectedDate, selectedPlanItemId, showAllMonthRecords }) {
            renderHeader(context.matrixHead, monthDates, selectedDate, context.onDateSelect);
            const selectedDateKey = formatDateKey(selectedDate);
            const displayRows = buildPlannerRows(planItems, occurrences, selectedDateKey);
            const rows = showAllMonthRecords
                ? displayRows
                : displayRows.filter(({ rowType }) => rowType === "occurrence");
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
            return rows.length;
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
