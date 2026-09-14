
# MVP 05.6 — Multi-slot Scheduling

## 1. Objetivo

Extender el Gestor de hábitos para permitir que cualquier `PlanItem`
tenga múltiples apariciones en un mismo día, cada una con su propio
intervalo horario.

Ejemplo:

```text
Trabajo / Uber — lunes

08:00–11:00
14:00–17:00
20:00–22:00
```

Otro ejemplo:

```text
Medicamento — cada día

08:00–08:05
14:00–14:05
22:00–22:05
```

La capacidad multi-slot es general.

No depende de:

- `kind`
- `activityType`
- `habitType`

Todos los PlanItems pueden tener uno o varios horarios cuando su modo
de generación lo permita.

---

# 2. Motivación

Hasta MVP 05.5, los modos recurrentes `weekly` e `interval_days`
representan esencialmente un solo horario para cada fecha generada.

Esto resulta insuficiente para casos reales donde el mismo PlanItem debe
ocurrir varias veces durante el mismo día.

No se debe resolver creando múltiples PlanItems con el mismo nombre.

Ejemplo incorrecto:

```text
Uber mañana
Uber tarde
Uber noche
```

cuando conceptualmente todos representan:

```text
PlanItem: Uber
```

con varios horarios.

La solución debe mantener una sola identidad de PlanItem y modelar
separadamente los horarios que generan sus occurrences.

---

# 3. Nueva entidad: GenerationSlot

Se introduce el concepto:

```text
GenerationSlot
```

Un `GenerationSlot` representa una instrucción horaria estable capaz de
generar occurrences.

Ejemplo:

```text
PlanItem: Uber

Slot S1
lunes
08:00–11:00

Slot S2
lunes
14:00–17:00

Slot S3
lunes
20:00–22:00
```

Un slot NO es una occurrence.

La diferencia es:

```text
GenerationSlot
→ regla/instrucción de generación

Occurrence
→ aparición concreta materializada en el calendario
```

Ejemplo:

```text
Slot S2
lunes 14:00–17:00
        │
        ├── occurrence 2026-09-14 14:00–17:00
        ├── occurrence 2026-09-21 14:00–17:00
        └── occurrence 2026-09-28 14:00–17:00
```

---

# 4. Identidad de los slots

Cada `GenerationSlot` debe tener un UUID propio.

```text
generation_slot.id
```

El ID:

- no deriva del horario;
- no deriva de la fecha;
- no deriva del weekday;
- no deriva del nombre del PlanItem;
- no deriva de la posición dentro de un array;
- identifica al horario lógico.

Ejemplo:

```text
S2
lunes 14:00–17:00
```

Si ese mismo horario lógico se modifica a:

```text
S2
lunes 15:00–18:00
```

puede conservar el mismo ID.

Si el slot se elimina y posteriormente se agrega nuevamente un horario,
aunque tenga exactamente los mismos valores, debe generarse un UUID nuevo.

```text
identidad != igualdad de valores
```

---

# 5. Quién genera los UUID de los slots

Los `GenerationSlot` adquieren identidad desde el momento en que son
creados en el frontend.

El frontend genera:

```text
GenerationSlot.id
```

mediante UUID v4.

Preferentemente:

```js
crypto.randomUUID()
```

o una abstracción/fallback ya existente en el proyecto si corresponde.

El backend debe posteriormente:

- validar que el valor recibido sea un UUID válido;
- preservar exactamente el UUID recibido;
- persistir esa misma identidad;
- devolver esa misma identidad;
- no reemplazar silenciosamente IDs de slots;
- no implementar un remapeo client-id → server-id.

Flujo esperado:

```text
Usuario agrega horario
        ↓
Frontend genera UUID S1
        ↓
GenerationSlot S1
        ↓
POST
        ↓
Backend valida S1
        ↓
PostgreSQL persiste S1
        ↓
GET
        ↓
continúa siendo S1
```

El backend continúa generando durante la creación persistente:

```text
PlanItem.id
Occurrence.id
```

salvo que otra decisión arquitectónica futura modifique explícitamente
esa política.

---

# 6. Relación con Occurrence

Las occurrences pueden conservar la procedencia del slot que las generó.

Nueva propiedad conceptual:

```text
sourceGenerationSlotId
```

Representación SQL futura:

```text
occurrences.source_generation_slot_id
```

Esta relación significa:

> Esta occurrence fue materializada a partir de este GenerationSlot.

NO significa:

> La occurrence obtiene actualmente su fecha u horario desde el slot.

Una occurrence sigue siendo independiente después de materializarse y
conserva sus propios:

```text
date
startTime
endTime
status
```

Ejemplo:

```text
Slot S2
lunes 14:00–17:00

Occurrence O27
2026-09-21
14:00–17:00
sourceGenerationSlotId = S2
```

Si se edita únicamente esa occurrence:

```text
Occurrence O27
2026-09-21
15:00–18:00
sourceGenerationSlotId = S2
```

el slot puede continuar siendo:

```text
S2
lunes 14:00–17:00
```

La occurrence fue corregida individualmente, pero conserva su procedencia.

---

# 7. Independencia histórica

La occurrence nunca debe depender del slot para conservar su información
histórica.

La FK futura debe ser nullable.

Conceptualmente:

```sql
FOREIGN KEY (source_generation_slot_id)
REFERENCES generation_slots(id)
ON DELETE SET NULL
```

Si un slot se elimina:

```text
GenerationSlot S2
→ eliminado
```

las occurrences históricas deben permanecer.

Ejemplo:

```text
2026-09-01 14:00–17:00 completed
2026-09-08 14:00–17:00 completed
```

pueden quedar con:

```text
source_generation_slot_id = NULL
```

pero conservan:

```text
date
start_time
end_time
status
```

La relación slot → occurrence es de procedencia, no de dependencia.

---

# 8. Modelo relacional propuesto

El núcleo queda conceptualmente:

```text
                         ┌────────────────────┐
                         │     plan_items     │
                         │────────────────────│
                         │ PK id              │
                         │ name               │
                         │ kind               │
                         │ subtype            │
                         │ created_at         │
                         └─────────┬──────────┘
                                   │
                  ┌────────────────┴────────────────┐
                  │                                 │
                  │ 1:1                             │ 1:N
                  ▼                                 ▼
       ┌──────────────────────┐          ┌────────────────────────┐
       │ generation_configs   │          │      occurrences       │
       │──────────────────────│          │────────────────────────│
       │ PK/FK plan_item_id   │          │ PK id                  │
       │ mode                 │          │ FK plan_item_id        │
       │ start_date           │          │ FK? source_generation_ │
       │ end_date             │          │     slot_id            │
       │ indefinite           │          │ occurrence_date        │
       │ interval_days        │          │ start_time             │
       │ stopped_from_date    │          │ end_time               │
       └──────────┬───────────┘          │ status                 │
                  │                      │ status_reason          │
                  │ 1:N                  │ source_occurrence_id   │
                  ▼                      └────────────────────────┘
       ┌──────────────────────┐
       │   generation_slots   │
       │──────────────────────│
       │ PK id                │
       │ FK plan_item_id      │
       │ start_time           │
       │ end_time             │
       └──────────┬───────────┘
                  │
             ┌────┴────────────┐
             │                 │
             ▼                 ▼
┌───────────────────────┐  ┌───────────────────────┐
│ generation_slot_      │  │ generation_slot_      │
│ weekdays              │  │ dates                 │
│───────────────────────│  │───────────────────────│
│ PK/FK slot_id         │  │ PK/FK slot_id        │
│ iso_weekday           │  │ entry_date            │
└───────────────────────┘  └───────────────────────┘
```

Además:

```text
generation_configs
        │
        └──── generation_excluded_dates
              → excluye TODO el PlanItem ese día


generation_slots
        │
        └──── generation_slot_excluded_dates
              → excluye SOLO ese slot ese día
```

---

# 9. Tabla generation_slots

Propuesta conceptual:

```text
generation_slots

id              UUID PK
plan_item_id    UUID NOT NULL FK
start_time      TIME NOT NULL
end_time        TIME NOT NULL
```

Debe cumplir:

```text
start_time < end_time
```

`plan_item_id` debe asociar el slot con la configuración del PlanItem.

Conceptualmente puede referenciar:

```text
generation_configs(plan_item_id)
```

No debe existir una restricción como:

```text
UNIQUE(plan_item_id, start_time, end_time)
```

porque el mismo intervalo puede utilizarse en distintos weekdays o fechas.

---

# 10. Weekly

El modo `weekly` utiliza:

```text
generation_slots
+
generation_slot_weekdays
```

Ejemplo:

```text
generation_slots

S1 | Uber | 08:00 | 11:00
S2 | Uber | 14:00 | 17:00
S3 | Uber | 20:00 | 22:00
S4 | Uber | 08:00 | 21:00
```

```text
generation_slot_weekdays

S1 | 1
S2 | 1
S3 | 1
S4 | 6
```

ISO weekday:

```text
1 = lunes
2 = martes
3 = miércoles
4 = jueves
5 = viernes
6 = sábado
7 = domingo
```

Cada slot weekly pertenece a exactamente un weekday.

Una configuración weekly debe contener al menos un slot.

---

