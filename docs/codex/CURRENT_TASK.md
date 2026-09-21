# CURRENT TASK

## OccurrenceSegment v1 — Frontend Segment Status + Reconciliation Integration

### Objective

Connect the existing frontend OccurrenceSegment read/display model to the
authoritative backend write behavior already implemented for:

```text
OccurrenceSegment status mutation
+
persistent temporal reconciliation
```

This phase must replace legacy frontend parent-status writes with:

```text
Segment status request
        ↓
backend validation
        ↓
backend aggregate recalculation
        ↓
GET planner-state
        ↓
frontend hydrate
```

It must also change planner bootstrap from:

```text
GET planner-state
→ hydrate
```

to:

```text
POST planner/reconcile
→ GET planner-state
→ hydrate
```

This phase is an INTEGRATION phase.

It does NOT implement structural segment editing or conflict resolution.

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

Also inspect the completed backend implementation for:

```text
PATCH /api/occurrence-segments/<segment_id>/status

POST /api/planner/reconcile

GET /api/planner-state
```

Read the existing frontend mutation/bootstrap tests before implementation.

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
frontend API integration for segment status

frontend API integration for reconciliation

bootstrap reconciliation flow

single-segment status control migration

multi-segment child status controls

authoritative GET-after-write hydration

minimal CORS support required by these routes

frontend tests

browser verification
```

Do NOT implement:

```text
segment time editing

segment create/delete

split

trim

translate

resize

reset segmentation

Apply Week segment behavior

Apply Future segment behavior

priority conflict resolution

user-forced conflict resolution

conflict confirmation handshake

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

Do NOT clean or mutate real development data.

Frontend tests should use:

```text
mocks
fixtures
existing frontend test infrastructure
```

If real schema-004 verification is needed, use isolated PostgreSQL 16 only.

---

# 3. Migrations remain immutable

Do NOT modify:

```text
001_initial_schema.sql
002_fix_occurrence_status_context.sql
003_multi_slot_scheduling.sql
004_occurrence_segments.sql
```

---

# 4. Preserve completed backend semantics

Do NOT redesign the completed backend behavior.

Existing authoritative routes are:

```text
PATCH /api/occurrence-segments/<segment_id>/status

POST /api/planner/reconcile

GET /api/planner-state
```

Frontend must consume them.

Do not create competing client-side domain rules.

---

# 5. CORS

The browser frontend runs from a different local origin than Flask.

Add only the minimum backend CORS support required for the two newly consumed
routes:

```text
PATCH /api/occurrence-segments/<segment_id>/status

POST /api/planner/reconcile
```

Follow the existing CORS/origin architecture.

Do NOT:

```text
allow every origin

hard-code unrelated origins

redesign global CORS

change security policy
```

Preserve:

```text
VCS_ALLOWED_ORIGINS
```

or the existing equivalent source of allowed origins.

Add/update CORS tests as necessary.

---

# 6. Frontend API client

Extend the existing planner API layer with focused operations conceptually
equivalent to:

```text
updateSegmentStatus(segmentId, status)

reconcilePlanner()
```

Use existing request/error conventions.

Do not call `fetch()` directly from view modules if the current architecture
uses a centralized API module.

---

# 7. Segment status request

Request:

```text
PATCH /api/occurrence-segments/<segmentId>/status
```

Payload:

```json
{
  "status": "<canonical-status>"
}
```

Do not send:

```text
occurrenceStatus

temporalPhase

now

today

startTime

endTime
```

The backend owns those decisions.

---

# 8. Reconciliation request

Request:

```text
POST /api/planner/reconcile
```

with no domain payload.

Do not send:

```text
today

now

timezone

temporalPhase
```

The backend determines current temporal context.

---

# 9. Backend remains status authority

Frontend must NOT compute the new parent aggregate and write it.

After a status mutation:

```text
PATCH segment status
→ GET planner-state
→ hydrate authoritative result
```

Do not perform:

```text
occurrence.status = localDerivedStatus
```

as persisted/domain truth.

---

