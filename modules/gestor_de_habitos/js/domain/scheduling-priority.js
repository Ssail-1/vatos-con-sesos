export const SCHEDULING_PRIORITY = Object.freeze({
    NORMAL: 100,
    EVENT: 200,
    UNEXPECTED: 300,
});

export const PRIORITY_OVERRIDE_REASON = "priority_override";

export function wasDisplacedByPriorityOverride(occurrence) {
    return occurrence?.statusContext?.reason === PRIORITY_OVERRIDE_REASON;
}

export function getSchedulingPriority(planItem) {
    if (planItem.kind !== "activity") return SCHEDULING_PRIORITY.NORMAL;
    if (planItem.activityType === "event") return SCHEDULING_PRIORITY.EVENT;
    if (planItem.activityType === "unexpected") return SCHEDULING_PRIORITY.UNEXPECTED;
    return SCHEDULING_PRIORITY.NORMAL;
}
