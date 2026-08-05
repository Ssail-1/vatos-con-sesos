import { getNextStatus } from "../domain/activity-status.js";
import { isValidTimeRange } from "../utils/date-time.js";

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
            throw new TypeError("La actividad no cumple el contrato de datos.");
        }

        idSequence += 1;
        return {
            id: createActivityId(activities, idSequence),
            name: activityDraft.name.trim(),
            position,
            plannedStartTime: activityDraft.plannedStartTime,
            plannedEndTime: activityDraft.plannedEndTime,
            statesByDate: {},
        };
    }

    sortAndRenumber();

    return {
        getActivities() {
            return activities.map(cloneActivity);
        },

        getActivityById(activityId) {
            const activity = activities.find((candidate) => candidate.id === activityId);
            return activity ? cloneActivity(activity) : null;
        },

        addActivity(activityDraft) {
            const activity = buildActivity(activityDraft, activities.length + 1);
            activities.push(activity);
            sortAndRenumber();
            return cloneActivity(activity);
        },

        insertActivityBefore(activityDraft, referenceActivityId) {
            const reference = activities.find((activity) => activity.id === referenceActivityId);
            if (!reference) return this.addActivity(activityDraft);

            const activity = buildActivity(activityDraft, reference.position - 0.5);
            activities.push(activity);
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
