Sí, ahora sí veo exactamente dónde estaba nuestra desconexión. Y en el punto principal **te doy la razón**: yo estaba mezclando dos necesidades distintas bajo `ScheduleRule`.

Una cosa es **el algoritmo/regla que utilizamos para agendar ocurrencias**, y otra muy distinta es **la información que representa una actividad una vez que ya fue agendada**. Tú quieres que, después de generadas las fechas, la agenda sea la verdad. Eso me parece correcto para Vatos con Sesos.

Y con lo último que escribiste, creo que podemos simplificar bastante la arquitectura que te propuse.

---

# 1. Primero: `real_start_time` y `real_end_time`

Aquí haría una pequeña distinción con lo que propones.

Para el MVP actual estoy de acuerdo en **quitarlos completamente**.

Pero no diría que:

> modificar `plannedStartTime` = registrar el tiempo real.

Diría:

> modificar la occurrence del día = **replanificar ese día**.

Ejemplo:

```text
Gym estaba planeado:
05:30 → 07:30

Hoy cambió el plan:
06:00 → 08:00
```

Editamos:

```text
Occurrence de hoy
06:00 → 08:00
```

Y listo.

Esto significa que para nuestra primera versión no tendremos:

```text
planned_start
actual_start
planned_end
actual_end
```

sino solamente:

```text
startTime
endTime
```

de **esa occurrence concreta**.

¿Por qué hago esa precisión? Porque si algún día queremos analizar:

> “Planeaba empezar a las 5:30 pero realmente empecé a las 6:10”

no podremos obtenerlo después de haber sobrescrito `05:30`.

Pero eso no me preocupa para el MVP. Lo archivamos como capacidad futura. Tu diseño original contemplaba explícitamente la comparación planeado/real, pero el modelo actual ya evolucionó bastante desde ese primer planteamiento. 

Así que:

```text
MVP actual:
una sola pareja startTime/endTime por occurrence

Futuro opcional:
actualStartTime/actualEndTime
```

Mucho más sencillo.

---

# 2. Sobre `ScheduleRule`: aquí cambio mi propuesta

Este era el punto que te estaba volviendo loco jajajaja.

## Ya no quiero esto:

```text
PlanItem
   ↓
ScheduleRule V1
   ↓
Occurrence
```

con:

```js
occurrence.scheduleId
```

No lo necesitamos para el producto que acabas de definir.

Tu objeción es válida: una vez que una fecha fue materializada, para saber:

* qué actividad es;
* cuándo ocurre;
* en qué horario;
* qué estado tiene;

**no necesito saber mediante qué algoritmo fue generada**. 

Entonces quitamos:

```js
scheduleId
```

de las occurrences.

Eso simplifica bastante.

---

# 3. Pero necesitamos conservar UNA cosa para lo indefinido

Aquí está el único lugar donde todavía necesitamos una configuración de repetición.

Supongamos:

```text
Salir a correr

Sábado y domingo
07:00–08:00
Repetir indefinidamente
```

Hoy materializamos hasta septiembre.

Llegamos a octubre.

¿Cómo sabe el programa que debe seguir creando sábados y domingos?

Necesita recordar:

```text
sábado/domingo
07:00–08:00
indefinido
```

Eso no debe desaparecer.

Pero podemos tratarlo justamente como tú dices:

> **configuración del generador**, no como parte de las occurrences.

Y tampoco necesita un `scheduleId`.

Podría pertenecer al propio `PlanItem`:

```js
{
    id: "6d0c...",

    name: "Salir a correr",

    itemKind: "activity",
    activityType: "anchor",

    generationConfig: {
        mode: "weekly",
        weekdays: [6, 7],
        startDate: "2026-08-20",
        endDate: null,
        indefinite: true,

        defaultStartTime: "07:00",
        defaultEndTime: "08:00"
    }
}
```

Y las occurrences:

```js
{
    id: "...",
    planItemId: "6d0c...",
    date: "2026-08-22",
    startTime: "07:00",
    endTime: "08:00",
    status: "pending"
}
```

Fíjate en la diferencia:

```text
generationConfig
→ únicamente dice cómo crear fechas futuras

Occurrence
→ representa lo que realmente está agendado
```

No existe:

```text
Occurrence → scheduleId
```

ni obligamos a conservar versiones antiguas del generador.

Creo que **esta es la pieza intermedia que faltaba para que conectáramos**.

---

