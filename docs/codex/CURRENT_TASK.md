# CURRENT TASK

## OccurrenceSegment v1 — Backend Read Compatibility

### Objective

Adapt the backend read path so it can correctly read and serialize the
PostgreSQL schema produced by:

```text
001
→ 002
→ 003
→ 004
```

The primary target of this phase is:

```text
GET planner-state
```

and the backend structures directly required to support that read path.

This phase must make the backend understand:

```text
Occurrence
+
1..N OccurrenceSegments
+
materialized occurrence aggregate
+
conflict metadata
```

without yet implementing segment mutations or the new conflict engine.

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

Also inspect the database migrations:

```text
modules/gestor_de_habitos/db/migrations/001_initial_schema.sql

modules/gestor_de_habitos/db/migrations/002_fix_occurrence_status_context.sql

modules/gestor_de_habitos/db/migrations/003_multi_slot_scheduling.sql

modules/gestor_de_habitos/db/migrations/004_occurrence_segments.sql
```

Read relevant existing backend tests before modifying implementation.

---

# Authority hierarchy

Use:

```text
CURRENT_TASK.md
→ current implementation scope

OCCURRENCE_SEGMENT_DECISIONS.md
→ approved technical decisions

OCCURRENCE_SEGMENT_V1.md
→ approved model

STATUS_CONFLICT_RULES.md
→ approved domain/product behavior

TECHNICAL_AUDIT
→ evidence about current implementation and alternatives
```

Do not silently reinterpret approved rules.

---

# Scope

This task is limited to:

```text
backend read compatibility
planner-state repository
planner-state service / serialization
read-side validation
backend tests
PostgreSQL integration tests for reading schema 004
```

Do NOT implement write-side OccurrenceSegment behavior yet.

---

# 1. Inspect working tree first

Before editing:

```text
git status --short --untracked-files=all
git diff --stat
```

Preserve all existing user modifications.

Do not revert architecture documents, migration 004 or existing work.

---

# 2. Database safety

Do NOT apply migration 004 to:

```text
vcs_dev
```

Do NOT query or mutate real development data for this task.

Use:

```text
isolated / ephemeral PostgreSQL 16
```

for schema-004 integration verification.

Do not expose credentials or private `.env` contents.

---

# 3. Migration files remain immutable

Do NOT modify:

```text
001_initial_schema.sql
002_fix_occurrence_status_context.sql
003_multi_slot_scheduling.sql
004_occurrence_segments.sql
```

Migration 004 is input to this task, not the implementation target.

If a genuine defect is discovered in 004:

```text
STOP before changing it
```

and report:

```text
finding
impact
possible fixes
recommendation
```

because migration architecture has already been approved and verified.

---

# 4. Primary backend target

Adapt the backend read path used by:

```text
GET planner-state
```

so it can read occurrences from schema 004.

Inspect at minimum:

```text
modules/gestor_de_habitos/backend/repositories/planner_state_repository.py

modules/gestor_de_habitos/backend/planner_state_service.py

modules/gestor_de_habitos/backend/app.py
```

and any directly related model/helper/test files.

Do not assume these are the only relevant files.

Follow actual call paths.

---

# 5. Read `occurrence_segments`

Planner-state must read:

```text
public.occurrence_segments
```

for every occurrence.

Each occurrence must expose:

```text
segments[]
```

with at least:

```text
id
startTime
endTime
status
```

---

# 6. Deterministic segment ordering

Segments must be serialized deterministically using:

```text
start_time
end_time
id
```

equivalent ordering.

Do not persist or invent:

```text
segment ordinal
segment number
position
```

UI labels such as:

```text
Seg 1
Seg 2
```

will be derived later.

---

# 7. Parent fields remain available

The planner-state occurrence contract must continue to include the existing
general occurrence fields:

```text
id
planItemId
date
startTime
endTime
status
sourceGenerationSlotId
```

`startTime` and `endTime` remain:

```text
general occurrence envelope
```

They are NOT replaced by segment boundaries.

