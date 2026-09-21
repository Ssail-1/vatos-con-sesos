# CURRENT TASK

## OccurrenceSegment v1 — Segment Status Mutation + Persistent Reconciliation

### Objective

Implement the authoritative backend behavior for:

```text
OccurrenceSegment status mutation
+
persistent temporal reconciliation
+
atomic Occurrence aggregate updates
```

This phase replaces the conceptual write:

```text
Occurrence.status = X
```

with:

```text
OccurrenceSegment.status = X
        ↓
derive_occurrence_status(...)
        ↓
Occurrence.status = aggregate
        ↓
COMMIT
```

It also moves temporal reconciliation into persistent backend domain behavior:

```text
pending
→ not_completed

in_progress
→ not_finished
```

for past dates.

This phase is BACKEND ONLY.

Frontend integration comes in a later task.

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

Also inspect:

```text
modules/gestor_de_habitos/db/migrations/004_occurrence_segments.sql
```

and all work completed in previous OccurrenceSegment phases, especially:

```text
occurrence_segment_domain.py

plan_item_creation_service.py

planner_state_service.py

planner_state_repository.py

scheduling_policy.py
```

Read the relevant existing tests before implementation.

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
backend segment-status mutation

temporal-zone validation for segment statuses

completed-time validation

aggregate recalculation

atomic parent + child persistence

read-only segment conflict guard for status activation

persistent reconciliation service

explicit reconciliation endpoint

backend tests

isolated PostgreSQL 16 verification
```

Do NOT implement:

```text
segment time editing

segment create/delete UI/API

split

trim

translate

resize

reset segmentation

Apply Week segment behavior

Apply Future segment behavior

priority conflict resolution

user-forced conflict resolution

structural conflict engine

frontend integration

pause/resume

live tracking
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

Use:

```text
isolated PostgreSQL 16
```

for actual schema-004 write verification.

Do not expose credentials or private `.env` contents.

---

# 3. Migrations remain immutable

Do NOT modify:

```text
001_initial_schema.sql
002_fix_occurrence_status_context.sql
003_multi_slot_scheduling.sql
004_occurrence_segments.sql
```

If a genuine defect is discovered:

```text
STOP before modifying the migration
```

and report:

```text
finding
impact
alternatives
recommendation
```

---

# 4. Existing aggregate domain is authoritative

Reuse:

```text
derive_occurrence_status(...)
```

from the completed OccurrenceSegment backend domain.

Do NOT create a second aggregate implementation.

Do NOT derive aggregate status inside:

```text
repository SQL
Flask route
frontend
planner-state renderer
```

---

# 5. Temporal phases

Use the approved explicit phases:

```text
future
current_day
previous_editable_day
frozen_history
```

Do not replace them with an ambiguous boolean such as:

```text
is_historical
```

---

# 6. Temporal-zone derivation

Backend must determine the phase from:

```text
occurrence.occurrence_date
+
authoritative current date/time
```

Conceptually:

```text
date > today
→ future

date == today
→ current_day

date == yesterday
→ previous_editable_day

date < yesterday
→ frozen_history
```

Do not trust a public API caller to declare the temporal phase.

---

# 7. Clock/date authority

Do NOT accept arbitrary values such as:

```text
today
now
temporalPhase
```

from public request payloads.

The backend determines current date/time.

For deterministic testing, use a small injectable clock/time provider or
equivalent existing project mechanism.

Avoid hidden calls to the wall clock throughout domain logic.

Prefer:

```text
one authoritative now value per operation
```

from which:

```text
today
current time
temporal phase
```

are derived coherently.

Do not expand this task into the final production timezone/job architecture.

If the project currently relies on system-local application time, preserve
that convention and document it.

---

# 8. Segment status mutation endpoint

Introduce an explicit backend endpoint for changing a persisted segment
status.

Preferred contract:

```text
PATCH /api/occurrence-segments/<segment_id>/status
```

Payload:

```json
{
  "status": "completed"
}
```

If repository routing conventions strongly justify a minor naming variation,
keep the semantics equivalent and report the final route.

Do NOT expose parent aggregate status as directly writable.

---

# 9. Successful status response

A successful mutation should return enough authoritative information to
confirm both levels.

Conceptually:

```json
{
  "status": "ok",
  "occurrenceId": "<uuid>",
  "segmentId": "<uuid>",
  "segmentStatus": "completed",
  "occurrenceStatus": "completed"
}
```

Exact envelope may follow existing API conventions.

Do not return a value that suggests parent status was independently chosen.

---

# 10. Valid status values

The endpoint accepts only:

```text
pending
in_progress
completed
not_completed
not_finished
cancelled
```

Unknown values are rejected.

Do not add aliases.

---

# 11. FUTURE status rules

For:

```text
future
```

allowed stable segment statuses are:

```text
pending
cancelled
```

Reject:

```text
in_progress
completed
not_completed
not_finished
```

Do not silently transform them.

---

# 12. CURRENT_DAY status rules

For:

```text
current_day
```

the six statuses may be used:

```text
pending
in_progress
completed
not_completed
not_finished
cancelled
```

subject to all integrity rules in this task.

---

# 13. PREVIOUS_EDITABLE_DAY status rules

For:

```text
previous_editable_day
```

allowed stable statuses are:

```text
completed
not_completed
not_finished
cancelled
```

Reject:

```text
pending
in_progress
```

as persisted stable history.

The user may still correct the interpretation of what happened while the day
remains editable.

---

# 14. FROZEN_HISTORY

For:

```text
frozen_history
```

status mutation is forbidden.

Reject:

```text
PATCH segment status
```

even if the requested status equals the currently stored status.

Frozen history is read-only.

---

# 15. Completed current-time rule

A segment may be persisted as:

```text
completed
```

only if:

```text
segment.endDateTime <= now
```

This validation is segment-level.

Do NOT use:

```text
occurrence.endDateTime
```

for this rule.

Example:

```text
Occurrence:
13:00–17:00

now:
15:00

Seg 1:
13:00–14:00
→ completed allowed

Seg 2:
15:30–17:00
→ completed NOT allowed
```

The parent general envelope may extend into the future.

---

# 16. Do not invent additional temporal restrictions

Do not add unapproved rules such as:

```text
in_progress requires current time inside segment

pending cannot exist before segment start

completed requires segment start before now
```

unless already present in approved normative documentation.

Implement only approved integrity rules.

---

# 17. Status mutation operates on one segment

The public mutation target is:

```text
segmentId
```

not:

```text
occurrenceId
```

The endpoint changes exactly one segment requested by the user.

The parent aggregate is then recomputed.

---

# 18. Parent aggregate update

After candidate segment status changes:

```text
derive_occurrence_status(all parent segments, phase)
```

and persist:

```text
occurrences.status = derived result
```

in the same transaction.

Never persist:

```text
segment status
```

without the corresponding aggregate update.

---

# 19. Preserve conflict metadata

A normal manual segment-status correction must NOT automatically clear or
rewrite:

```text
conflict_reason
source_occurrence_id
origin_reason
last_conflict_action
```

Those fields have separate semantics.

Status correction is not a new conflict event by itself.

---

# 20. Structural data remains unchanged

Status mutation must NOT modify:

```text
occurrence_date

occurrence.start_time

occurrence.end_time

segment.start_time

segment.end_time

segment.id

source_generation_slot_id
```

This task changes status only.

---

# 21. Transaction and locking

Status mutation must be atomic.

Use the established transaction strategy:

```text
SERIALIZABLE
```

where appropriate.

Conceptually:

```text
1. identify parent
2. lock parent
3. lock its segments deterministically
4. derive temporal phase
5. validate requested status
6. validate temporal integrity
7. validate blocking conflicts when required
8. build candidate segment state
9. derive parent aggregate
10. persist child + parent
11. COMMIT
```

