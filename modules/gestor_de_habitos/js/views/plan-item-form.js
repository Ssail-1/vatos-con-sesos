import { isValidClassification } from "../domain/plan-item-classification.js";
import {
    cloneGenerationConfig,
    compareGenerationSlots,
    createGenerationSlotId,
} from "../domain/generation-slots.js";
import { validateGenerationConfig } from "../scheduling/materializer.js";
import { getIsoWeekday, isValidDateKey, isValidTimeRange } from "../utils/date-time.js";

const WEEKDAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
const EXPLICIT_DATE_UI_MODE = "explicit_date";

function configsEqual(first, second) {
    const editableConfig = (config) => {
        if (config === null) return null;
        const { excludedDates, stoppedFromDate, ...editableFields } = cloneGenerationConfig(config);
        if (editableFields.mode === "manual_dates") editableFields.entries.sort(compareGenerationSlots);
        else editableFields.slots?.sort(compareGenerationSlots);
        return editableFields;
    };
    return JSON.stringify(editableConfig(first)) === JSON.stringify(editableConfig(second));
}

function normalizeManualDateEntry(entry = {}) {
    return {
        id: entry.id,
        date: entry.date ?? "",
        startTime: entry.startTime ?? "",
        endTime: entry.endTime ?? "",
    };
}

export function createManualDateDraft(entries = []) {
    return entries.map(normalizeManualDateEntry);
}

export function addManualDateDraftEntry(entries, suggestedEntry = {}, createSlotId = createGenerationSlotId) {
    return [
        ...createManualDateDraft(entries),
        normalizeManualDateEntry({ ...suggestedEntry, id: suggestedEntry.id ?? createSlotId() }),
    ];
}

export function updateManualDateDraftEntry(entries, index, changes) {
    return entries.map((entry, entryIndex) => (
        entryIndex === index
            ? normalizeManualDateEntry({ ...entry, ...changes })
            : normalizeManualDateEntry(entry)
    ));
}

export function removeManualDateDraftEntry(entries, index) {
    return createManualDateDraft(entries).filter((_, entryIndex) => entryIndex !== index);
}

export function normalizeWeekdayOverride(defaultStartTime, defaultEndTime, startTime, endTime) {
    return startTime === defaultStartTime && endTime === defaultEndTime
        ? null
        : { startTime, endTime };
}

export function reconstructWeeklySlotDraft(slots) {
    const sortedSlots = slots.map((slot) => ({ ...slot })).sort(compareGenerationSlots);
    const grouped = new Map();
    sortedSlots.forEach((slot) => {
        const weekdaySlots = grouped.get(slot.isoWeekday) ?? [];
        weekdaySlots.push(slot);
        grouped.set(slot.isoWeekday, weekdaySlots);
    });
    const weekdays = [...grouped.entries()].map(([isoWeekday, weekdaySlots]) => ({
        isoWeekday,
        primarySlot: { ...weekdaySlots[0] },
        additionalSlots: weekdaySlots.slice(1).map((slot) => ({ ...slot })),
    }));
    return {
        defaultStartTime: weekdays[0]?.primarySlot.startTime ?? "",
        defaultEndTime: weekdays[0]?.primarySlot.endTime ?? "",
        weekdays,
    };
}

