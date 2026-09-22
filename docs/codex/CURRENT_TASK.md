# CURRENT TASK

## OccurrenceSegment v1 — Conflict UX, Legacy Retirement & Planner Chronology

### Objective

Connect the completed backend segment-conflict engine to the real planner UI.

The user must be able to:

```text
attempt a source mutation
→ receive concrete segment conflicts
→ understand what will happen
→ explicitly confirm
→ retry the SAME mutation with exact blocker confirmations
→ receive authoritative persisted state
```

without the frontend:

```text
rewriting blocker status locally

calculating target fragments

deciding conflict authorization

calling legacy parent-level override code
```

This phase must also retire or guard every remaining active frontend/backend
writer that is incompatible with schema 004.

Finally, fix the known planner chronology debt:

```text
expanded OccurrenceSegments must participate in real temporal ordering
```

instead of always being visually grouped under their parent envelope.

This is the final integration phase before:

```text
05.7.5.12
Final verification + schema 004 rollout
```

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

modules/gestor_de_habitos/docs/segment_conflict_api.md
```

Also inspect the completed implementation from:

```text
05.7.5.3
05.7.5.6
05.7.5.8
05.7.5.9
05.7.5.10
```

Especially inspect:

```text
js/app.js

js/api/planner-api.js

js/mutations/

js/views/planner-matrix.js

js/views/occurrence-structure-editor.js

js/domain/occurrence-segments.js

js/domain/occurrence-structure-draft.js

backend/app.py

backend/segment_conflict_domain.py

backend/segment_conflict_service.py

backend/repositories/segment_conflict_repository.py

backend/plan_item_creation_service.py

backend/occurrence_structure_service.py
```

Read all relevant tests before editing.

---

# Authority hierarchy

Interpret requirements in this order:

```text
CURRENT_TASK.md
→ current implementation scope

segment_conflict_api.md
→ actual conflict API contract

STATUS_CONFLICT_RULES.md
→ product conflict semantics

OCCURRENCE_SEGMENT_DECISIONS.md
→ approved technical decisions

OCCURRENCE_SEGMENT_V1.md
→ segment model

TECHNICAL_AUDIT
→ history/evidence
```

The frontend must NOT reinterpret backend domain outcomes.

---

# Scope

This phase includes:

```text
conflict dialog / confirmation UX

PlanItem creation conflict UX

single-occurrence structural conflict UX

exact blocker snapshot confirmation

realized-time correction acknowledgement

stale confirmation recovery

network-safe retry behavior

selection/expansion preservation

retirement/guarding of legacy conflict frontend paths

final audit of parent-level PATCH/DELETE writers

schema-004-safe occurrence deletion where applicable

planner chronology cleanup

desktop/mobile browser verification

full frontend/backend regression
```

This phase does NOT implement:

```text
new conflict-domain rules

recurring destructive conflict resolution

segment-status destructive conflict resolution

cross-day custom recurring movement

undefined in_progress internal split semantics

multiple-source/same-target resolution

authentication / owner / guest

production security hardening

Supabase/cloud deployment

migration 004 on vcs_dev

pause/resume

event log

global schedule shifting
```

---

# 1. Inspect working tree first

Before editing:

```text
git status --short --untracked-files=all
git diff --stat
git diff --check
```

05.7.5.10 should already be committed.

Preserve all user work.

Do not revert previous OccurrenceSegment phases.

---

# 2. Database safety

Do NOT apply migration 004 to:

```text
vcs_dev
```

Do NOT query, clean or modify `vcs_dev`.

Do NOT delete legacy PlanItems.

All schema-004 backend verification must use isolated PostgreSQL 16.

---

# 3. Migrations remain immutable

Do NOT modify:

```text
001_initial_schema.sql
002_fix_occurrence_status_context.sql
003_multi_slot_scheduling.sql
004_occurrence_segments.sql
```

A migration defect must be reported before any migration change.

---

# 4. Backend remains authoritative

Frontend must NOT calculate:

```text
which blocker wins

priority_override vs user_forced_override

whether realized time may be corrected

target trim range

target split ranges

target resulting statuses

target aggregate

conflict metadata
```

Those are backend responsibilities.

Frontend only:

```text
shows

explains

collects confirmation

retries original mutation

hydrates authoritative result
```

---

# 5. Supported conflict-producing UI flows

Integrate the new conflict UX into active user flows that correspond to:

```text
PlanItem / occurrence creation

occurrence translate

occurrence structure replacement

reset segmentation
```

These are the backend paths completed in 05.7.5.10.

---

# 6. Rejection-only flows remain rejection-only

Do NOT add destructive confirmation UX to:

```text
PATCH segment status

Apply Week