# 4. Y para actividades con fecha final ni siquiera necesitamos conservarlo eternamente

Supongamos:

```text
Curso
lunes/miércoles/viernes
20 agosto → 30 diciembre
```

Nuestro algoritmo materializa absolutamente todas las occurrences hasta el 30 de diciembre.

Después de eso técnicamente la regla ya cumplió su propósito.

Podemos conservar `generationConfig` porque cuesta prácticamente nada y sirve para editar/reanudar, pero **las occurrences son autosuficientes**.

El usuario jamás tendrá que pensar en:

> plantilla

> schedule

> versión de regla

Solamente:

```text
Curso
Editar
Repetición
```

---

# 5. Esta es ahora mi arquitectura propuesta

Mucho más cercana a la que dibujaste:

```text
PLAN ITEM
────────────────────────

id
name
kind
activityType / habitType

generationConfig
    │
    │ solo genera/agrega occurrences
    │
    ▼

OCCURRENCES
────────────────────────

Occurrence A
date
startTime
endTime
status

Occurrence B
date
startTime
endTime
status

Occurrence C
date
startTime
endTime
status
```

Y lo importante:

```text
PlanItem
   │
   ├──── Occurrence
   ├──── Occurrence
   ├──── Occurrence
   └──── Occurrence
```

**No hay otra entidad obligatoria en medio.**

---

# 6. Tu objeto JavaScript puede verse casi exactamente como imaginabas

En frontend podemos perfectamente entregar al resto de la aplicación algo como:

```js
{
    id: "7b64cf1a-...",

    name: "Salir a correr",

    kind: "activity",
    activityType: "anchor",

    generationConfig: {
        mode: "weekly",
        weekdays: [6, 7],
        indefinite: true,
        startDate: "2026-08-20",
        endDate: null,
        defaultStartTime: "07:00",
        defaultEndTime: "08:00"
    },

    occurrences: {
        "2026-08-22": {
            id: "occ-...",
            startTime: "07:00",
            endTime: "08:00",
            status: "pending"
        },

        "2026-08-23": {
            id: "occ-...",
            startTime: "07:00",
            endTime: "08:00",
            status: "completed"
        }
    }
}
```

Eso está muy cerca de lo que tú dibujaste. 

Solo te hice dos cambios:

```text
Occurrence no es una tupla.
```

En JavaScript lo representaríamos como objeto/colección.

Y:

```text
cada occurrence conserva id propio
```

Ahora te explico por qué.

---

# 7. ¿Entonces por qué la base de datos se verá diferente?

Aquí estaba otra fuente de confusión importante.

El objeto que utiliza JavaScript **no tiene que parecerse físicamente a las tablas SQL**.

Puedes recibir desde backend:

```js
{
    id: "actividad-123",
    name: "Gym",

    occurrences: {
        "2026-08-20": {...},
        "2026-08-22": {...},
        "2026-08-24": {...}
    }
}
```

aunque PostgreSQL internamente tenga:

```text
PLAN_ITEMS
─────────────────────────────
id              name
a123            Gym
```

y:

```text
OCCURRENCES
──────────────────────────────────────────────
id       plan_item_id   date         start   end
o001     a123           2026-08-20   05:30   07:30
o002     a123           2026-08-22   05:30   07:30
o003     a123           2026-08-24   06:00   08:00
```

La API toma eso:

```text
SQL
 ↓
Backend
 ↓
organiza
 ↓
JSON
```

y el frontend puede recibir:

```js
{
    name: "Gym",
    occurrences: {...}
}
```

### Por eso parecía que yo “descomponía” innecesariamente tu objeto.

No era necesariamente una propuesta para que tú pensaras la actividad de esa manera.

Era cómo probablemente terminaremos **almacenándola relacionalmente**.

Y ahora que ya sé cómo quieres conceptualizarla, no debemos mezclar las dos capas.

---

# 8. En PostgreSQL NO guardaremos un array enorme dentro de `Gym`

Y aquí sí mantendría firme esta decisión.

No haría una columna:

```text
occurrences = JSON gigante
```

con:

```json
{
  "2026-08-20": {...},
  "2026-08-22": {...},
  "2026-08-24": {...}
}
```

Aunque conceptualmente tú lo pienses así.

En PostgreSQL:

```text
una occurrence = una fila
```

Porque entonces consultar:

> dame las actividades del 20 de agosto

es trivial:

```sql
SELECT ...
FROM occurrences
WHERE date = '2026-08-20';
```

En cambio, buscar dentro de un mega objeto metido en una actividad sería bastante más incómodo.

---

# 9. Entonces tu estructura y la mía no estaban tan peleadas

Visualmente tú estabas pensando:

```text
Gym
└── occurrences
    ├── 20 agosto
    ├── 22 agosto
    └── 24 agosto
```

Yo estaba pensando:

```text
PLAN_ITEMS

Gym
 ID 123


OCCURRENCES

ID 1 → Gym → 20 agosto
ID 2 → Gym → 22 agosto
ID 3 → Gym → 24 agosto
```

**Son la misma relación.**

Solo la estamos viendo desde dos perspectivas.

Esto era lo que nos faltaba conectar.

---

# 10. `id` NO debe ser `"Gym"`

Aquí sí quiero corregir algo de los ejemplos anteriores.

Cuando puse:

```js
id: "gym"
```

era únicamente porque los mock-data legibles eran más fáciles de explicar.

No es como quiero que funcione realmente.

En producción sería algo parecido a:

```js
{
    id: "7d123d7c-38c6-4bf1-...",
    name: "Gym"
}
```

o en PostgreSQL quizá:

```text
id = 42
name = Gym
```

El `id` no tiene significado humano.

Es identidad.

---

# 11. La diferencia entre `id` y `name` resuelve exactamente tu ejemplo

Hoy:

```text
id: 42
name: Gym
```

Hay 300 occurrences:

```text
occurrence.planItemId = 42
```

Mañana renombras:

```text
Gym
```

a:

```text
Entrenamiento
```

Solo hacemos:

```text
PLAN_ITEMS

42 | Entrenamiento
```

Y **no tocamos ninguna de las 300 occurrences**.

Siguen diciendo:

```text
planItemId = 42
```

Y cuando preguntamos:

> ¿cómo se llama el item 42?

la respuesta ahora es:

```text
Entrenamiento
```

Eso es exactamente la ventaja que intuías.

---

# 12. Y tu ejemplo extremo de cambiar Gym por Desayuno demuestra por qué el ID importa

Técnicamente podríamos hacer:

```text
42 | Gym
```

↓

```text
42 | Desayuno
```

y toda la historia parecería ahora “Desayuno”.

Pero eso sería conceptualmente incorrecto.

Ahí entra una regla de negocio:

> Editar el nombre corrige o renombra la misma actividad.

Pero:

> Transformar una actividad en otra cosa distinta debe crear otro PlanItem.

No podemos saber automáticamente si:

```text
Gym → Gimnasio
```

es un renombre válido, mientras:

```text
Gym → Desayuno
```

es otra entidad.

El usuario decidirá.

Y tu futuro autocompletado ayudará mucho en eso.

---

# 13. El historial dinámico entonces queda precioso

Justamente.

Dentro de siete meses escribes:

```text
Poncha...
```

El buscador consulta:

```text
PlanItems existentes
```

y propone:

```text
Ponchadura de llanta
```

con su mismo:

```text
id = 912
```

Seleccionas esa actividad.

Creamos:

```text
Occurrence nueva
planItemId = 912
date = ...
```

No creamos otra actividad.

Así un día podremos preguntar:

```text
Ponchadura de llanta
──────────────────────
2026 → 2 ocurrencias
2027 → 3 ocurrencias

Promedio entre eventos...
```

Eso sí encaja magníficamente con lo que quieres. 

No lo implementaría en MVP 04, pero **el modelo debe permitirlo desde hoy**.

Y lo permite.

---

# 14. ¿Por qué una occurrence necesita ID?

Podríamos buscar:

```text
PlanItem + fecha
```

si garantizáramos:

> una actividad solamente puede aparecer una vez al día.

Pero no quiero ponernos esa restricción artificial.

Imagina en el futuro:

```text
Tomar medicamento
08:00

Tomar medicamento
20:00
```

Mismo PlanItem.

Misma fecha.

Dos occurrences.

Entonces:

```text
planItemId + date
```

no identifica una sola.

---

## Y hay otra razón todavía mejor

Imagina:

```text
Boda de Efrén
10 julio
```

Después cambian la boda:

```text
11 julio
```

Si el ID fuera:

```text
2027-07-10
```

tendríamos que cambiar la identidad porque cambió la fecha.

Eso es precisamente lo que no queremos.

