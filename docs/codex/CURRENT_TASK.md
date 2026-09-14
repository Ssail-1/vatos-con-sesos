# CURRENT TASK

## MVP 05.6.1 — Canonical multi-slot model + local frontend/domain

### Documento normativo

La especificación global de esta feature está en:

`docs/codex/gestor_de_habitos/planeacion/MVP_05_6/MULTI_SLOT_SCHEDULING.md`

Ese documento define la semántica completa de multi-slot.

Este `CURRENT_TASK.md` define únicamente la fase activa:

```text
MVP 05.6.1
Canonical multi-slot model + frontend/domain local
```

---

# 1. Objetivo

Introducir en el frontend y dominio JavaScript el modelo canónico
multi-slot.

Un mismo `PlanItem` debe poder tener múltiples horarios que generen
múltiples occurrences en una misma fecha.

Ejemplo:

```text
Uber — lunes

08:00–11:00
14:00–17:00
20:00–22:00
```

En esta fase se modifica únicamente:

```text
frontend
dominio JavaScript
formularios
store local
materializador JavaScript
validaciones locales
tests frontend
```

NO se modifica todavía:

```text
PostgreSQL
backend Flask
repositorios Python
materializador Python
API persistente
```

---

# 2. Principio principal

La interfaz puede conservar conceptos cómodos de captura:

```text
horario default
override por weekday
"Una fecha"
"Agregar horario"
```

pero esos conceptos NO son necesariamente la representación canónica.

La fuente de verdad del dominio debe ser:

```text
GenerationSlots explícitos
```

---

# 3. Modos canónicos

Continúan existiendo únicamente:

```text
weekly
interval_days
manual_dates
```

`single_date` NO vuelve a existir.

La opción visual:

```text
Una fecha
```

continúa disponible y genera:

```text
manual_dates
```

---

# 4. Identidad de GenerationSlot

Cada `GenerationSlot` tiene UUID estable.

El UUID nace en frontend cuando el usuario crea el slot.

Usar:

```js
crypto.randomUUID()
```

o una abstracción/fallback ya existente en el proyecto si corresponde.

Reglas:

```text
crear slot
→ UUID nuevo

editar el mismo slot
→ conservar UUID

eliminar slot
→ la identidad desaparece de la configuración

crear después otro horario igual
→ UUID nuevo
```

Nunca derivar identidad de:

```text
hora
fecha
weekday
índice de array
nombre
```

---

# 5. Decisión arquitectónica de IDs

Esta decisión está cerrada.

El frontend genera:

```text
GenerationSlot.id
```

Posteriormente, en MVP 05.6.3, el backend deberá:

```text
validar ese UUID
preservarlo
persistirlo
devolverlo sin reemplazarlo
```

NO implementar:

```text
temporary slot id
client id → server id remapping
backend-generated replacement slot UUID
```

En esta fase no se modifica backend.

---

# 6. Contrato canónico — weekly

El estado canónico debe utilizar:

```js
{
  mode: "weekly",
  startDate: "YYYY-MM-DD",
  endDate: "YYYY-MM-DD" | null,
  indefinite: boolean,

  slots: [
    {
      id: "UUID",
      isoWeekday: 1,
      startTime: "08:00",
      endTime: "11:00"
    },
    {
      id: "UUID",
      isoWeekday: 1,
      startTime: "14:00",
      endTime: "17:00"
    }
  ],

  excludedDates?: ["YYYY-MM-DD"],
  stoppedFromDate?: "YYYY-MM-DD"
}
```

En el dominio canónico dejan de ser fuente de verdad:

```text
weekdays
defaultStartTime
defaultEndTime
weekdayTimeOverrides
```

Estos conceptos pueden seguir existiendo dentro del formulario/draft
para conservar la UX actual.

---

# 7. Contrato canónico — interval_days

Debe utilizar:

