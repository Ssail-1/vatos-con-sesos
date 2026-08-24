export const activityTypeDefinitions = Object.freeze({
    anchor: { label: "Ancla" },
    periodic: { label: "Periódica" },
    event: { label: "Evento" },
    unexpected: { label: "Imprevista" },
});

export const habitTypeDefinitions = Object.freeze({
    scheduled: { label: "Hábito programado" },
});

export function isValidClassification(kind, itemType) {
    if (kind === "activity") return Boolean(activityTypeDefinitions[itemType]);
    if (kind === "habit") return Boolean(habitTypeDefinitions[itemType]);
    return false;
}

export function getPlanItemType(planItem) {
    return planItem.kind === "activity" ? planItem.activityType : planItem.habitType;
}

export function getClassificationLabel(planItem) {
    if (planItem.kind === "habit" && habitTypeDefinitions[planItem.habitType]) {
        return habitTypeDefinitions[planItem.habitType].label;
    }
    const definition = activityTypeDefinitions[planItem.activityType];
    return definition ? `Actividad ${definition.label.toLowerCase()}` : "Clasificación no válida";
}