Apply Future
```

They continue to use their current controlled conflict errors.

---

# 7. First conflict response

Handle:

```text
409

code:
segment_conflict_resolution_required
```

as a distinct domain state.

Do NOT display it as a generic fatal error.

Do NOT mutate planner state.

Do NOT invoke legacy conflict handlers.

---

# 8. Conflict dialog

Create one dedicated conflict-resolution view/component.

Prefer a focused module such as:

```text
js/views/segment-conflict-dialog.js
```

or equivalent architecture consistent with the repository.

Do not grow `app.js` into the conflict UI implementation.

`app.js` should coordinate.

---

# 9. Dialog must identify the source intent

The dialog should clearly communicate what the user is trying to do.

Examples:

```text
Crear actividad

Mover actividad

Modificar estructura

Restablecer segmentación
```

Do not expose internal endpoint names.

---

# 10. Show every blocker

If backend returns multiple conflict entries:

```text
show ALL of them
```

Do not display only the first blocker.

The user must understand the complete operation being authorized.

---

# 11. Blocker information

For each conflict show, where available:

```text
target activity name

date

startTime – endTime

status

resolution effect
```

Use the existing planner/store to map:

```text
planItemId
```

to a human-readable activity name.

If the referenced PlanItem is unavailable:

```text
fall back gracefully
```

without inventing data.

---

# 12. Do not infer target structure

Frontend must NOT inspect blocker time and calculate:

```text
left fragment

right fragment

cancel result
```

Use the backend-provided conflict information / resolutionKind.

---

# 13. ResolutionKind mapping

Audit the actual resolutionKind values produced by 05.7.5.10.

Create one centralized presentation mapping.

Conceptually:

```text
backend resolutionKind
→ human description / action label
```

Do NOT duplicate this mapping throughout views.

Do NOT invent unsupported resolution kinds.

---

# 14. User-facing actions

For supported single-conflict cases, use concise contextual language when it
accurately represents the backend outcome.

Examples may include:

```text
Segmentar y continuar

Ajustar y continuar

Finalizar y continuar

Cancelar y continuar

Confirmar corrección
```

but use only labels that correspond exactly to the actual backend
resolutionKind/status outcome.

For multiple heterogeneous conflicts, prefer:

```text
Confirmar cambios y continuar
```

after presenting all effects.

---

# 15. `requiredAuthorization`

Backend returns:

```text
priority_override
```

or:

```text
user_forced_override
```

Frontend may explain the distinction.

It must NOT recompute it.

It must NOT allow the user to choose which value applies.

---

# 16. Priority override messaging

`priority_override` still requires user confirmation.

Do not present higher priority as:

```text
automatic

already approved

no-impact
```

The user is still authorizing modification of another occurrence.

---

# 17. User-forced messaging

For:

```text
user_forced_override
```

make it clear that the requested operation will modify an existing occupied
time even though priority does not automatically favor the source.

Do not sensationalize.

Keep wording concise and factual.

---

# 18. Realized-time conflicts

When:

```text
requiresRealizedTimeConfirmation == true
```

the user must receive a stronger warning.

Explain that the affected segment represents time already recorded as:

```text
completed

or

not_finished
```

and the operation will correct recorded history.

---

# 19. Explicit realized-time acknowledgement

The ordinary confirmation button is insufficient.

Require a dedicated acknowledgement control.

Example wording:

```text
Entiendo que esta acción corregirá tiempo ya registrado.
```

Only after that acknowledgement may the frontend send:

```json
"confirmRealizedTimeCorrection": true
```

for that blocker snapshot.

---

# 20. Bind strong acknowledgement per blocker

If there are multiple realized-time blockers:

```text
each exact blocker requiring strong confirmation
```

must receive the required acknowledgement.

Do not use one stale global flag detached from blocker identity.

---

# 21. Confirmation payload

On confirmation, retry the SAME source mutation with:

```text
conflictResolution.confirmations
```

using the exact contract from:

```text
segment_conflict_api.md
```

At minimum each confirmation binds:

```text
occurrenceId

segmentId

startTime

endTime

status

confirmed
```

and:

```text
confirmRealizedTimeCorrection
```

when required.

---

# 22. Preserve original mutation request

When first request returns conflict:

```text
store the exact original mutation intent/payload
```

as transient frontend command state.

The confirmation retry must use that same intended source mutation.

Do NOT reconstruct it from mutated planner state.

---

# 23. No domain persistence in pending conflict state

The transient conflict command may exist in frontend memory.

But it must NOT:

```text
modify planner domain state

change target statuses

change source persisted state

