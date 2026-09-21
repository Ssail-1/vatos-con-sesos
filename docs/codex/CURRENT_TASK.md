# CURRENT TASK

## OccurrenceSegment v1 — Segment-Aware Apply Week / Apply Future

### Objective

Make the existing recurring schedule mutation flows:

```text
Apply Week

Apply Future
```

fully compatible with the persisted OccurrenceSegment model.

The goal is NOT to make runtime segmentation recurring.

The goal is to preserve the structural meaning of each already-persisted
Occurrence while the recurring schedule itself changes.

The core rules are:

```text
SIMPLE OCCURRENCE
one segment == complete parent envelope
        ↓
may follow the recurring envelope change
        ↓
same segment identity/status
        ↓
segment becomes equal to new envelope
```

```text
CUSTOM SEGMENTED OCCURRENCE
same-duration pure move
        ↓
translate every segment by one delta
        ↓
preserve IDs / statuses / gaps / durations
```

```text
CUSTOM SEGMENTED OCCURRENCE
duration-changing recurring resize
        ↓
DO NOT scale
DO NOT trim
DO NOT reset
DO NOT guess
        ↓
reject and require explicit structural resolution
```

And critically:

```text
runtime OccurrenceSegments
ARE NOT recurring templates
```

A GenerationSlot continues to describe only the general recurring schedule.

This phase may update existing persisted occurrences and create new generated
occurrences, but newly generated occurrences still begin with:

```text
one default segment == occurrence envelope
```

unless a future explicit segment-template feature is approved.

---

# Required reading

Before changing anything, read completely:

```text
AGENTS.md

docs/codex/CURRENT_TASK.md

docs/architecture/STATUS_CONFLICT_RULES.md

docs/architecture/OCCURRENCE_SEGMENT_V1.md

docs/architecture/OCCURRENCE_SEGMENT_TECHNICAL_AUDIT.md

docs/architecture/OCCURRENCE_SEGMENT_DECISIONS.md

modules/gestor_de_habitos/docs/valores.md
```

Also inspect all existing implementation and tests for:

```text
Apply Week

Apply Future

generation configs

generation slots

generation slot weekdays/dates/exclusions

source_generation_slot_id

recurring schedule mutations

occurrence structural mutation

occurrence segment status

PlanItem creation

planner-state hydration

frontend mutation coordinators

legacy conflict preparation
```

Particularly inspect:

```text
occurrence_structure_domain.py

occurrence_structure_service.py

occurrence_segment_service.py

occurrence_segment_repository.py

plan_item_creation_service.py

planner-api.js

occurrence-mutation.js

occurrence-structure-mutation.js

app.js
```

Do not edit until the current recurring flows and their tests are understood.

---

# Authority hierarchy

Interpret requirements in this order:

```text
CURRENT_TASK.md
→ current implementation scope

OCCURRENCE_SEGMENT_DECISIONS.md
→ approved technical architecture

OCCURRENCE_SEGMENT_V1.md
→ approved segment model

STATUS_CONFLICT_RULES.md
→ approved product/domain behavior

TECHNICAL_AUDIT
→ evidence/history
```

Do not silently reinterpret approved behavior.

---

# Scope

This phase is limited to:

```text
audit existing Apply Week behavior

audit existing Apply Future behavior

make their backend writes segment-aware

make their active frontend flows consume authoritative backend behavior

preserve existing recurring semantics where compatible

transform simple occurrences safely

translate custom segmentation on pure same-duration moves

reject custom segmented recurring resize

create default segments for newly generated occurrences

segment-aware batch conflict detection for rejection only

atomic recurring schedule + occurrence + segment persistence

authoritative GET-after-success

tests

safe browser verification
```

Do NOT implement:

```text
runtime segment templates in GenerationSlot

segment inheritance across recurrence

priority conflict resolution

user-forced conflict resolution

automatic split/trim because of conflicts

conflict confirmation handshake

planner chronology redesign

pause/resume

live tracking

production timezone/jobs

new recurrence semantics unrelated to segments
```

---

# 1. Inspect working tree first

Before editing:

```text
git status --short --untracked-files=all
git diff --stat
```

The previous phase should already be committed.

Preserve all user work.

Do not revert completed OccurrenceSegment phases.

---

# 2. Database safety

Do NOT apply migration 004 to:

```text
vcs_dev
```

Do NOT query, clean or modify real development data.

Do NOT delete legacy PlanItems.

Use:

```text
isolated PostgreSQL 16
```

for actual schema-004 recurring-write verification.

Frontend/browser verification must use mocks or isolated data.

---

# 3. Migrations remain immutable

Do NOT modify:

```text
001_initial_schema.sql
002_fix_occurrence_status_context.sql
003_multi_slot_scheduling.sql
004_occurrence_segments.sql
```

If a genuine migration defect is discovered:

```text
STOP before changing it
```

and report the finding.

---

# 4. First audit the existing recurring semantics

Before implementation, determine exactly what the current code means by:

```text
Apply Week

Apply Future
```

Document internally:

```text
which occurrences each command targets

which generation config/slot rows change

whether missing occurrences are created

whether occurrences are removed/excluded

whether dates change

how source_generation_slot_id is preserved

which endpoint/service currently owns each operation

what conflict logic currently runs

what frontend coordinator invokes it
```

Do NOT redesign those semantics merely because this phase touches them.