Use a deterministic lock order.

---

# 22. Parent lock protects aggregate

A segment mutation must lock its parent before final aggregate derivation.

Two concurrent writers must not independently derive and overwrite:

```text
Occurrence.status
```

from different child snapshots.

---

# 23. Read all sibling segments before aggregate

Aggregate derivation uses:

```text
all persisted segments belonging to the parent
```

with the requested segment replaced by its candidate status.

Do not derive only from the changed child.

---

# 24. No zero-segment state

This phase does not delete segments.

Nevertheless, continue treating:

```text
0 segments
```

as invalid.

Do not fabricate a segment if corruption is encountered.

---

# 25. Status occupation semantics

Canonical blocking statuses:

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

Reuse the authoritative backend scheduling definition where appropriate.

Do not create another divergent status list.

---

# 26. Status changes can change occupation

A transition such as:

```text
cancelled
→ pending
```

or:

```text
not_completed
→ completed
```

can make a segment occupy time again.

VCS must not create an unresolved schedule overlap by changing status.

---

# 27. Minimal segment-aware conflict guard

This phase MAY implement the minimum segment-aware overlap query necessary to
validate status mutation.

This is:

```text
CONFLICT DETECTION FOR REJECTION ONLY
```

It is NOT the new conflict-resolution engine.

When the candidate segment status is blocking:

```text
check overlap against other blocking persisted segments
```

for the same date.

Use actual:

```text
OccurrenceSegment.start_time
OccurrenceSegment.end_time
OccurrenceSegment.status
```

not parent envelopes.

---

# 28. Conflict guard semantics

Use half-open overlap semantics:

```text
[start, end)
```

Adjacency is valid.

Example:

```text
08:00–09:00
09:00–10:00
```

is NOT conflict.

---

# 29. Exclude the segment's own parent correctly

Sibling segments cannot overlap due schema constraints.

The status conflict guard is concerned with occupying segments belonging to
other logical occurrences.

Do not report the segment itself as its own conflict.

Do not treat gaps in the parent general envelope as occupied time.

---

# 30. No priority resolution during status mutation

If activating/changing a segment to a blocking status would overlap another
blocking segment:

```text
REJECT
```

Do NOT:

```text
apply priority_override

apply user_forced_override

cancel blocker

split blocker

trim blocker

modify blocker status

move blocker
```

Conflict resolution belongs to a later phase.

---

# 31. Segment status conflict response

Use a controlled conflict response.

Preferred code:

```text
segment_status_conflict
```

Return sufficient blocker information for later frontend UX.

Conceptually each blocker should include:

```text
occurrenceId
segmentId
planItemId
date
startTime
endTime
status
```

This is informative only.

Do not implement the future authorization/confirmation handshake yet.

---

# 32. Conflict rejection is atomic

If status activation conflicts:

```text
target segment unchanged

parent aggregate unchanged

blockers unchanged

metadata unchanged
```

No partial write is allowed.

---

# 33. Existing conflict engine remains untouched

Do NOT reinterpret this minimal overlap guard as permission to rewrite:

```text
PlanItem creation conflict engine

priority override

Apply Week conflicts

Apply Future conflicts

split/trim resolution
```

Those remain later work.

---

# 34. Persistent reconciliation service

Implement one backend service responsible for temporal reconciliation.

It must operate on persisted:

```text
OccurrenceSegments
```

not directly on parent status.

---

# 35. Reconciliation mapping

For every historical segment requiring reconciliation:

```text
pending
→ not_completed
```

```text
in_progress
→ not_finished
```

Preserve:

```text
completed
not_completed
not_finished
cancelled
```

---

# 36. Reconciliation is segment-by-segment

Do NOT perform:

```text
Occurrence.status pending → not_completed
```

directly.

Correct flow:

```text
reconcile child statuses
        ↓
derive_occurrence_status(children, historical phase)
        ↓
persist parent aggregate
```

