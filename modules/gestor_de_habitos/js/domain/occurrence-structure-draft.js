import { isValidOccurrenceStatus } from "./occurrence-status.js";
import { isValidTimeRange, timeToMinutes, timeRangesOverlap } from "../utils/date-time.js";

let nextDraftKey = 0;

function newDraftKey() {
    nextDraftKey += 1;
    return `draft-${nextDraftKey}`;
}

export function createOccurrenceStructureDraft(occurrence) {
    if (!occurrence?.id || !Array.isArray(occurrence.segments) || !occurrence.segments.length) {
        throw new TypeError("La occurrence persistida requiere segments para editar su estructura.");
    }
    const segments = occurrence.segments.map(({ id, startTime, endTime, status }) => ({
        draftKey: `persisted-${id}`, id, startTime, endTime, status,
    }));
    return {
        occurrenceId: occurrence.id,
        date: occurrence.date,
        startTime: occurrence.startTime,
        endTime: occurrence.endTime,
        segments,
        original: {
            startTime: occurrence.startTime,
            endTime: occurrence.endTime,
            segments: segments.map(({ id, startTime, endTime, status }) => ({
                id, startTime, endTime, status,
            })),
        },
    };
}

export function addDraftSegment(draft) {
    const segment = { draftKey: newDraftKey(), startTime: "", endTime: "", status: "" };
    draft.segments.push(segment);
    return segment;
}

export function removeDraftSegment(draft, draftKey) {
    if (draft.segments.length <= 1) return false;
    const index = draft.segments.findIndex((segment) => segment.draftKey === draftKey);
    if (index < 0) return false;
    draft.segments.splice(index, 1);
    return true;
}

export function orderedDraftSegments(draft) {
    return [...draft.segments].sort((first, second) =>
        (!first.startTime && second.startTime ? 1 : first.startTime && !second.startTime ? -1 : 0)
        || first.startTime.localeCompare(second.startTime)
        || first.endTime.localeCompare(second.endTime)
        || first.draftKey.localeCompare(second.draftKey));
}

export function validateOccurrenceStructureDraft(draft) {
    if (!isValidTimeRange(draft.startTime, draft.endTime)) {
        return "Inicio general y Final general deben formar un horario válido.";
    }
    if (!draft.segments.length) return "La aparición necesita al menos un segment.";
    for (const segment of draft.segments) {
        if (!isValidTimeRange(segment.startTime, segment.endTime)) {
            return "Cada segment necesita inicio y final válidos.";
        }
        if (segment.startTime < draft.startTime || segment.endTime > draft.endTime) {
            return "Todos los segments deben caber dentro del horario general.";
        }
        if (!segment.id && !isValidOccurrenceStatus(segment.status)) {
            return "Selecciona un estado para cada segment nuevo.";
        }
    }
    const ordered = orderedDraftSegments(draft);
    for (let index = 1; index < ordered.length; index += 1) {
        if (timeRangesOverlap(
            ordered[index - 1].startTime, ordered[index - 1].endTime,
            ordered[index].startTime, ordered[index].endTime,
        )) return "Los segments de una misma aparición no pueden superponerse.";
    }
    return null;
}

export function buildOccurrenceStructurePayload(draft) {
    const error = validateOccurrenceStructureDraft(draft);
    if (error) throw new TypeError(error);
    return {
        startTime: draft.startTime,
        endTime: draft.endTime,
        segments: orderedDraftSegments(draft).map((segment) => segment.id
            ? { id: segment.id, startTime: segment.startTime, endTime: segment.endTime }
            : { startTime: segment.startTime, endTime: segment.endTime, status: segment.status }),
    };
}

export function canTranslateOccurrenceDraft(draft) {
    if (!isValidTimeRange(draft.startTime, draft.endTime)) return false;
    if (
        timeToMinutes(draft.endTime) - timeToMinutes(draft.startTime)
        !== timeToMinutes(draft.original.endTime) - timeToMinutes(draft.original.startTime)
    ) return false;
    if (draft.segments.length !== draft.original.segments.length) return false;
    return draft.original.segments.every((source) => draft.segments.some((candidate) =>
        candidate.id === source.id
        && candidate.startTime === source.startTime
        && candidate.endTime === source.endTime
        && candidate.status === source.status));
}

export function draftStructuralDuration(draft) {
    const minutes = draft.segments.reduce((total, segment) => {
        const start = timeToMinutes(segment.startTime);
        const end = timeToMinutes(segment.endTime);
        return total === null || start === null || end === null || end <= start
            ? null : total + end - start;
    }, 0);
    if (minutes === null) return "—";
    const hours = Math.floor(minutes / 60);
    const remainder = minutes % 60;
    if (hours && remainder) return `${hours}h ${remainder}min`;
    if (hours) return `${hours}h`;
    return `${remainder}min`;
}
