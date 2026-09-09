Sí. Leí con cuidado todo tu `current_fix`, y hay una idea central que sí compraría casi completa:

> **La unidad que realmente importa para el calendario no debe ser “la actividad con muchos estados por fecha”, sino la aparición concreta de esa actividad en una fecha concreta.**

Eso cambia bastante el modelo que veníamos imaginando, pero para bien. Tu necesidad original ya apuntaba a separar lo planeado de lo que ocurrió realmente y a conservar historial por fecha.  En tu nueva propuesta además ya aparecen explícitamente edición por semana o “de aquí en adelante”, eventos futuros, imprevistos, cancelaciones y horarios diferentes por fecha.  

Pero **no implementaría literalmente `week_1`, `week_2`, ..., `week_52` ni guardaría todo dentro de un gran array de una actividad**. Podemos conservar prácticamente todo lo que quieres con una estructura más sólida.

# El cambio fundamental que propongo

A partir del MVP 04 tendremos **tres conceptos**, aunque el usuario nunca tenga que pensar en ellos como “plantillas”.

```text
PLAN ITEM
¿Qué es?
        │
        ├── Gym
        ├── Trabajo
        ├── Boda de Efrén
        └── Ponchadura
        │
        ▼
SCHEDULE / REGLA
¿Cómo debe aparecer?
        │
        ▼
OCCURRENCES
¿Qué quedó realmente programado cada fecha?
```

En español conceptual:

```text
Registro
   ↓
Regla de programación
   ↓
Apariciones programadas
```

Y **la aparición (`occurrence`) será la pieza verdaderamente importante**.

---

# 1. `PlanItem`: identidad de la cosa

Por ejemplo:

```js
{
    id: "gym",
    name: "Gym - Pecho",
    recordKind: "activity",
    recordSubtype: "anchor"
}
```

Aquí ya **no guardaríamos el horario**.

Porque acabas de identificar correctamente el problema:

> Gym puede ser a las 5:30 un lunes y a las 7:00 otro día o la semana siguiente.

El horario no pertenece realmente a “Gym”.

Pertenece a:

> **Gym del 20 de agosto de 2026.**

Ese descubrimiento es importantísimo.

---

# 2. `Schedule`: cómo se generan fechas

Aquí quiero aclarar algo porque esto elimina nuestra discusión sobre “plantillas”.

**No necesitamos plantillas.**

Una plantilla sería algo como:

> “Rutina de gimnasio #1, reutilízala cuando quieras”.

No quiero eso tampoco.

Pero sí necesitamos conservar **una regla de repetición**.

¿Por qué?

Porque si marcas:

```text
Salir a correr
Sábados y domingos
Repetir indefinidamente
```

es matemáticamente imposible almacenar todas las fechas:

```text
2026
2027
2028
...
∞
```

En algún sitio debemos conservar:

```text
se repite sábados y domingos
```

para poder seguir generando apariciones futuras.

Eso **no es una plantilla**. Es una propiedad de programación de ese registro.

Podría existir internamente:

```js
{
    id: "schedule-running-01",
    planItemId: "running",

    recurrenceMode: "weekly",

    startDate: "2026-08-20",
    endDate: null,

    weekdays: [6, 7],

    defaultStartTime: "07:00",
    defaultEndTime: "08:00",

    indefinite: true
}
```

El usuario jamás tendría que pensar:

> “Estoy creando una plantilla”.

Para él simplemente sería:

> Repetir sábados y domingos indefinidamente.

---

# 3. `Occurrence`: aquí ocurre la magia

Por cada fecha materializada:

```js
{
    id: "occ-9182",
    planItemId: "running",
    scheduleId: "schedule-running-01",

    date: "2026-08-22",

    plannedStartTime: "07:00",
    plannedEndTime: "08:00",

    status: "pending"
}
```

Y otra:

```js
{
    id: "occ-9183",
    planItemId: "running",
    scheduleId: "schedule-running-01",

    date: "2026-08-23",

    plannedStartTime: "07:00",
    plannedEndTime: "08:00",

    status: "completed"
}
```

Y aquí ocurre exactamente lo que estabas buscando.

