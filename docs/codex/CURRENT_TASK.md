# CURRENT TASK

## OccurrenceSegment v1 — Persistent Planning Termination & Future Cleanup

### Objective

Replace the remaining local-only:

```text
Detener planificación
```

behavior with authoritative persisted backend commands.

The planner must support FOUR distinct user intentions:

```text
1. Eliminar solo esta aparición

2. Detener este horario
   después de este día

3. Detener toda la planificación recurrente
   después de este día

4. Eliminar todas las apariciones
   después de este día
```

These operations differ by identity and scope.

They must NOT be implemented as variations of:

```text
delete everything after this date
```

without respecting:

```text
Occurrence identity

GenerationSlot provenance

PlanItem identity

manual/ad-hoc occurrences

recurring configuration
```

This phase must make all four operations persistent and schema-004-compatible
before the real database rollout.

The real `vcs_dev` migration is moved to:

```text
05.7.5.13
Final Verification + Real Schema Rollout
```

---

# Core product rule

Let:

```text
D = date of the selected owning occurrence
```

For every "after this day" command:

```text
date == D
→ KEEP
```

```text
date < D
→ NEVER TOUCH
```

```text
date > D
→ affected according to command scope
```

The cutoff is therefore:

```text
exclusive toward the future
```

not:

```text
date >= D
```

---

# Required reading

Before editing, read completely:

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

Also inspect all current scheduling implementation:

```text
GenerationConfig

GenerationSlot

generation_slot_weekdays

generation_slot_dates

generation_slot_excluded_dates

generation_excluded_dates

source_generation_slot_id

Apply Week

Apply Future

occurrence DELETE

occurrence creation

occurrence generation/reconciliation

planner-store local stop-planning behavior
```

Especially inspect:

```text
backend/app.py

backend/occurrence_mutation_service.py

backend/week_mutation_service.py

backend/future_schedule_service.py

backend/recurring_segment_service.py

backend/repositories/

js/app.js

js/state/planner-store.js

js/views/planner-matrix.js

js/api/planner-api.js
```

Read relevant tests before implementation.

---

# 1. Inspect working tree first

Before editing:

```text
git status --short --untracked-files=all
git diff --stat
git diff --check
```

05.7.5.11 should already be committed.

Preserve user work.

Do not revert any completed OccurrenceSegment phase.

---

# 2. Database safety

DO NOT apply migration 004 to:

```text
vcs_dev
```

DO NOT query, clean or modify `vcs_dev`.

DO NOT delete the user's real legacy PlanItems.

Use isolated PostgreSQL 16 for all real persistence tests.

---

# 3. Existing migrations are immutable

Do NOT modify:

```text
001_initial_schema.sql
002_fix_occurrence_status_context.sql
003_multi_slot_scheduling.sql
004_occurrence_segments.sql
```

However, this phase MUST audit whether the current schema can persist an
unbounded recurring cutoff correctly.

If it cannot, an ADDITIVE migration:

```text
005_*.sql
```

may be created.

Never rewrite 001–004.

---

# 4. Persistence-model audit comes first

Before implementing the commands, determine exactly how the current scheduling
model answers:

```text
How does a GenerationSlot stop generating after a date?
```

and:

```text
How does a whole recurring PlanItem stop generating after a date?
```

Do not assume the schema already supports this.

Audit:

```text
GenerationConfig lifecycle

GenerationSlot lifecycle

weekdays

explicit dates

excluded dates

Apply Future rewriting

generation horizon/materialization

slot provenance
```

---

# 5. Forbidden fake persistence

Do NOT represent:

```text
stop forever after D
```

by generating an arbitrary finite list such as:

```text
D+1 exclusion
D+2 exclusion
...
next 365 days
```

That is not a durable recurrence cutoff.

Do NOT rely solely on deleting currently materialized future occurrences.

Otherwise regeneration could recreate them.

---

# 6. Preserve GenerationSlot provenance

Do NOT solve slot termination by deleting the GenerationSlot if that would
destroy historical:

```text
source_generation_slot_id
```

provenance.

Historical occurrences must still be able to answer:

```text
Which recurring slot created me?
```

even after that slot stops generating future occurrences.

---

# 7. If migration 005 is required

If current schema lacks a durable bounded recurrence representation:

create the MINIMAL additive schema needed.

The persistence model must support:

```text
slot-level inclusive final generation date
```

and, if technically required by the existing GenerationConfig architecture:

```text
schedule/config-level inclusive final generation date
```

or an equivalent normalized model.

Semantics:

```text
NULL
→ no cutoff

D
→ may generate on D
→ must not generate after D
```

Use clear naming consistent with repository style.

Do not add unrelated scheduling features.

---

# 8. Migration 005 requirements

If created:

```text
BEGIN / COMMIT

safe additive changes

NULL-compatible backfill

existing schedules remain unbounded

indexes only if justified

verification queries/tests
```

No existing schedule may accidentally stop.

Migration must be tested:

```text
001
→ 002
→ 003
→ 004
→ 005
```

on isolated PostgreSQL 16.

---

# 9. Generation engine must honor cutoff

Whatever persistent representation is selected:

ALL future occurrence generation must respect it.

A stopped slot may generate:

```text
date <= cutoff
```

but never:

```text
date > cutoff
```

This must remain true after:

```text
reload

Flask restart

reconciliation

later planner bootstrap
```

---

# 10. Apply Week / Apply Future cutoff audit

Audit how:

```text
Apply Week

Apply Future
```

interact with a stopped slot/schedule.

They must NOT silently clear or ignore an existing cutoff.

Do not automatically restart stopped planning.

If current semantics cannot safely combine with a cutoff:

```text
reject/report that exact operation
```

rather than silently reopening recurrence.

Explicit "restart planning" behavior is OUT OF SCOPE.

---

# 11. Selection may be a segment

The UI may currently have:

```text
selectedOccurrenceId

selectedSegmentId
```

The four commands are NOT segment operations.

If a segment is selected:

```text
selectedSegment
→ owning occurrence
→ command scope
```

The selected segment's individual time does not define the scope.

---

# 12. Command 1 — Delete only this occurrence

User-facing meaning:

```text
Eliminar solo esta aparición
```

Scope:

```text
exact selected occurrenceId
```

Existing schema-004 DELETE behavior from 05.7.5.11 should remain authoritative.

---

# 13. Generated occurrence deletion

If selected occurrence came from:

```text
source_generation_slot_id != NULL
```

deleting only that occurrence must preserve the existing recurrence semantics
that prevent that same occurrence from simply regenerating.

Reuse the approved exclusion behavior.

Do not stop the entire slot.

---

# 14. Manual occurrence deletion

If:

```text
source_generation_slot_id == NULL
```

delete only that occurrence.

Do not modify recurrence merely because the PlanItem itself is recurrent.

---

# 15. Command 2 — Stop this recurring slot

User-facing meaning:

```text
Detener este horario después de este día
```

Canonical identity:

```text
selected occurrence.source_generation_slot_id
```

---

# 16. Command 2 applicability

This command is available only when the selected owning occurrence has:

```text
source_generation_slot_id != NULL
```

If selected occurrence is manual/ad-hoc:

```text
source_generation_slot_id == NULL
```

this scope does not exist.

Frontend should hide/disable it appropriately.

Backend must still reject misuse safely.

---

# 17. Command 2 cutoff

Given selected occurrence date:

```text
D
```

persist:

```text
selected GenerationSlot may generate through D

selected GenerationSlot may NOT generate after D
```

---

# 18. Command 2 materialized cleanup

Delete/reconcile already-materialized occurrences satisfying:

```text
occurrence.source_generation_slot_id
==
selected source_generation_slot_id
```

AND:

```text
occurrence.date > D
```

---

# 19. Command 2 follows provenance, not current time

This is CRITICAL.

Example:

Original slot:

```text
14:00–17:00
```

Future occurrence was manually changed to:

```text
13:00–18:00
```

but still has:

```text
source_generation_slot_id = Slot B
```

Stopping Slot B after D MUST affect that customized occurrence.

Do NOT determine membership using:

```text
current startTime

current endTime
```

Use provenance:

```text
source_generation_slot_id
```

---

# 20. Command 2 preserves other slots

Example:

```text
Uber

Slot A 08:00–11:00
Slot B 14:00–17:00
Slot C 20:00–22:00
```

Stopping Slot B after D:

```text
A future occurrences → KEEP

B future occurrences → REMOVE / STOP

C future occurrences → KEEP
```

