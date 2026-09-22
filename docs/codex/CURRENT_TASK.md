# CURRENT TASK

## OccurrenceSegment v1 — Segment-Aware Conflict Engine

### Objective

Replace the remaining legacy parent-level conflict-resolution model with an
authoritative backend engine based on:

```text
OccurrenceSegment vs OccurrenceSegment
```

The engine must:

```text
detect
→ explain
→ require explicit confirmation
→ revalidate
→ resolve
→ persist atomically
```

It must never silently rewrite another occurrence because of priority.

The primary flow is:

```text
SOURCE mutation
        ↓
candidate source segments
        ↓
segment conflict detection
        ↓
409 resolution required
        ↓
user explicitly confirms exact blocker snapshot
        ↓
same mutation retried with confirmation
        ↓
backend locks + revalidates blocker
        ↓
build target resolution
        ↓
source + affected targets committed atomically
```

This phase is BACKEND-FIRST.

Do NOT implement the final conflict UX yet.

---

# Required reading

Before changing anything, read completely:

```text
AGENTS.md

docs/codex/CURRENT_TASK.md

docs/architecture/STATUS_CONFLICT_RULES.md

docs/architecture/OCCURRENCE_SEGMENT_V1.md

docs/architecture/OCCURRENCE_SEGMENT_DECISIONS.md

docs/architecture/OCCURRENCE_SEGMENT_TECHNICAL_AUDIT.md

modules/gestor_de_habitos/docs/valores.md
```

Also inspect all completed OccurrenceSegment implementation, especially:

```text
occurrence_segment_domain.py

occurrence_segment_service.py

occurrence_structure_domain.py

occurrence_structure_service.py

recurring_segment_policy.py

recurring_segment_service.py

scheduling_policy.py

plan_item_creation_service.py

week_mutation_service.py

future_schedule_service.py

repositories/

app.py
```

Audit the remaining legacy conflict code:

```text
edit_without_occurrence

prepareOccurrenceAddition

commitPreparedScheduleChange

commitPreparedChange

apply_priority_overrides

status_context / status_reason legacy code

legacy priority confirmation
```

Read relevant tests before implementation.

---

# Authority hierarchy

Interpret requirements in this order:

```text
CURRENT_TASK.md
→ current implementation scope

STATUS_CONFLICT_RULES.md
→ product conflict behavior

OCCURRENCE_SEGMENT_DECISIONS.md
→ approved technical decisions

OCCURRENCE_SEGMENT_V1.md
→ segment model

TECHNICAL_AUDIT
→ evidence/history
```

If the exact outcome for a blocker status is already defined in the normative
documents:

```text
follow it exactly
```

Do NOT invent an alternative.

If a blocker-status case required for this phase is genuinely not defined:

```text
STOP that branch
report the ambiguity
do not guess
```

---

# Scope

This task is limited to:

```text
segment conflict domain

single-source conflict planning

blocker snapshot confirmation protocol

priority/user-forced authorization classification

segment subtraction

trim

split

full-overlap status outcome

aggregate recalculation

conflict provenance metadata

atomic source + target persistence

PlanItem creation conflict integration

single-occurrence structural conflict integration

legacy backend override retirement/guarding

PostgreSQL 16 tests
```

This task does NOT implement:

```text
final frontend conflict UX

recurring conflict resolution

Apply Week/Future blocker modification

segment-status conflict resolution

global schedule shifting

planner chronology redesign

production rollout

pause/resume

live tracking

event log
```

Apply Week/Future remain:

```text
segment-aware detection + rejection
```

for this phase.

Segment status activation remains:

```text
segment-aware detection + rejection
```

for this phase.

---

# 1. Inspect working tree

Before editing:

```text
git status --short --untracked-files=all
git diff --stat
git diff --check
```

The previous phase should already be committed.

Preserve user work.

---

# 2. Database safety

Do NOT apply migration 004 to:

```text
vcs_dev
```

Do NOT query, clean or modify `vcs_dev`.

Do NOT delete legacy PlanItems.

Use isolated PostgreSQL 16 for real schema-004 verification.

---

# 3. Migrations remain immutable

Do NOT modify:

```text
001_initial_schema.sql
002_fix_occurrence_status_context.sql
003_multi_slot_scheduling.sql
004_occurrence_segments.sql
```

If a real migration defect is found:

```text
STOP before changing it
```

and report it.

---

# 4. Core conflict model

The current blocking statuses are:

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

Reuse the existing shared backend authority.

Do NOT create another status list.

---

# 5. Conflicts are segment-vs-segment

Conflict detection must use:

```text
source candidate OccurrenceSegments
vs
persisted target OccurrenceSegments
```

