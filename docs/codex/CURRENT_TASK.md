# CURRENT TASK

## OccurrenceSegment v1 — Backend Segment Domain + Creation + Aggregate Status

### Objective

Implement the first authoritative backend write foundation for
OccurrenceSegment v1.

This phase must introduce:

```text
pure OccurrenceSegment domain rules

deriveOccurrenceStatus(...)

default segment creation

atomic parent + segment creation

schema-004-compatible non-conflicting PlanItem creation

backend blocking-status correction for not_finished
```

This phase does NOT implement structural segment editing or the new conflict
engine.

The primary transition is:

```text
BEFORE

Create PlanItem
→ create Occurrence
→ status stored directly on parent
```

to:

```text
NOW

Create PlanItem
→ create Occurrence
→ create exactly one default OccurrenceSegment
→ derive parent aggregate
→ persist parent + child atomically
```

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

and the backend/frontend work already completed for schema-004 read
compatibility.

Read all relevant existing tests before implementation.

---

# Authority hierarchy

Interpret requirements in this order:

```text
CURRENT_TASK.md
→ current implementation scope

OCCURRENCE_SEGMENT_DECISIONS.md
→ approved technical choices

OCCURRENCE_SEGMENT_V1.md
→ approved model

STATUS_CONFLICT_RULES.md
→ approved domain/product behavior

TECHNICAL_AUDIT
→ evidence and alternatives
```

Do not silently reinterpret approved behavior.

---

# Scope

This task is limited to:

```text
backend pure segment domain

aggregate status derivation

default segment creation

PlanItem creation on schema 004

atomic parent + segment persistence

backend blocking-status correction

focused backend/PostgreSQL tests
```

Do NOT implement:

```text
segment status API

manual segment create/delete

split

trim

resize

reset segmentation

persistent reconciliation

Apply Week segment behavior

Apply Future segment behavior

segment-aware conflict engine

user-forced conflict resolution

frontend changes
```

---

# 1. Inspect working tree first

Before editing:

```text
git status --short --untracked-files=all
git diff --stat
```

Preserve all existing user work.

Do not revert previously completed OccurrenceSegment phases.

---

# 2. Database safety

Do NOT apply migration 004 to:

```text
vcs_dev
```

Do NOT inspect or mutate real development data for this task.

Use:

```text
isolated PostgreSQL 16
```

for actual schema-004 write verification.

Do not expose secrets or private `.env` contents.

---

# 3. Migrations are immutable

Do NOT modify:

```text
001_initial_schema.sql
002_fix_occurrence_status_context.sql
003_multi_slot_scheduling.sql
004_occurrence_segments.sql
```

If a genuine migration defect is discovered:

```text
STOP before changing a migration
```

and report:

```text
finding
impact
alternatives
recommendation
```

---

# 4. Introduce a pure OccurrenceSegment domain responsibility

Create or use an appropriate backend domain module for rules such as:

```text
validate segment status

derive occurrence aggregate

validate a segment collection

blocking status semantics
```

Follow existing repository structure and naming conventions.

Do NOT place these rules inside:

```text
Flask routes

SQL repositories

planner-state renderer

frontend
```

The domain must remain testable without PostgreSQL.

---

# 5. Avoid overengineering the domain module

Do not create a large generic framework.

This phase requires only the domain behavior actually needed now.

Prefer small pure functions with explicit inputs and outputs.

Conceptually useful responsibilities include:

```text
derive_occurrence_status(...)

validate_segment_set(...)
```

but exact names may follow current Python conventions.

---

# 6. Canonical segment statuses

The six canonical statuses remain:

```text
pending

in_progress

completed

not_completed

not_finished

cancelled
```

Do not add aliases.

Do not introduce:

```text
not_realized
paused
skipped
running
```

or speculative future statuses.

---

# 7. Temporal phases

Aggregate derivation must use an explicit temporal phase.

Conceptually:

```text
FUTURE

CURRENT_DAY

PREVIOUS_EDITABLE_DAY

FROZEN_HISTORY
```

Do not use an ambiguous boolean such as:

```text
isHistorical
```

The exact Python representation may follow repository style:

```text
constants
Literal
Enum
validated strings
```

but avoid unnecessary abstraction.

---

# 8. Aggregate status — uniform case

If every segment has the same status:

```text
aggregate = that status
```

Examples:

```text
pending + pending
→ pending
```

```text
completed + completed
→ completed
```

```text
not_finished + not_finished
→ not_finished
```

```text
cancelled + cancelled
→ cancelled
```

---

# 9. Aggregate status — FUTURE

Persisted future segments should only later be allowed to remain:

```text
pending
cancelled
```

For aggregate purposes:

```text
all pending
→ pending

pending + cancelled
→ pending

all cancelled
→ cancelled
```

This phase does NOT need to implement the full future status mutation
validator.

Do not invent realized future states merely to test aggregate behavior.

---

# 10. Aggregate status — CURRENT_DAY

For mixed segment statuses during the current editable day:

If ANY segment is:

```text
completed
in_progress
not_finished
```

then:

```text
Occurrence.status = in_progress
```

Examples:

```text
completed + pending
→ in_progress

completed + cancelled
→ in_progress

not_finished + pending
→ in_progress

in_progress + cancelled
→ in_progress
```

Otherwise, if any segment is:

```text
pending
```

then:

```text
Occurrence.status = pending
```

Example:

```text
pending + cancelled
→ pending
```

Otherwise, if any segment is:

```text
not_completed
```

then:

```text
Occurrence.status = not_completed
```

Example:

```text
not_completed + cancelled
→ not_completed
```

Otherwise:

```text
all cancelled
→ cancelled
```

---

# 11. Aggregate status — historical phases

For:

```text
PREVIOUS_EDITABLE_DAY
FROZEN_HISTORY
```

the stable aggregate follows historical rules after reconciliation.

If all segments have the same status:

```text
aggregate = that status
```

For mixed statuses:

If any segment is:

```text
completed
not_finished
```

then:

```text
Occurrence.status = not_finished
```

Examples:

```text
completed + not_finished
→ not_finished

completed + not_completed
→ not_finished

completed + cancelled
→ not_finished
```

Otherwise, if any segment is:

```text
not_completed
```

then:

```text
Occurrence.status = not_completed
```

Example:

```text
not_completed + cancelled
→ not_completed
```

Otherwise:

```text
all cancelled
→ cancelled
```

---

# 12. Historical transient states

The normative architecture says that after reconciliation historical stable
state must not retain:

```text
pending
in_progress
```

This task does NOT implement reconciliation yet.

The aggregate domain should not silently convert those statuses itself.

Do not hide invalid temporal state by changing segment status inside:

```text
deriveOccurrenceStatus(...)
```

Aggregate derivation:

```text
reads statuses
returns aggregate
```

It does NOT reconcile children.

If phase-specific invalid data must be rejected to preserve clear semantics,
do so explicitly and cover the choice with tests.

Do not mutate input segments.

---

# 13. Aggregate function must be pure

The aggregate function must:

```text
have no DB access

have no Flask access

have no frontend dependency

not mutate its inputs

not modify time

not reconcile statuses

not persist anything
```

Same input:

```text
segments + temporal phase
```

must produce the same result.

---

# 14. Empty segment collection is invalid

Calling aggregate derivation with:

```text
0 segments
```

must fail explicitly.

Do not invent:

```text
pending
null
cancelled
```

as fallback aggregate.

Every valid Occurrence has:

```text
1..N segments
```

---

# 15. Unknown statuses are invalid

The domain must reject:

```text
unknown segment status
```

rather than silently ignoring it.

---

# 16. Default occurrence creation

Every new occurrence materialized through PlanItem creation must receive:

```text
exactly one default segment
```

with:

```text
segment.start_time = occurrence.start_time

segment.end_time = occurrence.end_time

segment.status = initial occurrence status
```

For normal generated occurrences today:

```text
initial segment status = pending
```

---

# 17. Runtime segment IDs

New runtime segments must receive:

```text
independent UUID identities
```

generated by the backend.

Do NOT derive IDs from:

```text
occurrence ID
PlanItem ID
date
time
GenerationSlot ID
ordinal
array index
```

Do not ask PostgreSQL to invent the runtime identity if the application
normally owns entity identity.

Follow the approved architecture and existing backend UUID conventions.

---

# 18. Parent aggregate on creation

The parent status must be created from the segment state.

Conceptually:

```text
Segment 1
status = pending

deriveOccurrenceStatus(...)
→ pending

Occurrence.status = pending
```

Do not create an independent parent status that could disagree with its
segment.

---

# 19. Creation candidate graph

The creation pipeline should conceptually produce:

```text
PlanItem

GenerationConfig

GenerationSlots

Occurrences
    └── OccurrenceSegments
```

before persistence.

The exact internal representation may adapt existing draft structures.

Avoid duplicating the occurrence graph in unrelated layers.

---

# 20. Preserve GenerationSlot semantics

GenerationSlot remains:

```text
planning interval
```

It does NOT gain runtime segments.

A generated occurrence from:

```text
GenerationSlot 13:00–17:00
```

creates:

```text
Occurrence 13:00–17:00

Segment 1 13:00–17:00 pending
```

Do not create recurring segment templates.

---

# 21. `source_generation_slot_id`

Continue assigning:

```text
source_generation_slot_id
```

exactly as the current materialization rules require.

Adding OccurrenceSegment must not change slot provenance.

---

# 22. Atomic persistence

PlanItem creation must persist:

```text
parent occurrence
+
default segment
```

in the same database transaction.

Never allow:

```text
Occurrence committed
with 0 segments
```

because segment insertion failed later.

Any failure must produce:

```text
full rollback
```

of the creation transaction.

---

# 23. Parent and child consistency

For every created occurrence verify before persistence:

```text
segment.occurrence_id = occurrence.id

segment.start_time = occurrence.start_time

segment.end_time = occurrence.end_time

segment.status participates in the derived aggregate

occurrence.status = derived aggregate
```

---

# 24. Repository responsibility

Repository code may:

```text
insert parent rows
insert segment rows
read persistence data
```

but should NOT become the authority for:

```text
aggregate precedence
temporal phase semantics
conflict policy
```

Those remain domain/service responsibilities.

---

# 25. Creation service responsibility

The creation service should orchestrate:

```text
validation

materialization

segment identity creation

aggregate derivation

conflict checks

transaction

repository persistence
```

while preserving existing separation from `app.py`.

Do not move business logic into Flask routes.

---

# 26. Schema-004 column names

All new schema-004-compatible write SQL added or modified during this task
must use:

```text
conflict_reason
```

not:

```text
status_reason
```

However, do not expand this task into rewriting every unrelated write path.

---

# 27. Existing priority override path is NOT segment-aware

Current PlanItem creation can detect conflicts and currently has a
priority-override mutation path.

That old path modifies:

```text
Occurrence.status
```

directly and therefore is NOT valid for OccurrenceSegment v1.

Do NOT reinterpret it as valid merely because blockers currently have one
segment.

---

# 28. Conflict detection may remain legacy temporarily

This phase does NOT implement the new segment-aware conflict engine.

Existing conflict detection may continue to identify that:

```text
a creation conflicts
```

for purposes of guarding the operation.

But it must NOT perform an old parent-level override against schema 004.

---

# 29. Conflicting creation safety

For schema-004-compatible creation:

```text
NON-CONFLICTING creation
→ supported in this phase
```

A creation requiring mutation of another occurrence:

```text
priority override
user-forced override
split
trim
cancel blocker
not_finished transition
```

is NOT implemented yet.

The backend must fail safely rather than applying legacy parent-level conflict
writes.

---

# 30. Existing conflict handshake

The first conflict-detection response may remain useful for identifying a
conflict.

However, a confirmed legacy request must NOT proceed into the old
parent-level override mutation.

If necessary, introduce a controlled backend/domain error indicating that the
conflicting write requires the future segment-aware conflict phase.

Use the existing error architecture where possible.

Do not invent the final segment confirmation contract in this phase.

---

# 31. No partial conflict engine

Do NOT implement a special shortcut such as:

```text
if blocker has one segment,
modify it using old rules
```

That would create two conflict architectures.

Wait for the dedicated segment-aware conflict phase.

---

# 32. Existing priority metadata

This task may read/preserve existing:

```text
conflict_reason
source_occurrence_id
origin_reason
last_conflict_action
```

but normal non-conflicting creation should create:

```text
conflict_reason = NULL

source_occurrence_id = NULL

origin_reason = NULL

last_conflict_action = NULL
```

unless an already-approved rule demonstrably applies.

Do not invent conflict metadata.

---

# 33. `not_finished` occupies schedule

Correct the known backend divergence.

Canonical blocking statuses are:

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

Update the authoritative backend scheduling policy accordingly.

---

# 34. Scope of the `not_finished` correction

The correction should apply to the existing backend policy definition used by
current conflict checks.

Do NOT use this as permission to rewrite the entire conflict engine.

Add/update focused tests proving:

```text
not_finished
→ blocks schedule
```

and:

```text
not_completed
cancelled
→ do not block
```

---

# 35. Frontend blocking policy

Do NOT modify the frontend blocking policy in this task.

Frontend conflict-engine alignment belongs to a later conflict phase unless a
test demonstrates that a tiny parity change is unavoidable.

If parity remains temporarily divergent:

```text
document it explicitly
```

Do not silently expand scope.

---

# 36. Existing planner-state read path

Preserve the completed schema-004 read behavior:

```text
parents + segments

conflictContext

originReason

lastConflictAction

sourceGenerationSlotId
```

