import {
    getSelectableSegmentStatuses,
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
import { deriveAggregateOccurrenceDisplay } from "./aggregate-occurrence-display.js";
import {
    calculateSegmentDuration,
    isMultiSegmentOccurrence,
} from "../domain/occurrence-segments.js";

function createTextCell(tagName, className, text) {
    const cell = document.createElement(tagName);
    cell.className = className;
    cell.textContent = text;
    return cell;
}

function createSegmentStatusSelect(planItem, occurrence, segment, date, currentDate, onStatusChange, pending, ordinal = null) {
    const referenceDate = formatDateKey(currentDate);
    const zone = getDateTemporalZone(occurrence.date, referenceDate);
    const choices = getSelectableSegmentStatuses(occurrence.date, referenceDate, zone);
    const wrapper = document.createElement("span");
    wrapper.className = "status-button segment-status-picker";
    wrapper.dataset.status = segment.status;
    const glyph = document.createElement("span");
    glyph.textContent = statusDefinitions[segment.status].symbol;
    glyph.setAttribute("aria-hidden", "true");
    const select = document.createElement("select");
    select.className = "segment-status-select";
    select.dataset.occurrenceId = occurrence.id;
    select.dataset.segmentId = segment.id;
    select.dataset.date = occurrence.date;
    select.dataset.status = segment.status;
    for (const status of choices.includes(segment.status) ? choices : [segment.status, ...choices]) {
        const option = document.createElement("option");
        const definition = statusDefinitions[status];
        option.value = status;
        option.textContent = `${definition.symbol}${definition.modifier ?? ""} ${definition.label}`;
        option.disabled = !choices.includes(status);
        select.append(option);
    }
    select.value = segment.status;
    select.disabled = pending || zone === TEMPORAL_ZONES.FROZEN;
    if (select.disabled) wrapper.classList.add("is-disabled");
    const occurrencePosition = ordinal
        ? ` Horario ${ordinal.position} de ${ordinal.total}.`
        : "";
    const accessibleLabel = `${planItem.name}, ${formatSelectedDate(date)}: estado de Segment${occurrencePosition} ${statusDefinitions[segment.status].label}.`
        + (select.disabled ? " Solo lectura." : " Seleccionar nuevo estado.");
    select.setAttribute("aria-label", accessibleLabel);
    select.title = accessibleLabel;
    select.addEventListener("click", (event) => event.stopPropagation());
    select.addEventListener("change", (event) => {
        event.stopPropagation();
        if (select.disabled || !choices.includes(select.value) || select.value === segment.status) return;
        onStatusChange({
            occurrenceId: occurrence.id,
            segmentId: segment.id,
            status: select.value,
        });
    });
    wrapper.append(glyph, select);
    return wrapper;
}

function createReadOnlyStatus(status, accessibleLabel, className = "status-button") {
    const marker = document.createElement("span");
    const definition = statusDefinitions[status];
    marker.className = [
        "status-button",
        "status-read-only",
        className === "status-button" ? "" : className,
    ].filter(Boolean).join(" ");
    marker.dataset.status = status;
    marker.textContent = definition.symbol;
    marker.setAttribute("role", "img");
    marker.setAttribute("aria-label", accessibleLabel);
    marker.title = accessibleLabel;
    return marker;
}

function createOccurrenceStatusControl(
    planItem,
    occurrence,
    date,
    currentDate,
    onStatusChange,
    statusMutationPending,
    ordinal = null,
) {
    if (!isMultiSegmentOccurrence(occurrence)) {
        return createSegmentStatusSelect(
            planItem,
            occurrence,
            occurrence.segments[0],
            date,
            currentDate,
            onStatusChange,
            statusMutationPending,
            ordinal,
        );
    }
    const definition = statusDefinitions[occurrence.status];
    return createReadOnlyStatus(
        occurrence.status,
        `${planItem.name}, ${formatSelectedDate(date)}: ${definition.label}. `
            + "Estado agregado de una occurrence con varios segments; solo lectura.",
    );
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
        createTextCell("th", "end-time-column", "Final"),
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

export function buildPlannerRows(
    planItems,
    occurrences,
    selectedDateKey,
    expandedOccurrenceIds = new Set(),
) {
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
                endTime: occurrence.endTime,
                duration: calculateSegmentDuration(occurrence.segments)
                    ?? calculateDuration(occurrence.startTime, occurrence.endTime),
                selectedOccurrence: occurrence,
                selectedDateAmbiguous: model.selectedOccurrences.length > 1,
                occurrenceOrdinal: ordinalByOccurrenceId.get(occurrence.id),
                occurrenceCount: model.selectedOccurrences.length,
                carriesMonthlySummary,
            };
        })
        .flatMap((parentRow) => {
            if (
                !isMultiSegmentOccurrence(parentRow.occurrence)
                || !expandedOccurrenceIds.has(parentRow.occurrence.id)
            ) {
                return [parentRow];
            }
            return [
                parentRow,
                ...parentRow.occurrence.segments.map((segment, index) => ({
                    ...parentRow,
                    rowType: "segment",
                    segment,
                    segmentOrdinal: index + 1,
                    startTime: segment.startTime,
                    endTime: segment.endTime,
                    duration: calculateDuration(segment.startTime, segment.endTime),
                    carriesMonthlySummary: false,
                })),
            ];
        });

    const summaryRows = itemModels
        .filter(({ selectedOccurrences }) => selectedOccurrences.length === 0)
        .map((model) => ({
            rowType: "summary",
            ...model,
            occurrence: null,
            startTime: null,
            endTime: null,
            duration: null,
            selectedOccurrence: null,
            selectedDateAmbiguous: false,
            occurrenceOrdinal: null,
            occurrenceCount: 0,
            carriesMonthlySummary: true,
        }));

    return [...occurrenceRows, ...summaryRows];
}