The purpose is:

```text
make approved existing recurring behavior segment-aware
```

not:

```text
invent a new recurrence system
```

---

# 5. Existing target selection semantics remain authoritative

Preserve the already-approved meaning of:

```text
this week

future
```

including:

```text
date boundaries

GenerationSlot targeting

specific-date behavior

existing exclusions

sourceGenerationSlot relationships
```

Only change what is necessary for OccurrenceSegment compatibility.

If current implementation contains a genuine ambiguity or contradiction with
normative docs:

```text
stop in that area
report it
do not guess
```

---

# 6. No runtime segment templates

Do NOT add fields such as:

```text
generation_slot_segments

segment_template

segment_pattern

recurring_segments
```

GenerationSlot continues to store the recurring schedule envelope.

Runtime segmentation belongs to:

```text
Occurrence
```

only.

---

# 7. New generated occurrences remain simple

Any new occurrence created by Apply Week / Apply Future must start as:

```text
Occurrence envelope

└── exactly one OccurrenceSegment
    start = occurrence.start
    end   = occurrence.end
    status = valid initial status
```

Use the existing creation/domain behavior.

Do NOT copy the segment structure of another occurrence.

---

# 8. No segmentation inheritance

Example:

```text
Monday occurrence

Occurrence 13:00–17:00

Seg 1 13:00–14:00
Seg 2 16:00–17:00
```

Changing the recurring schedule must NOT cause future generated Mondays to
inherit:

```text
13:00–14:00
16:00–17:00
```

unless a future explicit recurring-segment-template feature is implemented.

This phase explicitly forbids that behavior.

---

# 9. Classify every targeted persisted occurrence

Before transforming an occurrence, classify its current structure as:

```text
SIMPLE

or

CUSTOM
```

---

# 10. Definition of SIMPLE

An occurrence is structurally simple only when:

```text
exactly one persisted segment exists
```

AND:

```text
segment.start_time == occurrence.start_time
```

AND:

```text
segment.end_time == occurrence.end_time
```

A one-segment occurrence whose child is trimmed inside the parent envelope is:

```text
CUSTOM
```

not simple.

---

# 11. Definition of CUSTOM

An occurrence is custom when ANY of these apply:

```text
more than one segment

one segment does not equal full parent envelope

runtime gaps exist

runtime trim exists

manual custom structure exists
```

Do not infer customness from number of segments alone.

---

# 12. Recurring candidate envelope

For every targeted occurrence, determine the envelope the existing recurring
operation wants to produce:

```text
old parent start/end

→

candidate parent start/end
```

Then transform segments according to the rules below.

---

# 13. SIMPLE occurrence transformation

For a SIMPLE target occurrence:

```text
old parent
08:00–09:00

S1
08:00–09:00
```

Recurring change to:

```text
10:00–11:30
```

may produce:

```text
parent
10:00–11:30

S1
10:00–11:30
```

Preserve:

```text
S1.id

S1.status

source_generation_slot_id

conflict metadata
```

The simple segment follows the new envelope.

---

# 14. SIMPLE resize is allowed

Because the simple child represents the entire parent envelope:

```text
08:00–09:00
→
10:00–11:30
```

may resize that one segment to the new envelope.

This is NOT considered scaling custom segmentation.

---

# 15. SIMPLE status remains preserved

Do NOT silently reset an existing simple occurrence status merely because its
schedule changes.

Preserve its current segment status and revalidate it against:

```text
temporal phase

completed-time integrity

other approved status rules
```

If the preserved status becomes invalid:

```text
reject the batch safely
```

Do not silently rewrite status.

---

# 16. CUSTOM same-duration move

For a CUSTOM occurrence, compare:

```text
old parent duration

candidate parent duration
```

If duration is unchanged and the requested modification is a pure envelope
translation:

```text
delta = newStart - oldStart
```

translate every child by the same delta.

---

# 17. CUSTOM move example

Before:

```text
parent
08:00–12:00

S1 08:00–09:00
S2 10:30–12:00
```

Recurring schedule moves to:

```text
13:00–17:00
```

Result:

```text
parent
13:00–17:00

S1 13:00–14:00
S2 15:30–17:00
```

Preserve:

```text
segment IDs

segment statuses

individual durations

gaps

relative positions
```

---

# 18. CUSTOM no-op

If the candidate envelope equals the old envelope:

```text
do not rewrite segment identities or structure unnecessarily
```

Preserve the graph.

---

# 19. CUSTOM duration-changing recurring resize

If:

```text
CUSTOM occurrence
```

and:

```text
candidate duration != old parent duration
```

the recurring mutation must NOT automatically modify its children.

Forbidden:

```text
scale

compress

stretch

trim

merge

reset segmentation

replace with one segment

delete children

invent new gaps
```

---

# 20. Custom resize requires explicit resolution

Reject the recurring operation with a controlled error.

Preferred code:

```text
segmented_recurring_resize_requires_resolution
```

The response should identify every affected occurrence that requires manual
structural resolution.

Conceptually:

```json
{
  "status": "error",
  "code": "segmented_recurring_resize_requires_resolution",
  "occurrences": [
    {
      "occurrenceId": "...",
      "planItemId": "...",
      "date": "2026-09-21",
      "startTime": "08:00",
      "endTime": "12:00",
      "requestedStartTime": "08:00",
      "requestedEndTime": "11:00"
    }
  ]
}
```

