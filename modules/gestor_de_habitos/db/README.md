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
└── 004_occurrence_segments.sql
```

La migración 004 requiere un despliegue coordinado con un backend compatible con
`conflict_reason` y `occurrence_segments`. No debe aplicarse a `vcs_dev` antes de
esa fase de compatibilidad.
