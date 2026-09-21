# CURRENT TASK

## OccurrenceSegment v1 — Frontend Structural Segment Editor

### Objective

Connect the completed backend structural OccurrenceSegment APIs to the planner
frontend through a local draft editor.

The frontend must allow the user to manually edit the temporal structure of
one persisted occurrence without persisting intermediate states.

The authoritative workflow is:

```text
persisted occurrence
        ↓
open structural editor
        ↓
create LOCAL DRAFT
        ↓
user edits envelope / segments
        ↓
draft may temporarily be invalid
        ↓
Save
        ↓
one explicit backend structural command
        ↓
backend validates complete final state
        ↓
GET planner-state
        ↓
hydrate authoritative graph
```

This phase integrates:

```text
translate

complete structure replacement

reset segmentation
```

It does NOT implement recurring structural propagation or automatic conflict
resolution.

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

Also inspect the completed backend structural implementation:

```text
occurrence_structure_domain.py

occurrence_structure_service.py

repositories/occurrence_segment_repository.py

app.py
```

and the existing frontend architecture:

```text
planner-api.js

planner-bootstrap.js

app.js

planner-store.js

planner-matrix.js

occurrence-mutation.js

occurrence-segments.js

occurrence-status.js
```

Read the relevant frontend tests before implementation.

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
→ approved product/domain rules

TECHNICAL_AUDIT
→ evidence/history
```

Do not silently reinterpret approved behavior.

---

# Scope

This task is limited to:

```text
frontend structural draft model

frontend structural editor UI

manual occurrence envelope editing

manual segment start/end editing

manual segment add

manual segment remove

manual split representation through draft editing

manual trim representation through draft editing

manual resize through complete final-state save

explicit pure translate integration

reset segmentation UI

structural API client integration

authoritative GET-after-write refresh

selection / expansion preservation

minimal CORS for structural routes

frontend tests

browser verification
```

Do NOT implement:

```text
occurrence date movement

Apply Week segment propagation

Apply Future segment propagation

recurring segment templates

priority conflict resolution

user-forced conflict resolution

automatic conflict split/trim

conflict confirmation handshake

planner global chronology redesign

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

Frontend verification should use:

```text
frontend mocks

isolated API fixtures

existing browser test strategy
```

If backend/database verification becomes necessary, use isolated PostgreSQL 16
only.

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

# 4. Existing backend structural API is authoritative

Consume the routes implemented in the previous phase.

Expected routes:

```text
POST /api/occurrences/<occurrence_id>/translate

PUT /api/occurrences/<occurrence_id>/structure

POST /api/occurrences/<occurrence_id>/reset-segmentation
```

Inspect the actual implementation and use its exact contract.

Do NOT redesign backend structural semantics in this phase unless a genuine
integration defect is discovered.

---

# 5. Core frontend principle

The frontend editor owns:

```text
a temporary draft
```

It does NOT own:

```text
persistent structural truth
```

The draft may temporarily contain:

```text
overlap

out-of-bounds values

unfinished times

temporary invalid ordering
```

while the user is editing.

Do not persist until the user explicitly saves.

---

# 6. Never persist intermediate edits

Do NOT perform requests such as:

```text
PATCH segment time

DELETE segment

POST segment

PATCH parent
```

while the user is editing individual fields.

Editing must remain local until:

```text
Guardar
```

---

# 7. Draft source

Opening the structural editor creates a draft from the currently persisted
occurrence.

Conceptually:

```text
draft = clone(
  occurrence.id,
  occurrence.date,
  occurrence.startTime,
  occurrence.endTime,
  occurrence.segments
)
```

Do NOT mutate planner-store persisted objects directly while editing.

---

# 8. Draft identity

Persisted segments keep:

```text
segment.id
```

inside the draft.

New unsaved segments must NOT receive a fake persisted segment ID.

Use a separate transient frontend identity such as:

```text
draftKey
```

if rendering requires stable local keys.

Never send:

```text
draftKey
```

to the backend.

---

# 9. New segment identity

For a new draft segment:

```text
persisted id = absent
```

On save:

```text
omit id
```

The backend generates the real UUID.

Do NOT generate a fake persisted UUID in frontend.

---

# 10. Editor ownership

The structural editor operates on:

```text
one occurrence at a time
```

It does not edit:

```text
PlanItem recurrence config

GenerationSlot

other occurrences

future instances
```

This phase is occurrence-local only.

---

# 11. Recurring PlanItems

