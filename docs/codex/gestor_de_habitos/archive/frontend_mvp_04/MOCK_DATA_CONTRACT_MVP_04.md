
# Contrato de datos simulados — MVP 04

## Nombre de la entrega

**MVP 04 — Motor de planificación por ocurrencias**

Este documento define la representación concreta en JavaScript del modelo
descrito en:

`/docs/codex/SCHEDULE_MODEL_MVP_04.md`

Es normativo para:

- MVP 04.0.1 — Motor temporal, modelo y materialización.
- MVP 04.0.2 — Navegación temporal y visualización frontend.

---

# Objetivo

La aplicación debe dejar atrás el modelo donde un único objeto contiene:

- un horario general;
- una posición;
- muchos estados agrupados por fecha.

En MVP 04 la agenda se divide conceptualmente en:

PlanItem
+
Occurrence

Un PlanItem representa qué cosa es.

Una Occurrence representa cuándo está agendada esa cosa en una fecha concreta.

---

# Fuente canónica en memoria

La fuente mutable principal debe poder representarse conceptualmente como:

```js
{
    planItems: [],
    occurrences: []
}
```

Estas dos colecciones son la fuente canónica.

No utilizar como fuente principal una estructura profundamente anidada como:

```js
{
    planItems: [
        {
            ...,
            occurrences: {
                "2026-08-20": {...},
                "2026-08-21": {...}
            }
        }
    ]
}
```

La UI puede construir una proyección agrupada equivalente cuando sea útil.

La razón para mantener las colecciones separadas es facilitar:

* consultas por fecha;
* edición de una occurrence concreta;
* detección de conflictos;
* navegación temporal;
* materialización;
* futura migración a PostgreSQL.

---

# Proyección permitida para la interfaz

Aunque el estado canónico permanezca separado, las vistas pueden recibir una
estructura derivada como:

```js
{
    planItem: {...},

    occurrences: [
        {...},
        {...},
        {...}
    ]
}
```

o conceptualmente:

```js
{
    id: "...",
    name: "Gym",

    occurrencesByDate: {
        "2026-08-20": [...],
        "2026-08-22": [...]
    }
}
```

Esta proyección:

* no es la fuente mutable;
* puede reconstruirse;
* no debe duplicar permanentemente la información.

---

# PlanItem

Cada PlanItem debe ser un objeto con identidad independiente de sus
occurrences.

Existen dos formas válidas principales.

---

# PlanItem de tipo Activity

Estructura conceptual:

```js
{
    id: "uuid",

    name: "Gym",

    kind: "activity",

    activityType: "periodic",

    generationConfig: {
        ...
    }
}
```

Campos permitidos:

```text
id
name
kind
activityType
generationConfig
```

No debe contener:

```text
habitType
occurrences
statesByDate
position
startTime
endTime
status
priority
```

---

# PlanItem de tipo Habit

Estructura conceptual:

```js
{
    id: "uuid",

    name: "Cepillado de dientes",

    kind: "habit",

    habitType: "scheduled",

    generationConfig: {
        ...
    }
}
```

Campos permitidos:

```text
id
name
kind
habitType
generationConfig
```

No debe contener:

```text
activityType
occurrences
statesByDate
position
startTime
endTime
status
priority
```

---

# Modelo discriminado

No utilizar estructuras como:

```js
{
    kind: "activity",
    activityType: "anchor",
    habitType: null
}
```

ni:

```js
{
    kind: "habit",
    activityType: null,
    habitType: "scheduled"
}
```

Cuando:

```js
kind === "activity"
```

debe existir:

```js
activityType
```

y no debe existir:

```js
habitType
```

Cuando:

```js
kind === "habit"
```

debe existir:

```js
habitType
```

y no debe existir:

```js
activityType
```

---

# id de PlanItem

Tipo:

```text
string
```

Debe ser:

* obligatorio;
* único;
* estable;
* independiente del nombre;
* independiente de las fechas;
* independiente de los horarios.

Para registros nuevos utilizar preferentemente:

```js
crypto.randomUUID()
```

Si el entorno no dispone de esa API, puede utilizarse un fallback local
adecuado.

---

# IDs del mock inicial

Los datos iniciales pueden conservar temporalmente identificadores legibles
si facilita las pruebas.

Ejemplo:

```js
id: "gym"
```

Pero la función utilizada para crear nuevos PlanItems debe generar identidad
técnica real.

No debe generarse el id nuevo a partir del nombre.

---

# name

Tipo:

```text
string
```

Reglas:

* obligatorio;
* trim;
* no aceptar únicamente espacios;
* máximo 80 caracteres;
* puede cambiar sin cambiar id.