---

# 21. Command 2 preserves manual occurrences

A future occurrence with:

```text
source_generation_slot_id = NULL
```

must remain.

Even if:

```text
plan_item_id
```

is the same.

---

# 22. Command 3 — Stop all recurring planning

User-facing meaning:

```text
Detener toda la planificación recurrente
después de este día
```

Scope:

```text
the selected PlanItem's recurring schedule
```

---

# 23. Command 3 recurrence effect

After cutoff D:

```text
NO recurring GenerationSlot belonging to the selected PlanItem's
authoritative recurring schedule may generate future occurrences.
```

All recurring slots are stopped after D.

---

# 24. Command 3 materialized cleanup

Remove/reconcile materialized occurrences where:

```text
plan_item_id == selected PlanItem
```

AND:

```text
date > D
```

AND:

```text
source_generation_slot_id != NULL
```

---

# 25. Command 3 preserves manual/ad-hoc occurrences

Occurrences satisfying:

```text
source_generation_slot_id == NULL
```

must remain.

This distinction is intentional.

The user is saying:

```text
Stop automatic recurring planning
```

not:

```text
Delete everything belonging to this PlanItem
```

---

# 26. Command 3 follows provenance after customization

A generated occurrence remains recurring-origin even if its runtime:

```text
date/time/segments
```

were customized, as long as its provenance identifies it as generated from the
recurring schedule.

Do not classify by matching current slot time.

---

# 27. Command 4 — Delete all future appearances

User-facing meaning:

```text
Eliminar todas las apariciones
después de este día
```

Scope:

```text
selected plan_item_id
```

regardless of occurrence origin.

---

# 28. Command 4 occurrence cleanup

For selected PlanItem:

```text
date > D
```

remove ALL relevant future occurrences, including:

```text
generated recurring occurrences

customized generated occurrences

manual/ad-hoc occurrences
```

---

# 29. Command 4 must also stop recurrence

This command cannot merely delete current future rows.

Otherwise recurring generation could recreate them.

Therefore Command 4 includes:

```text
Command 3
+
deletion of manual/ad-hoc future occurrences
```

Conceptually:

```text
stop all recurring generation after D
+
delete every PlanItem occurrence with date > D
```

---

# 30. Command 4 does not delete the PlanItem itself

The PlanItem identity remains.

This command removes/stops:

```text
future appearances
```

not the PlanItem definition/history.

Historical and cutoff-date data remain.

---

# 31. Summary of the four scopes

Canonical identity:

```text
1. This occurrence
→ occurrence_id

2. This recurring slot
→ source_generation_slot_id

3. All recurring planning
→ recurring schedule / GenerationSlots of plan_item_id

4. All future appearances
→ plan_item_id
```

---

# 32. Canonical example

PlanItem:

```text
Uber
```

Recurring slots:

```text
A → 08:00–11:00

B → 14:00–17:00

C → 20:00–22:00
```

Selected:

```text
21 Oct
Slot B occurrence
```

Manual occurrence:

```text
25 Oct
18:30–19:00
source_generation_slot_id = NULL
```

Customized B occurrence:

```text
25 Oct
13:00–18:00
source_generation_slot_id = B
```

---

# 33. Command 2 expected result

Stop this slot after 21 Oct:

```text
21 Oct → KEEP

22 Oct onward:

A → KEEP

B → REMOVE / no regeneration

customized B → REMOVE

C → KEEP

manual → KEEP
```

---

# 34. Command 3 expected result

Stop all recurring planning after 21 Oct:

```text
21 Oct → KEEP

22 Oct onward:

A → REMOVE

B → REMOVE

customized B → REMOVE

C → REMOVE

manual → KEEP
```

---

# 35. Command 4 expected result

Delete all future appearances after 21 Oct:

```text
21 Oct → KEEP

22 Oct onward:

A → REMOVE

B → REMOVE

customized B → REMOVE

C → REMOVE

manual → REMOVE
```

and recurring generation remains stopped after the cutoff.

---

# 36. Historical protection

These commands are planning operations, not history rewriting operations.

Do NOT permit a cutoff that would retrospectively delete historical data.

Preferred rule:

```text
selected occurrence date D
must be today or future
```

Backend enforces this using authoritative local date.

If:

```text
D < today
```