Do NOT use parent envelopes as occupation.

---

# 6. Half-open intervals

Use:

```text
[start, end)
```

Therefore:

```text
08:00–09:00
09:00–10:00
```

is adjacency, not conflict.

---

# 7. Parent gaps remain free

Example:

```text
Target parent
08:00–12:00

Target segments:
08:00–09:00
11:00–12:00
```

Source:

```text
09:30–10:30
```

Expected:

```text
NO conflict
```

The parent envelope is not continuous occupation.

---

# 8. Single-source engine

The resolution engine in this phase resolves conflicts produced by:

```text
one logical source occurrence
```

against one or more target occurrences.

This includes:

```text
new occurrence insertion

existing occurrence structural move/change
```

Do NOT generalize this phase into a multi-source recurring-resolution engine.

Apply Week/Future continue to reject conflicts.

---

# 9. Source action type

Every resolvable operation must explicitly identify the source action as:

```text
conflict_insertion
```

or:

```text
conflict_move
```

Use:

```text
conflict_insertion
```

for a newly created source occurrence.

Use:

```text
conflict_move
```

for an already-persisted occurrence whose structural position/change causes
the conflict.

Do not infer an event log.

---

# 10. First request never modifies blockers

When an unconfirmed source mutation encounters blockers:

```text
return controlled 409
```

and perform:

```text
ZERO blocker modifications
```

No implicit priority behavior.

---

# 11. Preferred first-response code

Use a canonical code such as:

```text
segment_conflict_resolution_required
```

unless an already-approved API convention requires a closely equivalent name.

Use the same conflict contract across integrated single-source mutation paths.

---

# 12. Conflict response

Each conflict response must expose the concrete blocker segment.

Conceptually:

```json
{
  "status": "error",
  "code": "segment_conflict_resolution_required",
  "message": "La operación requiere resolver conflictos de horario.",
  "conflicts": [
    {
      "blocker": {
        "occurrenceId": "<uuid>",
        "segmentId": "<uuid>",
        "planItemId": "<uuid>",
        "date": "2026-09-21",
        "startTime": "13:00",
        "endTime": "15:00",
        "status": "pending"
      },
      "requiredAuthorization": "priority_override",
      "resolutionKind": "<normative-resolution-kind>",
      "requiresRealizedTimeConfirmation": false
    }
  ]
}
```

Exact envelope may follow current API conventions.

---

# 13. Blocker snapshot contract

The approved confirmation granularity is the concrete blocker segment:

```text
occurrenceId

segmentId

startTime

endTime

status
```

Date and PlanItem ID may also be returned for UX, but confirmation validity
must bind at least to the approved concrete segment snapshot.

Do NOT confirm merely:

```text
occurrenceId
```

because one occurrence may contain multiple segments.

---

# 14. Confirmation is stateless

Do NOT store pending conflict confirmations in:

```text
memory

session

temporary DB tables

server cache
```

The client retries the original mutation with explicit confirmations.

Backend re-derives and revalidates everything.

---

# 15. Confirmation payload

Use one explicit optional object in the mutation request, conceptually:

```json
{
  "conflictResolution": {
    "confirmations": [
      {
        "blocker": {
          "occurrenceId": "<uuid>",
          "segmentId": "<uuid>",
          "startTime": "13:00",
          "endTime": "15:00",
          "status": "pending"
        },
        "confirmed": true
      }
    ]
  }
}
```

For blockers requiring stronger realized-time confirmation, include the
smallest explicit additional acknowledgement consistent with the normative
rules.

Do NOT reuse the old:

```text
confirmedOccurrenceIds
```

contract as the new source of authority.

---

# 16. Do not trust client authorization claims

The backend computes:

```text
priority_override
```

or:

```text
user_forced_override
```

from current persisted priorities.

The client does NOT decide which conflict reason applies.

If the payload contains an authorization label for display/echo purposes:

```text
recompute and verify it
```

Do not trust it.

---

# 17. Priority authorization

Canonical rule:

```text
source.priority > target.priority
→ priority_override
```

Otherwise:

```text
source.priority <= target.priority
→ user_forced_override
```

Even when the source has higher priority:

```text
explicit user awareness/confirmation is still required
```

Priority does NOT silently modify another occurrence.

---

# 18. Realized-time protection

Segments with:

```text
completed
not_finished
```

represent realized/historical time.

They must NEVER be silently rewritten merely because:

```text
source priority is higher
```

Use the stronger explicit confirmation required by the normative conflict
rules.

If the required target date is frozen:

```text
do not rewrite frozen history
```

Return a controlled resolution-unavailable/frozen error.

Do not bypass history immutability.