Ejemplo:

```text
"   Gym   "
```

se almacena como:

```text
"Gym"
```

---

# kind

Valores permitidos:

```text
activity
habit
```

No existen otros valores durante MVP 04.

---

# activityType

Solamente existe cuando:

```js
kind === "activity"
```

Valores permitidos:

```text
anchor
periodic
event
unexpected
```

Representación visible:

```text
anchor     → Ancla
periodic   → Periódica
event      → Evento
unexpected → Imprevista
```

---

# habitType

Solamente existe cuando:

```js
kind === "habit"
```

Valor permitido durante MVP 04:

```text
scheduled
```

Representación visible:

```text
Hábito programado
```

No incluir todavía:

```text
achievement
point
quantity
```

ni otros tipos futuros.

---

# Gym - Pecho

El mock actual puede conservar temporalmente el nombre visible:

```text
Gym - Pecho
```

Esto sigue representando UN único PlanItem.

El texto:

```text
- Pecho
```

no crea todavía una estructura de subactividad.

No implementar:

```text
Gym
└── Pecho
```

como relación de datos durante MVP 04.

---

# generationConfig

`generationConfig` es una propiedad del PlanItem.

Representa la configuración ACTUAL utilizada para generar occurrences futuras.

No tiene:

```text
id
```

propio.

No existe:

```text
scheduleId
scheduleVersionId
```

---

# generationConfig puede ser null

Debe permitirse conceptualmente:

```js
generationConfig: null
```

cuando un PlanItem existe históricamente pero actualmente no posee una
configuración activa de generación.

Esto permite conservar su identidad para reutilizarla posteriormente.

No es necesario implementar todavía toda la interfaz de pausa/reactivación.

---

# generationConfig como unión discriminada

generationConfig debe variar según:

```js
generationConfig.mode
```

Modos previstos:

```text
weekly
interval_days
manual_dates
single_date
```

No deben almacenarse todas las propiedades posibles rellenas con `null`.

Cada modo conserva únicamente los campos que necesita.

---

# Modo weekly

Ejemplo completo:

```js
{
    mode: "weekly",

    startDate: "2026-08-01",

    endDate: null,

    indefinite: true,

    weekdays: [1, 3, 5],

    defaultStartTime: "05:30",

    defaultEndTime: "07:15",

    weekdayTimeOverrides: {
        "5": {
            startTime: "06:00",
            endTime: "07:30"
        }
    }
}
```

---

# weekly.startDate

Formato:

```text
YYYY-MM-DD
```

Indica desde qué fecha puede comenzar a generar occurrences.

---

# weekly.endDate

Puede contener:

```text
YYYY-MM-DD
```

o:

```js
null
```

Cuando:

```js
indefinite === true
```

debe utilizarse:

```js
endDate === null
```

---

# weekly.indefinite

Tipo:

```text
boolean
```

Si:

```js
true
```

la configuración no posee una fecha final conceptual.

La materialización utiliza un horizonte limitado.

---

# Combinaciones válidas de fin

Configuración finita:

```js
{
    endDate: "2026-12-31",
    indefinite: false
}
```

Configuración indefinida:

```js
{
    endDate: null,
    indefinite: true
}
```

No permitir:

```js
{
    endDate: "2026-12-31",
    indefinite: true
}
```

---

# weekly.weekdays

Array de enteros ISO.

Valores permitidos:

```text
1 2 3 4 5 6 7
```

Donde:

```text
1 = lunes
2 = martes
3 = miércoles
4 = jueves
5 = viernes
6 = sábado
7 = domingo
```

Reglas:

* mínimo un día;
* valores únicos;
* no aceptar valores fuera de 1–7;
* ordenar de menor a mayor al normalizar.

Ejemplo:

```js
weekdays: [1, 3, 5]
```

---

# weekly.defaultStartTime

Formato:

```text
HH:MM
```

Hora general utilizada cuando un día no posee override.

---

# weekly.defaultEndTime

Formato:

```text
HH:MM
```

Debe ser posterior a:

```text
defaultStartTime
```

No se permiten cruces de medianoche durante MVP 04.

---

# weekdayTimeOverrides

Permite asignar un horario distinto a determinados weekdays.

Ejemplo:

```js
weekdayTimeOverrides: {
    "1": {
        startTime: "05:30",
        endTime: "07:00"
    },

    "5": {
        startTime: "06:30",
        endTime: "08:00"
    }
}
```

Las claves se representan como strings porque son propiedades de objeto.

Semánticamente continúan representando días ISO.

---

