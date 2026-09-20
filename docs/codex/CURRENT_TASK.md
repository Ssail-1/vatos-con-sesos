# CURRENT TASK

## OccurrenceSegment v1 — PostgreSQL Foundation / Migration 004

### Objective

Implement and verify the PostgreSQL foundation for:

```text
OccurrenceSegment v1
```

This phase must create and test:

```text
004_occurrence_segments.sql
```

using an isolated/ephemeral PostgreSQL 16 database.

This task establishes the database structure required by the approved
OccurrenceSegment architecture.

It does NOT activate OccurrenceSegment behavior in the real application yet.

---

## Required reading

Before making any change, read completely:

```text
AGENTS.md

docs/architecture/STATUS_CONFLICT_RULES.md

docs/architecture/OCCURRENCE_SEGMENT_V1.md

docs/architecture/OCCURRENCE_SEGMENT_TECHNICAL_AUDIT.md

docs/architecture/OCCURRENCE_SEGMENT_DECISIONS.md

modules/gestor_de_habitos/docs/valores.md
```

Also inspect:

```text
docs/codex/planeacion/
docs/codex/PRODUCTION_CONCERNS.md
```

when they contain relevant current architectural context.

The priority of interpretation is:

```text
CURRENT_TASK.md
→ current implementation scope

OCCURRENCE_SEGMENT_DECISIONS.md
→ approved technical choices

OCCURRENCE_SEGMENT_V1.md
→ approved technical model

STATUS_CONFLICT_RULES.md
→ approved product/domain behavior

TECHNICAL_AUDIT
→ evidence and alternatives, not authority over later decisions
```

Do not silently reinterpret approved rules.

---

# Scope

This task is limited to:

```text
PostgreSQL prototype
migration 004
migration/backfill tests
database-level verification
```

Do NOT implement application behavior yet.

---

# 1. Inspect current state first

Before editing:

```text
git status --short --untracked-files=all
git diff --stat
```

Preserve all existing user modifications.

Read the current migrations completely:

```text
modules/gestor_de_habitos/db/migrations/001_initial_schema.sql

modules/gestor_de_habitos/db/migrations/002_fix_occurrence_status_context.sql

modules/gestor_de_habitos/db/migrations/003_multi_slot_scheduling.sql
```

Do not modify migrations 001, 002 or 003.

---

# 2. PostgreSQL version

Target:

```text
PostgreSQL 16
```

All migration behavior must be verified against PostgreSQL 16.

Do not rely on SQLite or another database as proof of correctness.

---

# 3. Ephemeral PostgreSQL only

All migration development and verification in this task must use:

```text
isolated / ephemeral PostgreSQL
```

Do NOT apply migration 004 to:

```text
vcs_dev
```

Do NOT modify real development data.

Do NOT read or modify private `.env` files unless existing project tooling
already uses environment configuration without exposing secrets.

Never print credentials.

---

# 4. Migration file

Create:

```text
modules/gestor_de_habitos/db/migrations/004_occurrence_segments.sql
```

Migration 004 must be written as a forward migration from the exact schema
produced by:

```text
001
→ 002
→ 003
```

Do not rewrite historical migrations.

---

# 5. Create `occurrence_segments`

Create:

```text
public.occurrence_segments
```

with at least:

```text
id UUID PRIMARY KEY

occurrence_id UUID NOT NULL
    REFERENCES public.occurrences(id)
    ON DELETE CASCADE

start_time TIME NOT NULL

end_time TIME NOT NULL

status VARCHAR(...) NOT NULL
```

Status values:

```text
pending
in_progress
completed
not_completed
not_finished
cancelled
```

---

# 6. Local segment constraints

PostgreSQL must directly protect:

```text
id primary key

occurrence parent FK

ON DELETE CASCADE

start_time < end_time

status valid
```

Use explicit, descriptive constraint names consistent with the existing
migration style.

---

# 7. Structural index

Create an index equivalent in purpose to:

```text
(
    occurrence_id,
    start_time,
    end_time,
    id
)
```

for deterministic child lookup/order and mutation support.

The exact name should follow repository conventions.

---

# 8. Sibling overlap prototype

Prototype the approved preferred architecture:

```text
service validation
+
PostgreSQL exclusion constraint
```

for sibling segment overlap.

Two segments belonging to the same occurrence must not overlap.

Adjacency must remain valid:

```text
13:00–14:00
14:00–15:00
```

Semantics:

```text
[start, end)
```

---

# 9. `btree_gist` investigation

In ephemeral PostgreSQL 16:

1. verify whether `btree_gist` is available;
2. verify whether the test/deployment role can create/use it;
3. prototype a clean exclusion constraint;
4. verify adjacency is accepted;
5. verify true sibling overlap is rejected;
6. verify different occurrences may contain overlapping segment ranges.

Do not assume success.

Record the result in tests/report.

---

# 10. Fallback if `btree_gist` is not viable

If `btree_gist` cannot be used safely:

```text
do not block migration 004
```