---

# 19. `in_progress`

`in_progress` conflict handling must follow the exact rule defined in:

```text
STATUS_CONFLICT_RULES.md
```

This phase is where that nuanced rule becomes executable.

Do NOT treat:

```text
in_progress == pending
```

unless the normative rule explicitly says so.

Do NOT silently convert it.

---

# 20. Non-blocking statuses

Do not produce a conflict for:

```text
cancelled

not_completed
```

No confirmation is required merely because time ranges overlap them.

---

# 21. Resolution planner

Create a pure domain layer that transforms:

```text
target segment

minus

source occupied interval(s)
```

into the approved final result.

It must not query:

```text
Flask

PostgreSQL

wall clock
```

except through explicit inputs.

---

# 22. Conflict subtraction

Canonical structural rule:

```text
affected target segment
-
source occupied interval
=
surviving fragments
```

Possible structural outcomes:

```text
0 fragments

1 fragment

2 fragments
```

---

# 23. One surviving fragment

For one surviving fragment:

```text
trim the existing target segment
```

Preserve:

```text
original segment ID
```

unless a normative status-specific rule explicitly requires a different
outcome.

---

# 24. Two surviving fragments

For two surviving fragments:

```text
split within the SAME logical target occurrence
```

Preferred identity rule:

```text
left/earlier fragment
→ keeps original segment ID

right/later fragment
→ new backend UUID v4
```

Preserve appropriate status according to the normative conflict rules.

---

# 25. Zero surviving fragments

Never create:

```text
zero-duration segment
```

For full coverage:

```text
apply the normative status outcome
```

defined by `STATUS_CONFLICT_RULES.md`.

Do not invent an empty fragment.

Do not leave an occurrence with an invalid zero-segment graph.

---

# 26. At least one segment

Every surviving occurrence must still have:

```text
1..N OccurrenceSegments
```

If the full-overlap rule changes status rather than structure:

```text
preserve a valid segment according to the normative outcome
```

If normative documentation defines another exact strategy:

```text
follow it
```

Do not improvise.

---

# 27. Repeated segmentation

The engine must support already-segmented targets.

Example:

```text
Target occurrence

S1
08:00–09:00

S2
10:00–12:00
```

A later confirmed conflict may further trim/split:

```text
S2
```

Repeated conflict resolution is valid.

Do not assume:

```text
target originally had one segment
```

---

# 28. Multiple source segments

A custom source occurrence may itself contain:

```text
multiple blocking segments
```

Resolution must consider every occupied source interval.

Do not treat the source parent envelope as occupation.

---

# 29. Deterministic subtraction

When multiple source intervals affect one target:

```text
sort/process deterministically
```

The final target graph must not depend on incidental query ordering.

Existing original ID should remain attached to the earliest surviving fragment
where the approved identity rule allows it.

New fragments receive independent backend UUIDs.

---

# 30. Candidate target graph validation

After resolution, every affected target occurrence must satisfy:

```text
at least one segment

positive duration

inside parent envelope or approved updated envelope

sibling non-overlap

canonical ordering

valid statuses

temporal integrity
```

Reuse the existing structural/domain validators.

Do not create a parallel validator.

---

# 31. Target parent envelope

Do NOT automatically shrink the target occurrence general envelope merely
because its runtime segments were trimmed/split.

Recall:

```text
Occurrence.start/end
=
general/planned envelope
```

Segments may leave gaps inside it.

Unless normative documentation explicitly requires an envelope change for a
specific resolution:

```text
preserve parent envelope
```

---

# 32. Structural duration

Conflict segmentation does not change the duration definition:

```text
sum of ALL final segment durations
```

regardless of status.

No realized analytics in this phase.

---

# 33. Aggregate recalculation

After target segment resolution:

```text
derive_occurrence_status(
    all final target segments,
    target temporal phase
)
```

Persist the target parent aggregate in the same transaction.

Never manually choose the target parent status.

---

# 34. Source aggregate

The source occurrence also remains governed by:

```text
derive_occurrence_status(...)
```

Do not mutate its parent status independently.

---

# 35. Temporal phase

Use explicit:

```text
future

current_day

previous_editable_day

frozen_history
```

Do not use ambiguous historical booleans.

---

# 36. One authoritative `now`

Capture one backend `now` for the operation.

Use it consistently for:

```text
source validation

target temporal phase

completed-time validation

historical protection
```

Do not accept clock values from public requests.

---

# 37. Conflict metadata — target

When a confirmed conflict modifies the TARGET occurrence's:

```text
segment status

or

temporal structure
```

persist:

```text
conflict_reason
=
priority_override
or
user_forced_override
```

and:

```text
source_occurrence_id
=
current source occurrence ID
```

The latest confirmed modifying conflict wins.

---

# 38. Historical conflict context does not auto-clear

Later source movement or cancellation does NOT automatically clear:

```text
target.conflict_reason

target.source_occurrence_id
```

Those fields describe historical context.

Current blockers are always derived from current segment graph/status.

---

# 39. Source creation metadata

If a newly created occurrence successfully causes confirmed modifications to
another occurrence:

```text
source.origin_reason = conflict_insertion
```

and use the approved insertion conflict-action metadata.

Normal creation with no blocker modification keeps:

```text
origin_reason = NULL
```

`origin_reason` never changes after birth.

---

# 40. Existing source move metadata

If an already-existing source occurrence is structurally moved/changed and
confirmed resolution modifies another occurrence:

```text
preserve source.origin_reason
```

and record the approved:

```text
conflict_move
```

action metadata.

Do not rewrite its origin.

---

# 41. `last_conflict_action`

Follow the exact placement/semantics already documented in
`OCCURRENCE_SEGMENT_V1` / `DECISIONS`.

At minimum preserve the approved values:

```text
conflict_insertion

conflict_move
```

Do NOT invent:

```text
conflict_status_activation

conflict_week

conflict_future
```

in this phase.

---

# 42. Metadata is not an event log

Do NOT add:

```text
conflict history table

conflict count

conflictSources[]

event stream
```

The current model records latest relevant context only.

---

# 43. Latest conflict wins

If a target was previously modified by another conflict and a new confirmed
source modifies it again:

```text
conflict_reason

source_occurrence_id
```

must describe the NEW latest conflict.

Do not preserve the first cause as if it were permanent genealogy.

---

# 44. Source delete policy

Preserve:

```text
source_occurrence_id
ON DELETE NO ACTION
```

A referenced source still cannot be deleted.

Do not weaken provenance.

---

# 45. Source movement

Do NOT reintroduce:

```text
referenced source cannot move
```

A referenced source may move.

Historical target metadata remains valid historical context.

---

# 46. Snapshot revalidation

On confirmation retry:

```text
lock blocker rows
```

and compare the current blocker to the submitted snapshot.

At minimum verify exact:

```text
occurrenceId

segmentId

startTime

endTime

status
```

---

# 47. Changed blocker invalidates confirmation

If a blocker changed between:

```text
first 409
```

and:

```text
confirmation retry
```

the prior authorization is invalid.

Do NOT apply it to the changed segment.

Return a controlled stale/fresh-conflict response.

Preferred code:

```text
conflict_resolution_stale
```

or an equivalent explicit code.

---

# 48. Removed blocker

If a previously confirmed blocker disappeared or became materially different
before confirmation:

```text
do not blindly reuse old authorization
```

Treat the prior snapshot as stale.

Re-evaluate the operation.

No silent destructive action based on obsolete confirmation.

---

# 49. New blocker

If a new blocker appears before confirmation:

```text
do not modify it without explicit confirmation
```

Return the fresh conflict set.

---

# 50. Missing confirmation

If a current blocker requiring resolution has no matching confirmation:

```text
return resolution required
```

No partial resolution.

---

# 51. Extra/invalid confirmations

Reject malformed or duplicate confirmation entries.

Do not allow a confirmation for:

```text
one segment
```

to authorize:

```text
another segment
```

---

# 52. Strong confirmation

If the normative rules require stronger acknowledgement for:

```text
completed

not_finished
```

that acknowledgement must also be bound to the exact blocker snapshot.

Do not treat a generic:

```text
"yes"
```

from an earlier state as authorization for changed realized time.

---

# 53. Atomic operation

A confirmed source mutation and every affected target mutation must commit:

```text
together
```

or:

```text
not at all
```

No:

```text
source saved

target resolution failed
```

state may survive.

---

# 54. Transaction isolation

Use:

```text
SERIALIZABLE
```

consistent with current write architecture.

---

# 55. Deterministic locks

Establish one lock order consistent with existing services.

Conceptually:

```text
1. source parent when persisted
2. source segments when persisted
3. target parents ordered deterministically
4. target blocker segments ordered deterministically
5. remaining target siblings needed for final graph
6. validate
7. write
```

For a new source, generate required IDs/candidate graph without exposing
partial persistence.

Avoid deadlock-prone ordering divergence.

---

# 56. Source candidate validation first

Before modifying targets, validate the source candidate itself:

```text
valid temporal phase

valid statuses

valid structure

completed-time

no sibling overlap

bounds
```

Do not resolve blockers for an invalid source mutation.

---

# 57. Blocker discovery and locking

