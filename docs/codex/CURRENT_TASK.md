# CURRENT TASK

## OccurrenceSegment v1 — Backend Structural Segment Mutations

### Objective

Implement the authoritative backend foundation for manually changing the
temporal structure of an existing Occurrence.

This phase introduces three explicit structural intents:

```text
1. translate occurrence
2. replace occurrence structure with a complete final segment set
3. reset segmentation
```

The core principle is:

```text
frontend may build/edit a draft
        ↓
backend receives one explicit final-state command
        ↓
backend validates the COMPLETE candidate state
        ↓
parent + children are persisted atomically
```

The backend must never persist an invalid intermediate structure.

This phase is BACKEND ONLY.

Frontend segment-editor integration comes later.

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

Also inspect the completed implementation for:

```text
occurrence_segment_domain.py

occurrence_segment_service.py

repositories/occurrence_segment_repository.py

planner_state_service.py

plan_item_creation_service.py

scheduling_policy.py

app.py
```

and:

```text
modules/gestor_de_habitos/db/migrations/004_occurrence_segments.sql
```

Read all relevant existing tests before implementation.

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

Do not silently reinterpret approved behavior.

---

# Scope

This task is limited to:

```text
backend structural segment domain

explicit occurrence translation

atomic final-state structural replacement

manual segment add/remove through final-state replacement

manual segment time adjustment

manual split/trim representation through final-state replacement

occurrence envelope resize with explicit valid final segments

reset segmentation

aggregate recalculation

segment-based conflict detection for rejection only

backend tests

isolated PostgreSQL 16 verification
```

Do NOT implement:

```text
frontend segment editor

occurrence date mutation

Apply Week segment behavior

Apply Future segment behavior

priority conflict resolution

user-forced conflict resolution

automatic conflict split/trim

conflict confirmation handshake

pause/resume

live tracking

recurring segment templates
```

---

# 1. Inspect working tree first

Before editing:

```text
git status --short --untracked-files=all
git diff --stat
```

Preserve all existing user work.

Do not revert completed OccurrenceSegment phases.

---

# 2. Database safety

Do NOT apply migration 004 to:

```text
vcs_dev
```

Do NOT query, clean or modify real development data.

Legacy PlanItems must remain preserved.

Use:

```text
isolated PostgreSQL 16
```

for real schema-004 structural-write verification.

Do not expose secrets or private `.env` contents.

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
STOP before modifying it
```

and report:

```text
finding
impact
alternatives
recommendation
```

---

# 4. Why final-state replacement is preferred

Do NOT build a structural editor backend around a long sequence such as:

```text
DELETE segment
PATCH segment
POST segment
PATCH occurrence
```

where each HTTP request persists a partial edit.

The approved domain explicitly allows:

```text
temporarily invalid frontend draft
```

but never:

```text
temporarily invalid persisted state
```

Therefore manual structural editing should submit:

```text
one complete candidate final structure
```

which is validated and committed atomically.

---

# 5. Structural operations

Implement explicit backend support for three intents:

```text
TRANSLATE

REPLACE STRUCTURE

RESET SEGMENTATION
```

Do not infer one intent from another.

---

# 6. Translate endpoint

Preferred route:

```text
POST /api/occurrences/<occurrence_id>/translate
```

Payload:

```json
{
  "startTime": "13:00",
  "endTime": "17:00"
}
```

This represents:

```text
pure movement
```

not resize.

If existing routing conventions justify a small naming difference, preserve
the same explicit semantics and report the final route.

---

# 7. Translate requires unchanged duration

Translation is valid only if:

```text
new occurrence duration
==
old occurrence duration
```

Example:

```text
08:00–12:00
→
13:00–17:00
```

valid.

Example:

```text
08:00–12:00
→
13:00–18:00
```

NOT translation.

Reject duration-changing requests instead of silently treating them as resize.

Preferred controlled error:

```text
occurrence_translate_duration_mismatch
```

---

# 8. Translate all segments by the same delta

Calculate:

```text
delta = newStart - oldStart
```

Apply to every persisted segment:

```text
segment.start += delta
segment.end   += delta
```

Preserve:

```text
segment.id

