
# Siguientes pasos

## Decisiones...

### Ssail

Ya estoy empezando a poner mis plan_items para organizar mi vida, osea, ya son reales los plan_items que voy a guardar, pero me pongo a pensar algo...

Hace falta que independiente el tipo de plan_item y subtipo, se pueda poner solo una occurrence, por ejemplo, si agrego una actividad que se que es periodica o ancla como comer, que me permita poner solo una occurrence, se que se puede con el modelo actual, pero no es como si fuera una operación natural.

seguire pensandolo pero por ahora eso no me agrada mucho.

Tambien creo que falta algo delicado, por ahora puedo hacer que funcione para mi la app, pero vamos a tener problemas, eso creo, porque?

Digamos cuando uno empieza a organizar su vida, uno no puede organizar de un dia a otro actividades que simplemente no esta acostumbrado, aparte de que no va a saber realmente que es lo que tiene que hacer, al principio hay mucha resistencia, y aveces uno exagera y hace planes que no son sustentables, entonces si yo fuera alguien que esta guiando a otra persona, primero le diria que empezara a tomar control de su vida registrando lo que hace, al principio no hace falta saber todo, solo ir registrando, observando, analizando patrones, definiendo necesidades, cosas así.

Entonces necesitamos eliminar un poco la barrera de entrada, porque no puede llegar y luego luego saber a que se refiere uno con ancla, periodica y esas cosas. Por ahora lo dejaremos asi pero por lo anterior que te comente, creo que si deberiamos en programacion, independientemente que tipo de plan_item sea, que tenga la opcion de solo  poner una occurrence por dia, y si quiere otro boton que le permita poner otro slot, no que el sistema lo obligue a definir por dias y eso.

Ahora viene un super tema que ya habiamos hablado, si tenemos que implementar historial dinamico... porque estaba pensando en por ahora empezar a registrar lo que hice en el dia y para registrarlos rapido los iba a poner como eventos para rapido, lo que me lleva a que tambien nos hace falta un plan_item, que sea solo tipo actividad, una actividad pura, a la que posteriormente se le pueda asignar un subtipo, porque puede pasar que simplemente aun no sepa el user que es lo que esta registrando. Bueno, ese no era el punto pero que bueno que salio. A lo que voy es que me di cuenta que no puedo registrar tipos eventos y despues registrarlos bien, porque entonces estariamos creando 2 plan_items, cada uno con su id, que objetivamente son lo mismo!, eso esta mal, y deja eso, no sería lo peor, lo peor sería que hoy registrara con trucos por medio de la interfaz una occurrence (que ya no se si llamarle occurrence o segmento) que sea comida por ejemplo y lo pongo igual con tipo ancla porque comer es una actividad naturalmente ancla, y mañana o en un rato volver a poner comer y sería otro plan_item porque no hay manera de que referencie al mismo plan_item. Entonces tambien necesitamos que el sistema sea capaz de detectar e identificar cuando se esta registrando un mismo plan_item, mi solución, no se que tan compleja sea, pero podemos hacer que a la hora del registro, en especifico cuando se este generando el nombre, que se desplieguen todas las occurrences de ser posible, o las que tienen mas occurrences, o no se, tambien pienso que mejor cuando registremos primero el user seleccione tipo de registro, subtipo y así para que funcione como un filtro y al poner el nombre o seleccionar el input y poner el nombre mande los que coincidan justo con eso seleccionado anteriormente. Entonces digamos que por default arroje ya opciones, obviamente esas opciones serán todos o parte de los plan_items ya registrados, entonces si el user quisiera poner uno que ya existe, solo lo selecciona y se llena automaticamente lo que haga falta en  cuestion al tipo de item que este o quiera agendar para el dia seleccionado, de aqui nacen dos necesidades, al registrar una actividad el sistema debe entender y poder digerir o procesar si esta registrando una actividad nueva o esta registrando una occurrence nueva de una actividad que ya existe..., talvez primero podríamos hacer que nos arroje los plan_items y se puedan seleccionar y despues arreglamos o definimos los formularios.

Ahora, si el user no encuentra a la mano el plan_item que busca porque en las apps de ahora todo quieren facil y si tiene un a grado de dificultad de entrada las personas se van, entonces lo primero que va a hacer es ir escribiendo el nombre del plan_item, entonces mientras escriba que vayan apareciendo los plan_items que tengan mayor parecido o semejanza a lo que va escribiendo el user, para que si no se acuerda, pues lo va escribiendo y le va apareciendo lo mas relacionado, asi como los buscadores de redes sociales.

