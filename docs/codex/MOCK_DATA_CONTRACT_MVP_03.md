# Contrato de datos simulados — Frontend MVP 03

## Propósito

Este documento define la estructura de datos utilizada por el submódulo:

```text
Gestor de hábitos
└── Plan del día
```

durante el Frontend MVP 03.

La aplicación continúa funcionando exclusivamente con datos almacenados en memoria.

No existe todavía:

* backend;
* API;
* PostgreSQL;
* Supabase;
* persistencia;
* autenticación.

El objetivo del contrato es mantener una estructura consistente que posteriormente pueda trasladarse a una API y una base de datos sin reconstruir la interfaz.

---

# Principio fundamental

Un registro del `Plan del día` representa:

> Algo planeado para ocupar un intervalo temporal concreto dentro de una jornada.

Todos los registros de este submódulo deben tener:

* identidad;
* nombre;
* clasificación;
* posición;
* hora planeada de inicio;
* hora planeada de finalización;
* estados asociados a fechas.

---

# Estructura general

Cada registro tendrá conceptualmente esta forma:

```js
{
    id: "gym-pecho",
    name: "Gym - Pecho",
    recordKind: "activity",
    recordSubtype: "periodic",
    position: 1,
    plannedStartTime: "05:30",
    plannedEndTime: "07:15",
    statesByDate: {
        "2026-08-03": "completed"
    }
}
```

---

# Campos permitidos

En el MVP 03 solamente deben existir los siguientes campos persistentes dentro de cada registro:

```text
id
name
recordKind
recordSubtype
position
plannedStartTime
plannedEndTime
statesByDate
```

No agregar propiedades correspondientes a funciones futuras.

---

# `id`

Tipo conceptual:

```text
string
```

Representa la identidad única del registro.

Reglas:

* obligatorio;
* único durante toda la sesión;
* estable después de editar;
* no debe depender exclusivamente del nombre;
* no cambia cuando cambia la posición;
* no cambia cuando cambia el horario;
* no cambia cuando cambia la clasificación.

Ejemplo:

```js
id: "gym-pecho"
```

Las actividades iniciales pueden mantener identificadores legibles.

Las actividades creadas durante la sesión deben utilizar un identificador generado.

---

# Generación de identificadores

Utilizar preferentemente:

```js
crypto.randomUUID()
```

Cuando no esté disponible debe existir una alternativa local segura para la sesión.

Ejemplo conceptual:

```js
function createFallbackId() {
    return `record-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
