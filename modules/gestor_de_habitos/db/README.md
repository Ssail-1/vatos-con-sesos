# Base de datos — Gestor de hábitos

Persistencia PostgreSQL para el módulo `gestor_de_habitos` de Vatos con Sesos.

## Entorno actual

- PostgreSQL 16
- Base de datos local: `vcs_dev`
- Rol de aplicación local: `vcs_app`
- Administración visual: DBeaver Community

## Migraciones

Las migraciones viven en:

```text
db/migrations/
├── 001_initial_schema.sql
├── 002_fix_occurrence_status_context.sql
├── 003_multi_slot_scheduling.sql
├── 004_occurrence_segments.sql
└── 005_generation_slot_cutoff.sql
```

La migración 005 agrega `generation_slots.last_generation_date DATE NULL`.
`NULL` conserva horarios sin límite; una fecha `D` permite generar hasta `D`
inclusive y nunca después. No elimina slots ni altera su procedencia histórica.
El corte global continúa en `generation_configs.stopped_from_date` (exclusivo).

## Estado local del rollout

El 22 de septiembre de 2026, `vcs_dev` fue migrada y verificada con éxito
hasta schema 005:

- `004_occurrence_segments.sql` aplicada, con backfill e integridad verificados;
- `005_generation_slot_cutoff.sql` aplicada, conservando en `NULL` los cortes
  de todos los horarios preexistentes;
- backup custom-format previo al rollout verificado y conservado en
  `/home/ssail/.local/share/vcs/backups/vcs_dev_pre_005_20260922_135638.dump`.