---

Por ahora veo que no podre ir haciendo registros aislados porque generaria un problema, entonces intentare que todos los registros que hagan provengan del mismo plan_item, por ejemplo voy a registrar desde ayer porque ahorita ya es la 1am, hare que nazca el plan_item comida con sus horarios definidos y que justo se generen a futuro pero para crear en especifico el de hoy volvere a entrar despues de creado para editarlo y poner su horario real, igual sirve de prueba para el sistema  pero creo que es bueno documentarlo...

Ahora con esto que te digo primero dime que piensas, dime que tan dificil es o no se, necesito que me digas algo pero realmente no se en especifico que estoy buscando de ti.

Lo que si, esque vamos a desplegar ya la app como la tenemos ahorita y eso que te digo ya lo haremos despues y esa ya sera ahora si, vcs V 1.0.0.1, algo así, donde 1.0.0."1" sera esa implementacion de historial dinamico, o no se realmente como funcionan los tags jaja

### Noa

```md
Sí. Y creo que acabas de topar con algo más profundo que “faltan unas opciones en el formulario”: **hasta ahora VCS está muy bien diseñado para planificar, pero todavía no está igualmente bien diseñado para capturar la vida conforme ocurre**.

Eso explica casi todo lo que estás sintiendo al empezar a usarlo de verdad.

### Lo primero: no registraría “Comida” como PlanItem nuevo cada vez

Tu intuición es correcta. Conceptualmente:

```text
PlanItem
Comida
id = A
```

es la **identidad de la actividad**.

Luego puedes tener:

```text
Occurrence
ayer 14:10–14:40
plan_item_id = A

Occurrence
hoy 15:00–15:35
plan_item_id = A

Occurrence
mañana 14:30–15:00
plan_item_id = A
```

Y cada occurrence podría incluso tener varios segmentos:

```text
Occurrence Comida · hoy

Seg 1  14:00–14:15
Seg 2  14:30–14:50
```

Así que, para dejar también resuelta tu duda terminológica:

```text
PlanItem
→ "Comida"

Occurrence
→ "Comida que ocurrió/agendé el 23 de septiembre"

OccurrenceSegment
→ cada tramo temporal continuo dentro de esa occurrence
```

No deberíamos empezar a llamar occurrence a un segmento.

---

## Donde realmente descubriste el problema

Hoy el formulario mentalmente funciona más o menos así:

```text
Quiero registrar algo
        ↓
define qué tipo es
        ↓
define subtipo
        ↓
define días
        ↓
define recurrencia
        ↓
define horarios
        ↓
crear PlanItem
```

Eso está muy bien cuando **ya sabes cómo quieres organizar tu vida**.

Pero alguien empezando probablemente está en:

```text
¿Qué hice hoy?
        ↓
pues comí...
        ↓
de 3:10 a 3:40
        ↓
guardar
```

Y ya.

No debería necesitar entender todavía qué es:

```text
ancla
periódica
evento
slot
recurrencia
```

Eso que comentas de primero **observar → registrar → descubrir patrones → organizar** me parece una dirección de producto mucho más natural.

En realidad VCS podría tener dos caminos complementarios:

```text
REGISTRAR
¿Qué hice?

vs.

PLANIFICAR
¿Qué quiero hacer?
```

Y ambos terminarían alimentando el mismo modelo.

---

# La occurrence única debería ser una operación de primera clase

Aquí coincido completamente contigo.

Aunque técnicamente hoy podamos conseguirlo, si requiere “engañar” al formulario significa que **el modelo lo soporta pero la UX no lo reconoce como intención normal**.

Yo imaginaría el registro inicial así:

```text
Comida
23 septiembre
15:10 → 15:40

[ Guardar ]
```

Y debajo, opcionalmente:

```text
+ Añadir otro horario

☐ Hacer recurrente
```

No al revés.

Es decir:

```text
1 occurrence
```

debería ser el mínimo natural.

Después tú decides aumentar complejidad:

```text
1 occurrence
    ↓
+ otro slot
    ↓
+ recurrencia
    ↓
+ días específicos
    ↓
