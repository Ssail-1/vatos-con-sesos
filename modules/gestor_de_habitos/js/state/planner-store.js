import { isValidClassification, getPlanItemType } from "../domain/plan-item-classification.js";
import { cloneGenerationConfig, isGenerationSlotId } from "../domain/generation-slots.js";
import {
    DELETION_REASONS,
    getEarlierStoppedFromDate,
    getIndividualDeletionPolicy,
    getStopPlanningPolicy,
    shouldRemoveOccurrenceWhenStopping,
} from "../domain/deletion-policy.js";
import { getSchedulingPriority, PRIORITY_OVERRIDE_REASON } from "../domain/scheduling-priority.js";
import {
    getNextStatus,
    isValidOccurrenceStatus,
} from "../domain/occurrence-status.js";
import {
    getDateTemporalZone,
    getHistoryCutoff,
    HISTORY_EDIT_WINDOW_DAYS,
    reconcileFrozenStatus,
    TEMPORAL_ZONES,
} from "../domain/temporal-integrity.js";
import { findConflictInDraftSet, findOccurrenceConflict, findOccurrenceConflicts } from "../scheduling/conflict-detector.js";
import {
    getLatestExplicitDate,
    materializeOccurrenceDrafts,
    validateGenerationConfig,
} from "../scheduling/materializer.js";
import {
    addDays,
    getMonthEnd,
    getMonthStart,
    getIsoWeekday,
    isValidDateKey,
    isValidTimeRange,
    timeRangesOverlap,
} from "../utils/date-time.js";

export class PlannerStoreError extends Error {
    constructor(code, message, details = {}) {
        super(message);
        this.name = "PlannerStoreError";
        this.code = code;
        this.details = details;
    }
}

function preserveGenerationControls(existingConfig, nextConfig) {
    const candidate = cloneGenerationConfig(nextConfig);
    if (candidate === null || existingConfig === null) return candidate;
    if (existingConfig.excludedDates !== undefined) {
        candidate.excludedDates = [...existingConfig.excludedDates];
    }
    if (existingConfig.stoppedFromDate !== undefined) {
        candidate.stoppedFromDate = existingConfig.stoppedFromDate;
    }
    return candidate;
}

function clonePlanItem(planItem) {
    return { ...planItem, generationConfig: cloneGenerationConfig(planItem.generationConfig) };
}

function cloneOccurrence(occurrence) {
    return {
        ...occurrence,
        ...(occurrence.statusContext ? { statusContext: { ...occurrence.statusContext } } : {}),
    };
}

function getGenerationSlotIds(planItem) {
    const config = planItem.generationConfig;
    if (config === null) return [];
    return (config.mode === "manual_dates" ? config.entries : config.slots).map(({ id }) => id);
}

function generationConfigHasMultipleSlotsPerDate(config) {
    if (config?.mode === "interval_days") return config.slots.length > 1;
    const groupingValues = config?.mode === "weekly"
        ? config.slots.map(({ isoWeekday }) => isoWeekday)
        : config?.mode === "manual_dates"
            ? config.entries.map(({ date }) => date)
            : [];
    return new Set(groupingValues).size !== groupingValues.length;
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
        !isValidOccurrenceStatus(draft.status) ||
        (
            draft.sourceGenerationSlotId !== undefined &&
            draft.sourceGenerationSlotId !== null &&
            !isGenerationSlotId(draft.sourceGenerationSlotId)
        ) ||
        draft.statusContext !== undefined && (
            draft.statusContext?.reason !== PRIORITY_OVERRIDE_REASON ||
            typeof draft.statusContext.sourceOccurrenceId !== "string" ||
            !draft.statusContext.sourceOccurrenceId
        )
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
    if (occurrence.sourceGenerationSlotId) {
        return [occurrence.sourceGenerationSlotId, occurrence.date].join("|");
    }
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
    const dates = config.entries.map((entry) => entry.date).sort();
    return { rangeStart: dates[0], rangeEnd: dates.at(-1) };
}