---

# 37. Reconciliation target dates

A reconciliation run must correctly handle every persisted occurrence with:

```text
occurrence_date < today
```

that may require historical normalization/integrity checking.

This includes:

```text
yesterday
→ PREVIOUS_EDITABLE_DAY

older dates
→ FROZEN_HISTORY
```

This allows recovery if VCS was not opened for several days.

---

# 38. Yesterday reconciliation

For yesterday:

```text
pending
→ not_completed

in_progress
→ not_finished
```

then derive aggregate using:

```text
previous_editable_day
```

The date remains editable after reconciliation.

---

# 39. Pre-frozen / older-date reconciliation

For dates already:

```text
frozen_history
```

run the same transient mapping idempotently and derive the aggregate using:

```text
frozen_history
```

This represents the required final reconciliation/integrity pass before
history is considered stable.

---

# 40. Reconciliation idempotency

Running reconciliation multiple times with the same effective `now` must not
continue changing data.

Example:

```text
completed
not_completed
not_finished
cancelled
```

remain unchanged.

A second run after:

```text
pending → not_completed
```

must perform no further status transition.

---

# 41. Reconciliation aggregate integrity

For every parent processed by reconciliation:

```text
derive the expected historical aggregate
```

after child normalization.

If the persisted parent aggregate differs:

```text
update it inside the explicit reconciliation transaction
```

This is allowed because reconciliation is an explicit write operation.

Do NOT move this repair into GET planner-state.

---

# 42. No reconciliation of today/future

Persistent reconciliation must NOT transform statuses for:

```text
current_day
future
```

---

# 43. Explicit reconciliation endpoint

Expose an explicit backend command endpoint.

Preferred contract:

```text
POST /api/planner/reconcile
```

No client-provided date is required.

The backend derives current date/time.

If existing route conventions justify a minor naming variation, preserve the
same semantics and report it.

---

# 44. Reconciliation response

Return a small operational summary.

Conceptually:

```json
{
  "status": "ok",
  "updatedOccurrences": 3,
  "updatedSegments": 4
}
```

Exact naming may follow existing API conventions.

Do not return an entire planner-state response from the reconciliation
command.

The caller can perform:

```text
POST reconcile
→ GET planner-state
```

---

# 45. Reconciliation is not part of GET

Keep:

```text
GET /api/planner-state
```

read-only.

Do NOT invoke persistent reconciliation as a hidden side effect of GET.

---

# 46. No public arbitrary-date reconciliation

Do not allow API clients to submit:

```json
{
  "today": "2035-01-01"
}
```

and thereby force history transitions.

Tests may inject a clock at service/application construction level.

Public API uses backend time authority.

---

# 47. Reconciliation transaction strategy

A reconciliation run may affect multiple parents.

Use coherent transactional behavior.

At minimum:

```text
lock affected parents deterministically

lock their segments deterministically

normalize children

derive aggregates

persist

COMMIT
```

Avoid different lock ordering from segment-status mutation.

---

# 48. Reconciliation failure

If reconciliation fails partway through its transactional unit:

```text
do not leave a parent with reconciled children
and stale aggregate
```

Parent/children changes must remain atomic.

Choose transaction granularity deliberately and document it.

For the current MVP, a single reconciliation command transaction is acceptable
if consistent with existing service architecture and dataset scale.

Do not optimize prematurely.

---

# 49. Historical status mutation after reconciliation

After reconciliation, yesterday remains editable.

The user may later correct a segment among:

```text
completed
not_completed
not_finished
cancelled
```

Status mutation must then recompute the historical aggregate.

Example:

```text
Seg 1 completed
Seg 2 not_completed
→ parent not_finished
```

If the user corrects Seg 2:

```text
not_completed
→ completed
```

result:

```text
completed + completed
→ completed
```

---

# 50. Historical transient corruption

If a status-mutation request for:

```text
previous_editable_day
```