Use the approved fallback:

```text
no DB exclusion constraint in v1 foundation
```

and rely later on:

```text
domain final-state validation
parent locking
SERIALIZABLE
```

Document clearly why the constraint was omitted.

Do NOT invent a complex trigger as replacement.

---

# 11. At least one segment

Do NOT add a constraint trigger requiring:

```text
every occurrence has at least one segment
```

in migration 004.

This invariant is approved for:

```text
domain/service final-state validation
```

during the later backend phase.

Migration/backfill must nevertheless leave all current occurrences with at
least one segment.

---

# 12. Segment bounds

Do NOT implement complex DB triggers for:

```text
occurrence.start_time <= segment.start_time

segment.end_time <= occurrence.end_time
```

in this phase.

These bounds are approved as:

```text
domain/service final-state validation
```

for v1.

The backfill itself must satisfy the invariant exactly.

---

# 13. Backfill existing occurrences

Every occurrence existing after migrations 001–003 must receive:

```text
exactly one initial segment
```

with:

```text
segment.occurrence_id = occurrence.id

segment.start_time = occurrence.start_time

segment.end_time = occurrence.end_time

segment.status = occurrence.status
```

Use a new UUID for each segment.

Do NOT attempt to infer:

```text
historical pauses
historical splits
effective time
interruptions
segment history
```

The old database does not contain evidence for those facts.

---

# 14. UUID generation

Use a PostgreSQL-16-compatible UUID generation strategy that is verified in
the ephemeral test environment.

Do not derive segment IDs from:

```text
occurrence ID
PlanItem
date
time
ordinal
```

Segment IDs must be independent UUID identities.

If UUID generation requires an extension, verify and document the dependency
before committing to it.

Prefer existing project/database capabilities when possible.

---

# 15. Backfill verification

After backfill verify:

```text
number of occurrences
==
number of occurrence_segments
```

for the migrated legacy dataset.

Also verify:

```text
zero occurrence_segments without parent

zero legacy occurrences without segment

segment start/end/status exactly match parent legacy values
```

Immediately after migration 004, every legacy occurrence should still behave
as a single-segment occurrence.

---

# 16. Rename `status_reason` → `conflict_reason`

The approved strategy is:

```text
direct coordinated rename
```

Migration 004 should evolve:

```text
occurrences.status_reason
```

to:

```text
occurrences.conflict_reason
```

Do not keep two long-lived reason columns.

---

# 17. Conflict reason constraints

Replace the old status-context constraints that assume:

```text
reason only exists for cancelled/not_finished
```

because that assumption is no longer valid.

`conflict_reason` must initially allow:

```text
priority_override
user_forced_override
```

or:

```text
NULL
```

according to the approved model.

---

# 18. `source_occurrence_id`

Preserve:

```text
source_occurrence_id
```

as the source of the most recent stored conflict.

Keep:

```text
source_occurrence_id <> id
```

protection.

Keep the existing FK deletion behavior conservatively as:

```text
ON DELETE NO ACTION
```

in v1.

Do NOT change it to:

```text
SET NULL
CASCADE
```

during this task.

Application-level movement/deletion behavior is out of scope for this phase.

---

# 19. Add `origin_reason`

Add nullable:

```text
origin_reason
```

Initial allowed non-null value:

```text
conflict_insertion
```

Legacy/backfilled rows:

```text
origin_reason = NULL
```

Do not invent historical origin metadata.

---

# 20. Add `last_conflict_action`

Add nullable:

```text
last_conflict_action
```

Initial allowed values:

```text
conflict_insertion
conflict_move
```

Legacy/backfilled rows:

```text
last_conflict_action = NULL
```

---

# 21. Do not add speculative metadata

Do NOT add:

```text
conflictSources[]
occurrence_conflict_sources
event log
movement history
segment templates
pause/resume columns
analytics columns
advice columns
is_segmented boolean
segment ordinal column
```

unless required by an already-approved invariant.

---

# 22. Do not persist segment ordinal

Do NOT create:

```text
segment_number
position
ordinal
```

just to display:

```text
Seg 1
Seg 2
Seg 3
```

UI ordinal is derived later from deterministic chronological ordering.

---

# 23. Time precision

Preserve PostgreSQL:

```text
TIME
```

for start/end.

Do not introduce seconds-oriented behavior.

Canonical application precision remains:

```text
HH:MM
```

Do not normalize/truncate legacy data silently in migration 004 unless a
verified existing-data defect requires it.

If unexpected subminute legacy data is discovered in an isolated fixture,
report it rather than silently changing policy.

---

# 24. Migration atomicity

Migration 004 should execute atomically where PostgreSQL permits.

If any required migration step fails:

```text
the schema/backfill must not remain partially applied
```

---

# 25. Migration preconditions

Before destructive/renaming steps, migration/tests should verify assumptions
that matter for correctness.

Examples:

```text
existing occurrence statuses are valid

existing start_time < end_time

existing status reason/context data conforms to the pre-004 model
```