# 11. Interval days

`interval_days` utiliza:

```text
generation_configs.interval_days
+
generation_slots
```

No requiere una tabla hija adicional.

Ejemplo:

```text
generation_config

mode = interval_days
start_date = 2026-09-01
interval_days = 1
```

```text
generation_slots

S1 | 08:00–08:05
S2 | 14:00–14:05
S3 | 22:00–22:05
```

Cada fecha producida por la regla recibe todos los slots activos.

Ejemplo:

```text
Sep 01
├── 08:00–08:05
├── 14:00–14:05
└── 22:00–22:05

Sep 02
├── 08:00–08:05
├── 14:00–14:05
└── 22:00–22:05
```

---

# 12. Manual dates

`manual_dates` utiliza:

```text
generation_slots
+
generation_slot_dates
```

Ejemplo:

```text
S1 | 08:00–11:00
S2 | 14:00–17:00
S3 | 20:00–22:00
```

```text
generation_slot_dates

S1 | 2026-09-15
S2 | 2026-09-15
S3 | 2026-09-15
```

Esto permite varias apariciones del mismo PlanItem en el mismo día.

La interfaz visual “Una fecha” sigue existiendo.

Sin embargo, internamente:

```text
Una fecha
→ manual_dates
→ uno o varios slots con la misma entry_date
```

`single_date` NO vuelve a existir como modo de dominio.

---

# 13. Contrato canónico del frontend

## Weekly

La representación canónica deja de depender de:

```text
weekdays
defaultStartTime
defaultEndTime
weekdayTimeOverrides
```

Esos conceptos pueden seguir existiendo en el formulario como ayuda de UI,
pero no son la fuente persistente de verdad.

El dominio utiliza slots explícitos:

```js
{
  mode: "weekly",
  startDate: "2026-09-14",
  endDate: null,
  indefinite: true,

  slots: [
    {
      id: "uuid-s1",
      isoWeekday: 1,
      startTime: "08:00",
      endTime: "11:00"
    },
    {
      id: "uuid-s2",
      isoWeekday: 1,
      startTime: "14:00",
      endTime: "17:00"
    },
    {
      id: "uuid-s3",
      isoWeekday: 1,
      startTime: "20:00",
      endTime: "22:00"
    },
    {
      id: "uuid-s4",
      isoWeekday: 6,
      startTime: "08:00",
      endTime: "21:00"
    }
  ],

  excludedDates: [],
  stoppedFromDate: null
}
```

---

## Interval days

```js
{
  mode: "interval_days",
  startDate: "2026-09-14",
  endDate: null,
  indefinite: true,
  intervalDays: 1,

  slots: [
    {
      id: "uuid-s1",
      startTime: "08:00",
      endTime: "08:05"
    },
    {
      id: "uuid-s2",
      startTime: "14:00",
      endTime: "14:05"
    }
  ],

  excludedDates: [],
  stoppedFromDate: null
}
```

---

## Manual dates

```js
{
  mode: "manual_dates",

  entries: [
    {
      id: "uuid-s1",
      date: "2026-09-15",
      startTime: "08:00",
      endTime: "11:00"
    },
    {
      id: "uuid-s2",
      date: "2026-09-15",
      startTime: "14:00",
      endTime: "17:00"
    }
  ],

  stoppedFromDate: null
}
```

Una única entry sigue siendo:

```text
manual_dates
```

No existe `single_date`.

---

# 14. Generación de IDs en frontend

Cuando el usuario crea un nuevo slot:

```js
crypto.randomUUID()
```

produce su identidad.

Ejemplo:

```text
Agregar horario
        ↓
slot.id = 16e7...
```

Reglas:

```text
crear slot
→ nuevo UUID

editar horario
→ conservar UUID

editar weekday manteniendo la misma identidad lógica
→ puede conservar UUID

eliminar slot
→ esa identidad deja de existir en la configuración

crear otro posteriormente
→ UUID nuevo
```

Nunca generar identidad a partir de:

```text
hora
fecha
weekday
índice del array
nombre
```

---

# 15. Occurrence canónica

Una occurrence generada desde un slot puede quedar:

```js
{
  id: "occurrence-uuid",
  planItemId: "plan-item-uuid",
  sourceGenerationSlotId: "slot-uuid",
  date: "2026-09-21",
  startTime: "14:00",
  endTime: "17:00",
  status: "pending"
}
```

`sourceGenerationSlotId` puede ser `null` o estar ausente cuando la
occurrence sea ad-hoc y no provenga de una regla de generación.

No confundir:

```text
sourceGenerationSlotId
```

con:

```text
statusContext.sourceOccurrenceId
```

Son conceptos completamente distintos.