segment.status

relative gaps

segment durations

segment order
```

---

# 9. Translate example

Before:

```text
Occurrence
08:00–12:00

Seg A
08:00–10:00

Seg B
10:30–12:00
```

Translate to:

```text
13:00–17:00
```

Result:

```text
Occurrence
13:00–17:00

Seg A
13:00–15:00

Seg B
15:30–17:00
```

Same IDs.

Same statuses.

---

# 10. Translation must remain inside one local date

OccurrenceSegment v1 remains single-date.

Do NOT allow translation to wrap across midnight or create invalid TIME
semantics.

Examples requiring a different date/day model are out of scope.

Reject instead of wrapping.

---

# 11. Occurrence date is immutable in this phase

Do NOT change:

```text
occurrence_date
```

through structural endpoints in this task.

Date movement remains a later schedule-mutation concern.

This phase modifies only:

```text
times
segment structure
```

inside the existing occurrence date.

---

# 12. Final-state structure endpoint

Preferred route:

```text
PUT /api/occurrences/<occurrence_id>/structure
```

It receives the complete desired persisted structure for that occurrence.

Conceptually:

```json
{
  "startTime": "13:00",
  "endTime": "17:00",
  "segments": [
    {
      "id": "<existing-segment-uuid>",
      "startTime": "13:00",
      "endTime": "14:00"
    },
    {
      "startTime": "14:30",
      "endTime": "17:00",
      "status": "pending"
    }
  ]
}
```

Exact naming may follow established JSON conventions.

---

# 13. Meaning of structure payload

The structure payload represents:

```text
THE COMPLETE FINAL SEGMENT SET
```

not a sequence of patches.

Every segment that should remain after commit must appear in the request.

---

# 14. Existing segment entries

For an existing persisted segment:

```text
id is required
```

and:

```text
status is NOT structurally editable here
```

Its persisted status must be preserved.

The request may omit status for existing segments.

If the client supplies a status for an existing segment:

```text
reject it
```

or require exact equality with persisted status according to the simplest
consistent API convention.

Do NOT allow this endpoint to become a second status-mutation API.

---

# 15. New segment entries

A new manual segment:

```text
has no persisted id
```

The backend must generate:

```text
new UUID v4
```

for it.

A new segment must provide an explicit canonical:

```text
status
```

because there is no previous persisted status to preserve.

Do not invent hidden status inheritance for general manual creation.

---

# 16. New segment status validation

A new segment status must satisfy the same temporal rules already implemented
for status mutation.

Reuse existing domain behavior.

Do NOT duplicate the temporal-status matrix.

---

# 17. Existing segments omitted from final set

If an existing child belonging to the occurrence is absent from the complete
final segment set:

```text
it is deleted
```

inside the same transaction.

This is the manual segment-delete mechanism for this phase.

Do NOT add a separate public:

```text
DELETE /api/occurrence-segments/<id>
```

unless a strong repository convention requires it and final-state atomicity is
still preserved.

Preferred architecture:

```text
complete structure replacement
```

---

# 18. Never allow zero segments

The submitted final state must contain:

```text
1..N segments
```

Reject:

```text
segments: []
```

Preferred error:

```text
occurrence_requires_segment
```

Do not delete the parent implicitly.

---

# 19. Existing segment ownership

Every supplied persisted:

```text
segment.id
```

must already belong to:

```text
the target occurrence
```

Reject:

```text
segment from another occurrence

unknown segment ID

duplicate segment ID
```

Do not transfer segments between parents.

---

# 20. Stable identity

For existing segments included in the final state:

```text
preserve their IDs
```

A normal time adjustment does NOT create a new identity.

New entries receive new IDs.

Deleted entries cease to exist.

---

# 21. Manual split representation

A manual split can be represented as a final structure.

Example persisted segment:

```text
S1
13:00–17:00
pending
```

Desired final structure:

```text
S1
13:00–14:00
pending

