# CURRENT TASK

## OccurrenceSegment v1 — Frontend Read / Display Compatibility

### Objective

Adapt the planner frontend so it can understand and display the read contract
already produced by the schema-004-compatible backend:

```text
Occurrence
├── general parent envelope
├── materialized aggregate status
└── 1..N persisted OccurrenceSegments
```

This phase is:

```text
READ + DISPLAY COMPATIBILITY
```

It must NOT implement OccurrenceSegment write behavior yet.

The frontend should be able to:

```text
hydrate segments[]
preserve segment identities
display single-segment occurrences normally
display multi-segment occurrences coherently
expand/collapse segment rows
show structural duration
track occurrence + segment selection
consume conflictContext
```

without yet allowing structural segment mutations.

---

# Required reading

Before making any change, read completely:

```text
AGENTS.md

docs/codex/CURRENT_TASK.md

docs/architecture/STATUS_CONFLICT_RULES.md

docs/architecture/OCCURRENCE_SEGMENT_V1.md

docs/architecture/OCCURRENCE_SEGMENT_TECHNICAL_AUDIT.md

docs/architecture/OCCURRENCE_SEGMENT_DECISIONS.md

modules/gestor_de_habitos/docs/valores.md
```

Also inspect the current backend read contract implemented in the previous
phase.

Relevant backend files include at least:

```text
modules/gestor_de_habitos/backend/planner_state_service.py

modules/gestor_de_habitos/backend/repositories/planner_state_repository.py

modules/gestor_de_habitos/backend/test_planner_state.py
```

Read existing frontend tests before changing implementation.

---

# Authority hierarchy

Interpret requirements in this order:

```text
CURRENT_TASK.md
→ current implementation scope

OCCURRENCE_SEGMENT_DECISIONS.md
→ approved technical decisions

OCCURRENCE_SEGMENT_V1.md
→ approved model

STATUS_CONFLICT_RULES.md
→ approved product/domain behavior

TECHNICAL_AUDIT
→ evidence and alternatives
```

Do not silently change approved rules.

---

# Scope

This task is limited to:

```text
frontend API read validation
frontend hydration/cloning
frontend read model
occurrence + segment selection state
planner matrix rendering
expand/collapse behavior
segment duration display
conflictContext consumption
frontend tests
```

Do NOT implement segment write behavior.

---

# 1. Inspect working tree first

Before editing:

```text
git status --short --untracked-files=all
git diff --stat
```

Preserve all existing user changes.

Do not revert prior OccurrenceSegment work.

---

# 2. Database safety

Do NOT apply migration 004 to:

```text
vcs_dev
```

Do NOT mutate or inspect real development data merely to implement this
frontend phase.

The frontend can be verified using:

```text
fixtures
mocked planner-state responses
existing frontend test infrastructure
```

and, if useful, the already verified backend schema-004 contract.

---

# 3. No migration changes

Do NOT modify:

```text
001_initial_schema.sql
002_fix_occurrence_status_context.sql
003_multi_slot_scheduling.sql
004_occurrence_segments.sql
```

---

# 4. No backend write changes

Do NOT adapt backend runtime mutations in this task.

Out of scope:

```text
Create PlanItem segment creation

PATCH occurrence segment behavior

segment status mutation

segment create/delete

split

trim

reset segmentation

Apply Week segment writes

Apply Future segment writes

persistent reconciliation

segment-aware conflict resolution
```

---

# 5. Backend read contract to consume

The frontend must support occurrence objects conceptually shaped like:

```js
{
  id,
  planItemId,
  date,
  startTime,
  endTime,
  status,
  sourceGenerationSlotId,

  segments: [
    {
      id,
      startTime,
      endTime,
      status
    }
  ],

  conflictContext: {
    reason,
    sourceOccurrenceId
  },

  originReason,
  lastConflictAction
}
```

Optional metadata is omitted when not present.

---

# 6. `segments[]` is required in the new contract

For schema-004 planner-state:

```text
segments[]
```

is part of the occurrence model.

Do NOT fabricate segments client-side.

Do NOT create synthetic IDs.

Do NOT infer a segment from:

```text
occurrence.startTime
occurrence.endTime
occurrence.status
```

when the server omitted `segments`.

A missing segment collection in the new contract is invalid.

---

# 7. Persisted segment identity

Segment IDs come only from:

```text
backend / PostgreSQL
```

Frontend clone/hydration must preserve them exactly.

Do not derive identity from:

```text
ordinal
time
occurrence ID
array index
```

---

# 8. Frontend API validation

Update the planner-state response validation so every occurrence validates:

```text
segments is an array

segments.length >= 1

segment.id exists

segment.startTime valid

segment.endTime valid

segment.status valid
```

Continue validating parent occurrence fields.

---

# 9. Segment time validity

Validate:

```text
segment.startTime < segment.endTime
```

using the existing canonical time conventions.

Do not truncate or reinterpret invalid times.

---

# 10. Segment bounds

Frontend validation should reject a planner-state response where:

```text
segment.startTime < occurrence.startTime
```

or:

```text
segment.endTime > occurrence.endTime
```

The backend already validates these, but the frontend should not hydrate an
obviously invalid API state.

Do not turn the frontend into the authoritative validator.

---

# 11. Sibling ordering

Hydrated segments must retain deterministic chronological order equivalent to:

```text
startTime
endTime
id
```

Do not persist an ordinal.

---

# 12. Deep cloning

Update occurrence cloning so:

```text
segments[]
conflictContext
```

and other nested structures are cloned safely.

Do not share mutable segment arrays/objects across planner state snapshots.

---

# 13. Preserve parent envelope

The parent occurrence still exposes:

```text
startTime
endTime
```

These represent:

```text
general occurrence window
```

They must remain visible and must not be replaced by first/last segment
boundaries.

---

# 14. Parent status

The parent:

```text
occurrence.status
```

is the persisted materialized aggregate.

In this phase:

```text
display it
```

but do NOT recalculate it from segments as frontend authority.

A future domain phase will implement canonical aggregate derivation.

---

# 15. Single-segment occurrence UX

An occurrence with exactly one segment should remain visually close to the
existing planner experience.

Example:

```text
Estudiar
13:00 | 15:00 | 2h | pending
```

Do not force an expandable segment tree when there is only one segment.

The single persisted segment remains present in state even if not rendered as
a separate child row.

---

# 16. Multi-segment occurrence UX

An occurrence with multiple segments must render as one logical parent
occurrence.

Compact conceptual form:

```text
▸ Estudiar | 13:00 | 17:00 | 3h30 | in_progress
```

Expanded conceptual form:

```text
▾ Estudiar | 13:00 | 17:00 | 3h30 | in_progress

    Seg 1 | 13:00 | 14:00 | 1h   | completed
    Seg 2 | 14:30 | 16:00 | 1h30 | completed
    Seg 3 | 16:00 | 17:00 | 1h   | pending
```

Exact visual styling should follow the existing VCS identity.

Do not redesign unrelated planner UI.

---

# 17. Expand / collapse

Only the logical parent row owns:

```text
expand
collapse
```

control.

Segments must not contain nested expand controls.

Suggested semantics:

```text
▸ collapsed

▾ expanded
```

Use accessible controls consistent with existing frontend practices.

---

# 18. Expansion state

Expansion/collapse state is:

```text
UI state
```

not domain persistence.

Do NOT save it to PostgreSQL.

It may reset after page reload unless existing frontend architecture provides a
natural transient-state mechanism.

Do not overengineer persistence for it.

---

# 19. Duration

Occurrence display duration must now be:

```text
SUM(segment duration)
```

for all segments.

Do NOT calculate:

```text
occurrence.endTime - occurrence.startTime
```

for displayed structural duration when multiple segments exist.

---

# 20. Duration includes every segment

For v1 structural duration, include segments regardless of status:

```text
pending
in_progress
completed
not_completed
not_finished
cancelled
```

Example:

```text
13:00–14:00
14:30–15:30
16:00–17:00

duration = 3h
```

This is not yet a productivity metric.

---

# 21. Parent start/final columns

The main occurrence row continues to show:

```text
Inicio = occurrence.startTime

Final = occurrence.endTime
```

These remain the general envelope.

Child segment rows show their own:

```text
Inicio
Final
Duración
Status
```

---

# 22. Segment row label

Segment numbering is derived only for display.

Conceptually:

```text
Seg 1
Seg 2
Seg 3
```

based on chronological order.

Do not store or mutate segment identity through this number.

---

# 23. Chronological placement

When expanded, segment rows should preserve understandable temporal ordering.

If another occurrence exists temporally between two segments of an expanded
occurrence, do not design the renderer in a way that falsely implies the
parent occupies that gap continuously.

Prefer the existing planner chronology where possible.

If the current row architecture makes exact interleaving impossible without a
large redesign:

```text
document the limitation
```

rather than expanding scope silently.

---

# 24. Selection state

Frontend state must evolve conceptually toward:

```text
selectedOccurrenceId

selectedSegmentId
```

Do not use only:

```text
selectedPlanItemId
```

to represent planner row selection.

---

# 25. Selecting an occurrence

