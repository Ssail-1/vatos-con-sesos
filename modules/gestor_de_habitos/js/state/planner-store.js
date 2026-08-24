import { isValidClassification, getPlanItemType } from "../domain/plan-item-classification.js";
import {
    getNextStatus,
    isValidOccurrenceStatus,
} from "../domain/occurrence-status.js";
import { findConflictInDraftSet, findOccurrenceConflict } from "../scheduling/conflict-detector.js";
import {
    getLatestExplicitDate,
    materializeOccurrenceDrafts,
    validateGenerationConfig,
} from "../scheduling/materializer.js";
import {
    addDays,
    getMonthEnd,
    getMonthStart,
    isValidDateKey,
    isValidTimeRange,
} from "../utils/date-time.js";

export class PlannerStoreError extends Error {
    constructor(code, message, details = {}) {
        super(message);
        this.name = "PlannerStoreError";
        this.code = code;
        this.details = details;
    }
}

function cloneGenerationConfig(config) {
    if (config === null) return null;
    if (config.mode === "weekly") {
        return {
            ...config,
            weekdays: [...config.weekdays].sort((first, second) => first - second),
            weekdayTimeOverrides: Object.fromEntries(
                Object.entries(config.weekdayTimeOverrides).map(([key, value]) => [key, { ...value }]),
            ),
        };
    }
    if (config.mode === "manual_dates") {
        return { ...config, entries: config.entries.map((entry) => ({ ...entry })) };
    }
    return { ...config };
}

function clonePlanItem(planItem) {
    return { ...planItem, generationConfig: cloneGenerationConfig(planItem.generationConfig) };
}

function cloneOccurrence(occurrence) {
    return { ...occurrence };
}

function normalizePlanItemDraft(draft) {
    const planItem = {
        name: typeof draft?.name === "string" ? draft.name.trim() : "",
        kind: draft?.kind,
        generationConfig: cloneGenerationConfig(draft?.generationConfig ?? null),
    };
    if (draft?.kind === "activity") planItem.activityType = draft.activityType;
    if (draft?.kind === "habit") planItem.habitType = draft.habitType;
    return planItem;
}

function validatePlanItem(planItem) {
    if (!planItem.name || planItem.name.length > 80) {
        throw new PlannerStoreError("invalid_plan_item", "El nombre debe tener entre 1 y 80 caracteres.");
    }
    if (!isValidClassification(planItem.kind, getPlanItemType(planItem))) {
        throw new PlannerStoreError("invalid_plan_item", "La clasificación no es válida.");
    }
    if (
        (planItem.kind === "activity" && "habitType" in planItem) ||
        (planItem.kind === "habit" && "activityType" in planItem)
    ) {
        throw new PlannerStoreError("invalid_plan_item", "El PlanItem no respeta el modelo discriminado.");
    }
    validateGenerationConfig(planItem.generationConfig);
}

function validateOccurrenceDraft(draft) {
    if (
        !draft ||
        typeof draft.planItemId !== "string" ||
        !isValidDateKey(draft.date) ||
        !isValidTimeRange(draft.startTime, draft.endTime) ||
        !isValidOccurrenceStatus(draft.status)
    ) {
        throw new PlannerStoreError("invalid_occurrence", "La occurrence no cumple el contrato.");
    }
}

function createUniqueId(prefix, collection, sequence) {
    let candidate;
    do {
        candidate = globalThis.crypto?.randomUUID
            ? globalThis.crypto.randomUUID()
            : `${prefix}-${Date.now()}-${sequence}-${Math.random().toString(16).slice(2)}`;
    } while (collection.some((item) => item.id === candidate));
    return candidate;
}

function occurrenceKey(occurrence) {
    return [occurrence.planItemId, occurrence.date, occurrence.startTime, occurrence.endTime].join("|");
}

function compareOccurrences(first, second) {
    return (
        first.date.localeCompare(second.date) ||
        first.startTime.localeCompare(second.startTime) ||
        first.endTime.localeCompare(second.endTime) ||
        first.id.localeCompare(second.id)
    );
}