Si el domingo quieres correr a otra hora:

```js
{
    date: "2026-08-23",
    plannedStartTime: "09:00",
    plannedEndTime: "10:00"
}
```

**Solo modificamos esa aparición.**

El sábado queda intacto.

La semana anterior queda intacta.

La siguiente queda intacta.

---

# Esto elimina `statesByDate`

Ahorita teníamos conceptualmente:

```js
statesByDate: {
    "2026-08-20": "completed",
    "2026-08-21": "cancelled"
}
```

Con la nueva arquitectura ya no tiene mucho sentido.

Porque cada aparición ya posee:

```js
{
    date: "2026-08-20",
    status: "completed"
}
```

Entonces:

```text
antes

Actividad
 └── statesByDate
      ├── fecha
      ├── fecha
      └── fecha
```

se transforma en:

```text
ahora

Actividad
 ├── Occurrence 20 agosto → completed
 ├── Occurrence 22 agosto → pending
 └── Occurrence 24 agosto → cancelled
```

**Esto me gusta muchísimo más para lo que quieres construir.**

Además, el propio documento que planteaste antes ya detectaba que los horarios planeados y reales cambian por día y que se necesita conservar historial. 

---

# Entonces sí tendremos información repetida

Y está bien.

Por ejemplo:

```text
365 días
×
15 registros/día
```

son miles de filas anuales.

Eso para PostgreSQL es absolutamente normal.

El problema no será almacenar miles o decenas de miles de apariciones.

Lo que sí sería un problema conceptual es meter todo dentro de:

```js
actividad.dates[...]
```

y después tener un objeto gigantesco que tenemos que modificar entero.

En PostgreSQL eventualmente queremos:

```text
1 occurrence
=
1 fila
```

Eso es justamente para lo que una base de datos relacional es buena.

---

# Tu idea de las semanas: aquí haría una corrección importante

No guardaría:

```text
week_1
week_2
...
week_52
```

por varios motivos.

Primero, algunos años tienen **53 semanas**.

Segundo:

```text
week_1
```

no significa nada sin el año.

Necesitarías por lo menos:

```text
2026-W34
```

Y tercero, ni siquiera necesitamos almacenar la semana.

## Guardamos la fecha real

```text
2026-08-20
```

y de ella podemos derivar:

```text
Año ISO: 2026
Semana ISO: 34
Día ISO: 4
```

cuando necesitemos estadísticas.

---

# Qué semana usaría

Aquí sí tomaría una decisión formal:

## **ISO 8601**

Semana:

```text
Lunes → Domingo
```

Eso nos servirá para:

* “esta semana”;
* estadísticas semanales;
* edición semanal;
* comparar semanas;
* agrupar historial.

Y algo muy importante: una semana puede atravesar meses.

Eso **no representa ningún problema** porque la occurrence almacena fecha, no “mes”.

Por ejemplo:

```text
Semana ISO 36

Lun 31 agosto
Mar 1 septiembre
Mié 2 septiembre
...
Dom 6 septiembre
```

Perfectamente válido.

---

# Pero tu captura de Google Sheets no representa exactamente eso

En la captura de abril veo bloques como:

```text
1 2 3 4 5 6 7

8 9 10 11 12 13 14
```

Aunque el día 1 caiga miércoles.

Eso es más bien:

> **bloques de siete días del mes**

y no una semana calendario estándar.

Visualmente podemos hacerlo si te gusta.

Pero **no utilizaría esos bloques como nuestra definición de semana**.

Yo separaría:

```text
LÓGICA
Semana ISO lunes-domingo

VISUAL
Podemos dibujar divisiones como queramos
```

Mi recomendación visual, sin embargo, sería que el borde grueso aparezca cada lunes.

Así agosto puede comenzar:

```text
SÁB 1 | DOM 2 || LUN 3 ... DOM 9 || LUN 10 ...
```

El primer bloque es parcial porque el mes empezó en sábado.

Eso es más coherente con las semanas que luego utilizaremos para:

> Aplicar solo esta semana.

---

# Ahora viene tu idea más importante: materializar las fechas

Aquí estamos bastante de acuerdo.

Supongamos:

```text
Salir a correr

Sábado
Domingo

07:00–08:00

Desde:
20 agosto 2026

Hasta:
30 diciembre 2026
```

El algoritmo genera:

```text
22 ago 07:00–08:00
23 ago 07:00–08:00
29 ago 07:00–08:00
30 ago 07:00–08:00
...
26 dic
27 dic
```

**Cada una se vuelve una occurrence independiente.**

Eso es justamente lo que quieres.

---

# Horarios diferentes por día

También queda solucionado.

En el formulario podríamos tener:

```text
Horario general

Inicio: [07:00]
Final:  [08:00]

Repetir
☑ Lunes
☐ Martes
☑ Miércoles
☐ Jueves
☑ Viernes
```

Y debajo:

```text
Personalizar horarios por día

Lunes
[07:00] → [08:00]

Miércoles
[07:00] → [08:00]

Viernes
[09:00] → [10:30]
```

Al principio copia automáticamente el horario general.

El usuario únicamente cambia los días especiales.

Esto encaja exactamente con la necesidad de turnos diferentes que ya habías planteado anteriormente. 

---

# Actividad ancla

La interfaz específica podría ofrecer:

```text
Actividad ancla

Nombre
Horario base

Repetición:
☑ días de semana

Desde:
[fecha]

Hasta:
○ fecha determinada
○ repetir indefinidamente

Personalizar horario por día
```

Es la candidata natural para recurrencia semanal.

---

# Actividad periódica

Aquí tu propuesta también me parece apropiada.

Podemos ofrecer **modos de programación**, no todos activados a la vez:

```text
Repetición:

○ Días específicos de la semana
○ Cada N días
○ Fechas manuales
```

Por ejemplo:

```text
Cada:
[12] días
```

o:

```text
Próximas fechas

+ 01/09/2026
+ 14/09/2026
+ 03/10/2026
```

Eso resuelve cosas como:

* corte de cabello;
* mantenimiento;
* doctor;
* limpieza dental.

Tu requisito histórico justamente contemplaba actividades periódicas que pueden definirse por frecuencia o agendarse manualmente. 

---

# Agregamos `event`

Sí.

Nuestra clasificación queda:

```text
activity
├── anchor
├── periodic
├── event
└── unexpected

habit
└── scheduled
```

`event` faltaba y tu ejemplo demuestra por qué.

```text
Boda de Efrén
10 julio 2027
09:00–23:59
```

Eso no es:

* periódico;
* ancla;
* imprevisto.

Es un evento programado.

---

# Evento

Por ahora permitiría:

```text
Nombre
Fecha
Inicio
Final
```

y también varias fechas manuales si se desea:

```text
Viaje Acapulco

1 diciembre
2 diciembre
3 diciembre
4 diciembre
5 diciembre
```

No necesita recurrencia automática inicialmente.

---

# Imprevisto

Aquí:

```text
una única fecha
+
horario
```

No se repite automáticamente.

Pero queda registrado como el mismo **tipo conceptual**.

Entonces más adelante podremos preguntar:

> ¿Cuántas ponchaduras tuve este año?

aunque cada una sea una occurrence distinta.

Eso conserva exactamente la intención que escribiste: registrar imprevistos porque su repetición histórica puede revelar patrones. 

---

# Tu idea de las prioridades también me gusta, pero la cambiaría un poquito

Tu analogía con `z-index` está muy bien para entenderlo:

```text
ancla      10
periódica  10
evento     20
imprevisto 30
```

Pero **no almacenaría esos números dentro de cada occurrence**.

Serían una regla del dominio:

```js
getSchedulingPriority(recordSubtype)
```

Conceptualmente:

```text
scheduled habit  → NORMAL
anchor           → NORMAL
periodic         → NORMAL
event            → OVERRIDE
unexpected       → OVERRIDE_HIGH
```

Porque si algún día cambiamos:

```text
event = 30
```

no quiero actualizar diez mil registros guardados.

---

# Y no permitiría que simplemente se superpongan

Aquí pondría una UX un poco más cuidadosa.

Si intentas registrar:

```text
Trabajo
08:00–17:00

Boda
12:00–23:59
```

