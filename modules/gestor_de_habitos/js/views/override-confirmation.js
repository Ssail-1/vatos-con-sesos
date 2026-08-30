const ACTIVITY_TYPE_LABELS = Object.freeze({
    anchor: "actividad ancla",
    periodic: "actividad periódica",
    event: "evento",
    unexpected: "actividad imprevista",
});

const OPERATION_LABELS = Object.freeze({
    create_plan_item: "Crear",
    add_occurrence: "Agregar una fecha de",
    update_occurrence: "Actualizar",
});

function formatDate(dateKey) {
    const [year, month, day] = dateKey.split("-").map(Number);
    return new Intl.DateTimeFormat("es-MX", {
        day: "numeric",
        month: "long",
        year: "numeric",
    }).format(new Date(year, month - 1, day));
}

function describeCandidateType(candidate) {
    if (candidate.kind === "habit") return "hábito programado";
    return ACTIVITY_TYPE_LABELS[candidate.activityType] ?? "actividad";
}

function createScheduleItem({ date, startTime, endTime }, prefix = "") {
    const item = document.createElement("li");
    const dateText = document.createElement("strong");
    dateText.textContent = formatDate(date);
    const scheduleText = document.createElement("span");
    scheduleText.textContent = `${prefix}${startTime}–${endTime}`;
    item.append(dateText, scheduleText);
    return item;
}

export function createOverrideConfirmationView({
    dialog,
    candidateSummary,
    candidateOccurrences,
    conflictList,
    consequence,
    errorRegion,
    backButton,
    continueButton,
}) {
    let openerElement = null;
    let confirmOperation = null;
    let completeOperation = null;
    let confirmedResult = null;

    function clearError() {
        errorRegion.hidden = true;
        errorRegion.textContent = "";
        continueButton.disabled = false;
    }

    function render(prepared) {
        const operationLabel = OPERATION_LABELS[prepared.operation.kind] ?? "Guardar";
        const candidateType = describeCandidateType(prepared.candidate);
        candidateSummary.textContent = `${operationLabel} ${candidateType}: “${prepared.candidate.name}”`;
        candidateOccurrences.replaceChildren(
            ...prepared.candidate.occurrences.map((occurrence) => createScheduleItem(occurrence)),
        );
        conflictList.replaceChildren(...prepared.conflicts.map((conflict) => {
            const item = createScheduleItem(conflict, `${conflict.planItemName} · `);
            item.dataset.occurrenceId = conflict.id;
            return item;
        }));
        const pendingCount = prepared.conflicts.filter(({ status }) => status === "pending").length;
        const inProgressCount = prepared.conflicts.filter(({ status }) => status === "in_progress").length;
        const consequences = [];
        if (pendingCount) {
            consequences.push(pendingCount === 1
                ? "el registro pendiente se marcará como Cancelado"
                : `${pendingCount} registros pendientes se marcarán como Cancelados`);
        }
        if (inProgressCount) {
            consequences.push(inProgressCount === 1
                ? "el registro en progreso se marcará como No terminada"
                : `${inProgressCount} registros en progreso se marcarán como No terminados`);
        }
        consequence.textContent = `Si continúas, ${consequences.join(" y ")} únicamente para las fechas indicadas.`;
    }

    backButton.addEventListener("click", () => dialog.close("back"));
    dialog.addEventListener("keydown", (event) => {
        if (event.key !== "Tab") return;
        const focusableButtons = [backButton, continueButton].filter((button) => !button.disabled);
        const firstButton = focusableButtons[0];
        const lastButton = focusableButtons.at(-1);
        const movingBeforeFirst = event.shiftKey && document.activeElement === firstButton;
        const movingAfterLast = !event.shiftKey && document.activeElement === lastButton;
        if (!movingBeforeFirst && !movingAfterLast) return;
        event.preventDefault();
        (event.shiftKey ? lastButton : firstButton).focus();
    });
    continueButton.addEventListener("click", () => {
        clearError();
        try {
            confirmedResult = confirmOperation();
            dialog.close("confirmed");
        } catch (error) {
            errorRegion.textContent = error.message;
            errorRegion.hidden = false;
            continueButton.disabled = true;
            backButton.focus();
        }
    });

    dialog.addEventListener("close", () => {
        const wasConfirmed = dialog.returnValue === "confirmed";
        const onComplete = completeOperation;
        const result = confirmedResult;
        const opener = openerElement;
        confirmOperation = null;
        completeOperation = null;
        confirmedResult = null;
        openerElement = null;
        clearError();

        if (wasConfirmed) {
            queueMicrotask(() => onComplete?.(result));
        } else {
            queueMicrotask(() => {
                if (opener?.isConnected) opener.focus();
            });
        }
    });

    return {
        open(prepared, { onConfirm, onComplete }) {
            if (prepared?.type !== "override_required" || !prepared.conflicts?.length) {
                throw new TypeError("La confirmación requiere al menos un conflicto desplazable.");
            }
            openerElement = document.activeElement;
            confirmOperation = onConfirm;
            completeOperation = onComplete;
            confirmedResult = null;
            clearError();
            render(prepared);
            dialog.showModal();
            backButton.focus();
        },
    };
}