function getConfiguredMaterializationRange(planItem, fallbackStart, fallbackEnd) {
    const config = planItem.generationConfig;
    if (config === null || config.indefinite === true) {
        return { rangeStart: fallbackStart, rangeEnd: fallbackEnd };
    }
    if (config.mode === "weekly" || config.mode === "interval_days") {
        return { rangeStart: config.startDate, rangeEnd: config.endDate };
    }
    if (config.mode === "single_date") {
        return { rangeStart: config.date, rangeEnd: config.date };
    }
    const dates = config.entries.map((entry) => entry.date).sort();
    return { rangeStart: dates[0], rangeEnd: dates.at(-1) };
}

export function createPlannerStore(initialPlanItems, statusOverrides = [], referenceDateKey) {
    if (!isValidDateKey(referenceDateKey)) {
        throw new PlannerStoreError("invalid_reference_date", "La fecha de referencia no es válida.");
    }

    let planItems = initialPlanItems.map(clonePlanItem);
    let occurrences = [];
    let idSequence = 0;
    const materializationStart = getMonthStart(referenceDateKey);
    const minimumHorizon = getMonthEnd(referenceDateKey, 1);
    const explicitDate = getLatestExplicitDate(planItems);
    let materializedThrough =
        explicitDate && explicitDate > minimumHorizon ? getMonthEnd(explicitDate) : minimumHorizon;

    planItems.forEach(validatePlanItem);
    if (new Set(planItems.map((item) => item.id)).size !== planItems.length) {
        throw new PlannerStoreError("duplicate_plan_item_id", "Los IDs de PlanItem deben ser únicos.");
    }

    function assignOccurrenceIds(drafts) {
        return drafts.map((draft) => {
            idSequence += 1;
            return {
                ...draft,
                id: createUniqueId("occurrence", occurrences, idSequence),
            };
        });
    }

    function filterAutomaticDuplicates(drafts, baseOccurrences = occurrences) {
        const knownKeys = new Set(baseOccurrences.map(occurrenceKey));
        return drafts.filter((draft) => {
            const key = occurrenceKey(draft);
            if (knownKeys.has(key)) return false;
            knownKeys.add(key);
            return true;
        });
    }

    function validateDraftSet(drafts, baseOccurrences = occurrences) {
        drafts.forEach(validateOccurrenceDraft);
        const conflictResult = findConflictInDraftSet(drafts, baseOccurrences);
        if (conflictResult) {
            throw new PlannerStoreError("time_conflict", "El horario se superpone.", {
                conflictingOccurrence: describeConflict(conflictResult.conflict),
            });
        }
    }

    function commitMaterializedDrafts(drafts) {
        const uniqueDrafts = filterAutomaticDuplicates(drafts);
        validateDraftSet(uniqueDrafts);
        const created = assignOccurrenceIds(uniqueDrafts);
        occurrences.push(...created);
        occurrences.sort(compareOccurrences);
        return created.map(cloneOccurrence);
    }

    function materializePlanItemInternal(planItem, rangeStart, rangeEnd) {
        return commitMaterializedDrafts(materializeOccurrenceDrafts(planItem, rangeStart, rangeEnd));
    }

    // El bootstrap materializa una vez; renderizar nunca vuelve a consultar generationConfig.
    planItems.forEach((planItem) => {
        const range = getConfiguredMaterializationRange(
            planItem,
            materializationStart,
            materializedThrough,
        );
        materializePlanItemInternal(planItem, range.rangeStart, range.rangeEnd);
    });

    statusOverrides.forEach((override) => {
        const occurrence = occurrences.find(
            (candidate) =>
                candidate.planItemId === override.planItemId && candidate.date === override.date,
        );
        if (occurrence && isValidOccurrenceStatus(override.status)) occurrence.status = override.status;
    });

    function getPlanItemReference(planItemId) {
        return planItems.find((candidate) => candidate.id === planItemId) ?? null;
    }

    function getOccurrenceReference(occurrenceId) {
        return occurrences.find((candidate) => candidate.id === occurrenceId) ?? null;
    }

    function describeConflict(conflict) {
        const planItem = getPlanItemReference(conflict.planItemId);
        return {
            ...cloneOccurrence(conflict),
            planItemName: planItem?.name ?? "Otro registro",
        };
    }

    function ensureMaterializedThrough(targetDate) {
        const targetHorizon = getMonthEnd(targetDate);
        if (!targetHorizon || targetHorizon <= materializedThrough) return [];
        const rangeStart = addDays(materializedThrough, 1);
        const drafts = planItems.flatMap((planItem) =>
            planItem.generationConfig?.indefinite
                ? materializeOccurrenceDrafts(planItem, rangeStart, targetHorizon)
                : [],
        );
        const uniqueDrafts = filterAutomaticDuplicates(drafts);
        validateDraftSet(uniqueDrafts);
        const created = assignOccurrenceIds(uniqueDrafts);
        occurrences.push(...created);
        occurrences.sort(compareOccurrences);
        materializedThrough = targetHorizon;
        return created.map(cloneOccurrence);
    }

    return {
        getPlanItems() {
            return planItems.map(clonePlanItem);
        },

        getPlanItemById(planItemId) {
            const planItem = getPlanItemReference(planItemId);
            return planItem ? clonePlanItem(planItem) : null;
        },

        getOccurrences() {
            return occurrences.map(cloneOccurrence);
        },

        getOccurrenceById(occurrenceId) {
            const occurrence = getOccurrenceReference(occurrenceId);
            return occurrence ? cloneOccurrence(occurrence) : null;
        },

        getOccurrencesForDate(date) {
            return occurrences
                .filter((occurrence) => occurrence.date === date)
                .sort(compareOccurrences)
                .map(cloneOccurrence);
        },

        getOccurrencesForMonth(year, month) {
            const monthKey = `${year}-${String(month + 1).padStart(2, "0")}-`;
            return occurrences
                .filter((occurrence) => occurrence.date.startsWith(monthKey))
                .sort(compareOccurrences)
                .map(cloneOccurrence);
        },

        getOccurrencesForPlanItem(planItemId) {
            return occurrences
                .filter((occurrence) => occurrence.planItemId === planItemId)
                .sort(compareOccurrences)
                .map(cloneOccurrence);
        },

        getMaterializedThrough() {
            return materializedThrough;
        },

        findTimeConflict(date, startTime, endTime, ignoredOccurrenceId = null, status = "pending") {
            const conflict = findOccurrenceConflict(
                { date, startTime, endTime, status },
                occurrences,
                ignoredOccurrenceId,
            );
            return conflict ? describeConflict(conflict) : null;
        },

        materializePlanItem(planItemId, rangeStart, rangeEnd) {
            const planItem = getPlanItemReference(planItemId);
            if (!planItem) throw new PlannerStoreError("not_found", "El PlanItem no existe.");
            return materializePlanItemInternal(planItem, rangeStart, rangeEnd);
        },

        ensureMaterializedThrough,

        addPlanItem(planItemDraft) {
            const normalized = normalizePlanItemDraft(planItemDraft);
            validatePlanItem(normalized);
            idSequence += 1;
            const candidate = {
                id: createUniqueId("plan-item", planItems, idSequence),
                ...normalized,
            };
            const explicitCandidateDate = getLatestExplicitDate([candidate]);
            const candidateHorizon =
                explicitCandidateDate && explicitCandidateDate > materializedThrough
                    ? getMonthEnd(explicitCandidateDate)
                    : materializedThrough;
            const candidateRange = getConfiguredMaterializationRange(
                candidate,
                materializationStart,
                candidateHorizon,
            );
            const candidateDrafts = materializeOccurrenceDrafts(
                candidate,
                candidateRange.rangeStart,
                candidateRange.rangeEnd,
            );
            const extensionStart = addDays(materializedThrough, 1);
            const extensionDrafts =
                candidateHorizon > materializedThrough
                    ? planItems.flatMap((planItem) =>
                          planItem.generationConfig?.indefinite
                              ? materializeOccurrenceDrafts(planItem, extensionStart, candidateHorizon)
                              : [],
                      )
                    : [];
            const combinedDrafts = filterAutomaticDuplicates([...extensionDrafts, ...candidateDrafts]);
            validateDraftSet(combinedDrafts);
            const createdOccurrences = assignOccurrenceIds(combinedDrafts);
            planItems.push(candidate);
            occurrences.push(...createdOccurrences);
            occurrences.sort(compareOccurrences);
            materializedThrough = candidateHorizon;
            return {
                planItem: clonePlanItem(candidate),
                occurrences: createdOccurrences.map(cloneOccurrence),
            };
        },

        updatePlanItemAndOccurrence(planItemId, planItemChanges, occurrenceId, occurrenceChanges) {
            const planItem = getPlanItemReference(planItemId);
            const occurrence = getOccurrenceReference(occurrenceId);
            if (!planItem || !occurrence || occurrence.planItemId !== planItemId) {
                throw new PlannerStoreError("not_found", "El registro seleccionado ya no existe.");
            }
            const candidatePlanItem = normalizePlanItemDraft({
                ...planItem,
                ...planItemChanges,
                generationConfig: planItem.generationConfig,
            });
            validatePlanItem(candidatePlanItem);
            const candidateOccurrence = {
                ...occurrence,
                date: occurrenceChanges.date,
                startTime: occurrenceChanges.startTime,
                endTime: occurrenceChanges.endTime,
            };
            validateOccurrenceDraft(candidateOccurrence);
            const conflict = findOccurrenceConflict(candidateOccurrence, occurrences, occurrence.id);
            if (conflict) {
                throw new PlannerStoreError("time_conflict", "El horario se superpone.", {
                    conflictingOccurrence: describeConflict(conflict),
                });
            }
            const planItemIndex = planItems.findIndex((candidate) => candidate.id === planItemId);
            planItems[planItemIndex] = { id: planItem.id, ...candidatePlanItem };
            occurrence.date = candidateOccurrence.date;
            occurrence.startTime = candidateOccurrence.startTime;
            occurrence.endTime = candidateOccurrence.endTime;
            occurrences.sort(compareOccurrences);
            return {
                planItem: clonePlanItem(planItems[planItemIndex]),
                occurrence: cloneOccurrence(occurrence),
            };
        },

        updateOccurrence(occurrenceId, occurrenceChanges) {
            const occurrence = getOccurrenceReference(occurrenceId);
            if (!occurrence) throw new PlannerStoreError("not_found", "La occurrence no existe.");
            const candidate = {
                ...occurrence,
                date: occurrenceChanges.date,
                startTime: occurrenceChanges.startTime,
                endTime: occurrenceChanges.endTime,
            };
            validateOccurrenceDraft(candidate);
            const conflict = findOccurrenceConflict(candidate, occurrences, occurrence.id);
            if (conflict) {
                throw new PlannerStoreError("time_conflict", "El horario se superpone.", {
                    conflictingOccurrence: describeConflict(conflict),
                });
            }
            occurrence.date = candidate.date;
            occurrence.startTime = candidate.startTime;
            occurrence.endTime = candidate.endTime;
            occurrences.sort(compareOccurrences);
            return cloneOccurrence(occurrence);
        },

        setOccurrenceStatus(occurrenceId, status) {
            const occurrence = getOccurrenceReference(occurrenceId);
            if (!occurrence) throw new PlannerStoreError("not_found", "La occurrence no existe.");
            if (!isValidOccurrenceStatus(status)) {
                throw new PlannerStoreError("invalid_status", "El estado no es válido.");
            }
            const candidate = { ...occurrence, status };
            const conflict = findOccurrenceConflict(candidate, occurrences, occurrence.id);
            if (conflict) {
                throw new PlannerStoreError("time_conflict", "El estado reactivaría un horario ocupado.", {
                    conflictingOccurrence: describeConflict(conflict),
                });
            }
            occurrence.status = status;
            return cloneOccurrence(occurrence);
        },

        advanceOccurrenceStatus(occurrenceId) {
            const occurrence = getOccurrenceReference(occurrenceId);
            if (!occurrence) throw new PlannerStoreError("not_found", "La occurrence no existe.");
            const nextStatus = getNextStatus(occurrence.status);

            try {
                return this.setOccurrenceStatus(occurrenceId, nextStatus);
            } catch (error) {
                const canUseReleasedStatusFallback =
                    occurrence.status === "cancelled" &&
                    nextStatus === "pending" &&
                    error instanceof PlannerStoreError &&
                    error.code === "time_conflict";

                if (!canUseReleasedStatusFallback) throw error;
                return this.setOccurrenceStatus(occurrenceId, "not_completed");
            }
        },
    };
}
