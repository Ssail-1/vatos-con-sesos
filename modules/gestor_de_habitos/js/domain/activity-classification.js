export const recordKindDefinitions = {
    activity: { label: "Actividad", defaultSubtype: "periodic" },
    habit: { label: "Hábito", defaultSubtype: "scheduled" },
};

export const recordSubtypeDefinitions = {
    anchor: { label: "Ancla", recordKind: "activity" },
    periodic: { label: "Periódica", recordKind: "activity" },
    unexpected: { label: "Imprevista", recordKind: "activity" },
    scheduled: { label: "Hábito programado", recordKind: "habit" },
};

export function isValidClassification(recordKind, recordSubtype) {
    return (
        Boolean(recordKindDefinitions[recordKind]) &&
        recordSubtypeDefinitions[recordSubtype]?.recordKind === recordKind
    );
}

export function getClassificationLabel(recordKind, recordSubtype) {
    if (!isValidClassification(recordKind, recordSubtype)) return "Clasificación no válida";
    if (recordKind === "habit") return recordSubtypeDefinitions[recordSubtype].label;
    return `${recordKindDefinitions[recordKind].label} ${recordSubtypeDefinitions[recordSubtype].label.toLowerCase()}`;
}