```

No utilizar únicamente:

```js
name
```

porque dos registros pueden tener el mismo nombre.

---

# `name`

Tipo:

```text
string
```

Representa el nombre visible del registro.

Reglas:

* obligatorio;
* máximo 80 caracteres;
* eliminar espacios exteriores;
* no aceptar únicamente espacios;
* conservar acentos y caracteres en español.

Ejemplo recibido:

```text
"   Preparación del día siguiente   "
```

Valor almacenado:

```text
"Preparación del día siguiente"
```

---

# `recordKind`

Tipo conceptual:

```text
enum
```

Indica la clasificación principal.

Valores permitidos:

```text
activity
habit
```

---

# `recordKind: activity`

Representa una actividad del día.

Cuando:

```js
recordKind === "activity"
```

`recordSubtype` debe contener exactamente uno de:

```text
anchor
periodic
unexpected
```

---

# `recordKind: habit`

Representa un hábito programado temporalmente.

Cuando:

```js
recordKind === "habit"
```

el único valor permitido actualmente para `recordSubtype` es:

```text
scheduled
```

No agregar todavía otros subtipos de hábito.

---

# `recordSubtype`

Tipo conceptual:

```text
enum
```

Valores permitidos globalmente:

```text
anchor
periodic
unexpected
scheduled
```

Pero no todas las combinaciones son válidas.

---

# Combinaciones válidas

| `recordKind` | `recordSubtype` | Representación       |
| ------------ | --------------- | -------------------- |
| `activity`   | `anchor`        | Actividad ancla      |
| `activity`   | `periodic`      | Actividad periódica  |
| `activity`   | `unexpected`    | Actividad imprevista |
| `habit`      | `scheduled`     | Hábito programado    |

---

# Combinaciones inválidas

No aceptar estructuras como:

```js
{
    recordKind: "activity",
    recordSubtype: "scheduled"
}
```

ni:

```js
{
    recordKind: "habit",
    recordSubtype: "anchor"
}
```

El store debe comprobar esta coherencia.

---

# Por qué se utiliza `recordKind` + `recordSubtype`

No utilizar simultáneamente propiedades como:

```text
activityType
habitType
```

porque producirían estructuras como:

```js
{
    activityType: null,
    habitType: "scheduled"
}
```

o:

```js
{
    activityType: "anchor",
    habitType: null
}
```

El modelo del MVP 03 utilizará una clasificación común:

```text
recordKind
+
recordSubtype
```

Esto mantiene cada registro pequeño y consistente.

---

# `position`

Tipo:

```text
integer
```

Representa el orden secundario del registro.

Reglas:

* comienza en `1`;
* siempre es entero;
* debe ser consecutivo;
* debe renumerarse después de crear o editar;
* no debe contener duplicados después de la renumeración.

Ejemplo:

```text
1
2
3
4
5
```

No conservar resultados como:

```text
1
1.5
2
4
```

---

# Prioridad de orden

El orden visual se determina mediante:

1. `plannedStartTime`;
2. `position`.

La hora siempre tiene prioridad.

Conceptualmente:

```js
records.sort((first, second) => {
    return (
        first.plannedStartTime.localeCompare(second.plannedStartTime) ||
        first.position - second.position
    );
});
```

Después se renumeran las posiciones.

---

# `plannedStartTime`

Tipo:

```text
string
```

Formato:

```text
HH:MM
```

Ejemplo:

```js
plannedStartTime: "20:20"
```

Debe representar una hora válida dentro del mismo día.

---

# `plannedEndTime`

Tipo:

```text
string
```

Formato:

```text
HH:MM
```

Debe cumplir:

```text
plannedEndTime > plannedStartTime
```

No se permiten:

* horas iguales;
* hora final anterior;
* cruces de medianoche;
* `24:00`.

---

# Duración

La duración **no se almacena**.

Debe calcularse utilizando:

```text
plannedEndTime - plannedStartTime
```

Ejemplo:

```text
20:20 → 20:40
```

Resultado:

```text
20min
```

Si el horario cambia mediante edición, la duración se recalcula automáticamente.

No agregar:

```js
estimatedDuration
```

al objeto.

---

# `statesByDate`

Tipo conceptual:

```text
Record<string, ActivityStatus>
```

Relaciona una fecha con el estado de ese registro durante esa fecha.

Ejemplo:

```js
statesByDate: {
    "2026-08-03": "completed",
    "2026-08-04": "in_progress"
}
```

---

# Formato de fecha

Las claves deben utilizar:

```text
YYYY-MM-DD
```

Ejemplo:

```text
2026-08-04
```

---

# Estados permitidos

```text
pending
in_progress
completed
not_completed
cancelled
```

Si una fecha no existe dentro de `statesByDate`, debe interpretarse como:

```text
pending
```

No es necesario almacenar explícitamente:

```js
"2026-08-05": "pending"
```

---

# Regreso a pending

Cuando un estado recorra completamente el ciclo y regrese a:

```text
pending
```

el store puede eliminar esa clave de `statesByDate`.

Ejemplo:

Antes:

```js
statesByDate: {
    "2026-08-04": "cancelled"
}
```

Después de regresar a pendiente:

```js
statesByDate: {}
```

---

# Datos iniciales del MVP 03

El archivo:

```text
js/data/mock-activities.js
```

debe conservar los siete registros originales.

Además, cada uno debe recibir una clasificación válida.

---

# Clasificación inicial propuesta

## Gym - Pecho

```js
{
    recordKind: "activity",
    recordSubtype: "periodic"
}
```

---

## Cepillado de dientes

```js
{
    recordKind: "habit",
    recordSubtype: "scheduled"
}
```

---

## Meditar

```js
{
    recordKind: "habit",
    recordSubtype: "scheduled"
}
```

---

## Hybridge - Programación

```js
{
    recordKind: "activity",
    recordSubtype: "anchor"
}
```

---

## Comida

```js
{
    recordKind: "habit",
    recordSubtype: "scheduled"
}
```

---

## CCNA / Estudio

```js
{
    recordKind: "activity",
    recordSubtype: "periodic"
}
```

---

## Preparación del día siguiente

```js
{
    recordKind: "habit",
    recordSubtype: "scheduled"
}
```

Estas clasificaciones son datos iniciales de demostración y podrán modificarse cuando exista persistencia real.

---

# Ejemplo completo de registro inicial

```js
{
    id: "gym-pecho",
    name: "Gym - Pecho",
    recordKind: "activity",
    recordSubtype: "periodic",
    position: 1,
    plannedStartTime: "05:30",
    plannedEndTime: "07:15",
    statesByDate: {}
}
```

---

# Borrador de creación

El formulario no debe crear directamente el objeto definitivo.

Debe producir un borrador conceptual:

```js
{
    name: "SQL",
    recordKind: "activity",
    recordSubtype: "periodic",
    plannedStartTime: "20:20",
    plannedEndTime: "20:40"
}
```

El borrador no debe contener:

```text
id
position
statesByDate
```

Esas propiedades pertenecen al store.

---

# Registro creado por el store

Después de validar, el store construye:

```js
{
    id: "generated-id",
    name: "SQL",
    recordKind: "activity",
    recordSubtype: "periodic",
    position: 8,
    plannedStartTime: "20:20",
    plannedEndTime: "20:40",
    statesByDate: {}
}
```

---

# Borrador de edición

Editar utiliza la misma estructura conceptual del borrador:

```js
{
    name: "SQL avanzado",
    recordKind: "activity",
    recordSubtype: "periodic",
    plannedStartTime: "20:25",
    plannedEndTime: "20:45"
}
```

El formulario no debe enviar un nuevo:

```text
id
```

ni un nuevo:

```text
statesByDate
```

---

# `updateActivity`

El store debe proporcionar una operación equivalente a:

```js
updateActivity(activityId, activityDraft)
```

No es obligatorio utilizar exactamente ese nombre, pero sí esa responsabilidad.

---

# Comportamiento de `updateActivity`

Debe:

1. Buscar el registro mediante `activityId`.
2. Verificar que exista.
3. Validar el borrador.
4. Validar `recordKind` y `recordSubtype`.
5. Comprobar conflictos temporales ignorando el propio registro.
6. Conservar el mismo `id`.
7. Conservar completamente `statesByDate`.
8. Actualizar los campos editables.
9. Ordenar la colección.
10. Renumerar posiciones.
11. Devolver el registro actualizado o un resultado equivalente.

---

# Campos modificables

Editar puede modificar únicamente:

```text
name
recordKind
recordSubtype
plannedStartTime
plannedEndTime
```

---

# Campos protegidos durante edición

No reemplazar directamente:

```text
id
statesByDate
```

La posición puede cambiar únicamente como consecuencia de:

```text
ordenar
+
renumerar
```

---

# Ejemplo de conservación

Antes:

```js
{
    id: "sql",
    name: "SQL",
    recordKind: "activity",
    recordSubtype: "periodic",
    position: 8,
    plannedStartTime: "20:20",
    plannedEndTime: "20:40",
    statesByDate: {
        "2026-08-04": "completed"
    }
}
```

Edición:

```js
{
    name: "SQL avanzado",
    recordKind: "activity",
    recordSubtype: "anchor",
    plannedStartTime: "20:15",
    plannedEndTime: "20:35"
}
```

Resultado:

```js
{
    id: "sql",
    name: "SQL avanzado",
    recordKind: "activity",
    recordSubtype: "anchor",
    position: /* posición recalculada */,
    plannedStartTime: "20:15",
    plannedEndTime: "20:35",
    statesByDate: {
        "2026-08-04": "completed"
    }
}
```

---

# Integridad temporal

El store debe impedir que dos registros se superpongan.

---

# Conversión a minutos

Para comparar horarios puede utilizarse una función conceptual:

```js
function timeToMinutes(time) {
    const [hours, minutes] = time.split(":").map(Number);
    return hours * 60 + minutes;
}
```

Puede existir dentro de:

```text
utils/date-time.js
```

---

# Regla de conflicto

Dos intervalos:

```text
A = [startA, endA)
B = [startB, endB)
```

entran en conflicto cuando:

```js
startA < endB && endA > startB
```

Se interpretan conceptualmente como intervalos semiabiertos.

Esto permite horarios contiguos.

---

# Horarios contiguos válidos

```text
19:15 → 20:15
20:15 → 20:40
```

No existe conflicto.

---

# Superposición inicial

```text
Existente:
19:15 → 20:15