insert fake segments
```

It is only pending UI/command state.

---

# 24. Cancel conflict dialog

If user cancels:

```text
discard pending conflict confirmation state
```

No retry.

No backend write.

No planner mutation.

The original editor/form may remain available when appropriate.

---

# 25. Prevent double confirmation

While confirmed retry is pending:

```text
disable duplicate submit
```

One user confirmation must produce at most one mutation request.

---

# 26. Confirmed mutation success

After confirmed mutation succeeds:

```text
mutation
→ GET planner-state
→ hydrate authoritative state
```

Do not locally reproduce target split/trim/cancel outcomes.

---

# 27. GET failure after confirmed mutation

If mutation definitely succeeded but GET fails:

```text
do NOT resend the mutation
```

Recovery:

```text
GET planner-state only
```

Follow the established safe mutation pattern.

---

# 28. Ambiguous transport failure

If the mutation request itself fails at transport level and frontend cannot know
whether backend committed:

```text
DO NOT automatically resend
```

Surface an ambiguous-result state.

Offer/perform:

```text
authoritative GET
```

before allowing the user to decide whether to retry.

Never risk duplicate source creation because of automatic replay.

---

# 29. `conflict_resolution_stale`

Handle stale confirmation explicitly.

Meaning:

```text
the blocker changed after user reviewed it
```

Required behavior:

```text
old confirmation discarded

no automatic destructive retry

refresh authoritative planner state

tell user the conflict changed and must be reviewed again
```

---

# 30. Preserve source draft when safely possible

For structural editor conflicts:

If confirmation becomes stale but the source occurrence itself has not changed:

```text
the local structural draft may remain visible
```

but it must be marked/reviewed before another submission.

If authoritative refresh shows the source occurrence changed:

```text
invalidate the stale draft
```

Do not apply an old draft blindly to a changed source.

---

# 31. Fresh blocker after confirmation

If retry returns a new:

```text
segment_conflict_resolution_required
```

with additional/current blockers:

```text
replace old conflict dialog data with the fresh backend conflict set
```

The user must confirm the new concrete blockers.

No inherited authorization.

---

# 32. Undefined resolution

Handle backend errors such as:

```text
segment_resolution_undefined
```

as non-confirmable.

Especially:

```text
internal split of in_progress

full coverage of in_progress
```

where currently unsupported.

Explain that this exact case cannot yet be resolved automatically.

Do NOT offer a force button.

---

# 33. Multiple-source limitation

Handle:

```text
multiple_source_resolution_unavailable
```

as a controlled unsupported case.

Do not emulate ordering client-side.

Do not send several independent confirmations to simulate unsupported
multi-source semantics.

---

# 34. Frozen history

If backend rejects resolution because target is frozen:

```text
show that historical time cannot be rewritten
```

The user must modify the source intent instead.

No override button.

---

# 35. Creation conflict flow

For PlanItem/new occurrence creation:

```text
submit create
→ 409 conflict
→ show dialog
→ explicit confirmation
→ retry SAME create payload + conflictResolution
→ success
→ GET
```

---

# 36. Creation conflict must not duplicate

A create confirmation must never accidentally create:

```text
two PlanItems

two occurrences
```

Double-submit and transport recovery must be tested.

---

# 37. Structural translate conflict flow

For:

```text
POST /occurrences/<id>/translate
```

use the same shared conflict coordinator/dialog.

Do not build translate-specific conflict semantics.

---

# 38. Structure replacement conflict flow

For:

```text
PUT /occurrences/<id>/structure
```

preserve the existing local structural draft while conflict review is active.

Confirmed retry sends:

```text
same source structure payload
+
conflictResolution
```

---

# 39. Reset conflict flow

For:

```text
POST /occurrences/<id>/reset-segmentation
```

use the same conflict engine UX.

The initial explicit reset confirmation and the later conflict confirmation are
different concepts.

Do not collapse them into one accidental confirmation.

---

# 40. Shared conflict mutation coordinator

Prefer one shared frontend coordinator for:

```text
detect resolution-required response

store source command

open dialog

collect snapshots

retry command

recover

hydrate
```

Do not duplicate the complete flow for:

```text
create

translate

structure

reset
```

---

# 41. Existing mutation modules

Respect the current mutation architecture.

Extend/reuse existing:

```text
planner mutation coordinator

occurrence structure mutation coordinator

API client
```

rather than placing fetch logic in views.

---

# 42. No direct `fetch()` from conflict dialog

The conflict dialog is presentation.

It should not call endpoints directly.

Use centralized API/mutation layers.

---

# 43. Selection after successful conflict resolution

Preserve:

```text
selectedOccurrenceId
```

when that source/target still exists.

Preserve:

```text
selectedSegmentId
```

only if that segment ID still survives.

---

# 44. Split selection identity

When target split occurs:

```text
left fragment keeps old ID

