# Modelo de planificación — MVP 04

## Nombre de la entrega

**MVP 04 — Motor de planificación por ocurrencias**

Este documento define el modelo temporal y las reglas de dominio que utilizará
el submódulo:

Vatos con Sesos
└── Gestor de hábitos
    └── Plan del día

El MVP 04 se construirá en dos entregas internas:

- MVP 04.0.1 — Motor temporal, modelo y materialización.
- MVP 04.0.2 — Navegación temporal y visualización frontend.

Este documento es normativo para ambas.

---

# Objetivo

El sistema debe permitir automatizar la planificación recurrente sin perder
control sobre cada fecha concreta.

El principio fundamental es:

Automatización para generar el plan
+
independencia de cada fecha materializada
=
planificación flexible sin destruir historial

Una actividad o hábito representa una identidad reutilizable.

Cada vez que dicha actividad o hábito aparece en una fecha concreta se crea
una ocurrencia independiente.

---

# Conceptos principales

El modelo utiliza dos entidades conceptuales principales:

PlanItem
Occurrence

Y una configuración auxiliar:

generationConfig

La relación conceptual es:

PlanItem
│
├── generationConfig
│      └── indica cómo generar ocurrencias futuras
│
└── Occurrences
       ├── fecha A
       ├── fecha B
       ├── fecha C
       └── ...

No existe una entidad ScheduleRule independiente en el MVP 04.

No existe scheduleId.

Las ocurrencias NO necesitan saber mediante qué patrón fueron generadas.

---

# PlanItem

Un PlanItem representa la identidad reutilizable de una actividad o hábito.

Ejemplos:

- Gym
- Trabajo
- Cepillado de dientes
- CCNA / Estudio
- Ponchadura de llanta
- Boda de Efrén

Conceptualmente contiene:

PlanItem
────────────────────────
id
name
kind
activityType / habitType
generationConfig

Los horarios concretos de cada día NO pertenecen directamente al PlanItem.

---

# Identidad del PlanItem

`id` representa identidad técnica.

No debe depender del nombre.

Ejemplo conceptual:

id:
"8f6c2c19-..."

name:
"Gym"

No utilizar:

id: "gym"

como estrategia definitiva de identidad.

Los identificadores legibles utilizados anteriormente en mock data fueron
solamente una simplificación de desarrollo.

---

# Razón para separar id y name

El nombre puede cambiar.

Ejemplo:

Gym
↓
Gimnasio

El id debe permanecer igual.

No se deben modificar todas las ocurrencias históricas cuando únicamente
cambia el nombre visible de un PlanItem.

La relación continúa mediante:

Occurrence.planItemId

---

# Renombrar no significa transformar una entidad

Cambiar:

Gym
→
Gimnasio

puede representar el mismo PlanItem.

Pero cambiar:

Gym
→
Desayuno

probablemente representa otra entidad conceptual.

El sistema no intentará decidir automáticamente si un cambio de nombre
representa una corrección o una actividad completamente distinta.

Esa decisión corresponde al usuario.

---

# kind

Los tipos principales continúan siendo:

activity
habit

Representación visible:

Actividad
Hábito

---

# activityType

En MVP 04 las actividades pueden utilizar:

anchor
periodic
event
unexpected

Representación:

anchor
→ Ancla

periodic
→ Periódica

event
→ Evento

unexpected
→ Imprevista

---

# habitType

En MVP 04 solamente permanece:

scheduled

Representación:

Hábito programado

Los hábitos tipo logro y otros tipos de hábito quedan fuera del alcance actual.

---

# Subactividades

No se implementan subactividades en MVP 04.

Ejemplo:

Gym
├── Pecho
├── Pierna
└── Espalda

queda aplazado.

Durante esta entrega se trabaja solamente con:

Gym

como PlanItem de primer nivel.

---

# generationConfig

`generationConfig` representa únicamente:

La configuración actual que utilizan los algoritmos para generar
ocurrencias futuras.

NO representa:

- una plantilla administrable por el usuario;
- una occurrence;
- una entidad histórica independiente;
- una regla que deba relacionarse mediante id con cada occurrence.