Do not regress it while changing creation.

---

# 37. Creation round trip

A successful non-conflicting PlanItem creation against schema 004 should be
verifiable through:

```text
POST create
↓
COMMIT
↓
GET planner-state
```

and return each created occurrence with:

```text
exactly one persisted segment
```

having:

```text
same startTime
same endTime
same status
```

as the newly created parent.

---

# 38. No rematerialization on GET

The returned default segment must be:

```text
the same persisted segment created during POST
```

GET must not create/recreate it.

Segment ID should remain stable across repeated reads.

---

# 39. Multiple generated occurrences

If one PlanItem creation materializes multiple occurrences:

```text
each occurrence gets its own independent default segment
```

Do not reuse one segment ID.

Do not associate a segment with multiple parents.

---

# 40. Multi-slot creation

If current PlanItem creation produces multiple occurrences from multiple
GenerationSlots:

```text
each occurrence
→ own default segment
```

Preserve:

```text
source_generation_slot_id
```

per occurrence.

No GenerationSlot segment template is created.

---

# 41. Manual-date creation

Manual-date generation should follow the same invariant:

```text
each materialized occurrence
→ one equivalent default segment
```

No special second architecture.

---

# 42. Interval/weekly creation

Weekly and interval materialization also follow:

```text
parent occurrence
+
one default pending segment
```

Preserve existing recurrence calculations.

Do not rewrite recurrence logic merely to add children.

---

# 43. No occurrence structural edits

Do NOT implement:

```text
translate existing occurrence

resize existing occurrence

split existing segment

trim existing segment

delete segment

reset segmentation
```

in this phase.

---

# 44. No segment status endpoint

Do NOT create an HTTP endpoint that changes:

```text
OccurrenceSegment.status
```

yet.

That belongs to the later mutation/reconciliation phase.

---

# 45. No persistent reconciliation

Do NOT implement:

```text
pending → not_completed

in_progress → not_finished
```

in persistence yet.

Do not add:

```text
POST /planner/reconcile
```

during this task.

---

# 46. No Apply Week changes

Do NOT make:

```text
Apply Week
```

segment-aware yet.

Its incompatibility with schema 004 should remain explicitly documented.

---

# 47. No Apply Future changes

Do NOT make:

```text
Apply Future
```

segment-aware yet.

Do not change custom-segmentation behavior here.

---

# 48. No frontend changes

Do NOT modify frontend runtime behavior in this phase.

The previous frontend read/display phase is complete.

Do not add:

```text
segment editor
status writes
new conflict UI
```

---

# 49. Testing — pure aggregate domain

Add focused unit tests covering at minimum:

```text
empty segments rejected

unknown status rejected

single pending
single in_progress
single completed
single not_completed
single not_finished
single cancelled
```

And mixed CURRENT_DAY cases:

```text
completed + pending → in_progress

completed + cancelled → in_progress

not_finished + pending → in_progress

in_progress + cancelled → in_progress

pending + cancelled → pending

not_completed + cancelled → not_completed

all cancelled → cancelled
```

And historical cases:

```text
completed + not_finished → not_finished

completed + not_completed → not_finished

completed + cancelled → not_finished

not_completed + cancelled → not_completed

all cancelled → cancelled
```

Also verify the function does not mutate input data.

---

# 50. Testing — creation graph

Add/update tests proving that materialization/creation creates:

```text
one default segment per occurrence
```

with:

```text
new UUID

correct occurrence_id

correct start/end

correct status
```

---

# 51. Testing — atomicity

Use isolated PostgreSQL 16 to verify:

```text
parent + segment commit together
```

and that a forced failure during child persistence results in:

```text
no partial PlanItem graph
```

remaining after rollback.

Do not test this against `vcs_dev`.

---

# 52. Testing — real schema 004 round trip

At least one actual PostgreSQL 16 test must perform a real creation against:

```text
001
→ 002
→ 003
→ 004
```

and then verify persisted:

```text
PlanItem

Occurrence

OccurrenceSegment
```

through the real backend read path.

Mocks alone are insufficient.

---

# 53. Testing — stable segment ID

Verify:

```text
POST create
GET planner-state
GET planner-state again
```

returns the same persisted:

```text
segment.id
```

for the created occurrence.

---

# 54. Testing — several occurrences

Include at least one creation that materializes more than one occurrence and
verify:

```text
N occurrences
→ N distinct default segments
```

with the correct parent relationships.

---

# 55. Testing — `not_finished`

Verify backend conflict policy treats:

```text
not_finished
```

as blocking.

Also preserve tests showing:

```text
not_completed
cancelled
```

are non-blocking.

---

