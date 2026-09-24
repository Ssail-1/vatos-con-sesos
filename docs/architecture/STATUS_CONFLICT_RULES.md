# Status and conflict rules

## 1. Occurrence segments, aggregate status and temporal occupation

Una `Occurrence` representa una instancia lógica de una actividad.

La occurrence conserva un intervalo general:

```text
start_time
end_time
```

Este intervalo representa la ventana general de la occurrence.

Sin embargo, una occurrence puede desarrollarse en uno o varios intervalos
continuos internos llamados:

```text
OccurrenceSegment
```

Ejemplo:

```text
Occurrence: Estudiar

general:
13:00–17:00

segments:
13:00–14:00
14:30–17:00
```

Sigue siendo una sola occurrence de Estudiar.

No son dos occurrences independientes.

---

### 1.1 Purpose of the general interval

Los campos generales:

```text
Occurrence.start_time
Occurrence.end_time
```

representan:

```text
la ventana general de planificación o registro de la occurrence
```

No representan necesariamente ocupación continua.

Ejemplo:

```text
Occurrence:
13:00–17:00

Segments:
13:00–14:00
14:30–17:00
```

El intervalo:

```text
14:00–14:30
```

no está ocupado por esta occurrence aunque se encuentre dentro de su rango
general.

El rango general permite conservar información como:

```text
inicio general
final general
ventana planeada
límites permitidos para los segmentos
```

---

### 1.2 OccurrenceSegment

Cada segment representa un intervalo continuo perteneciente a una occurrence.

Conceptualmente:

```text
OccurrenceSegment
├── id
├── occurrence_id
├── start_time
├── end_time
└── status
```

Cada segment tiene su propio status.

Los statuses disponibles son:

```text
pending
in_progress
completed
not_completed
not_finished
cancelled
```

---

### 1.3 Every occurrence has at least one segment

Toda occurrence debe tener:

```text
1..N segments
```

Nunca:

```text
0 segments
```

Una occurrence nueva normalmente nace con:

```text
Segment 1
start_time = occurrence.start_time
end_time   = occurrence.end_time
```

Ejemplo:

```text
Occurrence:
08:00–10:00

Segment 1:
08:00–10:00
pending
```

---

### 1.4 Segments belong only to their occurrence

Los segments describen cómo se desarrolla una occurrence concreta.

No pertenecen al:

```text
PlanItem
GenerationConfig
GenerationSlot
```

por defecto.

Ejemplo:

```text
GenerationSlot:
13:00–17:00
```

genera:

```text
Occurrence Monday:
13:00–17:00

Segment 1:
13:00–17:00
```

Si esa occurrence termina siendo:

```text
13:00–14:00
14:30–17:00
```

la occurrence de la siguiente semana NO hereda automáticamente esa
segmentación.

La siguiente occurrence vuelve a nacer normalmente como:

```text
13:00–17:00
```

con un único segment.

---

### 1.5 Planned recurring segmentation is explicit

La segmentación producida durante la ejecución o corrección de una occurrence:

```text
NO se hereda por defecto
```

Si en el futuro el usuario desea que una segmentación se repita:

```text
debe convertirla explícitamente en planificación recurrente
```

Esto podrá implementarse posteriormente mediante una plantilla asociada al
slot correspondiente.

Conceptualmente:

```text
GenerationSlot
13:00–17:00

planned segment template:
13:00–14:00
14:30–17:00
```

No implementar herencia automática de segmentación accidental.

---

### 1.6 Segment boundaries

Todo segment debe cumplir:

```text
segment.start_time < segment.end_time
```

Además:

```text
occurrence.start_time <= segment.start_time
segment.end_time <= occurrence.end_time
```

Ejemplo válido:

```text
Occurrence:
13:00–17:00

Segment:
14:00–16:00
```

Ejemplo inválido:

```text
Occurrence:
13:00–17:00

Segment:
12:30–14:00
```

Ejemplo inválido:

```text
Segment:
16:00–18:00
```

---

### 1.7 Sibling segments cannot overlap

Dos segments pertenecientes a la misma occurrence no pueden superponerse.

Inválido:

```text
S1:
13:00–15:00

S2:
14:30–16:00
```

Válido:

```text
S1:
13:00–14:00

S2:
14:30–16:00
```

Los segments pueden ser adyacentes:

```text
13:00–14:00
14:00–15:00
```

aunque una futura normalización puede decidir fusionar segmentos contiguos
equivalentes.

---

### 1.8 Segment order

El orden visual de los segments se deriva cronológicamente mediante:

```text
start_time
end_time
```

Los nombres:

```text
Seg 1
Seg 2
Seg 3
```

son ordinales de UI.

No representan IDs persistidos.

Internamente cada segment debe conservar su propio identificador estable.

---

### 1.9 Segment status is the editable status

El usuario modifica statuses de segments.

El status general de la occurrence:

```text
NO se edita independientemente
```

Se deriva de sus segments.

Para una occurrence con un único segment:

```text
Occurrence
└── Segment 1
```

el control visible puede parecer el control normal de status de la
occurrence.

Sin embargo, técnicamente:

```text
usuario cambia Segment 1.status
↓
backend recalcula occurrence.status
```

Como existe un único segment:

```text
Segment 1.status
==
Occurrence.status
```

---

### 1.10 Aggregate occurrence status

`Occurrence.status` es un aggregate derivado de:

```text
todos sus segments
```

No debe existir una operación que modifique directamente:

```text
Occurrence.status
```

sin actualizar coherentemente sus segments.

Si físicamente la columna permanece en PostgreSQL:

```text
occurrences.status
```

debe tratarse como aggregate materializado.

Cada mutación de segments debe:

```text
1. modificar segments
2. recalcular aggregate
3. persistir todo dentro de la misma transacción
```

---

### 1.11 Aggregate when all segments have the same status

Si todos los segments tienen exactamente el mismo status:

```text
Occurrence.status = ese mismo status
```

Ejemplos:

```text
pending + pending
→ pending
```

```text
completed + completed
→ completed
```

```text
not_finished + not_finished
→ not_finished
```

```text
cancelled + cancelled
→ cancelled
```

---

### 1.12 Aggregate status while editable

Mientras la occurrence se encuentre en una zona donde pueden existir estados
activos, utilizar las siguientes reglas.

Primero:

```text
si todos los segments tienen el mismo status
→ utilizar ese status
```

Si los statuses son diferentes:

```text
si existe al menos un:
completed
in_progress
not_finished

→ aggregate = in_progress
```

Esto representa una occurrence que:

```text
ya comenzó
o tiene parte realizada
pero todavía tiene una composición mixta
```

Ejemplos:

```text
completed + pending
→ in_progress
```

```text
completed + cancelled
→ in_progress
```

```text
not_finished + pending
→ in_progress
```

```text
in_progress + cancelled
→ in_progress
```

Si no existe ningún:

```text
completed
in_progress
not_finished
```

pero existe:

```text
pending
```

entonces:

```text
aggregate = pending
```

Ejemplo:

```text
pending + cancelled
→ pending
```

Si no existe ninguno de los anteriores pero existe:

```text
not_completed
```

entonces:

```text
aggregate = not_completed
```

Ejemplo:

```text
not_completed + cancelled
→ not_completed
```

Si todos son:

```text
cancelled
```

entonces:

```text
aggregate = cancelled
```

---

### 1.13 Reconciliation when today becomes previous editable day

Cuando una fecha deja de ser el día actual:

```text
TODAY
→
PREVIOUS_EDITABLE_DAY
```

reconciliar cada segment:

```text
pending
→ not_completed
```

```text
in_progress
→ not_finished
```

Los demás statuses permanecen:

```text
completed
not_completed
not_finished
cancelled
```

Después:

```text
recalcular Occurrence.status
```

La fecha continúa siendo editable después de esta reconciliación.

---

### 1.14 Historical aggregate after reconciliation

Una vez que ya no existen:

```text
pending
in_progress
```

utilizar:

```text
si todos los segments tienen el mismo status
→ ese mismo status
```

Si los statuses son diferentes:

```text
si existe completed
o existe not_finished
→ aggregate = not_finished
```

Ejemplos:

```text
completed + not_finished
→ not_finished
```

```text
completed + not_completed
→ not_finished
```

```text
completed + cancelled
→ not_finished
```

```text
not_finished + cancelled
→ not_finished
```

Si no existe:

```text
completed
not_finished
```

pero existe:

```text
not_completed
```

entonces:

```text
aggregate = not_completed
```

Ejemplo:

```text
not_completed + cancelled
→ not_completed
```

Si todos son:

```text
cancelled
```

entonces:

```text
aggregate = cancelled
```

---

### 1.15 Final reconciliation before frozen history

Antes de que una fecha pase de:

```text
PREVIOUS_EDITABLE_DAY
→
FROZEN_HISTORY
```

VCS debe volver a ejecutar reconciliation.

Esto debe ser idempotente.

Volver a comprobar:

```text
pending
→ not_completed

in_progress
→ not_finished
```

aunque normalmente estos estados ya no deberían existir.

Después:

```text
recalcular aggregates
validar integridad
congelar la fecha
```

Esta segunda comprobación protege contra:

```text
datos inconsistentes
sesiones abiertas
bugs
correcciones parciales
estados transitorios inesperados
```

---

### 1.16 Temporal occupation belongs to segments

La ocupación temporal se determina utilizando:

```text
Segment.status
```

Statuses que ocupan tiempo:

```text
pending
in_progress
completed
not_finished
```

Statuses que NO ocupan tiempo:

```text
cancelled
not_completed
```

---

### 1.17 Conflict detection uses segments

Los conflictos temporales deben calcularse contra:

```text
segments que ocupan tiempo
```

No contra todo el rango general de la occurrence.

Ejemplo:

```text
Occurrence:
13:00–17:00

Segments:
13:00–14:00
14:30–17:00
```

Una nueva occurrence:

```text
14:00–14:30
```

NO entra en conflicto con esos segments.

El rango general:

```text
13:00–17:00
```

no debe utilizarse como un intervalo continuo para bloquear ese hueco.

---

### 1.18 Occurrence aggregate does not determine occupation by itself

Una occurrence puede tener:

```text
aggregate = in_progress
```

pero contener algunos segments:

```text
cancelled
not_completed
```

que no ocupan tiempo.

Por tanto:

```text
Occurrence.status
```

sirve como resumen.

La detección real de conflictos debe revisar:

```text
Segment.status
+
Segment.start_time
+
Segment.end_time
```

---

### 1.19 Duration

La duración compacta de una occurrence se calcula como:

```text
SUM(segment.end_time - segment.start_time)
```

de TODOS sus segments.

El status del segment no modifica este cálculo.

Ejemplo:

```text
S1:
13:00–14:00 completed
= 1h

S2:
14:30–15:30 cancelled
= 1h

S3:
16:00–17:00 not_completed
= 1h
```

Duración mostrada:

```text
3h
```

Esta duración representa:

```text
duración estructural actual de los segments
```

No representa todavía:

```text
tiempo efectivo
tiempo productivo
tiempo realmente completado
```

Las métricas estadísticas se definirán posteriormente.

---

### 1.20 Moving an occurrence without changing its duration

Si una occurrence cambia de horario pero conserva exactamente la misma
duración general, trasladar todos sus segments mediante el mismo delta.

Ejemplo:

```text
Occurrence:
08:00–12:00

S1:
08:00–10:00

S2:
10:30–12:00
```

Se mueve a:

```text
13:00–17:00
```

Delta:

```text
+5h
```

Resultado:

```text
S1:
13:00–15:00

S2:
15:30–17:00
```

Esto preserva:

```text
duraciones
distancias
huecos
estructura relativa
```

---

### 1.21 Resizing the general interval

Si la duración general cambia:

```text
08:00–12:00
→
08:00–11:00
```

o:

```text
08:00–12:00
→
08:00–14:00
```

VCS NO debe intentar escalar automáticamente los segments.

El editor debe permitir dos caminos.

#### Adjust segments manually

El usuario modifica primero el rango general y después corrige sus segments.

La mutación no puede persistirse hasta que todos cumplan:

```text
occurrence.start_time <= segment.start_time
segment.end_time <= occurrence.end_time
```

#### Reset segmentation

La UI debe ofrecer una acción equivalente a:

```text
[Restablecer segmentación]
```

Al confirmar:

```text
1. eliminar segments actuales
2. crear un nuevo Segment 1
3. Segment 1.start_time = occurrence.start_time
4. Segment 1.end_time   = occurrence.end_time
5. Segment 1.status hereda el aggregate anterior
6. recalcular aggregate
```

Después deben ejecutarse las validaciones normales del dominio.

---

### 1.22 Reset does not guess segment distribution

Cuando se utiliza:

```text
Restablecer segmentación
```

VCS no intenta:

```text
estirar segmentos
comprimir segmentos
redistribuir huecos
adivinar proporciones
```

El usuario podrá volver a crear la segmentación que desee.

---

### 1.23 Segment selection in UI

La selección debe distinguir:

```text
selectedOccurrenceId
selectedSegmentId
```

Si el usuario selecciona un segment:

```text
toda la occurrence se muestra visualmente seleccionada
```

pero:

```text
el segment específico recibe mayor énfasis
```

Esto permite conocer simultáneamente:

```text
qué occurrence está activa
qué segment exacto está siendo editado
```

---

### 1.24 Expanded occurrence UI

Una occurrence compacta puede verse conceptualmente como:

```text
▸ Estudiar | Inicio 13:00 | Final 17:00 | Duración 3h30 | Estado
```

Al expandir:

```text
▾ Estudiar | Inicio 13:00 | Final 17:00 | Duración 3h30 | Estado

    Seg 1 · Estudiar | 13:00–14:00 | 1h   | completed
    Seg 2 · Estudiar | 14:30–15:30 | 1h   | completed
    Seg 3 · Estudiar | 16:00–17:00 | ...  | ...
```

Los horarios mostrados deben respetar siempre los límites reales de la
occurrence.

Solo la fila principal muestra:

```text
▾
```

Los segments aparecen indentados.

Visualmente deben sentirse como filas temporales completas, no como simples
líneas descriptivas.

---

### 1.25 Single-segment UI

Si una occurrence solo tiene un segment:

```text
Occurrence
└── Segment 1
```

la UI puede continuar viéndose prácticamente como antes.

El control de status visible actúa como proxy de:

```text
Segment 1.status
```

No es necesario obligar al usuario a expandir una occurrence trivial.

---

### 1.26 Multi-segment aggregate control

Cuando existen múltiples segments:

```text
Occurrence.status
```

es principalmente informativo.

Los controls editables pertenecen a:

```text
cada Segment.status
```

Las acciones globales sobre toda la occurrence deberán ser explícitas y
definirse como operaciones bulk.

---

### 1.27 Principle

El modelo debe distinguir siempre:

```text
Occurrence
= instancia lógica y ventana general

OccurrenceSegment
= intervalos concretos dentro de esa instancia

Occurrence.status
= resumen derivado

Segment.status
= estado editable y operativo
```

Principio rector:

> VCS planifica occurrences, pero puede registrar y corregir cómo se
> desarrollaron mediante segments sin convertir cada interrupción en una
> occurrence independiente.

No permitir:

occurrence.status = completed

si:

occurrence.endDateTime > currentDateTime

Si el usuario afirma que ya la completó:

- ofrecer ajustar fecha/horario;
- validar conflictos del nuevo intervalo;
- después permitir completed.

Ejemplo:

Occurrence:
08:00–10:00

Current time:
09:20

No permitir completed todavía.

El usuario puede corregir:

08:00–09:15
completed

## 2. Editable temporal zones

La capacidad de modificar una occurrence depende de la zona temporal en la
que se encuentre.

Las zonas son:

```text
FUTURE
CURRENT_DAY
PREVIOUS_EDITABLE_DAY
FROZEN_HISTORY
```

Principio general:

> Mientras el día sea editable, VCS protege la integridad temporal pero
> permite corregir la interpretación de lo ocurrido.

La ventana temporal editable actual contempla:

```text
currentDay
+
previous editable day
```

La historia anterior queda congelada.

---

### 2.1 Future

Una occurrence futura todavía representa planificación, no historia.

Estados permitidos:

```text
pending
cancelled
```

Transición conceptual:

```text
pending ↔ cancelled
```

No permitir en futuro:

```text
in_progress
completed
not_completed
not_finished
```

porque todavía no existe una realidad ocurrida que justifique esos estados.

---

### 2.2 Future editing

Mientras una occurrence sea futura, el usuario puede modificar:

```text
date
startTime
endTime
```

siempre que la operación respete:

```text
integridad temporal
reglas de planificación
conflictos
prioridades
```

También puede eliminarla según las reglas existentes.

Una occurrence futura cancelada puede volver a:

```text
pending
```

si el usuario decide reactivarla y su horario sigue siendo válido.

---

### 2.3 Current day

Durante el día actual, el usuario tiene máxima libertad de corrección.

Puede:

```text
crear
editar
mover
eliminar
cambiar status
```

mientras se respeten las reglas de integridad temporal.

Los seis estados del dominio pueden existir durante el día actual:

```text
pending
in_progress
completed
not_completed
not_finished
cancelled
```

---

### 2.4 Current day status progression

No imponer una matriz rígida de transiciones entre todos los statuses.

