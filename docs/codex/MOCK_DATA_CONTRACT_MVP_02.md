# Contrato de datos simulados — Frontend MVP 02

## Propósito

Este documento define la estructura de datos y las operaciones en memoria
para la segunda entrega frontend.

Durante esta entrega no existe:

- backend;
- API;
- base de datos;
- persistencia;
- autenticación.

El modelo debe prepararse conceptualmente para reemplazar el store en
memoria por una API futura sin reconstruir las vistas.

---

# Principio de propiedad de los datos

El archivo:

```text
state/activity-store.js
```

es el propietario de la colección mutable de actividades.

Las vistas no deben modificar directamente:

- el arreglo;
- las posiciones;
- `statesByDate`;
- los identificadores.

El flujo debe ser:

```text
Vista
    ↓ expresa una intención
app.js
    ↓ coordina
Activity Store
    ↓ modifica datos
app.js
    ↓ solicita render
Vista
```

---

# Estructura de una actividad

Cada actividad debe respetar esta forma:

```js
{
    id: "gym-pecho",
    name: "Gym - Pecho",
    position: 1,
    plannedStartTime: "05:30",
    plannedEndTime: "07:15",
    statesByDate: {
        "2026-08-03": "completed"
    }
}
```

No se deben agregar propiedades correspondientes a funciones futuras.

---

# Campos

## `id`

Tipo conceptual:

```text
string
```

Reglas:

- obligatorio;
- único;
- estable durante la sesión;
- no dependiente exclusivamente del nombre.

Ejemplos:

```js
"gym-pecho"
"activity-4e2b1..."
```

Las actividades iniciales pueden conservar identificadores legibles.

Las actividades nuevas deben utilizar un identificador generado.

---

## `name`

Tipo conceptual:

```text
string
```

Reglas:

- obligatorio;
- eliminar espacios al inicio y al final;
- no aceptar únicamente espacios;
- longitud máxima: 80 caracteres;
- conservar acentos y caracteres en español.

Ejemplo:

```js
name: "Preparación del día siguiente"
```

El store puede asumir que `app.js` o el formulario entregan datos
validados, pero debe rechazar una actividad estructuralmente inválida.

---

## `position`

Tipo conceptual:

```text
integer
```

Reglas:

- comienza en `1`;
- se utiliza como criterio secundario de orden;
- debe renumerarse después de agregar o insertar;
- no debe haber posiciones duplicadas después de la renumeración;
- no representa la hora.

Ejemplo:

```js
position: 4
```

La posición es interna y no debe escribirse manualmente por el usuario.

---

## `plannedStartTime`

Tipo conceptual:

```text
string
```

Formato obligatorio:

```text
HH:MM
```

Ejemplos válidos:

```text
05:30
08:00
19:15
```

Debe representar una hora dentro del mismo día.

---

## `plannedEndTime`

Tipo conceptual:

```text
string
```

Formato:

```text
HH:MM
```

Reglas:

- obligatorio;
- posterior a `plannedStartTime`;
- no puede ser igual;
- no puede representar cruce de medianoche;
- no puede ser `24:00`.

---

## `statesByDate`

Tipo conceptual:

```text
Record<string, ActivityStatus>
```

Relaciona fechas con estados.

Ejemplo:

```js
statesByDate: {
    "2026-08-03": "completed",
    "2026-08-04": "in_progress"
}
```

Formato de fecha:

```text
YYYY-MM-DD
```

Estados permitidos:

```text
pending
in_progress
completed
not_completed
cancelled
```

Cuando una fecha no existe en `statesByDate`, su estado se interpreta como:

```text
pending
```

No deben guardarse entradas explícitas `pending` innecesarias.

Cuando un estado regresa a `pending`, el store puede eliminar esa clave
para conservar un objeto más limpio.

---

# Datos iniciales

El archivo:

```text
data/mock-activities.js
```

debe exportar las mismas siete actividades aprobadas en el MVP 01:

1. Gym - Pecho
2. Cepillado de dientes
3. Meditar
4. Hybridge - Programación
5. Comida
6. CCNA / Estudio
7. Preparación del día siguiente

Debe conservar:

- nombres;
- horarios;
- posiciones;
- duración resultante;
- estados demostrativos de la fecha actual.

Los datos iniciales deben poder copiarse al store sin que una recarga
en caliente o una mutación accidental modifique la definición original.

Una implementación válida puede clonar:

- el arreglo;
- cada actividad;
- cada objeto `statesByDate`.

---

# Borrador de actividad

El formulario no debe crear directamente el objeto definitivo.

Debe producir un borrador conceptual:

```js
{
    name: "Leer documentación",
    plannedStartTime: "10:00",
    plannedEndTime: "10:30"
}
```

Este borrador no contiene:

- `id`;
- `position`;
- `statesByDate`.

