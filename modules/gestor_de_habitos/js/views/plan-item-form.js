import { isValidClassification } from "../domain/plan-item-classification.js";
import { getIsoWeekday, isValidDateKey, isValidTimeRange } from "../utils/date-time.js";

const WEEKDAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];

function cloneConfig(config) {
    if (config?.mode === "weekly") return { ...config, weekdays: [...config.weekdays], weekdayTimeOverrides: Object.fromEntries(Object.entries(config.weekdayTimeOverrides).map(([key, value]) => [key, { ...value }])) };
    if (config?.mode === "manual_dates") return { ...config, entries: config.entries.map((entry) => ({ ...entry })) };
    return config ? { ...config } : null;
}

function configsEqual(first, second) {
    const editableConfig = (config) => {
        if (config === null) return null;
        const { excludedDates, stoppedFromDate, ...editableFields } = config;
        return editableFields;
    };
    return JSON.stringify(editableConfig(first)) === JSON.stringify(editableConfig(second));
}

function normalizeManualDateEntry(entry = {}) {
    return {
        date: entry.date ?? "",
        startTime: entry.startTime ?? "",
        endTime: entry.endTime ?? "",
    };
}

export function createManualDateDraft(entries = []) {
    return entries.map(normalizeManualDateEntry);
}

export function addManualDateDraftEntry(entries, suggestedEntry = {}) {
    return [...createManualDateDraft(entries), normalizeManualDateEntry(suggestedEntry)];
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

export function validateFormValues(values) {
    const itemType = values.kind === "habit" ? "scheduled" : values.itemType;
    const planItem = { name: values.name.trim(), kind: values.kind, ...(values.kind === "habit" ? { habitType: itemType } : { activityType: itemType }) };
    const occurrence = { date: values.date, startTime: values.startTime, endTime: values.endTime };
    const errors = [];
    if (!planItem.name || planItem.name.length > 80) errors.push({ field: "name", message: "Escribe un nombre de 1 a 80 caracteres." });
    if (!isValidClassification(values.kind, itemType)) errors.push({ field: "kind", message: "Selecciona una clasificación válida." });
    let generationConfig;
    if (values.scheduleMode === "weekly") {
        generationConfig = {
            mode: "weekly", startDate: values.startDate, endDate: values.indefinite ? null : values.endDate,
            indefinite: values.indefinite, weekdays: [...values.weekdays].sort((a, b) => a - b),
            defaultStartTime: values.defaultStartTime, defaultEndTime: values.defaultEndTime,
            weekdayTimeOverrides: values.weekdayTimeOverrides,
        };
        if (!isValidDateKey(values.startDate)) errors.push({ field: "startDate", message: "Selecciona una fecha inicial válida." });
        if (!values.indefinite && (!isValidDateKey(values.endDate) || values.endDate < values.startDate)) errors.push({ field: "endDate", message: "Selecciona una fecha final válida." });
        if (!values.weekdays.length) errors.push({ field: "scheduleMode", message: "Selecciona al menos un día de la semana." });
        if (!isValidTimeRange(values.defaultStartTime, values.defaultEndTime)) errors.push({ field: "weeklyDefaultEndTime", message: "El horario general no es válido." });
        if (Object.values(values.weekdayTimeOverrides).some(({ startTime, endTime }) => !isValidTimeRange(startTime, endTime))) errors.push({ field: "weekdayOverrideEndTime", message: "El horario diferente del día no es válido." });
    } else if (values.scheduleMode === "interval_days") {
        generationConfig = { mode: "interval_days", startDate: values.startDate, endDate: values.indefinite ? null : values.endDate, indefinite: values.indefinite, intervalDays: Number(values.intervalDays), defaultStartTime: values.startTime, defaultEndTime: values.endTime };
        if (!isValidDateKey(values.startDate) || !Number.isInteger(generationConfig.intervalDays) || generationConfig.intervalDays < 1) errors.push({ field: "intervalDays", message: "Indica una fecha inicial y un intervalo válido." });
        if (!isValidTimeRange(values.startTime, values.endTime)) errors.push({ field: "endTime", message: "La hora final debe ser posterior a la inicial." });
    } else if (values.scheduleMode === "manual_dates") {
        const entries = createManualDateDraft(values.manualDateEntries ?? []);
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
    } else {
        generationConfig = { mode: "single_date", date: values.date, startTime: values.startTime, endTime: values.endTime };
        if (!isValidDateKey(values.date)) errors.push({ field: "date", message: "Selecciona una fecha válida." });
        if (!isValidTimeRange(values.startTime, values.endTime)) errors.push({ field: "endTime", message: "La hora final debe ser posterior a la inicial." });
    }
    if (values.validateOccurrence && values.scheduleMode === "weekly" && !isValidTimeRange(values.startTime, values.endTime)) {
        errors.push({ field: "endTime", message: "El horario del día seleccionado no es válido." });
    }
    return { planItem, occurrence, generationConfig, errors };
}

export function createPlanItemFormView(options) {
    const { dialog, form, title, referenceMessage, errorsRegion, nameInput, kindInput, itemTypeInput,
        activityTypeField, habitTypeField, dateInput, occurrenceDateLabel, startTimeInput, endTimeInput, scheduleMode,
        weeklyFields, scheduleStartDate, weekdayChoices, weeklyDefaultStartTime, weeklyDefaultEndTime,
        indefiniteSchedule, scheduleEndDateField, scheduleEndDate, weekdayOverrides, weekdayOverrideFields,
        intervalFields, intervalDays, manualDatesField, manualDateEntries, addManualDateButton, singleDateField, occurrenceTimeFields,
        recurrenceScopeField, cancelButton, fallbackFocusElement, onValidate, onSubmit, onFallbackFocus } = options;
    const submitButton = form.querySelector("button[type='submit']");
    let formContext = { mode: "create" };
    let openerElement = null;
    let activeWeekdays = new Set();
    let editingWeekday = null;
    let overrideDraft = {};
    let manualDateDraft = [];
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

    function renderManualDateEntries() {
        manualDateEntries.replaceChildren(...manualDateDraft.map((entry, index) => {
            const row = document.createElement("div");
            row.className = "manual-date-entry";
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
        manualDateDraft = addManualDateDraftEntry(manualDateDraft, suggestedManualDateEntry());
        renderManualDateEntries();
        updateScopeVisibility();
        form.elements[`manualDate_${manualDateDraft.length - 1}`]?.focus();
    }

    function allowedModes() {
        if (kindInput.value === "habit" || itemTypeInput.value === "anchor") return [["weekly", "Días de la semana"]];
        if (itemTypeInput.value === "periodic") return [["weekly", "Días de la semana"], ["interval_days", "Cada N días"], ["manual_dates", "Fechas específicas"]];
        if (itemTypeInput.value === "event") return [["single_date", "Una fecha"], ["manual_dates", "Fechas específicas"]];
        return [["single_date", "Una fecha"]];
    }

    function saveEditedWeekday() {
        if (editingWeekday === null) return;
        const startInput = form.elements.weekdayOverrideStartTime;
        const endInput = form.elements.weekdayOverrideEndTime;
        if (!startInput || !endInput) return;
        const startTime = startInput.value;
        const endTime = endInput.value;
        const override = normalizeWeekdayOverride(
            weeklyDefaultStartTime.value,
            weeklyDefaultEndTime.value,
            startTime,
            endTime,
        );
        if (override === null) delete overrideDraft[String(editingWeekday)];
        else overrideDraft[String(editingWeekday)] = override;
    }

    function renderOverrideEditor() {
        weekdayOverrideFields.replaceChildren();
        if (editingWeekday === null) {
            const message = document.createElement("p");
            message.className = "override-empty-message";
            message.textContent = "Selecciona un día activo para personalizar su horario.";
            weekdayOverrideFields.append(message);
            return;
        }
        const effective = overrideDraft[String(editingWeekday)] ?? { startTime: weeklyDefaultStartTime.value, endTime: weeklyDefaultEndTime.value };
        const day = document.createElement("p");
        day.className = "override-weekday-name";
        day.textContent = `Día: ${WEEKDAY_NAMES[editingWeekday - 1]}`;
        const startField = document.createElement("label");
        startField.className = "form-field";
        startField.textContent = "Hora de inicio";
        const start = document.createElement("input");
        start.type = "time"; start.name = "weekdayOverrideStartTime"; start.value = effective.startTime;
        const endField = document.createElement("label");
        endField.className = "form-field";
        endField.textContent = "Hora de finalización";
        const end = document.createElement("input");
        end.type = "time"; end.name = "weekdayOverrideEndTime"; end.value = effective.endTime;
        [start, end].forEach((input) => input.addEventListener("change", () => { saveEditedWeekday(); updateScopeVisibility(); }));
        startField.append(start); endField.append(end);
        weekdayOverrideFields.append(day, startField, endField);
        weekdayOverrides.open = true;
    }

    function renderWeekdays() {
        weekdayChoices.querySelectorAll("button").forEach((button) => {
            const weekday = Number(button.dataset.weekday);
            const state = weekday === editingWeekday ? "editing" : activeWeekdays.has(weekday) ? "active" : "inactive";
            button.dataset.state = state;
            button.setAttribute("aria-pressed", String(state !== "inactive"));
            button.setAttribute("aria-label", `${WEEKDAY_NAMES[weekday - 1]}: ${state === "editing" ? "activo, editando horario" : state === "active" ? "activo" : "inactivo"}`);
        });
        renderOverrideEditor();
        updateScopeVisibility();
    }

    function currentConfig() {
        saveEditedWeekday();
        return {
            mode: "weekly", startDate: scheduleStartDate.value, endDate: indefiniteSchedule.checked ? null : scheduleEndDate.value,
            indefinite: indefiniteSchedule.checked, weekdays: [...activeWeekdays].sort((a, b) => a - b),
            defaultStartTime: weeklyDefaultStartTime.value, defaultEndTime: weeklyDefaultEndTime.value,
            weekdayTimeOverrides: Object.fromEntries(Object.entries(overrideDraft).filter(([weekday]) => activeWeekdays.has(Number(weekday)))),
        };
    }

    function updateScopeVisibility() {
        if (!recurrenceScopeField) return;
        const isRecurringEdit = ["edit", "edit_without_occurrence"].includes(formContext.mode) && originalGenerationConfig !== null;
        const draftConfig = currentGenerationConfigWithoutSaving();
        recurrenceScopeField.hidden = !isRecurringEdit || configsEqual(draftConfig, originalGenerationConfig);
        const weekScopeInput = form.querySelector('input[name="recurrenceScope"][value="week"]');
        const futureScopeInput = form.querySelector('input[name="recurrenceScope"][value="future"]');
        const supportsWeekScope = originalGenerationConfig?.mode === "weekly" && scheduleMode.value === "weekly";
        weekScopeInput.closest("label").hidden = !supportsWeekScope;
        if (!supportsWeekScope) futureScopeInput.checked = true;
        submitButton.textContent = formContext.mode === "edit_without_occurrence" && recurrenceScopeField.hidden
            ? "Agregar solo este día"
            : formContext.mode === "create" || formContext.mode === "insert_before"
                ? "Guardar"
                : "Aceptar";
    }

    function currentGenerationConfigWithoutSaving() {
        if (scheduleMode.value === "weekly") return currentConfigWithoutSaving();
        if (scheduleMode.value === "manual_dates") {
            return { mode: "manual_dates", entries: createManualDateDraft(manualDateDraft) };
        }
        if (scheduleMode.value === "interval_days") {
            return {
                mode: "interval_days",
                startDate: scheduleStartDate.value,
                endDate: indefiniteSchedule.checked ? null : scheduleEndDate.value,
                indefinite: indefiniteSchedule.checked,
                intervalDays: Number(intervalDays.value),
                defaultStartTime: startTimeInput.value,
                defaultEndTime: endTimeInput.value,
            };
        }
        return {
            mode: "single_date",
            date: dateInput.value,
            startTime: startTimeInput.value,
            endTime: endTimeInput.value,
        };
    }

    function currentConfigWithoutSaving() {
        return {
            mode: "weekly", startDate: scheduleStartDate.value, endDate: indefiniteSchedule.checked ? null : scheduleEndDate.value,
            indefinite: indefiniteSchedule.checked, weekdays: [...activeWeekdays].sort((a, b) => a - b),
            defaultStartTime: weeklyDefaultStartTime.value, defaultEndTime: weeklyDefaultEndTime.value,
            weekdayTimeOverrides: Object.fromEntries(Object.entries(overrideDraft).filter(([weekday]) => activeWeekdays.has(Number(weekday)))),
        };
    }

    function chooseWeekday(weekday) {
        saveEditedWeekday();
        if (editingWeekday === weekday) {
            activeWeekdays.delete(weekday);
            delete overrideDraft[String(weekday)];
            editingWeekday = null;
        } else {
            activeWeekdays.add(weekday);
            editingWeekday = weekday;
        }
        renderWeekdays();
    }

    function updateSchedule(preferred = scheduleMode.value) {
        const available = allowedModes();
        scheduleMode.replaceChildren(...available.map(([value, label]) => { const option = document.createElement("option"); option.value = value; option.textContent = label; return option; }));
        if (available.some(([value]) => value === preferred)) scheduleMode.value = preferred;
        const mode = scheduleMode.value;
        weeklyFields.hidden = mode !== "weekly";
        intervalFields.hidden = mode !== "interval_days";
        manualDatesField.hidden = mode !== "manual_dates";
        if (mode === "manual_dates" && manualDateDraft.length === 0) {
            manualDateDraft = addManualDateDraftEntry(manualDateDraft, suggestedManualDateEntry());
            renderManualDateEntries();
        }
        const weeklyEdit = ["edit", "edit_without_occurrence"].includes(formContext.mode) && mode === "weekly";
        singleDateField.hidden = mode !== "single_date" && !weeklyEdit;
        occurrenceTimeFields.hidden = mode === "manual_dates" || mode === "weekly" && !weeklyEdit;
        updateScopeVisibility();
    }

    function updateClassification() {
        const habit = kindInput.value === "habit";
        activityTypeField.hidden = habit; habitTypeField.hidden = !habit; itemTypeInput.disabled = habit;
        updateSchedule();
    }

    function clearErrors() { errorsRegion.hidden = true; errorsRegion.replaceChildren(); [...form.elements].forEach((field) => field.removeAttribute?.("aria-invalid")); }
    function showErrors(errors) { const list = document.createElement("ul"); errors.forEach(({ field, message }) => { const item = document.createElement("li"); item.textContent = message; list.append(item); form.elements[field]?.setAttribute("aria-invalid", "true"); }); errorsRegion.replaceChildren(list); errorsRegion.hidden = false; form.elements[errors[0].field]?.focus(); }

    function reset() {
        form.reset(); formContext = { mode: "create" }; originalGenerationConfig = null; activeWeekdays = new Set(); editingWeekday = null; overrideDraft = {}; manualDateDraft = [];
        renderManualDateEntries();
        kindInput.value = "activity"; itemTypeInput.value = "periodic"; indefiniteSchedule.checked = true; scheduleEndDateField.hidden = true;
        recurrenceScopeField.hidden = true; dateInput.readOnly = false; occurrenceDateLabel.textContent = "Fecha";
        submitButton.textContent = "Guardar"; updateClassification(); renderWeekdays(); clearErrors(); referenceMessage.hidden = true;
    }

    function fillGenerationConfig(config, occurrenceDate) {
        if (config.mode === "weekly") {
            originalGenerationConfig = cloneConfig(config);
            updateSchedule(config.mode);
            scheduleStartDate.value = config.startDate;
            indefiniteSchedule.checked = config.indefinite;
            scheduleEndDate.value = config.endDate ?? "";
            scheduleEndDateField.hidden = config.indefinite;
            weeklyDefaultStartTime.value = config.defaultStartTime;
            weeklyDefaultEndTime.value = config.defaultEndTime;
            activeWeekdays = new Set(config.weekdays);
            overrideDraft = cloneConfig(config).weekdayTimeOverrides;
            const occurrenceWeekday = getIsoWeekday(occurrenceDate);
            editingWeekday = activeWeekdays.has(occurrenceWeekday) ? occurrenceWeekday : null;
            renderWeekdays();
        } else if (config.mode === "manual_dates") {
            originalGenerationConfig = cloneConfig(config);
            manualDateDraft = createManualDateDraft(config.entries);
            renderManualDateEntries();
            updateSchedule(config.mode);
        } else {
            originalGenerationConfig = null;
            updateSchedule("single_date");
        }
    }

    function getSuggestedOccurrenceTime(config, date) {
        if (config?.mode === "weekly") {
            return config.weekdayTimeOverrides[String(getIsoWeekday(date))] ?? {
                startTime: config.defaultStartTime,
                endTime: config.defaultEndTime,
            };
        }
        if (config?.mode === "interval_days") return { startTime: config.defaultStartTime, endTime: config.defaultEndTime };
        if (config?.mode === "single_date") return { startTime: config.startTime, endTime: config.endTime };
        if (config?.mode === "manual_dates") {
            const entry = config.entries.find((candidate) => candidate.date === date) ?? config.entries[0];
            return entry ? { startTime: entry.startTime, endTime: entry.endTime } : { startTime: "", endTime: "" };
        }
        return { startTime: "", endTime: "" };
    }

    function open(context, opener) {
        reset(); formContext = context; openerElement = opener; dateInput.value = context.selectedDate; scheduleStartDate.value = context.selectedDate;
        title.textContent = ["edit", "edit_without_occurrence"].includes(context.mode) ? `Editar: ${context.planItem.name}` : context.mode === "insert_before" ? `Agregar antes de: ${context.referencePlanItem.name}` : "Agregar registro";
        if (context.mode === "edit") {
            nameInput.value = context.planItem.name; kindInput.value = context.planItem.kind; itemTypeInput.value = context.planItem.activityType ?? "periodic";
            updateClassification(); fillGenerationConfig(context.planItem.generationConfig, context.occurrence.date);
            dateInput.value = context.occurrence.date; startTimeInput.value = context.occurrence.startTime; endTimeInput.value = context.occurrence.endTime;
            dateInput.readOnly = true; occurrenceDateLabel.textContent = "Fecha del día seleccionado";
            referenceMessage.textContent = context.planItem.generationConfig?.mode === "manual_dates"
                ? "Se muestran todas las fechas específicas. Los cambios de la lista se aplican desde el día seleccionado en adelante."
                : "La fecha está fijada por el día seleccionado. El horario puede cambiarse solo para esta occurrence; los cambios recurrentes requieren alcance.";
            referenceMessage.hidden = false;
        }
        if (context.mode === "edit_without_occurrence") {
            nameInput.value = context.planItem.name; kindInput.value = context.planItem.kind; itemTypeInput.value = context.planItem.activityType ?? "periodic";
            updateClassification(); fillGenerationConfig(context.planItem.generationConfig, context.selectedDate);
            const suggestedTime = getSuggestedOccurrenceTime(context.planItem.generationConfig, context.selectedDate);
            dateInput.value = context.selectedDate; dateInput.readOnly = true; occurrenceDateLabel.textContent = "Fecha del día seleccionado";
            startTimeInput.value = suggestedTime.startTime; endTimeInput.value = suggestedTime.endTime;
            referenceMessage.textContent = context.planItem.generationConfig?.mode === "manual_dates"
                ? "Se muestran todas las fechas específicas. Los cambios de la lista se aplican desde el día seleccionado en adelante."
                : "No existe una occurrence en este día. Puedes agregar solo este día o cambiar la recurrencia con un alcance.";
            referenceMessage.hidden = false;
            updateScopeVisibility();
        }
        if (context.mode === "insert_before") { updateSchedule("single_date"); startTimeInput.value = context.suggestedStartTime; endTimeInput.value = context.referenceOccurrence.startTime; }
        dialog.showModal(); nameInput.focus();
    }

    weekdayChoices.addEventListener("click", (event) => { const button = event.target.closest("button[data-weekday]"); if (button) chooseWeekday(Number(button.dataset.weekday)); });
    kindInput.addEventListener("change", updateClassification); itemTypeInput.addEventListener("change", updateClassification); scheduleMode.addEventListener("change", () => updateSchedule());
    addManualDateButton.addEventListener("click", addManualDateEntry);
    indefiniteSchedule.addEventListener("change", () => { scheduleEndDateField.hidden = indefiniteSchedule.checked; updateScopeVisibility(); });
    [scheduleStartDate, scheduleEndDate, weeklyDefaultStartTime, weeklyDefaultEndTime].forEach((input) => input.addEventListener("change", () => { if ([weeklyDefaultStartTime, weeklyDefaultEndTime].includes(input)) renderOverrideEditor(); updateScopeVisibility(); }));

    form.addEventListener("submit", (event) => {
        event.preventDefault(); clearErrors(); saveEditedWeekday();
        const weeklyConfig = scheduleMode.value === "weekly" ? currentConfigWithoutSaving() : null;
        const result = validateFormValues({ name: nameInput.value, kind: kindInput.value, itemType: itemTypeInput.value,
            scheduleMode: scheduleMode.value, date: dateInput.value, startDate: scheduleStartDate.value,
            endDate: scheduleEndDate.value, indefinite: indefiniteSchedule.checked, weekdays: [...activeWeekdays],
            defaultStartTime: weeklyDefaultStartTime.value, defaultEndTime: weeklyDefaultEndTime.value,
            weekdayTimeOverrides: weeklyConfig?.weekdayTimeOverrides ?? {}, intervalDays: intervalDays.value,
            manualDateEntries: manualDateDraft, startTime: startTimeInput.value, endTime: endTimeInput.value,
            validateOccurrence: ["edit", "edit_without_occurrence"].includes(formContext.mode) });
        if (result.errors.length) return showErrors(result.errors);
        result.recurrenceChanged = ["edit", "edit_without_occurrence"].includes(formContext.mode) && originalGenerationConfig !== null && !configsEqual(result.generationConfig, originalGenerationConfig);
        result.scope = result.recurrenceChanged ? form.elements.recurrenceScope.value : "occurrence";
        const extra = onValidate(result, formContext); if (extra.length) return showErrors(extra);
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
    dialog.addEventListener("close", () => { const context = formContext; reset(); queueMicrotask(() => { if (openerElement?.isConnected) openerElement.focus(); else if (context.planItemId) onFallbackFocus(context.planItemId); else fallbackFocusElement.focus(); openerElement = null; }); });

    return {
        completePendingSubmission() {
            if (dialog.open) dialog.close("saved");
        },
        openCreate: (selectedDate, opener) => open({ mode: "create", selectedDate }, opener),
        openInsertBefore: (referencePlanItem, referenceOccurrence, suggestedStartTime, opener) => open({ mode: "insert_before", selectedDate: referenceOccurrence.date, referencePlanItem, referenceOccurrence, suggestedStartTime }, opener),
        openEdit: (planItem, occurrence, selectedDate, opener) => open({
            mode: occurrence ? "edit" : "edit_without_occurrence",
            selectedDate,
            planItemId: planItem.id,
            occurrenceId: occurrence?.id ?? null,
            planItem,
            occurrence,
        }, opener),
    };
}