NEW
14:30–17:00
pending
```

Result:

```text
left fragment keeps S1.id

right fragment receives new UUID
```

This supports the approved identity model.

---

# 22. Manual trim representation

A trim is simply an existing segment with adjusted bounds.

Example:

```text
S1
08:00–10:00
```

becomes:

```text
S1
08:00–09:15
```

Preserve:

```text
S1.id
S1.status
```

---

# 23. Automatic conflict split/trim remains out of scope

Although final-state replacement can represent:

```text
split
trim
```

do NOT implement automatic interval subtraction from another conflicting
occurrence yet.

That belongs to the segment-aware conflict engine phase.

This phase supports:

```text
explicit user-authored structural results
```

only.

---

# 24. Resize through final-state replacement

Changing:

```text
Occurrence.start_time
Occurrence.end_time
```

to a different duration is:

```text
resize
```

The backend must NOT:

```text
scale

compress

stretch

truncate
```

segments automatically.

---

# 25. Manual resize requires valid final children

A resize request through:

```text
PUT .../structure
```

is accepted only when the submitted final segments already satisfy:

```text
newOccurrence.start <= segment.start

segment.end <= newOccurrence.end
```

The backend never persists the invalid draft.

---

# 26. Resize example

Current:

```text
Occurrence
08:00–12:00

S1 08:00–10:00
S2 10:30–12:00
```

Requested:

```text
Occurrence
08:00–11:00

S1 08:00–09:30
S2 10:00–11:00
```

may be valid.

But:

```text
Occurrence
08:00–11:00

S1 08:00–10:00
S2 10:30–12:00
```

must be rejected.

---

# 27. Reset segmentation endpoint

Preferred route:

```text
POST /api/occurrences/<occurrence_id>/reset-segmentation
```

Payload:

```json
{
  "startTime": "08:00",
  "endTime": "11:00"
}
```

This action may simultaneously establish a new general range and reset its
segment structure.

---

# 28. Reset behavior

Reset segmentation must atomically:

```text
1. read current parent aggregate
2. validate requested new general range
3. remove current child structure
4. create exactly one new segment
5. segment.start = new parent.start
6. segment.end = new parent.end
7. segment.status = previous parent aggregate
8. generate new UUID
9. validate temporal rules
10. validate conflicts
11. derive aggregate again
12. persist parent + child
```

Do not assume previous aggregate is automatically valid.

---

# 29. Reset creates a new segment identity

For reset segmentation:

```text
new Segment 1
→ new UUID
```

Do not preserve an arbitrary old child identity merely because one existed.

Reset means:

```text
replace structural segmentation
```

---

# 30. Reset uses previous aggregate as initial status

Example:

```text
parent aggregate before reset:
in_progress
```

new single segment initially receives:

```text
in_progress
```

Then all temporal/integrity validations run.

If invalid:

```text
reject entire reset
```

No partial changes.

---

# 31. Reset completed-time validation

Example current day:

```text
previous aggregate = completed

new reset interval ends in the future
```

Result:

```text
reject
```

because a completed segment may not end after `now`.

Do not silently change:

```text
completed → pending
```

---

# 32. Structural temporal zones

Structural editing follows temporal immutability.

Conceptually:

```text
FUTURE
→ editable structurally

CURRENT_DAY
→ editable structurally

PREVIOUS_EDITABLE_DAY
→ editable structurally