Esos campos deben ser asignados por el store o por la coordinación de
creación.

---

# Contexto de inserción

El formulario puede abrirse en uno de dos modos.

## Modo normal

```js
{
    mode: "append",
    referenceActivityId: null
}
```

Significado:

- no existe fila de referencia;
- la actividad se agrega;
- posteriormente se ordena cronológicamente.

---

## Modo contextual

```js
{
    mode: "insert_before",
    referenceActivityId: "cepillado-dientes"
}
```

Significado:

- existe una actividad de referencia;
- la intención es aparecer antes de esa referencia cuando el horario lo
  permita;
- la hora continúa teniendo prioridad.

---

# Objeto definitivo de actividad nueva

Después de validar, debe construirse:

```js
{
    id: "activity-uuid",
    name: "Leer documentación",
    position: 8,
    plannedStartTime: "10:00",
    plannedEndTime: "10:30",
    statesByDate: {}
}
```

El store debe asignar:

- `id`;
- `position`;
- `statesByDate`.

---

# Generación de identificadores

Debe utilizarse preferentemente:

```js
crypto.randomUUID()
```

Cuando no exista, puede utilizarse una función alternativa.

Ejemplo conceptual:

```js
function createFallbackId() {
    return `activity-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
```

La implementación debe minimizar la posibilidad de colisiones dentro de
la sesión.

No se necesita todavía un UUID generado por servidor.

---

# Orden de actividades

El orden definitivo utiliza:

1. `plannedStartTime`;
2. `position`.

Conceptualmente:

```js
activities.sort((first, second) => {
    return (
        first.plannedStartTime.localeCompare(second.plannedStartTime) ||
        first.position - second.position
    );
});
```

Después de ordenar debe realizarse una renumeración:

```text
1, 2, 3, 4...
```

---

# Inserción normal

En modo:

```text
append
```

la actividad puede recibir inicialmente:

```text
posición máxima + 1
```

Después:

1. se agrega;
2. se ordena por hora;
3. se renumeran posiciones.

Por ello, “agregar al final” describe la intención de creación, pero la
posición visual final depende de la hora.

---

# Inserción antes de una referencia

En modo:

```text
insert_before
```

debe localizarse la actividad mediante:

```js
referenceActivityId
```

## Referencia inexistente

Si la referencia ya no existe:

- no debe fallar la aplicación;
- puede degradar a modo `append`;
- debe mantenerse un comportamiento consistente.

## Criterio de posición

Antes de ordenar, la nueva actividad debe recibir una posición que permita
situarla antes de la referencia cuando comparten hora.

Una estrategia válida:

1. localizar el índice de referencia;
2. insertar temporalmente antes de ese índice;
3. conservar el orden del arreglo;
4. ordenar por hora y orden previo;
5. renumerar posiciones.

Otra estrategia válida:

- asignar una posición temporal menor a la referencia;
- ordenar;
- renumerar.

No deben conservarse posiciones decimales como resultado final.

---

# Prioridad de la hora

La intención contextual no puede romper el orden cronológico.

## Mismo horario

```text
Nueva:      07:50
Referencia: 07:50
```

La nueva aparece antes.

## Horario anterior

```text
Nueva:      07:30
Referencia: 07:50
```

La nueva aparece antes por hora.

## Horario posterior

```text
Nueva:      08:10
Referencia: 07:50
```

La nueva aparece después.

No modificar horarios de ninguna actividad.

---

# API conceptual del store

El archivo `activity-store.js` puede exportar una fábrica o funciones.

Una forma conceptual aceptada es:

```js
const activityStore = createActivityStore(initialActivities);
```

Debe ofrecer operaciones equivalentes a las siguientes.

---

## `getActivities()`

Propósito:

- obtener las actividades actuales;
- entregarlas ordenadas;
- evitar que la vista modifique directamente el arreglo interno.

Forma conceptual:

```js
activityStore.getActivities();
```

Resultado:

```js
Activity[]
```

Es recomendable devolver:

- un arreglo nuevo;
- objetos clonados cuando sea razonable;
- una copia de `statesByDate`.

---

## `getActivityById(activityId)`

Propósito:

- localizar una actividad;
- obtener información para el modo contextual.

Forma conceptual:

```js
activityStore.getActivityById("gym-pecho");
```

Resultado:

```text
actividad o null
```

---

## `addActivity(activityDraft)`

Propósito:

- crear actividad sin referencia;
- generar identificador;
- asignar posición;
- crear `statesByDate`;
- ordenar;
- renumerar;
- devolver la actividad creada.

Forma conceptual:

```js
activityStore.addActivity({
    name: "Leer",
    plannedStartTime: "10:00",
    plannedEndTime: "10:30"
});
```

---

## `insertActivityBefore(activityDraft, referenceActivityId)`

Propósito:

- crear actividad con intención contextual;
- localizar referencia;
- conservar prioridad cronológica;
- situarla antes cuando comparten hora;
- renumerar;
- devolver la actividad creada.

Forma conceptual:

```js
activityStore.insertActivityBefore(
    {
        name: "Preparar mochila",
        plannedStartTime: "07:50",
        plannedEndTime: "08:00"
    },
    "cepillado-dientes"
);
```

---

## `advanceActivityStatus(activityId, dateKey)`

Propósito:

- obtener estado actual;
- calcular siguiente estado;
- modificar únicamente una actividad y fecha;
- devolver el nuevo estado.

Forma conceptual:

```js
activityStore.advanceActivityStatus(
    "gym-pecho",
    "2026-08-03"
);
```

La vista no debe calcular ni escribir directamente el nuevo valor dentro
de `statesByDate`.

---

# Validación defensiva del store

Aunque el formulario valide, el store debe evitar aceptar un objeto
evidentemente inválido.

Como mínimo debe verificar:

- nombre no vacío;
- hora inicial presente;
- hora final presente;
- final posterior al inicio.

Ante datos inválidos puede:

- lanzar un error controlado; o
- devolver un resultado de error documentado.

No debe insertar parcialmente una actividad inválida.

---

# Fecha seleccionada

La fecha seleccionada no pertenece a una actividad.

Debe mantenerse dentro de:

- `app.js`; o
- un estado de interfaz específico.

No debe guardarse dentro del store de actividades.

La fecha inicial es la fecha local actual.

---

# Fila seleccionada

El identificador de la fila seleccionada es estado de interfaz.

No pertenece al modelo persistente.

Puede almacenarse en:

```js
let selectedActivityId = null;
```

dentro del coordinador o de la vista.

No debe añadirse una propiedad como:

```js
isSelected
```

dentro de cada actividad.

---

# Estado del formulario

El modo del formulario tampoco forma parte de una actividad.

Ejemplo conceptual:

```js
{
    mode: "append",
    referenceActivityId: null,
    openerElement: null
}
```

Debe reiniciarse al:

- guardar;
- cancelar;
- cerrar con Escape.

---

# Duración estimada

No debe guardarse dentro de la actividad.

Debe calcularse:

```text
plannedEndTime - plannedStartTime
```

El cálculo debe seguir mostrando:

```text
1h 45min
5min
1h
```

No almacenar:

```js
estimatedDuration
```

en esta entrega.

---

# Propiedades no autorizadas

No agregar todavía:

```text
type
activityType
habitType
recurrence
weekdays
comment
actualStartTime
actualEndTime
realDuration
subactivities
priority
category
measurementType
unit
quantity
createdAt
updatedAt
userId
```

Estas propiedades pertenecen a entregas futuras y todavía no deben
contaminar el contrato frontend.

---

# Persistencia

El store vive únicamente en memoria.

No utilizar:

- `localStorage`;
- `sessionStorage`;
- IndexedDB;
- archivos JSON;
- API;
- PostgreSQL.

Al recargar se restauran los datos iniciales.

---

# Compatibilidad futura

La interfaz debe depender de operaciones conceptuales del store y no de
la ubicación física del arreglo.

En una entrega futura será posible reemplazar:

```text
MemoryActivityStore
```

por:

```text
ApiActivityStore
```

sin rehacer:

- formulario;
- matriz;
- control visual de estados.

No se debe implementar todavía la versión API.

Solo debe conservarse una separación razonable entre:

```text
datos
estado
vistas
coordinación
```

---

# Ejemplos de actividades nuevas

## Agregada normalmente

Entrada:

```js
{
    name: "Leer documentación",
    plannedStartTime: "10:00",
    plannedEndTime: "10:30"
}
```

Resultado conceptual:

```js
{
    id: "activity-generated-id",
    name: "Leer documentación",
    position: 5,
    plannedStartTime: "10:00",
    plannedEndTime: "10:30",
    statesByDate: {}
}
```

La posición final depende del orden cronológico y la renumeración.

---

## Insertada antes con la misma hora

Referencia:

```js
{
    id: "cepillado-dientes",
    plannedStartTime: "07:50",
    position: 2
}
```

Entrada:

```js
{
    name: "Tomar agua",
    plannedStartTime: "07:50",
    plannedEndTime: "07:55"
}
```

Resultado visual esperado:

```text
07:50 — Tomar agua
07:50 — Cepillado de dientes
```

---

## Insertada con una hora posterior

Referencia:

```text
07:50 — Cepillado de dientes
```

Entrada:

```text
08:10 — Tomar vitaminas
```

Resultado visual:

```text
07:50 — Cepillado de dientes
08:10 — Tomar vitaminas
```

La hora tiene prioridad sobre la referencia contextual.