en lugar de meter la boda silenciosamente encima, mostramos:

> Este evento entra en conflicto con Trabajo (08:00–17:00).
>
> Si continúas, Trabajo será cancelado únicamente para esta fecha.

Entonces:

```text
Boda        → pending
Trabajo     → cancelled
```

**solo ese día.**

No tocamos:

```text
Trabajo del lunes siguiente
Trabajo del martes siguiente
...
```

Eso preserva completamente el historial.

---

# Y acabas de identificar otra regla correcta

Una occurrence:

```text
status: cancelled
```

**no bloquea el horario.**

Así:

```text
Trabajo
14:00–18:00
CANCELLED
```

permite:

```text
Doctor
15:00–16:00
```

Eso debe formar parte formal de la detección de conflictos.

---

# Pero no borraría físicamente la cancelada

Esto es importante.

Si quieres estadísticas futuras:

> ¿Cuántos planes tuve que cancelar?

necesitamos saber que existió.

Entonces:

```text
Cancelar ≠ eliminar
```

Una actividad cancelada permanece como occurrence:

```js
{
    date: "...",
    status: "cancelled"
}
```

pero deja libre el intervalo para planificación.

---

# Incluso podemos registrar qué provocó la cancelación

Más adelante:

```js
{
    status: "cancelled",
    cancellationReason: "overridden",
    cancelledByOccurrenceId: "boda-efren-..."
}
```

Entonces podremos saber:

> Trabajo fue cancelado por Boda de Efrén.

Eso sí lo dejaría diseñado desde ahora, aunque quizá no implementemos todos esos campos todavía.

---

# “Aplicar esta semana” ahora tiene una definición perfecta

Aquí la architecture de occurrences funciona extremadamente bien.

Supongamos:

```text
Gym

Patrón:
L X V
05:30–07:00
```

Esta semana quieres:

```text
L J
06:00–07:30
```

Seleccionas:

> Aplicar solo esta semana

Entonces obtenemos la semana ISO correspondiente:

```text
lunes → domingo
```

y modificamos **solo las occurrences dentro de ese intervalo**.

La regla general sigue:

```text
L X V
05:30
```

para las semanas posteriores.

---

# “Aplicar de aquí en adelante”

Aquí hay una razón por la que **no podemos borrar por completo la regla de recurrencia**.

Seleccionas:

> Aplicar desde 24 agosto en adelante

La regla anterior se cierra:

```text
hasta 23 agosto
```

y empieza una nueva configuración:

```text
desde 24 agosto
L J
06:00–07:30
```

Las occurrences futuras materializadas desde el 24:

* se eliminan/recalculan si siguen `pending`;
* se vuelven a generar bajo la nueva regla.

Las pasadas:

**jamás se tocan.**

---

# Entonces `scheduleVersions` no desaparece completamente

Pero cambia su significado.

No representa:

> “Plantillas que el usuario debe administrar”.

Representa:

> **Historial interno de cambios de la regla de programación.**

El usuario no necesita conocer ese concepto.

Para él existe simplemente:

```text
Gym
→ Editar
→ Aplicar de aquí en adelante
```

Internamente nosotros necesitamos saber cuál era el patrón anterior para conservar el pasado y cuál es el nuevo.

---

# De hecho, la arquitectura final que propongo es ésta

```text
PlanItem
│
│ identidad
│
├── name
├── recordKind
└── recordSubtype
        │
        │
        ├──────────────────────┐
        ▼                      ▼
 ScheduleRule              Occurrence
 cómo se repite            qué existe ese día
        │                      │
        ├─ inicio              ├─ date
        ├─ fin                 ├─ plannedStartTime
        ├─ weekdays            ├─ plannedEndTime
        ├─ intervalo           ├─ status
        ├─ horarios/día        └─ ...
        └─ indefinite
```

Y si cambia una regla:

```text
PlanItem
    │
    ├── ScheduleRule V1
    │       ↓
    │    occurrences pasadas
    │
    └── ScheduleRule V2
            ↓
         occurrences futuras
```

Ésta sería mi decisión arquitectónica.

---

# Tu regla de materialización futura

También podemos conservar tu idea.