Por tanto:

Occurrence NO contiene scheduleId.

---

# Responsabilidad de generationConfig

generationConfig puede responder preguntas como:

- ¿en qué días se repite?
- ¿desde qué fecha?
- ¿hasta qué fecha?
- ¿es indefinida?
- ¿cuál es su horario general?
- ¿existen horarios distintos según el día?
- ¿se repite cada N días?
- ¿utiliza fechas específicas?

Su único objetivo es permitir generar o regenerar planificación futura.

---

# Historial de reglas

En MVP 04 NO se conservarán versiones históricas independientes de
generationConfig.

No utilizar:

ScheduleRule V1
ScheduleRule V2
ScheduleRule V3

El historial de lo que realmente estuvo planeado queda representado mediante
las Occurrences ya materializadas.

Cuando una configuración cambia para el futuro:

1. Las ocurrencias pasadas permanecen intactas.
2. Las ocurrencias futuras pendientes afectadas pueden eliminarse.
3. generationConfig se actualiza.
4. Las nuevas ocurrencias futuras se vuelven a materializar.

---

# Occurrence

Una Occurrence representa una aparición concreta de un PlanItem en una fecha.

Ejemplo conceptual:

{
    id: "...",
    planItemId: "...",
    date: "2026-08-22",
    startTime: "07:00",
    endTime: "08:00",
    status: "pending"
}

La Occurrence es la unidad principal del calendario.

---

# Propiedades conceptuales de Occurrence

Durante MVP 04 una Occurrence debe representar como mínimo:

id
planItemId
date
startTime
endTime
status

El contrato exacto será definido en:

MOCK_DATA_CONTRACT_MVP_04.md

---

# Occurrence.id

Cada Occurrence debe tener identidad propia.

No utilizar la fecha como id.

No utilizar:

2026-08-22

como identidad.

---

# Razón 1: más de una occurrence por fecha

En el futuro puede existir:

Tomar medicamento
08:00

Tomar medicamento
20:00

Mismo PlanItem.

Misma fecha.

Dos Occurrences.

Por tanto:

planItemId + date

no siempre será suficiente como identidad.

---

# Razón 2: una fecha puede modificarse

Ejemplo:

Boda de Efrén
10 julio

posteriormente cambia a:

11 julio

La occurrence continúa representando la misma aparición aunque haya cambiado
su fecha.

Por tanto:

Occurrence.id = identidad

date = propiedad editable

---

# Relación entre PlanItem y Occurrence

La relación conceptual es:

PlanItem 1 ─────── N Occurrences

Ejemplo:

Gym
│
├── 2026-08-03 05:30–07:15
├── 2026-08-05 05:30–07:15
├── 2026-08-07 05:30–07:15
└── ...

Cada occurrence puede modificarse independientemente.

---

# Representación frontend

Durante la fase frontend puede ser útil representar conceptualmente los datos
agrupados:

{
    id: "...",
    name: "Gym",

    occurrences: {
        "2026-08-03": {...},
        "2026-08-05": {...}
    }
}

Esto NO obliga a que PostgreSQL utilice posteriormente la misma estructura
física.

---

# Representación futura en base de datos

Conceptualmente PostgreSQL probablemente utilizará tablas separadas:

plan_items

id | name | kind | ...

occurrences

id | plan_item_id | date | start_time | end_time | status

Una occurrence corresponderá naturalmente a una fila.

La API podrá reconstruir una estructura agrupada para el frontend.

El modelo conceptual del frontend y el esquema físico de PostgreSQL no tienen
que tener la misma forma.

---

# Horarios planeados

En MVP 04 una occurrence utiliza solamente:

startTime
endTime

No utilizar todavía:

plannedStartTime
plannedEndTime
actualStartTime
actualEndTime

El horario de la occurrence representa el horario actualmente agendado para
esa fecha.

---

# Modificación del horario del día

Si el usuario modifica:

Gym
05:30–07:15

por:

Gym
06:00–08:00

para una fecha concreta, se modifica directamente la occurrence seleccionada.