An occurrence generated by a recurring schedule may still be structurally
edited locally.

That edit applies to:

```text
this persisted occurrence only
```

Do NOT modify its GenerationSlot.

Do NOT propagate its segmentation to Week/Future.

---

# 12. Editor entry point

Add a clear structural edit action for an editable occurrence.

Use wording consistent with the existing Spanish UI.

A concept such as:

```text
Editar horario
```

or:

```text
Editar estructura
```

is acceptable.

Prefer the wording that best fits the current planner UI after inspecting it.

Do not redesign unrelated controls.

---

# 13. Frozen history

For:

```text
FROZEN_HISTORY
```

do not expose an active structural editor action.

Structural information remains visible but read-only.

Backend protection remains authoritative.

---

# 14. Previous editable day

Yesterday remains structurally editable.

Do not locally reconcile transient statuses.

If backend requires:

```text
temporal_reconciliation_required
```

handle it explicitly as described later.

---

# 15. Parent envelope fields

The editor must expose:

```text
Inicio general

Final general
```

corresponding to:

```text
Occurrence.startTime

Occurrence.endTime
```

Do NOT expose:

```text
occurrence_date
```

for editing in this phase.

---

# 16. Segment rows

Show each draft segment with at minimum:

```text
segment label

start time

end time

status

duration

remove action
```

For persisted segments:

```text
status is read-only in the structural editor
```

Existing status changes continue to use the dedicated segment-status UI/API.

---

# 17. Existing segment status must not be editable here

The structural editor must NOT become another path for changing:

```text
persisted Segment.status
```

For existing segments:

```text
show status
do not send status as a mutation choice
```

Follow the backend contract exactly.

---

# 18. New segment status

A new segment has no previous persisted status.

Therefore the draft must collect an explicit canonical status for it.

Allowed values come from the existing canonical status model:

```text
pending
in_progress
completed
not_completed
not_finished
cancelled
```

Use existing temporal display/status-option helpers where appropriate.

The backend remains authoritative.

---

# 19. New status must be visible

Do NOT secretly assign a new segment status that the user cannot see.

If a default is used for UX:

```text
it must be visible in the draft control
```

and changeable before save.

---

# 20. Suggested new-segment default

If a simple default is needed:

```text
pending
```

may be selected only when it is a valid obvious default for the current
temporal context.

Do not force `pending` for yesterday where it would be invalid.

For historical editable dates, require or visibly choose a stable historical
status.

Do not create a second complex temporal engine solely for defaults.

---

# 21. Add segment

Provide:

```text
Agregar segmento
```

This creates only:

```text
a draft child
```

No API request occurs.

The user then provides:

```text
startTime

endTime

status
```

before save.

---

# 22. Remove segment

Removing a segment inside the editor means:

```text
remove it from the draft final set
```

Do NOT immediately call a DELETE endpoint.

On successful final save, an omitted persisted segment will be deleted by the
backend atomically.

---

# 23. Last-segment protection

The final persisted occurrence must have:

```text
at least one segment
```

The UI should avoid making the common path confusing.

It may:

```text
disable remove when only one segment remains
```

or show a clear draft validation message.

Backend validation remains authoritative.

---

# 24. Manual trim

A trim is simply:

```text
edit start/end of an existing segment
```

Example:

```text
08:00–10:00
→
08:00–09:15
```

Keep its persisted ID.

No dedicated `/trim` request exists.

---

# 25. Manual split

A manual split is represented in the draft as:

```text
existing segment adjusted
+
new draft segment
```

Example:

```text
S1
13:00–17:00
```

becomes:

```text
S1
13:00–14:00

NEW
14:30–17:00
```

The persisted segment keeps its ID.

The new segment has no persisted ID.

---

# 26. Dedicated Split button is optional

A dedicated UI control such as:

```text
Dividir
```

is NOT required for definition of done.

If the existing UI makes it simple and clear, it may be added.

Otherwise:

```text
Agregar segmento
+
editar límites
```

is sufficient to represent a manual split.

Do not build complex split UX in this phase.

---

# 27. Manual resize

Changing the parent envelope duration is allowed only as part of a complete
draft.

Example:

```text
parent
08:00–12:00
→
08:00–11:00
```

The frontend must NOT automatically scale:

```text
segments
gaps
durations
```

---

# 28. Resize means user resolves children

When parent duration changes:

```text
children remain exactly as the user edits them
```

If they no longer fit:

```text
draft may temporarily be invalid
```

The user must manually correct them before or during save attempts.