FROZEN_HISTORY
→ read-only
```

Do not allow structural modifications to frozen history.

---

# 33. Previous editable day

Yesterday may still be structurally corrected.

However its persisted segment statuses must already be historical stable
statuses:

```text
completed
not_completed
not_finished
cancelled
```

If transient:

```text
pending
in_progress
```

is encountered:

```text
temporal_reconciliation_required
```

instead of silently reconciling inside the structural endpoint.

---

# 34. Future structure status rules

For future occurrences, all resulting/new segment statuses must satisfy the
existing future status rules:

```text
pending
cancelled
```

Do not permit structural editing to bypass status temporal integrity.

---

# 35. Current-day completed-time integrity

Any structural change affecting a segment whose status is:

```text
completed
```

must revalidate:

```text
segment.endDateTime <= now
```

because moving/resizing time can make a previously valid completed segment
invalid.

---

# 36. One authoritative `now`

Capture one backend:

```text
now
```

per operation.

Use it consistently for:

```text
temporal phase
completed-time validation
```

Reuse the existing clock/time architecture from the status/reconciliation
phase.

Do not accept `now` from the public client.

---

# 37. Segment bounds

Every final segment must satisfy:

```text
occurrence.start_time <= segment.start_time
```

and:

```text
segment.end_time <= occurrence.end_time
```

Reject the entire operation if any child violates bounds.

---

# 38. Positive segment duration

Every final segment must satisfy:

```text
segment.start_time < segment.end_time
```

Do not create zero-duration fragments.

---

# 39. Sibling non-overlap

Final sibling segments must not overlap.

Adjacency remains valid:

```text
13:00–14:00
14:00–15:00
```

Overlap invalid:

```text
13:00–15:00
14:30–16:00
```

Use:

```text
[start, end)
```

semantics.

Validate in domain/service before persistence for a controlled error.

PostgreSQL exclusion constraint remains the final structural barrier.

---

# 40. Deterministic segment ordering

Canonical final order:

```text
start_time

end_time

id
```

New segments may require an internal temporary representation before UUID
assignment.

Do not persist:

```text
ordinal
position
segment_number
```

---

# 41. Aggregate after structural change

After obtaining the complete valid candidate segment set:

```text
derive_occurrence_status(all final segments, temporal_phase)
```

Persist:

```text
Occurrence.status
```

from that derived result.

Never independently preserve an old aggregate if the child set changed.

---

# 42. Existing status values are preserved during structural edits

For persisted segments:

```text
structural operation
```

changes structure/time only.

It does not reinterpret what happened.

Statuses remain unchanged unless:

```text
segment is new
```

or:

```text
reset segmentation
```

uses its explicitly approved aggregate inheritance rule.

---

# 43. Conflict metadata preservation

Successful ordinary structural edits must NOT automatically clear:

```text
conflict_reason

source_occurrence_id

origin_reason

last_conflict_action
```

Those fields describe other semantics.

---

# 44. Ordinary movement is not automatically a conflict event

A successful translate or resize that causes no conflict resolution does NOT
set:

```text
last_conflict_action = conflict_move
```

That field means the occurrence moved AND caused a conflict modification.

This phase rejects unresolved conflicts instead of resolving them.

Therefore successful ordinary movement leaves:

```text
last_conflict_action
```

unchanged.

---

# 45. `source_generation_slot_id`

Preserve:

```text
source_generation_slot_id
```

through structural edits.

Changing runtime structure does not change its generation provenance.

---

# 46. Referenced historical source may move

Do NOT reintroduce the old rule:

```text
source_occurrence_id referenced
→ occurrence cannot move
```

A referenced source may be structurally moved if all current domain rules are
satisfied.

Its old target metadata remains historical.

---

# 47. Referenced historical source deletion remains restricted

This phase does not delete occurrences.

Preserve the schema rule:

```text
source_occurrence_id
ON DELETE NO ACTION
```

No tombstones/event log in this task.

---

# 48. External conflict validation

Structural mutations can create new schedule occupancy.

Before commit, compare every final blocking candidate segment against:

```text
blocking persisted segments
belonging to OTHER occurrences
on the same date
```

Use actual segments, not parent envelopes.

---

# 49. Canonical blocking statuses

Reuse the existing backend authority:

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

Do not create another independent blocking-status set.

---

# 50. Candidate-set conflict checking

When validating external conflicts, use:

```text
the complete final candidate segment set
```

not the old persisted structure.

For the target occurrence itself:

```text
exclude its currently persisted segments
```

and evaluate the candidate replacement instead.

---

# 51. Gap-aware conflicts

Example:

```text
Target occurrence
08:00–12:00

