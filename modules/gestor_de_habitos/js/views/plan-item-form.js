import { isValidClassification } from "../domain/plan-item-classification.js";
import { isValidDateKey, isValidTimeRange, timeToMinutes } from "../utils/date-time.js";

export function validateFormValues(values) {
    const itemType = values.kind === "habit" ? "scheduled" : values.itemType;
    const result = {
        planItem: {
            name: values.name.trim(),
            kind: values.kind,
            ...(values.kind === "habit" ? { habitType: itemType } : { activityType: itemType }),
        },
        occurrence: {
            date: values.date,
            startTime: values.startTime,
            endTime: values.endTime,
        },
        errors: [],
    };

    if (!result.planItem.name) {
        result.errors.push({ field: "name", message: "Escribe el nombre del registro." });
    } else if (result.planItem.name.length > 80) {
        result.errors.push({ field: "name", message: "El nombre debe tener como máximo 80 caracteres." });
    }
    if (!isValidClassification(values.kind, itemType)) {
        result.errors.push({ field: "kind", message: "Selecciona una clasificación válida." });
    }
    if (!isValidDateKey(values.date)) {
        result.errors.push({ field: "date", message: "Selecciona una fecha válida." });
    }
    if (!values.startTime || timeToMinutes(values.startTime) === null) {
        result.errors.push({ field: "startTime", message: "Selecciona una hora de inicio válida." });
    }
    if (!values.endTime || timeToMinutes(values.endTime) === null) {
        result.errors.push({ field: "endTime", message: "Selecciona una hora de finalización válida." });
    } else if (values.startTime && !isValidTimeRange(values.startTime, values.endTime)) {
        result.errors.push({
            field: "endTime",
            message: "La hora final debe ser posterior a la inicial dentro del mismo día.",
        });
    }
    return result;
}

export function createPlanItemFormView({
    dialog,
    form,
    title,
    referenceMessage,
    errorsRegion,
    nameInput,
    kindInput,
    itemTypeInput,
    activityTypeField,
    habitTypeField,
    dateInput,
    startTimeInput,
    endTimeInput,
    cancelButton,
    fallbackFocusElement,
    onValidate,
    onSubmit,
    onFallbackFocus,
}) {
    let formContext = { mode: "create", planItemId: null, occurrenceId: null };
    let openerElement = null;

    function updateClassificationFields() {
        const isHabit = kindInput.value === "habit";
        activityTypeField.hidden = isHabit;
        habitTypeField.hidden = !isHabit;
        itemTypeInput.disabled = isHabit;
        if (!isHabit && !["anchor", "periodic", "event", "unexpected"].includes(itemTypeInput.value)) {
            itemTypeInput.value = "periodic";
        }
    }

    function clearErrors() {
        errorsRegion.hidden = true;
        errorsRegion.replaceChildren();
        [nameInput, kindInput, itemTypeInput, dateInput, startTimeInput, endTimeInput].forEach(
            (input) => input.removeAttribute("aria-invalid"),
        );
    }

    function resetFormState() {
        form.reset();
        kindInput.value = "activity";
        itemTypeInput.value = "periodic";
        updateClassificationFields();
        clearErrors();
        formContext = { mode: "create", planItemId: null, occurrenceId: null };
        title.textContent = "Agregar registro";
        referenceMessage.hidden = true;
        referenceMessage.textContent = "";
    }

    function restoreFocus(closedContext) {
        const focusTarget = openerElement?.isConnected ? openerElement : null;
        openerElement = null;
        queueMicrotask(() => {
            if (focusTarget) focusTarget.focus();
            else if (closedContext.planItemId) onFallbackFocus(closedContext.planItemId);
            else fallbackFocusElement?.focus();
        });
    }

    function showErrors(errors) {
        const list = document.createElement("ul");
        errors.forEach((error) => {
            const item = document.createElement("li");
            item.textContent = error.message;
            list.append(item);
            form.elements[error.field]?.setAttribute("aria-invalid", "true");
        });
        errorsRegion.replaceChildren(list);
        errorsRegion.hidden = false;
        form.elements[errors[0].field]?.focus();
    }

    function fillPlanItem(planItem) {
        nameInput.value = planItem.name;
        kindInput.value = planItem.kind;
        itemTypeInput.value = planItem.kind === "activity" ? planItem.activityType : "periodic";
        updateClassificationFields();
    }

    function openDialog(context, opener) {
        resetFormState();
        formContext = context;
        openerElement = opener;
        dateInput.value = context.selectedDate;

        if (context.mode === "insert_before") {
            title.textContent = `Agregar antes de: ${context.referencePlanItem.name}`;
            referenceMessage.textContent = `La fecha y la hora determinan la posición. Referencia: ${context.referencePlanItem.name}.`;
            referenceMessage.hidden = false;
            startTimeInput.value = context.suggestedStartTime || "";
            endTimeInput.value = context.referenceOccurrence.startTime;
        } else if (context.mode === "edit") {
            title.textContent = `Editar: ${context.planItem.name}`;
            referenceMessage.textContent = "Se conservarán el ID de la occurrence, su PlanItem y su estado.";
            referenceMessage.hidden = false;
            fillPlanItem(context.planItem);
            dateInput.value = context.occurrence.date;
            startTimeInput.value = context.occurrence.startTime;
            endTimeInput.value = context.occurrence.endTime;
        }

        dialog.showModal();
        nameInput.focus();
    }

    kindInput.addEventListener("change", updateClassificationFields);
    form.addEventListener("submit", (event) => {
        event.preventDefault();
        clearErrors();
        const result = validateFormValues({
            name: nameInput.value,
            kind: kindInput.value,
            itemType: itemTypeInput.value,
            date: dateInput.value,
            startTime: startTimeInput.value,
            endTime: endTimeInput.value,
        });
        if (result.errors.length) return showErrors(result.errors);
        const validationErrors = onValidate(result, formContext);
        if (validationErrors.length) return showErrors(validationErrors);

        try {
            onSubmit(result, formContext);
            dialog.close("saved");
        } catch (error) {
            const conflict = error.details?.conflictingOccurrence;
            const message = conflict
                ? `El horario se cruza con “${conflict.planItemName}” (${conflict.startTime}–${conflict.endTime}).`
                : error.message || "No fue posible guardar el registro.";
            showErrors([{ field: conflict ? "startTime" : "name", message }]);
            if (!conflict) console.error(error);
        }
    });

    cancelButton.addEventListener("click", () => dialog.close("cancelled"));
    dialog.addEventListener("close", () => {
        const closedContext = formContext;
        resetFormState();
        restoreFocus(closedContext);
    });

    return {
        openCreate(selectedDate, opener) {
            openDialog({ mode: "create", planItemId: null, occurrenceId: null, selectedDate }, opener);
        },

        openInsertBefore(referencePlanItem, referenceOccurrence, suggestedStartTime, opener) {
            openDialog(
                {
                    mode: "insert_before",
                    planItemId: null,
                    occurrenceId: null,
                    selectedDate: referenceOccurrence.date,
                    referencePlanItem,
                    referenceOccurrence,
                    suggestedStartTime,
                },
                opener,
            );
        },

        openEdit(planItem, occurrence, opener) {
            openDialog(
                {
                    mode: "edit",
                    planItemId: planItem.id,
                    occurrenceId: occurrence.id,
                    selectedDate: occurrence.date,
                    planItem,
                    occurrence,
                },
                opener,
            );
        },
    };
}