encounters sibling segments still persisted as:

```text
pending
in_progress
```

do NOT silently reconcile unrelated siblings inside the status endpoint.

Return a controlled error indicating reconciliation is required.

Preferred code:

```text
temporal_reconciliation_required
```

The explicit reconciliation command remains the authority for those
transitions.

---

# 51. Frozen mutation remains forbidden after reconciliation

Reconciliation may normalize frozen history.

It does NOT make frozen history user-editable.

After reconciliation:

```text
PATCH segment status on frozen date
→ rejected
```

---

# 52. Conflict metadata during reconciliation

Reconciliation does NOT represent a conflict event.

Do not clear or rewrite:

```text
conflict_reason
source_occurrence_id
origin_reason
last_conflict_action
```

because reconciliation changed segment status.

---

# 53. No realized-time invention

Reconciliation changes only status.

Do NOT modify:

```text
segment.start_time
segment.end_time
occurrence.start_time
occurrence.end_time
```

to invent when work actually happened.

---

# 54. No structural segmentation during reconciliation

Do NOT:

```text
split

merge

trim

delete

create
```

segments during reconciliation.

Only transform:

```text
status
```

and recompute aggregate.

---

# 55. Repository responsibilities

Repository code should provide focused persistence operations such as:

```text
lock segment + parent

list sibling segments

find blocking overlapping segments

list reconciliation candidates

update segment status

update parent aggregate
```

Exact organization may follow repository conventions.

Do NOT place temporal/domain precedence rules inside SQL repositories.

---

# 56. Service responsibilities

Service/domain layers own:

```text
temporal phase

allowed status rules

completed-time validation

candidate final state

aggregate derivation

reconciliation mapping

conflict rejection semantics

transaction orchestration
```

Keep Flask routes thin.

---

# 57. Existing planner-state behavior must remain intact

Do not regress:

```text
segments[]

conflictContext

originReason

lastConflictAction

sourceGenerationSlotId

parent aggregate read
```

---

# 58. Existing PlanItem creation must remain intact

Do not regress the previous phase:

```text
non-conflicting Create PlanItem
→ parent + default segment
```

The legacy conflict-write guard must remain active.

Do NOT re-enable:

```text
apply_priority_overrides()
```

from schema-004 PlanItem creation.

---

# 59. No frontend changes

Do NOT modify frontend files in this task.

Do not wire:

```text
status buttons

segment status rows

bootstrap reconciliation
```

yet.

That will be the next frontend integration phase.

---

# 60. Pure domain tests

Add focused tests for temporal status authorization.

At minimum:

```text
FUTURE:
pending allowed
cancelled allowed
completed rejected
in_progress rejected
not_completed rejected
not_finished rejected

CURRENT_DAY:
all six accepted subject to completed-time rule

PREVIOUS_EDITABLE_DAY:
completed allowed
not_completed allowed
not_finished allowed
cancelled allowed
pending rejected
in_progress rejected

FROZEN_HISTORY:
mutation rejected
```

---

# 61. Completed-time tests

Test current day:

```text
segment ending before now
→ completed allowed

segment ending exactly at now
→ completed allowed

segment ending after now
→ completed rejected
```

Use an injected deterministic `now`.

Do not rely on test wall-clock timing.

---

# 62. Aggregate mutation tests

Verify a segment update recalculates the parent.

Examples:

```text
CURRENT_DAY

completed + pending
→ parent in_progress

pending + cancelled
→ parent pending

not_completed + cancelled
→ parent not_completed
```

And historical:

```text
completed + not_completed
→ parent not_finished

completed + completed
→ parent completed
```

---

# 63. Single-segment mutation tests

Verify:

```text
Segment pending
→ completed
```

produces:

```text
Segment completed
Occurrence completed
```

when temporally valid.

---

# 64. Metadata preservation tests

Changing segment status must preserve existing:

```text
conflict_reason
source_occurrence_id
origin_reason
last_conflict_action
source_generation_slot_id
```