Do not rely on an unlocked conflict list from a prior request.

On confirmation:

```text
discover/lock authoritative blockers again
```

under the current transaction.

---

# 58. No global schedule shift

Forbidden:

```text
move every later occurrence

push schedule forward

cascade offsets globally
```

Conflict resolution modifies only the specifically affected target structures
according to approved rules.

---

# 59. PlanItem creation integration

Replace the old PlanItem creation conflict override behavior with the new
segment-aware protocol.

First request:

```text
detect real segment blockers
→ 409 resolution required
→ zero target writes
```

Confirmed request:

```text
revalidate
→ resolve target segments
→ create source PlanItem/occurrence/segment graph
→ write metadata
→ commit atomically
```

---

# 60. No legacy PlanItem override

The schema-004 PlanItem creation path must never call:

```text
apply_priority_overrides()
```

or legacy parent-level equivalent.

The temporary guard introduced in earlier phases can be replaced by the new
engine only when the new engine is valid.

Do not reopen the old mutation path.

---

# 61. New source IDs

When conflict metadata needs:

```text
source_occurrence_id
```

for a newly created source:

```text
generate the final source occurrence ID inside the authoritative operation
```

and use that same ID for:

```text
source persistence

target.source_occurrence_id
```

Do not write a temporary/fake source ID.

---

# 62. Structural mutation integration

Integrate the new engine into single-occurrence structural mutations:

```text
translate

replace structure

reset segmentation
```

when they produce blocking conflicts.

Unconfirmed:

```text
409 resolution required
```

Confirmed:

```text
revalidate
resolve blockers
persist source structure
persist target structures
commit
```

---

# 63. Structural target draft remains source-only

The source structural command continues to describe:

```text
the source occurrence candidate
```

Conflict resolution modifies blocker targets in backend domain logic.

Do not require the source structural payload to include manually edited target
graphs.

---

# 64. `conflict_move`

A confirmed structural mutation of an existing source that modifies blockers
uses:

```text
conflict_move
```

for the approved source conflict-action metadata.

A normal structural change with no blocker modifications does NOT.

---

# 65. Reset conflict

Reset segmentation may also produce a conflict.

It follows the same confirmation/revalidation engine.

Do not create a separate reset-specific override model.

---

# 66. Segment-status mutation remains rejection-only

Do NOT make:

```text
PATCH /api/occurrence-segments/<id>/status
```

modify blocker structures in this phase.

It continues to return:

```text
segment_status_conflict
```

when activation overlaps blockers.

Reason:

```text
the approved conflict-action metadata currently models insertion/move
```

and status-activation conflict semantics are not being expanded here.

---

# 67. Apply Week/Future remain rejection-only

Do NOT make recurring batch conflicts destructive in this phase.

They continue to return:

```text
recurring_schedule_conflict
```

with blockers.

The recurring segment-aware work from 05.7.5.9 must remain intact.

---

# 68. Ad-hoc occurrence addition audit

Audit:

```text
edit_without_occurrence

prepareOccurrenceAddition

commitPreparedScheduleChange
```

Determine which backend mutation should eventually own ad-hoc occurrence
insertion conflict resolution.

Do NOT preserve a local parent-status conflict writer merely because it already
exists.

If safely integrating the backend engine requires frontend UX work reserved for
05.7.5.11:

```text
keep that legacy frontend path guarded
```

and report it precisely.

Do not silently expand the UI scope.

---

# 69. Legacy backend override retirement

After the new engine is integrated, no active schema-004 backend insertion or
single-occurrence move path may perform:

```text
pending parent → cancelled

in_progress parent → not_finished

status_reason write

parent-envelope split logic
```

through the old override implementation.

Old helpers may remain physically only if completely unreachable and clearly
documented for later cleanup.

Prefer removing dead code when safe.

---

# 70. `status_reason`

Do not reintroduce:

```text
status_reason
```

Schema-004 writes use:

```text
conflict_reason
```

according to the new model.

---

# 71. `statusContext`

Do not reintroduce frontend/backend dependency on:

```text
statusContext
```

The canonical read model remains:

```text
conflictContext
```

---

# 72. Pure domain tests — authorization

Test:

```text
source priority > target
→ priority_override
```

and:

```text
source priority == target
→ user_forced_override

source priority < target
→ user_forced_override
```

All still require explicit confirmation.

---

# 73. Pure domain tests — snapshots

Test exact blocker snapshot comparison.

Changes to:

```text
segment ID

start

end

status
```

must invalidate previous confirmation.

---

# 74. Pure domain tests — subtraction

Cover at minimum:

```text
source covers middle
→ 2 fragments

source overlaps left edge
→ 1 right fragment

source overlaps right edge
→ 1 left fragment

source covers entire target
→ normative 0-fragment outcome

adjacency
→ no subtraction
```

---

# 75. Split identity test

For:

```text
2 fragments
```

verify:

```text
left keeps original ID

right gets backend UUID v4
```

---

# 76. Repeated segmentation test

Resolve a conflict against an occurrence that already has multiple segments.

Verify:

```text
existing unrelated sibling IDs unchanged

affected segment follows identity rule

no sibling overlap

aggregate coherent
```

---

# 77. Multiple source interval test

Use a custom source with more than one blocking segment.

Verify target subtraction uses:

```text
actual source segments
```

not source parent envelope.

---

# 78. Pending tests

Implement the exact `pending` outcomes defined by
`STATUS_CONFLICT_RULES.md`.

Cover:

```text
partial overlap

middle overlap

full overlap
```

---

# 79. In-progress tests

Implement and test the exact nuanced:

```text
in_progress
```

rule from the normative conflict document.

If that rule is not actually complete enough to implement:

```text
STOP
report before inventing behavior
```

---

# 80. Completed / not_finished tests

Verify:

```text
no silent modification
```

without the required strong explicit confirmation.

Also verify frozen realized history remains protected.

---

# 81. Non-blocking tests

Overlapping:

```text
cancelled

not_completed
```

must not require conflict resolution.

---

# 82. Aggregate tests

After each approved target resolution:

```text
derive aggregate from all target segments
```

Test both:

```text
single-segment target

multi-segment target
```

---

# 83. Metadata tests

Verify confirmed resolution updates exactly the approved fields.

At minimum test:

```text
target conflict_reason

target source_occurrence_id

source origin_reason for conflict insertion

source conflict-action metadata for insertion/move
```

and preservation of unrelated metadata.

---

# 84. Latest conflict test

Resolve target with Source A.

Later resolve same target with Source B.

Expected:

```text
latest target conflict metadata
→ Source B
```

No multi-source genealogy.

---

# 85. Metadata persistence after source move

After a confirmed conflict:

```text
move source away without another conflict
```

Expected:

```text
target historical conflict metadata remains
```

Current blocking relationship disappears because segments no longer overlap,
not because metadata was cleared.

---

# 86. Referenced source movement regression

A source referenced through:

```text
source_occurrence_id
```

may still move.

No legacy movement lock.

---

# 87. Referenced source delete regression

Deletion remains restricted by:

```text
ON DELETE NO ACTION
```

Do not weaken it.

---

# 88. First-request PostgreSQL test

Real schema 004:

```text
source insertion/move
→ blocker
```

Expected:

```text
409 resolution required

source unchanged/uncreated as appropriate

target unchanged

metadata unchanged
```

---

# 89. Confirmed insertion round trip

Real PostgreSQL:

```text
POST source insertion
→ 409
→ retry with blocker confirmation
→ success
→ GET planner-state
```

Verify:

```text
source exists

target segmentation resolved

target aggregate correct

target conflict metadata correct

source insertion metadata correct

stable IDs
```

---

# 90. Confirmed structural move round trip

Real PostgreSQL:

```text
translate/structure source
→ 409
→ confirmed retry
→ success
→ GET
```

Verify:

```text
source moved

target resolved

target metadata

source conflict_move metadata

unrelated segments unchanged
```

---

# 91. Stale snapshot PostgreSQL test

Flow:

```text
first 409

modify blocker legitimately before confirmation

retry old confirmation
```

Expected:

```text
conflict_resolution_stale
or equivalent

zero destructive writes from stale authorization
```

---

# 92. New blocker PostgreSQL test

Between first request and confirmation:

```text
new blocker appears
```

Old confirmation must not authorize it.

Return fresh conflict state.

---

# 93. Removed blocker test

If original blocker disappears/changes before confirmation:

```text
old snapshot must not be used destructively
```

Follow the approved stale revalidation behavior.

---

# 94. Wrong segment confirmation test

Confirmation for:

```text
Occurrence A / Segment X
```

must not authorize:

```text
Occurrence A / Segment Y
```

---

# 95. Priority override integration

Higher-priority source still requires first 409 + explicit confirmation.

After confirmation:

```text
target conflict_reason = priority_override
```

if target is actually modified.

---

# 96. User-forced integration

Equal/lower-priority source requires explicit user-forced confirmation.

After confirmed resolution:

```text
target conflict_reason = user_forced_override
```

---

# 97. Strong realized-time integration

For editable realized blockers requiring stronger confirmation:

```text
ordinary confirmation insufficient
```

Only the explicit stronger acknowledgement defined by the normative rules may
authorize the correction.

