# CURRENT TASK

## MVP 05.2 — Persistent PlanItem read

### Objetivo

Introducir la primera lectura real del dominio desde PostgreSQL mediante
el backend Flask.

### Alcance

- Crear una capa repository mínima para PlanItems.
- Leer PlanItems desde PostgreSQL.
- Exponer `GET /api/plan-items`.
- Serializar correctamente UUID y timestamps.
- Mantener disponibles los health checks existentes.
- Agregar pruebas del repository y del endpoint cuando sea posible.

### Fuera de alcance

- Crear, editar o eliminar PlanItems.
- Persistir generationConfig.
- Persistir occurrences.
- Conectar todavía el frontend con la API.
- Sustituir planner-store.js.
- Autenticación.
- Multiusuario.
- Supabase.
- Deployment.
- Cambios de esquema salvo defecto real detectado.

### Restricciones

- SQL parametrizado cuando existan parámetros.
- No hardcodear credenciales.
- app.py coordina HTTP.
- El acceso SQL debe vivir fuera de las vistas/rutas.
- No introducir ORM ni SQLAlchemy.
- Mantener arquitectura mínima.