El flujo normal puede continuar utilizando el comportamiento existente del
planner.

Ejemplo natural:

```text
pending
→ in_progress
→ completed
```

pero el usuario puede corregir la interpretación de lo ocurrido mientras la
fecha siga editable.

Ejemplos válidos:

```text
completed → not_finished
cancelled → completed
not_finished → cancelled
not_completed → completed
```

siempre que las demás reglas del dominio permitan el resultado final.

No convertir la máquina de estados en una restricción innecesaria.

---

### 2.5 Current day integrity

La libertad de cambiar status NO elimina la validación temporal.

Antes de que una occurrence quede en un status que ocupa tiempo:

```text
pending
in_progress
completed
not_finished
```

deben validarse overlaps con otras occurrences que también ocupen tiempo.

Los cambios de status y horario continúan sujetos a las reglas de conflicto.

---

### 2.6 Previous editable day

El día anterior todavía forma parte de la ventana de corrección.

El objetivo es permitir que el usuario reconstruya lo que realmente ocurrió
aunque no haya tenido oportunidad de registrar el día en tiempo real.

Durante este día el usuario puede:

```text
crear occurrences nuevas
editar occurrences existentes
cambiar fecha
cambiar startTime
cambiar endTime
cambiar status
eliminar occurrences
```

siempre que continúe dentro de la ventana editable y respete integridad
temporal.

---

### 2.7 Previous editable day statuses

Estados históricos permitidos:

```text
completed
not_completed
not_finished
cancelled
```

No permitir:

```text
in_progress
```

porque el día ya terminó y no puede existir una actividad actualmente en
progreso en una fecha pasada.

Tampoco debería persistir:

```text
pending
```

como estado histórico final.

---

### 2.8 Completed in previous editable day

`completed` está expresamente permitido en el día anterior editable.

Ejemplo:

El usuario realizó una actividad ayer pero no tuvo tiempo de registrarla.

Hoy puede crear o corregir la occurrence de ayer y dejarla como:

```text
completed
```

Esto no se considera un comportamiento excepcional.

Forma parte del objetivo de permitir reconstruir el día anterior.

---

### 2.9 Previous day corrections

Mientras siga editable, el usuario puede corregir libremente entre los
estados históricos permitidos.

Ejemplos:

```text
not_completed → completed
cancelled → completed
completed → not_finished
not_finished → completed
completed → cancelled
not_completed → not_finished
```

La prioridad es representar correctamente lo que finalmente ocurrió.

---

### 2.10 Previous day schedule correction

El usuario puede corregir también el intervalo real.

Ejemplo:

```text
Estudiar
08:00–10:00
not_finished
```

Después recuerda que únicamente estudió:

```text
08:00–08:45
```

Puede corregir:

```text
08:00–08:45
not_finished
```

Esto representa mejor el tiempo realmente utilizado.

Ajustar el horario de una `not_finished` es recomendable cuando se conoce el
intervalo real, pero no debe convertirse necesariamente en una obligación.

---

### 2.11 Previous day creation

Debe permitirse crear una occurrence nueva directamente en el día anterior
editable.

Ejemplo:

El usuario recuerda al día siguiente:

```text
ayer fui al médico de 13:00 a 14:00
```

Puede registrarlo retrospectivamente.

La creación debe pasar por las mismas validaciones de:

```text
overlap
ocupación temporal
conflictos
integridad
```

que cualquier otra mutación.

---

### 2.12 Previous day deletion

Mientras la fecha continúe editable, una occurrence puede eliminarse si las
reglas actuales del dominio lo permiten.

No tratar el día anterior como historia congelada únicamente por haber
cambiado de fecha.

---

### 2.13 Reconciliation

Cuando el día actual deja de ser:

```text
CURRENT_DAY
```

y pasa a:

```text
PREVIOUS_EDITABLE_DAY
```

los estados transitorios deben reconciliarse a nivel de:

```text
OccurrenceSegment
```

Aplicar segment por segment:

```text
pending
→ not_completed
```

```text
in_progress
→ not_finished
```

Los estados:

```text
completed
not_completed
not_finished
cancelled
```

se conservan.

Después de reconciliar todos los segments de una occurrence:

```text
recalcular Occurrence.status
```

utilizando las reglas de aggregate definidas para los statuses históricos.

Ejemplo:

```text
Antes:

Occurrence: Estudiar

Seg 1:
completed

Seg 2:
pending
```

Al pasar a `PREVIOUS_EDITABLE_DAY`:

```text
Seg 1:
completed

Seg 2:
not_completed
```

El aggregate resultante será:

```text
Occurrence.status = not_finished
```

porque parte de la occurrence fue realizada y parte no fue completada.

La reconciliación:

```text
NO
```

debe ejecutarse dentro del renderer.

Debe pertenecer a la capa de dominio correspondiente y persistirse de manera
coherente.

La fecha continúa siendo editable después de esta reconciliación.

### 2.14 Previous editable day after reconciliation

Que la reconciliación haya convertido:

```text
pending → not_completed
```

o:

```text
in_progress → not_finished
```

NO impide que el usuario corrija posteriormente el resultado mientras la
fecha siga dentro de la ventana editable.

Ejemplo:

```text
ayer quedó automáticamente:
not_completed
```

pero el usuario recuerda:

```text
sí la realicé
```

Puede cambiarla a:

```text
completed
```

---

### 2.14.1 Final reconciliation before frozen history

Antes de que una fecha pase de:

```text
PREVIOUS_EDITABLE_DAY
```

a:

```text
FROZEN_HISTORY
```

VCS debe ejecutar nuevamente la reconciliación.

Volver a comprobar, segment por segment:

```text
pending
→ not_completed
```

```text
in_progress
→ not_finished
```

Aunque estos estados normalmente ya no deberían existir en el día anterior,
la comprobación debe repetirse antes de congelar la fecha.

Esto protege contra casos como:

```text
datos inconsistentes
sesiones abiertas
correcciones parciales
bugs
estados transitorios inesperados
```

Después:

```text
1. reconciliar todos los segments
2. recalcular Occurrence.status de cada occurrence
3. validar integridad temporal y estructural
4. pasar la fecha a FROZEN_HISTORY
```

La operación debe ser:

```text
idempotente
```

Es decir, ejecutarla nuevamente sobre datos ya reconciliados no debe producir
cambios adicionales.

Ejemplo:

```text
Seg 1:
completed

Seg 2:
not_completed
```

permanece exactamente igual al ejecutar nuevamente reconciliation.

Pero si por alguna inconsistencia apareciera:

```text
Seg 2:
pending
```

antes de congelar:

```text
pending
→ not_completed
```

y después se recalcula el aggregate correspondiente.

Principio:

> Una fecha no debe entrar a FROZEN_HISTORY conservando estados transitorios
> que ya no son válidos para una fecha histórica.

### 2.15 Frozen history

Cuando una fecha sale de la ventana de edición:

```text
FROZEN_HISTORY
```

todas sus occurrences pasan a modo de consulta.

No permitir:

```text
crear
editar fecha
editar startTime
editar endTime
cambiar status
eliminar
```

La información histórica debe quedar estable.

---

### 2.16 Frozen status

Una occurrence congelada conserva el resultado final que tenía al momento de
cerrarse la ventana.

Ejemplos:

```text
completed
not_completed
not_finished
cancelled
```

No permitir reinterpretar posteriormente esa historia desde la UI normal.

---

### 2.17 Frozen conflict context

Si una occurrence congelada conserva:

```text
status_reason
source_occurrence_id
```

estos deben representar una relación de conflicto todavía válida al momento
de congelar la historia.

Si el contexto ya no era válido antes de congelar:

```text
status_reason = null
source_occurrence_id = null
```

sin restaurar automáticamente el status.

---

### 2.18 Current time and completed

Una occurrence no puede marcarse como:

```text
completed
```

si su finalización se encuentra en el futuro respecto al momento actual.

Regla:

```text
occurrence.endDateTime <= currentDateTime
```

debe cumplirse antes de establecer:

```text
status = completed
```

---

### 2.19 Completed with future endTime

Ejemplo:

```text
Current time:
09:20

Occurrence:
08:00–10:00
```

El usuario intenta:

```text
completed
```

VCS debe impedir la transición directa porque:

```text
10:00 > 09:20
```

La UI debe ofrecer una salida equivalente a:

```text
Ajustar horario
```

para que el usuario registre el intervalo real.

Ejemplo corregido:

```text
08:00–09:15
completed
```

---

### 2.20 Completed on a future date

Una occurrence completamente futura tampoco puede marcarse como completed.

Ejemplo inválido:

```text
tomorrow
08:00–10:00
completed
```

Si el usuario realmente realizó esa actividad antes, debe primero corregir:

```text
date
startTime
endTime
```

