import { getNextStatus } from "../domain/activity-status.js";
import { isValidClassification } from "../domain/activity-classification.js";
import { isValidTimeRange, timeRangesOverlap } from "../utils/date-time.js";

export class ActivityStoreError extends Error {
    constructor(code, message, details = {}) {
        super(message);
        this.name = "ActivityStoreError";
        this.code = code;
        this.details = details;
    }
}

function cloneActivity(activity) {
    return { ...activity, statesByDate: { ...activity.statesByDate } };
}

function compareActivities(firstActivity, secondActivity) {
    return (
        firstActivity.plannedStartTime.localeCompare(secondActivity.plannedStartTime) ||
        firstActivity.position - secondActivity.position
    );
}

function isValidDraft(activityDraft) {
    return (
        typeof activityDraft?.name === "string" &&
        activityDraft.name.trim().length > 0 &&
        activityDraft.name.trim().length <= 80 &&
        isValidClassification(activityDraft.recordKind, activityDraft.recordSubtype) &&
        isValidTimeRange(activityDraft.plannedStartTime, activityDraft.plannedEndTime)
    );
}

function createActivityId(existingActivities, sequence) {
    let candidate;
    do {
        candidate = globalThis.crypto?.randomUUID
            ? `activity-${globalThis.crypto.randomUUID()}`
            : `activity-${Date.now()}-${sequence}-${Math.random().toString(16).slice(2)}`;
    } while (existingActivities.some((activity) => activity.id === candidate));
    return candidate;
}

export function createActivityStore(initialActivities) {
    let activities = initialActivities.map(cloneActivity).sort(compareActivities);
    let idSequence = 0;

    function renumberActivities() {
        activities.forEach((activity, index) => {
            activity.position = index + 1;
        });
    }

    function sortAndRenumber() {
        activities.sort(compareActivities);
        renumberActivities();
    }

    function buildActivity(activityDraft, position) {
        if (!isValidDraft(activityDraft)) {
            throw new ActivityStoreError(
                "invalid_record",
                "El registro no cumple el contrato de datos.",
            );
        }

        idSequence += 1;
        return {
            id: createActivityId(activities, idSequence),
            name: activityDraft.name.trim(),
            recordKind: activityDraft.recordKind,
            recordSubtype: activityDraft.recordSubtype,
            position,
            plannedStartTime: activityDraft.plannedStartTime,
            plannedEndTime: activityDraft.plannedEndTime,
            statesByDate: {},
        };
    }

    sortAndRenumber();

    function findTimeConflict(startTime, endTime, ignoredActivityId = null) {
        return (
            activities.find(
                (activity) =>
                    activity.id !== ignoredActivityId &&
                    timeRangesOverlap(
                        startTime,
                        endTime,
                        activity.plannedStartTime,
                        activity.plannedEndTime,
                    ),
            ) || null
        );
    }

    function validateBeforeMutation(activityDraft, ignoredActivityId = null) {
        if (!isValidDraft(activityDraft)) {
            throw new ActivityStoreError(
                "invalid_record",
                "El registro no cumple el contrato de datos.",
            );
        }

        const conflictingActivity = findTimeConflict(
            activityDraft.plannedStartTime,
            activityDraft.plannedEndTime,
            ignoredActivityId,
        );
        if (conflictingActivity) {
            throw new ActivityStoreError("time_conflict", "El horario se superpone.", {
                conflictingActivity: cloneActivity(conflictingActivity),
            });
        }
    }

    return {
        getActivities() {
            return activities.map(cloneActivity);
        },

        getActivityById(activityId) {
            const activity = activities.find((candidate) => candidate.id === activityId);
            return activity ? cloneActivity(activity) : null;
        },

        findTimeConflict(startTime, endTime, ignoredActivityId = null) {
            const activity = findTimeConflict(startTime, endTime, ignoredActivityId);
            return activity ? cloneActivity(activity) : null;
        },

        addActivity(activityDraft) {
            validateBeforeMutation(activityDraft);
            const activity = buildActivity(activityDraft, activities.length + 1);
            activities.push(activity);
            sortAndRenumber();
            return cloneActivity(activity);
        },

        insertActivityBefore(activityDraft, referenceActivityId) {
            const reference = activities.find((activity) => activity.id === referenceActivityId);
            if (!reference) return this.addActivity(activityDraft);

            validateBeforeMutation(activityDraft);
            const activity = buildActivity(activityDraft, reference.position - 0.5);
            activities.push(activity);
            sortAndRenumber();
            return cloneActivity(activity);
        },

        updateActivity(activityId, activityDraft) {
            const activity = activities.find((candidate) => candidate.id === activityId);
            if (!activity) {
                throw new ActivityStoreError("not_found", "El registro ya no existe.");
            }

            validateBeforeMutation(activityDraft, activityId);
            activity.name = activityDraft.name.trim();
            activity.recordKind = activityDraft.recordKind;
            activity.recordSubtype = activityDraft.recordSubtype;
            activity.plannedStartTime = activityDraft.plannedStartTime;
            activity.plannedEndTime = activityDraft.plannedEndTime;
            sortAndRenumber();
            return cloneActivity(activity);
        },

        advanceActivityStatus(activityId, dateKey) {
            const activity = activities.find((candidate) => candidate.id === activityId);
            if (!activity || typeof dateKey !== "string") return null;

            const nextStatus = getNextStatus(activity.statesByDate[dateKey] || "pending");
            if (nextStatus === "pending") delete activity.statesByDate[dateKey];
            else activity.statesByDate[dateKey] = nextStatus;
            return nextStatus;
        },
    };
}