# 10. Avoid optimistic domain mutation

Prefer the existing authoritative mutation pattern:

```text
request mutation
→ request planner-state
→ hydrate
```

Do not permanently mutate local segment/parent status before backend success.

Temporary UI pending/loading state is allowed.

---

# 11. Single-segment occurrence status control

For an occurrence with exactly one segment:

```text
the existing parent-row status control may remain visually similar
```

but its semantics must change.

BEFORE:

```text
control
→ mutate occurrence.status locally/legacy
```

NOW:

```text
control
→ identify persisted Segment 1
→ PATCH Segment 1.status
→ GET planner-state
→ hydrate
```

The occurrence parent remains the aggregate.

---

# 12. Single-segment identity

Do not infer Segment 1 using:

```text
occurrence times

array index alone

synthetic ID
```

Use:

```text
occurrence.segments[0].id
```

from the persisted backend contract.

The fact that there is exactly one child allows the UX proxy.

---

# 13. Multi-segment parent status

For a multi-segment occurrence:

```text
Occurrence.status
```

remains:

```text
read-only aggregate information
```

Do NOT make the parent status badge/button mutate all segments.

Do NOT introduce a bulk-status action in this phase.

---

# 14. Multi-segment child status controls

Each expanded segment row should expose its own status control.

Conceptually:

```text
Seg 1 | 13:00 | 14:00 | completed

Seg 2 | 14:30 | 16:00 | pending

Seg 3 | 16:00 | 17:00 | pending
```

Each control operates only on:

```text
its persisted segment ID
```

---

# 15. Segment status choices

Use only canonical statuses:

```text
pending
in_progress
completed
not_completed
not_finished
cancelled
```

Do not add frontend aliases.

---

# 16. Temporal rules remain backend authoritative

The frontend may hide/disable obviously unavailable options for UX if current
temporal utilities already support doing so cleanly.

However:

```text
backend response is authoritative
```

Do not duplicate the entire temporal validation engine in the frontend.

If frontend and backend disagree:

```text
show backend error

refresh authoritative planner-state when appropriate
```

Do not override the backend.

---

# 17. FUTURE UX

Future segments ultimately support stable statuses:

```text
pending
cancelled
```

The frontend may limit the visible choices accordingly if it can determine the
zone using existing temporal utilities.

Do not implement new time architecture merely for this filtering.

Backend still validates every request.

---

# 18. CURRENT_DAY UX

Current-day segment controls may expose the six canonical statuses according
to existing UI conventions.

Backend enforces:

```text
completed end-time rule

conflict integrity

other temporal rules
```

---

# 19. PREVIOUS_EDITABLE_DAY UX

Yesterday remains editable.

Stable choices:

```text
completed
not_completed
not_finished
cancelled
```

Do not offer:

```text
pending
in_progress
```

if existing frontend temporal state can determine this cleanly.

Backend remains authoritative.

---

# 20. FROZEN_HISTORY UX

Frozen segment statuses are read-only.

Do not send PATCH requests from frozen rows.

The backend already rejects them; frontend should also avoid presenting an
active control where possible.

---

# 21. Existing status progression

Inspect the current status-control UX.

If it uses:

```text
advanceOccurrenceStatus()
```

or another cyclic transition mechanism, preserve its familiar interaction only
where doing so maps unambiguously to the valid segment statuses.

Do NOT preserve an old status cycle if it:

```text
writes parent status

offers invalid temporal states

bypasses backend
```

A small explicit segment-status control is preferable to maintaining invalid
legacy semantics.

Do not redesign unrelated UI.

---

# 22. Remove legacy parent status writes from active frontend paths

No active frontend status control should call:

```text
setOccurrenceStatus(...)

advanceOccurrenceStatus(...)
```

in a way that directly mutates parent domain status.

If these methods remain for unrelated legacy tests/code:

```text
make them unreachable from the new active status UI
```

or remove them if safe within scope.

Document remaining legacy code.

---

# 23. Mutation coordinator

Follow existing frontend mutation architecture.

