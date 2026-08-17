import { isValidClassification } from "../domain/activity-classification.js";
import { isValidTimeRange, timeToMinutes } from "../utils/date-time.js";

export function validateActivityDraft(values) {
    const draft = {
        name: values.name.trim(),
        recordKind: values.recordKind,
        recordSubtype: values.recordKind === "habit" ? "scheduled" : values.recordSubtype,
        plannedStartTime: values.plannedStartTime,
        plannedEndTime: values.plannedEndTime,
    };
    const errors = [];

    if (!draft.name) errors.push({ field: "name", message: "Escribe el nombre del registro." });
    else if (draft.name.length > 80) {
        errors.push({ field: "name", message: "El nombre debe tener como máximo 80 caracteres." });
    }

    if (!isValidClassification(draft.recordKind, draft.recordSubtype)) {
        errors.push({ field: "recordKind", message: "Selecciona una clasificación válida." });
    }

    if (!draft.plannedStartTime) {
        errors.push({ field: "plannedStartTime", message: "Selecciona una hora de inicio." });
    } else if (timeToMinutes(draft.plannedStartTime) === null) {
        errors.push({ field: "plannedStartTime", message: "La hora de inicio no es válida." });
    }

    if (!draft.plannedEndTime) {
        errors.push({ field: "plannedEndTime", message: "Selecciona una hora de finalización." });
    } else if (timeToMinutes(draft.plannedEndTime) === null) {
        errors.push({ field: "plannedEndTime", message: "La hora de finalización no es válida." });
    } else if (draft.plannedStartTime && !isValidTimeRange(draft.plannedStartTime, draft.plannedEndTime)) {
        errors.push({
            field: "plannedEndTime",
            message: "La hora final debe ser posterior a la hora inicial dentro del mismo día.",
        });
    }

    return { draft, errors };
}

export function createActivityFormView({
    dialog,
    form,
    title,
    referenceMessage,
    errorsRegion,
    nameInput,
    recordKindInput,
    recordSubtypeInput,
    activitySubtypeField,
    habitSubtypeField,
    startTimeInput,
    endTimeInput,
    cancelButton,
    fallbackFocusElement,
    onValidate,
    onSubmit,
    onFallbackFocus,
}) {
    let formContext = { mode: "create", activityId: null, referenceActivityId: null };
    let openerElement = null;

    function updateClassificationFields() {
        const isHabit = recordKindInput.value === "habit";
        activitySubtypeField.hidden = isHabit;
        habitSubtypeField.hidden = !isHabit;
        recordSubtypeInput.disabled = isHabit;
        if (!isHabit && !["anchor", "periodic", "unexpected"].includes(recordSubtypeInput.value)) {
            recordSubtypeInput.value = "periodic";
        }
    }

    function clearErrors() {
        errorsRegion.hidden = true;
        errorsRegion.replaceChildren();
        [nameInput, recordKindInput, recordSubtypeInput, startTimeInput, endTimeInput].forEach(
            (input) => input.removeAttribute("aria-invalid"),
        );
    }

    function resetFormState() {
        form.reset();
        recordKindInput.value = "activity";
        recordSubtypeInput.value = "periodic";
        updateClassificationFields();
        clearErrors();
        formContext = { mode: "create", activityId: null, referenceActivityId: null };
        title.textContent = "Agregar registro";
        referenceMessage.hidden = true;
        referenceMessage.textContent = "";
    }

    function restoreFocus(closedContext) {
        const focusTarget = openerElement?.isConnected ? openerElement : null;
        openerElement = null;
        queueMicrotask(() => {
            if (focusTarget) focusTarget.focus();
            else if (closedContext.activityId || closedContext.referenceActivityId) {
                onFallbackFocus(closedContext.activityId || closedContext.referenceActivityId);
            } else fallbackFocusElement?.focus();
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

    function fillRecord(record) {
        nameInput.value = record.name;
        recordKindInput.value = record.recordKind;
        recordSubtypeInput.value = record.recordSubtype === "scheduled" ? "periodic" : record.recordSubtype;
        startTimeInput.value = record.plannedStartTime;
        endTimeInput.value = record.plannedEndTime;
        updateClassificationFields();
    }

    function openDialog(context, opener) {
        resetFormState();
        formContext = context;
        openerElement = opener;

        if (context.mode === "insert_before") {
            title.textContent = `Agregar antes de: ${context.referenceActivity.name}`;
            referenceMessage.textContent = `La hora define el orden final. Referencia: ${context.referenceActivity.name}.`;
            referenceMessage.hidden = false;
            startTimeInput.value = context.suggestedStartTime || "";
            endTimeInput.value = context.referenceActivity.plannedStartTime;
        } else if (context.mode === "edit") {
            title.textContent = `Editar: ${context.activity.name}`;
            referenceMessage.textContent = "Se conservarán la identidad y los estados registrados.";
            referenceMessage.hidden = false;
            fillRecord(context.activity);
        }

        dialog.showModal();
        nameInput.focus();
    }

    recordKindInput.addEventListener("change", updateClassificationFields);
    form.addEventListener("submit", (event) => {
        event.preventDefault();
        clearErrors();

        const result = validateActivityDraft({
            name: nameInput.value,
            recordKind: recordKindInput.value,
            recordSubtype: recordSubtypeInput.value,
            plannedStartTime: startTimeInput.value,
            plannedEndTime: endTimeInput.value,
        });
        if (result.errors.length) {
            showErrors(result.errors);
            return;
        }

        const validationErrors = onValidate(result.draft, formContext);
        if (validationErrors.length) {
            showErrors(validationErrors);
            return;
        }

        try {
            onSubmit(result.draft, {
                mode: formContext.mode,
                activityId: formContext.activityId,
                referenceActivityId: formContext.referenceActivityId,
            });
            dialog.close("saved");
        } catch (error) {
            const conflict = error.details?.conflictingActivity;
            const message = conflict
                ? `El horario se cruza con “${conflict.name}” (${conflict.plannedStartTime}–${conflict.plannedEndTime}).`
                : "No fue posible guardar el registro.";
            showErrors([{ field: conflict ? "plannedStartTime" : "name", message }]);
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
        openCreate(opener) {
            openDialog({ mode: "create", activityId: null, referenceActivityId: null }, opener);
        },

        openInsertBefore(referenceActivity, suggestedStartTime, opener) {
            openDialog(
                {
                    mode: "insert_before",
                    activityId: null,
                    referenceActivityId: referenceActivity.id,
                    referenceActivity,
                    suggestedStartTime,
                },
                opener,
            );
        },

        openEdit(activity, opener) {
            openDialog(
                { mode: "edit", activityId: activity.id, referenceActivityId: null, activity },
                opener,
            );
        },
    };
}
