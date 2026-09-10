# CURRENT TASK

## MVP 05.1 — Backend PostgreSQL connection

### Objetivo

Introducir el backend mínimo del Gestor de hábitos y establecer
una conexión local entre Flask y PostgreSQL.

### Alcance

- Crear entorno Python aislado.
- Crear backend mínimo con Flask.
- Configurar credenciales mediante variables de entorno.
- Conectar con `vcs_dev` usando `vcs_app`.
- Crear un health check de aplicación y base de datos.
- Mantener intacto el comportamiento actual del frontend.

### Fuera de alcance

- CRUD completo.
- Repositories completos.
- Sustituir `planner-store.js`.
- Autenticación.
- Multiusuario.
- Supabase.
- Deployment.
- Cambios al esquema SQL salvo que encontremos un defecto real.

### Base de datos

La estructura inicial reproducible está definida en:

`modules/gestor_de_habitos/db/migrations/001_initial_schema.sql`