Prefer a coordinator flow equivalent to:

```text
guard double submit

PATCH segment

GET planner-state

hydrate

restore selection if still valid

release pending state
```

Do not place the entire mutation workflow in the view.

---

# 24. Double-submit protection

Prevent repeated status requests from:

```text
double click

rapid tapping

pending request
```

using the project's existing mutation/pending mechanisms.

Do not invent unrelated global state.

---

# 25. Mutation success

After successful PATCH:

```text
GET planner-state
```

must refresh:

```text
segment status

parent aggregate

monthly aggregate display

selection-dependent rendering
```

from authoritative state.

---

# 26. Preserve selection after refresh

When possible after status mutation:

```text
selectedOccurrenceId
```

should remain selected.

If a specific segment was selected and still exists:

```text
selectedSegmentId
```

should remain selected.

Do not preserve selection by array index.

Use stable persisted IDs.

---

# 27. Preserve expansion after refresh

If a multi-segment occurrence was expanded before status mutation:

```text
keep it expanded
```

when the same occurrence still exists after hydration.

Expansion remains transient frontend state.

---

# 28. Segment status conflict UX

Backend may return:

```text
409 segment_status_conflict
```

with:

```text
blockers[]
```

This phase does NOT resolve that conflict.

Frontend should:

```text
show a clear error/message

preserve authoritative current state

not retry automatically

not modify blockers
```

Do not implement:

```text
priority override

user-forced override

split

trim

move
```

from this response.

---

# 29. Conflict blocker information

If the existing UI error architecture can display concise blocker context
without a large redesign, it may use:

```text
startTime
endTime
status
```

from the returned blockers.

Do not create the final conflict-resolution modal in this phase.

A clear message is sufficient.

---

# 30. Other status API errors

Handle backend errors coherently:

```text
invalid_payload

segment_not_found

history_frozen

segment_status_not_allowed

segment_not_ended

temporal_reconciliation_required

segment_status_conflict

concurrent_conflict

persisted_state_invalid

database_unavailable
```

Do not create a unique elaborate UI for every code.

Map them into understandable existing error surfaces while preserving the
error code for debugging/tests where appropriate.

---

# 31. `temporal_reconciliation_required`

If status mutation returns:

```text
temporal_reconciliation_required
```

do NOT silently mutate siblings locally.

A reasonable integration flow is:

```text
run explicit reconciliation
→ GET planner-state
→ ask user to retry the status action
```

or fail with a clear message if automatic command orchestration would make the
interaction ambiguous.

Do not hide the fact that reconciliation occurred.

Use the simplest behavior consistent with current UI architecture and test it.

---

# 32. Bootstrap reconciliation

Planner startup should execute:

```text
POST /api/planner/reconcile
```

before the authoritative planner-state GET.

Flow:

```text
bootstrap start
        ↓
POST reconcile
        ↓
GET planner-state
        ↓
hydrate
        ↓
render
```

---

# 33. Bootstrap reconciliation result

The frontend does not need to display:

```text
updatedOccurrences
updatedSegments
```

during ordinary successful bootstrap.

The purpose is state normalization.

Do not add noisy UI such as:

```text
"4 segmentos reconciliados"
```

on every startup unless existing UX naturally supports operational notices.

---

# 34. Reconciliation failure

If:

```text
POST reconcile
```

fails because of:

```text
database unavailable

persisted invalid state

concurrency failure

unexpected backend error
```

do NOT silently continue into a normal GET and present potentially stale
historical state as fully reconciled.

Use the existing bootstrap failure/error UI.

A retry may rerun reconciliation because the command is idempotent.

---

# 35. Reconciliation idempotency in frontend

Frontend may safely call:

```text
POST reconcile
```

on every bootstrap.

Do not attempt to keep a client-side flag such as:

```text
alreadyReconciledToday
```

The backend command is authoritative and idempotent.

---

# 36. Reconciliation does not replace GET

Do not hydrate planner state from the reconciliation summary.

Always perform:

```text
GET planner-state
```

after successful reconciliation.