Do NOT auto-compress or auto-trim.

---

# 29. No implicit child scaling

Forbidden frontend behavior:

```text
parent reduced 25%
→ each child reduced 25%
```

or:

```text
parent moved/resized
→ silently squeeze every child into it
```

No such logic.

---

# 30. Pure movement

The backend provides an explicit:

```text
translate
```

command for pure movement.

A pure move means:

```text
same parent duration
+
all existing segments moved by same delta
+
no add/remove
+
no gap change
+
no child-duration change
```

---

# 31. Translate must be tied to explicit intent

Do NOT infer arbitrary structural changes as translation merely because they
look similar after several edits.

Use translate only when the frontend interaction clearly represents:

```text
move the whole occurrence
```

If the existing UI already has a clear whole-occurrence move/edit-time action,
wire that action to:

```text
POST translate
```

when duration remains unchanged.

Otherwise provide the smallest clear movement affordance inside the structural
editor.

---

# 32. Translation UX

A pure movement may allow the user to edit:

```text
new parent start
new parent end
```

while preserving duration.

The backend will move all children by one delta.

Do not locally persist translated children before backend confirmation.

---

# 33. Structure save

All non-pure-translation structural edits use:

```text
PUT /api/occurrences/<id>/structure
```

This includes:

```text
add

remove

trim

manual split

manual child movement

gap changes

parent resize
```

---

# 34. Structure payload

Build the payload from the complete draft final state.

Conceptually:

```json
{
  "startTime": "13:00",
  "endTime": "17:00",
  "segments": [
    {
      "id": "<persisted-id>",
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

Use the exact backend contract.

---

# 35. Persisted child payload

For an existing segment:

```text
send its persisted ID
send structural fields required by backend
do not use the structure endpoint to change status
```

Do not accidentally send stale status as a requested mutation if backend
forbids it.

---

# 36. New child payload

For a new segment:

```text
omit id

send startTime

send endTime

send explicit status
```

Never send:

```text
draftKey
```

---

# 37. Reset segmentation control

Expose an explicit action:

```text
Restablecer segmentación
```

This is destructive to the current child structure.

It must NOT happen accidentally.

---

# 38. Reset confirmation

Before sending reset:

```text
ask for explicit confirmation
```

Reuse the existing confirmation pattern if one exists.

Do not invent a large modal system solely for this action.

---

# 39. Reset payload

Call the existing backend:

```text
POST /api/occurrences/<id>/reset-segmentation
```

with the desired parent:

```text
startTime

endTime
```

Use the exact backend contract.

---

# 40. Reset status authority

Frontend does NOT choose the reset segment status.

Backend behavior is:

```text
previous parent aggregate
→ new Segment status
→ validation
```

Do not duplicate that logic client-side.

---

# 41. Reset success

After successful reset:

```text
GET planner-state
→ hydrate
```

The old selected segment ID will no longer exist.

Expected UI state:

```text
selectedOccurrenceId preserved if parent exists

selectedSegmentId cleared unless authoritative state deliberately selects the new one
```

Do not pretend the new segment has the old identity.

---

# 42. Structural save success

After any successful:

```text
translate

structure replacement

reset
```

always perform:

```text
GET planner-state
→ hydrate authoritative result
```

Do not build the final persisted graph solely from the mutation response.

---

# 43. No optimistic persisted structure

The draft can update visually while the editor is open.

The planner's authoritative occurrence graph must not be permanently replaced
until backend success + GET.

Keep:

```text
draft state
```

separate from:

```text
planner persisted state
```

---

# 44. Mutation coordinator

Follow the existing frontend mutation architecture.

Prefer a structural coordinator flow such as:

```text
guard pending

send command

mark command confirmed

GET planner-state

hydrate

restore valid UI state

clear draft

release pending
```

Do not put network orchestration directly in the matrix view.

---

# 45. Confirmed command + failed GET

Reuse the safety pattern established by segment status mutation.

If:

```text
structural command succeeds
```

but:

```text
GET planner-state fails
```

do NOT send the structural command again on retry.

The next retry must:

```text
perform only authoritative GET
```

until the result is recovered.

This protects against duplicate structural writes.

---

# 46. Pending/double-submit protection

While a structural command is in flight:

```text
disable duplicate Save

disable duplicate Reset

prevent rapid repeated submission
```

Do not send the same command twice.

---

# 47. Cancel editor

`Cancelar` must:

```text
discard local draft

make zero API requests

