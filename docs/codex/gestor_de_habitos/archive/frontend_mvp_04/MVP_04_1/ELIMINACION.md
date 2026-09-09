
# MVP 04.1.2 — Gestión de eliminación

## Propósito

Habilitar las operaciones destructivas controladas del Gestor de hábitos sin
permitir reescritura del historial frozen ni eliminación completa de PlanItems.

Esta fase introduce dos acciones:

1. Eliminar solo este día.
2. Detener de aquí en adelante.

No existe eliminación completa de PlanItem.

---

# 1. Principio de integridad histórica

Las operaciones de eliminación deben respetar la política temporal vigente.

Con `HISTORY_EDIT_WINDOW_DAYS = 1`:

- currentDate es editable;
- currentDate - 1 es editable;
- fechas anteriores están frozen;
- fechas futuras son planificación editable.

Una fecha frozen nunca puede ser modificada ni eliminada.

---

# 2. Eliminar solo este día

Esta operación trabaja sobre una Occurrence concreta e identificable.

Semántica:

> Esta aparición concreta no debió haber estado planificada.

No equivale a `cancelled`.

La Occurrence se elimina físicamente.

El PlanItem permanece.

Las demás Occurrences permanecen.

---

## 2.1 Estados permitidos

### Historial frozen

No se permite eliminar ningún estado.

### currentDate o pasado dentro de ventana editable

Se permite únicamente:

- `pending`.

No se permite:

- `cancelled`;
- `in_progress`;
- `completed`;
- `not_completed`;
- `not_finished`.

### Futuro

Se permite:

- `pending`;
- `cancelled`.

Los demás estados no deben existir manualmente en futuro según la política
temporal vigente.

---

# 3. excludedDates

Eliminar una Occurrence recurrente no debe permitir que el materializador la
regenere posteriormente.

La configuración de generación tendrá una colección conceptual de excepciones:

`excludedDates`

Ejemplo:

```js
excludedDates: [
    "2026-09-03"
]
```

El nombre exacto puede ajustarse si existe una representación más coherente,
pero debe existir una única fuente de verdad.

Antes de materializar una fecha:

1. comprobar `stoppedFromDate`;
2. comprobar `excludedDates`;
3. aplicar las reglas normales del modo de generación.

Una fecha excluida no genera Occurrence.

---

# 4. Restaurar una fecha eliminada

Mientras la fecha continúe siendo editable o futura, el usuario puede volver
a agregar el PlanItem mediante la operación existente:

`Agregar solo este día`.

Si selectedDate aparece en `excludedDates`:

1. validar completamente la nueva Occurrence;
2. validar conflictos y prioridades;
3. si todo es válido:

   * retirar selectedDate de `excludedDates`;
   * crear la Occurrence;
4. aplicar ambas operaciones atómicamente.

Si la creación falla:

* no crear Occurrence;
* no retirar la fecha de `excludedDates`.

---

# 5. Limpieza de excludedDates

Una exclusión deja de ser necesaria cuando su fecha queda definitivamente
frozen.

No implementar timers mensuales, cron ni infraestructura adicional.

Integrar una limpieza idempotente con la reconciliación temporal existente.

Una fecha puede retirarse de `excludedDates` únicamente cuando:

* está frozen;
* el dominio garantiza que el materializador nunca genera Occurrences nuevas
  en fechas frozen.

La limpieza puede ejecutarse al iniciar/reconciliar el planner.

No requiere que la aplicación estuviera abierta cuando la fecha cruzó el
cutoff.

---

# 6. Materialización del pasado frozen

El materializador no debe crear Occurrences nuevas en fechas frozen.

El historial frozen existente es autoritativo.

Esto permite eliminar de forma segura las exclusiones antiguas una vez que
cruzan la frontera temporal.

No modificar Occurrences históricas existentes durante esta comprobación.

---

# 7. Ambigüedad

`Eliminar solo este día` opera mediante `occurrence.id`.

Si la matriz no puede identificar inequívocamente qué Occurrence seleccionó
el usuario:

* no adivinar;
* bloquear la operación;
* informar la ambigüedad.

No imponer `UNIQUE(planItemId, date)`.

---

# 8. Detener de aquí en adelante

Semántica:

> Desde selectedDate este PlanItem deja de formar parte de la planificación.

No elimina el PlanItem.

No borra su historial.

No equivale a `cancelled`.

La operación puede ejecutarse cuando selectedDate pertenece a:

* currentDate;
* ventana editable;
* futuro.

No puede ejecutarse desde una fecha frozen.

No requiere que exista una Occurrence exactamente en selectedDate.

---

# 9. Tratamiento de Occurrences al detener

Todas las Occurrences anteriores a selectedDate permanecen intactas.

Desde selectedDate inclusive:

## pending

Eliminar.

## cancelled

Si:

`date > currentDate`

→ eliminar.

Si:

`date <= currentDate`

→ preservar.

Una cancelación ocurrida hoy o en el pasado representa una decisión
registrada.

Una cancelación futura deja de ser relevante cuando se detiene
conscientemente toda la planificación futura.

## in_progress

Preservar.

## completed

Preservar.

## not_completed

Preservar.

## not_finished

Preservar.

---

# 10. stoppedFromDate

La detención debe funcionar independientemente del modo de generationConfig:

* weekly;
* interval_days;
* manual_dates;
* single_date.

Utilizar una frontera conceptual común:

```js
stoppedFromDate: "YYYY-MM-DD"
```

El nombre exacto puede ajustarse si existe una representación mejor.

Regla universal:

`candidateDate >= stoppedFromDate`

→ no generar Occurrence.

No destruir la configuración anterior.

La configuración histórica continúa describiendo cómo estaba planificado el
PlanItem antes de ser detenido.

---

# 11. stoppedFromDate no reactiva

La operación `Detener de aquí en adelante` nunca debe mover
`stoppedFromDate` hacia el futuro.

Si ya existe una frontera:

* una nueva fecha anterior puede adelantar la detención;
* una fecha posterior no puede reactivar implícitamente el intervalo anterior.

Conceptualmente:

`stoppedFromDate = earliest(existingStoppedFromDate, selectedDate)`

Una futura funcionalidad explícita podrá definir cómo reanudar un PlanItem.

No implementar reactivación en MVP 04.1.2.

---

# 12. excludedDates redundantes al detener

Cuando se establece `stoppedFromDate`, cualquier `excludedDate` igual o
posterior a esa frontera deja de ser necesaria porque ninguna fecha desde esa
frontera volverá a materializarse.

La implementación puede normalizar esas exclusiones redundantes dentro de la
misma operación atómica.

---

# 13. Atomicidad

Todas las operaciones destructivas deben validar primero y mutar después.

Si cualquier paso falla:

* no eliminar Occurrences parcialmente;
* no modificar excludedDates parcialmente;
* no modificar stoppedFromDate parcialmente;
* no dejar cambios incompletos.

---

# 14. PlanItem

No implementar:

`Eliminar completamente PlanItem`.

Un PlanItem permanece como identidad histórica aunque deje de tener
planificación futura.

El historial del usuario no debe desaparecer mediante la interfaz normal.

---

# 15. Fuera de alcance

No implementar en esta fase:

* restauración completa/reanudación de un PlanItem detenido;
* eliminación completa de PlanItem;
* PostgreSQL;
* Flask;
* persistencia;
* cron;
* jobs de servidor;
* estadísticas.