---

# 16. UI weekly existente

La experiencia visual existente debe preservarse.

Actualmente el formulario permite:

```text
seleccionar weekdays
+
definir un horario default
+
modificar el horario principal de un weekday
```

Esto debe seguir funcionando.

Además se agrega, por weekday, la capacidad:

```text
+ Agregar horario
```

Ejemplo:

```text
LUNES

08:00 – 11:00

14:00 – 17:00     editar | eliminar
20:00 – 22:00     editar | eliminar

[ + Agregar horario ]
```

El botón vuelve a estar disponible después de agregar cada slot.

Nombre preferido:

```text
Agregar horario
```

---

# 17. Default y overrides como modelo de formulario

`defaultStartTime`, `defaultEndTime` y los overrides por weekday pueden
seguir utilizándose dentro del draft/formulario.

NO continúan siendo el modelo canónico persistente.

Ejemplo:

```text
UI

default:
08:00–11:00

lunes:
override principal 09:00–12:00
extra 14:00–17:00
extra 20:00–22:00
```

al confirmar se normaliza a:

```text
generation slots explícitos
```

La BD no necesita saber cuál horario era:

```text
default
override
extra
```

Para el dominio persistente todos son:

```text
GenerationSlots
```

---

# 18. Copiado del horario default

El comportamiento actual de horario default debe conservarse como ayuda
de captura.

Ejemplo:

```text
lunes
martes
miércoles
jueves
viernes

default:
08:00–11:00
```

puede producir inicialmente:

```text
lunes     08:00–11:00
martes    08:00–11:00
miércoles 08:00–11:00
jueves    08:00–11:00
viernes   08:00–11:00
```

Después el usuario puede personalizar cada weekday.

No se debe obligar a copiar automáticamente todos los horarios adicionales
a todos los días.

Los horarios adicionales son explícitos salvo que la UI futura ofrezca
intencionalmente una acción de copiado.

---

# 19. Reconstrucción del formulario al editar

Cuando se cargue una configuración persistida, el frontend debe poder
reconstruir el formulario sin pérdida de información.

Para weekly:

1. agrupar slots por `isoWeekday`;
2. ordenar cada grupo por hora;
3. elegir determinísticamente un horario principal para presentarlo en
   la UI existente;
4. presentar los demás como horarios adicionales;
5. conservar internamente el `slot.id` de cada horario existente.

El concepto visual "default" pertenece a la presentación.

La fuente de verdad sigue siendo:

```text
slots[]
```

No se debe persistir información únicamente para recordar qué slot fue
visualmente llamado "default".

---

# 20. UI interval_days

La experiencia actual de intervalo debe preservarse.

Además debe permitir:

```text
+ Agregar horario
```

Ejemplo:

```text
Cada 1 día

08:00–08:05
14:00–14:05
22:00–22:05
```

Todos estos horarios se normalizan a:

```text
slots[]
```

y todos aplican a cada fecha producida por la regla de intervalo.

---

# 21. UI manual_dates

Debe mantenerse la experiencia actual de agregar fechas.

Ahora debe permitirse agregar más de un horario en la misma fecha.

Ejemplo:

```text
2026-09-15

08:00–11:00
14:00–17:00
```

Cada entry debe conservar su UUID propio.

La opción visual:

```text
Una fecha
```

continúa existiendo.

Internamente continúa siendo:

```text
manual_dates
```

---

# 22. Validación interna de slots

Los slots de un mismo PlanItem que aplican a la misma fecha no deben
solaparse.

Los intervalos se consideran semiabiertos.

Ejemplo válido:

```text
08:00–11:00
11:00–14:00
```

Ejemplo inválido:

```text
08:00–11:00
10:30–14:00
```

La validación aplica a:

```text
weekly
→ slots del mismo isoWeekday

interval_days
→ todos los slots

manual_dates
→ entries de la misma fecha
```

---

# 23. Materialización weekly

Por cada fecha candidata:

```text
weekday de la fecha
        ↓
buscar todos los slots de ese isoWeekday
        ↓
generar una occurrence por slot
```

Ejemplo:

```text
lunes

S1 08:00–11:00
S2 14:00–17:00
S3 20:00–22:00
```

produce:

```text
Occurrence O1
sourceGenerationSlotId = S1

Occurrence O2
sourceGenerationSlotId = S2

Occurrence O3
sourceGenerationSlotId = S3
```

---

# 24. Materialización interval_days

Por cada fecha generada mediante:

```text
startDate + intervalDays
```

se crea una occurrence por cada slot.

Ejemplo:

```text
S1 08:00–08:05
S2 14:00–14:05
S3 22:00–22:05
```