right fragment receives new ID
```

If the old target segment was selected:

```text
selection naturally remains on the surviving left/original ID
```

Do not remap based on array indexes.

---

# 45. Cancelled/full-overlap selection

If a selected target segment changes status but keeps identity:

```text
selection may remain
```

If backend state legitimately removes/replaces the selected identity:

```text
clear dangling selection
```

Do not invent a replacement.

---

# 46. Expansion after conflict

Preserve expanded occurrence IDs after authoritative GET when those parents
still exist.

Conflict resolution must not unexpectedly collapse the whole planner.

---

# 47. Legacy frontend conflict audit

Audit exact callers of:

```text
edit_without_occurrence

prepareOccurrenceAddition

commitPreparedScheduleChange

openPersistentOverride

addPriorityOverride

confirmedOccurrenceIds

statusContext
```

---

# 48. `edit_without_occurrence`

05.7.5.10 guarded this path before the old local conflict writer.

After the new UI integration:

```text
do not restore its old conflict behavior
```

If it still owns a legitimate non-conflict interaction:

```text
keep only that compatible responsibility
```

Otherwise retire it.

---

# 49. `prepareOccurrenceAddition`

If it has no active caller after the new creation flow:

```text
remove it
```

when safe.

If retained for non-conflict logic:

```text
prove exact caller and responsibility
```

No legacy conflict mutation may remain reachable.

---

# 50. `commitPreparedScheduleChange`

If no active caller remains:

```text
remove it
```

or clearly isolate it as dead/deprecated code pending cleanup.

Do not keep a dormant writer reachable through accidental UI state.

---

# 51. `openPersistentOverride`

Retire it if the new dialog replaces its purpose.

No active UI path may open the old parent-level priority override interface.

---

# 52. `addPriorityOverride`

Retire/guard old client-side priority mutation logic.

Frontend no longer changes blockers itself.

---

# 53. `confirmedOccurrenceIds`

Remove it from active conflict authority.

The new confirmation authority is:

```text
exact blocker segment snapshots
```

---

# 54. `statusContext`

Do not restore dependency on this legacy alias.

Canonical frontend model remains:

```text
conflictContext
```

---

# 55. Legacy backend writer audit

Audit:

```text
PATCH /api/occurrences/<id>

DELETE /api/occurrences/<id>
```

and every backend caller/service they invoke.

Determine whether each is:

```text
schema-004 compatible

unused

or incompatible
```

---

# 56. Parent PATCH

The report from 05.7.5.10 identified:

```text
PATCH /api/occurrences/<id>
```

as still tied to:

```text
schema 003

status_reason

parent-level mutation
```

This path must NOT remain an active incompatible writer after this phase.

Preferred outcome:

```text
retire/remove active frontend use
```

and:

```text
retire/guard backend route
```

if no schema-004-compatible responsibility remains.

Do NOT simply rename:

```text
status_reason → conflict_reason
```

and preserve incompatible semantics.

---

# 57. No parent-level status authority

Occurrence status is materialized aggregate.

Therefore no generic endpoint may remain active that allows the client to set:

```text
Occurrence.status
```

independently of its segments.

Use:

```text
PATCH occurrence-segment status
```

instead.

---

# 58. Occurrence DELETE audit

Deleting a whole occurrence may be compatible because:

```text
occurrence_segments
ON DELETE CASCADE
```

but verify all behavior.

Deletion must respect:

```text
source_occurrence_id
ON DELETE NO ACTION
```

when the occurrence is referenced as historical conflict source.

---

# 59. Delete must be graph-aware

If active occurrence deletion remains supported:

```text
delete parent
→ segments cascade
```

must occur atomically.

Do not individually mutate segment statuses first.

---

# 60. Referenced source delete UX

If delete fails because occurrence is referenced as:

```text
source_occurrence_id
```

surface a controlled error.

Do not remove historical target provenance.

Do not clear references automatically.

---

# 61. Multi-segment deletion

Do not block whole-occurrence deletion merely because the parent has multiple
segments.

If deletion is otherwise valid:

```text
the whole graph may be deleted
```

through parent cascade.

If product semantics currently forbid deletion for another documented reason:

```text
preserve that rule
```

---

# 62. No status-as-delete fallback

Do not emulate deletion by changing:

```text
parent status
```

or all child statuses unless that is an explicit separate product action.

Delete and cancel are distinct operations.

---

# 63. Final active writer inventory

At completion, enumerate every active endpoint capable of modifying:

```text
plan_items

occurrences

occurrence_segments

