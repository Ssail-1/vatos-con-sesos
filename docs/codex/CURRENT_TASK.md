# CURRENT TASK

## MVP 05.4 — Explicit-date mode normalization

### Objetivo

Eliminar `single_date` como modo interno del Gestor de hábitos y
representar toda planificación por fechas explícitas mediante
`manual_dates`.

### Alcance

- Localizar todas las referencias a `single_date`.
- Mantener la experiencia actual de creación de una sola fecha si existe.
- Traducir una sola fecha a `manual_dates` con exactamente una entry.
- Mantener varias fechas como `manual_dates`.
- Actualizar materializador, formularios y tests cuando corresponda.
- Preservar comportamiento visual y funcional aprobado.

### Fuera de alcance

- API de escritura.
- Persistencia frontend.
- POST/PATCH/DELETE.
- Cambios PostgreSQL.
- Autenticación.
- Deployment.