```js
{
  mode: "interval_days",
  startDate: "YYYY-MM-DD",
  endDate: "YYYY-MM-DD" | null,
  indefinite: boolean,
  intervalDays: number,

  slots: [
    {
      id: "UUID",
      startTime: "08:00",
      endTime: "08:05"
    },
    {
      id: "UUID",
      startTime: "14:00",
      endTime: "14:05"
    }
  ],

  excludedDates?: ["YYYY-MM-DD"],
  stoppedFromDate?: "YYYY-MM-DD"
}
```

En el dominio canónico dejan de ser fuente de verdad:

```text
defaultStartTime
defaultEndTime
```

El formulario puede seguir usándolos como comodidad de captura si resulta
útil.

---

# 8. Contrato canónico — manual_dates

Debe utilizar:

```js
{
  mode: "manual_dates",

  entries: [
    {
      id: "UUID",
      date: "YYYY-MM-DD",
      startTime: "08:00",
      endTime: "11:00"
    },
    {
      id: "UUID",
      date: "YYYY-MM-DD",
      startTime: "14:00",
      endTime: "17:00"
    }
  ],

  stoppedFromDate?: "YYYY-MM-DD"
}
```

Debe permitirse:

```text
misma fecha
+
varios horarios
```

si no se solapan.

Una sola fecha continúa siendo simplemente:

```text
manual_dates
```

con una o varias entries en esa fecha.

---

# 9. Occurrence canónica

Se introduce:

```text
sourceGenerationSlotId
```

Forma conceptual:

```js
{
  id,
  planItemId,
  sourceGenerationSlotId,
  date,
  startTime,
  endTime,
  status,
  statusContext?
}
```

`sourceGenerationSlotId`:

```text
puede ser null/opcional
identifica el GenerationSlot que originó la occurrence
NO es fuente actual de su fecha/hora
```

La occurrence conserva siempre sus propios:

```text
date
startTime
endTime
status
```

No confundir:

```text
sourceGenerationSlotId
```

con:

```text
statusContext.sourceOccurrenceId
```

Son conceptos distintos.

---

# 10. Occurrences ad-hoc

Una occurrence que no proviene de una regla recurrente puede utilizar:

```text
sourceGenerationSlotId = null
```

No debe inventarse un GenerationSlot únicamente para darle procedencia.

---

# 11. Materialización weekly

Actualizar `materializer.js`.

Por cada fecha candidata:

```text
obtener isoWeekday
        ↓
buscar todos los slots de ese weekday
        ↓
crear una occurrence por slot
```

Ejemplo:

```text
lunes

S1 08:00–11:00
S2 14:00–17:00
S3 20:00–22:00
```

debe producir tres occurrences.

Cada una debe conservar:

```text
sourceGenerationSlotId = slot.id
```

---

# 12. Materialización interval_days

Por cada fecha válida según:

```text
startDate
+
intervalDays
```

crear una occurrence por cada slot.

Ejemplo:

```text
S1 08:00–08:05
S2 14:00–14:05
S3 22:00–22:05
```

produce tres occurrences por fecha válida.

---

# 13. Materialización manual_dates

Cada entry produce una occurrence.

Ejemplo:

```text
2026-09-15

S1 08:00–11:00
S2 14:00–17:00
```

produce dos occurrences para el mismo PlanItem y fecha.

Cada occurrence conserva:

```text
sourceGenerationSlotId = entry.id
```

---

# 14. Idempotencia local

Un `GenerationSlot` genera como máximo una occurrence por fecha.

La identidad lógica de materialización es:

```text
sourceGenerationSlotId
+
date
```

El materializador debe evitar duplicar esa combinación.

NO utilizar como identidad única:

```text
planItemId + date
```

porque un PlanItem puede tener múltiples occurrences válidas el mismo día.

---

# 15. Validación interna de slots

Los slots que aplican a la misma fecha no pueden solaparse.

Los intervalos son semiabiertos.

Válido:

```text
08:00–11:00
11:00–14:00
```

Inválido:

```text
08:00–11:00
10:30–14:00
```

Validar:

```text
weekly
→ slots del mismo isoWeekday

interval_days
→ todos los slots

manual_dates
→ entries de la misma fecha
```

La validación interna debe ocurrir antes de materializar.

---

# 16. UI weekly

Preservar la experiencia actual:

```text
seleccionar weekdays
horario default
override principal por weekday
```

Agregar capacidad multi-slot.

Control preferido:

```text
Agregar horario
```

Ejemplo:

```text
LUNES

08:00–11:00

14:00–17:00
20:00–22:00

[ + Agregar horario ]
```

Debe ser posible dentro del formulario:

```text
agregar
editar
eliminar
```

horarios adicionales.

---

# 17. Default y overrides

`defaultStartTime`, `defaultEndTime` y los overrides existentes pueden
seguir utilizándose dentro del draft del formulario.

Ejemplo:

```text
default
08:00–11:00

lunes
override principal 09:00–12:00

horarios adicionales
14:00–17:00
20:00–22:00
```

Al confirmar, el formulario debe normalizar todo a:

```text
slots[]
```

PostgreSQL no debe necesitar posteriormente conocer si un slot nació como:

```text
default
override
extra
```

---

# 18. Comportamiento del default

Conservar el comportamiento actual.

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

puede crear el horario principal equivalente para todos esos weekdays.

Los horarios adicionales NO deben copiarse automáticamente a todos los
weekdays únicamente porque exista un default.

Deben agregarse explícitamente salvo que exista una acción futura de
copiado deliberado.

---

# 19. Reconstrucción del formulario

Cuando se edite un PlanItem que ya utiliza el contrato canónico multi-slot:

```text
NO perder slots
NO perder IDs
```

Para weekly:

1. agrupar slots por `isoWeekday`;
2. ordenar los slots del grupo determinísticamente;
3. elegir un horario principal para presentarlo en la UI actual;
4. presentar los restantes como horarios adicionales;
5. conservar cada `slot.id`;
6. al guardar, reconstruir el conjunto completo sin pérdida.

La noción visual de:

```text
default
```

no tiene que persistirse como dato de dominio.

---

# 20. UI interval_days

Preservar el formulario actual de intervalo.

Agregar:

```text
Agregar horario
```

Ejemplo:

```text
Cada 1 día

08:00–08:05
14:00–14:05
22:00–22:05
```

Todos los horarios se normalizan a:

```text
slots[]
```

---

# 21. UI manual_dates

Preservar la experiencia actual de:

```text
agregar fecha
Una fecha
```

Debe permitirse más de un horario en la misma fecha.

Ejemplo:

```text
2026-09-15

08:00–11:00
14:00–17:00
```

Cada entry debe tener y conservar su UUID propio.

---

# 22. Identidad estable al editar

Ejemplo:

```text
slot S2
14:00–17:00
```

si el usuario modifica el mismo horario lógico a:

```text
15:00–18:00
```

debe permanecer:

```text
slot S2
```

No crear un UUID nuevo solo porque cambió el horario.

---

# 23. Eliminar y recrear

Si:

```text
slot S2
14:00–17:00
```

es eliminado del formulario, S2 deja de formar parte de la configuración.

Si posteriormente el usuario agrega:

```text
14:00–17:00
```

de nuevo:

```text
debe crearse S9
```

o cualquier UUID nuevo.

No resucitar S2 por igualdad de valores.

---

# 24. Integridad temporal

No rediseñar las reglas existentes de:

```text
HISTORY_EDIT_WINDOW_DAYS
frozen history
reconciliation
statuses
```

Actualmente:

```text
currentDate
→ editable

ayer
→ editable

antes de ayer o anterior
→ frozen
```

Multi-slot no autoriza reescribir historia.

---

# 25. Prioridad

No modificar el modelo actual:

```text
NORMAL       = 100
EVENT        = 200
UNEXPECTED   = 300
```