leave persisted planner state unchanged
```

---

# 48. Draft dirty state

Track whether the structural draft differs from its source where useful.

Do not introduce a large global unsaved-document framework.

A small editor-local dirty flag is sufficient.

---

# 49. Close with unsaved changes

If the current UI already has a confirmation pattern for discarding edits,
reuse it.

Otherwise keep the behavior simple and deterministic.

Do not expand this task into navigation lifecycle management.

---

# 50. Lightweight draft validation

Frontend may perform lightweight validation to improve UX.

Examples:

```text
required HH:MM values

parent start < parent end

at least one segment

segment start < segment end

obvious out-of-bounds segment

obvious sibling overlap
```

This is:

```text
draft readiness UX
```

not authoritative domain validation.

---

# 51. Backend remains authoritative

Do NOT duplicate in frontend the entire backend logic for:

```text
conflicts

completed-time

historical reconciliation

locking

concurrency

aggregate derivation
```

The frontend may anticipate simple errors but must accept backend decisions as
final.

---

# 52. Temporarily invalid drafts are allowed

Do not make time inputs impossible to edit because each keystroke must satisfy
the final graph.

Example:

```text
changing 13:00 to 15:00
```

may temporarily pass through an incomplete value.

The draft may be invalid while editing.

Only persistence requires a valid final state.

---

# 53. Save readiness

It is acceptable to disable Save for clearly malformed draft data such as:

```text
empty time

invalid HH:MM

zero segments
```

Do not block Save solely because the frontend predicts a complex domain rule
that the backend should decide.

---

# 54. Structural conflict response

Backend may return:

```text
409 occurrence_structure_conflict
```

with:

```text
blockers[]
```

Frontend must:

```text
show a clear conflict message

keep the structural draft available

not modify blockers

not automatically retry

not invoke priority resolution
```

---

# 55. Keep draft after conflict

A structural conflict rejection is especially useful because the user can
manually adjust the draft.

Therefore:

```text
409 structure conflict
→ preserve draft
→ show blocker context
→ allow user to edit and Save again
```

Do not discard their work.

---

# 56. Blocker display

When practical, show concise blocker information such as:

```text
hora

status

possibly PlanItem context if already available
```

Do not build the final conflict-resolution modal yet.

No actions such as:

```text
Ajustar blocker

Segmentar blocker

Finalizar blocker

Cancelar blocker
```

in this phase.

---

# 57. Conflict resolution remains forbidden

From a structural conflict response, frontend must NOT:

```text
change blocker status

move blocker

split blocker

trim blocker

priority override

user-forced override
```

Manual editing of the TARGET draft is allowed.

---

# 58. Duration mismatch

If translate returns:

```text
occurrence_translate_duration_mismatch
```

do not silently fall back to structure replacement behind the user's back.

The interaction should remain explicit.

If the user intended resize:

```text
use structural editing flow
```

---

# 59. History frozen error

If backend returns:

```text
history_frozen
```

or equivalent:

```text
show read-only message

do not retry mutation automatically
```

Refresh authoritative state if appropriate.

---

# 60. Temporal reconciliation required

If structural mutation returns:

```text
temporal_reconciliation_required
```

do NOT mutate sibling statuses locally.

Do NOT automatically resend the structural mutation after reconciliation.

A safe recovery is:

```text
POST reconcile
→ GET planner-state
→ invalidate/rebuild stale structural draft
→ tell user to review/retry
```

If implementing automatic reconciliation would complicate the current
architecture, a clear reload/retry message is acceptable.

Document the chosen behavior.

---

# 61. Concurrency conflict

If backend reports a concurrency/serialization conflict:

```text
do not auto-resubmit the structural command
```

Refresh authoritative state according to the existing recovery architecture.

A stale draft must not be silently replayed against a changed graph.

---

# 62. Occurrence not found

If the target occurrence disappeared:

```text
close/invalidate editor

refresh planner-state

clear dangling selectedOccurrenceId / selectedSegmentId as required
```

Do not retain an editor attached to a nonexistent entity.

---

# 63. Persisted-state invalid

If backend reports persisted corruption/inconsistent state:

```text
surface a controlled error

do not attempt client repair
```

---

# 64. Database unavailable

Preserve the draft where safe so the user does not immediately lose manual
work.

Do not claim the change was saved.

---

# 65. API client

Extend the centralized planner API layer with focused functions equivalent to:

```text
translateOccurrence(occurrenceId, startTime, endTime)

replaceOccurrenceStructure(occurrenceId, payload)

