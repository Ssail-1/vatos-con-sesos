# Mapa de Construcción

## Cómo numeraremos las versiones

No utilizaremos números como `03.1.1` para cada commit.

Separaremos tres conceptos.

## Entrega funcional

```text
MVP 03
```

Es una meta completa y visible para el usuario.

## Versión de Git

```text
v0.3.0
```

Corresponde al MVP 03 terminado.

## Corrección posterior

```text
v0.3.1
```

Solo se utiliza si encontramos un error después de cerrar el MVP 03.

Por ejemplo:

```text
MVP 03 / v0.3.0
→ edición, tipos y validación temporal

v0.3.1
→ corregir un fallo donde dos horarios contiguos se rechazaban

MVP 04 / v0.4.0
→ constructor de semana ideal
```

Los commits describen pasos de trabajo:

```text
docs: define alcance del MVP 03
feat: agrega edición de actividades
fix: evita solapamientos de horarios
```

La versión representa una entrega aprobada.

---

# Mapa general de construcción

## Estado actual

| Entrega           | Resultado                                                      | Estado        |
| ----------------- | -------------------------------------------------------------- | ------------- |
| Base 00           | Git, arquitectura modular y documentación para Codex           | ✅             |
| MVP 01 — `v0.1.0` | Matriz mensual responsive y cinco estados                      | ✅             |
| MVP 02 — `v0.2.0` | Código modular, creación e inserción de actividades en memoria | ✅ para commit |

---

## Próximas entregas

| Entrega               | Meta principal                         | Resultado esperado                                                                                   |
| --------------------- | -------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| **MVP 03 — `v0.3.0`** | Integridad y semántica de Plan del día | Registros tipados, edición, validación de cruces, controles contextuales y regreso a VCS             |
| **MVP 04 — `v0.4.0`** | Construir la semana ideal              | Seleccionar días, definir horarios distintos y repetir una planificación semanal en memoria          |
| **MVP 05 — `v0.5.0`** | Seguimiento de ejecución diaria        | Tiempos planeados y reales, vista expandida, comentarios y estados por fecha                         |
| **MVP 06 — `v0.6.0`** | Backend y PostgreSQL local             | Flask, API, base de datos, migraciones y persistencia después de reiniciar                           |
| **MVP 07 — `v0.7.0`** | Recurrencias e historial real          | Plantillas semanales generan apariciones diarias sin duplicados y conservan historial                |
| **MVP 08 — `v0.8.0`** | Planificación detallada                | Subactividades, excepciones de un día, cancelaciones y edición de una aparición o de la serie futura |
| **MVP 09 — `v0.9.0`** | Integración y despliegue beta          | Shell compartido de VCS, Dev Notes con Markdown, servidor y base remota en un entorno de prueba      |
| **MVP 10 — `v1.0.0`** | Primera versión pública funcional      | Dominio, despliegue estable, autenticación, datos protegidos, documentación y pruebas finales        |

Esto nos da la meta que querías:

```text
MVP 06
→ ya existe PostgreSQL y persistencia

MVP 09
→ ya existe una versión desplegada para pruebas

MVP 10
→ Vatos con Sesos está en línea y funciona como producto
```

---

# Alcance exacto de cada entrega

## MVP 03 — Integridad y semántica

Este es el siguiente.

### Entrará

* Validación contra solapamientos.
* Edición mediante lápiz.
* Botón contextual `+` en la esquina de la celda del nombre.
* Botón de papelera visible, pero todavía sin borrar.
* Enlace con casa hacia Vatos con Sesos.
* Tipo de registro:

  * actividad;
  * hábito programado.
* Si es actividad:

  * ancla;
  * periódica;
  * imprevista.
* Reutilización del diálogo para crear y editar.
* Preservación de estados cuando se edita.
* Actualización del contrato de datos en memoria.

### No entrará

* Eliminación real.
* Recurrencias.
* Persistencia.
* Logros diarios.
* Notificaciones.
* Reacomodo automático.

### Se considera terminado cuando

Puedes crear y editar registros tipados sin permitir horarios superpuestos, utilizar los controles contextuales y volver a la aplicación principal.

---

## MVP 04 — Semana ideal

Aquí aparecerá la planificación semanal real.

Permitirá definir algo como:

```text
Gym

Lunes
05:30–07:15
Pecho

Martes
05:30–07:15
Espalda

Miércoles
Descanso
```

Todavía en memoria.

El objetivo será validar:

* selector de días;
* horarios diferentes por día;
* activación y desactivación de días;
* generación visual de la semana;
* relación entre plantilla y día concreto.

No habrá PostgreSQL todavía porque primero debemos confirmar que la experiencia de crear una semana realmente funciona.

---

## MVP 05 — Ejecución diaria

