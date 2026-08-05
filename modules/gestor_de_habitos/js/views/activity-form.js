import { isValidTimeRange, timeToMinutes } from "../utils/date-time.js";

export function validateActivityDraft(values) {
    const draft = {
        name: values.name.trim(),
        plannedStartTime: values.plannedStartTime,
        plannedEndTime: values.plannedEndTime,
    };
    const errors = [];

    if (!draft.name) errors.push({ field: "name", message: "Escribe el nombre de la actividad." });
    else if (draft.name.length > 80) {
        errors.push({ field: "name", message: "El nombre debe tener como máximo 80 caracteres." });
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
    startTimeInput,
    endTimeInput,
    cancelButton,
    fallbackFocusElement,
    onSubmit,
}) {
    let formContext = { mode: "append", referenceActivityId: null };
    let openerElement = null;

    function clearErrors() {
        errorsRegion.hidden = true;
        errorsRegion.replaceChildren();
        [nameInput, startTimeInput, endTimeInput].forEach((input) => {
            input.removeAttribute("aria-invalid");
        });
    }

    function resetFormState() {
        form.reset();
        clearErrors();
        formContext = { mode: "append", referenceActivityId: null };
        title.textContent = "Agregar actividad";
        referenceMessage.hidden = true;
        referenceMessage.textContent = "";
    }

    function restoreFocus() {
        const focusTarget = openerElement?.isConnected ? openerElement : fallbackFocusElement;
        openerElement = null;
        queueMicrotask(() => focusTarget?.focus());
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

    function openDialog(context, opener) {
        resetFormState();
        formContext = context;
        openerElement = opener;

        if (context.mode === "insert_before") {
            title.textContent = `Agregar antes de: ${context.referenceActivity.name}`;
            referenceMessage.textContent = `La hora define el orden final. Referencia: ${context.referenceActivity.name}.`;
            referenceMessage.hidden = false;
            startTimeInput.value = context.referenceActivity.plannedStartTime;
            endTimeInput.value = context.referenceActivity.plannedEndTime;
        }

        dialog.showModal();
        nameInput.focus();
    }

    form.addEventListener("submit", (event) => {
        event.preventDefault();
        clearErrors();

        const result = validateActivityDraft({
            name: nameInput.value,
            plannedStartTime: startTimeInput.value,
            plannedEndTime: endTimeInput.value,
        });
        if (result.errors.length) {
            showErrors(result.errors);
            return;
        }

        try {
            onSubmit(result.draft, {
                mode: formContext.mode,
                referenceActivityId: formContext.referenceActivityId,
            });
            dialog.close("saved");
        } catch (error) {
            showErrors([{ field: "name", message: "No fue posible agregar la actividad." }]);
            console.error(error);
        }
    });

    cancelButton.addEventListener("click", () => dialog.close("cancelled"));
    dialog.addEventListener("close", () => {
        resetFormState();
        restoreFocus();
    });

    return {
        openAppend(opener) {
            openDialog({ mode: "append", referenceActivityId: null }, opener);
        },

        openInsertBefore(referenceActivity, opener) {
            openDialog(
                {
                    mode: "insert_before",
                    referenceActivityId: referenceActivity.id,
                    referenceActivity,
                },
                opener,
            );
        },
    };
}