Exact naming may follow existing API conventions.

---

# 21. Return all incompatible custom occurrences

Do not stop after finding the first custom resize incompatibility.

Return all relevant targeted occurrences requiring explicit structural
resolution in deterministic order.

This allows future UX to explain the complete problem.

---

# 22. Reject the whole recurring command atomically

If even one targeted occurrence requires explicit resolution:

```text
DO NOT partially apply the recurring mutation
```

No:

```text
GenerationSlot update

occurrence update

segment update

creation

deletion/exclusion side effect
```

from that command may commit.

The user must resolve the incompatible structure first.

---

# 23. Why whole-command rejection

Do not leave a state where:

```text
recurring config says one schedule
```

but:

```text
some targeted occurrences were updated
and others were silently left behind
```

unless that partial behavior is already an explicit approved semantic of the
existing recurrence system.

For segment incompatibility introduced by this phase:

```text
default to atomic rejection
```

---

# 24. No silent reset

Especially forbidden:

```text
custom occurrence
→ recurring resize
→ reset to one segment
```

even if doing so would make persistence easier.

Reset is an explicit user action only.

---

# 25. No silent segment-template creation

Likewise forbidden:

```text
custom occurrence
→ extract runtime segments
→ save them into GenerationSlot
```

No segment templates in this phase.

---

# 26. Existing segment identity

When transforming an already-persisted occurrence:

```text
preserve every surviving segment ID
```

Simple resize:

```text
same one segment ID
```

Custom pure move:

```text
same N segment IDs
```

Do not replace children merely because times changed.

---

# 27. Existing segment statuses

Recurring schedule changes are structural/scheduling operations.

Do NOT reinterpret existing segment statuses.

Preserve them and revalidate.

Do not call:

```text
setOccurrenceStatus

advanceOccurrenceStatus
```

to compensate for schedule changes.

---

# 28. Aggregate recalculation

After constructing each candidate occurrence segment graph:

```text
derive_occurrence_status(final segment statuses, temporal phase)
```

Persist the resulting:

```text
Occurrence.status
```

with the segment/envelope changes.

Do not independently choose the parent aggregate.

---

# 29. Temporal validation

Reuse existing temporal-domain behavior.

Do not duplicate another matrix for:

```text
future

current_day

previous_editable_day

frozen_history
```

---

# 30. Frozen history

Apply Week / Apply Future must not structurally mutate:

```text
FROZEN_HISTORY
```

If the existing target-selection semantics already exclude frozen history,
preserve that behavior.

If a command unexpectedly includes frozen persisted occurrences:

```text
reject rather than modify them
```

Do not silently alter historical structure.

---

# 31. Yesterday transient state

If a targeted editable historical occurrence contains:

```text
pending

in_progress
```

when a structural recurring transformation requires stable history:

```text
temporal_reconciliation_required
```

Do not reconcile statuses inside the recurring mutation.

---

# 32. Completed-time integrity

If an existing segment status is:

```text
completed
```

and a recurring move/resize would place:

```text
segment.endDateTime > now
```

reject the command.

Do not silently change:

```text
completed → pending
```

---

# 33. One authoritative now

Capture one backend `now` per recurring operation.

Reuse the existing injected clock/time architecture.

Do not accept:

```text
now

today

temporalPhase
```

from public payloads.

---

# 34. Occurrence date semantics

Do NOT invent new occurrence-date movement in this phase.

Preserve whatever date-targeting behavior Apply Week / Apply Future already
have.

If the existing recurring mutation changes `occurrence_date` for persisted
occurrences:

```text
audit it explicitly
```

before adapting it.

For CUSTOM segmented occurrences, do NOT translate a runtime segmented graph
across dates unless that behavior is already explicitly supported by the
approved model.

If a custom segmented occurrence would require date movement and the model is
ambiguous:

```text
reject/report instead of guessing
```

---

# 35. Single-date invariant

No transformed segment may wrap across midnight.

Continue respecting:

```text
OccurrenceSegment v1 = one local occurrence date
```

Reject transformations that cannot fit that model.

---

# 36. Candidate graph validation

For every transformed occurrence validate:

```text
at least one segment

positive segment duration

segment bounds inside parent

sibling non-overlap

canonical ordering

status temporal validity

completed-time rule
```

Reuse:

```text
occurrence_structure_domain
```

where appropriate.

Do not create duplicate structural validation logic.

---

# 37. Reuse structural transformation helpers

Prefer reusing existing tested behavior for:

```text
translate segment set

validate candidate segment set

bounds

sibling overlap

aggregate derivation
```

Do not implement one translation algorithm for structural editor and another
unrelated translation algorithm for recurrence.

---

# 38. Recurring batch candidate set

Build the full batch candidate state before writes where practical.

Conceptually:

```text
resolve targets

lock relevant schedule rows

lock target parents

lock target segments

classify simple/custom

build all candidate structures

validate temporal rules

validate custom resize compatibility

validate conflicts

only then write
```

---

# 39. Conflict detection uses actual segments

Recurring mutations must no longer detect occupancy solely from:

```text
Occurrence.start_time

Occurrence.end_time
```

Use candidate:

```text
OccurrenceSegments
```

---

# 40. Canonical blocking statuses

Reuse the existing shared backend definition:

```text
pending

in_progress

completed

not_finished
```

Non-blocking:

```text
not_completed

cancelled
```

Do not duplicate another list.

---

# 41. Gap-aware recurring conflicts

Example candidate target:

```text
parent
08:00–12:00

segments
08:00–09:00 pending
11:00–12:00 pending
```

External blocker:

```text
09:30–10:30 pending
```

Result:

```text
NO conflict
```

The parent envelope gap is free.

---

# 42. Exclude all batch targets from persisted blocker query

When validating a recurring batch:

```text
old persisted segments of every occurrence being replaced
```

must not block their own candidate state.

Do not exclude only one target at a time if that causes another old batch
member to be seen incorrectly as an external blocker.

---

# 43. Candidate-vs-candidate conflicts

After excluding the old persisted target graphs, validate:

```text
candidate blocking segments
against
other candidate blocking segments
```

within the same recurring batch.

The batch itself must not create unresolved overlaps.

---

# 44. Candidate-vs-external conflicts

Also validate all candidate blocking segments against:

```text
persisted blocking segments
belonging to occurrences outside the batch
```

on the relevant dates.

---

# 45. Half-open interval semantics

Use:

```text
[start, end)
```

Adjacency is allowed.

Example:

```text
08:00–09:00

09:00–10:00
```

is not conflict.

---

# 46. Conflict resolution remains out of scope

If Apply Week / Apply Future would create a segment conflict:

```text
REJECT
```

Do NOT:

```text
cancel blocker

change blocker status

move blocker

split blocker

trim blocker

priority override

user-forced override
```

The segment-aware conflict engine is the next dedicated phase.

---

# 47. Do not call legacy priority override

No schema-004 recurring path may invoke the old parent-level:

```text
apply_priority_overrides()
```

or equivalent behavior.

Guard/remove it from active Apply Week/Future execution.

---

# 48. Recurring conflict error

Use a controlled segment-aware recurring conflict response.

Preferred code:

```text
recurring_schedule_conflict
```

Return blockers including:

```text
occurrenceId

segmentId

planItemId

date

startTime

endTime

status
```

If multiple blockers exist:

```text
return all relevant blockers
```

in deterministic order.

---

# 49. Conflict metadata

Because this phase only rejects unresolved conflicts, successful Apply Week /
Apply Future operations do NOT represent conflict-resolution events.

Therefore preserve:

```text
conflict_reason

source_occurrence_id

origin_reason

last_conflict_action
```

on existing occurrences.

Do not set:

```text
last_conflict_action = conflict_move
```

merely because a recurring schedule moved normally.

---

# 50. `source_generation_slot_id`

Existing occurrences must preserve valid generation provenance.

If the existing recurring rewrite deliberately replaces/rebinds GenerationSlot
identity according to already-approved semantics:

```text
preserve that existing behavior
```

but keep every occurrence correctly linked to its resulting slot.

Do not clear provenance accidentally.

---

# 51. New occurrence creation

If the existing Apply Week / Apply Future command creates an occurrence:

```text
create parent + default segment atomically
```

Use:

```text
backend-generated UUID v4
```

for the segment.

Do not create parent-only occurrences.

---

# 52. New occurrence status

Use the same initial-status rules already approved for occurrence creation.

Do not invent recurring-specific status semantics.

The parent aggregate must be derived from the created segment.

---

# 53. Missing-occurrence generation

If the existing recurring implementation fills missing occurrences:

```text
continue doing so
```

but every newly created occurrence must satisfy schema 004 immediately.

Do not depend on migration backfill for runtime writes.

---

# 54. GenerationSlot remains envelope-only

Updating a slot may change:

```text
recurring start time

recurring end time

weekday/date configuration
```

according to existing behavior.

It must NOT store:

```text
runtime segment IDs

runtime gaps

runtime child statuses

runtime segment count
```

---

# 55. Runtime customization remains local

After successful recurring mutation:

```text
custom segmentation of a translated occurrence remains custom
```

It must not disappear.

Example:

```text
before
08:00–12:00
08:00–09:00
10:30–12:00

after schedule pure move
13:00–17:00
13:00–14:00
15:30–17:00
```

The gaps survive.

---

# 56. Future newly generated instances remain simple

Even if one existing occurrence retains translated custom segmentation:

```text
future instances generated later from GenerationSlot
```

still begin with:

```text
one segment equal envelope
```

This distinction must have explicit test coverage.

---

# 57. Transactional unit

Recurring mutation must atomically coordinate, as applicable:

```text
generation config

generation slots

slot weekdays/dates/exclusions

affected occurrences

affected occurrence segments

parent aggregates
```

Do not commit recurrence configuration separately from required occurrence
segment updates.

---

# 58. Isolation level

Use:

```text
SERIALIZABLE
```

consistent with the existing recurring mutation architecture.

---

# 59. Deterministic locks

Preserve/establish deterministic ordering for:

```text
generation rows

target occurrences

target segments

external blockers
```

Avoid deadlock-prone lock-order divergence from:

```text
segment status mutation

structure mutation
```

---

# 60. Concurrency

If the schedule or target occurrence graph changes between:

```text
read

validation

commit
```

do not overwrite blindly.

Use existing serialization/concurrency handling.

Preferred controlled error may remain:

```text
concurrent_conflict
```

if already standardized.

Do not auto-retry an ambiguous batch mutation internally unless existing
transaction infrastructure already safely does so.

---