La occurrence sigue siendo:

> la misma aparición de la Boda de Efrén

aunque haya cambiado de fecha.

Por eso:

```text
occurrenceId = identidad
date = dato editable
```

---

# 15. Entonces no buscamos normalmente por occurrenceId

Para mostrar el Plan del día preguntaremos:

```text
Dame occurrences donde:

date = selectedDate
```

Y PostgreSQL utiliza un índice sobre:

```text
date
```

para hacerlo rápido.

El ID sirve cuando queremos:

```text
editar ESTA occurrence
cancelar ESTA occurrence
poner comentario a ESTA occurrence
```

Ahí tenemos algo inequívoco:

```text
occurrenceId = 928173
```

---

# 16. Nuestra base conceptual queda así

Yo ya no la llamaría `TrackeableItem`, porque nuestro dominio se está convirtiendo en algo más concreto.

Podemos provisionalmente usar:

```text
PlanItem
```

para:

> la identidad reutilizable de una actividad o hábito.

Y:

```text
Occurrence
```

para:

> una aparición concreta de ese PlanItem dentro de la agenda.

Entonces:

```text
PlanItem
────────────────────────────
id
name
kind
activityType / habitType
generationConfig


Occurrence
────────────────────────────
id
planItemId
date
startTime
endTime
status
```

Eso es suficiente para el corazón del MVP 04.

---

# 17. Sobre `recordSubtype`

También entendí lo de `Gym - Pecho`.

Eso **no es lo que pretendíamos representar con `recordSubtype`**, pero el nombre puede habernos confundido.

Cuando teníamos:

```text
activity / anchor
```

`anchor` no significa una subactividad.

Significa el **tipo de actividad**.

Así que yo renombraría el concepto.

En lugar de:

```js
recordKind
recordSubtype
```

preferiría:

```js
kind: "activity"
activityType: "anchor"
```

Entonces:

```js
{
    id: "...",
    name: "Gym",

    kind: "activity",
    activityType: "anchor"
}
```

Y se acabó:

```text
Gym - Pecho
Gym - Pierna
Gym - Espalda
```

Por ahora solo:

```text
Gym
```

Más adelante:

```text
Gym
├── Pecho
├── Pierna
└── Espalda
```

serán subactividades si decidimos implementarlas.

Eso no afecta la identidad principal.

---

# 18. Los tipos quedan

Ahora:

```text
ACTIVITY

anchor
periodic
event
unexpected
```

Y:

```text
HABIT

scheduled
```

Más adelante añadiremos otros hábitos.

Tu documentación original ya distinguía actividad ancla, periódica, imprevista y hábitos con comportamiento diferente; ahora simplemente estamos refinando esa clasificación. 

---

# 19. Prioridades: sí, serían constantes

Y aquí combinaría tu idea numérica con la mía semántica.

No:

```js
const NORMAL = 10;
```

por todas partes.

Sino:

```js
const SCHEDULING_PRIORITY = {
    NORMAL: 100,
    EVENT: 200,
    UNEXPECTED: 300,
};
```

Y luego:

```js
function getSchedulingPriority(planItem) {

    if (planItem.kind === "habit") {
        return SCHEDULING_PRIORITY.NORMAL;
    }

    switch (planItem.activityType) {

        case "event":
            return SCHEDULING_PRIORITY.EVENT;

        case "unexpected":
            return SCHEDULING_PRIORITY.UNEXPECTED;

        default:
            return SCHEDULING_PRIORITY.NORMAL;
    }
}
```

Eso nos da lo que quieres.

Mañana aparece:

```text
Hábito puntual
```

y decidimos que debe convivir dentro de otros bloques:

```js
const SCHEDULING_PRIORITY = {
    NORMAL: 100,
    POINT_HABIT: 150,
    EVENT: 200,
    UNEXPECTED: 300,
};
```

Tenemos espacio entre niveles.

Y nada de eso va a PostgreSQL.

Es:

```text
regla del dominio
```

no:

```text
dato del usuario
```

---

# 20. Las semanas y tus estadísticas futuras

Las capturas nuevas me ayudaron bastante.

Ahora sí veo mejor por qué insistías en la separación visual.

Ahí realmente hay **tres escalas de análisis**:

```text
DÍA
↓
porcentaje diario

SEMANA
↓
porcentaje agregado de la semana

MES
↓
progreso total
```

Y más adelante:

```text
historial del mes
↓
gráfica
```