# 56. Testing — conflict write guard

Add a focused test demonstrating that schema-004 creation does NOT use the
legacy parent-level priority override mutation.

A request requiring such a write must:

```text
fail safely / remain unresolved
```

according to the chosen controlled error behavior.

No blocker parent/segment should be partially changed.

---

# 57. Existing tests

Run the existing backend suites.

Update expectations only where the approved schema-004 write contract changes.

Do not rewrite unrelated tests.

---

# 58. PostgreSQL integration

Use the existing ephemeral PostgreSQL 16 harness where possible.

Do not create another unrelated integration framework if the migration test
infrastructure can be reused cleanly.

---

# 59. No fake compatibility

Do not claim:

```text
schema 004 is now fully runtime-ready
```

after this task.

Only these writes become supported:

```text
non-conflicting initial PlanItem creation
+
default segment persistence
```

Other write paths remain intentionally incompatible.

---

# 60. `vcs_dev` remains untouched

Even if creation tests pass against schema 004:

```text
DO NOT apply migration 004 to vcs_dev
```

The application still lacks several required write paths.

---

# 61. Expected transitional state after this phase

Expected architecture:

```text
schema 004
✅

backend read
✅

frontend read/display
✅

backend aggregate domain
✅

non-conflicting PlanItem create + default segments
✅

segment status mutation
❌

persistent reconciliation
❌

structural segment mutations
❌

Apply Week / Future segment-aware
❌

segment-aware conflict engine
❌
```

This transitional state is intentional.

---

# 62. Documentation

Update documentation only if needed to explain:

```text
schema-004 creation support

temporary conflict-write guard

aggregate domain responsibility

remaining incompatible writes
```

Do not create speculative future docs.

---

# 63. Git rules

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

Do not revert existing work.

---

# 64. Test commands

Run all focused tests introduced/modified during this phase.

Also run the complete backend suite:

```text
.venv/bin/python -m unittest discover \
  -s modules/gestor_de_habitos/backend \
  -p 'test_*.py'
```

Run the PostgreSQL 004 migration/integration tests relevant to creation.

Run:

```text
.venv/bin/python -m compileall -q \
  modules/gestor_de_habitos/backend
```

and:

```text
git diff --check
```

If frontend files remain untouched, verify that explicitly through Git diff.

---

# 65. Completion report

At completion provide:

## Files changed

List every created/modified file.

## Domain

Explain:

```text
where deriveOccurrenceStatus lives

accepted temporal phases

aggregate precedence

validation behavior
```

## Creation

Explain:

```text
how default segments are created

where UUIDs come from

how parent aggregate is produced

how parent + child atomicity is maintained
```

## Conflict safety

Explain:

```text
what happens if creation encounters a conflict

how legacy parent-level overrides are prevented
```

## Blocking policy

Confirm:

```text
not_finished is blocking
```

and list all canonical blocking/non-blocking statuses.

## PostgreSQL verification

Explain the actual:

```text
001 → 004
POST
GET
```

round trip tested.

## Tests

Give exact commands and results.

## Safety

Confirm:

```text
vcs_dev was not queried or modified

migrations were not modified

frontend was not modified

segment status endpoint was not added

reconciliation was not implemented

split/trim/resize/reset were not implemented

Apply Week/Future were not made segment-aware

new conflict engine was not implemented
```

## Remaining incompatibilities

List exactly what still prevents schema 004 from becoming the active real
runtime database.

## Git

Show:

```text
git diff --stat

git status --short --untracked-files=all
```

No commit.

No push.

---

# 66. Definition of done

This task is complete when:

```text
a pure backend aggregate function exists

aggregate rules match approved OccurrenceSegment semantics

empty/unknown segment sets are rejected

new occurrences receive exactly one persisted default segment

segment IDs are backend-generated and stable

parent status is derived coherently from its segment

parent + child creation is atomic

non-conflicting PlanItem creation works against schema 004

created data round-trips through planner-state

not_finished blocks schedule in backend

legacy parent-level conflict override is not executed on schema 004

PostgreSQL 16 verifies the write path

vcs_dev remains untouched

no unrelated OccurrenceSegment write behavior is implemented
```

---

# Final principle

This phase establishes the first valid write into the new model.

The invariant is:

```text
Occurrence
cannot be born alone.

Occurrence
must be born together with
at least one persisted OccurrenceSegment.
```

For normal creation in this phase:

```text
Occurrence
└── Segment 1
    same start
    same end
    pending
```

The parent status is the aggregate of its children.

Do not continue from this foundation into structural editing, reconciliation
or conflict resolution until those phases are explicitly authorized.