+ excepciones
```

No obligar al usuario a atravesar toda esa complejidad para registrar que comió.

Y esto debería funcionar **sin importar el tipo del PlanItem**.

Una actividad ancla puede tener una occurrence aislada.

Una periódica también.

Un evento también.

El tipo describe la naturaleza de la actividad; **no debería dictar que obligatoriamente tenga que existir una recurrencia**.

---

# Y descubriste otra cosa que me parece todavía más importante

Esto:

> “una actividad pura a la que posteriormente se le pueda asignar un subtipo”

Sí.

Yo probablemente permitiría algo como:

```text
Tipo:
Actividad

Subtipo:
Sin clasificar
```

o incluso:

```text
Actividad
└── subtipo = null
```

No necesitamos obligar al usuario a tomar una decisión que aún no sabe tomar.

Hoy:

```text
Comida
Actividad
Sin clasificar
```

Después de una semana observas:

> Hmm... comer estructura mi día.

Entonces:

```text
Comida
Actividad
Ancla
```

**Mismo PlanItem. Mismo ID. Mismo historial.**

Eso es muy importante.

No:

```text
Comida #1 → actividad
Comida #2 → ancla
```

sino:

```text
PlanItem A
"Comida"

clasificación evolucionó
```

Aquí empieza precisamente el concepto que tú llamabas **historial dinámico**.

---

# Sobre detectar que ya existe el PlanItem

Aquí también estoy contigo, con una pequeña precaución:

**el sistema debería detectar y sugerir; no debería decidir automáticamente que son el mismo.**

Porque podríamos tener:

```text
Trabajo
Trabajo universidad
Trabajo Uber
```

o:

```text
Ejercicio
Ejercicio rehabilitación
```

Una coincidencia de nombres no necesariamente implica identidad.

Yo haría que al empezar un registro aparezca algo como:

```text
Actividad
┌────────────────────────────┐
│ com...                     │
└────────────────────────────┘

Ya existentes:

🍽 Comida
   Actividad · Ancla
   38 apariciones

🍽 Comer con Romi
   Actividad
   4 apariciones

+ Crear "com..."
```

Conforme escribes:

```text
c
co
com
comi
comida
```

las opciones se reordenan.

Y el ranking podría considerar después:

```text
parecido del nombre
+
frecuencia de uso
+
recencia
+
tipo/subtipo seleccionado
```

Pero eso se puede construir progresivamente.

Para la primera implementación ni siquiera necesitamos un buscador sofisticado. Tenemos pocos PlanItems: se puede hacer búsqueda normalizada en memoria sobre los PlanItems que ya trae el planner.

Después, cuando existan cientos o miles:

```text
GET /api/plan-items/search?q=comida
```

con ranking backend.

---

## Y tu idea de usar tipo/subtipo como filtro también sirve

Podríamos tener:

```text
Tipo
Actividad

Subtipo
Ancla
```

y entonces al enfocar nombre:

```text
PlanItems existentes compatibles:

Comida
Dormir
Despertar
...
```

Pero yo **no obligaría a seleccionar tipo y subtipo antes del nombre**.

Eso volvería a aumentar la fricción.

Mejor que ambos caminos funcionen:

```text
escribes "com..."
→ aparecen coincidencias globales
```

o:

```text
eliges Actividad / Ancla
→ sugerencias ya filtradas
```

El filtro ayuda, pero no es requisito.

---

# Lo que NO debemos hacer mientras tanto

Justo lo que tú ya detectaste:

```text
ayer:
crear PlanItem "Comida"

hoy:
crear otro PlanItem "Comida"

mañana:
crear otro PlanItem "Comida"
```

Eso sería muy malo porque después tendríamos:

```text
Comida UUID-A
Comida UUID-B
Comida UUID-C
```

y una pregunta sencillísima como:

> ¿Cuántas veces comí tarde esta semana?

se convertiría en:

```text
¿cuál de los tres "Comida"?
```

Lo mismo para Finanzas, estadísticas, hábitos y análisis futuro.

Así que tu estrategia temporal es correcta:

```text
crear UNA VEZ PlanItem Comida
        ↓
