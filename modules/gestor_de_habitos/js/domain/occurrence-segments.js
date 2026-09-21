import { isValidOccurrenceStatus } from "./occurrence-status.js";
import { isValidTimeRange, timeToMinutes } from "../utils/date-time.js";

export const CONFLICT_REASONS = Object.freeze([
    "priority_override",
    "user_forced_override",
]);

export const ORIGIN_REASONS = Object.freeze(["conflict_insertion"]);

export const LAST_CONFLICT_ACTIONS = Object.freeze([
    "conflict_insertion",
    "conflict_move",
]);

export function compareOccurrenceSegments(first, second) {
    return first.startTime.localeCompare(second.startTime)
        || first.endTime.localeCompare(second.endTime)
        || first.id.localeCompare(second.id);
}

export function getSegmentValidationError(occurrence) {
    if (!Array.isArray(occurrence?.segments)) return "missing_segments";
    if (occurrence.segments.length === 0) return "empty_segments";

    const ids = new Set();
    for (const segment of occurrence.segments) {
        if (!segment || typeof segment !== "object" || Array.isArray(segment)) {
            return "invalid_segment";
        }
        if (typeof segment.id !== "string" || !segment.id || ids.has(segment.id)) {
            return ids.has(segment.id) ? "duplicate_segment_id" : "invalid_segment_id";
        }
        ids.add(segment.id);
        if (!isValidTimeRange(segment.startTime, segment.endTime)) {
            return "invalid_segment_time";
        }
        if (!isValidOccurrenceStatus(segment.status)) return "invalid_segment_status";
        if (
            segment.startTime < occurrence.startTime
            || segment.endTime > occurrence.endTime
        ) {
            return "segment_outside_parent";
        }
    }
    return null;
}

export function cloneOrderedSegments(segments) {
    return segments
        .map((segment) => ({ ...segment }))
        .sort(compareOccurrenceSegments);
}

function formatDuration(totalMinutes) {
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    if (hours && minutes) return `${hours}h ${minutes}min`;
    if (hours) return `${hours}h`;
    return `${minutes}min`;
}

export function calculateSegmentDuration(segments) {
    if (!Array.isArray(segments) || segments.length === 0) return null;
    const totalMinutes = segments.reduce((total, segment) => (
        total + timeToMinutes(segment.endTime) - timeToMinutes(segment.startTime)
    ), 0);
    return formatDuration(totalMinutes);
}

export function isMultiSegmentOccurrence(occurrence) {
    return Array.isArray(occurrence?.segments) && occurrence.segments.length > 1;
}
