import { isValidClassification, getPlanItemType } from "../domain/plan-item-classification.js";
import {
    cloneGenerationConfig,
    isGenerationSlotId,
    preserveSlotExcludedDates,
} from "../domain/generation-slots.js";
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
    const candidate = preserveSlotExcludedDates(existingConfig, nextConfig);
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
            if (config === null) return;
            let changed = false;
            const candidate = cloneGenerationConfig(config);
            if (config.excludedDates?.length) {
                const editableExclusions = config.excludedDates.filter((date) =>
                    getDateTemporalZone(date, referenceDate, historyEditWindowDays) !== TEMPORAL_ZONES.FROZEN
                );
                if (editableExclusions.length !== config.excludedDates.length) {
                    candidate.excludedDates = editableExclusions;
                    changed = true;
                }
            }
            if (["weekly", "interval_days"].includes(config.mode)) {
                candidate.slots = candidate.slots.map((slot) => {
                    if (!slot.excludedDates?.length) return slot;
                    const editableExclusions = slot.excludedDates.filter((date) =>
                        getDateTemporalZone(date, referenceDate, historyEditWindowDays) !== TEMPORAL_ZONES.FROZEN
                    );
                    if (editableExclusions.length === slot.excludedDates.length) return slot;
                    changed = true;
                    return { ...slot, excludedDates: editableExclusions };
                });
            }
            if (changed) planItem.generationConfig = candidate;
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

    function generationConfigAfterOccurrenceEdit(planItem, occurrence, changes) {
        const config = cloneGenerationConfig(planItem.generationConfig);
        const sourceSlotId = occurrence.sourceGenerationSlotId;
        if (config === null || !sourceSlotId) return config;
        if (["weekly", "interval_days"].includes(config.mode)) {
            const sourceExists = config.slots.some(({ id }) => id === sourceSlotId);
            if (!sourceExists) {
                throw new PlannerStoreError("invalid_occurrence", "La occurrence no tiene un GenerationSlot válido.");
            }
            if (changes.date === occurrence.date) return config;
            return {
                ...config,
                slots: config.slots.map((slot) => (
                    slot.id === sourceSlotId
                        ? {
                            ...slot,
                            excludedDates: [...new Set([
                                ...(slot.excludedDates ?? []),
                                occurrence.date,
                            ])].sort(),
                        }
                        : slot
                )),
            };
        }
        const sourceExists = config.entries.some(({ id }) => id === sourceSlotId);
        if (!sourceExists) {
            throw new PlannerStoreError("invalid_occurrence", "La occurrence no tiene una entry manual válida.");
        }
        return {
            ...config,
            entries: config.entries.map((entry) => (
                entry.id === sourceSlotId
                    ? {
                        ...entry,
                        date: changes.date,
                        startTime: changes.startTime,
                        endTime: changes.endTime,
                    }
                    : entry
            )),
        };
    }

    function requireSourceSlotDateAvailable(occurrence, targetDate) {
        if (
            occurrence.sourceGenerationSlotId &&
            occurrences.some((candidate) => (
                candidate.id !== occurrence.id &&
                candidate.sourceGenerationSlotId === occurrence.sourceGenerationSlotId &&
                candidate.date === targetDate
            ))
        ) {
            throw new PlannerStoreError(
                "slot_date_conflict",
                "El GenerationSlot ya tiene una occurrence en la fecha destino.",
            );
        }
    }

    function getIsoWeekRange(anchorDate) {
        const weekStart = addDays(anchorDate, 1 - getIsoWeekday(anchorDate));
        return { weekStart, weekEnd: addDays(weekStart, 6) };
    }

    function addSlotExclusion(config, sourceGenerationSlotId, date) {
        if (!sourceGenerationSlotId) return config;
        let matched = false;
        const slots = config.slots.map((slot) => {
            if (slot.id !== sourceGenerationSlotId) return slot;
            matched = true;
            return {
                ...slot,
                excludedDates: [...new Set([...(slot.excludedDates ?? []), date])].sort(),
            };
        });
        if (!matched) {
            throw new PlannerStoreError(
                "invalid_occurrence",
                "La occurrence no tiene un GenerationSlot válido.",
            );
        }
        return { ...config, slots };
    }

    function requireExactOperationFields(operation, expectedFields) {
        if (
            !operation ||
            typeof operation !== "object" ||
            Object.keys(operation).length !== expectedFields.length ||
            expectedFields.some((field) => !Object.hasOwn(operation, field))
        ) {
            throw new PlannerStoreError("invalid_payload", "Una operación de Apply Week no cumple el contrato.");
        }
    }

    function validateLocalWeekOperations(operations) {
        if (!Array.isArray(operations) || operations.length === 0) {
            throw new PlannerStoreError("invalid_payload", "Apply Week requiere al menos una operación.");
        }
        const occurrenceIds = new Set();
        return operations.map((operation) => {
            const type = operation?.type;
            if (type === "update") {
                requireExactOperationFields(operation, ["type", "occurrenceId", "date", "startTime", "endTime"]);
            } else if (type === "delete") {
                requireExactOperationFields(operation, ["type", "occurrenceId"]);
            } else if (type === "create") {
                requireExactOperationFields(operation, ["type", "date", "startTime", "endTime"]);
            } else {
                throw new PlannerStoreError("invalid_payload", "El tipo de operación de Apply Week no es válido.");
            }
            if (["update", "delete"].includes(type)) {
                if (typeof operation.occurrenceId !== "string" || !operation.occurrenceId || occurrenceIds.has(operation.occurrenceId)) {
                    throw new PlannerStoreError("invalid_payload", "Un occurrenceId solo puede aparecer una vez.");
                }
                occurrenceIds.add(operation.occurrenceId);
            }
            if (["update", "create"].includes(type) && (
                !isValidDateKey(operation.date) ||
                !isValidTimeRange(operation.startTime, operation.endTime)
            )) {
                throw new PlannerStoreError("invalid_payload", "La fecha o el horario de Apply Week no es válido.");
            }
            return { ...operation };
        });
    }

    function validateLocalWeekFinalState(planItem, finalWeekOccurrences) {
        const sourceDates = new Set();
        finalWeekOccurrences.forEach((occurrence) => {
            validateOccurrenceDraft(occurrence);
            if (occurrence.sourceGenerationSlotId) {
                const key = `${occurrence.sourceGenerationSlotId}|${occurrence.date}`;
                if (sourceDates.has(key)) {
                    throw new PlannerStoreError(
                        "slot_date_conflict",
                        "Un GenerationSlot tendría dos occurrences en la misma fecha.",
                    );
                }
                sourceDates.add(key);
            }
        });

        const internalConflict = findConflictInDraftSet(finalWeekOccurrences, []);
        if (internalConflict) {
            throw new PlannerStoreError(
                "time_conflict",
                "El estado final de la semana contiene horarios que se superponen.",
                { conflictingOccurrence: describeConflict(internalConflict.conflict) },
            );
        }

        const externalOccurrences = occurrences.filter((occurrence) => occurrence.planItemId !== planItem.id);
        const conflictsById = new Map();
        finalWeekOccurrences.forEach((candidate) => {
            findOccurrenceConflicts(candidate, externalOccurrences).forEach((conflict) => {
                conflictsById.set(conflict.id, conflict);
            });
        });
        const conflicts = [...conflictsById.values()];
        if (!conflicts.length) return;
        const described = conflicts.map(describeConflict);
        if (conflicts.some(({ status }) => status === "completed")) {
            throw new PlannerStoreError(
                "completed_conflict",
                "El intervalo contiene un registro ya completado y protegido.",
                { conflictingOccurrences: described },
            );
        }
        const candidatePriority = getSchedulingPriority(planItem);
        if (conflicts.some((conflict) => {
            const existingPlanItem = getPlanItemReference(conflict.planItemId);
            return !existingPlanItem || candidatePriority <= getSchedulingPriority(existingPlanItem);
        })) {
            throw new PlannerStoreError(
                "priority_conflict",
                "La prioridad del registro no permite desplazar todo el conjunto en conflicto.",
                { conflictingOccurrences: described },
            );
        }
        throw new PlannerStoreError(
            "priority_override_required",
            "Apply Week requiere confirmar un desplazamiento por prioridad.",
            { conflictingOccurrences: described },
        );
    }

    function deriveRecurringWeekOperations(planItem, anchorDate, generationConfig) {
        const currentMode = planItem.generationConfig?.mode;
        if (currentMode === "manual_dates") {
            throw new PlannerStoreError("unsupported_mode", "Apply Week no está disponible para manual_dates.");
        }
        if (
            !["weekly", "interval_days"].includes(currentMode) ||
            generationConfig?.mode !== currentMode
        ) {
            throw new PlannerStoreError(
                "invalid_generation_config",
                "Apply Week requiere conservar el modo recurrente actual.",
            );
        }
        const candidateConfig = preserveGenerationControls(planItem.generationConfig, generationConfig);
        validateGenerationConfig(candidateConfig);
        const { weekStart, weekEnd } = getIsoWeekRange(anchorDate);
        const desired = materializeOccurrenceDrafts(
            { ...planItem, generationConfig: candidateConfig },
            weekStart,
            weekEnd,
        );
        const remainingDesired = new Set(desired);
        const existingRecurring = occurrences.filter((occurrence) => (
            occurrence.planItemId === planItem.id &&
            occurrence.date >= weekStart &&
            occurrence.date <= weekEnd &&
            occurrence.sourceGenerationSlotId
        ));
        const operations = [];
        existingRecurring.forEach((occurrence) => {
            let desiredOccurrence = desired.find((draft) => (
                remainingDesired.has(draft) &&
                draft.sourceGenerationSlotId === occurrence.sourceGenerationSlotId
            ));
            if (!desiredOccurrence) {
                const desiredOnDate = desired.filter((draft) => remainingDesired.has(draft) && draft.date === occurrence.date);
                const existingOnDate = existingRecurring.filter((candidate) => candidate.date === occurrence.date);
                if (desiredOnDate.length === 1 && existingOnDate.length === 1) {
                    [desiredOccurrence] = desiredOnDate;
                }
            }
            if (!desiredOccurrence) {
                operations.push({ type: "delete", occurrenceId: occurrence.id });
                return;
            }
            remainingDesired.delete(desiredOccurrence);
            if (
                occurrence.date !== desiredOccurrence.date ||
                occurrence.startTime !== desiredOccurrence.startTime ||
                occurrence.endTime !== desiredOccurrence.endTime
            ) {
                operations.push({
                    type: "update",
                    occurrenceId: occurrence.id,
                    date: desiredOccurrence.date,
                    startTime: desiredOccurrence.startTime,
                    endTime: desiredOccurrence.endTime,
                });
            }
        });
        const existingAdHoc = occurrences.filter((occurrence) => (
            occurrence.planItemId === planItem.id &&
            occurrence.date >= weekStart &&
            occurrence.date <= weekEnd &&
            !occurrence.sourceGenerationSlotId
        ));
        remainingDesired.forEach((draft) => {
            const alreadyRepresented = existingAdHoc.some((occurrence) => (
                occurrence.date === draft.date &&
                occurrence.startTime === draft.startTime &&
                occurrence.endTime === draft.endTime
            ));
            if (alreadyRepresented) return;
            operations.push({
                type: "create",
                date: draft.date,
                startTime: draft.startTime,
                endTime: draft.endTime,
            });
        });
        return operations;
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
            let restoredConfig = planItem.generationConfig === null
                ? null
                : {
                    ...cloneGenerationConfig(planItem.generationConfig),
                    ...(excludedDates.includes(candidate.date)
                        ? { excludedDates: excludedDates.filter((date) => date !== candidate.date) }
                        : {}),
                };
            if (restoredConfig !== null) {
                const configWithoutCandidateSlotExclusion = cloneGenerationConfig(restoredConfig);
                if (["weekly", "interval_days"].includes(configWithoutCandidateSlotExclusion.mode)) {
                    configWithoutCandidateSlotExclusion.slots = configWithoutCandidateSlotExclusion.slots.map((slot) => ({
                        ...slot,
                        ...(slot.excludedDates?.includes(candidate.date)
                            ? { excludedDates: slot.excludedDates.filter((date) => date !== candidate.date) }
                            : {}),
                    }));
                }
                const matchingSlotDrafts = materializeOccurrenceDrafts(
                    { ...planItem, generationConfig: configWithoutCandidateSlotExclusion },
                    candidate.date,
                    candidate.date,
                ).filter((draft) => (
                    draft.startTime === candidate.startTime && draft.endTime === candidate.endTime
                ));
                if (matchingSlotDrafts.length === 1) {
                    candidate.sourceGenerationSlotId = matchingSlotDrafts[0].sourceGenerationSlotId;
                    if (["weekly", "interval_days"].includes(restoredConfig.mode)) {
                        restoredConfig = {
                            ...restoredConfig,
                            slots: restoredConfig.slots.map((slot) => (
                                slot.id === candidate.sourceGenerationSlotId && slot.excludedDates?.includes(candidate.date)
                                    ? { ...slot, excludedDates: slot.excludedDates.filter((date) => date !== candidate.date) }
                                    : slot
                            )),
                        };
                    }
                }
            }
            const candidatePlanItem = { ...planItem, generationConfig: restoredConfig };
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
            const planItem = getPlanItemReference(occurrence.planItemId);
            if (!planItem) throw new PlannerStoreError("not_found", "El PlanItem no existe.");
            const referenceDate = getCurrentReferenceDate();
            reconcileTemporalState(referenceDate);
            const decision = getIndividualDeletionPolicy({
                occurrences: [occurrence],
                referenceDate,
                historyEditWindowDays,
                hasGenerationConfig: planItem.generationConfig !== null,
            });
            if (!decision.allowed) {
                throwForDeletionDecision(decision, "eliminar la occurrence");
            }
            let candidateConfig = cloneGenerationConfig(planItem.generationConfig);
            if (
                occurrence.sourceGenerationSlotId &&
                ["weekly", "interval_days"].includes(candidateConfig.mode)
            ) {
                candidateConfig.slots = candidateConfig.slots.map((slot) => (
                    slot.id === occurrence.sourceGenerationSlotId
                        ? {
                            ...slot,
                            excludedDates: [...new Set([
                                ...(slot.excludedDates ?? []),
                                occurrence.date,
                            ])].sort(),
                        }
                        : slot
                ));
            } else if (
                occurrence.sourceGenerationSlotId &&
                candidateConfig.mode === "manual_dates"
            ) {
                if (candidateConfig.entries.length === 1) {
                    throw new PlannerStoreError(
                        "last_manual_entry",
                        "No se puede eliminar la última entry manual.",
                    );
                }
                candidateConfig.entries = candidateConfig.entries.filter(
                    ({ id }) => id !== occurrence.sourceGenerationSlotId,
                );
            }
            const candidatePlanItem = { ...planItem, generationConfig: candidateConfig };
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
            const operations = deriveRecurringWeekOperations(planItem, anchorDate, generationConfig);
            if (!operations.length) {
                requireScheduleMutableDate(anchorDate);
                const { weekStart, weekEnd } = getIsoWeekRange(anchorDate);
                return occurrences
                    .filter((occurrence) => occurrence.planItemId === planItemId && occurrence.date >= weekStart && occurrence.date <= weekEnd)
                    .sort(compareOccurrences)
                    .map(cloneOccurrence);
            }
            return this.applyWeekOperations(planItemId, anchorDate, operations).occurrences;
        },

        applyWeekOperations(planItemId, anchorDate, operations) {
            const planItem = getPlanItemReference(planItemId);
            if (!planItem) throw new PlannerStoreError("not_found", "El PlanItem no existe.");
            if (!isValidDateKey(anchorDate)) {
                throw new PlannerStoreError("invalid_payload", "anchorDate no es una fecha válida.");
            }
            if (planItem.generationConfig?.mode === "manual_dates") {
                throw new PlannerStoreError("unsupported_mode", "Apply Week no está disponible para manual_dates.");
            }
            if (!["weekly", "interval_days"].includes(planItem.generationConfig?.mode)) {
                throw new PlannerStoreError("invalid_generation_config", "Apply Week requiere una configuración recurrente.");
            }
            const normalizedOperations = validateLocalWeekOperations(operations);
            const referenceDate = getCurrentReferenceDate();
            reconcileTemporalState(referenceDate);
            const { weekStart, weekEnd } = getIsoWeekRange(anchorDate);
            const initialWeek = occurrences
                .filter((occurrence) => occurrence.planItemId === planItemId && occurrence.date >= weekStart && occurrence.date <= weekEnd)
                .map(cloneOccurrence);
            const candidateById = new Map(initialWeek.map((occurrence) => [occurrence.id, occurrence]));
            let candidateConfig = cloneGenerationConfig(planItem.generationConfig);
            const createDrafts = [];
            const deletedIds = new Set();

            normalizedOperations.forEach((operation, index) => {
                if (operation.type === "create") {
                    if (operation.date < weekStart || operation.date > weekEnd) {
                        throw new PlannerStoreError("invalid_payload", "La creación debe quedar dentro de la semana objetivo.");
                    }
                    requireScheduleMutableDate(operation.date);
                    requirePlanningActiveOnDate(planItem, operation.date);
                    createDrafts.push({
                        id: `__apply_week_create_${index}__`,
                        planItemId,
                        date: operation.date,
                        startTime: operation.startTime,
                        endTime: operation.endTime,
                        status: "pending",
                    });
                    return;
                }

                const occurrence = candidateById.get(operation.occurrenceId);
                if (!occurrence || deletedIds.has(occurrence.id)) {
                    throw new PlannerStoreError("not_found", "La occurrence no existe en la semana seleccionada.");
                }
                requireScheduleMutableDate(occurrence.date);
                if (operation.type === "delete") {
                    const decision = getIndividualDeletionPolicy({
                        occurrences: [occurrence],
                        referenceDate,
                        historyEditWindowDays,
                        hasGenerationConfig: true,
                    });
                    if (!decision.allowed) throwForDeletionDecision(decision, "eliminar la occurrence");
                    if (occurrences.some((candidate) => candidate.statusContext?.sourceOccurrenceId === occurrence.id)) {
                        throw new PlannerStoreError("deletion_status_locked", "La occurrence conserva contexto de prioridad dependiente.");
                    }
                    deletedIds.add(occurrence.id);
                    candidateConfig = addSlotExclusion(
                        candidateConfig,
                        occurrence.sourceGenerationSlotId,
                        occurrence.date,
                    );
                    return;
                }

                if (operation.date < weekStart || operation.date > weekEnd) {
                    throw new PlannerStoreError("invalid_payload", "El movimiento debe quedar dentro de la semana objetivo.");
                }
                requireScheduleMutableDate(operation.date);
                if (operation.date !== occurrence.date) {
                    candidateConfig = addSlotExclusion(
                        candidateConfig,
                        occurrence.sourceGenerationSlotId,
                        occurrence.date,
                    );
                }
                candidateById.set(occurrence.id, {
                    ...occurrence,
                    date: operation.date,
                    startTime: operation.startTime,
                    endTime: operation.endTime,
                });
            });

            const finalWeek = [
                ...[...candidateById.values()].filter(({ id }) => !deletedIds.has(id)),
                ...createDrafts,
            ];
            validateLocalWeekFinalState(planItem, finalWeek);
            const candidatePlanItem = { ...planItem, generationConfig: candidateConfig };
            validatePlanItem(candidatePlanItem);

            const created = assignOccurrenceIds(
                createDrafts.map(({ id: _temporaryId, ...draft }) => draft),
            );
            const createdByTemporaryId = new Map(
                createDrafts.map((draft, index) => [draft.id, created[index]]),
            );
            const persistedWeek = finalWeek.map((occurrence) => (
                createdByTemporaryId.get(occurrence.id) ?? occurrence
            ));
            const weekIds = new Set(initialWeek.map(({ id }) => id));
            const planItemIndex = planItems.findIndex(({ id }) => id === planItemId);
            planItems[planItemIndex] = candidatePlanItem;
            occurrences = [
                ...occurrences.filter(({ id }) => !weekIds.has(id)),
                ...persistedWeek,
            ].sort(compareOccurrences);
            return {
                weekStart,
                weekEnd,
                occurrences: persistedWeek.sort(compareOccurrences).map(cloneOccurrence),
            };
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
                generationConfig: generationConfigAfterOccurrenceEdit(
                    planItem,
                    occurrence,
                    occurrenceChanges,
                ),
            });
            validatePlanItem(candidatePlanItem);
            const candidateOccurrence = {
                ...occurrence,
                date: occurrenceChanges.date,
                startTime: occurrenceChanges.startTime,
                endTime: occurrenceChanges.endTime,
            };
            validateOccurrenceDraft(candidateOccurrence);
            requireSourceSlotDateAvailable(occurrence, candidateOccurrence.date);
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
            const planItem = getPlanItemReference(occurrence.planItemId);
            if (!planItem) throw new PlannerStoreError("not_found", "El PlanItem no existe.");
            requireScheduleMutableDate(occurrence.date);
            const candidate = {
                ...occurrence,
                date: occurrenceChanges.date,
                startTime: occurrenceChanges.startTime,
                endTime: occurrenceChanges.endTime,
            };
            validateOccurrenceDraft(candidate);
            requireScheduleMutableDate(candidate.date);
            requireSourceSlotDateAvailable(occurrence, candidate.date);
            const candidatePlanItem = {
                ...planItem,
                generationConfig: generationConfigAfterOccurrenceEdit(
                    planItem,
                    occurrence,
                    candidate,
                ),
            };
            validatePlanItem(candidatePlanItem);
            const conflict = findOccurrenceConflict(candidate, occurrences, occurrence.id);
            if (conflict) {
                throw new PlannerStoreError("time_conflict", "El horario se superpone.", {
                    conflictingOccurrence: describeConflict(conflict),
                });
            }
            occurrence.date = candidate.date;
            occurrence.startTime = candidate.startTime;
            occurrence.endTime = candidate.endTime;
            const planItemIndex = planItems.findIndex(({ id }) => id === planItem.id);
            planItems[planItemIndex] = candidatePlanItem;
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