Aquí retomaremos tu diseño de seguimiento temporal:

```text
Planeado
├── inicio
├── final
└── duración

Real
├── inicio
├── final
└── duración
```

Incluirá:

* expansión y contracción del seguimiento;
* tiempos reales;
* estado `IN_PROGRESS` al comenzar;
* estado `COMPLETED` al finalizar;
* comentario por actividad;
* cambios únicamente para la fecha seleccionada.

El recorrimiento automático seguirá fuera. Primero registramos la realidad sin reorganizarla.

---

## MVP 06 — Flask y PostgreSQL

Este es el punto donde deja de ser un prototipo temporal.

```text
Frontend
    ↓ HTTP/JSON
Flask
    ↓
PostgreSQL
```

Implementaremos:

* esquema;
* migraciones;
* API;
* validaciones backend;
* persistencia;
* visualización gráfica mediante pgAdmin o una herramienta equivalente;
* sustitución del store en memoria por un store conectado a la API.

Las vistas no deberían necesitar una reconstrucción completa porque ya estamos separando:

```text
vista
≠
store
```

---

## MVP 07 — Recurrencias e historial

Con la base de datos funcionando, añadiremos:

```text
Plantilla semanal
        ↓
Apariciones diarias
```

Reglas:

* no duplicar apariciones;
* generar únicamente los rangos necesarios;
* conservar el pasado;
* desactivar una plantilla sin borrar historial;
* modificar un día sin modificar los demás;
* diferenciar plantilla e instancia diaria.

---

## MVP 08 — Planificación detallada

Aquí entra:

* subactividades;
* comentarios más completos;
* cancelar una aparición;
* borrar o desactivar con reglas;
* excepciones de horario;
* editar solo este día;
* editar este día y los siguientes;
* posible preparación para turnos rotativos.

Esta entrega completará la parte más delicada del dominio antes de publicar.

---

## MVP 09 — Beta en Internet

Primera versión desplegada para probar.

Incluirá:

* servidor de aplicación;
* PostgreSQL remoto;
* variables de entorno;
* URL de pruebas;
* navegación compartida de Vatos con Sesos;
* integración de Plan del día;
* integración de Dev Notes;
* lectura y presentación de archivos Markdown;
* pruebas responsive reales.

No será todavía la versión definitiva.

---

## MVP 10 — Vatos con Sesos 1.0

La versión pública tendrá:

```text
Zona pública
├── Inicio
├── Dev Notes
└── Información del proyecto

Zona privada
└── Gestor de hábitos
    └── Plan del día
```

Incluirá:

* autenticación;
* separación de datos por usuario;
* dominio;
* despliegue estable;
* seguridad mínima;
* manejo de errores;
* respaldo y recuperación;
* documentación;
* pruebas finales.

Aquí sí podremos decir:

> Vatos con Sesos está en línea y el gestor puede utilizarse de forma real.

---

# Después de `v1.0.0`

Estas funciones quedan dentro de la evolución posterior, no del primer lanzamiento:

```text
v1.1 — Logros diarios
v1.2 — Hábitos cuantitativos
v1.3 — Rachas y estadísticas
v1.4 — Reacomodo inteligente del día
v1.5 — Notificaciones y calendario
v2.0 — Recomendaciones y asistencia inteligente
```

Así `Logros diarios` tendrá su propio diseño y no contaminaremos la tabla temporal con cosas que no tienen hora.

---

# Regla para cambios inesperados

Cuando aparezca una nueva idea, la clasificaremos antes de programarla:

```text
¿Es necesaria para terminar la entrega actual?
├── Sí → entra en el MVP actual
└── No
    ├── ¿Es una corrección? → v0.X.1
    ├── ¿Es la siguiente meta? → MVP siguiente
    └── ¿Es futura? → backlog posterior a v1.0
```

El solapamiento de horarios sí entra en MVP 03 porque afecta la integridad de los registros.

Las estadísticas no entran porque pertenecen a una etapa posterior.

---

# Estado inmediato de Git

La implementación que acabas de probar corresponde a:

```text
MVP 02 / v0.2.0
```

Primero congélala localmente:

```bash
git add modules/gestor_de_habitos
git commit -m "feat: implementa Frontend MVP 02 del Plan del día"
```

También puedes marcarla localmente:

```bash
git tag -a v0.2.0 -m "Frontend MVP 02: creación e inserción en memoria"
```

El `push` y el envío del tag pueden esperar a que tengas Internet:

```bash
git push
git push origin v0.2.0
```

A partir de ahí abrimos formalmente:

```text
MVP 03 / v0.3.0
```

El mapa ya no será “a ver qué surge”. Podrán aparecer descubrimientos, pero sabremos en qué entrega colocarlos y qué meta no debemos sacrificar.