produce tres occurrences en cada fecha válida.

---

# 25. Materialización manual_dates

Cada entry produce exactamente una occurrence en su fecha.

Ejemplo:

```text
Entry S1
2026-09-15 08:00–11:00

Entry S2
2026-09-15 14:00–17:00
```

produce:

```text
2026-09-15 08:00–11:00
2026-09-15 14:00–17:00
```

para el mismo PlanItem.

---

# 26. Idempotencia de materialización

La materialización no debe crear duplicados.

Un slot genera como máximo una occurrence por fecha.

La identidad lógica de una materialización será:

```text
sourceGenerationSlotId
+
date
```

Debe evaluarse en PostgreSQL una restricción/índice futuro equivalente a:

```text
UNIQUE(source_generation_slot_id, occurrence_date)
```

cuando:

```text
source_generation_slot_id IS NOT NULL
```

Esto NO equivale a:

```text
UNIQUE(plan_item_id, occurrence_date)
```

La segunda está prohibida porque un mismo PlanItem puede tener múltiples
occurrences válidas el mismo día.

---

# 27. Occurrence modificada individualmente

Si una occurrence generada desde un slot cambia únicamente de horario:

```text
slot:
14:00–17:00

occurrence concreta:
15:00–18:00
```

la occurrence conserva:

```text
sourceGenerationSlotId
```

Esto permite recordar su procedencia aunque sus valores actuales ya no
coincidan exactamente con el slot.

Además evita que el materializador la considere una occurrence
completamente distinta.

---

# 28. Exclusión completa de un día

Continúa existiendo:

```text
generation_excluded_dates
```

Su significado es:

> Este PlanItem completo no debe generarse en esta fecha.

Ejemplo:

```text
Uber
2026-12-25
```

resultado:

```text
ningún slot de Uber se genera ese día
```

Aplica principalmente a:

```text
weekly
interval_days
```

---

# 29. Exclusión de un solo slot

Se introduce:

```text
generation_slot_excluded_dates
```

Estructura conceptual:

```text
slot_id
excluded_date
```

PK compuesta:

```text
(slot_id, excluded_date)
```

Ejemplo:

```text
Uber — 2026-09-21

S1 08:00–11:00    generar
S2 14:00–17:00    excluir
S3 20:00–22:00    generar
```

se representa:

```text
S2 | 2026-09-21
```

Esto evita excluir accidentalmente todo el PlanItem.

---

# 30. Eliminar solo este día

Cuando se elimina una occurrence concreta:

## Occurrence proveniente de weekly/interval_days

Debe poder:

```text
identificar sourceGenerationSlotId
+
registrar slot exclusion para selectedDate
+
eliminar/suprimir la occurrence según las reglas temporales
```

Esto evita que el materializador la vuelva a crear.

## Manual date

Una entry manual es una instrucción explícita para una fecha concreta.

Eliminarla implica eliminar su manual-date slot correspondiente cuando
la política temporal/status lo permita.

## Occurrence ad-hoc

Puede tener:

```text
sourceGenerationSlotId = null
```

y gestionarse mediante las reglas de occurrences existentes.

La implementación persistente completa de estas operaciones pertenece a
una fase posterior de MVP 05.6.

---

# 31. Editar solo este día

Modificar únicamente una occurrence:

```text
NO modifica generation_slots
```

Una edición de hora:

```text
mantiene sourceGenerationSlotId
```

y modifica únicamente los valores propios de la occurrence.

Ejemplo:

```text
Slot S2:
14:00–17:00
```

pero:

```text
Occurrence O27:
15:00–18:00
sourceGenerationSlotId = S2
```

Toda operación debe revalidar conflictos.

---

# 32. Aplicar solo esta semana

La semántica existente se conserva.

No modifica necesariamente la configuración recurrente general.

Puede permitir cambios sobre occurrences de esa semana:

```text
agregar
modificar
eliminar
```

Una occurrence agregada únicamente para esa semana puede existir con:

```text
sourceGenerationSlotId = null
```

Si se elimina una occurrence generada desde un slot, será necesario
registrar la exclusión slot+date apropiada para impedir rematerialización.

---

# 33. Aplicar de aquí en adelante

Esta operación sí modifica la configuración vigente.

Debe poder reestructurar:

```text
weekdays
cantidad de slots
horarios
intervalo
fechas manuales
```

desde una `effectiveDate`.

Filosofía:

```text
pasado
→ occurrences son autoridad histórica

effectiveDate en adelante
→ nueva configuración vigente
```

No se introduce todavía un sistema completo de versionado histórico de
ScheduleRules.

---

# 34. Identidad durante Apply Future

Cuando un slot existente únicamente cambia su horario y continúa
representando el mismo horario lógico:

```text
conservar slot.id
```

Ejemplo:

```text
S2
lunes 14:00–17:00
```

pasa a:

```text
S2
lunes 15:00–18:00
```

Si aparece un horario nuevo:

```text
crear nuevo slot.id
```

Si un horario desaparece:

```text
eliminar ese slot de la configuración vigente
```

Si cambia de forma fundamental su significado, por ejemplo se reemplaza
un slot de un weekday por otro concepto distinto, es preferible:

```text
slot anterior eliminado
+
slot nuevo
```

en lugar de reutilizar identidad ambiguamente.

---

# 35. Eliminación de un slot de aquí en adelante

Cuando un slot deja de existir en la configuración vigente:

```text
future pending occurrences derivadas del slot
→ eliminar/regenerar según la operación

non-pending/history
→ preservar

slot
→ eliminar
```

Las occurrences históricas no se eliminan.

Debido a:

```text
ON DELETE SET NULL
```

pueden conservar:

```text
source_generation_slot_id = NULL
```

No se implementa versionado histórico completo de slots en MVP 05.6.

---

# 36. stoppedFromDate

`stoppedFromDate` continúa siendo un límite del PlanItem/configuración,
no de un slot individual.

Significa:

```text
candidateDate >= stoppedFromDate
→ ningún slot del PlanItem debe generar
```

Eliminar solamente un slot de aquí en adelante NO utiliza
`stoppedFromDate`.

Se modifica el conjunto de slots.

---

# 37. Integridad temporal

Todas las reglas existentes siguen vigentes.

La ventana editable continúa definida por:

```text
HISTORY_EDIT_WINDOW_DAYS
```

Actualmente:

```text
currentDate
→ editable

currentDate - 1
→ editable

currentDate - 2 o anterior
→ frozen
```

Los slots no permiten reescribir historia.

Una modificación de configuración afecta planificación futura.

Las occurrences históricas son la autoridad.

---

# 38. Limpieza de exclusiones

Las exclusiones:

```text
generation_excluded_dates
generation_slot_excluded_dates
```

pueden limpiarse oportunistamente cuando su fecha ya está congelada,
siguiendo la filosofía actual.

El materializador nunca debe reconstruir planificación nueva dentro de
historia congelada.

La limpieza debe ser idempotente.

No depende de timers/cron.

---

# 39. Conflictos

Cada occurrence candidata generada desde cada slot debe pasar por las
reglas de conflicto existentes.

Intervalos:

```text
newStart < existingEnd
AND
newEnd > existingStart
```

Los intervalos contiguos están permitidos.

Los múltiples slots del MISMO PlanItem también deben validarse entre sí.

Ejemplo inválido:

```text
Uber

08:00–11:00
10:00–12:00
```

Debe rechazarse antes de persistir/materializar.

---

# 40. Prioridades

Multi-slot NO modifica el modelo de prioridad existente.

Se mantienen:

```text
NORMAL       = 100
EVENT        = 200
UNEXPECTED   = 300
```

Cada occurrence materializada se evalúa individualmente.

Un override de prioridad continúa trabajando sobre occurrences, no sobre
el PlanItem completo.

---

# 41. Operaciones atómicas

La creación o modificación estructural persistente de un PlanItem debe
ser atómica.

Ejemplo futuro:

```text
BEGIN

plan_item
generation_config
generation_slots
slot weekday/date details
exclusions
occurrences

COMMIT
```

Ante cualquier fallo:

```text
ROLLBACK
```

No puede existir un PlanItem nuevo parcialmente persistido.

---

# 42. Migración PostgreSQL

La implementación persistente debe introducir una nueva migración:

```text
003_multi_slot_scheduling.sql
```

NO modificar:

```text
001_initial_schema.sql
002_fix_occurrence_status_context.sql
```

Las migraciones anteriores son historia inmutable.

La migración `003` debe ser transaccional.

---

# 43. Transformación de datos existentes

La migración debe conservar los datos preexistentes cuando existan.

## Existing weekly

Actualmente:

```text
generation_configs.default_start_time
generation_configs.default_end_time

generation_weekdays.override_start_time
generation_weekdays.override_end_time
```

Para cada weekday existente debe crearse un `GenerationSlot`.

Horario:

```text
si hay override
→ usar override

si no
→ usar default
```

Resultado:

```text
un slot por weekday existente
```

## Existing interval_days

Crear un `GenerationSlot` utilizando:

```text
default_start_time
default_end_time
```

## Existing manual_dates

Cada fila actual de:

```text
generation_date_entries
```

se convierte en:

```text
GenerationSlot
+
generation_slot_dates
```