# Validación de weekdayTimeOverrides

Solo pueden existir overrides para días incluidos dentro de:

```js
weekdays
```

Ejemplo inválido:

```js
weekdays: [1, 3, 5]

weekdayTimeOverrides: {
    "2": {...}
}
```

porque martes no está activo.

Cada override debe tener:

```text
startTime
endTime
```

válidos.

---

# Resolución de horario weekly

Conceptualmente:

```text
Si existe override para weekday:
    utilizar override
Si no:
    utilizar horario default
```

No modificar el horario default al resolver una occurrence.

La occurrence recibe una copia concreta del horario resuelto.

---

# Modo interval_days

Ejemplo:

```js
{
    mode: "interval_days",

    startDate: "2026-08-20",

    endDate: null,

    indefinite: true,

    intervalDays: 20,

    defaultStartTime: "12:00",

    defaultEndTime: "13:00"
}
```

---

# intervalDays

Debe ser:

* entero;
* mayor o igual a 1.

Ejemplo:

```js
intervalDays: 20
```

La secuencia se calcula tomando:

```text
startDate
```

como fecha ancla.

---

# Ejemplo interval_days

```text
startDate:
20 agosto

intervalDays:
20
```

genera conceptualmente:

```text
20 agosto
9 septiembre
29 septiembre
19 octubre
...
```

hasta alcanzar el límite finito o el horizonte de materialización.

---

# Modo manual_dates

Debe permitir fechas manuales con horarios independientes.

Estructura:

```js
{
    mode: "manual_dates",

    entries: [
        {
            date: "2026-09-01",
            startTime: "10:00",
            endTime: "11:00"
        },

        {
            date: "2026-11-20",
            startTime: "16:00",
            endTime: "17:30"
        }
    ]
}
```

---

# manual_dates.entries

Debe ser un array no vacío.

Cada entrada contiene:

```text
date
startTime
endTime
```

Esto permite horarios diferentes para cada fecha.

---

# Fechas duplicadas en manual_dates

Puede existir más de una entrada para la misma fecha SI sus horarios son
diferentes y no generan un conflicto inválido.

Ejemplo futuro posible:

```text
Medicamento
08:00

Medicamento
20:00
```

No asumir que:

```text
un PlanItem
=
máximo una occurrence por día
```

---

# Entradas duplicadas idénticas

No debe materializarse dos veces:

```text
mismo PlanItem
+
misma fecha
+
mismo startTime
+
mismo endTime
```

La materialización debe ser idempotente respecto a esa combinación.

---

# Modo single_date

Estructura:

```js
{
    mode: "single_date",

    date: "2027-07-10",

    startTime: "09:00",

    endTime: "23:00"
}
```

Se utiliza principalmente para:

```text
event
unexpected
```

---

# single_date no utiliza

No agregar:

```text
weekdays
intervalDays
indefinite
endDate
weekdayTimeOverrides
```

---

# Occurrence

Cada occurrence debe tener exactamente la estructura conceptual:

```js
{
    id: "uuid",

    planItemId: "uuid",

    date: "2026-08-20",

    startTime: "05:30",

    endTime: "07:15",

    status: "pending"
}
```

Campos persistentes permitidos durante MVP 04:

```text
id
planItemId
date
startTime
endTime
status
```

---

# Occurrence no contiene

No agregar:

```text
name
kind
activityType
habitType
generationConfig
scheduleId
scheduleVersionId
position
statesByDate
priority
plannedStartTime
plannedEndTime
actualStartTime
actualEndTime
duration
isSelected
visible
weekday
weekNumber
month
year
```

Los datos derivados deben calcularse.

---

# occurrence.id

Tipo:

```text
string
```

Debe ser:

* único;
* estable;
* independiente de la fecha;
* independiente del horario.

Utilizar preferentemente:

```js
crypto.randomUUID()
```

para occurrences creadas durante la sesión.

---

# occurrence.planItemId

Debe corresponder al:

```text
PlanItem.id
```

del elemento al que pertenece.

No copiar:

```text
name
```

dentro de la occurrence.

---

# occurrence.date

Formato:

```text
YYYY-MM-DD
```

Ejemplo:

```js
date: "2026-08-20"
```

---

# occurrence.startTime

Formato:

```text
HH:MM
```

Representa el horario actualmente agendado para ESA occurrence.

---

# occurrence.endTime

Formato:

```text
HH:MM
```

Debe ser posterior a:

```text
startTime
```

No permitir cruce de medianoche en MVP 04.

---

# Duración

No almacenar:

```js
duration
```

Debe derivarse mediante:

```text
endTime - startTime
```