unless another already-approved rule explicitly changes them.

---

# 65. Conflict guard tests

Use schema 004 data such as:

```text
Occurrence A
Seg A:
08:00–09:00 pending

Occurrence B
Seg B:
08:30–09:30 cancelled
```

Attempt:

```text
Seg B cancelled → pending
```

Expected:

```text
409 segment_status_conflict
```

with no writes.

Also verify:

```text
09:00–10:00
```

adjacent to:

```text
08:00–09:00
```

is accepted.

---

# 66. Gap-aware conflict test

Prove the guard uses segments rather than parent envelope.

Example:

```text
Occurrence A:
08:00–12:00

segments:
08:00–09:00 pending
11:00–12:00 pending
```

Another segment:

```text
09:30–10:30 cancelled
```

Changing it to:

```text
pending
```

must be allowed because the envelope gap is not occupied.

---

# 67. Non-blocking transition tests

Verify transitions to:

```text
cancelled
not_completed
```

do not require conflict resolution merely because their interval overlaps
another occurrence.

They are non-blocking statuses.

---

# 68. Reconciliation mapping tests

For a historical date:

```text
pending
→ not_completed

in_progress
→ not_finished

completed
→ completed

not_completed
→ not_completed

not_finished
→ not_finished

cancelled
→ cancelled
```

---

# 69. Reconciliation aggregate tests

Examples:

```text
before:

completed
pending

after reconciliation:

completed
not_completed

parent:
not_finished
```

and:

```text
before:

in_progress
cancelled

after:

not_finished
cancelled

parent:
not_finished
```

---

# 70. Reconciliation idempotency test

Run reconciliation twice with the same deterministic `now`.

Second run must produce:

```text
0 additional segment transitions
```

and no semantic data difference.

---

# 71. Missed-days test

Simulate VCS not opening for multiple days.

Create persisted occurrences on:

```text
today - 1
today - 2
today - 5
```

with transient statuses.

One reconciliation call must correctly normalize all historical dates.

Yesterday remains editable by policy.

Older dates are frozen after normalization.

---

# 72. Today/future reconciliation test

Verify reconciliation does NOT modify:

```text
today
future dates
```

---

# 73. Reconciliation rollback test

Force a failure after at least one candidate has been processed but before
commit.

Verify no persisted parent/segment pair is left partially reconciled.

Use isolated PostgreSQL 16.

---

# 74. Real PostgreSQL 16 endpoint test

Against:

```text
001 → 002 → 003 → 004
```

verify actual HTTP/service behavior for:

```text
PATCH segment status
POST planner reconciliation
GET planner-state
```

without using `vcs_dev`.

---

# 75. Round-trip status mutation

Verify:

```text
PATCH segment
→ success
→ GET planner-state
```

returns:

```text
new segment status
correct parent aggregate
same segment ID
same time interval
same metadata
```

---

# 76. Round-trip reconciliation

Verify:

```text
POST reconcile
→ GET planner-state
```

returns reconciled:

```text
child statuses
parent aggregates
```

persistently.

A second GET must return the same data.

---

# 77. Concurrency test

Where practical, add focused PostgreSQL coverage proving two concurrent status
writers on segments of the same parent cannot produce a lost aggregate.

The implementation should use:

```text
parent lock
+
SERIALIZABLE
```

and controlled serialization handling consistent with project patterns.

Do not build a large concurrency framework solely for this test if existing
infrastructure cannot support it cleanly.

At minimum document and test the locking order.

---

# 78. Existing tests

Run the complete backend suite.

Update existing tests only where approved status-write behavior has changed.

Do not rewrite unrelated expectations.

---

# 79. PostgreSQL integration harness

Reuse the existing isolated PostgreSQL 16 infrastructure where practical.

Do not create another unrelated database test framework.

---

# 80. No fake runtime readiness

At the end of this phase, schema 004 is still NOT ready to replace the real
runtime database.