Nuevo:
20:00 → 20:40
```

Resultado:

```text
conflicto
```

---

# Superposición final

```text
Existente:
19:15 → 20:15

Nuevo:
19:00 → 19:30
```

Resultado:

```text
conflicto
```

---

# Intervalo contenido

```text
Existente:
19:15 → 20:15

Nuevo:
19:30 → 20:00
```

Resultado:

```text
conflicto
```

---

# Intervalo contenedor

```text
Existente:
19:15 → 20:15

Nuevo:
19:00 → 20:30
```

Resultado:

```text
conflicto
```

---

# API conceptual para conflictos

El store puede implementar una operación interna equivalente a:

```js
findTimeConflict(startTime, endTime, ignoredActivityId = null)
```

Resultado conceptual:

```text
registro conflictivo
o
null
```

No es obligatorio utilizar exactamente este nombre.

---

# Crear y conflictos

Cuando se crea:

```text
ignoredActivityId = null
```

Debe compararse contra todos los registros.

---

# Editar y conflictos

Cuando se edita:

```text
ignoredActivityId = activityId
```

El propio registro debe omitirse.

Todos los demás deben comprobarse.

---

# Error estructurado de conflicto

Es preferible que el store pueda comunicar información suficiente para que el formulario muestre:

```text
El horario se cruza con “CCNA / Estudio” (19:15–20:15).
```

Conceptualmente puede devolver o lanzar información como:

```js
{
    type: "time_conflict",
    conflictingActivity: {
        id: "ccna-estudio",
        name: "CCNA / Estudio",
        plannedStartTime: "19:15",
        plannedEndTime: "20:15"
    }
}
```

No es obligatorio utilizar exactamente esta estructura.

Sí debe evitarse depender de analizar texto de errores para saber qué ocurrió.

---

# Creación normal

El store mantiene una operación equivalente a:

```js
addActivity(activityDraft)
```

Aunque internamente el sistema ya maneje registros de distintos tipos, puede conservarse temporalmente este nombre para evitar una refactorización innecesaria.

También puede renombrarse a:

```js
addRecord()
```

si se actualizan todas las referencias de forma consistente.

Codex debe explicar cualquier renombrado.

---

# Inserción contextual

Debe conservar una operación equivalente a:

```js
insertActivityBefore(activityDraft, referenceActivityId)
```

o un nombre más general equivalente.

La referencia contextual no permite violar integridad temporal.

---

# Cambio importante respecto al MVP 02

En el MVP 02 era válido conceptualmente insertar otro registro con la misma hora inicial antes de una referencia.

A partir del MVP 03 esto solamente es válido si **los intervalos no se superponen**.

Ejemplo:

Referencia:

```text
07:50 → 08:00
```

Nueva actividad:

```text
07:50 → 07:55
```

Esto ahora es:

```text
INVÁLIDO
```

porque ambos intervalos se superponen.

La posición secundaria no puede justificar un conflicto temporal.

---

# Inserción contextual válida

Referencia:

```text
08:00 → 08:15
```

Registro anterior:

```text
07:50 → 07:55
```

Existe un espacio:

```text
07:55 → 08:00
```

Una nueva actividad:

```text
07:55 → 08:00
```

es válida.

---

# Sugerencia de horario

El formulario contextual puede recibir información suficiente para sugerir:

```text
plannedEndTime = inicio de la referencia
```

y, cuando resulte posible:

```text
plannedStartTime = final del registro anterior
```

Estas sugerencias:

* no son datos persistentes;
* pueden modificarse;
* no deben saltarse la validación final.

---

# Estado de interfaz no persistente

Los siguientes valores **no pertenecen al registro**:

```text
selectedDate
selectedActivityId
dialogMode
referenceActivityId
openerElement
isSelected
isEditing
```

Son estado de interfaz.

No agregar propiedades como:

```js
isSelected: true
```

dentro del objeto de actividad.

---

# Modos del formulario

El formulario puede mantener conceptualmente:

```js
{
    mode: "create",
    activityId: null,
    referenceActivityId: null
}
```

o:

```js
{
    mode: "insert_before",
    activityId: null,
    referenceActivityId: "sql"
}
```

o:

```js
{
    mode: "edit",
    activityId: "sql",
    referenceActivityId: null
}
```

Estos datos no deben almacenarse dentro del registro.

---

# API conceptual del store

El store debe ofrecer operaciones equivalentes a:

```text
getActivities()
getActivityById(activityId)
addActivity(activityDraft)
insertActivityBefore(activityDraft, referenceActivityId)
updateActivity(activityId, activityDraft)
advanceActivityStatus(activityId, dateKey)
```

Puede añadir internamente:

```text
findTimeConflict(...)
validateActivityDraft(...)
sortActivities(...)
renumberPositions(...)
```

No crear una API excesivamente grande si esas funciones solo son internas.

---

# `getActivities`

Debe evitar entregar innecesariamente la colección mutable original.

Puede devolver:

* un nuevo arreglo;
* copias de objetos;
* copias de `statesByDate`.

La vista no debe poder alterar silenciosamente el store.

---

# `getActivityById`

Debe devolver:

```text
registro
o
null
```

Debe permitir al formulario obtener los valores actuales para edición.

---

# `addActivity`

Debe:

* validar;
* comprobar clasificación;
* comprobar horarios;
* comprobar conflictos;
* generar identificador;
* crear `statesByDate`;
* asignar posición;
* ordenar;
* renumerar;
* devolver el registro creado.

---

# `insertActivityBefore`

Debe:

* validar;
* buscar referencia;
* comprobar conflictos;
* crear registro;
* conservar intención secundaria de inserción cuando sea aplicable;
* ordenar cronológicamente;
* renumerar.

Si la referencia no existe, puede degradarse de manera segura a creación normal.

---

# `updateActivity`

Debe:

* localizar registro;
* validar;
* ignorarse a sí mismo al buscar conflictos;
* preservar identidad;
* preservar estados;
* actualizar propiedades editables;
* ordenar;
* renumerar.

---

# `advanceActivityStatus`

Debe continuar modificando únicamente:

```text
una actividad
+
una fecha
```

No debe alterar:

* clasificación;
* nombre;
* horarios;
* otras fechas.

---

# Validación defensiva

Aunque el formulario valide correctamente, el store debe volver a comprobar como mínimo:

* nombre válido;
* tipo válido;
* subtipo compatible;
* inicio presente;
* final presente;
* final posterior;
* ausencia de conflicto temporal.

Esto protege la integridad del estado en memoria.

---

# Datos que no deben agregarse todavía

No incluir:

```text
actualStartTime
actualEndTime
actualDuration
comments
subactivities
recurrence
weekdays
priority
category
measurementType
unit
targetQuantity
actualQuantity
createdAt
updatedAt
userId
isAnchorLocked
autoShift
```

Aunque algunos se utilizarán en entregas futuras.

---

# Hábito tipo logro

No utilizar:

```text
achievement
```

como `recordSubtype` en este contrato.

Los hábitos tipo logro pertenecen a otro submódulo futuro.

---

# Persistencia

El store sigue siendo exclusivamente temporal.

No utilizar:

* `localStorage`;
* `sessionStorage`;
* IndexedDB;
* JSON externo;
* API;
* archivos escritos desde JavaScript;
* base de datos.

---

# Recarga

Después de recargar el navegador:

* regresan los siete registros iniciales;
* regresan sus clasificaciones iniciales;
* desaparecen registros nuevos;
* desaparecen ediciones;
* regresan estados originales.

---

# Compatibilidad futura

El contrato debe mantenerse suficientemente simple para que, en una entrega futura:

```text
Memory Activity Store
        ↓
API Store
        ↓
Flask
        ↓
PostgreSQL
```

pueda reemplazarse la fuente de datos sin rehacer las vistas.

Esto no significa implementar esa infraestructura ahora.

---

# Resumen del modelo MVP 03

Cada registro del `Plan del día` queda definido por:

```text
Identidad
    id

Descripción
    name

Clasificación
    recordKind
    recordSubtype

Planeación temporal
    plannedStartTime
    plannedEndTime

Orden
    position

Seguimiento por fecha
    statesByDate
```

Todo lo demás pertenece:

* al estado de interfaz;
* a funciones futuras;
* o a otros submódulos.