Esto representa una replanificación del día.

No se registra todavía una diferencia entre:

horario planeado original

y

horario real ejecutado.

---

# Tiempos reales

Los campos:

actualStartTime
actualEndTime

quedan aplazados.

Podrán reconsiderarse en una entrega futura si se desea analizar:

Planeado
vs
Real

No forman parte del MVP 04.

---

# status

Cada occurrence posee su propio estado.

Estados:

pending
in_progress
completed
not_completed
cancelled

Los estados dejan de pertenecer a un objeto `statesByDate`.

Cada occurrence contiene directamente su estado.

---

# Eliminación de statesByDate

La arquitectura anterior utilizaba:

statesByDate: {
    "2026-08-20": "completed",
    ...
}

MVP 04 reemplaza este concepto.

Ahora:

Occurrence del 20
→ completed

Occurrence del 22
→ pending

Occurrence del 24
→ cancelled

El historial queda distribuido naturalmente entre las occurrences.

---

# Estados que bloquean horario

Una occurrence bloquea su intervalo cuando su status es:

pending
in_progress
completed

Conceptualmente:

blocksSchedule = true

---

# Estados que NO bloquean horario

Una occurrence NO bloquea el horario cuando su status es:

cancelled
not_completed

Conceptualmente:

blocksSchedule = false

---

# Razón de cancelled

`cancelled` significa:

La actividad estaba planeada pero fue cancelada.

Debe permanecer en el historial.

Pero su intervalo puede utilizarse para otra actividad.

---

# Razón de not_completed

`not_completed` significa:

La actividad estaba planeada, pero no se realizó.

Ejemplo:

Despertar
04:30

Gym
05:30–07:30

El usuario no despertó a tiempo y decide marcar Gym como:

not_completed

Puede entonces registrar otra actividad dentro del horario anteriormente
ocupado por Gym.

La occurrence de Gym NO desaparece.

Permanece registrada como evidencia de que estaba planeada pero no fue
cumplida.

---

# Regla de bloqueo

Conceptualmente:

function blocksSchedule(occurrence) {
    return (
        occurrence.status !== "cancelled"
        &&
        occurrence.status !== "not_completed"
    );
}

El nombre y la implementación exacta pueden variar.

La responsabilidad debe existir centralizada dentro del dominio.

---

# completed

Una occurrence `completed` representa algo que sí ocurrió.

Continúa bloqueando su intervalo histórico.

No debe permitirse crear silenciosamente otro bloque incompatible encima de
una occurrence completada.

---

# Conflictos temporales

Los conflictos se evalúan exclusivamente entre occurrences que:

1. pertenecen a la misma fecha;
2. bloquean horario;
3. tienen intervalos superpuestos.

La regla temporal continúa siendo:

newStart < existingEnd
AND
newEnd > existingStart

---

# Fechas diferentes

Nunca existe conflicto temporal únicamente por compartir horario si las fechas
son diferentes.

Ejemplo:

Lunes:
Gym 05:30–07:00

Martes:
Trabajo 05:00–08:00

No existe conflicto.

---

# Prioridad de planificación

Las prioridades NO forman parte de PlanItem ni Occurrence como datos
persistentes.

Son reglas del dominio.

Debe existir una estructura equivalente a:

SCHEDULING_PRIORITY = {
    NORMAL: 100,
    EVENT: 200,
    UNEXPECTED: 300
}

Los valores concretos pueden cambiar.

La intención es dejar espacio entre niveles para añadir nuevas prioridades en
el futuro.

---

# Clasificación inicial de prioridades

Habit scheduled
→ NORMAL

Activity anchor
→ NORMAL

Activity periodic
→ NORMAL

Activity event
→ EVENT

Activity unexpected
→ UNEXPECTED

---

# Prioridades futuras

Puede aparecer posteriormente algo como:

POINT_HABIT

con una prioridad intermedia.

Ejemplo conceptual:

NORMAL: 100
POINT_HABIT: 150
EVENT: 200
UNEXPECTED: 300

POINT_HABIT NO se implementa todavía.