export function validateFormValues(values) {
    const itemType = values.kind === "habit" ? "scheduled" : values.itemType;
    const planItem = {
        name: values.name.trim(),
        kind: values.kind,
        ...(values.kind === "habit" ? { habitType: itemType } : { activityType: itemType }),
    };
    const occurrence = { date: values.date, startTime: values.startTime, endTime: values.endTime };
    const errors = [];
    if (!planItem.name || planItem.name.length > 80) {
        errors.push({ field: "name", message: "Escribe un nombre de 1 a 80 caracteres." });
    }
    if (!isValidClassification(values.kind, itemType)) {
        errors.push({ field: "kind", message: "Selecciona una clasificación válida." });
    }

    let generationConfig;
    if (values.scheduleMode === "weekly") {
        generationConfig = {
            mode: "weekly",
            startDate: values.startDate,
            endDate: values.indefinite ? null : values.endDate,
            indefinite: values.indefinite,
            slots: (values.weeklySlots ?? []).map((slot) => ({ ...slot })).sort(compareGenerationSlots),
        };
        if (!isValidDateKey(values.startDate)) {
            errors.push({ field: "startDate", message: "Selecciona una fecha inicial válida." });
        }
        if (!values.indefinite && (!isValidDateKey(values.endDate) || values.endDate < values.startDate)) {
            errors.push({ field: "endDate", message: "Selecciona una fecha final válida." });
        }
        if (!generationConfig.slots.length) {
            errors.push({ field: "scheduleMode", message: "Selecciona al menos un día de la semana." });
        }
    } else if (values.scheduleMode === "interval_days") {
        generationConfig = {
            mode: "interval_days",
            startDate: values.startDate,
            endDate: values.indefinite ? null : values.endDate,
            indefinite: values.indefinite,
            intervalDays: Number(values.intervalDays),
            slots: (values.intervalSlots ?? []).map((slot) => ({ ...slot })).sort(compareGenerationSlots),
        };
        if (!isValidDateKey(values.startDate) || !Number.isInteger(generationConfig.intervalDays) || generationConfig.intervalDays < 1) {
            errors.push({ field: "intervalDays", message: "Indica una fecha inicial y un intervalo válido." });
        }
    } else if (values.scheduleMode === "manual_dates") {
        const entries = createManualDateDraft(values.manualDateEntries ?? []).sort(compareGenerationSlots);
        generationConfig = { mode: "manual_dates", entries };
        if (!entries.length) {
            errors.push({ field: "addManualDateButton", message: "Agrega al menos una fecha específica." });
        }
        entries.forEach((entry, index) => {
            if (!isValidDateKey(entry.date)) {
                errors.push({ field: `manualDate_${index}`, message: `La fecha ${index + 1} no es válida.` });
            }
            if (!isValidTimeRange(entry.startTime, entry.endTime)) {
                errors.push({ field: `manualEndTime_${index}`, message: `El horario de la fecha ${index + 1} no es válido.` });
            }
        });
    } else if (values.scheduleMode === EXPLICIT_DATE_UI_MODE) {
        generationConfig = {
            mode: "manual_dates",
            entries: [{
                id: values.explicitDateSlotId,
                date: values.date,
                startTime: values.startTime,
                endTime: values.endTime,
            }],
        };
        if (!isValidDateKey(values.date)) {
            errors.push({ field: "date", message: "Selecciona una fecha válida." });
        }
        if (!isValidTimeRange(values.startTime, values.endTime)) {
            errors.push({ field: "endTime", message: "La hora final debe ser posterior a la inicial." });
        }
    } else {
        generationConfig = null;
        errors.push({ field: "scheduleMode", message: "Selecciona una programación válida." });
    }

    if (values.validateOccurrence && values.scheduleMode === "weekly" && !isValidTimeRange(values.startTime, values.endTime)) {
        errors.push({ field: "endTime", message: "El horario del día seleccionado no es válido." });
    }
    if (generationConfig !== null && errors.length === 0) {
        try {
            validateGenerationConfig(generationConfig);
        } catch (error) {
            errors.push({
                field: values.scheduleMode === "manual_dates" ? "addManualDateButton" : "scheduleMode",
                message: error.message,
            });
        }
    }
    return { planItem, occurrence, generationConfig, errors };
}