Do not overengineer runtime migration logic if the previous constraints
already prove an invariant.

---

# 26. Migration path tests

Test at minimum:

```text
empty DB:
001 → 002 → 003 → 004

representative populated DB:
001 → 002 → 003
insert legacy fixtures
apply 004
verify exact backfill

legacy priority_override occurrence
→ conflict metadata preserved

all six legacy statuses
→ equivalent segment status

source_occurrence_id null/non-null cases

source_generation_slot_id null/non-null cases
```

---

# 27. Constraint tests

Verify at minimum:

```text
segment start == end rejected

segment start > end rejected

invalid segment status rejected

orphan segment rejected

deleting occurrence cascades its segments

valid adjacent sibling segments accepted
```

If exclusion constraint is enabled also verify:

```text
overlapping sibling segments rejected

overlapping segments from different occurrences allowed
```

---

# 28. Existing migrations remain immutable

Do NOT modify:

```text
001_initial_schema.sql
002_fix_occurrence_status_context.sql
003_multi_slot_scheduling.sql
```

If a problem in an old migration is discovered:

```text
document it
```

and solve forward in:

```text
004
```

when appropriate.

---

# 29. No production/backend implementation

Do NOT modify production backend behavior in this task.

Specifically do NOT yet adapt:

```text
planner_state_service.py
plan_item_creation_service.py
plan_item_materializer.py
occurrence_mutation_service.py
week_mutation_service.py
future_schedule_service.py
scheduling_policy.py
app.py
repositories used by runtime
```

unless a test-only import/helper change is strictly required to verify the
migration and does not activate new behavior.

Prefer dedicated migration/integration test infrastructure.

---

# 30. No frontend implementation

Do NOT modify application frontend behavior.

Do not implement:

```text
segments[]
rendering
expand/collapse
selectedSegmentId
segment status controls
duration sum
conflict UX
```

in this phase.

---

# 31. No persistent reconciliation implementation

Do NOT implement:

```text
TODAY → PREVIOUS_EDITABLE_DAY reconciliation

PREVIOUS_EDITABLE_DAY → FROZEN reconciliation
```

yet.

That belongs to a later backend phase.

---

# 32. Do not apply migration 004 to `vcs_dev`

Even if all tests pass:

```text
DO NOT run migration 004 against the real vcs_dev database
```

during this task.

The approved rollout requires backend read compatibility before real
application.

---

# 33. Testing environment

Use isolated PostgreSQL 16.

The test environment may be:

```text
temporary database
temporary cluster
existing opt-in PostgreSQL integration harness
```

provided that:

```text
vcs_dev is never mutated
```

Reuse existing project testing conventions where practical.

---

# 34. Tests may be added

Add focused migration/PostgreSQL tests as needed.

Do not rewrite unrelated existing tests to pretend the runtime already
supports OccurrenceSegment.

Tests in this phase should prove:

```text
schema
migration
backfill
constraints
rollback/integrity
```

not future application behavior.

---

# 35. `btree_gist` result must be explicit

At completion clearly state one of:

```text
A. exclusion constraint implemented and verified
```

or:

```text
B. exclusion constraint intentionally omitted;
   approved fallback selected
```

Do not leave the decision ambiguous in migration 004.

---

# 36. Documentation update

If implementation discovers a factual technical constraint that changes the
approved DB approach:

```text
do not silently rewrite architecture
```

Report:

```text
finding
impact
alternatives
recommendation
```

before making a contradictory architectural choice.

Minor implementation details that do not alter approved semantics may be
documented directly in tests/comments as appropriate.

---

# 37. Git rules

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

# 38. Completion report

At completion provide:

### Files changed

List every file created/modified.

### Migration summary

Explain:

```text
what 004 creates
what 004 renames
what 004 backfills
what constraints it adds
```

### `btree_gist`

Report:

```text
availability
prototype result
final selected strategy
```

### Tests

Report exact commands and results.

### Safety

Confirm:

```text
vcs_dev was not modified
001/002/003 were not modified
no backend runtime behavior was activated
no frontend behavior was changed
```

### Git

Show:

```text
git diff --stat
git status --short --untracked-files=all
```

No commit.

No push.

---

# 39. Definition of done

This task is complete only when:

```text
004_occurrence_segments.sql exists

001→004 succeeds on isolated PostgreSQL 16

legacy occurrence backfill is verified

all legacy occurrences receive exactly one equivalent segment

local segment constraints are verified

ON DELETE CASCADE is verified

conflict_reason migration is verified

origin_reason / last_conflict_action schema is verified

source_occurrence_id NO ACTION is preserved

sibling no-overlap strategy has an explicit verified outcome

no real vcs_dev mutation occurred

no application runtime implementation occurred
```

---

# Final principle

This phase creates only the database foundation.

The desired result is:

```text
old database model
+
safe segment storage capability
+
exact legacy backfill
```

without yet changing how the running application behaves.

Do not expand scope merely because the next implementation step appears
obvious.