No silent rewrite.

---

# 98. Frozen blocker integration

A blocker in frozen history must not be structurally rewritten through this
engine.

Return a controlled error requiring source adjustment instead.

---

# 99. Atomic rollback — source write

Force failure after target candidate planning but during source persistence.

Verify target remains unchanged.

---

# 100. Atomic rollback — target update

Force failure while updating a target child.

Verify:

```text
source unchanged/uncreated

all targets unchanged
```

---

# 101. Atomic rollback — split insert

Force failure inserting a new right-side split fragment.

Verify the original target graph survives intact.

---

# 102. Atomic rollback — aggregate

Force failure after child changes but before parent aggregate update.

Verify rollback restores complete prior graph.

---

# 103. Atomic rollback — metadata

Force failure after structural resolution but before metadata completion.

No partial conflict context may remain.

---

# 104. Concurrency

Test two competing confirmed source operations where practical.

They must not both commit based on the same stale blocker snapshot.

Expected outcomes may include:

```text
one success

other concurrent_conflict / stale conflict
```

but never:

```text
lost target fragments

invalid sibling overlap

stale aggregate

partial source/target write
```

---

# 105. PlanItem creation regression

No-conflict creation still produces:

```text
PlanItem

Occurrence

one default Segment
```

without conflict metadata.

---

# 106. Structural mutation regression

No-conflict:

```text
translate

PUT structure

reset
```

must continue working exactly as before.

---

# 107. Segment-status regression

`PATCH segment status` remains:

```text
segment-aware

aggregate-aware

conflict rejection only
```

No new override behavior there.

---

# 108. Reconciliation regression

`POST /api/planner/reconcile` remains unchanged.

Conflict engine must not become a hidden reconciliation mechanism.

---

# 109. Apply Week/Future regression

Verify the completed 05.7.5.9 behavior remains:

```text
SIMPLE segment-aware

CUSTOM translate

CUSTOM resize rejection

real segment conflict rejection

no runtime segment inheritance
```

No blocker modifications from recurring commands.

---

# 110. Planner-state regression

GET remains read-only and correctly returns:

```text
segments[]

conflictContext

originReason

lastConflictAction

sourceGenerationSlotId

derived/materialized parent aggregate
```

---

# 111. Frontend scope

Do NOT build final conflict UI.

Do not add:

```text
Segmentar y continuar

Finalizar y continuar

Cancelar y continuar

Confirmar corrección
```

as real interactive flows yet.

That is 05.7.5.11.

---

# 112. Existing frontend safety

If current frontend sees the new backend resolution-required response before
05.7.5.11:

```text
it may surface a controlled generic error
```

but must NOT fall back to old parent-level conflict mutation.

Guard any dangerous legacy confirmation path.

---

# 113. No CORS redesign

Use existing route CORS behavior.

Only adjust CORS if a backend route contract change genuinely requires it.

No wildcard origins.

---

# 114. Documentation

Update only necessary architecture/API documentation for:

```text
segment blocker snapshot contract

confirmation/revalidation protocol

resolution metadata

remaining rejection-only conflict paths
```

Do not create event-log or future template designs.

---

# 115. PostgreSQL 16

Use isolated PostgreSQL 16:

```text
001
→ 002
→ 003
→ 004
```

Do not use `vcs_dev`.

---

# 116. Full backend suite

Run:

```text
.venv/bin/python -m unittest discover \
  -s modules/gestor_de_habitos/backend \
  -p 'test_*.py'
```

Report skips honestly.

---

# 117. Schema-004 integration suite

Add/reuse real PostgreSQL tests for:

```text
first conflict 409

confirmed insertion

confirmed move

trim

split

full-overlap normative outcome

stale blocker

new blocker

priority override

user-forced override

strong realized confirmation

metadata

atomic rollback

concurrency
```

---

# 118. Frontend regression suite

Even though this phase is backend-first, run:

```text
for test_file in modules/gestor_de_habitos/tests/*.test.mjs
do
  node "$test_file" || exit 1
done
```

The existing UI must not regress.

---

# 119. Syntax / consistency

Run:

```text
.venv/bin/python -m compileall -q \
  modules/gestor_de_habitos/backend
```

Run `node --check` only for JS modified if any minimal guard is necessary.

Run:

```text
git diff --check
```

---

# 120. Still no real schema rollout

Do NOT apply migration 004 to real `vcs_dev`.

After this phase the primary remaining work is:

```text
05.7.5.11
Conflict UX + chronology cleanup + remaining frontend legacy conflict path

05.7.5.12
Final writer audit + schema rollout
```

---

# 121. Expected architecture after this phase

