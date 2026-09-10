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
└── 002_fix_occurrence_status_context.sql
```