al intervalo donde realmente ocurrió.

Después puede establecer:

```text
completed
```

si ya se encuentra en el pasado o presente permitido.

---

### 2.21 Temporal freedom does not bypass conflicts

Editar retrospectivamente no permite crear dos realidades temporales
incompatibles.

Ejemplo:

```text
Ayer:

08:00–10:00 Estudiar
completed
```

y el usuario intenta crear:

```text
08:30–09:30 Gym
completed
```

Como ambas occurrences ocupan tiempo y se superponen:

```text
existe conflicto
```

El usuario debe corregir horarios o resolver conscientemente cuál refleja la
realidad.

---

### 2.22 No automatic restoration

Si una occurrence fue:

```text
cancelled
not_completed
not_finished
```

el sistema no debe cambiarla automáticamente a otro estado únicamente porque
desapareció un conflicto.

Cualquier reinterpretación debe ser explícita por parte del usuario mientras
la fecha siga editable.

---

### 2.23 Contextual help for previous editable day

Cuando el usuario seleccione el día anterior editable, mostrar una leyenda
informativa mínima.

Texto conceptual:

> Ayer todavía es editable. Puedes agregar, corregir o eliminar actividades
> y registrar cómo terminaron. Cuando finalice la ventana de edición, el día
> quedará congelado.

Esta leyenda es únicamente UX.

No modifica las reglas de dominio.

---

### 2.24 Future contextual help

Más adelante puede existir un sistema general de ayuda contextual accesible
desde un control de información.

Conceptualmente:

```text
contextual help button
→ muestra información útil según el flujo actual
```

Ejemplo futuro:

```text
botón circular de ayuda/información
en la parte inferior derecha
```

No implementar todavía salvo que una fase futura lo autorice.

---

### 2.25 Summary

La matriz temporal queda:

```text
FUTURE
────────────────────────────────
statuses:
pending
cancelled

editing:
sí

create:
sí

delete:
sí

in_progress:
no

completed:
no mientras pertenezca al futuro


CURRENT_DAY
────────────────────────────────
statuses:
los 6

editing:
sí

create:
sí

delete:
sí

status correction:
sí

integrity checks:
sí


PREVIOUS_EDITABLE_DAY
────────────────────────────────
statuses finales:
completed
not_completed
not_finished
cancelled

editing:
sí

create:
sí

delete:
sí

status correction:
sí

in_progress:
no

pending histórico:
no


FROZEN_HISTORY
────────────────────────────────
editing:
no

create:
no

delete:
no

status changes:
no

mode:
read-only
```

Principio rector:

> Mientras el día sea editable, VCS protege integridad temporal pero permite
> corregir la interpretación de lo ocurrido.

La ventana temporal existe para proteger la historia, no para impedir que el
usuario registre correctamente su realidad.

## 3. Conflict and origin context

VCS no almacenará una genealogía completa de conflictos.

No implementar:

```text
conflictSources[]
```

ni una relación persistente con todas las occurrences que alguna vez
modificaron a otra.

La base conservará únicamente contexto mínimo útil sobre:

```text
el último conflicto que modificó una occurrence
```

y sobre:

```text
cómo una occurrence nació o provocó un conflicto
```

---

### 3.1 Conflict context belongs to Occurrence

El contexto de conflicto pertenece a:

```text
Occurrence
```

No a:

```text
OccurrenceSegment
```

No crear en segments:

```text
status_reason
conflict_reason
source_occurrence_id
```

Los segments derivan estructuralmente de su occurrence.

---

### 3.2 Current physical column and semantic target

La base actual contiene:

```text
status_reason
source_occurrence_id
```

Sin embargo, con el modelo segmentado:

```text
status_reason
```

es un nombre demasiado limitado.

El concepto normativo será:

```text
conflict_reason
```

porque un conflicto puede modificar:

```text
status
segments
start/end structure
```

sin necesariamente ser la razón directa del status actual.

Una futura migration puede:

```text
renombrar status_reason → conflict_reason
```

o realizar la adaptación equivalente.

No modificar migraciones antiguas.

---

### 3.3 Conflict reason meaning

`conflict_reason` significa:

> Tipo del último conflicto autorizado que modificó el estado o la estructura
> temporal de esta occurrence.

Valores mínimos:

```text
priority_override
user_forced_override
```

---

### 3.4 `priority_override`

Usar:

```text
priority_override
```

cuando la política de prioridades permite que una occurrence source se
imponga sobre otra.

Ejemplo:

```text
source.priority > target.priority
```

y las demás reglas del dominio permiten la operación.

Entonces target puede conservar:

```text
conflict_reason = priority_override
source_occurrence_id = source.id
```

---

### 3.5 `user_forced_override`

Usar:

```text
user_forced_override
```

cuando la política de prioridades no permite automáticamente la operación
o cuando el tipo de información afectada exige confirmación explícita.

Ejemplos:

```text
equal priority
lower-priority source
completed target
not_finished target
```

Si el usuario confirma:

```text
conflict_reason = user_forced_override
source_occurrence_id = source.id
```

---

### 3.6 `source_occurrence_id`

`source_occurrence_id` representa:

> La occurrence source del último conflicto que modificó a target.

Ejemplo:

```text
A modifica U
```

Entonces:

```text
U.source_occurrence_id = A.id
```

Posteriormente:

```text
B vuelve a modificar U
```

Actualizar:

```text
U.source_occurrence_id = B.id
```

y:

```text
U.conflict_reason
```

también pasa a representar ese último conflicto.

---

### 3.7 Latest conflict wins

Como solo existe:

```text
un conflict_reason
un source_occurrence_id
```

VCS no intenta conservar mediante estas columnas toda la historia.

Ejemplo:

```text
A segmentó U
B posteriormente volvió a segmentar U
C posteriormente la recortó
```

El contexto persistido corresponde al conflicto más reciente:

```text
source_occurrence_id = C
```

No conservar:

```text
A
B
C
```

como lista.

Si en el futuro se necesita esa historia completa:

```text
crear un event log separado
```

---

### 3.8 Conflict context is not active-only

`conflict_reason` y `source_occurrence_id` NO deben limpiarse únicamente porque
source haya dejado de superponerse con target.

Ejemplo:

```text
U:
13:00–17:00
```

A provoca:

```text
U segments:
13:00–14:00
14:30–17:00
```

Después de resolver el conflicto:

```text
A ya no se superpone con los segments de U
```

pero A sigue siendo el último conflicto que modificó su estructura.

Por tanto:

```text
conflict_reason
source_occurrence_id
```

se conservan.

---

### 3.9 Conflict context is not cleared by normal later movement

Si una occurrence conserva información sobre su último conflicto y después el
usuario realiza otra modificación normal:

```text
no limpiar automáticamente conflict_reason
no limpiar automáticamente source_occurrence_id
```

Estas columnas continúan respondiendo:

> ¿Cuál fue el último conflicto registrado que afectó esta occurrence?

Solo un conflicto posterior reemplaza ese contexto.

---

### 3.10 Manual cancellation without conflict

Una cancelación normal no crea contexto de conflicto.

Ejemplo:

```text
pending → cancelled
```

por decisión normal del usuario:

```text
conflict_reason = null
source_occurrence_id = null
```

si la occurrence nunca había tenido un conflicto previo.

Si ya conserva metadata histórica del último conflicto, una acción normal no
la borra automáticamente.

---

### 3.11 Current conflicts are still derived

`conflict_reason` y `source_occurrence_id` NO se utilizan para descubrir los
blockers actuales.

Los blockers actuales se calculan dinámicamente utilizando:

```text
segment.start_time
segment.end_time
segment.status
```

Un segment bloquea si:

```text
se superpone
+
su status ocupa tiempo
```

---

### 3.12 Multiple current blockers

Aunque target solo conserve un:

```text
source_occurrence_id
```

una operación puede encontrar:

```text
1
2
3
N
```

blockers actuales.

Todos deben detectarse dinámicamente.

No limitar la detección al source histórico almacenado.

---

### 3.13 No inverse conflict list

Una occurrence source no necesita guardar:

```text
affected_occurrence_ids[]
```

Si A es el último source de varias occurrences:

```text
U1.source_occurrence_id = A
U2.source_occurrence_id = A
U3.source_occurrence_id = A
```

la relación inversa puede consultarse cuando sea necesario.

No duplicar información.

---

### 3.14 Origin context

El origen de una occurrence es diferente de su status y de su conflict
context.

Se puede conservar mediante:

```text
origin_reason
```

---

### 3.15 `conflict_insertion`

Si una occurrence nace y para poder insertarse provoca un conflicto con una
o más occurrences existentes:

```text
origin_reason = conflict_insertion
```

Ejemplo:

```text
PlanItem:
Comprar tortillas
```

ya existe.