# 61. All-or-nothing segment compatibility

Before applying a recurring batch, confirm every affected persisted occurrence
can be transformed under these rules.

If one cannot:

```text
reject before commit
```

Do not transform the easy ones and leave custom incompatible ones behind
silently.

---

# 62. Apply Week backend

Make the existing Apply Week service/repository path segment-aware.

Preserve its existing definition of:

```text
week scope
```

and its recurrence configuration semantics.

For each targeted persisted occurrence:

```text
simple
→ follow new envelope

custom + same-duration pure move
→ translate segments

custom + duration resize
→ resolution required
```

New occurrences:

```text
one default segment
```

---

# 63. Apply Future backend

Make the existing Apply Future service/repository path segment-aware.

Preserve its existing definition of:

```text
future scope
```

and GenerationSlot rewrite semantics.

Use the same structural classification rules as Apply Week.

Do NOT create separate incompatible transformation behavior.

---

# 64. Shared recurring structural policy

Apply Week and Apply Future should reuse one shared policy/helper for deciding:

```text
simple follow-envelope

custom translate

custom resize reject
```

Do not duplicate the rules in two independent services.

---

# 65. No client-side structural authority

Frontend must NOT decide how every affected occurrence segment graph should
change.

Frontend expresses:

```text
Apply Week

or

Apply Future
```

Backend determines the candidate graphs.

---

# 66. Existing frontend interaction

Preserve the existing user-facing distinction between:

```text
this occurrence

Apply Week

Apply Future
```

where already present.

Do not redesign the entire recurring editor.

---

# 67. Frontend success flow

After successful Apply Week / Apply Future:

```text
command
→ GET planner-state
→ hydrate authoritative state
```

Do not reconstruct all affected segment graphs locally.

---

# 68. Confirmed command + failed GET

Use the established mutation safety pattern.

If:

```text
Apply Week/Future command succeeded
```

but:

```text
GET planner-state failed
```

retry/recovery must perform:

```text
GET only
```

Do NOT resend the recurring mutation.

---

# 69. Double-submit protection

While Apply Week / Apply Future is pending:

```text
prevent duplicate submission
```

Do not send the same batch command twice from rapid clicking.

---

# 70. Custom resize frontend error

Handle:

```text
segmented_recurring_resize_requires_resolution
```

without modifying planner state.

Explain clearly that one or more customized occurrences cannot be resized
automatically.

Do not silently reset them.

---

# 71. Resolution-required occurrence information

If the backend returns affected occurrences, display enough context for the
user to understand:

```text
which date

current range

requested range
```

A concise message/list is sufficient.

Do NOT build the final guided conflict/resolution wizard in this phase.

---

# 72. Structural resolution remains explicit

The user may later manually edit those occurrences using the structural editor
already implemented.

Do NOT automatically open/edit/save every incompatible occurrence as part of
Apply Week/Future.

Keep this first implementation simple.

---

# 73. Recurring conflict frontend behavior

For:

```text
recurring_schedule_conflict
```

frontend should:

```text
show blocker information

leave authoritative planner unchanged

not modify blockers

not invoke legacy override

not automatically retry
```

---

# 74. `temporal_reconciliation_required`

Do NOT locally reconcile statuses.

Do NOT automatically resend Apply Week / Apply Future afterward.

Use the established reconciliation/reload recovery pattern.

---

# 75. Concurrency frontend behavior

For:

```text
concurrent_conflict
```

do not automatically replay the batch.

Refresh authoritative state according to existing mutation recovery behavior.

The user must review/retry.

---

# 76. Preserve structural editor

This phase must not regress:

```text
single-occurrence structural draft editor

translate

PUT structure

reset segmentation
```

Apply Week/Future should not route through the local structural draft for every
target occurrence.

---

# 77. Preserve segment status mutation

Do not regress:

```text
PATCH /api/occurrence-segments/<id>/status
```

Recurring schedule mutation does not replace segment status mutation.

---

# 78. Preserve reconciliation bootstrap

Startup remains:

```text
POST reconcile
→ GET planner-state
→ hydrate
```

Do not change that order.

---

# 79. Legacy recurring local writes must retire

After this phase, active Apply Week and Apply Future frontend paths must NOT
perform local persisted-domain writes such as:

```text
Occurrence.status = ...

Occurrence.startTime = ...

Occurrence.endTime = ...

blocker.status = ...
```

as authoritative state.

Mutation success is followed by authoritative GET.

---

# 80. `edit_without_occurrence`

Audit how this legacy path interacts with Apply Week/Future.

If its recurring branches are the active old mechanism:

```text
remove/bypass those recurring branches
```

in favor of the segment-aware backend flow.

Do NOT necessarily remove the entire helper if another legacy conflict path
still uses it.

At completion classify what remains.

---

# 81. `commitPreparedScheduleChange`

No Apply Week/Future path may use it to perform incompatible parent-only
segment-unaware writes after this phase.

If the helper remains for the future conflict-engine migration:

```text
leave it isolated/dormant/limited
```

and report its remaining callers.

---

# 82. Legacy conflict resolution

Do NOT migrate the entire conflict engine in this phase.

If an Apply Week/Future operation encounters a conflict:

```text
new segment-aware backend detection
→ reject
```

Do not fall back to the legacy resolution mechanism.

---

# 83. Deletion/exclusion semantics

Preserve existing recurring deletion/exclusion semantics if Apply Week/Future
uses them.