---

# 37. No hidden reconciliation inside unrelated UI renders

Call reconciliation from intentional orchestration points such as:

```text
bootstrap
```

or explicit recovery.

Do not call it from:

```text
render()

buildPlannerRows()

status badge formatter()
```

---

# 38. Existing frontend local reconciliation

The old frontend contains legacy local temporal reconciliation behavior.

Now that backend reconciliation exists:

```text
frontend must stop acting as independent reconciliation authority
```

Remove, disable or bypass active calls that mutate local statuses during:

```text
bootstrap

render

normal planner operation
```

Do not maintain two reconciliation authorities.

---

# 39. Reusable temporal display helpers may remain

Do not delete useful frontend utilities merely because local persistence
authority moves backend-side.

Helpers for:

```text
determining display zone

read-only/frozen presentation

labels

UI option filtering
```

may remain.

Only remove/bypass:

```text
local status mutation pretending to reconcile persisted state
```

---

# 40. Monthly aggregate

Preserve the existing monthly aggregate behavior.

Because parent aggregate is refreshed by GET:

```text
deriveAggregateOccurrenceDisplay(...)
```

should naturally consume the new authoritative parent status.

Do not make monthly aggregate read segments directly unless an approved rule
requires it.

---

# 41. `conflictContext`

Preserve completed frontend migration to:

```text
conflictContext
```

Do not reintroduce:

```text
statusContext
```

as an active frontend dependency.

---

# 42. `originReason` / `lastConflictAction`

Preserve:

```text
originReason

lastConflictAction
```

through hydrate/status refresh.

Status mutation must not cause the frontend to discard them.

---

# 43. Source provenance

Preserve:

```text
sourceGenerationSlotId
```

through mutation → GET → hydrate.

---

# 44. Multi-segment structural controls remain disabled

Continue guarding existing parent-level controls that would perform:

```text
date/time edit

recurrence edit

delete via incompatible path

legacy add behavior
```

for multi-segment occurrences where they are still unsafe.

This phase only unlocks:

```text
status mutation
```

per persisted segment.

---

# 45. Structural segment UI remains out of scope

Do NOT add controls for:

```text
Add Segment

Delete Segment

Split

Trim

Move Segment

Resize

Reset Segmentation
```

---

# 46. Conflict resolution UI remains out of scope

Do NOT implement:

```text
Ajustar

Segmentar y continuar

Finalizar y continuar

Cancelar y continuar

Confirmar corrección

priority override confirmation

user-forced override confirmation
```

---

# 47. Apply Week / Apply Future remain unchanged

Do NOT make recurring mutations segment-aware.

Continue guarding operations where existing multi-segment safety requires it.

---

# 48. No planner chronology redesign

The previous read/display phase documented that expanded child rows currently
remain grouped beneath their parent rather than globally interleaving with
other occurrences.

Do NOT solve that chronology/layout redesign in this task.

Preserve the limitation and leave it for the dedicated planner UX cleanup
phase.

---

# 49. Browser accessibility

Segment status controls must have understandable accessible names.

Do not make status mutation depend solely on:

```text
color

icon
```

Keep:

```text
keyboard accessibility

focus behavior

disabled state
```

consistent with current UI.

---

# 50. Mobile behavior

Status controls on segment rows must remain usable at the existing mobile
breakpoint.

Do not introduce horizontal overflow.

Do not redesign the entire mobile planner.

---

# 51. API tests

Add/update tests covering:

```text
PATCH segment status request

payload

backend success parsing

backend controlled error parsing

POST reconciliation

no reconciliation payload

GET-after-status mutation

POST-reconcile-before-GET bootstrap order
```

---

# 52. Bootstrap tests

Verify exact call order:

```text
1. POST reconcile
2. GET planner-state
3. hydrate
```

Do not allow GET to race ahead of reconciliation.

---

# 53. Bootstrap failure tests

Verify:

```text
reconcile fails
→ planner-state GET does not proceed as successful bootstrap
→ existing failure UI/state is used
```

Retry should be possible.