Durante Estudiar, el usuario crea una occurrence:

```text
Comprar tortillas
14:10–14:25
```

y esa creación provoca segmentación o modificación de otra occurrence.

Entonces:

```text
origin_reason = conflict_insertion
```

Esto describe:

> Esta occurrence nació mediante una inserción que generó un conflicto.

---

### 3.16 Normal creation

Si una occurrence se crea normalmente sin provocar conflicto:

```text
origin_reason = null
```

por ahora.

No crear razones innecesarias para cada creación normal.

---

### 3.17 Origin reason does not change after birth

`origin_reason` describe:

```text
cómo nació la occurrence
```

No cambia posteriormente porque la occurrence sea movida o editada.

Ejemplo:

```text
origin_reason = null
```

y meses después la occurrence se mueve provocando conflicto:

```text
origin_reason sigue null
```

porque no nació mediante conflict insertion.

---

### 3.18 Last conflict action

Para conocer qué tipo de acción de la occurrence source produjo recientemente
un conflicto, utilizar un concepto separado:

```text
last_conflict_action
```

Valores iniciales útiles:

```text
conflict_insertion
conflict_move
```

---

### 3.19 Conflict insertion action

Si una occurrence nace provocando un conflicto:

```text
origin_reason = conflict_insertion
last_conflict_action = conflict_insertion
```

---

### 3.20 Conflict move action

Si una occurrence ya existía y después se mueve a un horario donde provoca
un conflicto:

```text
origin_reason
```

no cambia.

Actualizar:

```text
last_conflict_action = conflict_move
```

Esto permite saber que la occurrence produjo su conflicto más reciente al ser
movida.

---

### 3.21 Last action is not full history

`last_conflict_action` conserva únicamente:

```text
la acción conflictiva más reciente
```

No permite deducir por sí sola:

```text
cuántas veces se movió
cuántas veces interrumpió otra actividad
con qué frecuencia ocurre
```

Para detectar patrones históricos completos se necesitará posteriormente:

```text
event log
o métricas históricas
```

No sobrecargar estas columnas para intentar resolver estadísticas futuras.

---

### 3.22 Segmentation can be caused repeatedly

Una occurrence puede ser modificada por conflictos múltiples a lo largo de
su vida.

Ejemplo:

```text
U
├── conflicto con A
├── conflicto con B
└── conflicto con C
```

Cada conflicto autorizado puede:

```text
recortar segments
dividir segments
cancelar segments
modificar statuses
```

siguiendo las reglas vigentes.

No impedir nuevas segmentaciones únicamente porque U ya esté segmentada.

---

### 3.23 Latest conflict replaces previous context

Después:

```text
A modifica U
```

guardar A.

Después:

```text
B modifica U
```

reemplazar con B.

Después:

```text
C modifica U
```

reemplazar con C.

El estado final conserva únicamente:

```text
conflict_reason del conflicto más reciente
source_occurrence_id del conflicto más reciente
```

---

### 3.24 No `conflictSources[]`

No crear:

```text
conflictSources[]
occurrence_conflict_sources
```

con las reglas actuales.

La aplicación necesita:

```text
último contexto persistido
+
conflictos actuales derivados dinámicamente
```

La genealogía completa queda fuera de este modelo.

---

### 3.25 Frozen history

Cuando una occurrence pase a historia frozen:

```text
conflict_reason
source_occurrence_id
origin_reason
last_conflict_action
```

pueden conservarse.

No necesitan representar un conflicto todavía activo.

Representan metadata histórica mínima sobre:

```text
cómo nació
qué último conflicto la modificó
qué acción conflictiva reciente realizó
```

---

### 3.26 Principle

Separar siempre:

```text
status
→ resultado actual derivado de segments

conflict_reason
→ tipo del último conflicto que modificó target

source_occurrence_id
→ source de ese último conflicto

origin_reason
→ cómo nació esta occurrence

last_conflict_action
→ cómo esta occurrence provocó su conflicto más reciente
```

Principio rector:

> VCS conserva contexto mínimo con valor operativo y analítico, pero no intenta
> convertir cada occurrence en un historial completo de eventos.

## 4. Conflict resolution with segments

Los conflictos temporales se resuelven sobre:

```text
OccurrenceSegments
```

No sobre el rango general completo de una occurrence.

Una occurrence source será representada como:

```text
A
```

La occurrence afectada será:

```text
U
```

Cada operación debe identificar los segments concretos de U que se superponen
con segments ocupantes de A.

---

### 4.1 Blocking segment statuses

Un segment bloquea tiempo si su status es:

```text
pending
in_progress
completed
not_finished
```

No bloquea si es:

```text
cancelled
not_completed
```

---

### 4.2 General conflict process

Antes de persistir una operación:

```text
1. calcular overlaps actuales entre segments
2. ignorar segments no ocupantes
3. identificar blockers
4. determinar qué resolución permite cada status
5. mostrar consecuencias al usuario
6. obtener las confirmaciones necesarias
7. revalidar blockers
8. calcular estado final completo
9. persistir atómicamente
```

---

### 4.3 Interval subtraction

Cuando A ocupa parte del intervalo de un segment U, VCS puede calcular:

```text
U - A
```

El resultado puede dejar:

```text
0 fragments
1 fragment
2 fragments
```

---

### 4.4 No overlap

Si no existe overlap:

```text
U permanece sin cambios
```

---

### 4.5 Overlap on the end of U

Ejemplo:

```text
U:
08:00────────────10:00

A:
        09:15────────────11:00
```

El fragmento superviviente es:

```text
08:00–09:15
```

Por tanto:

```text
U.end_time = A.start_time
```

o se actualiza el segment equivalente.

---

### 4.6 Overlap on the beginning of U

Ejemplo:

```text
A:
08:00────────────11:00

U:
       09:00────────────12:00
```

El fragmento superviviente es:

```text
11:00–12:00
```

Por tanto:

```text
U.start_time = A.end_time
```

en el segment afectado.

El rango general de la occurrence no tiene que modificarse automáticamente.

---

### 4.7 Internal overlap

Ejemplo:

```text
U:
08:00────────────────12:00

A:
       09:00────10:00
```

El resultado estructural puede ser:

```text
Segment 1:
08:00–09:00

Segment 2:
10:00–12:00
```

Sigue existiendo:

```text
una sola Occurrence U
```

con:

```text
dos segments
```

No crear automáticamente dos occurrences.

---

### 4.8 Full coverage

Si A cubre completamente un segment U:

```text
A:
08:00────────────────13:00

U:
     09:00────12:00
```

no queda ningún fragmento temporal superviviente de ese segment.

No crear segments de:

```text
duración cero
duración negativa
```

La resolución dependerá del status original de U.

Cuando corresponda cancelar:

```text
el segment puede conservar su intervalo
pero status → cancelled
```

Como `cancelled` no ocupa tiempo, deja de ser blocker.

---

### 4.9 Segment splitting

Cuando un segment se divide:

```text
original
→ fragmento izquierdo
+ fragmento derecho
```

el fragmento izquierdo puede conservar el ID original.

El fragmento adicional recibe un nuevo ID.

Ejemplo:

```text
S1:
08:00–12:00
```

A ocupa:

```text
09:00–10:00
```

Resultado:

```text
S1:
08:00–09:00

S2:
10:00–12:00
```

---

### 4.10 Repeated segmentation

Una occurrence ya segmentada puede volver a ser modificada.

Ejemplo:

```text
U:
08:00–09:00
10:00–12:00
```

A aparece:

```text
08:30–10:30
```

Resultado posible:

```text
08:00–08:30
10:30–12:00
```

No existe un límite conceptual de:

```text
1 conflicto por occurrence
```

Una occurrence puede terminar con:

```text
N segments
```

si su historia/ejecución lo requiere.

---

### 4.11 Segment status inheritance after structural split

Cuando un conflict split no implica por sí mismo una transición especial de
status:

```text
los fragments supervivientes heredan el status del segment original
```

Ejemplo:

```text
pending segment
08:00–12:00
```

se divide en:

```text
08:00–09:00 pending
10:00–12:00 pending
```

Lo mismo puede aplicar a:

```text
completed
not_finished
```

cuando el usuario autoriza explícitamente la corrección correspondiente.

---

### 4.12 `pending` blocker

`pending` representa planificación todavía no realizada.

Puede resolverse mediante prioridad cuando:

```text
A.priority > U.priority
```

Entonces:

```text
conflict_reason = priority_override
source_occurrence_id = A.id
```

Si:

```text
A.priority == U.priority
```

o:

```text
A.priority < U.priority
```

la resolución requiere confirmación explícita:

```text
conflict_reason = user_forced_override
source_occurrence_id = A.id
```

---

### 4.13 Pending partial overlap