candidate segments:
08:00–09:00 pending
11:00–12:00 pending
```

Another occurrence:

```text
09:30–10:30 pending
```

Result:

```text
NO conflict
```

The parent envelope gap is free.

---

# 52. Conflict rejection only

If a candidate structural mutation overlaps an external blocking segment:

```text
REJECT
```

Do NOT:

```text
cancel blocker

change blocker status

split blocker

trim blocker

move blocker

priority override

user-forced override
```

Conflict resolution remains a later phase.

---

# 53. Structural conflict error

Preferred code:

```text
occurrence_structure_conflict
```

Return blockers with enough data for the future frontend:

```text
occurrenceId

segmentId

planItemId

date

startTime

endTime

status
```

This is informational only.

---

# 54. Multiple blockers

Validate against all current relevant blockers.

Do not stop after the first merely because one conflict was found.

Return deterministic blocker ordering.

Do not modify any blocker.

---

# 55. Final-state validation before writes

Conceptual flow:

```text
load parent
        ↓
lock parent
        ↓
lock persisted children
        ↓
derive temporal phase
        ↓
build COMPLETE candidate graph
        ↓
validate identities
        ↓
validate statuses
        ↓
validate time ranges
        ↓
validate bounds
        ↓
validate sibling non-overlap
        ↓
validate completed-time rules
        ↓
derive aggregate
        ↓
query external blockers
        ↓
validate external conflicts
        ↓
persist complete result
        ↓
COMMIT
```

---

# 56. Transaction isolation

Use:

```text
SERIALIZABLE
```

consistent with existing structural/status mutation architecture.

Do not assume SERIALIZABLE replaces explicit deterministic locking.

---

# 57. Lock order

Follow one consistent order with other OccurrenceSegment services.

Conceptually:

```text
1. target parent
2. target segments ordered deterministically
3. current external blocker rows when needed
4. validate final state
5. write
```

Avoid introducing a conflicting lock order relative to status mutation.

---

# 58. Atomic replacement

For:

```text
PUT structure
```

updates/inserts/deletes must commit together.

Never expose a state such as:

```text
old segments deleted
new segments not yet inserted
```

after a failure.

---

# 59. Deferred sibling exclusion constraint

Migration 004 uses a deferred exclusion constraint.

Use that property appropriately during final-state replacement.

An intermediate SQL statement inside the transaction may temporarily overlap
if the final committed state is valid.

Do NOT disable the constraint.

---

# 60. Parent aggregate atomicity

Parent envelope, child structure and parent aggregate must be committed
together.

Never:

```text
COMMIT child changes
then update parent later
```

---

# 61. New UUID generation

New manual segments and reset segments use:

```text
backend-generated UUID v4
```

consistent with PlanItem creation.

Do not accept caller-provided IDs for new segments.

---

# 62. Client must not forge new persisted IDs

For structure replacement:

```text
id present
→ must refer to existing child of this parent

id absent
→ backend creates new identity
```

Do not allow:

```text
arbitrary unknown client UUID
```

to become a persisted new segment identity.

---

# 63. Response should be authoritative

Successful structural commands should return enough information to identify
the mutation.

But the intended frontend flow later remains:

```text
structural command
→ GET planner-state
→ hydrate authoritative graph
```

Do not return a second independently assembled planner-state representation
from mutation routes.

A compact command result is sufficient.

---

# 64. Suggested structure response

Conceptually:

```json
{
  "status": "ok",
  "occurrenceId": "<uuid>",
  "occurrenceStatus": "in_progress",
  "segmentIds": [
    "<uuid>",
    "<uuid>"
  ]
}
```

Exact shape may follow current backend API conventions.

---

# 65. No direct public child-time PATCH

Do NOT introduce a separate endpoint that independently persists:

```text
segment.start_time
segment.end_time
```

outside final-state structural validation.

Manual child-time editing should be committed through:

```text
PUT occurrence structure
```

This prevents partial invalid drafts.

---

# 66. No direct public child delete

Prefer not to introduce standalone:

```text
DELETE occurrence-segment
```

in this phase.

Deletion is represented by absence from:

```text
complete final structure
```

This enforces:

```text
at least one child
```

atomically.

---

# 67. No direct public split/trim command required

Do not create unnecessary:

```text
/split