---

# occurrence.status

Valores permitidos:

```text
pending
in_progress
completed
not_completed
cancelled
```

Cada occurrence tiene exactamente un status.

No utilizar:

```text
statesByDate
```

---

# Status inicial

Toda occurrence recién materializada comienza como:

```text
pending
```

salvo que los mocks de demostración apliquen explícitamente otro status.

---

# Status y bloqueo temporal

Bloquean horario:

```text
pending
in_progress
completed
```

No bloquean horario:

```text
not_completed
cancelled
```

---

# Función conceptual

Debe existir una responsabilidad de dominio equivalente a:

```js
blocksSchedule(occurrence)
```

No duplicar esta decisión mediante condiciones diferentes repartidas en
múltiples vistas.

---

# Regla conceptual

```js
function blocksSchedule(occurrence) {
    return (
        occurrence.status !== "cancelled"
        &&
        occurrence.status !== "not_completed"
    );
}
```

La implementación exacta puede variar.

---

# Conflictos

Una nueva occurrence entra en conflicto solamente con una occurrence que:

1. tenga la misma `date`;
2. bloquee horario;
3. tenga un intervalo superpuesto.

Regla:

```text
newStart < existingEnd
AND
newEnd > existingStart
```

---

# Contigüidad

Debe permitirse:

```text
08:00–09:00
09:00–10:00
```

No existe conflicto.

---

# cancelled libera horario

Ejemplo:

```js
{
    date: "2026-08-20",
    startTime: "05:30",
    endTime: "07:30",
    status: "cancelled"
}
```

no debe bloquear otra occurrence:

```text
06:00–07:00
```

de la misma fecha.

---

# not_completed libera horario

También debe permitirse superponer una nueva occurrence sobre otra con:

```text
status: "not_completed"
```

Ejemplo:

```text
Gym
05:30–07:30
not_completed

Desayuno
06:15–06:45
pending
```

Esta estructura es válida.

Gym permanece en el historial.

---

# completed continúa bloqueando

No debe permitirse silenciosamente:

```text
Gym
05:30–07:30
completed
```

y:

```text
Otra actividad
06:00–07:00
```

para la misma fecha.

---

# Conflictos durante edición

Cuando se edita una occurrence debe ignorarse únicamente:

```text
su propio id
```

durante la detección de conflicto.

No ignorar todas las occurrences del mismo PlanItem.

---

# Prioridad

NO almacenar:

```js
priority
```

dentro del PlanItem ni de Occurrence.

La prioridad se deriva del tipo del PlanItem.

---

# Constantes conceptuales

Puede existir una estructura de dominio equivalente a:

```js
const SCHEDULING_PRIORITY = Object.freeze({
    NORMAL: 100,
    EVENT: 200,
    UNEXPECTED: 300,
});
```

---

# Resolución conceptual de prioridad

```text
habit / scheduled
→ NORMAL

activity / anchor
→ NORMAL

activity / periodic
→ NORMAL

activity / event
→ EVENT

activity / unexpected
→ UNEXPECTED
```

---

# Materialización

La materialización recibe conceptualmente:

```text
PlanItem
+
generationConfig
+
rango objetivo
```

y produce:

```text
Occurrences
```

---

# API conceptual de materialización

Debe existir una responsabilidad equivalente a:

```js
materializeOccurrences(planItem, rangeStart, rangeEnd)
```

Puede dividirse internamente por modo.

No es obligatorio utilizar exactamente este nombre.

---

# Resultado de materialización

La función debe producir borradores equivalentes a:

```js
{
    planItemId: "...",
    date: "2026-08-24",
    startTime: "05:30",
    endTime: "07:15",
    status: "pending"
}
```

La capa propietaria del estado debe asignar:

```text
id
```

antes de insertarlas.

---

# Idempotencia

Ejecutar materialización varias veces sobre el mismo rango NO debe crear
duplicados idénticos.

Debe comprobarse al menos:

```text
planItemId
date
startTime
endTime
```

antes de crear una occurrence materializada automáticamente.

---

# No utilizar fecha como identidad

La comprobación anterior sirve para evitar duplicados de materialización.

NO convierte:

```text
planItemId + date + startTime + endTime
```

en el id de la occurrence.

La occurrence continúa teniendo id independiente.

---

# Materialización weekly

Para cada fecha del rango:

1. calcular weekday ISO;
2. comprobar si está incluido en `weekdays`;
3. comprobar startDate;
4. comprobar endDate cuando aplique;
5. resolver horario general u override;
6. crear occurrence si no existe duplicado.

---

# Materialización interval_days

