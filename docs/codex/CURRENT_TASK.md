# CURRENT TASK

## MVP 05.7.5.13 — Final Verification & Real Schema Rollout

### Objective

Perform the controlled rollout of the real local development database:

```text
vcs_dev
```

from its current pre-OccurrenceSegment schema to the fully approved schema:

```text
001
→ 002
→ 003
→ 004_occurrence_segments
→ 005_generation_slot_cutoff
```

This phase is NOT a feature phase.

The implementation for:

```text
OccurrenceSegment v1
Segment Conflict Engine
Recurring segment-aware mutations
Conflict UX
Planner chronology
Persistent Planning Termination
```

is already complete.

This phase exists to:

```text
backup
→ preflight
→ migrate
→ verify
→ boot
→ smoke test
→ confirm real local usability
```

while preserving the user's real PlanItems and historical data.

---

# 1. Critical principle

The real database is valuable user data.

Treat:

```text
vcs_dev
```

as production-like data for purposes of migration safety.

Do not improvise.

Do not clean data merely to make migration pass.

Do not delete historical PlanItems.

Do not rewrite user records unless an approved migration or normal planner
operation explicitly requires it.

---

# 2. Git first

Before touching PostgreSQL:

```text
git status --short --untracked-files=all
git diff --stat
git diff --check
git log -1 --oneline
```

Expected:

- 05.7.5.12 implementation is committed;
- code working tree is clean;
- `CURRENT_TASK.md` may be modified by the user for this phase.

If application code has unexplained uncommitted changes:

```text
STOP.
```

Do not migrate real data until the code state is understood.

Do NOT:

```text
commit
push
merge
rebase
switch branch
create branch
```

The user controls Git.

---

# 3. Required reading

Read completely:

```text
AGENTS.md

docs/codex/CURRENT_TASK.md

modules/gestor_de_habitos/db/README.md

modules/gestor_de_habitos/db/migrations/004_occurrence_segments.sql

modules/gestor_de_habitos/db/migrations/005_generation_slot_cutoff.sql

modules/gestor_de_habitos/docs/planning_termination_api.md

modules/gestor_de_habitos/docs/segment_conflict_api.md
```

Also inspect the application bootstrap and database connection code required to
understand how the real local app connects to `vcs_dev`.

Do not expose secrets in logs/report.

Do not print passwords.

Do not ask the user for the database password.

Do not ask the user to paste `.env`.

Use the already configured local connection mechanism.

---

# 4. Establish the actual database state

Do NOT assume the remembered schema state is correct.

Before migration, query the real database read-only and record:

```text
current_database()

PostgreSQL version

current_user

database owner if relevant

whether occurrence_segments exists

whether occurrences.conflict_reason exists

whether occurrences.status_reason exists

whether generation_slots.last_generation_date exists

whether btree_gist extension exists
```

Also inspect the structural preconditions expected by migration 004.

Expected historical state is approximately:

```text
schema 003 present
004 not yet applied
005 not yet applied
```

but this MUST be proven.

---

# STOP GATE A — unexpected schema

If `vcs_dev` appears:

```text
partially migrated

already schema 004

already schema 005

missing required schema-003 objects

or structurally inconsistent with migration preconditions
```

DO NOT apply anything.

Report:

```text
actual state

expected state

difference

safe next step
```

Do not attempt an improvised repair.

---

# 5. Stop application writers

Before backup/migration:

ensure local writer processes using `vcs_dev` are stopped.

This includes, if running:

```text
Flask development server

frontend workflow that may trigger bootstrap/reconcile

browser automation
```

Inspect PostgreSQL activity when practical.

Do not kill unrelated user processes.

The goal is a quiet maintenance window for the database.

---

# 6. Pre-migration data snapshot

Before backup, record read-only baseline counts.

At minimum:

```text
plan_items

generation_configs

generation_slots

generation_slot_weekdays

generation_slot_dates

generation_slot_excluded_dates

generation_excluded_dates

occurrences
```

Also record relevant occurrence status/provenance integrity metrics such as:

```text
occurrences with source_generation_slot_id

occurrences with source_occurrence_id

NULL/non-NULL status/provenance fields where relevant
```

Do not dump sensitive row content into the final report.

Counts and integrity summaries are enough.