/trim
```

HTTP endpoints for manual editing.

Manual split/trim is represented by the submitted final structure.

Automatic conflict-driven split/trim will use domain primitives later.

---

# 68. Domain helpers

Extract small pure helpers where useful for:

```text
validate final segment set

sort segment set

translate times

validate bounds

validate sibling overlap
```

Do not create a generic scheduling framework.

Reuse existing domain status and temporal validation.

---

# 69. Preserve planner-state read behavior

Do not regress:

```text
segments[]

conflictContext

originReason

lastConflictAction

sourceGenerationSlotId

parent aggregate
```

---

# 70. Preserve status endpoint

Do not regress:

```text
PATCH /api/occurrence-segments/<segment_id>/status
```

Structural endpoints must not compete with it for existing segment status
changes.

---

# 71. Preserve reconciliation

Do not regress:

```text
POST /api/planner/reconcile
```

Structural mutation of yesterday encountering transient state should require
reconciliation rather than silently performing it.

---

# 72. Preserve PlanItem creation

Do not regress:

```text
PlanItem
→ Occurrence
→ default Segment
```

The legacy conflict-resolution guard must remain active.

---

# 73. Existing legacy occurrence mutation path

The repository still contains older parent-level mutation behavior.

Do NOT silently route new structural commands through logic that assumes:

```text
1 Occurrence = one continuous occupied interval
```

Build the new structural service using segment-aware rules.

Document which old path remains incompatible.

---

# 74. Existing frontend remains unchanged

Do NOT modify:

```text
planner matrix

segment controls

frontend API

segment editor UI

CSS
```

during this task.

The next phase will connect frontend structural editing.

---

# 75. No CORS expansion yet

Do not add CORS for structural endpoints merely because a future frontend will
need them.

CORS can be added when the frontend integration phase consumes the routes.

---

# 76. Pure domain tests

Add focused tests for:

```text
valid final segment set

zero segments rejected

positive durations

bounds

adjacency accepted

sibling overlap rejected

deterministic order

translate delta

translate preserves gaps

translate preserves IDs

translate preserves statuses

duration mismatch rejected
```

---

# 77. Structure identity tests

Verify:

```text
existing child ID preserved

unknown child ID rejected

foreign-parent child ID rejected

duplicate supplied child ID rejected

new child gets UUID v4

two new children get different IDs
```

---

# 78. Manual add test

Current:

```text
Occurrence
13:00–17:00

S1
13:00–14:00
pending
```

Final request adds:

```text
NEW
14:30–17:00
pending
```

Expected:

```text
S1 preserved

new persisted UUID created

aggregate recalculated
```

---

# 79. Manual delete test

Current:

```text
S1
S2
```

Final structure contains:

```text
S1 only
```

Expected:

```text
S2 deleted

S1 preserved

at least one remains

aggregate recalculated
```

---

# 80. Delete-last protection test

Current:

```text
S1 only
```

Final request:

```text
segments: []
```

Expected:

```text
reject

S1 remains

parent unchanged
```

---

# 81. Manual split test

Current:

```text
S1 13:00–17:00 pending
```

Submit:

```text
S1 13:00–14:00

NEW 14:30–17:00 pending
```

Verify:

```text
left keeps S1 ID

right receives new ID

gap remains free

parent remains one logical occurrence
```

---

# 82. Manual trim test

Current:

```text
S1 08:00–10:00
```

Submit:

```text
S1 08:00–09:15
```

Verify:

```text
same ID

same status

new time persisted
```

---

# 83. Resize tests

Verify:

```text
new shorter envelope
+
all submitted segments inside
→ accepted
```

and:

```text
new shorter envelope
+
one segment still outside
→ rejected
```

No scaling occurs.

---

# 84. Completed structural-time tests

Current day:

```text
completed segment moved so end <= now
→ allowed if all other rules pass

completed segment moved so end > now
→ rejected
```

Use deterministic injected `now`.

---

# 85. Frozen structure test

Any:

```text
translate