Eso reafirma que **lunes → domingo** es una buena decisión para nosotros.

En la matriz pondremos divisiones visuales entre semanas ISO.

Por ejemplo, si el mes comienza sábado:

```text
        S  D || L  M  X  J  V  S  D || L...
        1  2 || 3  4  5  6  7  8  9
```

El primer bloque del mes será parcial.

Pero conceptualmente pertenece a una semana:

```text
lunes anterior → domingo 2
```

Cuando hagamos estadísticas futuras podremos elegir:

> mostrar únicamente los días del mes

pero seguir sabiendo a qué semana ISO pertenecen.

No necesitamos cambiar el modelo por las gráficas.

De hecho, **Occurrence lo facilita muchísimo**:

```text
SELECT occurrences
WHERE date BETWEEN lunes AND domingo
```

y podemos calcular lo que queramos.

---

# 21. Y el porcentaje diario será trivial en el futuro

Conceptualmente:

```text
occurrences programadas ese día
        ↓
cuántas fueron completed
        ↓
porcentaje
```

Por ejemplo:

```text
10 programadas
8 completadas

80%
```

Luego debemos decidir qué hacen:

```text
cancelled
unexpected
not_completed
```

en el denominador.

Pero eso es una regla de estadísticas futura.

No necesitamos resolverla ahora.

---

# 22. Editar con lápiz: ahora hay tres alcances clarísimos

Esto queda formalmente:

```text
✎ Editar
```

puede terminar ofreciendo:

```text
Solo esta fecha

Solo esta semana

De aquí en adelante
```

### Solo esta fecha

Modifica directamente:

```text
Occurrence seleccionada
```

Puede cambiar:

```text
fecha
inicio
final
```

sin tocar nada más.

Es exactamente la opción que notaste que faltaba.

---

### Solo esta semana

Obtenemos:

```text
lunes de la semana seleccionada
↓
domingo
```

y modificamos únicamente las occurrences de **ese PlanItem** dentro de ese rango.

La `generationConfig` general no cambia.

---

### De aquí en adelante

Aquí:

```text
generationConfig
```

sí cambia.

Y las occurrences futuras de ese PlanItem que todavía sean planificación futura pueden regenerarse.

El pasado queda intacto.

---

# 23. Entonces ya no necesitamos historial de `ScheduleRule`

Éste era otro punto donde yo estaba metiendo complejidad.

Ejemplo:

Hoy:

```text
generationConfig:

L X V
05:30
```

Cambiamos desde septiembre:

```text
L J
06:00
```

No necesito guardar:

```text
Rule V1
Rule V2
```

porque agosto ya está materializado:

```text
Occurrences de agosto
```

Ahí está nuestro historial.

Actualizamos:

```text
generationConfig
```

a la nueva configuración.

Y solamente regeneramos futuro.

**Eso sí encaja con tu modelo.**

---

# 24. ¿Qué pasa al pausar?

También queda simple.

```text
PlanItem
generationConfig.active = false
```

o algo equivalente.

Las occurrences pasadas permanecen.

Las futuras todavía no ocurridas pueden retirarse de la agenda.

Cuando reactivamos:

```text
mismo PlanItem.id
```

y asignamos la nueva configuración.

Generamos nuevas occurrences.

Exactamente el escenario de trabajo/vacaciones que describiste. 

---

# 25. Algo que sí debemos diferenciar: borrar futuro vs cancelar

Aquí quiero proteger la semántica.

### Si hoy iba a hacer Gym y no fui:

```text
status = cancelled
```

Conservamos la occurrence porque fue parte del plan.

### Si cambio mi rutina de octubre en adelante y los antiguos Gym de noviembre todavía no ocurrieron:

no hace falta guardar 20:

```text
cancelled
cancelled
cancelled
cancelled...
```

Podemos **eliminar esas materializaciones futuras** y generar las nuevas.

Porque todavía no constituyen historia.

Entonces:

```text
pasado / presente
→ conservar historial

futuro pendiente
→ puede regenerarse
```

Esto también reduce datos innecesarios sin quitarte control.

---

# 26. Superposición y cancelaciones

Aquí seguimos completamente alineados.

La validación solo considera occurrences de:

```text
misma fecha
```

y que **bloqueen horario**.

Conceptualmente:

```js
function blocksSchedule(occurrence) {
    return occurrence.status !== "cancelled";
}
```