```text
schema 004
✅

backend read
✅

frontend read/display
✅

creation + default segment
✅

segment status
✅

persistent reconciliation
✅

frontend status
✅

backend structure
✅

frontend structure
✅

Apply Week/Future segment-aware
✅

segment conflict detection
✅

single-source segment conflict resolution engine
✅

snapshot confirmation
✅

priority/user-forced conflict metadata
✅

automatic interval subtraction after explicit confirmation
✅

final conflict UX
❌

planner chronology cleanup
❌

real schema rollout
❌
```

---

# 122. Legacy audit

At completion identify every remaining caller of:

```text
edit_without_occurrence

prepareOccurrenceAddition

commitPreparedScheduleChange

commitPreparedChange

apply_priority_overrides

legacy confirmedOccurrenceIds
```

Classify each as:

```text
retired

guarded

dormant

active and still incompatible
```

The report must identify exact remaining active incompatible paths before
05.7.5.11.

---

# 123. Git rules

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

# 124. Completion report

At completion provide:

## Files

Every created/modified file.

## Conflict domain

Explain:

```text
blocking statuses

segment-vs-segment detection

subtraction

0 / 1 / 2 fragment outcomes

repeated segmentation

multi-segment source
```

## Confirmation contract

Report exact:

```text
first 409 payload

confirmation payload

snapshot fields

stale error

strong realized-time acknowledgement
```

## Authorization

Explain:

```text
priority_override

user_forced_override

how backend computes each
```

## Status behavior

Explain exact normative outcomes for:

```text
pending

in_progress

completed

not_finished
```

and identify non-blockers.

## Metadata

Explain exactly where and when:

```text
conflict_reason

source_occurrence_id

origin_reason

last_conflict_action
```

change.

## Integration

Report behavior for:

```text
PlanItem creation

translate

structure replacement

reset
```

and which paths remain rejection-only:

```text
segment status

Apply Week

Apply Future
```

## Transactions

Explain:

```text
SERIALIZABLE

lock order

atomic source + targets

snapshot revalidation
```

## PostgreSQL

Describe actual schema-004 tests for:

```text
confirmed insertion

confirmed move

trim

split

full overlap

stale confirmation

priority

user-forced

realized-time confirmation

metadata

rollback

concurrency
```

## Legacy paths

List exact callers remaining.

## Tests

Give exact commands/results.

## Safety

Confirm:

```text
vcs_dev untouched

PlanItems preserved

migrations unchanged

no recurring conflict resolution

no segment-status conflict resolution

no global shifting

no event log

no final conflict UX

no chronology redesign
```

## Remaining incompatibilities

List exactly what still blocks schema-004 rollout.

## Git

Show:

```text
git diff --stat

git status --short --untracked-files=all
```

No commit.

No push.

---

# 125. Definition of done

This phase is complete when:

```text
conflicts are detected by concrete segment

first conflict request performs zero blocker writes

confirmation is bound to exact blocker snapshot

changed blocker invalidates authorization

priority does not imply silent mutation

equal/lower priority requires user-forced authorization

realized time is strongly protected

pending/in-progress outcomes follow normative rules

conflict subtraction supports 0/1/2 fragments

split preserves left ID and creates right UUID

already-segmented targets can be segmented again

source custom gaps are respected

target aggregate is recalculated

target latest conflict metadata is correct

source insertion/move metadata is correct

metadata does not auto-clear

PlanItem insertion uses the new engine

single-occurrence structural moves use the new engine

legacy parent-level backend override is not reachable

Apply Week/Future remain safe rejection-only

segment status remains safe rejection-only

all source + target writes are atomic

stale confirmations cannot mutate data

real PostgreSQL 16 verification passes

vcs_dev remains untouched
```

---

# Final principle

Priority is not permission to silently rewrite history.

The backend may determine:

```text
priority_override
```

but the user still authorizes the concrete effect.

The authorization is not:

```text
"yes, modify that occurrence"
```

It is tied to:

```text
THIS occurrence
THIS segment
THIS start/end
THIS status
```

If that blocker changes:

```text
the authorization expires
```

The engine operates on actual occupied time:

```text
SOURCE SEGMENTS
        ↓
TARGET SEGMENT
        ↓
SUBTRACT OCCUPIED INTERVAL
        ↓
0 / 1 / 2 SURVIVING FRAGMENTS
        ↓
STATUS + STRUCTURE + AGGREGATE
        ↓
ATOMIC COMMIT
```

No parent envelope is treated as continuous occupation.

No priority silently rewrites realized time.

No conflict operation guesses what happened.

And no target is modified until the user has explicitly confirmed the current
concrete blocker.