Selecting a parent occurrence should set:

```text
selectedOccurrenceId = occurrence.id
```

and may use:

```text
selectedSegmentId = null
```

when no specific child is selected.

---

# 26. Selecting a segment

Selecting a segment should produce:

```text
selectedOccurrenceId = parent occurrence.id

selectedSegmentId = segment.id
```

Visual result:

```text
whole occurrence group is selected

specific segment receives stronger emphasis
```

Do not treat a segment as a separate PlanItem or separate Occurrence.

---

# 27. Selection stability

Selection must use stable IDs.

Do not store:

```text
selected segment index
```

because chronological edits in later phases may change the displayed ordinal.

---

# 28. `conflictContext`

Frontend must migrate read consumers toward:

```text
conflictContext
```

as the canonical API field.

Recognized reasons:

```text
priority_override
user_forced_override
```

Do not apply the old assumption that conflict metadata only exists for:

```text
cancelled
not_finished
```

---

# 29. `statusContext`

The backend currently emits a temporary:

```text
statusContext
```

alias for legacy `priority_override` consumers.

This frontend phase should migrate relevant frontend reads/tests to:

```text
conflictContext
```

Do not create new dependencies on `statusContext`.

If removing all current frontend use is possible within this read/display
scope:

```text
remove the frontend dependency
```

The backend alias itself may remain until a later cleanup phase.

Do not modify backend merely to remove the alias in this task.

---

# 30. `originReason`

Hydrate and preserve:

```text
originReason
```

when supplied.

Current known value:

```text
conflict_insertion
```

This phase does not need to add prominent UI for it unless existing UI has a
natural metadata location.

Primary requirement:

```text
do not discard it during hydration/cloning
```

---

# 31. `lastConflictAction`

Hydrate and preserve:

```text
lastConflictAction
```

Known values:

```text
conflict_insertion
conflict_move
```

Do not derive or invent values.

Prominent UI is not required in this phase unless naturally justified.

---

# 32. `sourceGenerationSlotId`

Continue preserving:

```text
sourceGenerationSlotId
```

with no behavioral change.

---

# 33. Status controls — critical restriction

This phase does NOT implement segment status writes.

For a multi-segment occurrence, do NOT allow an existing parent-level status
control to silently execute:

```text
occurrence.status = ...
```

as if the parent were still the editable status unit.

That would violate the new domain.

---

# 34. Single-segment legacy status control

Do not expand this phase into backend write compatibility merely to preserve
status controls.

If the existing status control can remain present without exercising new
schema-004 writes during tests, preserve its visual behavior where reasonable.

If necessary for correctness:

```text
disable or guard ambiguous write actions
```

in the schema-004/multi-segment presentation.

Document any temporary disabled behavior.

Do NOT invent segment mutation behavior.

---

# 35. Structural editing is out of scope

Do NOT implement UI actions for:

```text
Add segment

Delete segment

Split

Trim

Resize

Reset segmentation

Pause

Resume
```

in this phase.

---

# 36. Conflict resolution UI is out of scope

Do NOT implement yet:

```text
Ajustar

Segmentar y continuar

Finalizar y continuar

Cancelar y continuar

Confirmar corrección

user_forced_override confirmation
```

This phase only understands and displays already persisted data.

---

# 37. Reconciliation remains out of scope

Do NOT modify frontend reconciliation logic into the new final architecture
yet.

Do NOT create the backend reconciliation endpoint.

If existing frontend reconciliation conflicts with the new read-only display
tests:

```text
isolate/guard it minimally
```

and document the limitation.

Do not redesign reconciliation in this task.

---

# 38. Existing monthly aggregate

Preserve:

```text
deriveAggregateOccurrenceDisplay(...)
```

which aggregates multiple occurrences of the same PlanItem/day.

Do NOT replace it with the internal segment aggregate concept.

These are different operations:

```text
Occurrence.status
→ aggregate of one occurrence's segments

monthly aggregate display
→ aggregate across multiple occurrences
```

Keep names/tests conceptually distinct.

---

# 39. Planner matrix impact

Inspect and adapt at least the actual code paths around:

```text
js/views/planner-matrix.js

js/state/planner-store.js

js/api/planner-api.js

js/app.js
```

and any related rendering/selection modules.

Do not assume these are the only files.

Follow actual dependencies.

---

# 40. Existing styling

Preserve VCS visual identity:

```text
dark
gold accents
current responsive behavior
```

Do not perform unrelated CSS redesign.

Add only the styling necessary for:

```text
expanded parent grouping
segment indentation
selection distinction
expand/collapse affordance
```

---

# 41. Accessibility