replace structure

reset segmentation
```

on frozen history:

```text
rejected
```

No write.

---

# 86. Yesterday transient-state test

If yesterday still contains:

```text
pending
or
in_progress
```

a structural operation should return:

```text
temporal_reconciliation_required
```

rather than silently modifying status.

---

# 87. Translate PostgreSQL round trip

Against isolated schema 004:

```text
POST translate
→ GET planner-state
```

Verify:

```text
parent times moved

all child times moved by exact delta

IDs unchanged

statuses unchanged

gaps unchanged

aggregate correct
```

---

# 88. Structure replacement PostgreSQL round trip

Verify:

```text
PUT structure
→ GET planner-state
```

for a candidate involving:

```text
existing child update

existing child deletion

new child insertion
```

all in one atomic mutation.

---

# 89. Reset PostgreSQL round trip

Verify:

```text
POST reset-segmentation
→ GET planner-state
```

returns:

```text
one child

new child UUID

child range == parent range

status inherited from previous aggregate

aggregate coherent
```

---

# 90. Reset conflict validation test

If resetting to one blocking interval would overlap another blocking segment:

```text
reject entire reset
```

Old structure must remain unchanged.

---

# 91. External structure conflict test

Example:

```text
A candidate blocking segment
08:00–10:00

external blocker
09:00–11:00
```

Expected:

```text
409 occurrence_structure_conflict
```

No partial writes.

---

# 92. Gap-aware external conflict test

Parent envelopes may overlap.

If candidate segments do not overlap actual blocker segments:

```text
allow
```

Prove the query does not fall back to parent envelope conflict logic.

---

# 93. Multiple blocker test

Return all relevant external blocker segments in deterministic order.

No blocker may be modified.

---

# 94. Non-blocking candidate test

Candidate segments with:

```text
cancelled
not_completed
```

do not block schedule.

Existing statuses remain semantically intact.

---

# 95. Metadata preservation tests

Structural edits preserve:

```text
conflict_reason

source_occurrence_id

origin_reason

last_conflict_action

source_generation_slot_id
```

unless a future conflict-resolution rule explicitly changes them.

---

# 96. Referenced source movement test

Create:

```text
Target.source_occurrence_id = Source.id
```

Then structurally translate:

```text
Source
```

Expected:

```text
allowed if no current integrity conflict

Target.source_occurrence_id remains Source.id

Target historical metadata unchanged
```

This proves the legacy movement lock is not reintroduced.

---

# 97. Atomic rollback tests

Force failures during:

```text
new child insert

old child delete

parent envelope update

parent aggregate update
```

Verify the complete previous graph remains intact.

Use isolated PostgreSQL.

---

# 98. Concurrent structural writes

Where practical, verify concurrent structural mutations of the same parent do
not produce:

```text
lost child

lost aggregate

invalid combined structure
```

Use existing:

```text
parent lock

SERIALIZABLE
```

and controlled concurrency handling.

Do not build a large new framework solely for this test.

---

# 99. Status mutation regression

After structural operations exist, verify:

```text
PATCH segment status
```

still works on surviving segment IDs.

A deleted segment should return:

```text
segment_not_found
```

through existing behavior.

---

# 100. Reconciliation regression

Verify structural additions do not break:

```text
POST planner/reconcile
```

on historical occurrences.

Newly created historical segments must already satisfy stable historical
status rules.

---

# 101. PlanItem creation regression

Run creation tests proving:

```text
new PlanItem occurrences
still receive exactly one default segment
```

---

# 102. Full backend suite

Run:

```text
.venv/bin/python -m unittest discover \
  -s modules/gestor_de_habitos/backend \
  -p 'test_*.py'
```

Report skips honestly.

---

# 103. PostgreSQL 16 integration

Use the existing isolated PostgreSQL harness.

Verify actual schema:

```text
001
→ 002
→ 003
→ 004
```

Do not use `vcs_dev`.

---

# 104. Syntax / consistency

Run:

```text
.venv/bin/python -m compileall -q \
  modules/gestor_de_habitos/backend