export function createPlanItemFormView(options) {
    const {
        dialog, form, title, referenceMessage, errorsRegion, nameInput, kindInput, itemTypeInput,
        activityTypeField, habitTypeField, dateInput, occurrenceDateLabel, startTimeInput, endTimeInput,
        scheduleMode, weeklyFields, scheduleStartDate, weekdayChoices, weeklyDefaultStartTime,
        weeklyDefaultEndTime, indefiniteSchedule, scheduleEndDateField, scheduleEndDate, weekdayOverrides,
        weekdayOverrideFields, intervalFields, intervalDays, intervalAdditionalSlots, addIntervalSlotButton,
        manualDatesField, manualDateEntries, addManualDateButton, explicitDateField, occurrenceTimeAnchor, occurrenceTimeFields,
        recurrenceScopeField, cancelButton, fallbackFocusElement, onValidate, onSubmit, onFallbackFocus,
        createSlotId = createGenerationSlotId,
    } = options;
    const submitButton = form.querySelector("button[type='submit']");
    let formContext = { mode: "create" };
    let openerElement = null;
    let activeWeekdays = new Set();
    let editingWeekday = null;
    let overrideDraft = {};
    let weeklyPrimarySlotIds = new Map();
    let weeklyAdditionalSlotDraft = new Map();
    let intervalPrimarySlotId = null;
    let intervalAdditionalSlotDraft = [];
    let manualDateDraft = [];
    let explicitDateSlotId = null;
    let originalGenerationConfig = null;

    weekdayChoices.replaceChildren(...WEEKDAY_NAMES.map((name, index) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "weekday-choice";
        button.dataset.weekday = String(index + 1);
        const label = document.createElement("span");
        label.textContent = index === 2 ? "X" : name[0];
        const editIndicator = document.createElement("span");
        editIndicator.className = "weekday-edit-indicator";
        editIndicator.textContent = "✎";
        editIndicator.setAttribute("aria-hidden", "true");
        button.append(label, editIndicator);
        return button;
    }));

    function createTimeSlotRow(slot, labelText, idPrefix, onChange, onRemove) {
        const row = document.createElement("div");
        row.className = "generation-slot-row";
        row.dataset.slotId = slot.id;
        row.setAttribute("role", "group");
        row.setAttribute("aria-label", labelText);
        const heading = document.createElement("strong");
        heading.className = "generation-slot-label";
        heading.textContent = labelText;
        const makeField = (text, property) => {
            const field = document.createElement("label");
            field.className = "form-field";
            field.textContent = text;
            const input = document.createElement("input");
            input.type = "time";
            input.id = `${idPrefix}_${property}`;
            input.value = slot[property];
            input.required = true;
            input.addEventListener("input", () => onChange({ [property]: input.value }));
            field.append(input);
            return field;
        };
        const removeButton = document.createElement("button");
        removeButton.type = "button";
        removeButton.className = "manual-date-remove-button";
        removeButton.textContent = "Quitar";
        removeButton.setAttribute("aria-label", `Quitar ${labelText.toLowerCase()}`);
        removeButton.addEventListener("click", onRemove);
        row.append(
            heading,
            makeField("Hora de inicio", "startTime"),
            makeField("Hora de finalización", "endTime"),
            removeButton,
        );
        return row;
    }

    function renderManualDateEntries() {
        manualDateEntries.replaceChildren(...manualDateDraft.map((entry, index) => {
            const row = document.createElement("div");
            row.className = "manual-date-entry";
            row.dataset.slotId = entry.id;
            row.setAttribute("role", "group");
            row.setAttribute("aria-label", `Fecha específica ${index + 1}`);
            const createField = (labelText, property, type, name) => {
                const field = document.createElement("div");
                field.className = "form-field";
                const label = document.createElement("label");
                label.htmlFor = name;
                label.textContent = labelText;
                const input = document.createElement("input");
                input.id = name;
                input.name = name;
                input.type = type;
                input.value = entry[property];
                input.required = true;
                input.addEventListener("input", () => {
                    manualDateDraft = updateManualDateDraftEntry(manualDateDraft, index, { [property]: input.value });
                    updateScopeVisibility();
                });
                field.append(label, input);
                return field;
            };
            const removeButton = document.createElement("button");
            removeButton.className = "manual-date-remove-button";
            removeButton.type = "button";
            removeButton.textContent = "Quitar";
            removeButton.setAttribute("aria-label", `Quitar fecha específica ${index + 1}`);
            removeButton.addEventListener("click", () => {
                manualDateDraft = removeManualDateDraftEntry(manualDateDraft, index);
                renderManualDateEntries();
                updateScopeVisibility();
                addManualDateButton.focus();
            });
            row.append(
                createField(`Fecha ${index + 1}`, "date", "date", `manualDate_${index}`),
                createField("Hora de inicio", "startTime", "time", `manualStartTime_${index}`),
                createField("Hora de finalización", "endTime", "time", `manualEndTime_${index}`),
                removeButton,
            );
            return row;
        }));
    }

    function suggestedManualDateEntry() {
        const previous = manualDateDraft.at(-1);
        return {
            date: manualDateDraft.length ? "" : dateInput.value || scheduleStartDate.value,
            startTime: previous?.startTime ?? startTimeInput.value,
            endTime: previous?.endTime ?? endTimeInput.value,
        };
    }

    function addManualDateEntry() {
        manualDateDraft = addManualDateDraftEntry(manualDateDraft, suggestedManualDateEntry(), createSlotId);
        renderManualDateEntries();
        updateScopeVisibility();
        form.elements[`manualDate_${manualDateDraft.length - 1}`]?.focus();
    }

    function allowedModes() {
        if (formContext.mode === "insert_before") return [[EXPLICIT_DATE_UI_MODE, "Una fecha"]];
        if (kindInput.value === "habit" || itemTypeInput.value === "anchor") return [["weekly", "Días de la semana"]];
        if (itemTypeInput.value === "periodic") return [["weekly", "Días de la semana"], ["interval_days", "Cada N días"], ["manual_dates", "Fechas específicas"]];
        if (itemTypeInput.value === "event") return [[EXPLICIT_DATE_UI_MODE, "Una fecha"], ["manual_dates", "Fechas específicas"]];
        return [[EXPLICIT_DATE_UI_MODE, "Una fecha"]];
    }

    function saveEditedWeekday() {
        if (editingWeekday === null) return;
        const startInput = form.elements.weekdayOverrideStartTime;
        const endInput = form.elements.weekdayOverrideEndTime;
        if (!startInput || !endInput) return;
        const override = normalizeWeekdayOverride(
            weeklyDefaultStartTime.value,
            weeklyDefaultEndTime.value,
            startInput.value,
            endInput.value,
        );
        if (override === null) delete overrideDraft[String(editingWeekday)];
        else overrideDraft[String(editingWeekday)] = override;
    }

    function updateWeeklyAdditionalSlot(weekday, slotId, changes) {
        const slots = weeklyAdditionalSlotDraft.get(weekday) ?? [];
        weeklyAdditionalSlotDraft.set(weekday, slots.map((slot) => (
            slot.id === slotId ? { ...slot, ...changes } : slot
        )));
        updateScopeVisibility();
    }

    // The remainder of this view keeps the visual default/override workflow,
    // while every draft below is canonicalized as stable GenerationSlots.
    function renderOverrideEditor() {
        weekdayOverrideFields.replaceChildren();
        if (editingWeekday === null) {
            const message = document.createElement("p");
            message.className = "override-empty-message";
            message.textContent = "Selecciona un día activo para personalizar o agregar horarios.";
            weekdayOverrideFields.append(message);
            return;
        }
        const effective = overrideDraft[String(editingWeekday)] ?? {
            startTime: weeklyDefaultStartTime.value,
            endTime: weeklyDefaultEndTime.value,
        };
        const day = document.createElement("p");
        day.className = "override-weekday-name";
        day.textContent = `Día: ${WEEKDAY_NAMES[editingWeekday - 1]}`;
        const startField = document.createElement("label");
        startField.className = "form-field";
        startField.textContent = "Inicio del horario principal";
        const start = document.createElement("input");
        start.type = "time";
        start.name = "weekdayOverrideStartTime";
        start.value = effective.startTime;
        const endField = document.createElement("label");
        endField.className = "form-field";
        endField.textContent = "Final del horario principal";
        const end = document.createElement("input");
        end.type = "time";
        end.name = "weekdayOverrideEndTime";
        end.value = effective.endTime;
        [start, end].forEach((input) => input.addEventListener("change", () => {
            saveEditedWeekday();
            updateScopeVisibility();
        }));
        startField.append(start);
        endField.append(end);

        const extraContainer = document.createElement("div");
        extraContainer.className = "generation-slot-list";
        const additionalSlots = weeklyAdditionalSlotDraft.get(editingWeekday) ?? [];
        extraContainer.replaceChildren(...additionalSlots.map((slot, index) => createTimeSlotRow(
            slot,
            `Horario adicional ${index + 1}`,
            `weeklySlot_${editingWeekday}_${index}`,
            (changes) => updateWeeklyAdditionalSlot(editingWeekday, slot.id, changes),
            () => {
                weeklyAdditionalSlotDraft.set(
                    editingWeekday,
                    (weeklyAdditionalSlotDraft.get(editingWeekday) ?? []).filter((candidate) => candidate.id !== slot.id),
                );
                renderOverrideEditor();
                updateScopeVisibility();
            },
        )));
        const addButton = document.createElement("button");
        addButton.type = "button";
        addButton.className = "manual-date-add-button";
        addButton.textContent = "+ Agregar horario";
        addButton.addEventListener("click", () => {
            const slots = weeklyAdditionalSlotDraft.get(editingWeekday) ?? [];
            weeklyAdditionalSlotDraft.set(editingWeekday, [
                ...slots,
                { id: createSlotId(), startTime: "", endTime: "" },
            ]);
            renderOverrideEditor();
            updateScopeVisibility();
            weekdayOverrideFields.querySelector(".generation-slot-list > :last-child input")?.focus();
        });
        weekdayOverrideFields.append(day, startField, endField, extraContainer, addButton);
        weekdayOverrides.open = true;
    }

    function renderWeekdays() {
        weekdayChoices.querySelectorAll("button").forEach((button) => {
            const weekday = Number(button.dataset.weekday);
            const state = weekday === editingWeekday ? "editing" : activeWeekdays.has(weekday) ? "active" : "inactive";
            button.dataset.state = state;
            button.setAttribute("aria-pressed", String(state !== "inactive"));
            button.setAttribute("aria-label", `${WEEKDAY_NAMES[weekday - 1]}: ${state === "editing" ? "activo, editando horarios" : state === "active" ? "activo" : "inactivo"}`);
        });
        renderOverrideEditor();
        updateScopeVisibility();
    }

    function currentWeeklySlots() {
        const slots = [];
        [...activeWeekdays].sort((a, b) => a - b).forEach((isoWeekday) => {
            const effective = overrideDraft[String(isoWeekday)] ?? {
                startTime: weeklyDefaultStartTime.value,
                endTime: weeklyDefaultEndTime.value,
            };
            slots.push({
                id: weeklyPrimarySlotIds.get(isoWeekday),
                isoWeekday,
                startTime: effective.startTime,
                endTime: effective.endTime,
            });
            (weeklyAdditionalSlotDraft.get(isoWeekday) ?? []).forEach((slot) => {
                slots.push({ ...slot, isoWeekday });
            });
        });
        return slots.sort(compareGenerationSlots);
    }

    function renderIntervalAdditionalSlots() {
        intervalAdditionalSlots.replaceChildren(...intervalAdditionalSlotDraft.map((slot, index) => createTimeSlotRow(
            slot,
            `Horario adicional ${index + 1}`,
            `intervalSlot_${index}`,
            (changes) => {
                intervalAdditionalSlotDraft = intervalAdditionalSlotDraft.map((candidate) => (
                    candidate.id === slot.id ? { ...candidate, ...changes } : candidate
                ));
                updateScopeVisibility();
            },
            () => {
                intervalAdditionalSlotDraft = intervalAdditionalSlotDraft.filter((candidate) => candidate.id !== slot.id);
                renderIntervalAdditionalSlots();
                updateScopeVisibility();
                addIntervalSlotButton.focus();
            },
        )));
    }

    function currentIntervalSlots() {
        return [
            { id: intervalPrimarySlotId, startTime: startTimeInput.value, endTime: endTimeInput.value },
            ...intervalAdditionalSlotDraft.map((slot) => ({ ...slot })),
        ].sort(compareGenerationSlots);
    }

    function currentGenerationConfigWithoutSaving() {
        if (scheduleMode.value === "weekly") {
            return {
                mode: "weekly",
                startDate: scheduleStartDate.value,
                endDate: indefiniteSchedule.checked ? null : scheduleEndDate.value,
                indefinite: indefiniteSchedule.checked,
                slots: currentWeeklySlots(),
            };
        }
        if (scheduleMode.value === "manual_dates") {
            return { mode: "manual_dates", entries: createManualDateDraft(manualDateDraft).sort(compareGenerationSlots) };
        }
        if (scheduleMode.value === "interval_days") {
            return {
                mode: "interval_days",
                startDate: scheduleStartDate.value,
                endDate: indefiniteSchedule.checked ? null : scheduleEndDate.value,
                indefinite: indefiniteSchedule.checked,
                intervalDays: Number(intervalDays.value),
                slots: currentIntervalSlots(),
            };
        }
        if (scheduleMode.value === EXPLICIT_DATE_UI_MODE) {
            return {
                mode: "manual_dates",
                entries: [{
                    id: explicitDateSlotId,
                    date: dateInput.value,
                    startTime: startTimeInput.value,
                    endTime: endTimeInput.value,
                }],
            };
        }
        return null;
    }

    function updateScopeVisibility() {
        if (!recurrenceScopeField) return;
        const isRecurringEdit = ["edit", "edit_without_occurrence", "edit_schedule"].includes(formContext.mode) && originalGenerationConfig !== null;
        const draftConfig = currentGenerationConfigWithoutSaving();
        recurrenceScopeField.hidden = !isRecurringEdit || configsEqual(draftConfig, originalGenerationConfig);
        const weekScopeInput = form.querySelector('input[name="recurrenceScope"][value="week"]');
        const futureScopeInput = form.querySelector('input[name="recurrenceScope"][value="future"]');
        const supportsWeekScope = originalGenerationConfig?.mode === "weekly" && scheduleMode.value === "weekly";
        weekScopeInput.closest("label").hidden = !supportsWeekScope;
        if (!supportsWeekScope) futureScopeInput.checked = true;
        submitButton.textContent = formContext.mode === "edit_schedule" && recurrenceScopeField.hidden
            ? "Cerrar"
            : formContext.mode === "edit_without_occurrence" && recurrenceScopeField.hidden
                ? "Agregar solo este día"
                : formContext.mode === "create" || formContext.mode === "insert_before"
                    ? "Guardar"
                    : "Aceptar";
    }

    function chooseWeekday(weekday) {
        saveEditedWeekday();
        if (editingWeekday === weekday) {
            activeWeekdays.delete(weekday);
            weeklyPrimarySlotIds.delete(weekday);
            weeklyAdditionalSlotDraft.delete(weekday);
            delete overrideDraft[String(weekday)];
            editingWeekday = null;
        } else {
            activeWeekdays.add(weekday);
            if (!weeklyPrimarySlotIds.has(weekday)) weeklyPrimarySlotIds.set(weekday, createSlotId());
            if (!weeklyAdditionalSlotDraft.has(weekday)) weeklyAdditionalSlotDraft.set(weekday, []);
            editingWeekday = weekday;
        }
        renderWeekdays();
    }

    function updateSchedule(preferred = scheduleMode.value) {
        const available = allowedModes();
        scheduleMode.replaceChildren(...available.map(([value, label]) => {
            const option = document.createElement("option");
            option.value = value;
            option.textContent = label;
            return option;
        }));
        if (available.some(([value]) => value === preferred)) scheduleMode.value = preferred;
        const mode = scheduleMode.value;
        weeklyFields.hidden = mode !== "weekly";
        intervalFields.hidden = mode !== "interval_days";
        manualDatesField.hidden = mode !== "manual_dates";
        if (mode === "manual_dates" && manualDateDraft.length === 0) {
            manualDateDraft = addManualDateDraftEntry(manualDateDraft, suggestedManualDateEntry(), createSlotId);
            renderManualDateEntries();
        }
        if (mode === "interval_days" && intervalPrimarySlotId === null) intervalPrimarySlotId = createSlotId();
        if (mode === EXPLICIT_DATE_UI_MODE && explicitDateSlotId === null) explicitDateSlotId = createSlotId();
        if (mode === "interval_days") intervalFields.insertBefore(occurrenceTimeFields, intervalAdditionalSlots);
        else occurrenceTimeAnchor.after(occurrenceTimeFields);
        const weeklyEdit = ["edit", "edit_without_occurrence"].includes(formContext.mode) && mode === "weekly";
        explicitDateField.hidden = mode !== EXPLICIT_DATE_UI_MODE && !weeklyEdit;
        occurrenceTimeFields.hidden = mode === "manual_dates" || mode === "weekly" && !weeklyEdit;
        renderIntervalAdditionalSlots();
        updateScopeVisibility();
    }

    function updateClassification() {
        const habit = kindInput.value === "habit";
        activityTypeField.hidden = habit;
        habitTypeField.hidden = !habit;
        itemTypeInput.disabled = habit;
        updateSchedule();
    }

    function clearErrors() {
        errorsRegion.hidden = true;
        errorsRegion.replaceChildren();
        [...form.elements].forEach((field) => field.removeAttribute?.("aria-invalid"));
    }

    function showErrors(errors) {
        const list = document.createElement("ul");
        errors.forEach(({ field, message }) => {
            const item = document.createElement("li");
            item.textContent = message;
            list.append(item);
            form.elements[field]?.setAttribute("aria-invalid", "true");
        });
        errorsRegion.replaceChildren(list);
        errorsRegion.hidden = false;
        form.elements[errors[0].field]?.focus();
    }

    function reset() {
        form.reset();
        formContext = { mode: "create" };
        originalGenerationConfig = null;
        activeWeekdays = new Set();
        editingWeekday = null;
        overrideDraft = {};
        weeklyPrimarySlotIds = new Map();
        weeklyAdditionalSlotDraft = new Map();
        intervalPrimarySlotId = null;
        intervalAdditionalSlotDraft = [];
        manualDateDraft = [];
        explicitDateSlotId = null;
        renderManualDateEntries();
        renderIntervalAdditionalSlots();
        kindInput.value = "activity";
        itemTypeInput.value = "periodic";
        indefiniteSchedule.checked = true;
        scheduleEndDateField.hidden = true;
        recurrenceScopeField.hidden = true;
        dateInput.readOnly = false;
        occurrenceDateLabel.textContent = "Fecha";
        submitButton.textContent = "Guardar";
        updateClassification();
        renderWeekdays();
        clearErrors();
        referenceMessage.hidden = true;
    }

    function reconstructWeeklyConfig(config, occurrenceDate, sourceSlotId) {
        const reconstructed = reconstructWeeklySlotDraft(config.slots);
        activeWeekdays = new Set(reconstructed.weekdays.map(({ isoWeekday }) => isoWeekday));
        weeklyPrimarySlotIds = new Map();
        weeklyAdditionalSlotDraft = new Map();
        weeklyDefaultStartTime.value = reconstructed.defaultStartTime;
        weeklyDefaultEndTime.value = reconstructed.defaultEndTime;
        overrideDraft = {};
        reconstructed.weekdays.forEach(({ isoWeekday, primarySlot, additionalSlots }) => {
            weeklyPrimarySlotIds.set(isoWeekday, primarySlot.id);
            weeklyAdditionalSlotDraft.set(
                isoWeekday,
                additionalSlots.map(({ id, startTime, endTime }) => ({ id, startTime, endTime })),
            );
            const override = normalizeWeekdayOverride(
                weeklyDefaultStartTime.value,
                weeklyDefaultEndTime.value,
                primarySlot.startTime,
                primarySlot.endTime,
            );
            if (override) overrideDraft[String(isoWeekday)] = override;
        });
        const sourceSlot = config.slots.find((slot) => slot.id === sourceSlotId);
        const occurrenceWeekday = sourceSlot?.isoWeekday ?? getIsoWeekday(occurrenceDate);
        editingWeekday = activeWeekdays.has(occurrenceWeekday) ? occurrenceWeekday : null;
    }

    function fillGenerationConfig(config, occurrenceDate, sourceSlotId = null) {
        originalGenerationConfig = cloneGenerationConfig(config);
        if (config.mode === "weekly") {
            updateSchedule(config.mode);
            scheduleStartDate.value = config.startDate;
            indefiniteSchedule.checked = config.indefinite;
            scheduleEndDate.value = config.endDate ?? "";
            scheduleEndDateField.hidden = config.indefinite;
            reconstructWeeklyConfig(config, occurrenceDate, sourceSlotId);
            renderWeekdays();
            return;
        }
        if (config.mode === "interval_days") {
            updateSchedule(config.mode);
            scheduleStartDate.value = config.startDate;
            indefiniteSchedule.checked = config.indefinite;
            scheduleEndDate.value = config.endDate ?? "";
            scheduleEndDateField.hidden = config.indefinite;
            intervalDays.value = String(config.intervalDays);
            const sortedSlots = config.slots.map((slot) => ({ ...slot })).sort(compareGenerationSlots);
            const matchingIndex = sortedSlots.findIndex((slot) => slot.id === sourceSlotId);
            const primaryIndex = matchingIndex < 0 ? 0 : matchingIndex;
            const [primary] = sortedSlots.splice(primaryIndex, 1);
            intervalPrimarySlotId = primary.id;
            startTimeInput.value = primary.startTime;
            endTimeInput.value = primary.endTime;
            intervalAdditionalSlotDraft = sortedSlots;
            renderIntervalAdditionalSlots();
            updateScopeVisibility();
            return;
        }
        manualDateDraft = createManualDateDraft(config.entries);
        renderManualDateEntries();
        const usesExplicitDateUi = config.entries.length === 1 && allowedModes().some(
            ([mode]) => mode === EXPLICIT_DATE_UI_MODE,
        );
        if (usesExplicitDateUi) {
            const [entry] = config.entries;
            explicitDateSlotId = entry.id;
            dateInput.value = entry.date;
            startTimeInput.value = entry.startTime;
            endTimeInput.value = entry.endTime;
            originalGenerationConfig = null;
        }
        updateSchedule(usesExplicitDateUi ? EXPLICIT_DATE_UI_MODE : config.mode);
    }

    function getSuggestedOccurrenceTime(config, date, sourceSlotId = null) {
        if (config?.mode === "weekly") {
            const slot = config.slots.find((candidate) => candidate.id === sourceSlotId)
                ?? config.slots.filter((candidate) => candidate.isoWeekday === getIsoWeekday(date)).sort(compareGenerationSlots)[0];
            return slot ? { startTime: slot.startTime, endTime: slot.endTime } : { startTime: "", endTime: "" };
        }
        if (config?.mode === "interval_days") {
            const slot = config.slots.find((candidate) => candidate.id === sourceSlotId)
                ?? [...config.slots].sort(compareGenerationSlots)[0];
            return slot ? { startTime: slot.startTime, endTime: slot.endTime } : { startTime: "", endTime: "" };
        }
        if (config?.mode === "manual_dates") {
            const entry = config.entries.find((candidate) => candidate.id === sourceSlotId)
                ?? config.entries.find((candidate) => candidate.date === date)
                ?? config.entries[0];
            return entry ? { startTime: entry.startTime, endTime: entry.endTime } : { startTime: "", endTime: "" };
        }
        return { startTime: "", endTime: "" };
    }

    function open(context, opener) {
        reset();
        formContext = context;
        openerElement = opener;
        dateInput.value = context.selectedDate;
        scheduleStartDate.value = context.selectedDate;
        title.textContent = ["edit", "edit_without_occurrence", "edit_schedule"].includes(context.mode)
            ? `Editar: ${context.planItem.name}`
            : context.mode === "insert_before"
                ? `Agregar antes de: ${context.referencePlanItem.name}`
                : "Agregar registro";
        if (context.mode === "edit") {
            nameInput.value = context.planItem.name;
            kindInput.value = context.planItem.kind;
            itemTypeInput.value = context.planItem.activityType ?? "periodic";
            updateClassification();
            fillGenerationConfig(
                context.planItem.generationConfig,
                context.occurrence.date,
                context.occurrence.sourceGenerationSlotId,
            );
            dateInput.value = context.occurrence.date;
            startTimeInput.value = context.occurrence.startTime;
            endTimeInput.value = context.occurrence.endTime;
            dateInput.readOnly = true;
            occurrenceDateLabel.textContent = "Fecha del día seleccionado";
            referenceMessage.textContent = context.planItem.generationConfig?.mode === "manual_dates"
                ? "Se muestran todas las fechas específicas. Los cambios de la lista se aplican desde el día seleccionado en adelante."
                : "La fecha está fijada por el día seleccionado. El horario puede cambiarse solo para esta occurrence; los cambios recurrentes requieren alcance.";
            referenceMessage.hidden = false;
        }
        if (context.mode === "edit_without_occurrence") {
            nameInput.value = context.planItem.name;
            kindInput.value = context.planItem.kind;
            itemTypeInput.value = context.planItem.activityType ?? "periodic";
            updateClassification();
            fillGenerationConfig(context.planItem.generationConfig, context.selectedDate);
            const suggestedTime = getSuggestedOccurrenceTime(context.planItem.generationConfig, context.selectedDate);
            dateInput.value = context.selectedDate;
            dateInput.readOnly = true;
            occurrenceDateLabel.textContent = "Fecha del día seleccionado";
            startTimeInput.value = suggestedTime.startTime;
            endTimeInput.value = suggestedTime.endTime;
            referenceMessage.textContent = context.planItem.generationConfig?.mode === "manual_dates"
                ? "Se muestran todas las fechas específicas. Los cambios de la lista se aplican desde el día seleccionado en adelante."
                : "No existe una occurrence en este día. Puedes agregar solo este día o cambiar la recurrencia con un alcance.";
            referenceMessage.hidden = false;
            updateScopeVisibility();
        }
        if (context.mode === "edit_schedule") {
            nameInput.value = context.planItem.name;
            kindInput.value = context.planItem.kind;
            itemTypeInput.value = context.planItem.activityType ?? "periodic";
            updateClassification();
            fillGenerationConfig(context.planItem.generationConfig, context.selectedDate);
            dateInput.value = context.selectedDate;
            dateInput.readOnly = true;
            occurrenceDateLabel.textContent = "Fecha del día seleccionado";
            referenceMessage.textContent = "Este día contiene varios horarios. Puedes revisar el conjunto completo; los cambios con alcance se detienen si requieren semántica multi-slot todavía aplazada.";
            referenceMessage.hidden = false;
            updateScopeVisibility();
        }
        if (context.mode === "insert_before") {
            updateSchedule(EXPLICIT_DATE_UI_MODE);
            startTimeInput.value = context.suggestedStartTime;
            endTimeInput.value = context.referenceOccurrence.startTime;
        }
        dialog.showModal();
        nameInput.focus();
    }

    weekdayChoices.addEventListener("click", (event) => {
        const button = event.target.closest("button[data-weekday]");
        if (button) chooseWeekday(Number(button.dataset.weekday));
    });
    kindInput.addEventListener("change", updateClassification);
    itemTypeInput.addEventListener("change", updateClassification);
    scheduleMode.addEventListener("change", () => updateSchedule());
    addManualDateButton.addEventListener("click", addManualDateEntry);
    addIntervalSlotButton.addEventListener("click", () => {
        intervalAdditionalSlotDraft = [
            ...intervalAdditionalSlotDraft,
            { id: createSlotId(), startTime: "", endTime: "" },
        ];
        renderIntervalAdditionalSlots();
        updateScopeVisibility();
        intervalAdditionalSlots.lastElementChild?.querySelector("input")?.focus();
    });
    indefiniteSchedule.addEventListener("change", () => {
        scheduleEndDateField.hidden = indefiniteSchedule.checked;
        updateScopeVisibility();
    });
    [scheduleStartDate, scheduleEndDate, weeklyDefaultStartTime, weeklyDefaultEndTime, startTimeInput, endTimeInput, intervalDays]
        .forEach((input) => input.addEventListener("change", () => {
            if ([weeklyDefaultStartTime, weeklyDefaultEndTime].includes(input)) renderOverrideEditor();
            updateScopeVisibility();
        }));

    form.addEventListener("submit", (event) => {
        event.preventDefault();
        clearErrors();
        saveEditedWeekday();
        const result = validateFormValues({
            name: nameInput.value,
            kind: kindInput.value,
            itemType: itemTypeInput.value,
            scheduleMode: scheduleMode.value,
            date: dateInput.value,
            startDate: scheduleStartDate.value,
            endDate: scheduleEndDate.value,
            indefinite: indefiniteSchedule.checked,
            weeklySlots: currentWeeklySlots(),
            intervalDays: intervalDays.value,
            intervalSlots: currentIntervalSlots(),
            manualDateEntries: manualDateDraft,
            explicitDateSlotId,
            startTime: startTimeInput.value,
            endTime: endTimeInput.value,
            validateOccurrence: ["edit", "edit_without_occurrence"].includes(formContext.mode),
        });
        if (result.errors.length) return showErrors(result.errors);
        result.recurrenceChanged = ["edit", "edit_without_occurrence", "edit_schedule"].includes(formContext.mode)
            && originalGenerationConfig !== null
            && !configsEqual(result.generationConfig, originalGenerationConfig);
        result.scope = result.recurrenceChanged ? form.elements.recurrenceScope.value : "occurrence";
        const extra = onValidate(result, formContext);
        if (extra.length) return showErrors(extra);
        try {
            const submission = onSubmit(result, formContext);
            if (!submission?.pendingConfirmation) dialog.close("saved");
        } catch (error) {
            const conflict = error.details?.conflictingOccurrence;
            const hasConflicts = Boolean(conflict || error.details?.conflictingOccurrences?.length);
            showErrors([{
                field: hasConflicts
                    ? scheduleMode.value === "manual_dates" ? "manualStartTime_0" : "startTime"
                    : "name",
                message: conflict
                    ? `El horario se cruza con “${conflict.planItemName}” (${conflict.startTime}–${conflict.endTime}).`
                    : error.message,
            }]);
        }
    });
    cancelButton.addEventListener("click", () => dialog.close("cancelled"));
    dialog.addEventListener("close", () => {
        const context = formContext;
        reset();
        queueMicrotask(() => {
            if (openerElement?.isConnected) openerElement.focus();
            else if (context.planItemId) onFallbackFocus(context.planItemId);
            else fallbackFocusElement.focus();
            openerElement = null;
        });
    });

    return {
        completePendingSubmission() {
            if (dialog.open) dialog.close("saved");
        },
        openCreate: (selectedDate, opener) => open({ mode: "create", selectedDate }, opener),
        openInsertBefore: (referencePlanItem, referenceOccurrence, suggestedStartTime, opener) => open({
            mode: "insert_before",
            selectedDate: referenceOccurrence.date,
            referencePlanItem,
            referenceOccurrence,
            suggestedStartTime,
        }, opener),
        openEdit: (planItem, occurrence, selectedDate, opener, scheduleOnly = false) => open({
            mode: scheduleOnly ? "edit_schedule" : occurrence ? "edit" : "edit_without_occurrence",
            selectedDate,
            planItemId: planItem.id,
            occurrenceId: occurrence?.id ?? null,
            planItem,
            occurrence,
        }, opener),
    };
}