export function createPlannerStore(initialPlanItems, statusOverrides = [], referenceDateKey, options = {}) {
    if (!isValidDateKey(referenceDateKey)) {
        throw new PlannerStoreError("invalid_reference_date", "La fecha de referencia no es válida.");
    }

    const historyEditWindowDays = options.historyEditWindowDays ?? HISTORY_EDIT_WINDOW_DAYS;
    const getCurrentDateKey = options.getCurrentDateKey ?? (() => referenceDateKey);
    // Valida también la configuración de la ventana antes de materializar datos.
    getHistoryCutoff(referenceDateKey, historyEditWindowDays);

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
    const initialSlotIds = planItems.flatMap(getGenerationSlotIds);
    if (new Set(initialSlotIds).size !== initialSlotIds.length) {
        throw new PlannerStoreError(
            "duplicate_generation_slot_id",
            "Cada GenerationSlot debe tener identidad única entre todos los PlanItems.",
        );
    }

    function validateGenerationSlotOwnership(candidatePlanItem, replacedPlanItemId = null) {
        const occupiedIds = new Set(
            planItems
                .filter(({ id }) => id !== replacedPlanItemId)
                .flatMap(getGenerationSlotIds),
        );
        if (getGenerationSlotIds(candidatePlanItem).some((id) => occupiedIds.has(id))) {
            throw new PlannerStoreError(
                "duplicate_generation_slot_id",
                "El UUID de un GenerationSlot ya pertenece a otro PlanItem.",
            );
        }
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

    function getCurrentReferenceDate() {
        const currentReferenceDate = getCurrentDateKey();
        if (!isValidDateKey(currentReferenceDate)) {
            throw new PlannerStoreError("invalid_reference_date", "La fecha actual no es válida.");
        }
        return currentReferenceDate;
    }

    function reconcileTemporalState(referenceDate = getCurrentReferenceDate()) {
        const reconciled = [];
        occurrences.forEach((occurrence) => {
            if (getDateTemporalZone(occurrence.date, referenceDate, historyEditWindowDays) !== TEMPORAL_ZONES.FROZEN) return;
            const reconciledStatus = reconcileFrozenStatus(occurrence.status);
            if (reconciledStatus === occurrence.status) return;
            occurrence.status = reconciledStatus;
            reconciled.push(cloneOccurrence(occurrence));
        });
        planItems.forEach((planItem) => {
            const config = planItem.generationConfig;
            if (!config?.excludedDates?.length) return;
            const editableExclusions = config.excludedDates.filter((date) =>
                getDateTemporalZone(date, referenceDate, historyEditWindowDays) !== TEMPORAL_ZONES.FROZEN
            );
            if (editableExclusions.length === config.excludedDates.length) return;
            planItem.generationConfig = {
                ...config,
                excludedDates: editableExclusions,
            };
        });
        return reconciled;
    }

    function requireScheduleMutableDate(date) {
        if (!isValidDateKey(date)) {
            throw new PlannerStoreError("invalid_occurrence", "La fecha de la occurrence no es válida.");
        }
        const referenceDate = getCurrentReferenceDate();
        reconcileTemporalState(referenceDate);
        const zone = getDateTemporalZone(date, referenceDate, historyEditWindowDays);
        if (zone === TEMPORAL_ZONES.FROZEN) {
            throw new PlannerStoreError("history_frozen", "La occurrence está fuera de la ventana editable y es de solo lectura.");
        }
        return { referenceDate, zone };
    }

    function requireStatusTransition(occurrence, targetStatus) {
        const temporal = requireScheduleMutableDate(occurrence.date);
        if (
            temporal.zone === TEMPORAL_ZONES.FUTURE &&
            (!["pending", "cancelled"].includes(occurrence.status) || !["pending", "cancelled"].includes(targetStatus))
        ) {
            throw new PlannerStoreError(
                "future_status_locked",
                "En una fecha futura solamente puede alternarse entre Pendiente y Cancelada.",
            );
        }
        return temporal;
    }

    function requireDraftsOutsideFrozenHistory(drafts, referenceDate = getCurrentReferenceDate()) {
        reconcileTemporalState(referenceDate);
        const containsFrozenDate = drafts.some(({ date }) =>
            getDateTemporalZone(date, referenceDate, historyEditWindowDays) === TEMPORAL_ZONES.FROZEN
        );
        if (containsFrozenDate) {
            throw new PlannerStoreError(
                "history_frozen",
                "No se pueden crear registros dentro del historial congelado.",
            );
        }
    }

    function requirePlanningActiveOnDate(planItem, date) {
        if (planItem.generationConfig?.stoppedFromDate && date >= planItem.generationConfig.stoppedFromDate) {
            throw new PlannerStoreError(
                "planning_stopped",
                `La planificación está detenida desde ${planItem.generationConfig.stoppedFromDate} y no puede reanudarse implícitamente.`,
            );
        }
    }

    // El bootstrap aplica primero sus fixtures y después cierra cualquier historia ya congelada.
    reconcileTemporalState();

    function describeConflict(conflict) {
        const planItem = getPlanItemReference(conflict.planItemId);
        return {
            ...cloneOccurrence(conflict),
            planItemName: planItem?.name ?? "Otro registro",
        };
    }

    function getDeletionOptionsInternal(planItemId, selectedDate, referenceDate = getCurrentReferenceDate()) {
        if (!isValidDateKey(selectedDate)) {
            throw new PlannerStoreError("invalid_occurrence", "La fecha seleccionada no es válida.");
        }
        reconcileTemporalState(referenceDate);
        const planItem = getPlanItemReference(planItemId);
        if (!planItem) throw new PlannerStoreError("not_found", "El PlanItem no existe.");
        const selectedOccurrences = occurrences.filter((occurrence) =>
            occurrence.planItemId === planItemId && occurrence.date === selectedDate
        );
        const individual = getIndividualDeletionPolicy({
            occurrences: selectedOccurrences,
            referenceDate,
            historyEditWindowDays,
            hasGenerationConfig: planItem.generationConfig !== null,
        });
        const stop = getStopPlanningPolicy({
            generationConfig: planItem.generationConfig,
            selectedDate,
            referenceDate,
            historyEditWindowDays,
        });
        return {
            planItem: clonePlanItem(planItem),
            selectedDate,
            individual: {
                ...individual,
                occurrence: individual.occurrence ? cloneOccurrence(individual.occurrence) : null,
            },
            stop: { ...stop },
        };
    }

    function throwForDeletionDecision(decision, operationName) {
        if (decision.reason === DELETION_REASONS.FROZEN) {
            throw new PlannerStoreError("history_frozen", "El historial congelado es de solo lectura.");
        }
        if (decision.reason === DELETION_REASONS.AMBIGUOUS) {
            throw new PlannerStoreError("ambiguous_occurrence", "Hay varias occurrences para este registro y fecha; no se eliminó ninguna.");
        }
        if (decision.reason === DELETION_REASONS.MISSING_OCCURRENCE) {
            throw new PlannerStoreError("not_found", "No existe una occurrence para eliminar en la fecha seleccionada.");
        }
        if (decision.reason === DELETION_REASONS.MISSING_GENERATION_CONFIG) {
            throw new PlannerStoreError("missing_generation_config", `No existe configuración de generación para ${operationName}.`);
        }
        if (decision.reason === DELETION_REASONS.ALREADY_STOPPED) {
            throw new PlannerStoreError("already_stopped", `La planificación ya está detenida desde ${decision.stoppedFromDate}.`);
        }
        throw new PlannerStoreError("deletion_status_locked", "El estado de la occurrence conserva historia y no permite esta eliminación.");
    }

    function ensureMaterializedThrough(targetDate) {
        reconcileTemporalState();
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

    function buildWeeklyCandidate(planItem, generationConfig, rangeStart, rangeEnd, removableOccurrences) {
        const candidatePlanItem = {
            ...planItem,
            generationConfig: preserveGenerationControls(planItem.generationConfig, generationConfig),
        };
        validatePlanItem(candidatePlanItem);
        validateGenerationSlotOwnership(candidatePlanItem, planItem.id);
        const removableIds = new Set(removableOccurrences.map(({ id }) => id));
        const preservedOccurrences = occurrences.filter(({ id }) => !removableIds.has(id));
        const preservedDates = new Set(
            preservedOccurrences
                .filter((occurrence) => occurrence.planItemId === planItem.id && occurrence.date >= rangeStart)
                .map(({ date }) => date),
        );
        const drafts = materializeOccurrenceDrafts(candidatePlanItem, rangeStart, rangeEnd)
            .filter(({ date }) => !preservedDates.has(date));
        validateDraftSet(drafts, preservedOccurrences);
        return { candidatePlanItem, preservedOccurrences, drafts };
    }

    function evaluatePriorityConflicts(candidatePlanItem, candidateDrafts, ignoredOccurrenceId = null) {
        const internalConflict = findConflictInDraftSet(candidateDrafts, []);
        if (internalConflict) {
            throw new PlannerStoreError("candidate_internal_conflict", "La operación contiene horarios que se superponen entre sí.");
        }
        const conflictsById = new Map();
        candidateDrafts.forEach((draft) => {
            findOccurrenceConflicts(draft, occurrences, ignoredOccurrenceId).forEach((conflict) => {
                conflictsById.set(conflict.id, conflict);
            });
        });
        const conflicts = [...conflictsById.values()].sort(compareOccurrences);
        if (!conflicts.length) return { type: "ready", conflicts: [] };
        const described = conflicts.map(describeConflict);
        const completed = conflicts.find(({ status }) => status === "completed");
        if (completed) {
            throw new PlannerStoreError("completed_conflict", "El intervalo contiene un registro ya completado y protegido.", {
                conflictingOccurrences: described,
            });
        }
        const candidatePriority = getSchedulingPriority(candidatePlanItem);
        const nonDisplaceable = conflicts.find((conflict) => {
            const existingPlanItem = getPlanItemReference(conflict.planItemId);
            return !existingPlanItem || candidatePriority <= getSchedulingPriority(existingPlanItem);
        });
        if (nonDisplaceable) {
            throw new PlannerStoreError("priority_conflict", "La prioridad del registro no permite desplazar todo el conjunto en conflicto.", {
                conflictingOccurrences: described,
            });
        }
        return { type: "override_required", conflicts: described };
    }

    function preparePlanItemCreation(planItemDraft) {
        const normalized = normalizePlanItemDraft(planItemDraft);
        validatePlanItem(normalized);
        validateGenerationSlotOwnership(normalized);
        const preview = { id: "__candidate_plan_item__", ...normalized };
        const explicitDate = getLatestExplicitDate([preview]);
        const previewHorizon = explicitDate && explicitDate > materializedThrough ? getMonthEnd(explicitDate) : materializedThrough;
        const range = getConfiguredMaterializationRange(preview, materializationStart, previewHorizon);
        const drafts = materializeOccurrenceDrafts(preview, range.rangeStart, range.rangeEnd);
        requireDraftsOutsideFrozenHistory(drafts);
        return {
            ...evaluatePriorityConflicts(preview, drafts),
            operation: { kind: "create_plan_item", planItemDraft: clonePlanItem(normalized) },
            candidate: {
                name: preview.name,
                kind: preview.kind,
                activityType: preview.activityType,
                habitType: preview.habitType,
                occurrences: drafts.map(({ date, startTime, endTime }) => ({ date, startTime, endTime })),
            },
        };
    }

    function prepareOccurrenceAddition(planItemId, occurrenceDraft) {
        const planItem = getPlanItemReference(planItemId);
        if (!planItem) throw new PlannerStoreError("not_found", "El PlanItem no existe.");
        requireScheduleMutableDate(occurrenceDraft?.date);
        requirePlanningActiveOnDate(planItem, occurrenceDraft?.date);
        const draft = { planItemId, date: occurrenceDraft?.date, startTime: occurrenceDraft?.startTime, endTime: occurrenceDraft?.endTime, status: "pending" };
        validateOccurrenceDraft(draft);
        return {
            ...evaluatePriorityConflicts(planItem, [draft]),
            operation: { kind: "add_occurrence", planItemId, occurrenceDraft: { ...occurrenceDraft } },
            candidate: {
                name: planItem.name,
                kind: planItem.kind,
                activityType: planItem.activityType,
                habitType: planItem.habitType,
                occurrences: [{ date: draft.date, startTime: draft.startTime, endTime: draft.endTime }],
            },
        };
    }

    function prepareOccurrenceUpdate(planItemId, planItemChanges, occurrenceId, occurrenceChanges) {
        const planItem = getPlanItemReference(planItemId);
        const occurrence = getOccurrenceReference(occurrenceId);
        if (!planItem || !occurrence || occurrence.planItemId !== planItemId) {
            throw new PlannerStoreError("not_found", "El registro seleccionado ya no existe.");
        }
        requireScheduleMutableDate(occurrence.date);
        if (occurrenceChanges.date !== occurrence.date) {
            throw new PlannerStoreError("date_locked", "La fecha pertenece al día seleccionado y no puede cambiarse desde este editor.");
        }
        const candidatePlanItem = normalizePlanItemDraft({ ...planItem, ...planItemChanges, generationConfig: planItem.generationConfig });
        validatePlanItem(candidatePlanItem);
        const candidateOccurrence = { ...occurrence, date: occurrenceChanges.date, startTime: occurrenceChanges.startTime, endTime: occurrenceChanges.endTime };
        validateOccurrenceDraft(candidateOccurrence);
        return {
            ...evaluatePriorityConflicts(candidatePlanItem, [candidateOccurrence], occurrenceId),
            operation: { kind: "update_occurrence", planItemId, planItemChanges: { ...planItemChanges }, occurrenceId, occurrenceChanges: { ...occurrenceChanges } },
            candidate: {
                name: candidatePlanItem.name,
                kind: candidatePlanItem.kind,
                activityType: candidatePlanItem.activityType,
                habitType: candidatePlanItem.habitType,
                occurrences: [{
                    date: candidateOccurrence.date,
                    startTime: candidateOccurrence.startTime,
                    endTime: candidateOccurrence.endTime,
                }],
            },
        };
    }

    function prepareOperation(operation) {
        if (operation?.kind === "create_plan_item") return preparePlanItemCreation(operation.planItemDraft);
        if (operation?.kind === "add_occurrence") return prepareOccurrenceAddition(operation.planItemId, operation.occurrenceDraft);
        if (operation?.kind === "update_occurrence") return prepareOccurrenceUpdate(operation.planItemId, operation.planItemChanges, operation.occurrenceId, operation.occurrenceChanges);
        throw new PlannerStoreError("invalid_operation", "La operación preparada no es válida.");
    }

    function conflictSignature(conflicts) {
        return conflicts.map(({ id, date, startTime, endTime, status }) => [id, date, startTime, endTime, status].join("|")).sort().join(";");
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

        getHistoryEditWindowDays() {
            return historyEditWindowDays;
        },

        reconcileTemporalState,

        getDeletionOptions(planItemId, selectedDate) {
            return getDeletionOptionsInternal(planItemId, selectedDate);
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
            const referenceDate = getCurrentReferenceDate();
            reconcileTemporalState(referenceDate);
            const historyCutoff = getHistoryCutoff(referenceDate, historyEditWindowDays);
            const mutableRangeStart = rangeStart < historyCutoff ? historyCutoff : rangeStart;
            if (mutableRangeStart > rangeEnd) return [];
            const created = materializePlanItemInternal(planItem, mutableRangeStart, rangeEnd);
            return created.map(({ id }) => cloneOccurrence(getOccurrenceReference(id)));
        },

        ensureMaterializedThrough,

        preparePlanItemCreation,
        prepareOccurrenceAddition,
        prepareOccurrenceUpdate,

        commitPreparedScheduleChange(prepared) {
            const current = prepareOperation(prepared?.operation);
            if (prepared.type !== current.type || conflictSignature(prepared.conflicts ?? []) !== conflictSignature(current.conflicts ?? [])) {
                throw new PlannerStoreError("stale_override", "La agenda cambió desde la confirmación. Revisa nuevamente los conflictos.");
            }
            const conflictReferences = (current.conflicts ?? []).map(({ id }) => getOccurrenceReference(id));
            const originalStatuses = conflictReferences.map(({ id, status, statusContext }) => ({
                id,
                status,
                ...(statusContext ? { statusContext: { ...statusContext } } : {}),
            }));
            if (current.type === "override_required") {
                conflictReferences.forEach((occurrence) => {
                    occurrence.status = occurrence.status === "in_progress" ? "not_finished" : "cancelled";
                });
            }
            try {
                let result;
                if (current.operation.kind === "create_plan_item") {
                    result = this.addPlanItem(current.operation.planItemDraft);
                } else if (current.operation.kind === "add_occurrence") {
                    result = this.addOccurrenceForPlanItem(current.operation.planItemId, current.operation.occurrenceDraft);
                } else {
                    result = this.updatePlanItemAndOccurrence(
                        current.operation.planItemId,
                        current.operation.planItemChanges,
                        current.operation.occurrenceId,
                        current.operation.occurrenceChanges,
                    );
                }

                if (current.type === "override_required") {
                    const sourceOccurrences = current.operation.kind === "create_plan_item"
                        ? result.occurrences.filter(({ planItemId }) => planItemId === result.planItem.id)
                        : current.operation.kind === "add_occurrence"
                            ? [result]
                            : [result.occurrence];
                    conflictReferences.forEach((occurrence) => {
                        const source = sourceOccurrences.find((candidate) =>
                            candidate.date === occurrence.date &&
                            timeRangesOverlap(candidate.startTime, candidate.endTime, occurrence.startTime, occurrence.endTime)
                        ) ?? sourceOccurrences[0];
                        occurrence.statusContext = {
                            reason: PRIORITY_OVERRIDE_REASON,
                            sourceOccurrenceId: source.id,
                        };
                    });
                }
                return result;
            } catch (error) {
                originalStatuses.forEach(({ id, status, statusContext }) => {
                    const occurrence = getOccurrenceReference(id);
                    if (!occurrence) return;
                    occurrence.status = status;
                    if (statusContext) occurrence.statusContext = { ...statusContext };
                    else delete occurrence.statusContext;
                });
                throw error;
            }
        },

        addOccurrenceForPlanItem(planItemId, occurrenceDraft) {
            const planItem = getPlanItemReference(planItemId);
            if (!planItem) throw new PlannerStoreError("not_found", "El PlanItem no existe.");
            requireScheduleMutableDate(occurrenceDraft?.date);
            requirePlanningActiveOnDate(planItem, occurrenceDraft?.date);
            const candidate = {
                planItemId,
                date: occurrenceDraft?.date,
                startTime: occurrenceDraft?.startTime,
                endTime: occurrenceDraft?.endTime,
                status: "pending",
            };
            const excludedDates = planItem.generationConfig?.excludedDates ?? [];
            const restoredConfig = planItem.generationConfig === null
                ? null
                : {
                    ...cloneGenerationConfig(planItem.generationConfig),
                    ...(excludedDates.includes(candidate.date)
                        ? { excludedDates: excludedDates.filter((date) => date !== candidate.date) }
                        : {}),
                };
            const candidatePlanItem = { ...planItem, generationConfig: restoredConfig };
            if (restoredConfig !== null) {
                const matchingSlotDrafts = materializeOccurrenceDrafts(
                    candidatePlanItem,
                    candidate.date,
                    candidate.date,
                ).filter((draft) => (
                    draft.startTime === candidate.startTime && draft.endTime === candidate.endTime
                ));
                if (matchingSlotDrafts.length === 1) {
                    candidate.sourceGenerationSlotId = matchingSlotDrafts[0].sourceGenerationSlotId;
                }
            }
            validateOccurrenceDraft(candidate);
            validateDraftSet([candidate]);
            validatePlanItem(candidatePlanItem);
            const created = assignOccurrenceIds([candidate])[0];
            const planItemIndex = planItems.findIndex(({ id }) => id === planItemId);
            planItems[planItemIndex] = candidatePlanItem;
            occurrences.push(created);
            occurrences.sort(compareOccurrences);
            return cloneOccurrence(created);
        },

        deleteOccurrenceForDate(occurrenceId) {
            const occurrence = getOccurrenceReference(occurrenceId);
            if (!occurrence) throw new PlannerStoreError("not_found", "La occurrence no existe.");
            const options = getDeletionOptionsInternal(occurrence.planItemId, occurrence.date);
            if (!options.individual.allowed) {
                throwForDeletionDecision(options.individual, "registrar la fecha excluida");
            }
            if (options.individual.occurrence.id !== occurrenceId) {
                throw new PlannerStoreError("ambiguous_occurrence", "La occurrence seleccionada dejó de ser inequívoca.");
            }

            const planItem = getPlanItemReference(occurrence.planItemId);
            const excludedDates = [...new Set([
                ...(planItem.generationConfig.excludedDates ?? []),
                occurrence.date,
            ])].sort();
            const candidatePlanItem = {
                ...planItem,
                generationConfig: {
                    ...cloneGenerationConfig(planItem.generationConfig),
                    excludedDates,
                },
            };
            validatePlanItem(candidatePlanItem);
            const preservedOccurrences = occurrences.filter(({ id }) => id !== occurrenceId);

            const planItemIndex = planItems.findIndex(({ id }) => id === planItem.id);
            planItems[planItemIndex] = candidatePlanItem;
            occurrences = preservedOccurrences;
            return {
                planItem: clonePlanItem(candidatePlanItem),
                deletedOccurrence: cloneOccurrence(occurrence),
            };
        },

        stopPlanItemFromDate(planItemId, selectedDate) {
            const referenceDate = getCurrentReferenceDate();
            const options = getDeletionOptionsInternal(planItemId, selectedDate, referenceDate);
            if (!options.stop.allowed) {
                throwForDeletionDecision(options.stop, "detener la planificación");
            }

            const planItem = getPlanItemReference(planItemId);
            const stoppedFromDate = getEarlierStoppedFromDate(
                planItem.generationConfig.stoppedFromDate,
                selectedDate,
            );
            const candidatePlanItem = {
                ...planItem,
                generationConfig: {
                    ...cloneGenerationConfig(planItem.generationConfig),
                    stoppedFromDate,
                    ...(planItem.generationConfig.excludedDates !== undefined
                        ? {
                            excludedDates: planItem.generationConfig.excludedDates.filter(
                                (date) => date < stoppedFromDate,
                            ),
                        }
                        : {}),
                },
            };
            validatePlanItem(candidatePlanItem);
            const removedOccurrences = occurrences.filter((occurrence) =>
                occurrence.planItemId === planItemId &&
                shouldRemoveOccurrenceWhenStopping(occurrence, stoppedFromDate, referenceDate)
            );
            const removedIds = new Set(removedOccurrences.map(({ id }) => id));
            const preservedOccurrences = occurrences.filter(({ id }) => !removedIds.has(id));

            const planItemIndex = planItems.findIndex(({ id }) => id === planItemId);
            planItems[planItemIndex] = candidatePlanItem;
            occurrences = preservedOccurrences;
            return {
                planItem: clonePlanItem(candidatePlanItem),
                removedOccurrences: removedOccurrences.map(cloneOccurrence),
            };
        },

        applyWeeklyToWeek(planItemId, anchorDate, generationConfig) {
            const planItem = getPlanItemReference(planItemId);
            if (!planItem || !isValidDateKey(anchorDate)) {
                throw new PlannerStoreError("not_found", "El registro o la fecha seleccionada no existe.");
            }
            const { referenceDate } = requireScheduleMutableDate(anchorDate);
            if (generationConfig?.mode !== "weekly") {
                throw new PlannerStoreError("invalid_generation_config", "La excepción semanal requiere configuración weekly.");
            }
            validateGenerationConfig(generationConfig);
            if (generationConfigHasMultipleSlotsPerDate(generationConfig)) {
                throw new PlannerStoreError(
                    "ambiguous_week",
                    "Apply week no modifica todavía una configuración que produce varios horarios por fecha.",
                );
            }
            const weekStart = addDays(anchorDate, 1 - getIsoWeekday(anchorDate));
            const weekEnd = addDays(weekStart, 6);
            const historyCutoff = getHistoryCutoff(referenceDate, historyEditWindowDays);
            const mutableWeekStart = weekStart < historyCutoff ? historyCutoff : weekStart;
            const occurrenceCountByDate = new Map();
            occurrences
                .filter((occurrence) => (
                    occurrence.planItemId === planItemId
                    && occurrence.date >= mutableWeekStart
                    && occurrence.date <= weekEnd
                ))
                .forEach(({ date }) => {
                    occurrenceCountByDate.set(date, (occurrenceCountByDate.get(date) ?? 0) + 1);
                });
            if ([...occurrenceCountByDate.values()].some((count) => count > 1)) {
                throw new PlannerStoreError(
                    "ambiguous_week",
                    "Hay varios horarios del mismo registro en una fecha; esta edición multi-slot requiere un alcance posterior.",
                );
            }
            const pendingByDate = new Map();
            occurrences
                .filter((occurrence) => occurrence.planItemId === planItemId && occurrence.status === "pending" && occurrence.date >= mutableWeekStart && occurrence.date <= weekEnd)
                .forEach((occurrence) => {
                    const sameDate = pendingByDate.get(occurrence.date) ?? [];
                    sameDate.push(occurrence);
                    pendingByDate.set(occurrence.date, sameDate);
                });
            const removable = [...pendingByDate.values()].flat();
            const { preservedOccurrences, drafts } = buildWeeklyCandidate(planItem, generationConfig, mutableWeekStart, weekEnd, removable);
            const reusableByDate = new Map(removable.map((occurrence) => [occurrence.date, occurrence]));
            const replacements = drafts.map((draft) => {
                const reusable = reusableByDate.get(draft.date);
                if (reusable) return { ...draft, id: reusable.id };
                return assignOccurrenceIds([draft])[0];
            });
            occurrences = [...preservedOccurrences, ...replacements].sort(compareOccurrences);
            return replacements.map(cloneOccurrence);
        },

        applyGenerationConfigFromDate(planItemId, effectiveDate, generationConfig) {
            const planItem = getPlanItemReference(planItemId);
            if (!planItem || !isValidDateKey(effectiveDate)) {
                throw new PlannerStoreError("not_found", "El registro o la fecha efectiva no existe.");
            }
            requireScheduleMutableDate(effectiveDate);
            const normalizedConfig = cloneGenerationConfig(generationConfig);
            if (["weekly", "interval_days"].includes(normalizedConfig?.mode)) {
                normalizedConfig.startDate = effectiveDate;
                if (!normalizedConfig.indefinite && normalizedConfig.endDate < effectiveDate) {
                    throw new PlannerStoreError("invalid_generation_config", "La fecha final es anterior a la fecha efectiva.");
                }
            }
            validateGenerationConfig(normalizedConfig);
            if (generationConfigHasMultipleSlotsPerDate(normalizedConfig)) {
                throw new PlannerStoreError(
                    "ambiguous_future",
                    "Apply future no modifica todavía una configuración que produce varios horarios por fecha.",
                );
            }
            const occurrenceCountByDate = new Map();
            occurrences
                .filter((occurrence) => occurrence.planItemId === planItemId && occurrence.date >= effectiveDate)
                .forEach(({ date }) => {
                    occurrenceCountByDate.set(date, (occurrenceCountByDate.get(date) ?? 0) + 1);
                });
            if ([...occurrenceCountByDate.values()].some((count) => count > 1)) {
                throw new PlannerStoreError(
                    "ambiguous_future",
                    "Hay varios horarios del mismo registro en una fecha; Apply future multi-slot pertenece a una fase posterior.",
                );
            }
            const removable = occurrences.filter(
                (occurrence) => occurrence.planItemId === planItemId && occurrence.status === "pending" && occurrence.date >= effectiveDate,
            );
            const preservedEffectiveDateOccurrences = occurrences
                .filter(
                    (occurrence) =>
                        occurrence.planItemId === planItemId &&
                        occurrence.date === effectiveDate &&
                        occurrence.status !== "pending",
                )
                .map(cloneOccurrence);
            const { candidatePlanItem, preservedOccurrences, drafts } = buildWeeklyCandidate(
                planItem,
                normalizedConfig,
                effectiveDate,
                materializedThrough,
                removable,
            );
            const created = assignOccurrenceIds(drafts);
            const planItemIndex = planItems.findIndex(({ id }) => id === planItemId);
            planItems[planItemIndex] = candidatePlanItem;
            occurrences = [...preservedOccurrences, ...created].sort(compareOccurrences);
            return {
                planItem: clonePlanItem(candidatePlanItem),
                occurrences: created.map(cloneOccurrence),
                preservedEffectiveDateOccurrences,
            };
        },

        addPlanItem(planItemDraft) {
            reconcileTemporalState();
            const normalized = normalizePlanItemDraft(planItemDraft);
            validatePlanItem(normalized);
            validateGenerationSlotOwnership(normalized);
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
            requireDraftsOutsideFrozenHistory(candidateDrafts);
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
            reconcileTemporalState();
            return {
                planItem: clonePlanItem(candidate),
                occurrences: createdOccurrences.map(({ id }) => cloneOccurrence(getOccurrenceReference(id))),
            };
        },

        updatePlanItemAndOccurrence(planItemId, planItemChanges, occurrenceId, occurrenceChanges) {
            const planItem = getPlanItemReference(planItemId);
            const occurrence = getOccurrenceReference(occurrenceId);
            if (!planItem || !occurrence || occurrence.planItemId !== planItemId) {
                throw new PlannerStoreError("not_found", "El registro seleccionado ya no existe.");
            }
            requireScheduleMutableDate(occurrence.date);
            if (occurrenceChanges.date !== occurrence.date) {
                throw new PlannerStoreError("date_locked", "La fecha pertenece al día seleccionado y no puede cambiarse desde este editor.");
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
            requireScheduleMutableDate(occurrence.date);
            const candidate = {
                ...occurrence,
                date: occurrenceChanges.date,
                startTime: occurrenceChanges.startTime,
                endTime: occurrenceChanges.endTime,
            };
            validateOccurrenceDraft(candidate);
            requireScheduleMutableDate(candidate.date);
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
            requireStatusTransition(occurrence, status);
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
            const temporal = requireStatusTransition(
                occurrence,
                occurrence.status === "pending" ? "cancelled" : occurrence.status === "cancelled" ? "pending" : getNextStatus(occurrence.status),
            );
            const nextStatus = temporal.zone === TEMPORAL_ZONES.FUTURE
                ? occurrence.status === "pending" ? "cancelled" : "pending"
                : getNextStatus(occurrence.status);

            try {
                return this.setOccurrenceStatus(occurrenceId, nextStatus);
            } catch (error) {
                const canUseReleasedStatusFallback =
                    temporal.zone === TEMPORAL_ZONES.EDITABLE &&
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