Si solo una parte de un pending segment es desplazada:

```text
preservar los fragments restantes
```

Los fragments supervivientes continúan:

```text
pending
```

Ejemplo:

```text
U:
13:00–17:00 pending

A:
14:00–14:30
```

Resultado:

```text
13:00–14:00 pending
14:30–17:00 pending
```

---

### 4.14 Pending full coverage

Si un pending segment queda completamente cubierto y la resolución está
autorizada:

```text
segment.status → cancelled
```

El interval puede conservarse como registro estructural.

---

### 4.15 Priority rule

La prioridad autoriza automáticamente a nivel de dominio únicamente cuando:

```text
source.priority > target.priority
```

Igual prioridad:

```text
NO priority_override
```

Menor prioridad:

```text
NO priority_override
```

Ambos pueden resolverse mediante:

```text
user_forced_override
```

si las demás reglas permiten la operación.

---

### 4.16 Priority authorization is not silent mutation

Aunque:

```text
priority_override
```

sea permitido por el dominio:

```text
la UI debe informar qué se modificará
```

No realizar modificaciones conflictivas silenciosas.

---

### 4.17 `in_progress` blocker

`in_progress` ocupa tiempo y representa una actividad activa o registrada como
iniciada.

La estructura puede corregirse mediante segmentación.

---

### 4.18 `in_progress` interrupted at its end

Ejemplo:

```text
U:
08:00–10:00
in_progress

A:
09:15–11:00
```

Si el único fragmento superviviente es el prefijo:

```text
08:00–09:15
```

entonces:

```text
status → not_finished
end_time → 09:15
```

Esto conserva la regla:

> La actividad sí ocurrió hasta el momento en que fue interrumpida.

---

### 4.19 `in_progress` correction at its beginning

Ejemplo:

```text
A:
08:00–11:00

U:
09:00–12:00
in_progress
```

Si el usuario confirma que el inicio registrado de U era incorrecto:

```text
U segment:
11:00–12:00
```

puede conservar:

```text
in_progress
```

si la zona temporal permite ese status.

Si la fecha ya requiere estados históricos:

```text
aplicar reconciliation correspondiente
```

---

### 4.20 Internal split of `in_progress`

Si A aparece completamente dentro de un `in_progress`:

```text
U:
08:00–12:00

A:
09:00–10:00
```

VCS puede segmentar U:

```text
08:00–09:00
10:00–12:00
```

La operación debe mostrar al usuario los fragments resultantes.

El fragmento anterior a la interrupción puede cerrarse como:

```text
not_finished
```

cuando representa actividad efectivamente interrumpida.

Los demás fragments permanecen editables y deben terminar con statuses válidos
para su zona temporal antes de persistir.

VCS no debe inventar silenciosamente un resultado histórico que el usuario no
confirmó.

---

### 4.21 Warning for `in_progress`

Antes de modificar una occurrence `in_progress`, informar:

```text
qué segment será recortado o dividido
qué horario resultará
qué status cambiará
```

Ejemplo:

> Estudiar está en progreso. Si continúas, el tramo realizado hasta las 09:15
> quedará como No terminada.

---

### 4.22 `completed` blocker

`completed` representa tiempo declarado como realmente realizado.

Por tanto:

```text
completed → ocupa tiempo
```

y no puede modificarse automáticamente mediante prioridad.

---

### 4.23 Completed cannot be automatically overridden

Aunque:

```text
A.priority > U.priority
```

no ejecutar automáticamente:

```text
completed → cancelled
```

ni:

```text
recorte/split de completed
```

sin confirmación explícita fuerte.

---

### 4.24 Completed partial correction

Si el usuario confirma que una parte del intervalo previously completed era
incorrecta:

```text
completed segments pueden recortarse o dividirse
```

Los fragments supervivientes conservan por defecto:

```text
completed
```

Ejemplo:

```text
U:
13:00–17:00 completed

A:
14:00–14:30
```

Con confirmación:

```text
U:
13:00–14:00 completed
14:30–17:00 completed
```

---

### 4.25 Completed full coverage

Si el usuario confirma que una completed completamente cubierta era un error:

```text
segment.status → cancelled
```

y:

```text
conflict_reason = user_forced_override
source_occurrence_id = A.id
```

---

### 4.26 Completed warning

Mensaje conceptual:

> Esta actividad está marcada como completada. Continuar modificará tiempo que
> registraste como realizado.

Acciones posibles:

```text
[Volver]
[Ajustar]
[Confirmar corrección]
```

---

### 4.27 `not_finished` blocker

`not_finished` significa que el segment sí ocurrió, pero la actividad no
terminó correctamente.

Por tanto:

```text
not_finished → ocupa tiempo
```

---

### 4.28 Not finished partial correction

Si el usuario confirma un nuevo conflicto:

```text
not_finished
```

puede recortarse o dividirse.

Los fragments supervivientes conservan por defecto:

```text
not_finished
```

Ejemplo:

```text
U:
08:00–10:00 not_finished

A:
09:15–11:00
```

Resultado:

```text
08:00–09:15 not_finished
```

---

### 4.29 Not finished internal split

Ejemplo:

```text
U:
08:00–12:00 not_finished

A:
09:00–10:00
```

Con confirmación:

```text
08:00–09:00 not_finished
10:00–12:00 not_finished
```

Sigue siendo:

```text
una Occurrence
```

con dos fragments.

---

### 4.30 Not finished requires explicit confirmation

Una prioridad superior no debe modificar silenciosamente tiempo registrado
como `not_finished`.

Requiere:

```text
user_forced_override
```

porque el usuario está corrigiendo realidad registrada.

---

### 4.31 Not finished full coverage

Si no queda ningún fragmento y el usuario confirma la corrección:

```text
segment.status → cancelled
```

con:

```text
conflict_reason = user_forced_override
source_occurrence_id = A.id
```

---

### 4.32 `not_completed`

`not_completed` significa:

```text
la actividad no ocurrió
```

Por tanto:

```text
no ocupa tiempo
no bloquea
```

No necesita ser modificada para permitir otra occurrence superpuesta.

Si el usuario afirma que sí realizó una parte:

```text
debe corregirla a un status realizado apropiado
```

por ejemplo:

```text
not_finished
```

---

### 4.33 `cancelled`

`cancelled`:

```text
no ocupa tiempo
no bloquea
```

Esto aplica aunque conserve:

```text
conflict_reason
source_occurrence_id
```

La metadata histórica no hace que vuelva a reservar tiempo.

---

### 4.34 Multiple blockers

Una operación puede encontrar múltiples blockers pertenecientes a una o más
occurrences.

Ejemplo:

```text
A:
09:00–12:00
```

encuentra:

```text
B pending
C completed
D not_finished
E cancelled
```

Analizar:

```text
B
C
D
```

Ignorar como blocker:

```text
E
```

Cada blocker se resuelve según su propio status.

---

### 4.35 Multiple blockers inside the same occurrence

A puede intersectar más de un segment de la misma occurrence.

La resolución debe calcular el resultado sobre:

```text
todos los segments afectados
```

antes de persistir.

Una misma U puede terminar con una segmentación más compleja sin convertirse
en múltiples occurrences.

---

### 4.36 Final temporal integrity

Después de resolver todos los conflictos:

```text
ningún segment ocupante
```

puede solaparse con otro segment ocupante incompatible.

Estados ocupantes:

```text
pending
in_progress
completed
not_finished
```

Estados no ocupantes:

```text
cancelled
not_completed
```

---

### 4.37 No partial conflict resolution

Si A encuentra tres blockers y el usuario solo resuelve dos:

```text
no persistir A como ocupante
```

La operación completa debe quedar temporalmente válida.

---

### 4.38 Revalidation

Antes del commit:

```text
volver a calcular blockers
```

Si apareció un blocker nuevo que el usuario no vio:

```text
no cancelarlo ni segmentarlo silenciosamente
```

La operación debe volver a solicitar resolución.

---

### 4.39 Atomicity

Una resolución puede incluir:

```text
crear o modificar A
recortar segments
crear fragments nuevos
cambiar segment statuses
recalcular occurrence aggregates
actualizar conflict_reason
actualizar source_occurrence_id
actualizar origin/action metadata
```

Todo debe persistirse como:

```text
una sola operación atómica
```

Si cualquier paso falla:

```text
rollback completo
```

---

### 4.40 Conflict metadata after mutation

Cuando A modifica U mediante conflicto:

```text
U.conflict_reason
U.source_occurrence_id
```

deben actualizarse con el conflicto más reciente.

Si A nació provocando el conflicto:

```text
A.origin_reason = conflict_insertion
A.last_conflict_action = conflict_insertion
```

Si A ya existía y fue movida para provocar el conflicto:

```text
A.last_conflict_action = conflict_move
```

---