---

# 8. `status` remains materialized parent aggregate

In this phase:

```text
occurrence.status
```

must be read from the persisted parent.

Do NOT yet implement:

```text
deriveOccurrenceStatus(...)
```

as write authority.

That belongs to a later phase.

Do not recalculate or overwrite aggregate status during GET.

---

# 9. Read-side integrity

Planner-state must not silently fabricate or repair structural data.

At minimum detect invalid read states such as:

```text
occurrence with zero segments

segment with unknown status

segment outside parent occurrence identity/association

duplicate segment identity in assembled state

invalid time serialization
```

Where practical on the read side also validate:

```text
segment.start_time < segment.end_time

segments are ordered deterministically
```

Do not silently:

```text
create a missing segment
truncate times
repair parent status
rewrite metadata
```

---

# 10. Segment bounds

The approved rule is:

```text
occurrence.start_time <= segment.start_time

segment.end_time <= occurrence.end_time
```

Although service-level write enforcement belongs to a later phase,
planner-state may detect violations when reading.

If detected:

```text
fail safely
```

rather than presenting corrupted planner state as valid.

Do not mutate the database from GET.

---

# 11. Sibling overlap

Migration 004 already protects sibling overlap through PostgreSQL.

The read path does not need to become a second conflict engine.

It may assert obvious structural consistency in tests, but do not duplicate
the full exclusion-constraint implementation in Python.

---

# 12. `conflict_reason`

Schema 004 renamed:

```text
status_reason
```

to:

```text
conflict_reason
```

All planner-state read SQL for schema 004 must use:

```text
conflict_reason
```

Do not query the old physical column in the new-schema read path.

---

# 13. Conflict context API

Expose the new semantic API field:

```text
conflictContext
```

when conflict metadata exists.

Conceptual shape:

```js
{
  reason: "priority_override",
  sourceOccurrenceId: "..."
}
```

Allowed reasons in schema 004:

```text
priority_override
user_forced_override
```

---

# 14. Conflict context pair

The database guarantees conflict metadata as a pair.

Planner-state must treat:

```text
conflict_reason
source_occurrence_id
```

as one context.

Valid:

```text
both NULL
```

or:

```text
both present
```

Do not fabricate one side.

---

# 15. Historical conflict semantics

Do NOT preserve the old assumption:

```text
conflict context only valid when status is cancelled/not_finished
```

That rule was removed by migration 004.

`conflictContext` is historical structural metadata.

It may exist even if the current aggregate status is something else.

---

# 16. `statusContext` compatibility

The final public direction is:

```text
conflictContext
```

not:

```text
statusContext
```

However the frontend has not yet been migrated.

For this phase, a short-lived compatibility alias MAY be emitted if required
to keep existing read consumers/tests operational.

If an alias is used:

```text
conflictContext
```

must remain the canonical source.

Never maintain:

```text
two independent contexts
```

or two independent pieces of state.

Document clearly:

```text
where the alias exists
why it exists
when it should be removed
```

Do not preserve old semantic restrictions merely to satisfy the alias.

---

# 17. `originReason`

Planner-state must support reading:

```text
origin_reason
```

and expose conceptually:

```text
originReason
```

Allowed current non-null value:

```text
conflict_insertion
```

When DB value is NULL:

```text
omit the optional API field
```

or follow the repository's established nullable-field convention.

Do not invent:

```text
normal
normal_creation
```

---

# 18. `lastConflictAction`

Planner-state must support:

```text
last_conflict_action
```

and expose:

```text
lastConflictAction
```

Allowed non-null values:

```text
conflict_insertion
conflict_move
```

Do not derive history beyond the stored value.

---

# 19. `sourceGenerationSlotId`

Preserve current support for:

```text
sourceGenerationSlotId
```

No recurrence semantics change in this phase.

---

# 20. No invented segment IDs

Never create segment IDs during:

```text
hydrate
serialization
fallback
GET
```

Segment IDs must come from:

```text
occurrence_segments.id
```