```

and:

```text
git diff --check
```

Verify frontend files remained unchanged.

---

# 105. Expected state after this phase

Expected architecture:

```text
schema 004
✅

backend read
✅

frontend read/display
✅

PlanItem creation
✅

segment status
✅

persistent reconciliation
✅

frontend status integration
✅

backend translate
✅

backend atomic structural replacement
✅

backend reset segmentation
✅

frontend structural editor
❌

Apply Week/Future segment-aware
❌

conflict resolution engine
❌

planner chronology cleanup
❌
```

---

# 106. Still not runtime-ready

Do NOT apply migration 004 to real `vcs_dev`.

Remaining incompatible paths still include:

```text
frontend structural editing

legacy parent schedule mutation paths

Apply Week

Apply Future

conflict resolution

edit_without_occurrence legacy conflict write
```

Do not claim full runtime readiness.

---

# 107. Documentation

Update documentation only if necessary to describe:

```text
structural command APIs

final-state replacement semantics

temporary conflict rejection

remaining legacy incompatible paths
```

Do not create speculative feature docs.

---

# 108. Git rules

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

# 109. Completion report

At completion provide:

## Files changed

List every created/modified file.

## Structural API

Report final routes and payloads for:

```text
translate

replace structure

reset segmentation
```

## Final-state semantics

Explain:

```text
how existing IDs are preserved

how new IDs are generated

how omitted children are deleted

how statuses are preserved

how new segment statuses are validated
```

## Translation

Explain:

```text
delta calculation

duration equality

ID preservation

status preservation

gap preservation
```

## Resize

Explain how:

```text
manual final-state resize
```

works without scaling children.

## Reset

Explain:

```text
previous aggregate inheritance

new UUID

new range

validation
```

## Conflict guard

Explain:

```text
candidate segment checking

gap-aware behavior

blocker response

rejection-only semantics
```

## Transactions

Explain:

```text
lock ordering

SERIALIZABLE behavior

atomic replacement
```

## Tests

Give exact commands and results.

## PostgreSQL verification

Describe real:

```text
001 → 004

translate → GET

structure replace → GET

reset → GET
```

verification.

## Safety

Confirm:

```text
vcs_dev not queried or modified

legacy PlanItems preserved

migrations unchanged

frontend unchanged

no occurrence date mutation

no Apply Week/Future segment support

no priority/user-forced conflict resolution

no automatic conflict split/trim

no pause/resume
```

## Remaining incompatibilities

List what still prevents schema 004 from becoming active on real `vcs_dev`.

## Git

Show:

```text
git diff --stat

git status --short --untracked-files=all
```

No commit.

No push.

---

# 110. Definition of done

This task is complete when:

```text
pure translation moves parent + all segments by one delta

translation preserves IDs/statuses/gaps

duration-changing translation is rejected

manual structural edits submit one complete final state

existing segment identities are validated and preserved

new segments receive backend UUIDs

omitted existing children are removed atomically

zero-segment final state is rejected

all final segments fit inside parent envelope

siblings cannot overlap

adjacency is valid

completed-time integrity survives time edits

frozen history remains immutable

yesterday transient state requires reconciliation

parent aggregate is recalculated from final children

structural conflicts use actual segments

conflicts are rejected, not resolved

reset segmentation produces one new child using prior aggregate

all structural writes are atomic

schema-004 structural paths are verified on PostgreSQL 16

frontend remains unchanged

vcs_dev remains untouched
```

---

# Final principle

A structural edit is not:

```text
a sequence of partially persisted little edits
```

It is:

```text
one proposed final temporal structure
        ↓
validate complete graph
        ↓
persist atomically
```

The frontend may eventually let the user freely manipulate a draft.

PostgreSQL never stores that draft until it satisfies all invariants.

For a pure movement:

```text
translate the complete occurrence
```

For a resize:

```text
the user provides a valid final structure
```

For a reset:

```text
discard the old segmentation
and deliberately return to one segment
```

No operation may guess how the user's time should be redistributed.