Cada occurrence candidata generada por un slot se evalúa individualmente
con las reglas existentes.

---

# 26. Conflictos

No sustituir la lógica de conflictos existente.

Cada occurrence producida por cada slot debe pasar por ella.

Además, los slots de la propia configuración deben ser internamente
válidos antes de materializar.

Los intervalos contiguos siguen permitidos.

---

# 27. excludedDates global

La semántica actual de:

```text
excludedDates
```

permanece.

Significa:

```text
no generar NINGÚN slot del PlanItem en esa fecha
```

La exclusión individual:

```text
slot + date
```

pertenece a una fase posterior y NO se implementa persistentemente en
05.6.1.

---

# 28. stoppedFromDate

La semántica actual se conserva.

```text
candidateDate >= stoppedFromDate
→ no generar slots del PlanItem
```

No introducir `stoppedFromDate` por slot.

---

# 29. Alcance de edición en MVP 05.6.1

Esta fase trabaja:

```text
modelo canónico
draft/formulario
materialización local
identidad local
validaciones
tests
```

NO implementar todavía la semántica persistente completa de:

```text
eliminar un slot solo este día
slot excluded dates
modificar slot future en PostgreSQL
Apply Future persistente multi-slot
DELETE/PATCH de slots
```

Eso corresponde a:

```text
MVP 05.6.4
```

---

# 30. Apply week / Apply future existentes

No rediseñar estas operaciones en esta fase.

Adaptar únicamente lo estrictamente necesario para que el nuevo modelo
multi-slot:

```text
no pierda slots
no pierda IDs
no reduzca silenciosamente N slots a 1
```

Si algún flujo requiere decisiones que pertenecen a MVP 05.6.4:

```text
detenerse
preservar integridad
reportarlo
```

No inventar una semántica permanente.

---

# 31. Compatibilidad temporal con backend

Durante MVP 05.6.1 existe deliberadamente esta diferencia:

```text
Frontend/domain
→ nuevo contrato multi-slot

Backend/PostgreSQL
→ contrato MVP 05.5
```

Esto es esperado.

El frontend todavía NO está conectado al backend persistente.

NO modificar backend para hacer coincidir ambos contratos en esta fase.

La compatibilidad se restaurará en:

```text
MVP 05.6.2
→ PostgreSQL / migración 003

MVP 05.6.3
→ backend read/create multi-slot + paridad JS/Python
```

---

# 32. Áreas permitidas

Puede modificarse lo necesario dentro del frontend del módulo:

```text
modules/gestor_de_habitos/
```

Áreas esperables:

```text
index.html
js/app.js
js/state/
js/scheduling/
js/views/
tests/
```

No asumir que todos deben modificarse.

Modificar solamente lo necesario.

---

# 33. Áreas prohibidas en esta fase

NO modificar:

```text
modules/gestor_de_habitos/backend/
modules/gestor_de_habitos/db/
```

NO modificar:

```text
001_initial_schema.sql
002_fix_occurrence_status_context.sql
```

NO crear todavía:

```text
003_multi_slot_scheduling.sql
```

NO modificar:

```text
vcs_dev
```

---

# 34. No implementar todavía

Fuera de alcance:

```text
Flask multi-slot
Python materializer multi-slot
GET planner-state multi-slot
POST multi-slot
PATCH
DELETE persistente
PostgreSQL slot tables
slot exclusions persistentes
auth
multiusuario
Supabase
deployment
notificaciones
timezone por usuario
nuevo sistema de estadísticas
```

---

# 35. Pruebas obligatorias

Agregar/actualizar cobertura como mínimo para:

```text
weekly con 1 slot

weekly con varios slots en el mismo weekday

weekly con distintos slots según weekday

interval_days con múltiples slots

manual_dates con múltiples entries en la misma fecha

"Una fecha" sigue produciendo manual_dates

slots contiguos permitidos

slots solapados rechazados

UUID de slot generado

UUID de slot estable tras editar

UUID nuevo tras eliminar/recrear

sourceGenerationSlotId correcto

varias occurrences mismo PlanItem/misma fecha

idempotencia por sourceGenerationSlotId + date

excludedDates global

stoppedFromDate

conflictos existentes

prioridades existentes

temporal integrity

deletion management

recurrence editor

formularios
```

Ejecutar todas las suites frontend relevantes.

---

# 36. Regresión backend

Ejecutar las pruebas backend existentes como regresión.

El backend NO debe modificarse para adaptarse al nuevo contrato en esta
fase.

Si las pruebas backend existentes continúan pasando:

```text
reportarlo
```

Si aparece una incompatibilidad únicamente porque el frontend ya utiliza
el nuevo contrato pero ambos todavía no están integrados:

```text
reportarla
```

No resolverla modificando backend.

---

# 37. Verificación visual

Comprobar al menos:

```text
1440 × 900
390 × 844
```

Validar:

```text
múltiples horarios legibles
Agregar horario usable
edición/eliminación dentro del draft
sin overflow
dark/gold preservado
responsive preservado
labels/control accesibles
default/override sigue entendible
Una fecha sigue funcionando
```

---

# 38. Caso principal — Uber

Debe poder representarse localmente UN solo PlanItem:

```text
Uber
```

con:

```text
lunes
08:00–11:00
14:00–17:00
20:00–22:00

martes
08:00–11:00
14:00–17:00
20:00–22:00

miércoles
08:00–11:00
14:00–17:00
20:00–22:00

jueves
08:00–11:00
14:00–17:00
20:00–22:00

viernes
08:00–11:00
14:00–17:00
20:00–22:00

sábado
08:00–21:00

domingo
08:00–21:00
```

sin crear varios PlanItems.

Cada horario genera su occurrence independiente.

---

# 39. Caso — Medicamento

Debe poder representarse:

```text
Medicamento

interval_days = 1

08:00–08:05
14:00–14:05
22:00–22:05
```

Todos los slots aplican en cada fecha válida.

---

# 40. Caso — Manual dates

Debe permitirse:

```text
2026-09-15

08:00–11:00
14:00–17:00
```

para un solo PlanItem.

Cada entry tiene UUID independiente.

---

# 41. Invariantes de esta fase

Al terminar MVP 05.6.1 debe cumplirse:

```text
Un PlanItem puede tener múltiples slots.

Los slots tienen UUID estable.

El UUID nace en frontend.

weekly utiliza slots explícitos.

interval_days utiliza slots explícitos.

manual_dates utiliza entries con UUID.

Una occurrence puede recordar su sourceGenerationSlotId.

Una occurrence sigue teniendo datos propios.

Un PlanItem puede tener múltiples occurrences el mismo día.

No se utiliza planItemId + date como unicidad.

Un slot genera como máximo una occurrence por fecha.

default/override son UX, no dominio canónico.

single_date no existe.

La persistencia todavía NO está adaptada.

Backend y PostgreSQL permanecen sin cambios.
```

---

# 42. Git

Codex NO debe:

```text
commit
push
merge
cambiar de rama
```

El usuario controla Git.

---

# 43. Reporte requerido

Al terminar, reportar:

1. archivos modificados;
2. contrato canónico final de `weekly`;
3. contrato canónico final de `interval_days`;
4. contrato canónico final de `manual_dates`;
5. cómo se generan los UUID de slots;
6. cómo se conservan durante edición;
7. cómo default/override se normaliza a slots;
8. cómo funciona `Agregar horario`;
9. cómo se reconstruye un formulario desde slots;
10. cómo materializa cada modo;
11. cómo funciona la idempotencia;
12. tests ejecutados;
13. resultados;
14. verificación visual;
15. flujos que quedaron deliberadamente pendientes para MVP 05.6.4;
16. cualquier incompatibilidad o riesgo detectado.

No hacer commit.