Remaining incompatible write paths include at least:

```text
frontend status mutation wiring

structural segment mutations

Apply Week

Apply Future

segment-aware conflict resolution
```

Do not claim otherwise.

---

# 81. Expected state after this phase

Expected architecture:

```text
schema 004
✅

backend read
✅

frontend read/display
✅

PlanItem creation + default segment
✅

aggregate domain
✅

segment status backend mutation
✅

persistent reconciliation backend
✅

frontend status/reconciliation integration
❌

structural segment mutation
❌

Apply Week/Future segment-aware
❌

conflict resolution engine
❌
```

---

# 82. Documentation

Update documentation only where necessary to explain:

```text
segment status endpoint

reconciliation command

clock/time authority

temporary conflict rejection
```

Do not create speculative future documentation.

If a production-scale concern is discovered:

```text
document it in the existing production concerns location
```

rather than expanding current scope.

---

# 83. Git rules

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

# 84. Test commands

Run focused tests for:

```text
segment status domain

segment status service/API

reconciliation

conflict guard
```

Run the full backend suite:

```text
.venv/bin/python -m unittest discover \
  -s modules/gestor_de_habitos/backend \
  -p 'test_*.py'
```

Run the schema-004 PostgreSQL tests relevant to this phase.

Run:

```text
.venv/bin/python -m compileall -q \
  modules/gestor_de_habitos/backend
```

and:

```text
git diff --check
```

Verify frontend files remain unchanged.

---

# 85. Completion report

At completion provide:

## Files changed

List every created/modified file.

## Status endpoint

Report:

```text
final route

request payload

success payload

error codes
```

## Temporal rules

Explain:

```text
future

current day

previous editable day

frozen history

completed end-time rule
```

## Aggregate

Explain:

```text
how all sibling segments are loaded

how aggregate is derived

how parent + child are committed atomically
```

## Conflict guard

Explain:

```text
when it runs

how blockers are queried by segment

response shape

why it is detection/rejection only
```

## Reconciliation

Explain:

```text
endpoint

date authority

pending → not_completed

in_progress → not_finished

yesterday handling

older frozen handling

idempotency
```

## PostgreSQL verification

Describe actual:

```text
001 → 004

PATCH segment status

POST reconcile

GET planner-state
```

tests.

## Tests

Give exact commands and results.

## Safety

Confirm:

```text
vcs_dev not queried or modified

migrations unchanged

frontend unchanged

no segment time/structure mutations implemented

no split/trim/resize/reset

Apply Week/Future unchanged

priority/user-forced conflict resolution not implemented

PlanItem legacy override remains guarded
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

# 86. Definition of done

This task is complete when:

```text
segment status has an explicit backend mutation path

parent status is never independently chosen by that mutation

all sibling segments participate in aggregate derivation

temporal-zone status rules are enforced

completed segment future-end is rejected

frozen history is immutable

status activation cannot create unresolved segment overlap

conflict guard uses segments rather than parent envelopes

reconciliation persists pending → not_completed

reconciliation persists in_progress → not_finished

reconciliation recalculates parent aggregates

reconciliation handles missed historical days

reconciliation is idempotent

GET planner-state remains read-only

schema-004 status/reconciliation paths are verified on PostgreSQL 16

vcs_dev remains untouched

no structural segment editing or conflict resolution was implemented
```

---

# Final principle

VCS no longer changes the meaning of an occurrence by writing directly to:

```text
Occurrence.status
```

The operational truth is:

```text
OccurrenceSegment.status
```

and the parent is a derived summary:

```text
Segments
    ↓
derive_occurrence_status(...)
    ↓
Occurrence.status
```

Temporal reconciliation follows the same rule:

```text
reconcile children
        ↓
derive parent
        ↓
persist together
```

While the day remains editable:

> VCS protects temporal integrity, but allows the user to correct the
> interpretation of what happened.

Frozen history remains immutable.