return a controlled error.

Do not delete past occurrences.

---

# 37. Today is allowed

If:

```text
D == today
```

the selected day's occurrences are preserved.

Only:

```text
date > today
```

are affected.

---

# 38. Future is allowed

If:

```text
D > today
```

the selected occurrence/day remains.

All affected rows strictly after D follow command scope.

---

# 39. No client clock authority

Backend determines:

```text
today
```

from its authoritative clock.

Do not accept:

```text
today

now

temporalPhase
```

from public payloads.

Capture one authoritative `now` per command.

---

# 40. Derive scope from server data

Prefer command APIs where the frontend supplies:

```text
selected occurrence ID
```

and backend derives:

```text
cutoff date

planItemId

sourceGenerationSlotId

GenerationConfig/slot ownership
```

Do NOT trust the client to tell backend which PlanItem or Slot it owns.

---

# 41. Preferred API shape

Prefer explicit command endpoints consistent with repository conventions.

Conceptually:

```text
DELETE /api/occurrences/<id>
```

for Command 1.

And commands conceptually equivalent to:

```text
POST /api/occurrences/<id>/stop-slot-after

POST /api/occurrences/<id>/stop-recurring-after

POST /api/occurrences/<id>/delete-future-after
```

Exact naming may follow existing API style.

Avoid an overloaded generic endpoint whose behavior depends on ambiguous
boolean combinations.

---

# 42. No client-side deletion loops

Frontend must NOT:

```text
GET all future occurrences

loop

DELETE each one
```

The backend owns the command atomically.

---

# 43. Atomicity

Commands 2–4 must be atomic.

A successful command may need to coordinate:

```text
recurrence cutoff state

GenerationConfig

GenerationSlots

materialized occurrences

occurrence_segments through cascade

slot/date exclusions when applicable
```

All or nothing.

---

# 44. Isolation

Use:

```text
SERIALIZABLE
```

consistent with current mutation architecture.

---

# 45. Deterministic locking

Lock relevant rows in deterministic order.

Conceptually:

```text
selected occurrence

PlanItem / GenerationConfig

GenerationSlots

target occurrences ordered by date + ID

dependent provenance rows if needed
```

Avoid lock-order divergence from existing scheduling mutations.

---

# 46. Referential provenance

Remember:

```text
source_occurrence_id
ON DELETE NO ACTION
```

Future occurrences selected for deletion may themselves be referenced as
historical conflict sources.

Do not clear provenance automatically.

---

# 47. External source reference

If an occurrence to be deleted is referenced by an occurrence OUTSIDE the same
deletion set:

```text
do not delete it silently
```

Return a controlled conflict explaining that historical provenance protects the
occurrence.

No automatic:

```text
source_occurrence_id = NULL
```

---

# 48. References entirely inside deletion set

Audit actual PostgreSQL FK behavior.

If both source and referencing occurrence belong to the SAME atomic deletion
set and PostgreSQL permits the final consistent delete:

```text
allow it
```

only with explicit integration coverage.

Do not guess.

---

# 49. Segment handling

Deleting an occurrence deletes its:

```text
OccurrenceSegments
```

through:

```text
ON DELETE CASCADE
```

Do not individually delete/modify child segments first.

---

# 50. Conflict metadata

Stopping recurrence / deleting future planning is NOT:

```text
priority_override

user_forced_override

conflict_move

conflict_insertion
```

Do not create conflict metadata merely because scheduling was stopped.

---

# 51. Generation provenance survives cutoff

Stopping a slot does not alter historical:

```text
source_generation_slot_id
```

of surviving occurrences.

Do not rewrite old occurrences to NULL.

---

# 52. No segmentation templates

These commands do not introduce:

```text
runtime segment templates

generation-slot segments

segment inheritance
```

GenerationSlot remains recurring-envelope/domain scheduling state.

---

# 53. Customized future occurrence membership

For Commands 2 and 3:

membership is based on provenance.

Example:

```text
source_generation_slot_id = B
```

remains B even if occurrence changed:

```text
14:00–17:00
→
13:00–18:00
```

That occurrence is still affected by stopping B.

---

# 54. Manual future occurrence membership

For:

```text
source_generation_slot_id = NULL
```

Command 2:

```text
KEEP
```

Command 3:

```text
KEEP
```

Command 4:

```text
DELETE
```

This must have explicit tests.

---

# 55. Existing individual DELETE remains distinct

Do not replace:

```text
Eliminar solo esta aparición
```

with one of the new bulk commands.

All four actions remain independently available when applicable.

---

# 56. Frontend action menu

Expose four clearly distinct actions.

Recommended wording:

```text
Eliminar solo esta aparición

Detener este horario
después de este día

Detener toda la planificación recurrente
después de este día

Eliminar todas las apariciones
después de este día
```

Keep wording concise.

---

# 57. Applicability in UI

Command 2:

only available when:

```text
source_generation_slot_id != NULL
```

Command 3:

available when the PlanItem has recurring planning that can be stopped.

Command 4:

available for any PlanItem for which future appearances may exist.

Do not show impossible actions as though they will work.

---

# 58. Confirmation UX — Command 1

Existing occurrence delete confirmation may remain.

Explain:

```text
only this occurrence is removed
```

---

# 59. Confirmation UX — Command 2

Explain:

```text
This occurrence/day remains.

Future occurrences from this same recurring time slot will stop.

Other recurring times remain.

Manual occurrences remain.
```

---

# 60. Confirmation UX — Command 3

Explain:

```text
This day remains.

All future recurring occurrences of this PlanItem stop.

Manual future occurrences remain.
```

---

# 61. Confirmation UX — Command 4

This is the broadest/destructive action.

Explain clearly:

```text
This day remains.

All future recurring planning stops.

All future occurrences of this PlanItem are removed,
including occurrences added manually.
```

Require explicit confirmation.

Do not make it the accidental default action.

---

# 62. Segment selection UX

If user selected:

```text
Seg 2
```

and opens planning/deletion actions:

the UI acts on:

```text
owning occurrence
```

Make parent identity clear.

Do not imply:

```text
stop only this segment
```

---

# 63. Authoritative success flow

For Commands 2–4:

```text
command
→ success
→ GET planner-state
→ hydrate
```

Do not manually remove rows from store as authoritative domain state.

---

# 64. Success + GET failure

If command succeeded but GET failed:

```text
recovery = GET only
```

Do NOT resend destructive command.

---

# 65. Ambiguous transport failure

If frontend cannot know whether destructive command committed:

```text
NO automatic replay
```

Perform authoritative GET before allowing another attempt.

This is especially important for bulk deletion.

---

# 66. Double-submit

While command is pending:

```text
disable duplicate confirmation/submission
```

One intent must send at most one active mutation request.

---

# 67. Selection after success

After authoritative hydrate:

If selected occurrence still exists:

```text
keep selection
```

Commands 2–4 keep cutoff-day occurrence, so selection should normally survive.

If exact selected segment survives:

```text
keep selectedSegmentId
```

Clear only dangling IDs.

---

# 68. Expanded parent after success

Preserve expansion for surviving cutoff-day parent.

Do not collapse unrelated planner state.

---

# 69. Planner chronology regression

Do not regress 05.7.5.11 chronology.

Expanded segments must still interleave globally:

```text
A1
B
A2
```

---

# 70. Conflict UX regression

Do not regress:

```text
segment conflict confirmation

realized-time acknowledgement

stale confirmation handling

structural conflict draft preservation
```

---

# 71. Apply Week/Future regression

Apply Week/Future remain segment-aware and rejection-only for conflicts.

They must additionally respect any persisted recurrence cutoffs.

They must not silently resurrect stopped planning.

---

# 72. Segment status regression

PATCH segment status remains segment-aware and conflict rejection-only.

No changes to this domain.

---

# 73. Reconciliation regression

Bootstrap remains:

```text
POST reconcile
→ GET planner-state
→ hydrate
```

Stopped planning must remain stopped after bootstrap.

---

# 74. Generation regression

After stopping a slot/schedule:

trigger whatever normal generation path would ordinarily materialize future
occurrences.

Verify:

```text
stopped dates do NOT return
```

This is a critical persistence test.

---

# 75. Restart Flask regression

Persist stop command.

Restart/recreate service context.

Re-read/generate.

Expected:

```text
cutoff still enforced
```

This proves the feature is not memory-only.

---

# 76. Pure/domain tests

Add focused tests for scope classification.

Given selected occurrence:

```text
occurrenceId

planItemId

sourceGenerationSlotId

date D
```

verify target sets for:

```text
this occurrence

this slot after D

recurring schedule after D

all PlanItem appearances after D
```

---

# 77. Exclusive cutoff tests

Explicitly verify:

```text
date < D → untouched

date == D → untouched

date > D → affected according to scope
```

for Commands 2–4.

---

# 78. Slot provenance test

Future customized occurrence:

```text
original slot B 14–17

occurrence changed to 13–18

source_generation_slot_id = B
```

Command 2 on B:

```text
must remove it
```

---

# 79. Other-slot preservation test

Command 2:

```text
A remains

B stops

C remains
```

---

# 80. Manual preservation test

Command 2:

```text
manual future occurrence remains
```

Command 3:

```text
manual future occurrence remains
```

Command 4:

```text
manual future occurrence removed
```

---

# 81. All-recurring test

Command 3 must stop:

```text
all recurring-origin occurrences
```

after D for selected PlanItem.

No GenerationSlot may regenerate them.

---

# 82. All-appearances test

Command 4 must:

```text
stop recurrence

delete generated future occurrences

delete manual future occurrences
```

while preserving:

```text
PlanItem itself

D

history < D
```

---

# 83. Non-recurring PlanItem test

If PlanItem has no recurring schedule:

Command 3 should be:

```text
unavailable / controlled no-op/error
```

according to UI/backend convention.

Command 4 may still remove:

```text
manual future occurrences
```

after D.

---

# 84. Manual selected occurrence test

If selected occurrence is manual:

Command 2:

```text
not applicable
```

Command 3:

may still operate on the PlanItem's recurrence if one exists.

Command 4:

operates on all PlanItem future occurrences.

---

# 85. Historical cutoff test

Attempt command from:

```text
D < today
```

Expected:

```text
controlled rejection
```

No writes.

---

# 86. Today cutoff test

Selected occurrence today:

```text
today occurrence remains

tomorrow onward affected
```

---

# 87. Future cutoff test

Selected future D:

```text
D remains

D+1 onward affected
```

---

# 88. Referenced source test

Future occurrence targeted for deletion is referenced by surviving historical
provenance.

Expected:

```text
controlled rejection

atomic rollback
```

unless the full referencing graph is also legitimately part of the same
deletion set and tested safe.

---

# 89. Atomicity tests

Force failures during:

```text
cutoff persistence

slot update

config update

occurrence deletion

cascade-sensitive operation

final commit
```

Expected:

```text
no partial cutoff

no partial future deletion

no recurrence configuration divergence
```

---

# 90. Concurrency

Test where practical:

```text
stop-slot command
vs
Apply Future

stop-all recurrence
vs
generation

delete-all future
vs
manual occurrence creation
```

Use SERIALIZABLE behavior.

No lost cutoff or half-deleted schedule.

---

# 91. Migration 005 integration tests

If migration 005 is necessary:

real PostgreSQL 16:

```text
001
→ 002
→ 003
→ 004
→ 005
```

Verify old schedules:

```text
remain unlimited by default
```

and new cutoff fields/constraints behave correctly.

---

# 92. Existing schema path

If audit proves no migration 005 is required:

document exactly how existing persisted schema represents an unbounded
post-date stop.

Prove it survives regeneration/restart.

Do not merely assert it.

---

# 93. PostgreSQL real Command 2

Create:

```text
A

B

C
```

with materialized future occurrences.

Customize one future B occurrence.

Add manual occurrence.

Stop B after D.

Verify real DB:

```text
D kept

future B removed

custom B removed

A/C kept

manual kept

slot cannot regenerate > D
```

---

# 94. PostgreSQL real Command 3

Stop all recurrence after D.

Verify:

```text
D kept

future generated A/B/C removed

manual future occurrence kept

future recurring generation blocked
```

---

# 95. PostgreSQL real Command 4

Delete all appearances after D.

Verify:

```text
D kept

generated future removed

customized generated future removed

manual future removed

recurrence cannot regenerate
```

---

# 96. PostgreSQL individual DELETE regression

Verify Command 1 still works:

```text
generated single occurrence

manual single occurrence

multi-segment occurrence

referenced source rejection
```

---

# 97. Frontend tests — menu

Test availability:

```text
generated occurrence
→ all four applicable when schedule exists

manual occurrence
→ no "this slot" action

non-recurring PlanItem
→ recurring-stop action unavailable
```

---

# 98. Frontend tests — Command 2

Verify:

```text
confirmation

one POST

GET

hydrate

selected D remains
```

No local deletion loop.

---

# 99. Frontend tests — Command 3

Verify explanatory text makes clear:

```text
manual future occurrences remain
```

Then:

```text
command
→ GET
→ hydrate
```

---

# 100. Frontend tests — Command 4

Verify stronger destructive explanation states:

```text
manual future occurrences are also removed
```

Double-submit protected.

---

# 101. Network recovery tests

For Commands 2–4 test:

```text
command success + GET failure
→ GET-only retry
```

and:

```text
ambiguous command transport failure
→ no automatic destructive replay
```

---

# 102. Browser verification

Use mocked or isolated schema-compatible backend.

DO NOT use `vcs_dev`.

Desktop:

```text
1440×900
```

Mobile:

```text
~390×844
```

---

# 103. Browser — four actions

Verify the action menu/dialog makes the distinction understandable.

Specifically verify the user can distinguish:

```text
this occurrence

this recurring slot

all recurring planning

all future appearances
```

---

# 104. Browser — slot stop

Using Uber-like scenario:

```text
A / B / C
```

confirm after authoritative hydrate:

```text
A visible

B future gone

C visible
```

---

# 105. Browser — all recurrence stop

Confirm:

```text
generated future gone

manual future remains
```

---

# 106. Browser — all appearances stop

Confirm:

```text
generated future gone

manual future gone
```

---

# 107. Responsive behavior

No horizontal overflow.

Confirmation text must remain readable.

Do not redesign VCS.

Preserve:

```text
dark/gold identity

planner controls

chronology
```

---

# 108. Active writer inventory

Update the 05.7.5.11 writer inventory with the new command endpoints.

At minimum:

```text
PlanItem create

segment status

planner reconcile

translate

structure

reset segmentation

single occurrence DELETE

stop-slot-after

stop-recurring-after

delete-future-after

Apply Week

Apply Future
```

For each report:

```text
endpoint

service

tables modified

segment-aware?

aggregate-safe?

scope

schema-ready?
```

---

# 109. No local-only planning action

At phase completion:

```text
Detener planificación
```

must not exist as an authoritative memory-only action.

Every exposed planner termination action must:

```text
persist backend state

or

be removed
```

---

# 110. No schema-003 writer regression

05.7.5.11 established:

```text
no active application writer requires schema 003
```

This must remain true.

Do not reactivate:

```text
PATCH parent status

status_reason

legacy override writer
```

---

# 111. Full frontend suite

Run:

```text
for test_file in modules/gestor_de_habitos/tests/*.test.mjs
do
  node "$test_file" || exit 1
done
```

Report exact file/test result.

---

# 112. Full backend suite

Run:

```text
.venv/bin/python -m unittest discover \
  -s modules/gestor_de_habitos/backend \
  -p 'test_*.py'
```

Report opt-in skips honestly.

---

# 113. Real PostgreSQL integration

Run all relevant isolated suites.

If 005 exists:

```text
schema target = 001→005
```

otherwise:

```text
001→004
```

Include regression:

```text
segment conflict engine

recurring Apply Week/Future

single DELETE

new termination commands
```

---

# 114. Syntax / consistency

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

# 115. Still NO real rollout

Even if this phase passes:

```text
DO NOT migrate vcs_dev
```

Do not apply:

```text
004

or 005 if created
```

to real user data.

That belongs exclusively to:

```text
05.7.5.13
```

---

# 116. Documentation

Update normative/project documentation with the four command semantics.

Document explicitly:

```text
D kept

>D affected
```

and scope identities:

```text
occurrenceId

source_generation_slot_id

recurrence

plan_item_id
```

---

# 117. If migration 005 exists

Update DB README/migration documentation to state:

```text
vcs_dev still has NOT received 004/005
```

Do not imply rollout occurred.

---

# 118. Git rules

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

# 119. Completion report

At completion provide:

## Persistence model audit

Explain exactly how recurrence cutoff is persisted.

State whether migration 005 was required and why.

## Migration

If 005 exists:

```text
filename

schema changes

NULL/backfill behavior

constraints/indexes

001→005 verification
```

## Four commands

For each explain:

```text
identity

cutoff

what is removed

what is preserved

recurrence effect
```

## Command 1

Explain individual occurrence delete and regeneration prevention.

## Command 2

Explain:

```text
source_generation_slot_id identity

customized occurrence behavior

other slots preserved

manual occurrences preserved
```

## Command 3

Explain:

```text
all recurring slots stopped

generated future occurrences removed

manual future occurrences preserved
```

## Command 4

Explain:

```text
recurrence stopped

all future PlanItem occurrences removed

manual included

PlanItem/history preserved
```

## Temporal protection

Explain:

```text
D < today

D == today

D > today
```

## Provenance

Explain:

```text
source_generation_slot_id preservation

source_occurrence_id restrictions
```

## Transactions

Explain:

```text
SERIALIZABLE

lock order

atomic cutoff + cleanup

rollback

concurrency
```

## Frontend

Explain four action labels/applicability and selected-segment→parent behavior.

## Recovery

Explain:

```text
GET-after-success

GET-only retry

ambiguous transport

double submit
```

## Generation

Prove stopped recurrence does not regenerate after:

```text
reconcile

reload

service restart
```

## Apply Week/Future

Explain how cutoffs interact and confirm stopped planning cannot be silently
resurrected.

## PostgreSQL

Report real isolated results for all four scopes.

## Writer inventory

Give complete active mutating endpoint inventory.

## Tests

Give exact commands/results.

## Browser

Report desktop/mobile.

## Safety

Confirm:

```text
vcs_dev untouched

real PlanItems preserved

001–004 unchanged

005 only additive if created

no schema rollout

no auth/security/cloud work

no new conflict semantics
```

## Rollout readiness

Explicitly answer:

```text
Is every exposed planning/deletion action now persisted and schema-ready?
```

and:

```text
Is any active application writer still dependent on schema 003?
```

Required for completion:

```text
YES
NO
```

respectively.

## Remaining work

State exactly what remains for:

```text
05.7.5.13
Final Verification + Real Schema Rollout
```

## Git

Show:

```text
git diff --stat

git status --short --untracked-files=all
```

No commit.

No push.

---

# 120. Definition of done

This phase is complete when:

```text
"Eliminar solo esta aparición"
is persisted

"Detener este horario después de este día"
is persisted

"Detener toda la planificación recurrente después de este día"
is persisted

"Eliminar todas las apariciones después de este día"
is persisted

selected date D is always preserved

history before D is always preserved

slot stop uses source_generation_slot_id

customized slot-origin occurrences remain attributable to that slot

other recurring slots survive slot-only stop

manual occurrences survive slot-only stop

manual occurrences survive recurring-only stop

manual occurrences are removed by all-appearances stop

all-appearances stop also prevents recurrence regeneration

recurring cutoffs survive reload/restart/reconcile

no finite fake exclusion horizon is used

historical slot provenance is preserved

segment selection resolves to owning occurrence

all commands are backend-authoritative

no client deletion loop exists

success hydrates from GET

ambiguous failures never auto-replay destructive commands

transactions are atomic

schema-004/005 PostgreSQL integration passes

05.7.5.11 conflict UX/chronology remains green

Apply Week/Future do not silently resurrect stopped schedules

no active writer requires schema 003

vcs_dev remains untouched
```

---

# Final principle

These four actions are not interchangeable.

They represent four different identities:

```text
Occurrence
→ this concrete appearance
```

```text
GenerationSlot
→ this recurring time/source
```

```text
Recurring schedule
→ all automatic planning for the PlanItem
```

```text
PlanItem
→ every future appearance regardless of origin
```

Therefore:

```text
DELETE THIS OCCURRENCE
≠
STOP THIS SLOT
≠
STOP RECURRENCE
≠
DELETE ALL FUTURE APPEARANCES
```

And for every future-cutoff command:

```text
D remains.

History remains.

Only dates > D are affected.
```

Runtime customization does not erase provenance.

If an occurrence was born from Slot B:

```text
source_generation_slot_id = B
```

then it remains part of Slot B's recurring lineage even if its runtime time was
later changed.

That provenance, not its current clock time, determines the scope of
"Detener este horario".