resetOccurrenceSegmentation(occurrenceId, startTime, endTime)
```

Use existing request/error conventions.

Views must not call `fetch()` directly.

---

# 66. CORS

Add only the minimum backend CORS support required for browser consumption of:

```text
POST /api/occurrences/<id>/translate

PUT /api/occurrences/<id>/structure

POST /api/occurrences/<id>/reset-segmentation
```

Preserve the existing:

```text
VCS_ALLOWED_ORIGINS
```

architecture.

Do NOT allow:

```text
*
```

Do not redesign CORS globally.

---

# 67. CORS preflight

Ensure an allowed frontend origin can perform:

```text
PUT structure
```

including browser preflight.

Also preserve rejection behavior for unapproved origins.

---

# 68. Selection preservation

After successful command + GET:

```text
selectedOccurrenceId
```

should remain when the occurrence still exists.

Use persisted IDs.

---

# 69. Selected segment after normal structural save

If:

```text
selectedSegmentId
```

refers to a persisted segment that survived the final structure:

```text
preserve selection
```

If that segment was omitted/deleted:

```text
clear selectedSegmentId
```

Do not select another segment by index automatically.

---

# 70. Selected segment after reset

Reset deletes all old segments and creates a new ID.

Therefore:

```text
old selectedSegmentId
→ clear
```

Do not assume:

```text
Segment 1 before reset
==
Segment 1 after reset
```

---

# 71. Expanded occurrence preservation

If the occurrence was expanded before structural save:

```text
keep it expanded
```

when the same parent still exists after hydration.

Expansion remains transient UI state.

---

# 72. New segments after authoritative GET

A newly created draft segment receives its real backend UUID only after:

```text
command
→ GET planner-state
```

Do not attempt to map the transient draft key into a permanent identity by
array position.

---

# 73. Editor after successful save

After authoritative GET succeeds:

```text
close draft editor
```

or rebuild it from the authoritative state only if the current UX clearly
expects it to remain open.

Prefer:

```text
save → close → refreshed planner
```

for this first implementation.

---

# 74. Editor after failed save

For a rejected command:

```text
keep editor open
keep draft
show error
```

unless the error proves the target no longer exists or the draft is stale due
to concurrency.

---

# 75. Single-segment occurrence

The structural editor must work for:

```text
1 segment
```

The user may:

```text
trim it

resize parent + adjust it

add another segment

move the entire occurrence

reset segmentation
```

---

# 76. Multi-segment occurrence

The editor must work for:

```text
N segments
```

without relying on parent status controls.

Each persisted child remains independently identified.

---

# 77. Status controls remain separate

The segment status UI implemented in the previous phase remains active outside
the structural editor.

Do not merge:

```text
status mutation

structural mutation
```

into one generic endpoint or one ambiguous action.

---

# 78. Monthly aggregate

Preserve monthly aggregate semantics.

Structural edits may change parent aggregate only when the backend determines
that the final child set requires it.

Frontend reads the refreshed:

```text
Occurrence.status
```

after GET.

Do not derive a replacement parent status locally.

---

# 79. Duration display

While editing, draft duration display may be computed locally from:

```text
sum of draft segment durations
```

because it is purely presentation.

Recall approved semantics:

```text
structural duration
=
sum ALL segment durations regardless of status
```

Do not treat parent envelope length as actual active duration when gaps exist.

---

# 80. Gap visibility

The editor should make gaps understandable.

It is sufficient that the user can see:

```text
Seg 1 13:00–14:00

Seg 2 16:00–17:00
```

and therefore understand that:

```text
14:00–16:00
```

is free.

Do not create a timeline visualization unless the existing UI makes it trivial.

---

# 81. Segment ordering in editor

Present draft segments chronologically:

```text
startTime

endTime

stable tie-breaker
```

Do not persist an ordinal.

For new draft rows, use a transient tie-breaker if necessary.

---

# 82. Reordering is derived

Do not implement drag-and-drop ordering.

Changing times may cause rows to appear in a new chronological order.

Order is derived from time, not user-managed position.

---

# 83. Ordinal labels remain derived

Labels such as:

```text
Seg 1
Seg 2
Seg 3
```

are presentation only.

Do not send/persist segment number.

---

# 84. Existing expanded child rows

Preserve the current planner read/display model:

```text
parent row
└── child rows when expanded
```

The structural editor may be:

```text
inline

panel