---

# 54. Single-segment status integration test

Given:

```text
Occurrence
└── one Segment pending
```

status interaction must target:

```text
segment.id
```

not:

```text
occurrence.id
```

After successful mutation + GET:

```text
segment status updated

parent aggregate updated

same occurrence selected where practical
```

---

# 55. Multi-segment status integration tests

Given:

```text
Occurrence in_progress

Seg 1 completed
Seg 2 pending
```

changing:

```text
Seg 2 pending → completed
```

must send PATCH for:

```text
Seg 2.id
```

After GET:

```text
Seg 1 completed
Seg 2 completed
Occurrence completed
```

according to backend authoritative response.

Do not calculate this result solely in frontend tests without mocking the GET
response.

---

# 56. Parent multi-segment read-only test

Verify clicking/interacting with the parent aggregate does NOT send:

```text
PATCH occurrence status

PATCH all segments
```

Parent remains informational.

---

# 57. Frozen status UI test

Frozen segment status should not present an active mutation path.

If a request is nevertheless simulated and backend rejects it:

```text
state remains unchanged
```

---

# 58. Conflict error test

Simulate:

```text
409 segment_status_conflict
```

with blockers.

Verify:

```text
no optimistic local status change survives

no blocker mutation is attempted

error is surfaced

no conflict-resolution request is invented
```

---

# 59. Concurrent conflict test

Simulate:

```text
409 concurrent_conflict
```

Frontend should:

```text
surface conflict/retry message

refresh only according to established recovery strategy
```

Do not silently retry the mutation itself.

---

# 60. Reconciliation-required test

Simulate:

```text
409 temporal_reconciliation_required
```

Verify the chosen explicit behavior is deterministic and documented.

Do not locally transform sibling statuses.

---

# 61. Local reconciliation retirement test

Update tests that previously expected frontend code to perform:

```text
pending → not_completed

in_progress → not_finished
```

locally.

New expectation:

```text
backend reconciliation
+
GET authoritative state
```

Frontend should not mutate these statuses independently.

---

# 62. Selection tests

Verify after status refresh:

```text
selectedOccurrenceId
```

survives when parent remains.

Verify:

```text
selectedSegmentId
```

survives when child remains.

If selected entity disappeared unexpectedly:

```text
clear selection safely
```

Do not retain dangling IDs.

---

# 63. Expansion tests

Verify an expanded occurrence remains expanded after:

```text
status PATCH
→ GET
→ hydrate
```

when it still exists.

---

# 64. Double-submit test

Verify rapid repeated status interaction does not generate duplicate concurrent
PATCH requests from the same control.

---

# 65. Monthly aggregate regression

Verify status refresh updates monthly presentation from refreshed parent
aggregate without changing monthly aggregate semantics.

---

# 66. CORS tests

Verify allowed frontend origin can use:

```text
PATCH segment status

POST reconciliation
```

including browser preflight where applicable.

Verify unapproved origins remain rejected according to existing policy.

Do not weaken CORS globally.

---

# 67. Frontend full suite

Run all frontend test files:

```text
for test_file in modules/gestor_de_habitos/tests/*.test.mjs
do
  node "$test_file" || exit 1
done
```

Report exact totals.

---

# 68. Backend regression

Because minimal CORS code may change backend routing, run the complete backend
suite:

```text
.venv/bin/python -m unittest discover \
  -s modules/gestor_de_habitos/backend \
  -p 'test_*.py'
```

Report skips honestly.

---

# 69. Syntax / consistency checks

Run:

```text
node --check
```

for modified JS files as appropriate.

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

# 70. Browser verification

Verify the integrated flow in a browser-compatible test environment without
using real `vcs_dev`.

At minimum inspect:

```text
desktop

mobile
```

and verify:

```text
single-segment status interaction

multi-segment status controls

parent aggregate read-only

expand/collapse preserved

selection preserved

error state

no overflow regression
```

Use mock/isolated backend state where necessary.

---

# 71. Do not apply schema 004 to real runtime