Para una regla indefinida no generamos infinito.

Definimos:

```text
materialization horizon
```

Por ejemplo:

### Caso sin nada futuro

Hoy:

```text
20 agosto
```

como mínimo materializamos hasta:

```text
30 septiembre
```

Es decir:

> resto de este mes + siguiente mes completo.

### Aparece Boda de Efrén

```text
10 julio 2027
```

podemos extender todas las recurrencias indefinidas hasta:

```text
31 julio 2027
```

### Aparece viaje en diciembre 2027

extendemos hasta:

```text
31 diciembre 2027
```

Esto reproduce exactamente tu regla. 

Y lo mejor es que seguimos conservando:

```text
indefinite: true
```

para poder continuar extendiendo el horizonte en el futuro.

---

# ¿Será demasiada información?

Para este proyecto: **no me preocupa**.

Y prefiero muchísimo:

```text
50 000 occurrences claras
```

a:

```text
500 objetos súper comprimidos
```

que después sean una pesadilla de modificar.

Cuando lleguemos a PostgreSQL, este tipo de estructura es natural.

Podremos indexar:

```text
date
plan_item_id
status
```

y consultar rápidamente.

La optimización viene después.

Tu prioridad actual debe ser:

> modelo correcto + comportamiento predecible.

Ahí estoy contigo.

---

# Ahora la navegación mensual

Tu propuesta es perfectamente realizable.

Mantendremos dos variables conceptuales:

```js
selectedDate
visibleMonth
```

---

# Navegación por día

En escritorio:

```text
click MAR 18
```

produce:

```text
selectedDate = 18 agosto
```

y muestra las occurrences de esa fecha.

Compacto:

```text
← día anterior

→ día siguiente
```

más el selector de fecha que hablamos.

---

# Navegación por mes

Desktop:

```text
‹                  MATRIZ                   ›
```

como dibujaste.

Compacto:

```text
‹      Agosto de 2026      ›
```

El mes además puede ser clicable.

Yo utilizaría preferentemente:

```html
<input type="month">
```

para selección de mes y fallback a un selector de fecha si el navegador no lo soporta adecuadamente.

---

# Aquí cambiaría una pequeña parte de tu regla

Tú propusiste:

> Al avanzar al siguiente mes, seleccionar día 1.
>
> Al retroceder, seleccionar último día.

Eso funciona técnicamente.

Pero con **ojo cerrado**, puede provocar:

```text
Avanzo a diciembre porque hay actividades.
↓
Selecciono 1 diciembre.
↓
No hay nada el día 1.
↓
Plan del día aparece vacío.
```

aunque tal vez la actividad esté el 20.

Yo haría algo un poco mejor:

### Al avanzar con flecha de mes

selecciona:

> **la primera fecha con occurrences dentro del siguiente mes con planificación.**

### Al retroceder

selecciona:

> **la última fecha con occurrences del mes anterior con planificación.**

Así:

```text
Agosto
   ↓
›
   ↓
Diciembre
12 diciembre ← primera actividad
```

Y:

```text
Julio
   ↓
‹
   ↓
Marzo
27 marzo ← última actividad
```

Esto hace que esas flechas sean realmente:

> **Anterior / siguiente mes con planificación**

---

# Selector manual de mes o fecha

Aquí sí permitimos navegar libremente.

Si eliges:

```text
octubre 2029
```

y está vacío:

```text
Plan del día
────────────
No hay registros programados.
```

Eso coincide con lo que quieres.

---

# Flechas deshabilitadas

Si no existe nada anterior:

```text
‹ disabled
```

y podemos mostrar:

> No hay planificación anterior.

Si no existe nada posterior:

```text
› disabled
```

excepto cuando existen reglas `indefinite`.

Porque si tenemos:

```text
Salir a correr
indefinite = true
```

**sí existe planificación futura conceptualmente**, aunque todavía no hayamos materializado ese mes.

En ese caso al avanzar podemos materializar el siguiente mes y mostrarlo.

Este detalle es importante.

---

# Ojo cerrado

Estado inicial siempre:

```text
showAllMonthRecords = false
```

Mostramos occurrences del:

```text
selectedDate
```