generation configs / slots
```

and classify whether it is schema-004 compatible.

This inventory is critical input for 05.7.5.12.

---

# 64. No incompatible writer allowed

Definition before phase completion:

```text
no active UI path may reach a schema-003-only writer
```

Any remaining historical helper must be:

```text
removed

or provably unreachable
```

Do not leave "probably unused" as the only protection.

---

# 65. Planner chronology debt

Current known limitation:

Expanded children are visually grouped under their parent instead of
participating in global chronological order.

Example current grouping:

```text
Estudiar
  Seg 1 13:00–14:00
  Seg 2 16:00–17:00

Comer
14:30–15:30
```

This visually hides the real chronology.

---

# 66. Chronology goal

Expanded temporal rows must be ordered by actual occupied time:

```text
13:00  Estudiar · Seg 1

14:30  Comer

16:00  Estudiar · Seg 2
```

without changing domain ownership:

```text
Seg 1 and Seg 2
still belong to the same occurrence
```

---

# 67. Chronology is presentation only

Do NOT modify persisted data to achieve visual ordering.

Do NOT duplicate occurrences.

Do NOT change segment IDs.

Do NOT create synthetic persisted rows.

Build a derived render model.

---

# 68. Compact occurrence behavior

A non-expanded occurrence may continue to render as one parent-level temporal
row using its general envelope.

Do not force every occurrence to display child rows all the time.

---

# 69. Expanded multi-segment behavior

When a multi-segment occurrence is expanded:

```text
its child temporal rows
```

must participate individually in the global chronological ordering.

They may appear separated by rows from other occurrences.

---

# 70. Parent identity in interleaved rows

Because children may no longer remain physically contiguous:

Each segment row must make its parent identity clear.

Examples:

```text
Estudiar · Seg 1/2

Estudiar · Seg 2/2
```

Use derived ordinal ordering.

Do NOT persist:

```text
segment number
```

---

# 71. Parent controls

The user must still be able to access parent actions:

```text
structural editor

recurring editor

delete if available

expand/collapse
```

even when segment rows are interleaved.

Choose a minimal clear presentation.

Do not redesign the entire planner.

---

# 72. Parent summary

If retaining a parent summary/control row:

```text
it must not masquerade as another occupied time interval
```

It may be a non-temporal group/control element.

Do not allow it to distort chronological sorting.

---

# 73. Global temporal sort

Use a derived sort key based on the actual row represented.

For child rows:

```text
segment.startTime
```

For compact parent rows:

```text
occurrence.startTime
```

Use deterministic tie-breaking.

---

# 74. Tie-breaking

When multiple temporal rows share the same start time:

Use deterministic stable ordering based on existing planner semantics, then
stable IDs if needed.

Do not rely on incidental object insertion order.

---

# 75. Cross-parent gaps

The visual chronology must correctly show another occurrence inside the gap of
a segmented parent.

This is the main acceptance case for chronology cleanup.

---

# 76. Single-segment occurrence

A one-segment occurrence should retain the familiar compact UI.

Do not add unnecessary expansion complexity.

---

# 77. Status controls

For expanded multi-segment rows:

```text
segment status controls remain attached to that concrete segment
```

Parent aggregate remains informational/read-only.

---

# 78. Structural editing

Opening the structural editor from any segment row must edit:

```text
the owning occurrence
```

not only that child.

Selection should set:

```text
selectedOccurrenceId

selectedSegmentId
```

appropriately.

---

# 79. Recurring control

The dedicated:

```text
↻
```

recurring action from 05.7.5.9 remains distinct from:

```text
✏️
```

structural editing.

Chronology cleanup must not regress that distinction.

---

# 80. Accessibility

Conflict dialog must support:

```text
keyboard focus

clear labels

button disabled state while submitting

readable warning text

close/cancel action
```

Use appropriate dialog semantics consistent with existing app patterns.

---

# 81. Dialog focus

When conflict dialog opens:

```text
focus should enter the dialog
```

When it closes:

```text
return focus to a sensible originating control
```

where practical.

Do not trap the user with no keyboard escape path.

---

# 82. Visual hierarchy

Distinguish:

```text
normal scheduling conflict

user-forced conflict

realized-time correction

unsupported/frozen case
```

without using alarming or sensational language.

---

# 83. Responsive behavior

The conflict dialog and chronology layout must work at approximately:

```text
1440×900 desktop

390×844 mobile
```

No horizontal overflow.

No action buttons outside viewport.

---

# 84. Long conflict lists

If many blockers exist:

```text
dialog content may scroll internally
```

while keeping primary actions usable.

Do not expand the whole page uncontrollably.

---

# 85. Creation conflict frontend tests

Test:

```text
create
→ 409
→ dialog
→ confirmation
→ same create + conflictResolution
→ GET
→ hydrate
```

---

# 86. Creation realized-time test

Test:

```text
create
→ completed/not_finished blocker
→ dialog
→ normal confirmation unavailable
→ realized acknowledgement
→ confirmed retry
```

Verify exact snapshot payload.

---

# 87. Creation cancel test

Conflict dialog cancel:

```text
zero retry requests