El modelo numérico permite insertar nuevas prioridades sin reestructurar todo
el sistema.

---

# Prioridad no significa datos guardados

No almacenar en PostgreSQL ni mock data:

priority: 200

La prioridad debe derivarse del tipo del PlanItem mediante una función del
dominio.

---

# Eventos e imprevistos

Un Event o Unexpected puede intentar ocupar un horario ya reservado.

El sistema no debe superponerlo silenciosamente.

Debe detectar los conflictos.

---

# Override mediante confirmación

Si una occurrence Event o Unexpected tiene prioridad superior a una
occurrence normal:

1. detectar conflicto;
2. informar qué occurrence será afectada;
3. solicitar confirmación;
4. si el usuario confirma:
   - la occurrence normal puede cambiar a cancelled;
   - se crea la nueva occurrence;
5. el resto de las fechas del PlanItem afectado permanecen intactas.

---

# not_completed y overrides

Si la occurrence existente ya está:

not_completed

su horario está disponible.

No necesita cancelarse.

La nueva occurrence puede ocupar ese intervalo.

---

# cancelled y overrides

Si la occurrence existente ya está:

cancelled

su horario está disponible.

La nueva occurrence puede ocupar ese intervalo.

---

# completed y overrides

Una occurrence completada no debe sobrescribirse automáticamente.

Si se intenta registrar retrospectivamente una actividad encima de algo ya
completado, el sistema debe rechazarlo durante MVP 04.

Una futura herramienta de corrección histórica podrá resolver esos casos.

---

# cancelación causada por otra occurrence

En el futuro puede resultar útil registrar:

cancelledByOccurrenceId

para conocer qué evento provocó una cancelación.

Ejemplo:

Trabajo
status: cancelled

cancelledBy:
Boda de Efrén

Este campo NO es obligatorio en MVP 04 salvo que los criterios posteriores lo
incorporen explícitamente.

Debe documentarse como capacidad futura.

---

# Modos de generación

generationConfig puede soportar distintos modos.

Los modos principales previstos para MVP 04 son:

weekly
interval_days
manual_dates
single_date

El contrato exacto será definido posteriormente.

---

# weekly

Utilizado para recurrencia semanal.

Ejemplo:

Gym

Lunes
Miércoles
Viernes

05:30–07:00

Desde:
2026-08-01

Hasta:
2026-12-31

o indefinidamente.

---

# Días ISO

Los días de semana utilizan la convención:

1 = lunes
2 = martes
3 = miércoles
4 = jueves
5 = viernes
6 = sábado
7 = domingo

No utilizar el esquema JavaScript:

0 = domingo

como representación persistente del dominio.

Las conversiones necesarias deben vivir en utilidades.

---

# Horario general

Una generación semanal puede incluir:

defaultStartTime
defaultEndTime

Ejemplo:

07:00
08:00

Los días seleccionados utilizan ese horario inicialmente.

---

# Horarios personalizados por día

generationConfig puede permitir overrides por weekday.

Ejemplo conceptual:

Lunes
07:00–08:00

Miércoles
07:00–08:00

Viernes
09:00–10:30

El formulario puede comenzar copiando el horario general.

El usuario solamente modifica los días especiales.

---

# interval_days

Permite programar algo cada N días.

Ejemplo:

Corte de cabello

Cada:
20 días

Desde:
2026-08-20

El sistema genera occurrences:

20 agosto
9 septiembre
29 septiembre
...

según corresponda.

---

# manual_dates

Permite introducir varias fechas concretas.

Ejemplo:

Doctor

2026-08-25
2026-11-20
2027-02-15

Cada fecha materializa una occurrence.

---

# single_date

Representa una sola aparición.

Puede utilizarse para:

event
unexpected

Ejemplo:

Boda de Efrén
2027-07-10

o:

Ponchadura de llanta
2026-08-20

---

# Actividad ancla

Una actividad `anchor` puede utilizar principalmente recurrencia:

weekly

Puede tener:

- fecha inicial;
- fecha final;
- repetición indefinida;
- días activos;
- horarios diferentes por día.

Ejemplos:

Trabajo
Escuela
Gym
Clase

---

# Actividad periódica

Una actividad `periodic` puede utilizar:

weekly
interval_days
manual_dates

Ejemplos:

CCNA
Corte de cabello
Doctor
Mantenimiento

---

# Evento

`event` representa una actividad conocida con anticipación y asociada a una o
varias fechas concretas.

Ejemplos:

Boda
Concierto
Viaje
Graduación

Puede utilizar principalmente:

single_date
manual_dates

No utiliza recurrencia semanal automática en MVP 04.

---

# Imprevisto

`unexpected` representa algo no planeado que ocurrió o debe insertarse
inmediatamente.

Ejemplos:

Ponchadura
Emergencia
Trámite inesperado

Utiliza normalmente:

single_date

No se repite automáticamente.

La reutilización histórica del mismo PlanItem será posible en el futuro.

---

# Hábito programado

`habit / scheduled` continúa siendo un bloque temporal durante MVP 04.

Puede utilizar principalmente:

weekly

Ejemplos:

Despertar
Cepillarse los dientes
Tomar agua en horario definido

Los hábitos puntuales sin duración quedan aplazados.

---

# Materialización

Materializar significa:

Tomar generationConfig
↓
calcular las fechas correspondientes
↓
crear occurrences concretas

La generación automática nunca sustituye las occurrences existentes.

Las occurrences son la agenda materializada.

---

# Reglas de materialización

Al crear occurrences el algoritmo debe:

1. calcular fechas válidas;
2. resolver horario para cada fecha;
3. comprobar conflictos;
4. crear una occurrence por aparición;
5. asignar identity propia;
6. relacionarla con PlanItem mediante planItemId.

---

# Materialización finita

Si generationConfig tiene:

endDate

el sistema puede generar todas las occurrences hasta esa fecha.

Ejemplo:

Desde:
2026-08-20

Hasta:
2026-12-30

Todas las occurrences correspondientes pueden generarse de una vez.

---

# Materialización indefinida

No se puede materializar infinitamente.

Cuando:

indefinite = true

se utilizará un horizonte de materialización.

---

# Horizonte inicial

Como regla inicial del MVP 04:

si no existe ninguna planificación más lejana, una recurrencia indefinida debe
materializar al menos:

- el resto del mes visible/actual;
- el siguiente mes completo.

Ejemplo:

Fecha actual:
20 agosto

Materializar al menos hasta:
30 septiembre

---

# Extensión del horizonte

Si aparece planificación futura más lejana, puede extenderse la materialización
de recurrencias indefinidas hasta el final del mes correspondiente.

Ejemplo:

Existe una boda:

10 julio 2027

Las recurrencias indefinidas pueden extenderse hasta:

31 julio 2027

---

# Horizonte no es una fecha final real

Una recurrencia indefinida continúa siendo conceptualmente infinita.

La última occurrence actualmente materializada NO significa:

fin de la repetición.

generationConfig.indefinite debe conservar esa intención.

---

# Edición de una occurrence

El botón de edición debe poder modificar una occurrence concreta.

El primer alcance de edición es:

Solo esta fecha

Esto permite cambiar:

- date;
- startTime;
- endTime;

de la occurrence seleccionada.

No modifica otras occurrences.

No modifica generationConfig.

---

# Editar solo esta fecha

Ejemplo:

Gym

Miércoles 20
05:30–07:00

Se modifica únicamente a:

06:00–08:00

La occurrence del miércoles cambia.

Las demás occurrences de Gym permanecen intactas.

---

# Editar solo esta semana

La semana lógica utiliza:

lunes → domingo

Al seleccionar:

Aplicar solo esta semana

el sistema debe obtener el rango:

lunes de la semana seleccionada
↓
domingo de la misma semana

Solo se modifican las occurrences del mismo PlanItem dentro de ese rango.

generationConfig general permanece intacta.

---

# Editar de aquí en adelante

Cuando el usuario selecciona:

Aplicar de aquí en adelante

debe modificarse la configuración futura del PlanItem.

Principio:

pasado
→ no tocar