---

# 7. Backup location

Create a durable local backup OUTSIDE tracked repository content.

Preferred shape:

```text
~/.local/share/vcs/backups/
```

or another safe non-repository location already appropriate for the environment.

Use a timestamped name, conceptually:

```text
vcs_dev_pre_005_YYYYMMDD_HHMMSS.dump
```

Do not store the backup in `/tmp`.

Do not add it to Git.

Do not expose secrets in its filename.

---

# 8. Full backup

Create a PostgreSQL custom-format backup of `vcs_dev`.

Prefer:

```text
pg_dump
--format=custom
```

using the existing configured authentication mechanism.

Capture:

```text
backup path

file size

SHA-256 hash
```

Do not display credentials.

---

# STOP GATE B — backup creation

If backup creation fails:

```text
STOP.
```

No migration may run.

---

# 9. Backup verification is mandatory

A backup merely existing is NOT enough.

At minimum:

```text
pg_restore --list
```

must succeed.

Then prove restorable data by restoring the backup into a TEMPORARY verification
database.

Use a unique database name such as:

```text
vcs_restore_verify_<timestamp>
```

Do NOT overwrite `vcs_dev`.

Restore using whatever safe ownership/privilege flags are required by the local
environment.

After restore, compare key baseline counts with the real pre-migration snapshot.

At minimum:

```text
plan_items

generation_configs

generation_slots

occurrences
```

must match.

Drop only the temporary restore-verification database after successful proof.

Do not drop `vcs_dev`.

---

# STOP GATE C — backup restore verification

If the backup cannot be restored successfully or counts do not match:

```text
STOP.
```

Do NOT migrate `vcs_dev`.

This gate is absolute.

---

# 10. Preserve backup after verification

Do NOT delete the verified backup after testing it.

It is the recovery artifact for the rollout.

The final report must provide:

```text
backup path

size

SHA-256
```

but never a password or secret.

---

# 11. Migration execution rules

Use PostgreSQL tooling configured to:

```text
stop on the first SQL error
```

Conceptually:

```text
ON_ERROR_STOP
```

Apply migrations EXACTLY from the immutable files.

Do not copy/paste pieces manually.

Do not edit migrations during rollout.

Order:

```text
004_occurrence_segments.sql

VERIFY 004

005_generation_slot_cutoff.sql

VERIFY 005
```

Never run 005 before 004 verification succeeds.

---

# 12. Migration 004 — before execution

Re-read its preconditions against the actual real schema.

Migration 004 is expected to:

```text
create/ensure btree_gist

rename status_reason → conflict_reason

introduce conflict provenance fields

create occurrence_segments

add constraints/indexes/exclusion

backfill exactly one segment for each existing occurrence
```

Verify all assumptions before executing.

---

# 13. Apply migration 004

Apply:

```text
modules/gestor_de_habitos/db/migrations/004_occurrence_segments.sql
```

exactly once.

Do not manually reproduce statements.

Record success/failure.

---

# STOP GATE D — migration 004 SQL failure

If migration 004 itself fails:

```text
STOP.
```

Because the migration is transaction-protected, verify whether the transaction
rolled back cleanly.

Do NOT attempt 005.

Do NOT modify data manually to force success.

Report the exact failing precondition/error without secrets.

---

# 14. Verify migration 004

Before 005, verify real data integrity.

At minimum confirm:

```text
occurrence_segments table exists

btree_gist is available as required

conflict_reason exists

old status_reason is gone from active schema

origin_reason exists

last_conflict_action exists
```

---

# 15. 004 count invariants

Immediately after 004:

The following existing logical entities should have unchanged counts:

```text
plan_items

generation_configs

generation_slots

occurrences
```

Migration 004 must NOT delete the user's existing PlanItems or occurrences.

Record before/after counts.

---

# 16. 004 segment backfill invariant

Immediately after migration 004:

Every existing occurrence must have exactly one backfilled segment.

Verify:

```text
occurrence count
==
occurrence_segments count
```

for this immediate migration state.

Also verify:

```text
COUNT(DISTINCT occurrence_id)
==
occurrence count
```

and:

```text
no occurrence without a segment
```

---

# 17. 004 backfill equivalence

For every backfilled segment, verify equivalent legacy values:

```text
segment.start_time == occurrence.start_time

segment.end_time == occurrence.end_time

segment.status == occurrence.status
```

No mismatch is allowed immediately after migration.

---

# 18. 004 structural integrity

Verify:

```text
no orphan occurrence_segments

no segment outside parent bounds

no non-positive segment duration

no sibling overlaps

no invalid conflict_reason/source_occurrence pairing

no source_occurrence_id self-reference
```

Use the actual constraints plus explicit verification queries where useful.

---

# STOP GATE E — post-004 verification failure

If ANY required 004 invariant fails:

```text
STOP.
```

Do NOT apply 005.

Do NOT launch the application.

Preserve all evidence.

Because 004 may already be committed, do not improvise a downgrade.

Prepare the verified backup restore procedure and report the failure.

Do not restore `vcs_dev` destructively without explicit user approval unless the
database itself remained transactionally unchanged.

---

# 19. Migration 005 — preflight

Only after 004 is fully verified.

Confirm before 005:

```text
generation_slots.last_generation_date
does not already exist
```

and that all 005 assumptions hold.

---

# 20. Apply migration 005

Apply:

```text
modules/gestor_de_habitos/db/migrations/005_generation_slot_cutoff.sql
```

exactly once.

Semantics:

```text
NULL
→ unlimited recurring slot

D
→ may generate through D inclusive
→ may not generate after D
```

---

# STOP GATE F — migration 005 SQL failure

If 005 fails:

```text
STOP.
```

Do not launch the app.

Verify transaction state.

Do not invent a manual patch.

Because 004 may already have succeeded, document current schema precisely.

Prepare recovery options from the verified backup.

---

# 21. Verify migration 005

After success confirm:

```text
generation_slots.last_generation_date exists
```

and every legacy slot has:

```text
last_generation_date IS NULL
```

unless there is explicit preexisting data that proves otherwise.

Expected rollout state:

```text
all existing legacy slots remain unlimited
```

Migration 005 must not stop any user's existing schedule automatically.

---

# 22. 005 count invariants

Migration 005 is additive.

Therefore confirm unchanged counts for:

```text
plan_items

generation_configs

generation_slots

occurrences

occurrence_segments
```

between post-004 and post-005 snapshots.

---

# 23. Final schema verification

After 004 + 005 confirm the real database is compatible with current code.

At minimum verify:

```text
occurrence_segments

conflict_reason

origin_reason

last_conflict_action

generation_slots.last_generation_date
```

and all required foreign keys/constraints used by current services.

---

# 24. Do not run synthetic destructive SQL against user records

No manual:

```text
DELETE

UPDATE

TRUNCATE
```

against real user PlanItems merely to "test" features.

Application smoke tests that mutate data must use controlled synthetic data only.

---

# 25. Start backend against real vcs_dev

Only after all migration verification succeeds.

Use the existing local development configuration.

Expected workflow remains conceptually:

```text
source .venv/bin/activate

cd modules/gestor_de_habitos/backend

flask --app app run --debug
```

Do not expose or print secrets.

---

# 26. Start frontend

Use the existing development workflow, conceptually:

```text
cd modules/gestor_de_habitos

python3 -m http.server 8000
```

Open the app with the configured API base URL.

---

# 27. First real planner load

The first goal is READ/BOOTSTRAP validation.

Verify:

```text
frontend loads

planner-state GET succeeds

bootstrap reconcile succeeds

no "No se pudo cargar el planner"

existing PlanItems appear

historical occurrences remain visible

segment rows hydrate correctly

planner chronology renders correctly
```

Do not immediately perform destructive actions on existing user data.

---

# 28. Reconcile verification

The normal app bootstrap performs:

```text
POST reconcile
→ GET planner-state
→ hydrate
```

Allow the approved reconciliation behavior.

Record:

```text
whether reconcile succeeded

whether occurrence/segment statuses changed

how many rows changed if practical
```

Do not treat approved temporal reconciliation as migration corruption.

But if large/unexpected structural deletion occurs:

```text
STOP.
```

---

# 29. Existing-data visual smoke

Using existing data read-only where possible, verify:

```text
PlanItems render

single-segment occurrences render

multi-segment occurrences render if present

expanded segments globally interleave

selection works

recurring controls appear correctly

deletion/planning action menu opens correctly
```

Do NOT delete or stop any real existing user PlanItem during smoke testing.

---

# 30. Mutation smoke-test policy

We still need confidence that the real schema accepts current writers.

Use CONTROLLED SYNTHETIC TEST DATA only.

Do not use a real historical PlanItem.

Before creating synthetic data:

determine a safe cleanup strategy.

Preferred order:

```text
1. supported application-level cleanup if available

2. backend/service test transaction that rolls back

3. narrowly scoped explicit cleanup of only the synthetic IDs if absolutely
   necessary and proven safe
```

Never run broad cleanup conditions.

If no safe cleanup strategy exists:

do not persist destructive browser smoke data.

Use backend transaction-level verification instead and report that limitation.

---

# 31. Synthetic smoke identity

Any synthetic rollout PlanItem must have an unmistakable unique marker, e.g.:

```text
__VCS_ROLLOUT_SMOKE_<timestamp>__
```

Record every synthetic:

```text
plan_item_id

occurrence_id

generation_slot_id
```

created.

Cleanup must target only those exact identities.

---

# 32. Real-schema create smoke

Against the migrated `vcs_dev` schema, verify with synthetic data:

```text
PlanItem creation

GenerationConfig creation

GenerationSlot creation

Occurrence creation

OccurrenceSegment creation
```

Then GET/hydrate.

No schema errors allowed.

---

# 33. Segment status smoke

Using synthetic data only:

verify:

```text
PATCH segment status

parent aggregate update

GET authoritative state
```

Do not modify user history.

---

# 34. Structural smoke

Using synthetic data only:

verify at least:

```text
translate

or structure/reset path
```

against schema 005.

No legacy `status_reason` failure may occur.

---

# 35. Conflict writer smoke

If safely reproducible with synthetic data:

create a controlled conflict and verify:

```text
409 segment conflict contract

confirmation

authoritative GET
```

Do not involve real user occurrences as blockers.

---

# 36. Four planning/deletion actions smoke

Use synthetic PlanItems only.

Verify the four approved actions when safe:

```text
1. Eliminar solo esta aparición

2. Detener este horario después de este día

3. Detener toda la planificación recurrente después de este día

4. Eliminar todas las apariciones después de este día
```

Do not test these on the user's real PlanItems.

---

# 37. Slot-cutoff smoke

Synthetic scenario:

```text
A 08–11
B 14–17
C 20–22
```

Stop B after D.

Verify:

```text
D kept

A future remains

B future removed

C future remains

manual future remains

last_generation_date written for B

B does not regenerate
```

---

# 38. Recurrence-stop smoke

Synthetic scenario.

Verify:

```text
D kept

all recurring future removed

manual future remains

all relevant slots receive cutoff

future generation cannot recreate them
```

---

# 39. Delete-all-future smoke

Synthetic scenario.

Verify:

```text
D kept

generated future removed

manual future removed

PlanItem remains

future recurrence remains stopped
```

---

# 40. Reload persistence

After synthetic cutoff command:

```text
F5 / fresh GET

reconcile

materialization
```

must not restore stopped future occurrences.

This confirms real `vcs_dev` now honors migration 005.

---

# 41. Apply Week / Apply Future smoke

Using synthetic data only where practical:

verify stopped planning cannot be silently reopened.

Expected:

```text
Apply Week beyond cutoff
→ controlled planning_stopped where applicable

Apply Future on stopped recurrence
→ controlled rejection
```

No cutoff disappearance.

---

# 42. Synthetic data cleanup

After successful smoke verification:

clean ONLY synthetic rollout data.

Verify cleanup by exact IDs/marker.

Then confirm:

```text
no __VCS_ROLLOUT_SMOKE_* PlanItems remain
```

Do not touch any other data.

If synthetic provenance prevents safe cleanup:

STOP cleanup rather than clearing historical references blindly.

Report remaining synthetic IDs so the user can decide.

---

# 43. Post-smoke real-data counts

After synthetic cleanup, compare key real-data counts with the post-migration
baseline.

Account explicitly for:

```text
approved reconcile status changes
```

but user PlanItems/occurrences must not disappear because of smoke testing.