zero local planner mutation
```

---

# 88. Create double-submit test

Rapid confirmation clicks:

```text
one confirmed mutation request only
```

---

# 89. Structural conflict frontend tests

Cover:

```text
translate

PUT structure

reset
```

through shared conflict coordinator.

---

# 90. Preserve structural draft test

For PUT structure:

```text
conflict dialog opens
→ source draft remains intact
→ confirm
→ same source candidate sent
```

No target graph is authored client-side.

---

# 91. Stale confirmation frontend test

Mock:

```text
conflict_resolution_stale
```

Verify:

```text
old confirmation discarded

GET authoritative state

no automatic mutation replay

review message shown
```

---

# 92. New blocker test

Confirmed retry returns a fresh resolution-required 409.

Expected:

```text
fresh conflict set replaces old dialog data

old confirmations do not carry forward automatically
```

---

# 93. Undefined resolution frontend test

Mock:

```text
segment_resolution_undefined
```

Verify:

```text
no force button

no retry with fabricated confirmation

clear unsupported message
```

---

# 94. Multiple-source limitation frontend test

Mock:

```text
multiple_source_resolution_unavailable
```

Verify safe explanation and no client-side workaround.

---

# 95. Frozen conflict frontend test

No confirm button capable of rewriting frozen target.

User must return and modify source.

---

# 96. Network ambiguity test

Mutation transport failure after confirmation:

```text
no automatic replay
```

Authoritative refresh path only.

---

# 97. Confirmed success + GET failure test

Verify:

```text
mutation sent once

GET fails

recovery performs GET only
```

---

# 98. Selection tests

Verify selection through:

```text
trim

split

cancel/status result

authoritative hydration
```

using stable IDs.

No index-based remapping.

---

# 99. Chronology unit tests

Create derived render-model tests covering:

```text
compact rows

expanded children

interleaving

gaps

same-time deterministic sorting

single segment

multi segment

selection identity
```

---

# 100. Chronology acceptance example

Explicit test:

```text
Occurrence A
parent 13:00–17:00

A1 13:00–14:00
A2 16:00–17:00

Occurrence B
14:30–15:30
```

Expanded result must render temporal order:

```text
A1

B

A2
```

not:

```text
A1

A2

B
```

---

# 101. Conflict-created split chronology

After authoritative GET from a confirmed conflict producing a split:

```text
new right fragment
```

must immediately participate correctly in chronology.

No special-case reload required beyond normal GET/hydrate.

---

# 102. Monthly/status regression

Chronology cleanup must not change:

```text
monthly aggregate status

segment status semantics

parent aggregate semantics
```

Presentation only.

---

# 103. Apply Week/Future regression

Verify:

```text
↻ recurring action

Apply Week

Apply Future

custom resize rejection

recurring conflict rejection
```

still work as in 05.7.5.9.

Do NOT route recurring conflicts into destructive conflict dialog.

---

# 104. Segment-status regression

A segment status conflict remains:

```text
segment_status_conflict
```

and must not accidentally open the destructive creation/move resolution flow.

---

# 105. Reconciliation regression

Bootstrap remains:

```text
POST planner/reconcile
→ GET planner-state
→ hydrate
```

No conflict dialog during ordinary bootstrap.

---

# 106. Planner-state remains authoritative

GET remains read-only.

Frontend may derive:

```text
display rows

segment ordinals

dialog labels
```

but not persistent conflict outcomes.

---

# 107. Backend API regression

Do not redesign the 05.7.5.10 conflict contract merely for easier frontend
implementation.

If a truly missing field makes UX impossible:

```text
make the smallest backend contract addition

test it

document it
```

Do not move domain authority client-side.

---

# 108. Backend parent writer tests

Add/adjust tests proving no schema-004 path can:

```text
set parent status independently

write status_reason

invoke legacy priority override
```

---

# 109. DELETE integration tests

If occurrence deletion remains active, test against schema 004:

```text
single-segment occurrence delete

multi-segment occurrence delete

segments cascade

referenced-source delete rejection

no orphan segments
```

Use isolated PostgreSQL 16.

---

# 110. Legacy code cleanup

Remove clearly dead code when safe.

Do not keep large legacy conflict systems solely because tests reference them.

Update/remove obsolete tests alongside retired code.

Do not delete historical documentation merely to make grep clean.

---

# 111. Runtime grep audit

At completion search active code for:

```text
status_reason