existing edit area
```

depending on current architecture.

Choose the smallest coherent integration.

Do not redesign the entire planner matrix.

---

# 85. Planner chronology limitation remains

Do NOT solve the known limitation where expanded segments remain grouped under
their parent instead of globally interleaving with other occurrences.

That cleanup remains a later phase.

---

# 86. Legacy single-occurrence time mutation paths

Audit existing active frontend paths that edit:

```text
Occurrence.startTime

Occurrence.endTime
```

directly or through legacy parent-level logic.

Normal single-occurrence structural editing must no longer bypass the new
segment-aware API.

Route the normal editable occurrence UX through:

```text
translate
or
replace structure
```

as appropriate.

---

# 87. Legacy recurring mutation paths remain out of scope

Do NOT rewrite:

```text
Apply Week

Apply Future
```

in this phase.

If existing recurring UI offers those actions from a structural editor:

```text
guard/disable them
```

until the next dedicated phase.

Do not fake propagation.

---

# 88. Legacy conflict write path

The previously identified incompatible path:

```text
edit_without_occurrence
→ commitPreparedScheduleChange
```

may still exist for the old conflict system.

Do NOT route the new structural editor through it.

Do NOT attempt to redesign the conflict engine here.

Report whether it remains active and where.

---

# 89. No direct parent-status write

Structural editor code must not call legacy:

```text
setOccurrenceStatus

advanceOccurrenceStatus
```

to compensate for structural changes.

Backend aggregate is authoritative.

---

# 90. No local conflict mutation

Do not call existing local helpers that:

```text
cancel blocker

mark blocker not_finished

change parent status because of conflict
```

from the structural editor.

---

# 91. Accessibility

Structural editor controls need understandable labels.

Time inputs must be associated with:

```text
general start/end

segment start/end
```

Buttons such as:

```text
Agregar segmento

Eliminar segmento

Guardar

Cancelar

Restablecer segmentación
```

must be keyboard reachable.

Do not rely only on color/icons.

---

# 92. Focus

When opening the editor:

```text
focus should move to a meaningful first control
```

where practical.

After save/cancel:

```text
return focus sensibly
```

if existing architecture supports it.

Do not create an elaborate focus-management framework.

---

# 93. Mobile behavior

Verify at the existing mobile breakpoint.

The editor must not create global horizontal overflow.

Segment fields may stack vertically if needed.

Do not shrink controls to unusable sizes merely to keep one row.

---

# 94. Visual identity

Preserve the existing:

```text
dark

gold

VCS planner
```

visual language.

Do not redesign the module.

Use existing spacing, border, button and input patterns where possible.

---

# 95. API unit tests

Add/update tests for:

```text
translate request

structure PUT request

reset request

request methods

URLs

payloads

controlled backend errors

blockers preservation
```

---

# 96. Draft model tests

Test:

```text
opening draft does not mutate persisted occurrence

existing IDs preserved

new rows have no persisted ID

draftKey not serialized

remove only affects draft

cancel sends no request
```

---

# 97. Structure payload tests

Verify exact serialization for:

```text
existing segment

new segment

existing + new

omitted deleted child

multiple segments
```

---

# 98. Existing status serialization test

Prove the structure editor does not accidentally change an existing persisted
segment status.

Follow the backend's exact payload rule.

---

# 99. New status serialization test

Prove a new draft child sends:

```text
explicit status
```

and no fake ID.

---

# 100. Add segment integration test

Start:

```text
Occurrence
└── S1
```

Draft:

```text
S1
NEW
```

Save.

Mock authoritative GET:

```text
S1
S2-real-uuid
```

Verify UI uses the backend-provided S2 ID rather than the draft key.

---

# 101. Remove segment integration test

Start:

```text
S1
S2
```

Draft removes:

```text
S2
```

Verify:

```text
PUT final set contains S1 only

no DELETE request occurs

GET authoritative state contains S1
```

---

# 102. Manual split integration test

Represent:

```text
S1 13:00–17:00
```

as:

```text
S1 13:00–14:00
NEW 14:30–17:00
```

Verify payload identity semantics.

No dedicated backend split endpoint should be called.

---

# 103. Trim integration test

Verify:

```text
S1 08:00–10:00
→
S1 08:00–09:15
```

sends:

```text
same S1 ID
new times
```

---

# 104. Resize integration test

Verify changing parent duration and adjusting children sends:

```text
one complete PUT
```

Do not send:

```text
translate

