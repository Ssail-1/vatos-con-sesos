# CURRENT TASK

## MVP 05.5 — Atomic persistent PlanItem creation

### Objetivo

Implementar la primera escritura persistente del Gestor de hábitos.

Crear un PlanItem debe persistir de forma atómica:

- identidad del PlanItem;
- generationConfig;
- detalles específicos de generación;
- occurrences inicialmente materializadas.

Si cualquier parte falla, la operación completa debe revertirse.

### Alcance

- Implementar POST /api/plan-items.
- Validar el payload según el contrato canónico actual.
- Persistir plan_items.
- Persistir generation_configs.
- Persistir generation_weekdays para weekly.
- Persistir generation_date_entries para manual_dates.
- Persistir exclusions/stoppedFromDate cuando correspondan.
- Materializar occurrences usando las reglas actuales del dominio.
- Ejecutar toda la creación dentro de una sola transacción PostgreSQL.
- Devolver el PlanItem creado y/o el estado necesario para el cliente.
- Mantener todos los endpoints GET existentes.

### Modos válidos

- weekly
- interval_days
- manual_dates

La opción visual “Una fecha” del frontend sigue existiendo, pero debe llegar
al backend como manual_dates con una sola entry.

### Invariante principal

Un PlanItem recién creado nunca puede quedar parcialmente persistido.

Debe ocurrir:

COMMIT de toda la estructura

o

ROLLBACK completo.

### Fuera de alcance

- PATCH / edición.
- DELETE.
- Persistencia de cambios de status.
- Apply week/future persistente.
- Integración frontend con POST.
- Autenticación.
- Multiusuario.
- Supabase.
- Deployment.

### Restricciones

- No introducir ORM.
- Usar psycopg y SQL parametrizado.
- Respetar reglas de dominio existentes.
- No duplicar lógica si ya existe una implementación reusable en JS;
  si no puede reutilizarse directamente por ser otro runtime, portar la
  semántica explícitamente y probar equivalencia.
- No modificar migraciones salvo defecto real detectado.