confirmedOccurrenceIds

apply_priority_overrides

openPersistentOverride

addPriorityOverride

prepareOccurrenceAddition

commitPreparedScheduleChange

PATCH /api/occurrences
```

Classify every remaining occurrence.

Distinguish:

```text
historical tests/docs

dormant compatibility code

active runtime code
```

---

# 112. No active `status_reason`

Schema-004 runtime code must not write:

```text
status_reason
```

If references remain only in migrations/schema-003 compatibility or historical
tests:

```text
report them precisely
```

---

# 113. No active parent status mutation

At phase completion:

```text
Occurrence.status
```

must only change as:

```text
materialized aggregate derived from segments
```

within schema-004 active paths.

---

# 114. PostgreSQL 16 isolated verification

Use:

```text
001
→ 002
→ 003
→ 004
```

in an isolated PostgreSQL 16 instance.

Do NOT use `vcs_dev`.

---

# 115. Conflict regression PostgreSQL

Re-run the full 05.7.5.10 schema-004 conflict suite.

It must remain green.

---

# 116. Recurring regression PostgreSQL

Re-run:

```text
test_recurring_schema004_integration.py
```

Apply Week/Future remain rejection-only and segment-aware.

---

# 117. Deletion PostgreSQL tests

If deletion path changes, verify real:

```text
parent deletion

segment cascade

NO ACTION provenance restriction

rollback
```

---

# 118. Full backend suite

Run:

```text
.venv/bin/python -m unittest discover \
  -s modules/gestor_de_habitos/backend \
  -p 'test_*.py'