futuro pendiente
→ puede regenerarse

---

# Regeneración futura

Al cambiar generationConfig desde una fecha:

1. conservar occurrences históricas;
2. conservar occurrences ya realizadas;
3. identificar occurrences futuras pendientes afectadas;
4. eliminarlas de la planificación futura;
5. actualizar generationConfig;
6. materializar nuevas occurrences según la nueva configuración.

---

# Qué se considera historia

Como regla inicial:

Las occurrences con fecha anterior a la fecha de aplicación del cambio se
consideran historial y no deben reescribirse automáticamente.

También deben preservarse cuidadosamente occurrences que ya tengan información
histórica significativa.

---

# Futuro pendiente

Una occurrence futura con:

status = pending

puede eliminarse y regenerarse cuando cambia la planificación futura.

Esto evita llenar el historial con:

cancelled
cancelled
cancelled
...

cuando en realidad el usuario simplemente cambió su rutina futura.

---

# Cancelar no es replanificar

Si una actividad estaba prevista para hoy y el usuario decide no hacerla:

status = cancelled

La occurrence permanece.

Si el usuario modifica su patrón para dentro de tres meses:

las antiguas occurrences futuras pendientes pueden regenerarse.

Son operaciones semánticamente diferentes.

---

# Pausar planificación

Pausar significa:

dejar temporalmente de generar nuevas occurrences.

Las occurrences históricas permanecen.

El mismo PlanItem continúa existiendo.

Posteriormente puede reactivarse utilizando:

el mismo id.

---

# Detener desde una fecha

Detener significa:

la planificación ya no debe continuar a partir de determinada fecha.

Las occurrences anteriores permanecen.

Las occurrences futuras pendientes posteriores pueden retirarse.

generationConfig debe reflejar que ya no continúa.

---

# Reactivar

Una actividad pausada o detenida puede reactivarse posteriormente.

Debe reutilizar:

el mismo PlanItem.id

No debe crearse automáticamente otro PlanItem solo porque haya existido una
pausa.

Ejemplo:

Trabajo
↓
Vacaciones
↓
Trabajo nuevamente

continúa siendo el mismo PlanItem.

---

# Historial dinámico futuro

En una entrega futura, al escribir un nombre, la aplicación podrá buscar
PlanItems existentes.

Ejemplo:

Usuario escribe:

Poncha...

Sistema recomienda:

Ponchadura de llanta

Al seleccionarlo:

NO se crea un PlanItem nuevo.

Se reutiliza el id existente y se genera una nueva occurrence.

Esta función NO se implementa en MVP 04.

El modelo debe permitirla.

---

# Semanas

La semana lógica utiliza:

lunes
↓
domingo

Se utilizará la convención ISO como referencia conceptual.

No almacenar:

week_1
week_2
week_3

dentro de los datos.

La semana puede derivarse a partir de `date`.

---

# Meses y semanas

Una semana puede atravesar dos meses.

Ejemplo:

Lunes 31 agosto
↓
Domingo 6 septiembre

Continúa siendo una sola semana lógica.

La navegación mensual no altera esa definición.

---

# División visual futura

La matriz mensual podrá mostrar divisiones visuales entre semanas.

Ejemplo:

SÁB 1 | DOM 2 || LUN 3 ... DOM 9 || LUN 10 ...

El primer bloque puede ser parcial porque el mes puede comenzar a mitad de una
semana.

Esto no modifica el modelo de datos.

---

# Estadísticas futuras

El modelo debe permitir posteriormente calcular:

Por día:
- porcentaje completado.

Por semana:
- porcentaje agregado.

Por mes:
- porcentaje total.

También deberá permitir:

- rachas;
- gráficas;
- premios;
- evolución histórica.

Estas funciones NO se implementan en MVP 04.

---

# Porcentaje diario futuro

Conceptualmente podrá calcularse mediante occurrences de una fecha.

Ejemplo:

10 occurrences consideradas
8 completed

→ 80%

Todavía NO se define:

- tratamiento estadístico de cancelled;
- tratamiento estadístico de not_completed;
- tratamiento de unexpected;
- denominador exacto.