Para cada fecha calculada desde:

```text
startDate
```

en saltos de:

```text
intervalDays
```

crear occurrence hasta:

* endDate;
* o el horizonte solicitado.

---

# Materialización manual_dates

Para cada:

```js
entry
```

crear una occurrence equivalente.

No generar fechas fuera de las entradas explícitas.

---

# Materialización single_date

Produce como máximo una occurrence para esa configuración.

---

# Horizonte para indefinite

Cuando:

```js
generationConfig.indefinite === true
```

no intentar generar infinitamente.

Debe materializarse solamente hasta un horizonte finito.

---

# Horizonte mínimo inicial

Durante MVP 04.0.1, el horizonte mínimo inicial será:

```text
fin del mes siguiente al mes de referencia actual/visible
```

Ejemplo:

Referencia:

23 agosto 2026

Horizonte mínimo:

30 septiembre 2026

````

No hardcodear agosto o septiembre.

Debe calcularse.

---

# Extensión del horizonte

Si existe un PlanItem con una fecha futura explícita posterior al horizonte
actual, las configuraciones indefinidas pueden extenderse hasta:

```text
último día del mes de esa fecha futura
````

Ejemplo:

Evento:

10 julio 2027

Nuevo horizonte:

31 julio 2027

````

---

# Horizonte actual como estado del motor

El horizonte de materialización puede mantenerse como estado del motor/store.

NO pertenece al PlanItem.

NO pertenece a Occurrence.

No persistirlo como dato de negocio durante MVP 04.

---

# Estado canónico sugerido del store

Conceptualmente:

```js
{
    planItems: [...],
    occurrences: [...]
}
````

Puede existir además estado interno no persistente como:

```js
{
    materializedThrough: "2026-09-30"
}
```

si facilita el motor.

`materializedThrough` no forma parte del contrato de PlanItem ni Occurrence.

---

# Consultas derivadas

El store debe poder ofrecer responsabilidades equivalentes a:

```text
getPlanItems()
getPlanItemById(id)

getOccurrences()
getOccurrenceById(id)

getOccurrencesForDate(date)
getOccurrencesForMonth(year, month)

getOccurrencesForPlanItem(planItemId)

getPlanItemsForDate(date)
```

No es obligatorio exponer todas públicamente si algunas pueden permanecer
internas.

---

# getOccurrencesForDate

Debe devolver occurrences cuya:

```js
occurrence.date === date
```

Ordenadas por:

```text
startTime
```

---

# getOccurrencesForMonth

Debe devolver occurrences cuya fecha pertenezca al mes solicitado.

No utilizar propiedades almacenadas:

```text
month
year
```

La información se deriva desde:

```text
date
```

---

# Posición

MVP 04 elimina la propiedad persistente:

```text
position
```

La posición visual se deriva al ordenar occurrences por horario.

Si la UI necesita mostrar:

```text
1
2
3
4
```

debe calcular esos números después de ordenar.

No almacenarlos.

---

# Selección

No guardar dentro de PlanItem ni Occurrence:

```text
selected
isSelected
```

La selección pertenece al estado de interfaz.

---

# selectedOccurrenceId

La UI puede mantener:

```js
selectedOccurrenceId
```

como estado temporal.

No forma parte del contrato persistente.

---

# selectedPlanItemId

También puede existir como estado de interfaz si resulta necesario.

No agregarlo al objeto PlanItem.

---

# selectedDate

Estado de interfaz.

Formato:

```text
YYYY-MM-DD
```

No forma parte de los datos persistentes.

---

# visibleMonth

Estado de interfaz.

Puede representarse mediante:

```text
año + mes
```

o un objeto Date interno.

No forma parte de PlanItem ni Occurrence.

---

# showAllMonthRecords

Booleano de interfaz.

Valor inicial esperado en MVP 04.0.2:

```js
false
```

No forma parte de los datos persistentes.

---

# Ausencia de occurrence

Si un PlanItem no tiene occurrence para una fecha:

```text
NO PROGRAMADO
```

No crear una occurrence artificial con:

```js
status: "disabled"
```

No existe ese status.

---

# No programado ≠ cancelled

No programado:

```text
no existe occurrence
```

Cancelled:

```text
sí existe occurrence
+
status === "cancelled"
```

Son conceptos diferentes.

---

# No programado ≠ not_completed

Not completed:

```text
sí existía algo planeado
pero no se cumplió
```

No programado:

```text
nunca estuvo agendado en esa fecha
```

---

# Vista mensual futura

Cuando un PlanItem aparezca en alguna fecha del mes pero no en otra:

la celda sin occurrence deberá poder representarse como:

```text
disabled
gris
sin símbolo
```

Esto se deriva de la AUSENCIA de occurrence.

No guardar un dato adicional para lograrlo.

---

# Modificación de una occurrence

Debe existir una operación equivalente a:

```js
updateOccurrence(
    occurrenceId,
    occurrenceDraft
)
```

---

# occurrenceDraft para edición individual

Debe contener únicamente campos editables:

```js
{
    date: "2026-08-21",
    startTime: "06:00",
    endTime: "08:00"
}
```

No permitir desde ese draft reemplazar:

```text
id
planItemId
status
```

salvo mediante operaciones específicas.

---

# Cambiar status

Debe existir una responsabilidad independiente equivalente a:

```js
setOccurrenceStatus(
    occurrenceId,
    status
)
```

o el ciclo multestado equivalente ya existente.

No modificar horario para cambiar status.

---

# Cambio de status y conflictos existentes

Cuando una occurrence cambia de:

```text
pending
```

a:

```text
not_completed
```

su horario deja de bloquear planificación inmediatamente.

Lo mismo para:

```text
cancelled
```

---

# Regresar de not_completed/cancelled

Si posteriormente una occurrence intenta volver a un status que bloquea
horario, por ejemplo:

```text
not_completed
→ pending
```

y actualmente existe otra occurrence superpuesta en ese espacio, el store NO
debe crear un estado temporal inválido.

Debe detectar el conflicto.

La transición debe:

* rechazarse;
* o requerir resolución explícita.

No debe producir dos occurrences bloqueantes superpuestas.

---

# Regla importante del ciclo multestado

El ciclo automático del MVP 03 deberá revisarse.

Antes era posible recorrer libremente:

pending
→ in_progress
→ completed
→ not_completed
→ cancelled
→ pending

Con el nuevo modelo:

volver desde un estado que libera horario hacia uno que lo bloquea puede
requerir validación temporal.

La UI no debe asumir que toda transición siempre es válida.

---

# Creación de PlanItem

El formulario no debe insertar directamente objetos completos.

Debe producir un draft equivalente a:

```js
{
    name: "Gym",

    kind: "activity",

    activityType: "periodic",

    generationConfig: {
        ...
    }
}
```

El store debe asignar:

```text
id
```

---

# Creación de Habit draft

Ejemplo:

```js
{
    name: "Cepillado de dientes",

    kind: "habit",

    habitType: "scheduled",

    generationConfig: {
        ...
    }
}
```

---

# Campos prohibidos en PlanItem draft

No aceptar directamente:

```text
id
occurrences
priority
statesByDate
position
```

---

# Creación de occurrence manual

El store puede recibir un draft equivalente a:

```js
{
    planItemId: "...",
    date: "2026-08-23",
    startTime: "14:00",
    endTime: "15:00"
}
```

Debe añadir:

```text
id
status = pending
```

después de validar.

---

# Reutilización futura de PlanItem

El modelo debe permitir crear una occurrence utilizando un PlanItem existente.

Ejemplo futuro:

```text
buscar:
Ponchadura de llanta
```

seleccionar PlanItem existente:

```js
planItemId: "..."
```

crear solamente una nueva occurrence.

No crear otro PlanItem.

La UI de autocompletado queda fuera de MVP 04.

---

# Edición solo esta fecha

Opera únicamente sobre:

```text
Occurrence
```

No modifica:

```text
PlanItem
generationConfig
otras occurrences
```

---

# Edición solo esta semana

El payload de interfaz puede representar conceptualmente:

```js
{
    scope: "week",
    occurrenceId: "...",
    changes: {...}
}
```

`scope` NO se almacena.

Es una instrucción de operación.

---

# Semana lógica

La semana utiliza:

```text
lunes → domingo
```

El rango se deriva desde:

```text
occurrence.date
```

No almacenar:

```text
weekNumber
```

en Occurrence.

---

# Edición de aquí en adelante

El payload puede representar:

```js
{
    scope: "future",
    effectiveDate: "2026-08-24",
    generationConfig: {...}
}
```

Estas propiedades representan una operación.

No se almacenan dentro de Occurrence.

---

# Regeneración futura

Cuando cambia generationConfig desde una fecha:

las occurrences futuras que puedan regenerarse deben filtrarse cuidadosamente.

En MVP 04 la candidata principal a regeneración automática es:

```text
status === pending
```

---

# Occurrences históricas

No eliminar automáticamente occurrences:

```text
completed
not_completed
cancelled
```

que ya representen historia.

Tampoco reescribir retrospectivamente fechas pasadas sin una acción explícita.