Any surviving or newly created occurrence must maintain valid segments.

Do not create:

```text
zero-segment surviving occurrence
```

---

# 84. Occurrence deletion

If existing approved recurring behavior deletes an occurrence entirely:

```text
ON DELETE CASCADE
```

may remove its segments as already defined by schema 004.

Do not manually orphan/delete children outside the parent transaction.

---

# 85. Historical provenance references

Remember:

```text
source_occurrence_id
ON DELETE NO ACTION
```

If existing recurring mutation attempts to delete a referenced occurrence:

```text
preserve the current deletion restriction
```

Do not weaken historical provenance to make the batch succeed.

---

# 86. No movement lock

Conversely, a referenced source occurrence may still move when allowed.

Do not restore the old:

```text
referenced source cannot move
```

rule.

---

# 87. Pure domain tests

Add focused tests for recurring transformation classification:

```text
simple full-envelope detection

one trimmed child classified custom

multi-segment classified custom

simple resize follows envelope

simple move follows envelope

custom same-duration move translates

custom move preserves IDs

custom move preserves statuses

custom move preserves gaps

custom resize rejected
```

---

# 88. No segment inheritance test

Explicitly verify:

```text
existing occurrence has custom segmentation
```

then Apply Future changes recurring schedule / produces a new generated
occurrence.

Expected new occurrence:

```text
exactly one default segment
```

NOT the custom runtime segment set.

---

# 89. Simple recurring resize test

Persist:

```text
parent 08:00–09:00

S1 08:00–09:00 pending
```

Recurring candidate:

```text
10:00–11:30
```

Expected:

```text
same S1 ID

S1 10:00–11:30

same status
```

assuming temporal/conflict validation passes.

---

# 90. Custom pure move test

Persist:

```text
parent 08:00–12:00

S1 08:00–09:00

S2 10:30–12:00
```

Candidate:

```text
13:00–17:00
```

Verify:

```text
S1/S2 IDs unchanged

statuses unchanged

gaps unchanged

durations unchanged
```

---

# 91. Custom resize rejection test

Same custom occurrence:

```text
08:00–12:00
```

candidate:

```text
08:00–11:00
```

Expected:

```text
segmented_recurring_resize_requires_resolution
```

and:

```text
zero writes
```

to schedule/occurrences/segments.

---

# 92. Multiple custom resize test

If several targeted occurrences are incompatible:

```text
return all of them
```

deterministically.

Still:

```text
zero writes
```

---

# 93. Completed-time recurring test

Current-day completed segment translated so its end becomes future:

```text
reject
```

No status rewrite.

---

# 94. Frozen recurring test

Prove frozen occurrences are not structurally rewritten.

Follow existing target semantics:

```text
excluded if they should never be targets
```

or:

```text
controlled rejection if unexpectedly targeted
```

but never mutate them.

---

# 95. Yesterday reconciliation test

Historical editable target with transient segment:

```text
pending
or
in_progress
```

Expected:

```text
temporal_reconciliation_required
```

No silent normalization.

---

# 96. Gap-aware recurring conflict test

Candidate parent envelopes may overlap another occurrence.

If actual candidate segments do not overlap:

```text
allow
```

---

# 97. Batch self-conflict test

Two candidate occurrences in the same recurring batch become blocking and
overlap.

Expected:

```text
recurring_schedule_conflict
```

No partial writes.

---

# 98. External conflict test

Candidate segment overlaps an unaffected external blocker.

Expected:

```text
recurring_schedule_conflict
```

with actual blocker segment data.

No blocker mutation.

---

# 99. Multiple blocker test

Return all relevant blockers deterministically.

---

# 100. Non-blocking candidate test

Segments with:

```text
cancelled

not_completed
```

must not block other schedules.

Use shared blocking policy.

---

# 101. Metadata preservation test

Recurring transformations preserve:

```text
conflict_reason

source_occurrence_id

origin_reason

last_conflict_action
```

on existing occurrences.

---

# 102. `source_generation_slot_id` test

Verify existing and newly generated occurrences maintain correct generation
slot provenance after:

```text
Apply Week

Apply Future
```

---

# 103. Referenced source movement test

A source occurrence referenced by another occurrence may be translated through
an allowed recurring move.

Expected:

```text
movement succeeds if all current constraints pass

historical source link remains
```

No legacy movement lock.

---

# 104. New occurrence graph test

Every occurrence created by recurring mutation must immediately contain:

```text
1 parent

1 default segment
```

with:

```text
stable UUID

matching envelope

valid initial status

derived parent aggregate
```

---

# 105. Atomicity tests

Force failures during:

```text
GenerationSlot update

existing segment update

new occurrence insert

new segment insert

parent aggregate update
```

Verify the recurring transaction leaves no partial schedule rewrite.

---

# 106. Concurrency test

Where practical, verify concurrent Apply Week/Future or structural/status
changes cannot produce:

```text
lost segment structure

stale aggregate

partial recurrence update
```

Reuse current SERIALIZABLE/locking infrastructure.

---

# 107. Apply Week PostgreSQL round trip

Against isolated PostgreSQL 16:

```text
001 → 002 → 003 → 004
```

exercise real Apply Week behavior involving at least:

```text
simple occurrence

custom pure-move occurrence

newly generated occurrence where applicable
```

Then:

```text
GET planner-state
```