Expand/collapse controls should expose understandable state where practical,
for example:

```text
aria-expanded
button semantics
```

Do not make segment interaction depend only on color.

---

# 42. Mobile behavior

The expanded multi-segment representation must not destroy existing mobile
layout.

Segments may stack naturally using the existing responsive system.

Do not implement future fullscreen activity tracking.

---

# 43. Frontend tests

Add/update focused tests for at least:

```text
API validation with segments[]

single-segment hydrate

multi-segment hydrate

deep clone independence

stable segment IDs

deterministic segment ordering

segment bounds rejection

single-segment rendering

multi-segment collapsed rendering

multi-segment expanded rendering

expand/collapse

duration = sum of segments

parent general start/end preserved

derived Seg 1 / Seg 2 labels

selectedOccurrenceId

selectedSegmentId

segment selection highlights parent group

conflictContext priority_override

conflictContext user_forced_override

originReason preservation

lastConflictAction preservation

sourceGenerationSlotId preservation

monthly aggregate behavior remains conceptually separate
```

---

# 44. Invalid input tests

Verify frontend rejects or safely handles:

```text
segments missing

segments empty

duplicate segment IDs

invalid segment status

start >= end

segment outside parent envelope
```

Do not fabricate recovery data.

---

# 45. Existing frontend tests

Run existing frontend suites relevant to:

```text
planner store

planner bootstrap

planner matrix

occurrence-aware rendering

monthly aggregate

API validation

selection

priority/conflict display
```

Update expectations only when the approved contract changed.

Do not rewrite unrelated tests.

---

# 46. Backend tests

Because backend runtime is not the implementation target:

```text
do not modify backend merely to satisfy frontend tests
```

Still run the existing backend suite as a regression check if practical.

Report skips honestly.

---

# 47. No real schema rollout yet

At completion:

```text
vcs_dev remains schema 003
```

unless explicitly changed by the user outside this task.

Do NOT apply 004.

Do not claim end-to-end local runtime against real `vcs_dev` is ready yet.

---

# 48. Known transitional architecture

At the end of this phase the expected state is:

```text
schema 004
→ designed and tested

backend schema-004 reads
→ implemented and tested

frontend schema-004 reads/display
→ implemented and tested

schema-004 runtime writes
→ NOT implemented yet
```

This is intentional.

---

# 49. Git rules

The user controls Git.

Do NOT:

```text
commit
push
merge
rebase
switch branch
create branch
```

Do not revert existing user work.

---

# 50. Completion report

At completion provide:

## Files changed

List every created/modified file.

## Frontend model

Explain:

```text
how segments are validated
how they are hydrated
how they are cloned
how they are ordered
```

## Rendering

Explain:

```text
single-segment behavior

multi-segment parent row

expanded child rows

duration calculation

expand/collapse
```

## Selection

Explain:

```text
selectedOccurrenceId

selectedSegmentId

visual grouping
```

## Conflict metadata

Confirm frontend canonical usage of:

```text
conflictContext
```

and state whether any frontend dependency on:

```text
statusContext
```

remains.

## Write safety

Explain what controls were:

```text
preserved
guarded
disabled
```

to avoid parent-level writes against multi-segment occurrences.

## Tests

Show exact commands and results.

## Safety

Confirm:

```text
vcs_dev not modified

migrations unchanged

backend write behavior unchanged

no segment mutations implemented

no reconciliation implemented

no conflict engine implemented

Apply Week/Future not made segment-aware
```

## Remaining incompatibilities

List what still prevents schema 004 from becoming the active real runtime
database.

## Git

Show:

```text
git diff --stat

git status --short --untracked-files=all
```

No commit.

No push.

---

# 51. Definition of done

This task is complete when:

```text
frontend understands persisted segments[]

single-segment occurrences remain visually simple

multi-segment occurrences can be expanded/collapsed

segments render as temporal child rows

parent envelope remains visible

display duration sums segment durations

selection distinguishes occurrence and segment

segment IDs remain stable/persisted

conflictContext is the canonical frontend read field

originReason and lastConflictAction survive hydration

monthly aggregate remains a separate concept

multi-segment parent-level writes are not silently allowed

frontend tests pass

vcs_dev remains untouched

no write-side OccurrenceSegment implementation was added
```

---

# Final principle

This phase teaches the frontend to:

```text
understand
select
and display
```

OccurrenceSegments.

It does NOT yet teach the application to:

```text
create
edit
split
trim
delete
reconcile
or resolve conflicts
```

between them.

Desired transition:

```text
schema 004
        ↓
backend reads segments
        ↓
frontend understands + displays segments
        ↓
STOP
```