### 4.41 No automatic schedule shifting

VCS no mueve automáticamente una occurrence completa a otro horario para
evitar conflicto.

No hacer:

```text
08:00–10:00
→ automáticamente 10:00–12:00
```

La segmentación únicamente representa:

```text
tramos supervivientes
interrupciones
correcciones explícitas
```

Mover la occurrence completa sigue siendo una decisión del usuario.

---

### 4.42 UI actions

Según el caso, la UI puede ofrecer acciones como:

```text
[Ajustar nueva actividad]
[Ajustar actividad existente]
[Segmentar y continuar]
[Finalizar actividad y continuar]
[Cancelar actividad y continuar]
[Confirmar corrección]
[Volver]
```

No todas las acciones aparecen para todos los statuses.

---

### 4.43 UI must show concrete result

No mostrar únicamente:

```text
"Existe un conflicto"
```

Mostrar el resultado esperado.

Ejemplo:

```text
Estudiar:
13:00–17:00
```

A:

```text
Lavar ropa:
14:00–14:30
```

VCS puede informar:

> Estudiar se dividirá en 13:00–14:00 y 14:30–17:00.

Así el usuario conoce la transformación antes de confirmarla.

---

### 4.44 Principle

La regla estructural general es:

```text
segment afectado
-
intervalo ocupante confirmado
=
fragments supervivientes
```

Los fragments siguen perteneciendo a:

```text
la misma occurrence
```

El status original del blocker determina:

```text
qué puede hacerse automáticamente
qué requiere confirmación
qué status resultará
```

Principio rector:

> VCS puede dividir o recortar la estructura temporal de una occurrence para
> representar interrupciones reales, pero no debe inventar resultados ni
> reescribir silenciosamente tiempo que el usuario ya declaró como realizado.

## 5. Hard integrity rules and non-overridable prohibitions

VCS debe distinguir entre:

```text
una operación permitida normalmente
```

```text
una operación que requiere confirmación explícita
```

y:

```text
una operación estructuralmente inválida
```

`user_forced_override` permite al usuario corregir o imponer decisiones que la
política normal de prioridad no tomaría automáticamente.

Sin embargo:

```text
user_forced_override
```

NO permite romper las invariantes estructurales del dominio.

Existen estados que VCS nunca debe persistir aunque el usuario confirme la
operación.

---

### 5.1 Three authorization levels

Las operaciones pueden clasificarse conceptualmente como:

```text
PERMITTED
CONFIRMATION_REQUIRED
FORBIDDEN
```

#### Permitted

La operación cumple normalmente todas las reglas del dominio.

Ejemplo:

```text
una occurrence de mayor prioridad
modifica un pending de menor prioridad
```

cuando la política correspondiente autoriza:

```text
priority_override
```

#### Confirmation required

La operación puede representar una corrección válida, pero VCS necesita
confirmación consciente del usuario.

Ejemplos:

```text
menor prioridad modifica mayor prioridad
igual prioridad modifica otra occurrence
completed es corregida
not_finished es recortada o segmentada
```

Estas operaciones pueden utilizar:

```text
user_forced_override
```

cuando corresponda.

#### Forbidden

La operación produciría un estado imposible o rompería una invariante del
dominio.

No existe:

```text
"forzar de todas maneras"
```

para estos casos.

---

### 5.2 Frozen history is immutable

Una fecha en:

```text
FROZEN_HISTORY
```

es de solo lectura.

No permitir:

```text
crear occurrences
crear segments
editar occurrences
editar segments
mover horarios
redimensionar horarios
cambiar statuses
segmentar
eliminar
resolver conflictos modificando la fecha frozen
```

Ni:

```text
priority_override
```

ni:

```text
user_forced_override
```

pueden modificar historia congelada.

---

### 5.3 Frozen history cannot be bypassed indirectly

Tampoco puede modificarse una occurrence frozen como efecto secundario de una
operación realizada desde otra fecha o activity.

Ejemplo:

```text
A editable
```

no puede imponerse sobre:

```text
U frozen
```

si para hacerlo sería necesario modificar U.

La operación debe ser rechazada o A debe ajustarse.

---

### 5.4 Every occurrence must contain segments

Toda occurrence debe conservar:

```text
1..N OccurrenceSegments
```

Nunca persistir:

```text
Occurrence
segments = []
```

Incluso cuando un conflict cubre completamente un segment, puede conservarse
su intervalo con:

```text
status = cancelled
```

si esa es la resolución aprobada.

---

### 5.5 Segment duration must be positive

Todo segment debe cumplir:

```text
segment.start_time < segment.end_time
```

Prohibido:

```text
start_time == end_time
```

y:

```text
start_time > end_time
```

No crear fragments de duración cero o negativa durante:

```text
recortes
splits
conflict resolution
resize
```

---

### 5.6 Segments must remain inside the occurrence range

Todo segment debe cumplir:

```text
occurrence.start_time <= segment.start_time
```

y:

```text
segment.end_time <= occurrence.end_time
```

Ejemplo inválido:

```text
Occurrence:
13:00–17:00

Segment:
12:30–14:00
```

Ejemplo inválido:

```text
Occurrence:
13:00–17:00

Segment:
16:30–18:00
```

La UI puede permitir estados temporales inválidos mientras el usuario está
editando un draft.

Sin embargo:

```text
NO persistir
```

hasta que todos los segments vuelvan a ser válidos.

---

### 5.7 Sibling segments cannot overlap

Dos segments pertenecientes a la misma occurrence no pueden superponerse.

Inválido:

```text
S1:
13:00–15:00

S2:
14:30–16:00
```

La operación debe corregirse antes de persistir.

Segments adyacentes sí pueden existir:

```text
13:00–14:00
14:00–15:00
```

---

### 5.8 Aggregate status cannot contradict its segments

`Occurrence.status` es derivado.

Prohibido persistir:

```text
Occurrence.status
```

con un valor incompatible con:

```text
Segment.status[]
```

Toda mutación de segments debe:

```text
1. modificar segments
2. derivar nuevamente Occurrence.status
3. persistir ambos coherentemente
```

No existe una edición independiente del aggregate.

---

### 5.9 Direct aggregate mutation is prohibited

No implementar una operación de dominio equivalente a:

```text
setOccurrenceStatus(...)
```

que modifique solamente:

```text
occurrences.status
```

El control de status siempre opera sobre:

```text
uno o más segments
```

y el aggregate se recalcula después.

---

### 5.10 Completed segment cannot end in the future

Un segment no puede tener:

```text
status = completed
```

si:

```text
segment.endDateTime > currentDateTime
```

Esto es una invariante temporal.

No basta con una confirmación del usuario.

Debe corregirse primero:

```text
fecha
start_time
end_time
```

o utilizar un status compatible con el tiempo actual.

---

### 5.11 General occurrence range may extend into the future

La prohibición anterior se aplica al:

```text
completed Segment
```

no necesariamente a todo el rango general de la occurrence.

Ejemplo válido:

```text
Occurrence:
13:00–17:00

Current time:
15:00

S1:
13:00–14:00 completed

S2:
15:30–17:00 pending
```

El primer segment ya ocurrió.

El segundo todavía pertenece al futuro.

El aggregate puede derivarse según las reglas normales.

---

### 5.12 Historical transient statuses must be reconciled

Cuando una fecha deja de ser TODAY:

```text
pending
→ not_completed
```

```text
in_progress
→ not_finished
```

segment por segment.

No debe permanecer como estado histórico estable:

```text
pending
in_progress
```

en una fecha que ya requiere reconciliación.

---

### 5.13 Reconciliation must run again before Frozen

Antes de:

```text
PREVIOUS_EDITABLE_DAY
→ FROZEN_HISTORY
```

VCS debe ejecutar nuevamente:

```text
pending
→ not_completed

in_progress
→ not_finished
```

y después:

```text
recalcular aggregates
validar integridad
congelar
```

La operación debe ser idempotente.

---

### 5.14 No unresolved occupying overlap may be persisted

Después de resolver una operación, no pueden quedar dos segments
incompatibles superpuestos cuando ambos ocupan tiempo.

Statuses ocupantes:

```text
pending
in_progress
completed
not_finished
```

Statuses no ocupantes:

```text
cancelled
not_completed
```

Si el estado final todavía contiene:

```text
occupying overlap
```

la operación completa es inválida.

---

### 5.15 All blockers must be resolved

Si una operación encuentra:

```text
B
C
D
```

como blockers y solamente se resuelven:

```text
B
C
```

pero:

```text
D
```

continúa bloqueando:

```text
NO persistir la operación
```

No existe una resolución parcial que deje el planner temporalmente
inconsistente.

---

### 5.16 Newly discovered blockers cannot be modified silently

Los blockers deben volver a calcularse inmediatamente antes de persistir.