Cuando sea viable se puede reutilizar el UUID existente de la entry como
ID del nuevo slot para conservar identidad.

---

# 44. Backfill de sourceGenerationSlotId

Las occurrences existentes pueden asociarse a un slot durante la migración
solo cuando la procedencia pueda determinarse de forma inequívoca.

Ejemplo seguro:

```text
mismo PlanItem
misma fecha generada
mismo intervalo
único slot posible
```

Si existe ambigüedad:

```text
source_generation_slot_id = NULL
```

No se debe inventar procedencia.

---

# 45. Elementos SQL antiguos a retirar

Después de migrar correctamente el modelo, el diseño nuevo debe dejar de
depender de:

```text
generation_configs.default_start_time
generation_configs.default_end_time

generation_weekdays.override_start_time
generation_weekdays.override_end_time
```

La antigua estructura de:

```text
generation_weekdays
generation_date_entries
```

será sustituida por el modelo de slots.

Las constraints de `generation_configs` deben actualizarse para no exigir
default times.

---

# 46. Constraints relacionales nuevas

## generation_slots

```text
PK id
FK plan_item_id → generation_configs(plan_item_id)

CHECK start_time < end_time
```

## generation_slot_weekdays

```text
PK/FK slot_id → generation_slots(id)
iso_weekday NOT NULL

CHECK iso_weekday BETWEEN 1 AND 7
```

## generation_slot_dates

```text
PK/FK slot_id → generation_slots(id)
entry_date NOT NULL
```

## generation_slot_excluded_dates

```text
PK (slot_id, excluded_date)
FK slot_id → generation_slots(id)
```

Las tablas dependientes del slot pueden utilizar:

```text
ON DELETE CASCADE
```

porque no tienen sentido sin su slot.

Occurrences deben utilizar:

```text
ON DELETE SET NULL
```

para:

```text
source_generation_slot_id
```

---

# 47. Invariantes por mode

Estas invariantes pertenecen principalmente al dominio/backend porque
dependen de varias tablas.

## weekly

```text
>= 1 GenerationSlot

cada slot:
→ exactamente un generation_slot_weekdays

ningún slot:
→ generation_slot_dates
```

## interval_days

```text
>= 1 GenerationSlot

ningún slot:
→ generation_slot_weekdays
→ generation_slot_dates
```

## manual_dates

```text
>= 1 GenerationSlot

cada slot:
→ exactamente un generation_slot_dates

ningún slot:
→ generation_slot_weekdays
```

No introducir triggers únicamente para imponer estas reglas en MVP 05.6.

---

# 48. API persistente futura

Después de las fases persistentes de MVP 05.6:

```text
GET /api/planner-state
```

debe devolver slots con sus IDs.

La creación:

```text
POST /api/plan-items
```

debe aceptar el contrato normalizado multi-slot.

En creación:

```text
GenerationSlot IDs
→ generados en frontend
→ enviados al backend
→ validados
→ preservados
→ persistidos
```

En lectura:

```text
GenerationSlot IDs
→ devueltos sin reemplazarlos
```

El frontend podrá posteriormente referenciar un slot específico por UUID.

---

# 49. Paridad JavaScript ↔ Python

Actualmente existe materialización en:

```text
JavaScript
Python
```

La implementación multi-slot debe mantener pruebas directas de paridad.

Los mismos fixtures deben producir las mismas occurrences en ambos
runtimes.

Casos mínimos:

```text
weekly con 1 slot

weekly con varios slots mismo weekday

weekly con distintos slots por weekday

interval_days con varios slots

manual_dates con varias entries mismo día

slots contiguos

slots solapados inválidos

global excluded date

slot excluded date

stoppedFromDate

sourceGenerationSlotId
```

---

# 50. UI responsive

La incorporación de múltiples horarios no debe romper el diseño aprobado.

Debe validarse al menos:

```text
desktop
mobile
```

Referencias mínimas:

```text
1440 × 900
390 × 844
```

Las filas adicionales deben ser legibles y editables.

La UI debe conservar:

```text
tema dark/gold
jerarquía visual existente
responsive
accesibilidad por teclado
labels accesibles
```

---

# 51. No crear restricciones artificiales por subtipo

En MVP 05.6 NO se limita multi-slot según:

```text
anchor
periodic
event
unexpected
scheduled
```

Todos pueden utilizar la capacidad.

Si posteriormente aparece una regla real de negocio que deba restringir
un subtipo, se agregará explícitamente.

No anticipar restricciones sin evidencia.

---

# 52. Fuera de alcance global de MVP 05.6

No implementar por iniciativa propia:

```text
autenticación
multiusuario
Supabase
deployment
versionado histórico completo de ScheduleRules
soft-delete completo de GenerationSlots
cron
timers
timezone por usuario
estadísticas nuevas
recordatorios/notificaciones
```

Los concerns de producción existentes continúan documentados en:

```text
PRODUCTION_CONCERNS.md
```

---

# 53. Implementación por fases

MVP 05.6 se implementará en varias etapas.

Este documento define el comportamiento global.

`CURRENT_TASK.md` define únicamente la fase activa.

Orden previsto:

```text
MVP 05.6.1
Canonical multi-slot model + frontend/domain local

MVP 05.6.2
PostgreSQL migration 003 + relational multi-slot model

MVP 05.6.3
Backend read/create multi-slot + JS/Python parity

MVP 05.6.4
Persisted slot editing/deletion semantics

MVP 05.6.5
Integral verification before frontend/backend persistence integration
```

La subdivisión puede ajustarse si durante la implementación aparece una
razón técnica real.

No implementar fases futuras por iniciativa propia.

---

# 54. Caso de aceptación — Uber weekly

Debe poder existir UN solo PlanItem:

```text
Uber
```

con:

```text
lunes–viernes

08:00–11:00
14:00–17:00
20:00–22:00

sábado–domingo

08:00–21:00
```

sin crear varios PlanItems.

El materializador debe producir una occurrence independiente por horario.

---

# 55. Caso de aceptación — Medicamento

Debe poder representarse:

```text
Medicamento

cada 1 día

08:00–08:05
14:00–14:05
22:00–22:05
```

mediante:

```text
interval_days
+
3 GenerationSlots
```

---

# 56. Caso de aceptación — Manual date

Debe permitir:

```text
2026-09-15

08:00–11:00
14:00–17:00
```

para el mismo PlanItem.

Cada horario tiene identidad propia.

---

# 57. Caso de aceptación — Editar una occurrence

Debe poder modificarse solamente:

```text
2026-09-21
14:00–17:00
```

a:

```text
15:00–18:00
```

sin alterar las demás occurrences producidas por el slot.

La occurrence conserva:

```text
sourceGenerationSlotId
```

---

# 58. Caso de aceptación — Eliminar un slot solo un día

Debe poder eliminarse:

```text
2026-09-21
14:00–17:00
```

sin eliminar:

```text
08:00–11:00
20:00–22:00
```

del mismo PlanItem y misma fecha.

Esto requerirá una exclusión:

```text
slot + date
```

---

# 59. Caso de aceptación — Apply week

Debe poder modificarse únicamente la semana seleccionada sin alterar
automáticamente la regla recurrente general.

Las modificaciones deben respetar:

```text
IDs
history
statuses
conflicts
priority
```

---

# 60. Caso de aceptación — Apply future

Debe poder reestructurarse el conjunto de slots desde una fecha efectiva.

Ejemplo:

Antes:

```text
lunes

08:00–11:00
14:00–17:00
20:00–22:00
```

Después, desde una fecha determinada:

```text
lunes

09:00–12:00
15:00–18:00
```

El pasado permanece intacto.

---

# 61. Invariantes finales

```text
Un PlanItem puede tener N GenerationSlots.

Un GenerationSlot pertenece a una sola generationConfig.

Un GenerationSlot tiene UUID estable.

El UUID del GenerationSlot nace en frontend.

Backend y PostgreSQL preservan ese UUID.

Un GenerationSlot puede generar N occurrences.

Un GenerationSlot genera como máximo una occurrence por fecha.

Una occurrence pertenece a un PlanItem.

Una occurrence puede recordar qué slot la generó.

Una occurrence sigue siendo independiente después de materializarse.

Un mismo PlanItem puede tener múltiples occurrences el mismo día.

No existe UNIQUE(plan_item_id, occurrence_date).

El pasado materializado no se reconstruye desde la configuración actual.

Los cambios futuros no reescriben historia.

La UI puede utilizar default/override como herramientas de captura.

El dominio y PostgreSQL persisten slots explícitos.

Una sola fecha continúa siendo manual_dates.

single_date no vuelve a existir.

Todos los PlanItems pueden utilizar multi-slot.
```

---

# 62. Filosofía

La configuración responde:

> ¿Qué debe generar el planner?

Los GenerationSlots responden:

> ¿En qué horarios debe ocurrir?

Las occurrences responden:

> ¿Qué existe realmente en el calendario?

La identidad del slot permite saber:

> ¿Qué regla generó esta occurrence?

sin convertir esa regla en la fuente actual de verdad de la occurrence.

La configuración puede cambiar.

Los slots pueden cambiar.

Las occurrences históricas deben sobrevivir.

El pasado registrado no debe reescribirse.