and verify authoritative segment graphs.

---

# 108. Apply Future PostgreSQL round trip

Do the equivalent real verification for Apply Future.

Verify:

```text
GenerationSlot state

existing occurrence segments

new occurrence default segments

sourceGenerationSlotId

parent aggregates
```

---

# 109. Custom resize PostgreSQL rollback

Real PostgreSQL test:

```text
Apply Week/Future includes custom segmented resize
```

Expected:

```text
controlled rejection

GenerationSlot unchanged

parents unchanged

segments unchanged
```

---

# 110. Recurring conflict PostgreSQL rollback

Real PostgreSQL test:

```text
candidate segment conflict
```

Expected:

```text
409/control error

no blocker modification

no target modification

no recurrence configuration partial write
```

---

# 111. Frontend API integration

Use the existing centralized API client.

Do not introduce direct `fetch()` calls from views.

If existing Apply Week/Future API functions already exist:

```text
adapt them
```

rather than unnecessarily duplicating them.

---

# 112. Frontend authoritative refresh

On success:

```text
Apply Week/Future
→ GET planner-state
→ hydrate
```

Verify all affected segment structures come from the backend response.

---

# 113. Selection after recurring mutation

Preserve:

```text
selectedOccurrenceId
```

if that occurrence still exists.

Preserve:

```text
selectedSegmentId
```

only if that persisted segment survives.

Clear dangling IDs.

Do not remap by array index.

---

# 114. Expansion after recurring mutation

Preserve expanded parent state where the same parent survives.

No chronology redesign.

---

# 115. Command-success / GET-failure

Test at least one recurring path:

```text
command success

GET failure
```

Then recovery:

```text
GET only
```

No repeated Apply Week/Future command.

---

# 116. Resolution-required frontend test

Mock:

```text
segmented_recurring_resize_requires_resolution
```

Verify:

```text
no local recurring write

no segment reset

no local scaling

message identifies affected occurrence(s)

no automatic retry
```

---

# 117. Recurring conflict frontend test

Mock:

```text
recurring_schedule_conflict
```

Verify:

```text
blocker context shown

no blocker mutation

no legacy conflict helper invoked

no priority confirmation invented
```

---

# 118. No runtime segment-template test

Frontend must not send:

```text
segments

segmentIds

segment templates
```

as part of GenerationSlot recurrence configuration unless the current endpoint
specifically needs occurrence-level data already approved.

Do not extend recurrence payloads with custom segment patterns.

---

# 119. Structural editor regression

Run tests proving the occurrence-local editor still supports:

```text
draft

PUT structure

translate

reset
```

without being redirected into Apply Week/Future.

---

# 120. Status regression

Run tests proving:

```text
PATCH segment status
```

still works.

---

# 121. Reconciliation regression

Run tests proving bootstrap remains:

```text
POST reconcile
→ GET planner-state
→ hydrate
```

---

# 122. PlanItem creation regression

Verify default segment creation still works independently from recurring
mutation.

---

# 123. Legacy path audit

At completion re-audit:

```text
edit_without_occurrence

commitPreparedScheduleChange

Apply Week

Apply Future

legacy parent-level schedule mutation
```

Expected after this phase:

```text
Apply Week
→ segment-aware

Apply Future
→ segment-aware
```

No active Apply Week/Future path may remain:

```text
parent-only

segment-unaware

local-authoritative
```

---

# 124. Conflict path may remain for next phase

It is acceptable if:

```text
edit_without_occurrence

commitPreparedScheduleChange
```

still have remaining callers belonging specifically to the legacy conflict
resolution workflow.

Those callers must be clearly identified.

Do not use them as fallback for recurring conflicts.

---

# 125. CORS

If Apply Week/Future routes already have correct browser CORS support:

```text
do not change it unnecessarily
```

If integration requires a minimal method/header update:

```text
make only that change
```

Preserve:

```text
VCS_ALLOWED_ORIGINS
```

No wildcard.

---

# 126. Browser verification

Use mocks / isolated backend only.

Do NOT use `vcs_dev`.

Verify existing recurring UX in:

```text
desktop 1440×900

mobile approximately 390×844
```

---

# 127. Browser — simple Apply Week/Future

Verify a normal/simple occurrence can use recurring actions and authoritative
refresh succeeds.

---

# 128. Browser — custom pure move

Mock authoritative response showing translated custom segments.

Verify:

```text
same child IDs

same gaps

new times
```

render correctly after GET.

Frontend must not calculate/persist these children itself.

---

# 129. Browser — custom resize rejection

Verify:

```text
controlled message

planner unchanged

no hidden reset

no hidden scaling
```

---

# 130. Browser — recurring conflict rejection

Verify blocker message without legacy conflict resolution actions firing.

---

# 131. Responsive behavior

Do not redesign recurring UI.

Verify no new global horizontal overflow.

---

# 132. Full frontend suite

Run:

```text
for test_file in modules/gestor_de_habitos/tests/*.test.mjs
do
  node "$test_file" || exit 1
done
```

Report:

```text
number of files

number of tests if available

result
```

---

# 133. Full backend suite

Run:

```text
.venv/bin/python -m unittest discover \
  -s modules/gestor_de_habitos/backend \
  -p 'test_*.py'
```

Report skipped tests honestly.

---

# 134. PostgreSQL 16 integration

Run the existing isolated schema-004 harness.