multiple child PATCHes
```

---

# 105. No auto-scale test

Change parent envelope duration without manually changing children.

Verify frontend does NOT silently alter child times.

Draft may become invalid.

---

# 106. Pure translate integration test

For explicit movement:

```text
same duration
same child structure
```

verify:

```text
POST translate
```

is used.

No structure PUT should be required for that explicit movement interaction.

---

# 107. Translate success test

After:

```text
POST translate success
```

verify:

```text
GET planner-state

authoritative moved children

same persisted child IDs
```

are used for render.

Do not derive final translated children only from local delta.

---

# 108. Reset integration test

Verify:

```text
explicit confirmation

POST reset

GET planner-state
```

and:

```text
old selectedSegmentId cleared
new backend UUID used
```

---

# 109. Reset cancellation test

If user cancels confirmation:

```text
no API request
```

---

# 110. Conflict test

Mock:

```text
409 occurrence_structure_conflict
```

with blockers.

Verify:

```text
draft preserved

error surfaced

no blocker mutation

no automatic conflict-resolution call

no authoritative planner mutation
```

---

# 111. Retry after manual adjustment

After a conflict rejection:

```text
user edits target draft
→ Save again
```

A new structural request is allowed.

This is a new user attempt, not an automatic retry.

---

# 112. Command-success / GET-failure test

Verify:

```text
PUT succeeds

GET fails
```

Then retry/recovery performs:

```text
GET only
```

and does NOT send PUT again.

Test the same safety model for at least one structural command.

---

# 113. Concurrency error test

Mock the actual backend concurrent/serialization error.

Verify:

```text
no automatic structural replay
```

and stale state is not silently accepted.

---

# 114. Reconciliation-required test

Mock:

```text
temporal_reconciliation_required
```

Verify:

```text
no local sibling status rewrite

no automatic resend of structure command
```

Test the chosen recovery behavior.

---

# 115. Frozen UI test

Frozen occurrence:

```text
structural editor entry disabled/hidden

no structural request emitted
```

---

# 116. Selection tests

Verify:

```text
parent survives
→ selectedOccurrenceId survives
```

and:

```text
selected existing child survives
→ selectedSegmentId survives
```

and:

```text
selected removed child
→ selectedSegmentId cleared
```

---

# 117. Expansion test

Expanded multi-segment parent remains expanded after:

```text
structural command
→ GET
→ hydrate
```

when parent survives.

---

# 118. Monthly aggregate regression

Verify refreshed parent aggregate continues to drive monthly display.

Do not change monthly aggregate semantics.

---

# 119. Segment status regression

Verify the existing dedicated:

```text
PATCH segment status
```

flow still works after structural editor integration.

Structural editor must not intercept normal status actions.

---

# 120. Bootstrap regression

Verify startup remains:

```text
POST reconcile
→ GET planner-state
→ hydrate
```

Structural editor integration must not change this order.

---

# 121. CORS tests

Backend CORS tests should verify allowed origins can use:

```text
POST translate

PUT structure

POST reset
```

and that unapproved origins remain rejected.

Do not weaken existing policy.

---

# 122. Frontend full suite

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

number of tests

result
```

---

# 123. Backend regression

Because CORS/app routing may change, run:

```text
.venv/bin/python -m unittest discover \
  -s modules/gestor_de_habitos/backend \
  -p 'test_*.py'
```

Report skips honestly.

---

# 124. Syntax checks

Run `node --check` for every modified JS file.

Also run:

```text
.venv/bin/python -m compileall -q \
  modules/gestor_de_habitos/backend
```

and:

```text
git diff --check
```

---

# 125. Browser verification

Use the same safe browser strategy as the previous frontend integration phase.

Do NOT use real `vcs_dev`.

Verify at minimum:

```text
desktop 1440×900

mobile approximately 390×844
```

---

# 126. Browser — single segment

Verify visually:

```text
open editor

edit times

add segment

remove draft segment

cancel

save
```

with no unexpected planner mutation before save.

---

# 127. Browser — multi-segment

Verify:

```text
existing IDs represented correctly

rows understandable

status read-only for existing children

new child status input

duration display

save/cancel
```

---

# 128. Browser — reset

Verify:

```text
confirmation

success refresh

old child selection cleared

parent preserved
```

---

# 129. Browser — conflict

Mock a structural 409.

Verify:

```text
draft remains visible

error is understandable

user can manually adjust target times
```

---

# 130. Browser — responsive

Verify:

```text
no global horizontal overflow

controls usable

time fields readable

buttons reachable
```

---

# 131. No real schema rollout

Even after this phase passes:

```text
DO NOT apply migration 004 to vcs_dev
```

Remaining incompatible paths still exist.

---

# 132. Expected architecture after this phase

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

segment status backend
✅

persistent reconciliation
✅

frontend segment status
✅

backend structural mutations
✅

frontend structural editor
✅

Apply Week/Future segment-aware
❌

segment conflict-resolution engine
❌

conflict UX
❌

planner chronology final cleanup
❌
```

---

# 133. Legacy path audit

At completion explicitly identify active frontend write paths that still use
legacy occurrence-level schedule/conflict behavior.

Especially inspect:

```text
edit_without_occurrence

commitPreparedScheduleChange

Apply Week

Apply Future
```

Classify each as:

```text
active incompatible

guarded

dormant

not applicable
```

Do not silently leave unknown compatibility.

---

# 134. Runtime readiness statement

Do NOT claim schema 004 is runtime-ready unless all remaining write paths are
compatible.

This phase does not resolve:

```text
recurring propagation

legacy conflict resolution
```

Therefore real migration remains blocked.

---

# 135. Documentation

Update documentation only where necessary to describe:

```text
structural editor behavior

local draft model

authoritative save flow

remaining incompatible legacy paths
```

Do not create speculative future docs.

---

# 136. Git rules

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

# 137. Completion report

At completion provide:

## Files changed

List every created/modified file.

## Editor architecture

Explain:

```text
where draft state lives

how it is cloned

how persisted state stays untouched

how new draft children are identified
```

## UI

Explain:

```text
editor entry point

parent envelope controls

segment controls

add

remove

trim/split representation

resize

translate

reset
```

## API integration

Report final client functions and exact payloads for:

```text
translate

structure replacement

reset
```

## Save behavior

Explain:

```text
draft
→ command
→ GET
→ hydrate
```

and:

```text
command succeeds / GET fails
```

recovery.

## Identity

Explain:

```text
existing IDs

new draft keys

new backend IDs

deleted IDs

reset IDs
```

## Status behavior

Explain:

```text
existing status read-only

new segment explicit status

dedicated status API remains separate
```

## Errors

Explain frontend behavior for:

```text
occurrence_structure_conflict

duration mismatch

history frozen

temporal reconciliation required

concurrent conflict

not found

database unavailable
```

## Selection / expansion

Explain preservation and cleanup rules.

## CORS

Explain minimal structural-route changes.

## Legacy paths

Classify:

```text
edit_without_occurrence

commitPreparedScheduleChange

Apply Week

Apply Future

other parent-level structural writers
```

## Tests

Give exact commands and results.

## Browser verification

Report desktop/mobile behavior.

## Safety

Confirm:

```text
vcs_dev not queried or modified

legacy PlanItems preserved

migrations unchanged

no occurrence date mutation

no Apply Week/Future segment support

no conflict resolution

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

# 138. Definition of done

This task is complete when:

```text
structural edits occur in a separate local draft

editing fields performs no persistence

existing segment IDs survive draft/save

new draft rows have no fake persisted IDs

manual add works

manual remove works through final-state omission

manual trim works

manual split can be represented

resize does not scale children

pure movement uses explicit translate behavior

structure save uses one complete PUT

reset uses explicit backend reset command

backend remains structural authority

GET refreshes authoritative graph after success

confirmed mutation is not resent after GET failure

conflict rejection preserves draft

blockers are not modified

existing statuses are not structurally rewritten

new segments provide explicit status

selection/expansion remain coherent after refresh

frozen history has no active structural edit path

CORS supports structural commands without weakening origins

segment-status flow still works

bootstrap reconciliation still works

frontend/backend tests pass

desktop/mobile behavior is verified

legacy recurring/conflict paths are identified

vcs_dev remains untouched
```

---

# Final principle

The user may freely manipulate:

```text
a draft
```

but VCS persists only:

```text
a complete valid final structure
```

The frontend does not tell PostgreSQL:

```text
"delete this child now"
"move this child now"
"insert this one now"
```

while the edit is unfinished.

Instead:

```text
PERSISTED GRAPH
      ↓
LOCAL DRAFT
      ↓
USER EDITS
      ↓
FINAL CANDIDATE
      ↓
ONE BACKEND COMMAND
      ↓
VALIDATE
      ↓
ATOMIC COMMIT
      ↓
GET AUTHORITATIVE STATE
      ↓
UI
```

Existing child identity belongs to the persisted segment.

New draft identity belongs only to the editor.

The backend decides the final persisted graph.