```

Report exact result and opt-in skips.

---

# 119. Full frontend suite

Run:

```text
for test_file in modules/gestor_de_habitos/tests/*.test.mjs
do
  node "$test_file" || exit 1
done
```

Report:

```text
file count

test count if available

result
```

---

# 120. Syntax

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

Run:

```text
git diff --check
```

---

# 121. Browser verification — conflict UX

Use mocked or isolated schema-004 backend.

Do NOT use `vcs_dev`.

Desktop:

```text
1440×900
```

Mobile:

```text
approximately 390×844
```

---

# 122. Browser creation conflict

Verify:

```text
create source

dialog opens

blocker readable

resolution effect readable

confirm

authoritative GET

final planner correct
```

---

# 123. Browser realized-time correction

Verify stronger confirmation cannot be bypassed.

Ordinary confirm button must not send:

```text
confirmRealizedTimeCorrection: true
```

without explicit acknowledgement.

---

# 124. Browser split result

After confirmed split and GET:

```text
left original segment

right new segment
```

both render correctly.

If expanded:

```text
both participate in global chronology
```

---

# 125. Browser stale conflict

Verify stale response:

```text
does not auto retry

refreshes authoritative state

asks for review
```

---

# 126. Browser unsupported conflict

Verify:

```text
segment_resolution_undefined
```

has no destructive action.

---

# 127. Browser recurring conflict

Verify Apply Week/Future conflict does NOT open the destructive single-source
conflict confirmation flow.

---

# 128. Browser structural conflict

Verify:

```text
structural draft
→ conflict
→ dialog
→ confirmation
→ authoritative GET
```

without losing the intended source structure.

---

# 129. Browser chronology desktop

Verify the gap/interleaving case visually.

No child grouping that creates false chronology.

---

# 130. Browser chronology mobile

Verify:

```text
segment parent identity remains clear

controls remain usable

no horizontal overflow
```

---

# 131. No complete visual redesign

Preserve current VCS identity:

```text
dark/gold styling

planner structure

responsive behavior
```

Make only the UX/layout changes necessary for conflict review and chronology.

---

# 132. Documentation

Update only documentation necessary for:

```text
frontend confirmation flow

remaining unsupported conflict cases

legacy retirement

chronological render behavior
```

Do not document future auth/security/deployment in this phase.

---

# 133. Still no schema rollout

Even after this phase:

```text
DO NOT apply 004 to vcs_dev
```

05.7.5.12 owns the real rollout.

---

# 134. Expected architecture after this phase

```text
schema 004 foundation
✅

backend planner read
✅

frontend segment read/display
✅

segment creation
✅

segment status
✅

persistent reconciliation
✅

structural backend
✅

structural editor
✅

Apply Week/Future
✅

segment conflict engine
✅

conflict confirmation API
✅

conflict UX
✅

legacy frontend conflict writer
✅ retired/guarded

parent status writer
✅ retired/guarded

planner temporal chronology
✅

real vcs_dev schema rollout
❌

owner/guest auth
❌ later

security hardening
❌ later

production deployment
❌ later
```

---

# 135. Final writer inventory

Produce a table/report of every ACTIVE mutating route, including at minimum:

```text
PlanItem creation

segment status

planner reconciliation

occurrence translate

occurrence structure

reset segmentation

occurrence delete if active

Apply Week

Apply Future
```

For each state:

```text
endpoint

service

tables changed

segment-aware?

aggregate-safe?

conflict behavior

schema-004 ready?
```

Do not score or rank; just factual compatibility.

---

# 136. Remaining incompatibilities

At completion, explicitly answer:

```text
Is there any active application write path that still requires schema 003?
```

If yes:

```text
05.7.5.11 is NOT complete.
```

Either make it schema-004 compatible, retire it, or guard it so it is provably
unreachable from active application behavior.

Historical test helpers do not count as active runtime paths, but must be
identified.

---

# 137. Git rules

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

# 138. Completion report

At completion provide:

## Files

Every created/modified/deleted file.

## Conflict UX

Explain:

```text
first 409 handling

dialog state

blocker display

resolutionKind presentation

priority/user-forced messaging

realized-time acknowledgement

confirmation payload

confirmed retry

GET-after-success
```

## Recovery

Explain:

```text
stale confirmation

new blocker

removed/changed blocker

network ambiguity

success + GET failure

double submit
```

## Unsupported cases

Report UI behavior for:

```text
in_progress internal split

in_progress full coverage if still undefined

multiple-source resolution

frozen history
```

## Flow integration

Report:

```text
creation

translate

structure replacement

reset
```

and confirm:

```text
segment status rejection-only

Apply Week/Future rejection-only
```

## Legacy retirement

Give exact final status/callers for:

```text
edit_without_occurrence

prepareOccurrenceAddition

commitPreparedScheduleChange

openPersistentOverride

addPriorityOverride

confirmedOccurrenceIds

apply_priority_overrides

status_reason

statusContext
```

## Parent writer audit

Explain final disposition of:

```text
PATCH /api/occurrences/<id>

DELETE /api/occurrences/<id>
```

## Writer inventory

List every active mutating endpoint and schema-004 compatibility.

## Chronology

Explain:

```text
derived render model

expanded segment interleaving

parent identity

tie-breaking

selection

controls
```

## PostgreSQL

Report:

```text
conflict regression

recurring regression

deletion tests if applicable
```

## Frontend tests

Exact commands and results.

## Backend tests

Exact commands and results.

## Browser

Report desktop/mobile:

```text
creation conflict

realized correction

split

stale

unsupported

structural conflict

recurring rejection

chronology
```

## Safety

Confirm:

```text
vcs_dev untouched

PlanItems preserved

migrations unchanged

no auth work

no production security work

no cloud deployment

no recurring destructive resolution

no segment-status destructive resolution

no undefined in_progress semantics invented
```

## Rollout readiness

State exactly what remains before 05.7.5.12 can apply schema 004 to real
`vcs_dev`.

## Git

Show:

```text
git diff --stat

git status --short --untracked-files=all
```

No commit.

No push.

---

# 139. Definition of done

This phase is complete when:

```text
creation conflict UX uses concrete segment snapshots

structural conflict UX uses the same shared coordinator

realized-time correction requires explicit strong acknowledgement

stale confirmations cannot be reused

new blockers require new review

ambiguous transport failures never auto-replay mutations

confirmed success hydrates from authoritative GET

legacy local blocker mutation is unreachable

confirmedOccurrenceIds is no longer active authority

active parent status writer is retired/guarded

no active runtime status_reason writes remain

whole-occurrence deletion is schema-004 safe or retired

Apply Week/Future remain rejection-only

segment status remains rejection-only

expanded child segments render in real global chronology

segment ownership remains clear

selection/expansion survive authoritative hydration

desktop/mobile UX is verified

all frontend tests pass

all backend tests pass

schema-004 PostgreSQL conflict regression passes

schema-004 recurring regression passes

no active application writer still depends on schema 003

vcs_dev remains untouched
```

---

# Final principle

The backend already knows:

```text
WHAT conflicts

WHAT resolution is allowed

WHAT target state results

WHICH authorization is required
```

The frontend must now provide only:

```text
UNDERSTANDING

EXPLICIT HUMAN CONFIRMATION

SAFE COMMAND RETRY

AUTHORITATIVE REFRESH
```

It must never become a second conflict engine.

And the planner must visually represent the same truth stored in the domain:

```text
an occurrence may have multiple occupied temporal pieces
```

Therefore a gap inside one occurrence is genuinely available for another
activity, both in:

```text
conflict logic
```

and in:

```text
what the user sees on the timeline
```

After this phase there should be no remaining active schema-003-only writer
between VCS and the schema-004 rollout.
