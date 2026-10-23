# Vatos con Sesos (VCS)

Vatos con Sesos es un proyecto personal de organización y aprendizaje de desarrollo
web. Su módulo principal, el **Gestor de hábitos**, permite planificar actividades,
distribuirlas en el calendario y registrar su cumplimiento.

El proyecto busca representar tanto las rutinas como los cambios de horario que
ocurren durante el día, sin confundir una actividad con cada una de sus apariciones.
También incluye **Dev Notes**, una colección de apuntes y ejercicios de desarrollo web.

**Estado: en desarrollo, orientado al uso local.** El gestor tiene persistencia
en PostgreSQL. El backend aún no está preparado para desplegarse públicamente:
requiere autenticación, autorización por usuario y configuración de producción.

## Qué permite hacer

- Crear actividades y hábitos con programación semanal, por intervalos de días
  o en fechas concretas, con varios horarios según la modalidad.
- Consultar el plan diario y mensual y navegar entre fechas, en escritorio
  o pantallas compactas.
- Registrar el cumplimiento mediante seis estados, desde pendiente hasta
  completada, no realizada, no terminada o cancelada, pasando por en progreso.
- Dividir una aparición en segmentos con horarios y estados propios.
- Editar horarios de una aparición, aplicar ajustes a una semana o cambiar
  la planificación futura.
- Detectar conflictos y confirmar las resoluciones admitidas antes de guardar.
- Eliminar una aparición o detener parte de la planificación posterior a una
  fecha, con reglas para proteger el historial y las referencias entre registros.
- Recuperar los datos guardados al abrir el gestor y reconciliar los estados
  de días anteriores.

Dev Notes ofrece contenido estático de consulta de HTML, CSS y JavaScript;
no es un editor de notas con almacenamiento de usuario.

## Objetivo del proyecto

Construir una herramienta útil mientras pongo en práctica el modelado de datos,
la separación de responsabilidades, las APIs, las pruebas y el mantenimiento de
una aplicación. El desarrollo avanza mediante entregas pequeñas y documentadas,
con énfasis en comprender las decisiones y conservar el comportamiento existente.

## Arquitectura y tecnologías

```text
Frontend HTML + CSS + JavaScript
               ↕ HTTP / JSON
Backend Flask: servicios de dominio y repositorios SQL
               ↕
           PostgreSQL
```

El frontend separa vistas, estado, planificación y comunicación con la API.
El backend valida las operaciones y coordina su persistencia en transacciones.
El modelo distingue actividades, reglas de planificación, apariciones y segmentos.

| Área | Tecnologías utilizadas |
| --- | --- |
| Frontend | HTML, CSS y JavaScript nativo con módulos ES |
| Backend | Python, Flask, Psycopg 3 y `python-dotenv` |
| Base de datos | PostgreSQL 16 y migraciones SQL |
| Pruebas | `unittest`, `node:test` y `node:assert` |
| Herramientas | Git; DBeaver Community como administrador de BD opcional |

El frontend no necesita compilación. Las dependencias Python están fijadas en
[`requirements.txt`](/modules/gestor_de_habitos/backend/requirements.txt).

## Documentación

| Para conocer… | Documento |
| --- | --- |
| Conceptos, estados, ventanas temporales, edición y conflictos | [Guía de funcionamiento](/documentacion-oficial/funcionamiento.md) |
| Requisitos, instalación, ejecución local y pruebas | [Instalación local](/documentacion-oficial/instalacion-local.md) |
| Tablas, relaciones, restricciones y migraciones | [Modelo PostgreSQL](/modules/gestor_de_habitos/db/README.md) |
| Decisiones técnicas del proyecto | [Arquitectura](/docs/architecture/) |

## Organización del repositorio

```text
index.html, css/, js/        Portada y navegación general
modules/dev_notes/          Apuntes y ejercicios de desarrollo web
modules/gestor_de_habitos/
  index.html, css/          Interfaz del gestor
  js/                      API, dominio, estado, planificación y vistas
  backend/                 Flask, servicios, repositorios y pruebas Python
  db/                      Migraciones, pruebas de migración y modelo de datos
  docs/                    Contratos de operaciones de la API
  tests/                   Pruebas JavaScript
docs/                      Guías, arquitectura, entregas e ideas futuras
```

## Trabajo pendiente

Quedan tareas de estabilización local, autenticación, autorización y seguridad
antes de un despliegue público. Las propuestas de evolución incluyen registro
rápido, reutilización de actividades existentes, autocompletado e historial dinámico.
Son **mejoras planeadas**, no capacidades disponibles.

Consulta la [propuesta V1.1](/docs/proximas-features/gestor_de_habitos/V%201.0.0.0/V1.1-PRODUCT-IMPROVEMENT.md).
La documentación histórica conserva decisiones de etapas anteriores; las guías
actuales señalan las diferencias relevantes con la implementación.

## Autor

Proyecto personal de **Ssail** ([@Ssail-1](https://github.com/Ssail-1)),
desarrollado durante mi formación en Ingeniería de Software.

Este repositorio documenta mi proceso de aprendizaje,
las decisiones técnicas tomadas y los problemas que he resuelto.