persisted by PostgreSQL.

If a parent has no persisted child:

```text
that is invalid schema state
```

not a reason to fabricate a segment.

---

# 21. Planner-state query consistency

Parent occurrences and child segments must be read from:

```text
the same coherent database snapshot
```

Preserve the existing read transaction semantics, currently based on:

```text
REPEATABLE READ
READ ONLY
```

or an equivalent verified approach.

Do not fetch parents and segments through unrelated snapshots.

---

# 22. Avoid N+1 queries

Do not issue:

```text
one segment query per occurrence
```

for planner-state.

Prefer a bounded query strategy such as:

```text
one parent query
+
one segments query
```

within the same read transaction,

or another clean equivalent.

The implementation should remain understandable and testable.

---

# 23. Repository responsibility

Repository code should:

```text
read rows
map DB columns
return structured persistence data
```

Do not move aggregate/domain mutation rules into the repository.

---

# 24. Service responsibility

Planner-state service should:

```text
assemble API representation
validate supported stored values
validate references required by the contract
serialize times
attach ordered segments
```

Do not implement future:

```text
split
trim
translate
reconciliation
conflict resolution
```

here.

---

# 25. Time serialization

Continue canonical API time representation:

```text
HH:MM
```

Preserve existing rejection behavior for unsupported subminute DB values.

Do not silently truncate:

```text
seconds
microseconds
```

---

# 26. PostgreSQL integration fixture

Add or extend isolated PostgreSQL tests so schema 004 is exercised.

Test flow should include:

```text
001
→ 002
→ 003
→ 004
```

then insert/read representative schema-004 data.

Do not use:

```text
vcs_dev
```

---

# 27. Minimum planner-state integration cases

Verify at least:

### Single segment

```text
Occurrence 08:00–10:00 pending

Segment:
08:00–10:00 pending
```

serializes correctly.

### Multiple segments

```text
Occurrence 13:00–17:00 in_progress

Segments:
13:00–14:00 completed
14:30–17:00 pending
```

serializes both children in deterministic order.

### Conflict metadata

Verify:

```text
priority_override
```

and:

```text
user_forced_override
```

can be read without assuming parent status must be cancelled/not_finished.

### Origin metadata

Verify:

```text
originReason = conflict_insertion
```

when present.

### Last conflict action

Verify:

```text
conflict_insertion
conflict_move
```

when present.

### Generation provenance

Verify:

```text
sourceGenerationSlotId
```

is preserved.

---

# 28. Invalid read-state tests

Add focused tests for safe rejection of invalid states where possible.

Examples:

```text
parent with zero segments

invalid subminute time

segment outside parent envelope
```

For DB-protected states such as sibling overlap:

```text
the database constraint test may remain the proof
```

rather than bypassing PostgreSQL protections unnaturally.

---

# 29. Existing legacy backend tests

Update tests only where required by the new read contract.

Do not rewrite unrelated tests.

Preserve existing behavior where not contradicted by approved schema 004.

---

# 30. Backend runtime writes remain out of scope

Do NOT adapt write behavior yet.

Do not implement schema-004 write compatibility for:

```text
Create PlanItem

PATCH occurrence

DELETE occurrence behavior changes

Apply Week

Apply Future

status mutation

priority override writes

user-forced conflict writes
```

unless a tiny non-behavioral refactor is strictly necessary for the read path.

If a write path becomes visibly incompatible:

```text
document it
```

Do not expand scope to fix it.

---

# 31. No segment creation runtime yet

Do not modify:

```text
plan_item_materializer.py
plan_item_creation_service.py
```

to create segments during real runtime operations in this phase.

That belongs to the later creation/write phase.

---

# 32. No aggregate domain implementation yet

Do NOT implement:

```text
deriveOccurrenceStatus(...)
```

as mutation authority.

Do not update parent status from children.

Read:

```text
stored parent aggregate
```

only.

Aggregate implementation belongs to its dedicated phase.

---

# 33. No reconciliation implementation

Do NOT implement:

```text
pending → not_completed

in_progress → not_finished
```

on segments yet.

Do not introduce:

```text
POST /api/planner/reconcile
```

in this task.

---

# 34. No conflict engine changes

Do NOT change:

```text
blocking status policy

segment-aware conflict detection

priority override engine

split/trim resolution

confirmed conflict snapshots
```

yet.

Even though current code is known to omit `not_finished`, that correction
belongs to the later domain/conflict phase unless required solely by a read
test.

Document the known divergence rather than expanding scope.

---

# 35. No frontend changes

Do NOT modify:

```text
planner-store.js
planner-matrix.js
app.js frontend
conflict-detector.js
occurrence-status.js
plan-item-form.js
frontend API validators
```

during this task.

The frontend read/display compatibility phase comes next.

---

# 36. Existing application compatibility

Because `vcs_dev` remains on schema 003 during this task:

```text
do not claim the local running application is ready for migration 004
```

The purpose is only to prove:

```text
new backend read code
+
schema 004
```

works correctly in isolation.

Real database rollout still requires later write compatibility planning.

---

# 37. Test commands

Run the focused tests required by your implementation.

Also run the existing backend test suite:

```text
.venv/bin/python -m unittest discover \
  -s modules/gestor_de_habitos/backend \
  -p 'test_*.py'
```

Run migration 004 tests:

```text
.venv/bin/python -W error::ResourceWarning \
  -m unittest -v \
  modules/gestor_de_habitos/db/test_migration_004.py
```

If new PostgreSQL integration tests use another command, report it exactly.

Run:

```text
git diff --check
```

before completion.

---

# 38. No fake success

If some existing tests cannot run because they require opt-in infrastructure:

```text
report the skip honestly
```

Do not represent skipped tests as passed.

The new schema-004 read path must have at least one actual PostgreSQL 16
verification, not mocks only.

---

# 39. Documentation

Update backend/database documentation only when necessary to explain:

```text
new planner-state read contract
temporary compatibility alias
schema-004 test procedure
```

Do not create broad speculative documentation.

---

# 40. Git rules

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

Do not revert pre-existing user changes.

---

# 41. Completion report

At completion provide:

## Files changed

List all created/modified files.

## Read path

Explain:

```text
how occurrences are queried

how segments are queried

how they are assembled

how snapshot consistency is preserved
```

## Planner-state contract

Show one representative serialized occurrence with:

```text
segments[]
conflictContext
originReason
lastConflictAction
sourceGenerationSlotId
```

where applicable.

## Compatibility

State explicitly whether:

```text
statusContext
```

still exists temporarily and why.

## Tests

Give exact commands and results.

## Safety

Confirm:

```text
vcs_dev not queried or modified

001/002/003/004 not modified

frontend not modified

runtime segment writes not implemented

reconciliation not implemented

new conflict engine not implemented
```

## Known remaining incompatibilities

List write paths that still cannot safely operate on schema 004.

## Git

Show:

```text
git diff --stat

git status --short --untracked-files=all
```

No commit.

No push.

---

# 42. Definition of done

This task is complete when:

```text
planner-state backend can read schema 004

every occurrence returned contains persisted segments[]

segment IDs come only from PostgreSQL

segments are deterministically ordered

parent envelope fields remain intact

parent status remains the stored materialized aggregate

conflict_reason is read as conflictContext

origin_reason is readable

last_conflict_action is readable

sourceGenerationSlotId remains supported

reads occur from one coherent DB snapshot

schema-004 read path is verified on PostgreSQL 16

existing backend tests remain healthy or justified changes are documented

vcs_dev remains untouched

no write-side OccurrenceSegment behavior was implemented
```

---

# Final principle

This phase teaches the backend to understand the new persisted model.

It does NOT yet teach the backend to modify that model.

Desired transition:

```text
schema 004
        ↓
backend can read it faithfully
        ↓
planner-state exposes persisted segments
        ↓
STOP
```

Do not continue into mutations merely because the new data is now available.