Verify real:

```text
001 → 004

Apply Week

Apply Future

custom translation

new default segment creation

custom resize rollback

segment conflict rollback
```

Do not use `vcs_dev`.

---

# 135. Syntax and consistency

Run:

```text
node --check
```

for every modified JS file.

Run:

```text
.venv/bin/python -m compileall -q \
  modules/gestor_de_habitos/backend
```

and:

```text
git diff --check
```

---

# 136. Still no real schema rollout

Even after this phase passes:

```text
DO NOT apply migration 004 to vcs_dev
```

The major remaining blocker is still:

```text
segment-aware conflict resolution
```

plus any legacy active write paths found by the final audit.

---

# 137. Expected architecture after this phase

Expected state:

```text
schema 004
✅

backend read
✅

frontend read/display
✅

PlanItem creation + default segment
✅

segment status
✅

persistent reconciliation
✅

frontend segment status
✅

backend structural mutations
✅

frontend structural editor
✅

Apply Week segment-aware
✅

Apply Future segment-aware
✅

runtime segment templates
❌ intentionally

segment conflict-resolution engine
❌

conflict UX
❌

planner chronology final cleanup
❌

real schema rollout
❌
```

---

# 138. Documentation

Update only necessary documentation describing:

```text
segment-aware recurring mutation behavior

simple vs custom classification

custom resize rejection

no segment-template inheritance

remaining conflict-engine incompatibility
```

Do not create speculative recurring segment-template docs.

---

# 139. Git rules

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

Do not revert user work.

---

# 140. Completion report

At completion provide:

## Files changed

List every created/modified file.

## Existing recurring behavior audit

Explain exactly what:

```text
Apply Week

Apply Future
```

currently target and mutate.

## Classification

Explain:

```text
SIMPLE

CUSTOM
```

including why one trimmed child is custom.

## Simple behavior

Explain:

```text
envelope update

segment ID preservation

status preservation

aggregate validation
```

## Custom behavior

Explain:

```text
same-duration translate

ID/status/gap preservation

duration-changing rejection
```

## New occurrences

Explain:

```text
default single segment creation

UUID generation

status/aggregate

sourceGenerationSlotId
```

## No inheritance

Explicitly confirm runtime custom segmentation is NOT copied into GenerationSlot
or future generated occurrences.

## Conflict guard

Explain:

```text
batch target exclusion

candidate-vs-candidate

candidate-vs-external

gap awareness

blocking statuses

rejection-only behavior
```

## Transactions

Explain:

```text
SERIALIZABLE

lock order

schedule + occurrence + segment atomicity
```

## Frontend integration

Explain:

```text
Apply Week

Apply Future

GET-after-success

GET-only recovery

resolution-required UX

conflict UX
```

## Legacy paths

Classify remaining:

```text
edit_without_occurrence

commitPreparedScheduleChange

other parent-only writers
```

and identify exact remaining callers.

## PostgreSQL verification

Describe actual:

```text
001 → 004

Apply Week round trip

Apply Future round trip

custom move

new occurrence

custom resize rollback

conflict rollback
```

## Tests

Give exact commands and results.

## Browser

Report desktop/mobile findings.

## Safety

Confirm:

```text
vcs_dev not queried or modified

legacy PlanItems preserved

migrations unchanged

no runtime segment templates

no priority/user-forced conflict resolution

no automatic conflict split/trim

no planner chronology redesign

no pause/resume
```

## Remaining incompatibilities

List exactly what still prevents schema 004 rollout.

## Git

Show:

```text
git diff --stat

git status --short --untracked-files=all
```

No commit.

No push.

---

# 141. Definition of done

This task is complete when:

```text
Apply Week is segment-aware

Apply Future is segment-aware

simple occurrences follow recurring envelope changes

simple segment IDs/statuses are preserved

custom occurrences translate only on same-duration pure moves

custom segment IDs/statuses/gaps/durations are preserved

custom recurring resize is rejected explicitly

no custom segmentation is silently reset

no runtime segmentation is copied into GenerationSlot

new generated occurrences receive one default segment

parent aggregates remain derived

temporal rules remain enforced

completed-time integrity remains enforced

recurring conflicts use real segments

batch self-conflicts are detected

external segment conflicts are detected

conflicts are rejected, not resolved

GenerationSlot + occurrence + segment writes are atomic

Apply Week/Future frontend uses authoritative GET after success

confirmed batch commands are not repeated after GET failure

legacy Apply Week/Future parent-only writes are retired

full frontend/backend tests pass

real PostgreSQL 16 schema-004 recurring paths are verified

vcs_dev remains untouched
```

---

# Final principle

Recurring schedule intent and runtime temporal structure are related, but they
are not the same thing.

```text
GenerationSlot
=
general recurring schedule
```

```text
Occurrence
=
one concrete generated instance
```

```text
OccurrenceSegment
=
the actual structural pieces of that concrete instance
```

Therefore:

```text
simple runtime instance
→ can follow recurring envelope changes
```

```text
custom runtime instance + pure move
→ preserve customization by translation
```

```text
custom runtime instance + resize
→ do not guess
→ require explicit structural resolution
```

And:

```text
CUSTOM RUNTIME SEGMENTATION
≠
RECURRING SEGMENT TEMPLATE
```

VCS must preserve the user's concrete history and custom structure without
silently turning it into a recurrence rule.