At minimum verify no unexpected loss of:

```text
PlanItems

GenerationConfigs

GenerationSlots

historical Occurrences
```

---

# 44. Browser desktop

Verify real migrated app at approximately:

```text
1440×900
```

At minimum:

```text
planner loads

historical data visible

chronology works

no console-breaking error

action dialogs open

no schema mismatch message
```

---

# 45. Browser mobile

Verify approximately:

```text
390×844
```

At minimum:

```text
planner usable

dialog readable

segment identity visible

no global horizontal overflow
```

No need for a visual redesign.

---

# 46. Final server restart

After successful smoke:

stop Flask/frontend.

Restart them once.

Reload planner.

Verify the migrated DB still works from a clean application process.

This guards against accidental in-memory state masking persistence issues.

---

# 47. Final database integrity

After all testing and synthetic cleanup, run final integrity checks.

At minimum:

```text
no orphan segments

every occurrence has >= 1 segment

segment bounds valid

no sibling overlaps

source_occurrence_id integrity valid

conflict metadata pairing valid

legacy slots retain expected cutoff values

no accidental non-NULL cutoff on untouched user slots
```

Important:

real user slots should remain:

```text
last_generation_date IS NULL
```

unless the user actually performed a stop operation after rollout.

Synthetic test cutoffs must disappear when synthetic data is cleaned up.

---

# 48. No automatic destructive restore

If a post-commit migration verification fails:

do NOT perform an improvised downgrade.

do NOT run reverse SQL manually.

do NOT automatically overwrite `vcs_dev`.

Instead:

```text
stop application writers

preserve evidence

verify backup still exists/hash matches

prepare exact restore command/plan

report to user
```

Restoring the real database from backup is a destructive recovery action and
requires explicit user approval unless the failed migration transaction already
rolled itself back without changing the database.

---

# 49. Rollback plan

The final report must include the concrete recovery plan:

```text
1. stop application writers

2. preserve failed database separately if useful

3. recreate/restore vcs_dev from verified custom-format backup

4. compare baseline counts

5. return application to pre-rollout compatible code/state if necessary
```

Do not execute it unless required and explicitly authorized.

---

# 50. Documentation after successful rollout

After all verification passes, update only the minimum documentation necessary
to reflect factual local state.

For example `db/README.md` may now state:

```text
local vcs_dev schema = 005
004 applied successfully
005 applied successfully
backup verified before rollout
```

Do not include:

```text
passwords

connection secrets

sensitive row contents
```

Do not create unnecessary rollout documentation if the existing DB README is
the correct canonical location.

---

# 51. No new features

OUT OF SCOPE:

```text
auth

owner/guest

security hardening

Supabase

cloud hosting

deployment

Finance module

restart planning

event log

pause/resume

new conflict semantics

new recurrence semantics

UI redesign

new planner capabilities
```

If a genuine bug blocks the migrated application:

fix only the smallest compatibility defect necessary.

Document it clearly.

Do not expand scope.

---

# 52. Tests after any code change

If rollout requires ANY application-code fix:

rerun affected suites.

Before declaring complete, run full frontend:

```text
for test_file in modules/gestor_de_habitos/tests/*.test.mjs
do
  node "$test_file" || exit 1
done
```

and backend:

```text
.venv/bin/python -m unittest discover \
  -s modules/gestor_de_habitos/backend \
  -p 'test_*.py'
```

If no code changed, previous 05.7.5.12 suite results remain useful, but run at
least relevant smoke/integrity checks against real schema 005.

---

# 53. PostgreSQL migration files remain immutable

Never modify:

```text
001_initial_schema.sql
002_fix_occurrence_status_context.sql
003_multi_slot_scheduling.sql
004_occurrence_segments.sql
005_generation_slot_cutoff.sql
```

during rollout.

If a migration defect is discovered:

```text
STOP.
```

Do not rewrite migration history after it has been committed.

Report whether a new additive migration would be required instead.

---

# 54. Success criteria

05.7.5.13 succeeds only if ALL are true:

```text
verified restorable backup exists

actual pre-migration schema was understood

004 applied successfully

004 backfill verified

005 applied successfully

legacy slots remain cutoff NULL

no user PlanItem lost

no user occurrence lost through migration

OccurrenceSegments valid

planner bootstrap succeeds

reconcile succeeds

real planner loads

existing user data renders

current writers are schema-compatible

controlled synthetic writes succeed

planning termination persists

stopped recurrence does not regenerate

synthetic data is cleaned safely

app survives server restart

final integrity checks pass

rollback artifact remains available
```

---

# 55. Final product state

If successful, the local stack should finally be:

```text
Frontend
    ↓
Flask backend
    ↓
vcs_dev
    ↓
schema 005
```

with:

```text
OccurrenceSegment authoritative

segment conflict engine active

recurring mutations segment-aware

planner chronology active

persistent planning termination active
```

---

# 56. Final report

Provide a COMPLETE rollout report.

Include:

## Git/preflight

```text
commit inspected

working tree condition

branch unchanged
```

## Actual pre-migration DB state

Report:

```text
PostgreSQL version

schema objects discovered

whether state matched expected schema 003
```

Do not reveal secrets.

## Baseline

Report pre-migration counts.

## Backup

Report:

```text
backup path

format

size

SHA-256

pg_restore --list result

temporary restore verification result

restored count comparison
```

## Maintenance window

Report which local writer processes were stopped/confirmed inactive.

## Migration 004

Report:

```text
command/result

schema changes verified

count invariants

segment backfill count

backfill equivalence

integrity checks
```

## Migration 005

Report:

```text
command/result

last_generation_date verification

legacy NULL behavior

count invariants
```

## Real schema

State exact final schema compatibility.

## First app boot

Report:

```text
Flask result

frontend result

reconcile

planner-state

hydrate

existing real PlanItems visibility
```

## Existing data

Report:

```text
PlanItem preservation

Occurrence preservation

historical visibility

segment rendering
```

Do not reveal sensitive user content unnecessarily.

## Synthetic smoke

Report:

```text
unique smoke identity

creation

segment status

structural mutation

conflict flow if tested

Command 1

Command 2

Command 3

Command 4

Apply Week/Future cutoff behavior

reload persistence
```

## Synthetic cleanup

State whether all test data was removed safely.

If not, list exact synthetic IDs only.

## Browser

Report desktop/mobile.

## Restart

Report clean Flask/frontend restart and final reload.

## Final integrity

Report:

```text
orphans

segment bounds

overlaps

provenance

conflict metadata

cutoff values

counts
```

## Rollback

Give exact backup-based recovery plan.

Do NOT perform it merely for demonstration.

## Code changes

State whether rollout required any code compatibility fix.

If yes:

```text
files

reason

tests
```

## Documentation

State factual rollout documentation changes.

## Explicit answers

Answer:

```text
Is vcs_dev now schema 005?
```

Required:

```text
YES
```

```text
Were migrations 004 and 005 both verified on the real database?
```

Required:

```text
YES
```

```text
Were the user's existing PlanItems preserved?
```

Required:

```text
YES
```

```text
Is the real planner usable after a clean server restart?
```

Required:

```text
YES
```

```text
Is the verified pre-rollout backup still available?
```

Required:

```text
YES
```

If any answer is NO:

05.7.5.13 is NOT complete.

## Remaining work

State what remains AFTER OccurrenceSegment rollout.

Do not start it.

Likely next macro-phase:

```text
local stabilization / release candidate
→ auth/authorization
→ security hardening
→ production configuration
→ staging/cloud
→ public deployment
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

# 57. STOP CONDITIONS SUMMARY

Immediately stop real rollout if:

```text
unexpected pre-migration schema

dirty unexplained application code

backup fails

backup restore verification fails

004 fails

004 integrity verification fails

005 fails

005 integrity verification fails

unexpected user-data loss

unexpected structural corruption
```

Do not continue merely because the next step might repair it.

---

# Final principle

This phase is not:

```text
"run two SQL files and see what happens"
```

It is:

```text
PROVE we can recover
        ↓
PROVE the starting state
        ↓
apply 004
        ↓
PROVE 004
        ↓
apply 005
        ↓
PROVE 005
        ↓
boot real VCS
        ↓
PROVE current writers
        ↓
PROVE persistence
        ↓
PROVE restart
        ↓
declare rollout complete
```

The user's real data is more important than completing the phase quickly.