---

# in_progress

Una occurrence:

```text
in_progress
```

no debe eliminarse mediante regeneración automática.

Representa una ejecución actualmente iniciada.

---

# pending futuro

Una occurrence futura:

```text
pending
```

puede eliminarse y regenerarse si cambia la planificación futura.

---

# Pausa y reactivación

No se define todavía un campo persistente obligatorio como:

```js
isPaused
```

durante MVP 04.0.1.

La arquitectura debe permitir posteriormente:

```text
generationConfig = null
```

o una solución equivalente para detener generación sin borrar el PlanItem.

La interfaz de pausa queda pendiente.

---

# CancelledByOccurrenceId

NO agregar todavía:

```js
cancelledByOccurrenceId
```

al contrato obligatorio.

Debe registrarse en el documento de funciones futuras.

Puede incorporarse cuando se implemente resolución avanzada de overrides.

---

# Campos futuros prohibidos durante MVP 04

No agregar todavía:

```text
actualStartTime
actualEndTime

comments
notes

subactivities

quantity
unit
targetQuantity

createdAt
updatedAt

userId

cancelledByOccurrenceId

priority

weekNumber

month

year
```

salvo que otro documento normativo del mismo MVP los autorice
explícitamente.

---

# Datos iniciales

Los siete PlanItems del MVP 03 deben conservarse como base de demostración.

Propuesta normativa:

```text
1. Gym - Pecho
2. Cepillado de dientes
3. Meditar
4. Hybridge - Programación
5. Comida
6. CCNA / Estudio
7. Preparación del día siguiente
```

---

# Clasificación inicial

## Gym - Pecho

```js
kind: "activity"
activityType: "periodic"
```

---

## Cepillado de dientes

```js
kind: "habit"
habitType: "scheduled"
```

---

## Meditar

```js
kind: "habit"
habitType: "scheduled"
```

---

## Hybridge - Programación

```js
kind: "activity"
activityType: "anchor"
```

---

## Comida

```js
kind: "habit"
habitType: "scheduled"
```

---

## CCNA / Estudio

```js
kind: "activity"
activityType: "periodic"
```

---

## Preparación del día siguiente

```js
kind: "habit"
habitType: "scheduled"
```

---

# Configuración inicial propuesta

Los mocks deben demostrar que no todos los PlanItems existen todos los días.

Esto es necesario para validar MVP 04.0.2.

---

# Gym - Pecho

Ejemplo:

```js
generationConfig: {
    mode: "weekly",

    startDate: "2026-08-01",

    endDate: null,

    indefinite: true,

    weekdays: [1, 3, 5],

    defaultStartTime: "05:30",

    defaultEndTime: "07:15",

    weekdayTimeOverrides: {}
}
```

---

# Cepillado de dientes

```js
generationConfig: {
    mode: "weekly",

    startDate: "2026-08-01",

    endDate: null,

    indefinite: true,

    weekdays: [1, 2, 3, 4, 5, 6, 7],

    defaultStartTime: "07:50",

    defaultEndTime: "07:55",

    weekdayTimeOverrides: {}
}
```

---

# Meditar

```js
generationConfig: {
    mode: "weekly",

    startDate: "2026-08-01",

    endDate: null,

    indefinite: true,

    weekdays: [1, 2, 3, 4, 5, 6, 7],

    defaultStartTime: "08:00",

    defaultEndTime: "08:15",

    weekdayTimeOverrides: {}
}
```

---

# Hybridge - Programación

```js
generationConfig: {
    mode: "weekly",

    startDate: "2026-08-01",

    endDate: null,

    indefinite: true,

    weekdays: [1, 2, 3, 4, 5],

    defaultStartTime: "08:45",

    defaultEndTime: "09:45",

    weekdayTimeOverrides: {}
}
```

---

# Comida

```js
generationConfig: {
    mode: "weekly",

    startDate: "2026-08-01",

    endDate: null,

    indefinite: true,

    weekdays: [1, 2, 3, 4, 5, 6, 7],

    defaultStartTime: "14:00",

    defaultEndTime: "14:30",

    weekdayTimeOverrides: {}
}
```

---

# CCNA / Estudio

```js
generationConfig: {
    mode: "weekly",

    startDate: "2026-08-01",

    endDate: null,

    indefinite: true,

    weekdays: [1, 3, 5],

    defaultStartTime: "19:15",

    defaultEndTime: "20:15",

    weekdayTimeOverrides: {}
}
```

---

# Preparación del día siguiente

