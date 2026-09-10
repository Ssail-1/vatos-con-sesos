# CURRENT TASK

## MVP 05.3 — Persistent planner state read

### Objetivo

Reconstruir desde PostgreSQL el estado persistente completo que necesita
el Gestor de hábitos.

### Alcance

- Leer PlanItems.
- Leer generation_configs.
- Leer generation_weekdays.
- Leer generation_date_entries.
- Leer generation_excluded_dates.
- Leer occurrences.
- Reconstruir la forma de dominio que actualmente consume el frontend.
- Exponer GET /api/planner-state.
- Mantener los endpoints existentes.
- Detectar datos relacionales incompletos sin inventarlos.

### Fuera de alcance

- Escrituras POST/PATCH/DELETE.
- Integración frontend.
- Sustituir planner-store.js.
- Materialización desde API.
- Autenticación.
- Multiusuario.
- Supabase.
- Deployment.

### Restricciones

- PostgreSQL es la fuente persistente.
- El contrato debe respetar el modelo actual del frontend.
- No duplicar fuentes de verdad.
- No modificar migraciones salvo defecto real.
- No introducir ORM.