todas las occurrences posteriores
referencian ese mismo PlanItem
```

Aunque por ahora tengas que hacer un poco más de trabajo desde la interfaz.

---

# Y aquí veo la parte realmente delicada del siguiente desarrollo

No es el autocomplete.

Eso es relativamente sencillo.

La parte arquitectónicamente interesante va a ser separar bien:

```text
IDENTIDAD
PlanItem
```

de:

```text
CLASIFICACIÓN
tipo/subtipo
```

de:

```text
PLANIFICACIÓN
GenerationConfig / GenerationSlots
```

de:

```text
REALIDAD
Occurrences / OccurrenceSegments
```

Porque hasta ahora nuestra aplicación creció desde la perspectiva de planificación.

Y sospecho —esto habrá que auditar antes de programarlo— que actualmente tenemos bastante acoplado:

```text
PlanItem
↔ GenerationConfig
```

De hecho, en tu DB acabamos de ver:

```text
4 PlanItems
4 GenerationConfigs
```

Eso no demuestra por sí solo que sea obligatorio, pero es una señal de que debemos revisar esa relación.

Porque en la nueva visión tendría muchísimo sentido poder tener:

```text
PlanItem: Comida
        │
        ├── occurrences históricas ✅
        │
        └── GenerationConfig ❌ todavía no
```

Y quizá tres días después:

```text
PlanItem: Comida
        │
        ├── historial
        └── GenerationConfig ✅
             ├── 08:00
             ├── 14:00
             └── 21:00
```

**El PlanItem debería poder existir antes de que el usuario sepa cómo quiere planificarlo.**

Para mí esa es una de las conclusiones más importantes de todo lo que acabas de escribir.

---

# ¿Qué tan difícil es?

No creo que estemos ante otra odisea del tamaño de OccurrenceSegment 😂.

Pero tampoco es “cambiar tres botones”.

Yo lo separaría conceptualmente así:

```text
Occurrence única como flujo natural
████░░░░░░  relativamente sencilla

PlanItem sin clasificación completa
████░░░░░░  sencilla-media

Selector de PlanItems existentes
████░░░░░░  media

Autocomplete / búsqueda inteligente
█████░░░░░  media

PlanItem independiente de recurrencia
██████░░░░  depende del schema actual

Historial dinámico completo
████████░░  la parte profunda
```

Porque “historial dinámico” eventualmente nos hará preguntarnos cosas como:

```text
¿el PlanItem cambió de subtipo
o siempre fue ese subtipo?

¿una occurrence histórica debe mostrar
la clasificación actual o la que tenía entonces?

¿un horario planificado y un horario realmente realizado
son la misma información?

¿puedo registrar primero y clasificar después?

¿puedo convertir patrones observados en recurrencia?
```

Esas preguntas son buenísimas, pero no tenemos que resolverlas esta madrugada 😅.

---

# Y estoy de acuerdo con desplegar primero

De hecho, ahora me parece todavía mejor decisión.

Usar VCS real nos está revelando cosas que **ningún test nos iba a revelar**.

Los tests nos dijeron:

> la base es consistente.

Tú usando VCS nos estás diciendo:

> sí, pero una persona real no piensa de esa forma.

Ambas cosas son necesarias.

Así que yo congelaría este descubrimiento como siguiente evolución, pero **no retrasaría el deployment actual**.

---

# Sobre las versiones: `1.0.0.1` no sería lo habitual

Lo estándar suele ser **Semantic Versioning**:

```text
MAJOR.MINOR.PATCH

1.0.0
│ │ │
│ │ └── correcciones
│ └──── nuevas funciones compatibles
└────── cambios incompatibles/grandes
```

Entonces, si lo que tenemos ahora lo consideramos nuestro primer VCS funcional:

```text
v1.0.0
```

Un bug como el control de estado:

```text
v1.0.1
```

Una feature importante pero compatible como:

```text
registro rápido
reutilización de PlanItems
autocomplete
historial dinámico inicial
```

sería más naturalmente:

```text
v1.1.0
```

Y si algún día hacemos un rediseño que rompe contratos/modelo:

```text
v2.0.0
```

Así que el mapa que a mí me empieza a gustar es:

```text
VCS v1.0.0
────────────────────────
Planner actual
OccurrenceSegment
PostgreSQL
recurrence
conflicts
termination
deployment


VCS v1.1.0
────────────────────────
Dynamic History / Capture

registro rápido
occurrence aislada first-class
PlanItem existente o nuevo
actividad sin clasificar
autocomplete/suggestions
reutilización de identidad
menos fricción de entrada
```

Incluso le pondría nombre a esa siguiente línea de producto:

> **Capture & Dynamic History**

porque ya no se trata solamente de “historial”. Se trata de que VCS pueda acompañarte **antes de que tengas organizada tu vida**.

Y eso cambia algo bonito del propósito de la app:

```text
VCS no te exige tener tu vida organizada
para empezar a usarlo.

VCS te ayuda a observarla
para poder organizarla.
```

Ese, para mí, es el descubrimiento importante de esta noche.

```