```js
generationConfig: {
    mode: "weekly",

    startDate: "2026-08-01",

    endDate: null,

    indefinite: true,

    weekdays: [1, 2, 3, 4, 5, 6, 7],

    defaultStartTime: "21:15",

    defaultEndTime: "21:45",

    weekdayTimeOverrides: {}
}
```

---

# Fechas de mock

No hardcodear la lógica general al año 2026.

Los valores anteriores son datos de demostración.

Las utilidades y algoritmos deben funcionar con cualquier:

```text
año
mes
fecha
```

válidos.

---

# Status de demostración

Después de materializar las occurrences iniciales pueden aplicarse algunos
status de demostración para comprobar visualmente el ciclo.

Ejemplo conceptual:

```js
const MOCK_STATUS_OVERRIDES = [
    {
        planItemId: "cepillado",
        date: "2026-08-20",
        status: "in_progress"
    },

    {
        planItemId: "meditar",
        date: "2026-08-20",
        status: "completed"
    },

    {
        planItemId: "hybridge-programacion",
        date: "2026-08-20",
        status: "not_completed"
    },

    {
        planItemId: "comida",
        date: "2026-08-20",
        status: "cancelled"
    }
];
```

Esta colección es solamente:

```text
fixture / bootstrap de demostración
```

No representa una entidad del dominio.

---

# Aplicación de status override

El bootstrap puede:

1. materializar occurrences;
2. localizar la occurrence correspondiente;
3. aplicar el status de demostración.

No crear statesByDate para preservar el comportamiento anterior.

---

# Si un override no encuentra occurrence

Debe ignorarse de forma segura o informar durante desarrollo.

No debe crear una occurrence ficticia únicamente para aplicar un status.

---

# Archivos sugeridos

La implementación puede evolucionar hacia una estructura equivalente a:

```text
js/
├── data/
│   ├── mock-plan-items.js
│   └── mock-status-overrides.js
│
├── domain/
│   ├── plan-item-classification.js
│   ├── occurrence-status.js
│   └── scheduling-priority.js
│
├── state/
│   └── planner-store.js
│
├── scheduling/
│   ├── materializer.js
│   └── conflict-detector.js
│
├── utils/
│   └── date-time.js
│
└── ...
```

Esta estructura es orientativa.

Codex no debe crear archivos únicamente por copiar este árbol.

Cada archivo nuevo debe tener una responsabilidad clara.

---

# Migración desde MVP 03

Modelo anterior:

```js
{
    id,
    name,
    recordKind,
    recordSubtype,
    position,
    plannedStartTime,
    plannedEndTime,
    statesByDate
}
```

Debe transformarse conceptualmente en:

```text
PlanItem
+
Occurrences
```

---

# Mapeo conceptual

```text
recordKind
→
kind
```

---

Para Activity:

```text
recordSubtype
→
activityType
```

---

Para Habit:

```text
recordSubtype
→
habitType
```

---

```text
position
→
ELIMINADO
```

Se deriva del orden visual.

---

```text
plannedStartTime
plannedEndTime
→
generationConfig
+
horario concreto de cada occurrence
```

---

```text
statesByDate
→
Occurrence.status
```

---

# Regla de migración

No conservar simultáneamente:

```text
statesByDate
```

y:

```text
occurrence.status
```

como dos fuentes de verdad.

Después de la migración:

```text
Occurrence.status
```

es la única fuente válida del estado por fecha.

---

# Regla de consistencia

No debe existir simultáneamente:

```text
PlanItem con horario global mutable
```

y:

```text
Occurrences con horarios propios
```

como dos fuentes autoritativas del calendario.

`generationConfig` sirve para GENERAR futuro.

La agenda visible se obtiene desde:

```text
Occurrences
```

---

# Regla central del contrato

Para saber qué está agendado en una fecha:

consultar Occurrences.

NO consultar directamente generationConfig.

generationConfig responde:

qué se debe generar en el futuro.

Occurrences responden:

qué existe realmente en la agenda materializada.

---

# Resumen

Fuente canónica:

```text
planItems[]
occurrences[]
```

PlanItem:

```text
identidad
clasificación
generationConfig
```

Occurrence:

```text
identidad
planItemId
date
startTime
endTime
status
```

generationConfig:

```text
algoritmo actual para generar futuro
```

La agenda:

```text
se consulta desde Occurrences
```

No desde generationConfig.

---

# Principio final

La generación automatiza.

La occurrence materializa.

Después de materializada:

la occurrence es independiente.

Este contrato debe permitir que Vatos con Sesos automatice rutinas durante
meses o años sin impedir que el usuario modifique una fecha concreta cuando la
vida real cambie el plan.