Nada más.

---

# Ojo abierto

Aquí confirmo lo que dijiste.

Mostramos todos los `PlanItem` que tienen al menos una occurrence dentro del mes visible.

Las fechas donde ese PlanItem no ocurre:

```text
gris
sin símbolo
disabled
```

Perfecto.

---

# Los empalmes entre diferentes días no importan

Correcto.

Si:

```text
Lunes
Gym 05:30

Martes
Trabajo 05:00
```

en modo mensual ambas filas pueden aparecer juntas.

**No existe ningún conflicto.**

El conflicto siempre se evalúa:

```text
MISMA FECHA
+
INTERVALOS
```

Nunca entre días diferentes.

---

# Orden en modo ojo abierto

Aquí haría una regla determinista.

Primero:

> registros que sí existen en `selectedDate`, ordenados por su hora de ese día.

Después:

> registros que solo existen en otras fechas del mes.

Éstos pueden ordenarse por su siguiente occurrence más cercana.

Así el Plan del día seleccionado siempre conserva prioridad visual.

---

# Estado cancelado en ojo cerrado

Esto es otro detalle que quiero fijar.

Una occurrence cancelada **sí pertenece a ese día**.

Por lo tanto no la escondería automáticamente.

Ejemplo:

```text
08:00 Trabajo     CANCELLED
09:00 Boda        PENDING
```

Eso explica qué ocurrió con el plan.

Y `Trabajo`:

* aparece;
* se ve cancelado;
* no bloquea horario.

Excelente para historial.

---

# La interfaz de registro ahora sí debe cambiar bastante

Y tienes razón:

> cada subtipo necesita reglas diferentes.

Pero **no crearía cuatro `<dialog>` distintos**.

Usaría el mismo formulario con secciones dinámicas.

```text
¿Qué quieres registrar?

Actividad
└── Ancla
└── Periódica
└── Evento
└── Imprevisto

Hábito
└── Programado
```

Después cambia la sección inferior dependiendo de la elección.

---

# Cómo lo organizaría

La única lista que quiero dejar fijada desde ahora es ésta:

| Tipo                  | Programación propuesta                                                     | Choques                                                               |
| --------------------- | -------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| **Ancla**             | semanal, rango de fechas o indefinida, horario general + overrides por día | no puede solaparse con prioridad normal                               |
| **Periódica**         | semanal / cada N días / fechas manuales                                    | no puede solaparse con prioridad normal                               |
| **Evento**            | fecha o fechas concretas                                                   | puede desplazar registros normales con confirmación                   |
| **Imprevisto**        | una occurrence en la fecha seleccionada                                    | puede desplazar registros normales con confirmación y mayor prioridad |
| **Hábito programado** | semanal/rango como alarma temporal                                         | por ahora se comporta como prioridad normal                           |

Eso deja muchísimo más clara la aplicación.

---

# Eliminación

También cambiaría el significado.

En un planificador con historial:

> **eliminar físicamente debe ser excepcional.**

El botón 🗑 terminará ofreciendo cosas como:

```text
Cancelar solo esta aparición

Cancelar esta semana

Detener desde esta fecha

Pausar repetición
```

No necesitamos implementarlo todavía.

Pero ya sabemos cómo debe funcionar.

Tu propuesta de “esta semana / de aquí en adelante” encaja perfectamente con esta separación. 

---

# Una observación sobre “pausar”

Yo distinguiría:

```text
CANCELAR OCCURRENCE
```

de:

```text
PAUSAR SCHEDULE
```

Cancelar:

> El martes 25 no voy al Gym.

Pausar:

> Dejo de generar Gym temporalmente.

Detener:

> Gym ya no forma parte de mi rutina desde esta fecha.

Son tres acciones distintas.

Después las diseñaremos.

---

# Entonces, ¿cambiamos el MVP 04?

Sí.

Y bastante.

**No llenaría todavía ninguno de esos documentos que ya creaste.**

Déjalos en su sitio, pero vamos a reescribirlos con esta arquitectura.

Ahora el MVP 04 ya no debería llamarse simplemente:

> Visualización por día y planificación versionada.

Yo lo llamaría:

# **MVP 04 — Motor de planificación por ocurrencias**

Porque eso es realmente lo que estamos construyendo.

Incluye:

```text
PlanItem
+
ScheduleRule
+
Occurrence
+
materialización
+
selección por fecha
+
navegación mensual
+
filtro mensual
```

Y será probablemente el cambio estructural más importante antes de PostgreSQL.

---

# Pero no le daría todo a Codex de una sola vez

Aquí sí quiero proteger el avance.

Mantendría **MVP 04 como una sola meta**, pero la construiría en dos entregas internas.

### MVP 04-A — Motor temporal

Migrar:

```text
modelo actual
↓
PlanItem
ScheduleRule
Occurrence
```

y conseguir:

* generación finita;
* generación indefinida con horizonte;
* recurrencia semanal;
* horarios por día;
* cada N días;
* fechas manuales;
* evento;
* imprevisto;
* validaciones por occurrence;
* estados por occurrence.

Sin cambiar demasiado la interfaz mensual todavía.

### MVP 04-B — Navegación y visualización

Implementar:

* click en día;
* calendario;
* ojo;
* filas filtradas;
* casillas disabled;
* semanas visuales;
* navegación inteligente de meses;
* flechas;
* selector de mes;
* edición “esta semana / de aquí en adelante”.

Al cerrar **04-B** decimos:

```text
MVP 04 ✅
```

Esto no es caminar sin rumbo. Es evitar pedirle a Codex que cambie simultáneamente el motor y toda la interfaz sin un checkpoint intermedio.

---

# Y tus documentos actuales

Por las capturas veo que ya tienes creados:

```text
CURRENT_TASK.md
FRONTEND_MVP_04.md
MOCK_DATA_CONTRACT_MVP_04.md
SCHEDULE_MODEL_MVP_04.md
ACCEPTANCE_CRITERIA_MVP_04.md
```

Perfecto.

**No los archives ni los borres.**

Los vamos a llenar/reemplazar una vez que terminemos esta discusión.

`SCHEDULE_MODEL_MVP_04.md` ahora se vuelve todavía más importante, porque será el documento donde dejaremos formalmente:

```text
PlanItem
ScheduleRule
Occurrence
materialization horizon
ISO weeks
overrides
priorities
cancelled conflicts
edit scopes
```

Y conservaría tus notas de `planeacion/` tal como están: ahí está precisamente la evolución del razonamiento que nos llevó a esta arquitectura.

---

# Mi decisión final sobre la estructura

Yo **sí cambio la arquitectura actual** y tomo gran parte de tu propuesta.

Pero con esta modificación:

```text
NO:

Actividad
└── array enorme con todas sus fechas
```

ni:

```text
week_1
week_2
week_3
```

SINO:

```text
PlanItem
│
├── ScheduleRule
│
└── Occurrences
     ├── 2026-08-20
     │    05:30–07:00
     │    completed
     │
     ├── 2026-08-22
     │    07:00–08:30
     │    pending
     │
     └── ...
```

La regla sirve para **crear** occurrences.

Después, cada occurrence es independiente y editable.

Ahí tenemos las dos cosas que estás buscando:

> **automatización para no programar todo manualmente**

y al mismo tiempo:

> **control absoluto sobre cada fecha concreta**.

Ese equilibrio me parece mucho más fuerte que cualquiera de las dos soluciones por separado.

Y algo más: ahora sí siento que el modelo empezó a encajar con la idea original del proyecto, donde una cosa es la rutina recurrente y otra la instancia concreta de una actividad en una fecha, sin que cambiar el futuro destruya el pasado. Esa separación ya aparecía como un requisito importante en el análisis inicial del proyecto. 

**Todavía no tocaría `CURRENT_TASK.md`.** Primero cerraría contigo dos o tres reglas delicadas del nuevo motor —principalmente qué ocurre al modificar una serie, cómo tratar los conflictos de evento/imprevisto y cómo materializar lo “indefinido”— y después sí escribimos los documentos. En lo demás, ya tenemos una arquitectura que considero suficientemente buena como para llevarla posteriormente a PostgreSQL sin tener que tirar todo y empezar otra vez.