export function getPlannerCellModel(rowData, dateKey, selectedDateKey, currentDateKey = null) {
    if (dateKey === selectedDateKey) {
        if (rowData.rowType === "segment") {
            return {
                type: "segment",
                occurrence: rowData.occurrence,
                segment: rowData.segment,
            };
        }
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
    if (rowData.rowType === "segment") return { type: "duplicate-summary" };
    if (!rowData.carriesMonthlySummary) return { type: "duplicate-summary" };
    const dailyOccurrences = rowData.occurrencesByDate.get(dateKey) ?? [];
    if (dailyOccurrences.length === 0) return { type: "empty" };
    if (dailyOccurrences.length === 1) {
        return { type: "occurrence", occurrence: dailyOccurrences[0], ordinal: null, total: 1 };
    }
    return {
        type: "aggregate",
        display: deriveAggregateOccurrenceDisplay(
            dailyOccurrences,
            dateKey,
            currentDateKey ?? selectedDateKey,
        ),
    };
}

export function getPlannerRowSelection(
    rowData,
    { selectedPlanItemId = null, selectedOccurrenceId = null, selectedSegmentId = null },
) {
    const groupSelected = rowData.occurrence
        ? rowData.occurrence.id === selectedOccurrenceId
        : rowData.planItem.id === selectedPlanItemId;
    const rowSelected = rowData.rowType === "segment"
        ? groupSelected && rowData.segment.id === selectedSegmentId
        : groupSelected && selectedSegmentId === null;
    return { groupSelected, rowSelected };
}

function createAggregateBadge(planItem, date, display) {
    const marker = document.createElement("span");
    const symbol = document.createElement("span");
    const count = document.createElement("sup");
    const accessibleLabel = `${planItem.name}, ${formatSelectedDate(date)}: ${display.ariaLabel}.`;
    marker.className = "aggregate-occurrence-badge";
    marker.dataset.aggregateType = display.type;
    if (display.status) marker.dataset.status = display.status;
    marker.setAttribute("role", "img");
    marker.setAttribute("aria-label", accessibleLabel);
    marker.title = accessibleLabel;
    symbol.className = "aggregate-occurrence-symbol";
    symbol.textContent = display.symbol;
    symbol.setAttribute("aria-hidden", "true");
    marker.append(symbol);
    if (display.modifier) {
        const modifier = document.createElement("span");
        modifier.className = "aggregate-occurrence-modifier";
        modifier.textContent = display.modifier;
        modifier.setAttribute("aria-hidden", "true");
        marker.append(modifier);
    }
    count.textContent = String(display.count);
    count.setAttribute("aria-hidden", "true");
    marker.append(count);
    return marker;
}

function createPlanItemRow(rowData, position, context) {
    const {
        planItem,
        occurrence,
        selectedOccurrence,
    } = rowData;
    const row = document.createElement("tr");
    const nameCell = document.createElement("th");
    const nameContent = document.createElement("span");
    const nameText = document.createElement("span");
    const { groupSelected } = getPlannerRowSelection(
        rowData,
        context,
    );
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
    row.setAttribute("aria-selected", String(groupSelected));
    if (groupSelected) row.classList.add("is-selected-group");

    if (isMultiSegmentOccurrence(occurrence)) {
        const expanded = context.expandedOccurrenceIds.has(occurrence.id);
        row.classList.add("has-segments");
        if (expanded) row.classList.add("is-expanded");
        const expandButton = document.createElement("button");
        expandButton.type = "button";
        expandButton.className = "occurrence-expand-button";
        expandButton.textContent = expanded ? "▾" : "▸";
        expandButton.setAttribute("aria-expanded", String(expanded));
        expandButton.setAttribute(
            "aria-label",
            `${expanded ? "Contraer" : "Expandir"} segments de ${planItem.name}`,
        );
        expandButton.title = expandButton.getAttribute("aria-label");
        expandButton.addEventListener("click", (event) => {
            event.stopPropagation();
            context.onToggleOccurrence(occurrence.id);
        });
        nameContent.prepend(expandButton);
    }

    if (groupSelected) {
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
        insertButton.disabled = !selectedOccurrence
            || !selectedOccurrencePolicy.canEditSchedule
            || isMultiSegmentOccurrence(occurrence);
        insertButton.setAttribute(
            "aria-label",
            isMultiSegmentOccurrence(occurrence)
                ? `${planItem.name}: agregar junto a una occurrence con varios segments está temporalmente bloqueado`
                : selectedDateFrozen
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
        const scheduleButton = document.createElement("button");
        const deleteButton = document.createElement("button");
        actions.className = "row-actions";
        editButton.type = "button";
        editButton.className = "row-action-button edit-activity-button";
        editButton.textContent = "✎";
        editButton.setAttribute(
            "aria-label",
            selectedDateFrozen
                ? `${planItem.name}: historial congelado, solo lectura`
                : selectedOccurrence
                ? `Editar horario de ${planItem.name} de ${selectedOccurrence.startTime} a ${selectedOccurrence.endTime}, solo esta aparición`
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
                    false,
                );
            }
        });
        scheduleButton.type = "button";
        scheduleButton.className = "row-action-button edit-schedule-button";
        scheduleButton.textContent = "↻";
        scheduleButton.setAttribute(
            "aria-label",
            `Editar planificación recurrente de ${planItem.name} desde ${selectedDateKey}`,
        );
        scheduleButton.title = scheduleButton.getAttribute("aria-label");
        scheduleButton.disabled = selectedDateFrozen;
        scheduleButton.addEventListener("click", (event) => {
            event.stopPropagation();
            if (!scheduleButton.disabled) {
                context.onEdit(planItem, null, scheduleButton, selectedDateKey, true);
            }
        });
        deleteButton.type = "button";
        deleteButton.className = "row-action-button delete-activity-button";
        deleteButton.textContent = "🗑";
        deleteButton.disabled = isMultiSegmentOccurrence(occurrence);
        deleteButton.setAttribute(
            "aria-label",
            isMultiSegmentOccurrence(occurrence)
                ? `${planItem.name}: la eliminación de occurrences con varios segments está temporalmente bloqueada`
                : selectedDateFrozen
                ? `Consultar eliminación de ${planItem.name}: historial congelado`
                : selectedOccurrence
                ? `Gestionar eliminación de ${planItem.name} de ${selectedOccurrence.startTime} a ${selectedOccurrence.endTime}`
                : `Gestionar eliminación de ${planItem.name} desde la fecha seleccionada`,
        );
        deleteButton.title = deleteButton.getAttribute("aria-label");
        deleteButton.addEventListener("click", (event) => {
            event.stopPropagation();
            if (!deleteButton.disabled) {
                context.onDelete(planItem, selectedOccurrence, deleteButton, selectedDateKey);
            }
        });
        actions.append(editButton);
        if (selectedOccurrence && ["weekly", "interval_days"].includes(planItem.generationConfig?.mode)) {
            actions.append(scheduleButton);
        }
        actions.append(deleteButton);
        nameContent.prepend(insertButton);
        nameContent.append(actions);
    }

    row.addEventListener("click", (event) => {
        if (event.target.closest("button, a, input, select")) return;
        context.onRowSelect({
            planItemId: planItem.id,
            occurrenceId: occurrence?.id ?? null,
            segmentId: null,
        }, false);
    });
    row.addEventListener("keydown", (event) => {
        if (event.target !== row || !["Enter", " "].includes(event.key)) return;
        event.preventDefault();
        context.onRowSelect({
            planItemId: planItem.id,
            occurrenceId: occurrence?.id ?? null,
            segmentId: null,
        }, true);
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
            "end-time-column activity-time",
            rowData.endTime ?? "—",
        ),
        createTextCell(
            "td",
            "duration-column activity-duration",
            rowData.duration ?? "—",
        ),
        nameCell,
    );

    const selectedDateKey = formatDateKey(context.selectedDate);
    const currentDateKey = formatDateKey(context.currentDate);
    context.monthDates.forEach((date) => {
        const dateKey = formatDateKey(date);
        const cell = document.createElement("td");
        const cellModel = getPlannerCellModel(rowData, dateKey, selectedDateKey, currentDateKey);
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
        } else if (cellModel.type === "aggregate") {
            cell.classList.add("aggregate-occurrence-cell");
            cell.append(createAggregateBadge(planItem, date, cellModel.display));
        } else {
            const controls = document.createElement("span");
            controls.className = "occurrence-controls";
            controls.append(
                createOccurrenceStatusControl(
                    planItem,
                    cellModel.occurrence,
                    date,
                    context.currentDate,
                    context.onStatusChange,
                    context.statusMutationPending,
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

function createSegmentRow(rowData, context) {
    const { planItem, occurrence, segment, segmentOrdinal } = rowData;
    const row = document.createElement("tr");
    const nameCell = document.createElement("th");
    const { groupSelected: selectedGroup, rowSelected: selectedSegment } = getPlannerRowSelection(
        rowData,
        context,
    );
    row.dataset.planItemId = planItem.id;
    row.dataset.occurrenceId = occurrence.id;
    row.dataset.segmentId = segment.id;
    row.dataset.rowType = "segment";
    row.className = "occurrence-segment-row";
    row.tabIndex = 0;
    row.setAttribute("aria-selected", String(selectedSegment));
    if (selectedGroup) row.classList.add("is-selected-group");
    if (selectedSegment) row.classList.add("is-selected-segment");

    nameCell.className = "name-column activity-name segment-name";
    nameCell.scope = "row";
    nameCell.textContent = `Seg ${segmentOrdinal} · ${planItem.name}`;
    nameCell.title = `${planItem.name}, segment ${segmentOrdinal}`;

    row.addEventListener("click", (event) => {
        if (event.target.closest("button, a, input, select")) return;
        context.onRowSelect({
            planItemId: planItem.id,
            occurrenceId: occurrence.id,
            segmentId: segment.id,
        }, false);
    });
    row.addEventListener("keydown", (event) => {
        if (event.target !== row || !["Enter", " "].includes(event.key)) return;
        event.preventDefault();
        context.onRowSelect({
            planItemId: planItem.id,
            occurrenceId: occurrence.id,
            segmentId: segment.id,
        }, true);
    });

    row.append(
        createTextCell("td", "position-column activity-position", "↳"),
        createTextCell("td", "time-column activity-time", segment.startTime),
        createTextCell("td", "end-time-column activity-time", segment.endTime),
        createTextCell("td", "duration-column activity-duration", rowData.duration),
        nameCell,
    );

    const selectedDateKey = formatDateKey(context.selectedDate);
    context.monthDates.forEach((date) => {
        const dateKey = formatDateKey(date);
        const cell = document.createElement("td");
        cell.className = "day-column";
        cell.dataset.date = dateKey;
        if (isSameLocalDate(date, context.selectedDate)) {
            cell.classList.add("selected-day-column");
            const zone = getDateTemporalZone(occurrence.date, formatDateKey(context.currentDate));
            if (zone === TEMPORAL_ZONES.FROZEN) {
                const definition = statusDefinitions[segment.status];
                cell.append(createReadOnlyStatus(
                    segment.status,
                    `${planItem.name}, Seg ${segmentOrdinal}: ${definition.label}; historial congelado, solo lectura.`,
                    "segment-status-marker",
                ));
            } else {
                const control = createSegmentStatusSelect(
                    planItem,
                    occurrence,
                    segment,
                    date,
                    context.currentDate,
                    context.onStatusChange,
                    context.statusMutationPending,
                );
                control.classList.add("segment-status-control");
                const select = control.querySelector("select");
                select.setAttribute(
                    "aria-label",
                    `${planItem.name}, Seg ${segmentOrdinal}: ${statusDefinitions[segment.status].label}. Seleccionar nuevo estado.`,
                );
                select.title = select.getAttribute("aria-label");
                cell.append(control);
            }
        } else {
            cell.classList.add("duplicate-summary-cell");
            cell.setAttribute("aria-hidden", "true");
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
        render({
            planItems,
            occurrences,
            monthDates,
            currentDate,
            selectedDate,
            selectedPlanItemId,
            selectedOccurrenceId = null,
            selectedSegmentId = null,
            expandedOccurrenceIds = new Set(),
            statusMutationPending = false,
            showAllMonthRecords,
        }) {
            renderHeader(context.matrixHead, monthDates, selectedDate, context.onDateSelect);
            const selectedDateKey = formatDateKey(selectedDate);
            const displayRows = buildPlannerRows(
                planItems,
                occurrences,
                selectedDateKey,
                expandedOccurrenceIds,
            );
            const rows = showAllMonthRecords
                ? displayRows
                : displayRows.filter(({ rowType }) => rowType !== "summary");
            const fragment = document.createDocumentFragment();
            let parentPosition = 0;
            rows.forEach((rowData) => {
                if (rowData.rowType !== "segment") parentPosition += 1;
                const rowContext = {
                    ...context,
                    monthDates,
                    currentDate,
                    selectedDate,
                    selectedPlanItemId,
                    selectedOccurrenceId,
                    selectedSegmentId,
                    expandedOccurrenceIds,
                    statusMutationPending,
                };
                fragment.append(
                    rowData.rowType === "segment"
                        ? createSegmentRow(rowData, rowContext)
                        : createPlanItemRow(rowData, parentPosition, rowContext),
                );
            });
            context.matrixBody.replaceChildren(fragment);
            return rows.length;
        },

        renderLegend() {
            renderLegend(context.statusLegend);
        },

        focusPlannerRow({ planItemId, occurrenceId = null, segmentId = null }) {
            const selector = segmentId
                ? `[data-segment-id="${CSS.escape(segmentId)}"]`
                : occurrenceId
                    ? `[data-occurrence-id="${CSS.escape(occurrenceId)}"]:not([data-segment-id])`
                    : `[data-plan-item-id="${CSS.escape(planItemId)}"]`;
            const row = context.matrixBody.querySelector(selector);
            row?.focus();
            return Boolean(row);
        },

        focusPlanItemRow(planItemId) {
            return this.focusPlannerRow({ planItemId });
        },

        focusSegmentStatusControl(segmentId) {
            const button = context.matrixBody.querySelector(
                `select.segment-status-select[data-segment-id="${CSS.escape(segmentId)}"]`,
            );
            if (!button || button.disabled) return false;
            button.focus();
            return true;
        },
    };
}