Estas reglas se definirán cuando se implemente el módulo estadístico.

---

# Navegación temporal

El modelo debe permitir mantener conceptualmente:

selectedDate
visibleMonth

Estos valores son estado de interfaz.

NO pertenecen a PlanItem ni Occurrence.

---

# selectedDate

Representa la fecha actualmente observada.

El frontend utilizará selectedDate para resolver:

qué occurrences mostrar en Plan del día.

---

# visibleMonth

Representa el mes actualmente mostrado en la matriz.

Puede cambiar independientemente mediante navegación.

---

# Estado de interfaz

No almacenar dentro de PlanItem u Occurrence:

selectedDate
visibleMonth
showAllMonthRecords
selectedPlanItemId
selectedOccurrenceId
dialogMode

Son estado del frontend.

---

# Regla de vista diaria

Cuando el modo filtrado esté activo:

mostrar occurrences cuya:

date === selectedDate

La lista debe ordenar por:

startTime

---

# Vista mensual completa

Cuando el usuario active el futuro modo:

Mostrar todo el mes

la interfaz podrá mostrar PlanItems que tengan al menos una occurrence dentro
del visibleMonth.

Los detalles visuales se definirán en FRONTEND_MVP_04.md.

---

# Casillas no aplicables

Cuando un PlanItem no tenga occurrence para una fecha concreta:

esa celda representa:

No programado

No representa:

pending
cancelled
not_completed

Debe mostrarse posteriormente como una casilla deshabilitada y sin símbolo.

No debe existir una occurrence ficticia únicamente para dibujar esa celda.

---

# Regla importante

Ausencia de occurrence
≠
pending

`pending` significa:

La occurrence existe y está pendiente.

Ausencia significa:

Ese PlanItem no estaba programado para esa fecha.

---

# Persistencia durante MVP 04

MVP 04 continúa utilizando únicamente memoria.

Todavía no se implementa:

- Flask;
- PostgreSQL;
- API;
- Supabase;
- localStorage.

Pero el modelo debe prepararse para su futura separación relacional.

---

# Arquitectura objetivo futura

Conceptualmente:

Frontend
↓
API
↓
Backend
↓
PostgreSQL

Tablas probables:

plan_items
occurrences

generationConfig puede almacenarse posteriormente:

- dentro de plan_items;
- mediante columnas específicas;
- mediante otra tabla normalizada;

según la arquitectura backend elegida.

Esa decisión física NO corresponde al MVP 04.

---

# Lo que NO debe existir

No implementar como entidad independiente:

ScheduleRule

No implementar:

scheduleId
scheduleVersionId

dentro de Occurrence.

No guardar week_1, week_2, etc.

No utilizar name como id.

No utilizar date como occurrenceId.

No guardar priority dentro de los registros.

No generar occurrences infinitas.

No conservar estados mediante statesByDate.

---

# Resumen del dominio MVP 04

PlanItem
──────────────────────
Identidad reutilizable.

Occurrence
──────────────────────
Aparición concreta del PlanItem en una fecha.

generationConfig
──────────────────────
Configuración actual utilizada por los algoritmos para generar futuro.

status
──────────────────────
Qué ocurrió o está ocurriendo con una occurrence.

priority
──────────────────────
Regla derivada del dominio, no dato persistido.

---

# Regla central

La planificación automática crea occurrences.

Después de creadas:

cada occurrence es independiente.

Esto permite:

- modificar un solo día;
- modificar una semana;
- cambiar el futuro;
- conservar el pasado;
- pausar;
- reactivar;
- cancelar;
- registrar no realizados;
- registrar eventos;
- registrar imprevistos;
- reutilizar una misma actividad durante años.

---

# Principio final

El sistema debe favorecer simultáneamente:

AUTOMATIZACIÓN

y

CONTROL INDIVIDUAL.

La generación evita planificar manualmente cada fecha.

Las occurrences permiten modificar cada fecha sin destruir el resto de la
planificación.

Ese equilibrio constituye la base del motor temporal de Vatos con Sesos.