Even after frontend status/reconciliation integration succeeds:

```text
DO NOT apply migration 004 to vcs_dev
```

Structural mutations and recurring writes remain incompatible.

---

# 72. Existing data remains preserved

Do not delete legacy PlanItems.

They are intentionally retained as part of VCS development history and will
later exercise the real migration/backfill path.

---

# 73. Expected state after this phase

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

persistent backend reconciliation
✅

frontend segment-status integration
✅

bootstrap reconciliation integration
✅

structural segment mutation
❌

Apply Week/Future segment-aware
❌

conflict resolution engine
❌

planner chronology final UX
❌
```

---

# 74. Remaining legacy write code

At completion identify any active or dormant frontend paths that still
conceptually write:

```text
Occurrence.status
```

directly.

Distinguish:

```text
unreachable legacy helper
```

from:

```text
still-active incompatible path
```

No still-active parent status write should remain in normal planner status UI.

---

# 75. Documentation

Update documentation only if necessary to explain:

```text
bootstrap reconciliation

segment status mutation integration

temporary error behavior

remaining runtime incompatibilities
```

Do not create speculative feature docs.

---

# 76. Git rules

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

# 77. Completion report

At completion provide:

## Files changed

List all created/modified files.

## Bootstrap

Explain exact flow:

```text
POST reconcile

GET planner-state

hydrate
```

and failure behavior.

## API integration

Explain:

```text
segment PATCH client

reconciliation client

CORS changes
```

## Single-segment UX

Explain how the familiar status control now targets:

```text
Segment 1
```

instead of parent status.

## Multi-segment UX

Explain:

```text
parent aggregate read-only

child status controls

selection

expansion
```

## Error handling

Explain frontend behavior for:

```text
segment_status_conflict

segment_not_ended

segment_status_not_allowed

history_frozen

temporal_reconciliation_required

concurrent_conflict

database_unavailable
```

## Legacy reconciliation

Confirm whether active frontend local reconciliation has been fully removed or
bypassed.

## Legacy parent writes

List any remaining direct parent-status helpers and whether they are active or
dormant.

## Tests

Give exact commands and results.

## Browser verification

Report desktop/mobile findings.

## Safety

Confirm:

```text
vcs_dev not modified

legacy PlanItems not deleted

migrations unchanged

no structural segment mutations

no split/trim/resize/reset

Apply Week/Future unchanged

no priority/user-forced conflict resolution

no planner chronology redesign
```

## Remaining incompatibilities

List what still prevents schema 004 from becoming active on `vcs_dev`.

## Git

Show:

```text
git diff --stat

git status --short --untracked-files=all
```

No commit.

No push.

---

# 78. Definition of done

This task is complete when:

```text
bootstrap reconciles before planner-state GET

frontend no longer reconciles persisted statuses independently

single-segment status UI writes persisted Segment 1

multi-segment children have segment-specific status controls

multi-segment parent aggregate remains read-only

status mutations use PATCH segment endpoint

successful writes refresh planner-state authoritatively

selection/expansion survive refresh when valid

conflict rejection does not mutate local/blocker state

CORS permits the new frontend requests without weakening origin policy

monthly aggregate continues using refreshed parent aggregate

frontend/backend tests pass

desktop/mobile behavior is verified

vcs_dev remains untouched

legacy PlanItems remain preserved
```

---

# Final principle

The frontend no longer decides:

```text
what the occurrence status should become
```

It expresses only:

```text
what status the user wants for this Segment
```

The backend decides whether that request is valid and derives:

```text
Occurrence.status
```

from all persisted children.

Likewise, the frontend no longer decides whether historical statuses need
reconciliation.

Bootstrap asks the backend to reconcile:

```text
POST reconcile
```

and then reads the authoritative state:

```text
GET planner-state
```

The desired application loop is now:

```text
USER
 ↓
SEGMENT
 ↓
BACKEND DOMAIN
 ↓
POSTGRESQL
 ↓
OCCURRENCE AGGREGATE
 ↓
PLANNER-STATE
 ↓
UI
```