Ejemplo:

```text
UI mostró:
B
C
```

El usuario autorizó la resolución.

Antes del commit aparece:

```text
D
```

El backend encuentra:

```text
B
C
D
```

D no puede ser:

```text
cancelled
recortada
segmentada
modificada
```

silenciosamente.

La operación debe detenerse y presentar el nuevo conflicto al usuario cuando
requiera autorización.

---

### 5.17 Previous authorization applies only to known conflicts

Una confirmación del usuario autoriza:

```text
las consecuencias concretas que fueron presentadas
```

No representa autorización genérica para:

```text
"resolver cualquier otro conflicto que aparezca"
```

Si cambia el conjunto de blockers:

```text
revalidar autorización
```

---

### 5.18 Priority cannot bypass structural integrity

Aunque:

```text
A.priority > U.priority
```

`priority_override` no puede permitir:

```text
segmentos inválidos
historia frozen modificada
completed futuro
overlaps ocupantes sin resolver
aggregate inconsistente
operaciones parciales
```

La prioridad decide quién puede imponerse dentro de un estado válido.

No permite crear estados inválidos.

---

### 5.19 User forced override cannot bypass structural integrity

La misma regla aplica a:

```text
user_forced_override
```

La libertad del usuario permite corregir interpretación y planificación.

No permite persistir:

```text
contradicciones estructurales
```

---

### 5.20 Realized time cannot be rewritten silently

Los statuses:

```text
completed
not_finished
```

representan tiempo registrado como realizado.

Una prioridad superior:

```text
NO
```

puede modificarlos silenciosamente.

Puede existir una corrección mediante:

```text
user_forced_override
```

mientras la fecha sea editable.

La prohibición es:

```text
modificación automática sin conocimiento del usuario
```

no:

```text
corrección consciente
```

---

### 5.21 No invented realized time

VCS puede conservar fragments que resultan matemáticamente de una corrección
confirmada.

Pero no debe inventar que una actividad ocurrió durante un tramo que el
usuario nunca confirmó.

Ejemplo:

```text
A.start_time <= U.start_time
```

no permite crear artificialmente:

```text
U not_finished
```

con un fragmento inexistente antes de A.

Si no existe tramo superviviente válido:

```text
aplicar la resolución correspondiente
```

por ejemplo:

```text
cancelled
```

cuando esté autorizada.

---

### 5.22 No automatic global schedule shifting

Resolver un conflicto no permite inventar otro horario completo para U.

No hacer automáticamente:

```text
08:00–10:00
→
10:00–12:00
```

simplemente porque apareció un conflicto.

Sí pueden existir:

```text
recortes
splits
fragments supervivientes
```

porque derivan directamente de la resta de intervalos confirmada.

Mover toda la occurrence es decisión explícita del usuario.

---

### 5.23 Pure movement may translate segments

Si una occurrence se mueve conservando exactamente su duración general:

```text
08:00–12:00
→
13:00–17:00
```

sus segments pueden trasladarse mediante el mismo delta.

Esto NO se considera:

```text
automatic schedule shifting
```

porque el usuario solicitó explícitamente mover la occurrence completa.

---

### 5.24 Resize cannot guess segment proportions

Cuando cambia la duración general:

```text
08:00–12:00
→
08:00–11:00
```

VCS no puede:

```text
escalar automáticamente
comprimir
estirar
redistribuir
```

los segments.

El usuario debe:

```text
ajustarlos manualmente
```

o utilizar:

```text
Restablecer segmentación
```

---

### 5.25 Resize draft may temporarily contain invalid segments

Durante la edición de un resize:

```text
pueden existir temporalmente segments fuera del nuevo rango
```

en el estado local/draft del editor.

Esto es válido solamente mientras:

```text
la operación todavía no ha sido persistida
```

Antes del commit:

```text
todos los segments deben ser corregidos
```

o:

```text
la segmentación debe ser restablecida
```

---

### 5.26 Reset segmentation must leave a valid occurrence

La acción:

```text
Restablecer segmentación
```

debe terminar con:

```text
exactamente un Segment 1 inicial
```

con:

```text
start_time = occurrence.start_time
end_time   = occurrence.end_time
```

y status derivado/heredado según las reglas aprobadas.

Después:

```text
volver a validar zona temporal
completed futuro
conflictos
aggregate
```

No asumir que heredar el aggregate garantiza automáticamente un estado válido.

---

### 5.27 Segment split must produce valid fragments

Cuando:

```text
U - A
```

produce fragments, cada fragment debe cumplir individualmente:

```text
start < end
```

Los fragments vacíos:

```text
se descartan
```

No crear records de duración cero únicamente para conservar una estructura.

---

### 5.28 No duplicate occupation after split

Después de dividir un segment:

```text
original
→
left fragment
+
right fragment
```

el interval original no puede permanecer además como tercer blocker ocupante.

La transformación debe reemplazar coherentemente la estructura anterior.

---

### 5.29 Atomicity is mandatory

Una resolución puede involucrar:

```text
source occurrence
target occurrences
segments existentes
segments nuevos
segment statuses
aggregate statuses
conflict_reason
source_occurrence_id
origin_reason
last_conflict_action
```

Todos los cambios pertenecientes a la misma resolución deben ejecutarse:

```text
atómicamente
```

Si un paso falla:

```text
ROLLBACK
```

No dejar:

```text
segments divididos sin source
source creada sin resolver blockers
aggregate viejo con segments nuevos
metadata actualizada sin mutación temporal
```

---

### 5.30 Validation uses final state

No basta con validar cada operación individualmente.

El backend debe comprobar:

```text
el estado final completo que resultaría después de todas las mutaciones
```

antes del commit.

Esto permite resolver correctamente:

```text
swaps
multiple blockers
multiple segments
splits
recortes simultáneos
```

sin rechazar estados intermedios que nunca serán persistidos.

---

### 5.31 UI confirmation never replaces backend validation

Aunque la UI ya haya:

```text
calculado conflictos
mostrado warnings
recibido confirmación
```

el backend debe volver a validar:

```text
estructura
statuses
blockers
temporal zone
authorization
```

antes de persistir.

La UI ayuda al usuario.

El backend protege la integridad.

---

### 5.32 No persistence based only on occurrence envelope

El rango:

```text
Occurrence.start_time–Occurrence.end_time
```

no puede utilizarse como única prueba de ocupación temporal.

Los conflictos reales deben comprobar:

```text
Segment.start_time
Segment.end_time
Segment.status
```

Dos occurrences pueden tener envelopes superpuestos y aun así no tener
segments ocupantes superpuestos.

---

### 5.33 Segment metadata cannot contradict ownership

Todo segment pertenece a:

```text
exactamente una occurrence
```

Una operación no puede mover un segment entre occurrences como efecto
secundario de una resolución.

Si conceptualmente se necesita otro logical occurrence:

```text
crear o utilizar otra occurrence explícitamente
```

---

### 5.34 Runtime segmentation does not automatically become recurring planning

Que una occurrence termine segmentada:

```text
NO
```

autoriza a modificar automáticamente:

```text
GenerationSlot
future occurrences
other days
```

La segmentación de ejecución pertenece únicamente a esa occurrence.

Convertirla en planificación recurrente debe ser:

```text
una acción explícita futura del usuario
```

---

### 5.35 Conflict metadata does not authorize future conflicts

Que una occurrence conserve:

```text
conflict_reason
source_occurrence_id
```

no le concede ni le quita autoridad especial para conflictos futuros.

Cada conflicto nuevo se evalúa mediante:

```text
estado actual
segments actuales
priority
temporal zone
confirmación necesaria
```

No existe una:

```text
conflict lineage lock
```

---

### 5.36 Hard rules summary

No pueden persistirse, incluso con confirmación:

```text
modificaciones a FROZEN_HISTORY

occurrence sin segments

segment.start_time >= segment.end_time

segment fuera del rango general de su occurrence

segments hermanos superpuestos

aggregate incompatible con sus segment statuses

completed segment cuyo endDateTime todavía está en el futuro

pending/in_progress históricos después de reconciliation

occupying overlaps incompatibles sin resolver

resolución parcial de blockers

blockers nuevos modificados sin autorización

fragments de duración cero o negativa

resize que deja segments inválidos

mutaciones parciales no atómicas
```

En cambio, sí pueden realizarse con confirmación cuando la fecha sea editable:

```text
corregir completed

recortar o dividir not_finished

forzar equal/lower priority

corregir una occurrence previamente mal registrada

segmentar una occurrence para representar una interrupción real
```

Principio rector:

> VCS debe dar mucha libertad para corregir la realidad mientras una fecha sea
> editable, pero ninguna confirmación puede autorizar un estado internamente
> contradictorio o estructuralmente imposible.