Evento/imprevisto con mayor prioridad:

```text
conflicto
↓
advertencia
↓
usuario confirma
↓
occurrence normal → cancelled
↓
se crea evento
```

Muy sólido.

---

# 27. Y aquí `cancelledByOccurrenceId` empieza a tener una razón real

No lo metería todavía obligatoriamente, pero fíjate:

```text
Trabajo
↓ cancelled

porque

Boda
↓
```

Si guardamos:

```js
cancelledByOccurrenceId: "id-de-boda"
```

podemos saber:

> esta cancelación fue automática y causada por este evento.

Eso incluso permitiría más adelante:

> se canceló la boda → ¿quieres restaurar Trabajo?

Ahí sí existe una función concreta para ese dato.

Por eso lo anotaría como campo futuro, no como decoración.

---

# 28. La estructura final que yo aprobaría ahora

Esta sería la base conceptual antes de escribir documentos de Codex:

```text
┌─────────────────────────────────┐
│            PlanItem             │
├─────────────────────────────────┤
│ id                              │
│ name                            │
│ kind                            │
│ activityType / habitType        │
│ generationConfig                │
└───────────────┬─────────────────┘
                │
                │ 1 : N
                ▼
┌─────────────────────────────────┐
│          Occurrence             │
├─────────────────────────────────┤
│ id                              │
│ planItemId                      │
│ date                            │
│ startTime                       │
│ endTime                         │
│ status                          │
└─────────────────────────────────┘
```

Y `generationConfig` **NO representa una entidad de negocio independiente**.

Es:

> la configuración actual utilizada por los algoritmos de agendamiento para crear nuevas occurrences.

No necesitamos:

```text
scheduleId
```

No necesitamos:

```text
scheduleVersionId
```

No necesitamos relacionar occurrences con una regla antigua.

Creo que esto resuelve por completo el punto donde no conectábamos.

---

# 29. En memoria vs PostgreSQL

En JavaScript podemos trabajar cómodamente como tú lo imaginas:

```js
const planItems = [
    {
        id: "...",
        name: "Gym",
        kind: "activity",
        activityType: "anchor",

        generationConfig: {...},

        occurrences: {
            "2026-08-20": {...},
            "2026-08-22": {...}
        }
    }
];
```

Pero cuando lleguemos a PostgreSQL:

```text
plan_items
occurrences
generation_configs   ← posiblemente tabla separada
```

¿Por qué `generation_configs` quizá termine en otra tabla?

No porque conceptualmente sea otra cosa.

Sino porque una base relacional prefiere normalizar estructuras complejas.

Desde JavaScript podemos seguir viendo:

```text
PlanItem.generationConfig
```

aunque PostgreSQL lo guarde separado.

**La arquitectura del dominio y el esquema físico de la BD no tienen por qué ser idénticos.**

Creo que ésta era la pieza que más te estaba desorientando.

---

# 30. Y ahora sí entiendo mejor qué querías decir con “control total”

Tu propuesta no pretende:

> guardar redundancia porque sí.

Lo que estás buscando es:

```text
la recurrencia automatiza
        +
cada fecha materializada es independiente
        =
automatización sin perder control
```

Y sí.

Eso me parece una arquitectura excelente para este proyecto.

---

## Qué considero cerrado ahora

Ya no necesito que discutamos más sobre `ScheduleRule`: **retiro esa entidad del modelo actual**.

La decisión queda:

```text
PlanItem
+
generationConfig
+
Occurrence
```

También queda:

```text
Occurrence no guarda scheduleId.
```

```text
PlanItem.id no depende del nombre.
```

```text
Occurrence.id no depende de la fecha.
```

```text
lunes-domingo como semana lógica.
```

```text
la planificación futura puede regenerarse.
```

```text
el historial pasado vive en las occurrences.
```

```text
real_start/end no entra por ahora.
```

```text
editar día / semana / desde aquí en adelante.
```

```text
prioridades = constantes del dominio, no datos persistidos.
```

Y el futuro de estadísticas que muestras en las capturas **encaja perfectamente encima de este modelo**, sin que tengamos que rediseñarlo.

Ahora sí considero que estamos en condiciones de reescribir `SCHEDULE_MODEL_MVP_04.md`; de hecho, después de toda esta conversación, **empezaría por ese documento y no por `CURRENT_TASK`**, porque el motor de datos acaba de quedar definido y será la fuente de la que deriven los demás documentos.
