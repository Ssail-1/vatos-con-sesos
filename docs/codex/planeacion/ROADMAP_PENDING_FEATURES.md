Sí, **yo movería `ROADMAP_PENDING_FEATURES.md` a `docs/codex/planeacion/`**.

La razón es justo la que ya establecimos: el archivo contiene cosas que **queremos recordar**, pero que Codex **no debe interpretar como alcance vigente**. Si lo dejamos junto a `CURRENT_TASK`, `FRONTEND...`, `MOCK_DATA...`, etc., visualmente parece otro documento normativo.

Yo lo dejaría así:

```text
docs/codex/
├── planeacion/
│   ├── ...
│   └── ROADMAP_PENDING_FEATURES.md
│
├── CURRENT_TASK.md
├── FRONTEND_MVP_04.md
├── MOCK_DATA_CONTRACT_MVP_04.md
├── SCHEDULE_MODEL_MVP_04.md
├── ACCEPTANCE_CRITERIA_MVP_04.md
└── UI_REFERENCE.md
```

Puedes moverlo con:

```bash
git mv docs/codex/ROADMAP_PENDING_FEATURES.md \
docs/codex/planeacion/ROADMAP_PENDING_FEATURES.md
```

Y ahora sí, el siguiente archivo que quiero cerrar es **`CURRENT_TASK.md`**.

Pero hay un cambio importante: este `CURRENT_TASK` **no manda construir todo MVP 04 todavía**. Mandará construir únicamente:

# `MVP 04.0.1 — Motor temporal, modelo y materialización`

Después haremos `04.0.2` para toda la navegación/visualización nueva.

---

## `docs/codex/CURRENT_TASK.md`

````md
# Current Task

## Entrega actual

**MVP 04.0.1 — Motor temporal, modelo y materialización por ocurrencias**

---

# Proyecto

Vatos con Sesos

Submódulo actual:

```text
Vatos con Sesos
└── Gestor de hábitos
    └── Plan del día
````

---

# Propósito de esta entrega

El objetivo de MVP 04.0.1 es reemplazar el modelo temporal heredado de MVP 03
por un motor basado en:

```text
PlanItem
+
generationConfig
+
Occurrence
```

Esta entrega debe construir y validar el nuevo dominio temporal antes de
realizar los cambios grandes de navegación y visualización correspondientes
a MVP 04.0.2.

La prioridad de esta entrega es:

```text
modelo correcto
+
integridad temporal
+
materialización
+
regresión funcional
```

No realizar todavía el rediseño completo de la matriz mensual.

---

# División del MVP 04

El MVP 04 completo se divide internamente en:

```text
MVP 04.0.1
Motor temporal, modelo y materialización

MVP 04.0.2
Navegación temporal, selección por fecha y visualización frontend
```

Esta tarea corresponde únicamente a:

```text
MVP 04.0.1
```

No adelantar funcionalidad exclusiva de MVP 04.0.2 salvo que sea estrictamente
necesaria para mantener funcionando la aplicación actual.

---

# Documentos normativos

Antes de modificar código, leer completamente:

1. `/AGENTS.md`
2. `/docs/codex/CURRENT_TASK.md`
3. `/docs/codex/SCHEDULE_MODEL_MVP_04.md`
4. `/docs/codex/MOCK_DATA_CONTRACT_MVP_04.md`
5. `/docs/codex/FRONTEND_MVP_04.md`
6. `/docs/codex/UI_REFERENCE.md`
7. `/docs/codex/ACCEPTANCE_CRITERIA_MVP_04.md`

Cuando exista una contradicción:

```text
CURRENT_TASK
↓
SCHEDULE_MODEL
↓
MOCK_DATA_CONTRACT
↓
FRONTEND
↓
ACCEPTANCE_CRITERIA
```

deben interpretarse conjuntamente buscando la decisión más reciente y
específica del MVP 04.

Si existe una contradicción real que no pueda resolverse sin inventar una
regla de negocio:

1. no tomar una decisión silenciosa;
2. detener únicamente esa parte;
3. informar el conflicto al usuario.

---

# Documentación no normativa

Las siguientes carpetas contienen contexto histórico, ideas y planificación:

```text
/docs/codex/planeacion/
/docs/codex/proximas-features/
/docs/codex/archive/
```

Pueden consultarse únicamente para comprender el proyecto.

NO deben utilizarse para:

* ampliar el alcance;
* implementar funciones futuras;
* reemplazar decisiones normativas;
* asumir requisitos no presentes en los documentos actuales.

En especial:

```text
/docs/codex/planeacion/ROADMAP_PENDING_FEATURES.md
```

es un registro de funciones pendientes.

NO representa trabajo autorizado en esta entrega.

---

# Área autorizada de código

Codex puede crear, modificar, mover o eliminar código únicamente dentro de:

```text
/modules/gestor_de_habitos/
```

No modificar código fuera del módulo.

---

# Archivos externos

No modificar:

```text
/AGENTS.md
/docs/
/index.html
/css/
/js/
/modules/dev_notes/
/README.md
/.gitignore
```

ni ningún otro archivo externo.

La documentación puede leerse, pero no editarse.

---

# Git

No ejecutar:

```text
git commit
git push
git merge
git switch
git checkout
git reset
git restore
git clean
git tag
```

No cambiar de rama.

No modificar historial.

Se permiten comandos no destructivos de inspección como:

```text
git status
git diff
git diff --check
```

---

# Estado inicial

MVP 03 ya funciona y debe considerarse baseline.

Actualmente existen:

* Plan del día;
* matriz mensual;
* vista compacta;
* cinco estados;
* creación;
* inserción contextual;
* edición;
* clasificación de registros;
* validación temporal;
* acciones contextuales;
* navegación a Vatos con Sesos;
* persistencia exclusivamente en memoria.

MVP 04.0.1 debe preservar estas capacidades en la medida compatible con el
nuevo modelo.

---

# Cambio arquitectónico principal

El modelo anterior:

```text
Activity object
├── horario global
├── position
└── statesByDate
```

debe ser reemplazado por:

```text
PlanItem
│
├── identidad
├── clasificación
└── generationConfig

Occurrence
│
├── identidad
├── planItemId
├── date
├── startTime
├── endTime
└── status
```

---

# Fuente canónica

La fuente mutable principal en memoria debe quedar conceptualmente separada:

```js
{
    planItems: [],
    occurrences: []
}
```

No mantener simultáneamente el modelo MVP 03 como una segunda fuente de
verdad.

---

# PlanItem

Un PlanItem representa:

```text
qué cosa es
```

Ejemplos:

* Gym
* Meditar
* Trabajo
* CCNA / Estudio
* Boda de Efrén

Debe poseer identidad independiente del nombre.

---

# Occurrence

Una Occurrence representa:

```text
una aparición concreta de un PlanItem en una fecha
```

Ejemplo:

```text
Gym
20 agosto 2026
05:30–07:15
completed
```

Cada occurrence posee:

* id propio;
* planItemId;
* fecha;
* horario;
* status propio.

---

# Regla central del MVP 04

Para saber:

```text
qué está realmente agendado
```

consultar:

```text
Occurrences
```

Para saber:

```text
qué debe generarse en el futuro
```

consultar:

```text
generationConfig
```

Una occurrence materializada NO debe reconstruirse automáticamente desde
generationConfig cada vez que se renderiza.

---

# generationConfig

generationConfig es:

```text
configuración actual del algoritmo de generación futura
```

NO es:

* una occurrence;
* una plantilla de usuario;
* una entidad histórica independiente;
* un ScheduleRule;
* una versión de planificación.

No crear:

```text
ScheduleRule
scheduleId
scheduleVersionId
```

---

# Modos de generación que debe soportar el motor

MVP 04.0.1 debe preparar o implementar los modos definidos por el contrato:

```text
weekly
interval_days
manual_dates
single_date
```

El grado exacto de interacción visible puede permanecer limitado.

La lógica de dominio sí debe quedar separada y comprobable.

---

# Weekly

Debe soportar:

* startDate;
* endDate o indefinite;
* weekdays ISO;
* horario general;
* horarios personalizados por weekday.

Días ISO:

```text
1 lunes
2 martes
3 miércoles
4 jueves
5 viernes
6 sábado
7 domingo
```

---

# interval_days

Debe permitir generar occurrences cada:

```text
N días
```

a partir de una fecha inicial.

---

# manual_dates

Debe permitir fechas explícitas.

Cada fecha puede tener horario propio.

---

# single_date

Debe permitir una sola fecha y horario.

Debe servir como base para:

```text
event
unexpected
```

---

# Nueva clasificación de Activity

Los tipos permitidos son:

```text
anchor
periodic
event
unexpected
```

`event` es nuevo respecto al MVP anterior.

---

# Habit

Durante MVP 04 continúa únicamente:

```text
habit / scheduled
```

Los hábitos puntuales, logros y cantidades quedan fuera de alcance.

---

# Estados por occurrence

Eliminar como fuente de verdad:

```text
statesByDate
```

Cada occurrence contiene directamente:

```text
status
```

Estados:

```text
pending
in_progress
completed
not_completed
cancelled
```

---

# Estados que bloquean horario

Bloquean:

```text
pending
in_progress
completed
```

---

# Estados que liberan horario

NO bloquean:

```text
not_completed
cancelled
```

Esta regla es obligatoria.

---

# Ejemplo not_completed

Existe:

```text
Gym
05:30–07:30
not_completed
```

Debe poder registrarse posteriormente:

```text
Desayuno
06:00–06:30
```

sin eliminar la occurrence de Gym.

Gym permanece como historial de algo planeado que no se realizó.

---

# Ejemplo cancelled

Existe:

```text
Trabajo
08:00–17:00
cancelled
```

Debe poder registrarse otra occurrence dentro de ese horario.

La occurrence cancelada permanece en historial.

---

# completed

Una occurrence:

```text
completed
```

continúa bloqueando su intervalo.

No permitir superposición silenciosa sobre algo registrado como realizado.

---

# Detección de conflictos

Los conflictos se evalúan solamente entre occurrences que:

1. tienen la misma fecha;
2. bloquean horario;
3. tienen intervalos superpuestos.

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

---

# Cambios de status e integridad

La validación temporal ya no debe ocurrir únicamente al:

* crear;
* editar.

También debe considerarse cuando cambia un status.

Ejemplo:

```text
Gym
05:30–07:30
not_completed

Desayuno
06:00–06:30
pending
```

Si posteriormente el usuario intenta convertir Gym nuevamente a:

```text
pending
```

esa transición produciría dos bloques activos superpuestos.

Debe rechazarse o exigir resolución explícita.

Durante MVP 04.0.1 es suficiente:

```text
rechazar la transición
+
informar el conflicto
```

No implementar todavía una interfaz compleja de resolución.

---

# Ciclo de estados existente

El ciclo visual previo puede conservarse:

```text
pending
→ in_progress
→ completed
→ not_completed
→ cancelled
→ pending
```

pero ya NO debe asumirse que cada transición siempre puede ejecutarse.

Antes de pasar desde un status que libera horario hacia uno que bloquea:

* comprobar conflictos.

---

# Materialización

Debe existir un componente/responsabilidad de dominio que:

```text
generationConfig
+
rango
↓
Occurrences
```

---

# Idempotencia

Ejecutar materialización dos veces sobre el mismo rango NO debe crear
occurrences automáticas duplicadas idénticas.

La comprobación de duplicado puede considerar conceptualmente:

```text
planItemId
date
startTime
endTime
```

sin utilizar esa combinación como identidad definitiva.

---

# ID de PlanItem

Los nuevos PlanItems deben utilizar identidad técnica independiente del nombre.

Preferentemente:

```js
crypto.randomUUID()
```

con fallback cuando sea necesario.

---

# ID de Occurrence

Cada occurrence también debe poseer id independiente.

No utilizar:

```text
fecha
```

como id.

---

# Materialización indefinida

Nunca intentar generar infinitamente.

Debe utilizarse un horizonte finito.

---

# Horizonte inicial

Durante MVP 04.0.1:

```text
mes de referencia
+
mes siguiente completo
```

Ejemplo:

```text
23 agosto 2026
↓
materializado al menos hasta 30 septiembre 2026
```

El cálculo debe ser genérico.

---

# Extensión futura del horizonte

Si existe una fecha explícita posterior:

```text
10 julio 2027
```

las recurrencias indefinidas pueden materializarse hasta:

```text
31 julio 2027
```

cuando corresponda.

No hardcodear años o meses.

---

# Datos iniciales

Los siete registros demostrativos del MVP 03 deben convertirse a PlanItems.

Los mocks deben demostrar que NO todos los PlanItems ocurren todos los días.

Ejemplo:

```text
Gym
L / X / V

CCNA
L / X / V

Cepillado
todos los días
```

La configuración exacta está definida en:

```text
MOCK_DATA_CONTRACT_MVP_04.md
```

---

# Estados demostrativos

Los estados de demostración anteriores deben migrarse a:

```text
Occurrence.status
```

No reconstruir:

```text
statesByDate
```

---

# Orden

Eliminar `position` como propiedad persistente.

La posición visible se deriva desde:

```text
occurrences ordenadas por startTime
```

---

# Duración

No almacenar duración.

Calcular:

```text
endTime - startTime
```

---

# Editar una occurrence

Debe existir una operación de estado equivalente a:

```text
updateOccurrence(occurrenceId, draft)
```

que permita cambiar al menos:

```text
date
startTime
endTime
```

Debe preservar:

```text
id
planItemId
status
```

---

# Cambiar status

Debe existir una responsabilidad separada equivalente a:

```text
setOccurrenceStatus(...)
```

o la abstracción multestado correspondiente.

No mezclar cambio de horario y cambio de status en una única mutación genérica.

---

# Creación de PlanItem

Debe existir una responsabilidad que:

1. valide el draft;
2. genere id;
3. almacene PlanItem;
4. materialice las occurrences iniciales correspondientes;
5. rechace el conjunto si la creación produce un estado inválido.

No dejar un PlanItem creado parcialmente si falla toda su materialización
inicial.

---

# Atomicidad conceptual

Si una operación nueva intenta generar varias occurrences y alguna entra en
conflicto, no debe quedar silenciosamente una mitad creada y otra no.

Durante MVP 04.0.1 debe existir un comportamiento determinista.

Preferencia:

```text
validar primero el conjunto completo
↓
si todo es válido
↓
insertar
```

Para Event/Unexpected con reglas de override, seguir el alcance definido en
los documentos normativos.

---

# Event

`activity / event` debe incorporarse al dominio.

Representa una actividad conocida con anticipación asociada principalmente a:

```text
single_date
manual_dates
```

---

# Unexpected

`activity / unexpected` representa un imprevisto.

Normalmente utiliza:

```text
single_date
```

---

# Prioridades

No almacenar priority como dato.

Debe derivarse mediante reglas del dominio.

Conceptualmente:

```text
NORMAL      100
EVENT       200
UNEXPECTED  300
```

---

# Override avanzado

La lógica completa de:

```text
evento desplaza actividad
↓
confirmación
↓
cancelación causada por otra occurrence
```

puede permanecer limitada si FRONTEND_MVP_04 o ACCEPTANCE_CRITERIA no exige
todavía la interfaz completa.

Pero la arquitectura no debe impedirla.

No agregar todavía campos futuros no autorizados.

---

# cancelledByOccurrenceId

NO forma parte del contrato actual.

No implementarlo salvo autorización explícita posterior.

---

# Edición por alcance

El modelo debe quedar preparado conceptualmente para:

```text
Solo esta fecha
Solo esta semana
De aquí en adelante
```

---

# MVP 04.0.1 y edición

En esta primera entrega es obligatorio que el nuevo modelo soporte al menos:

```text
Solo esta fecha
```

mediante edición directa de una occurrence.

---

# Solo esta semana

La lógica completa puede pertenecer a MVP 04.0.2 si así lo establece
ACCEPTANCE_CRITERIA.

No adelantar interfaz innecesaria.

---

# De aquí en adelante

Debe quedar soportado arquitectónicamente mediante:

```text
actualización de generationConfig
+
regeneración de futuro pendiente
```

La interacción completa puede aplazarse a MVP 04.0.2.

---

# Regeneración

Nunca modificar automáticamente occurrences históricas.

Las principales candidatas a regeneración futura son:

```text
fecha futura
+
status === pending
```

---

# No regenerar automáticamente

No eliminar mediante regeneración automática occurrences con:

```text
in_progress
completed
not_completed
cancelled
```

que ya representen información histórica significativa.

---

# Frontend durante MVP 04.0.1

La interfaz actual debe seguir siendo utilizable.

No realizar todavía el rediseño grande de MVP 04.0.2.

Se permiten ajustes mínimos necesarios para:

* trabajar con occurrences;
* mostrar la agenda actual;
* crear;
* editar;
* cambiar estados;
* demostrar diferentes días programados.

---

# No implementar todavía en 04.0.1

No implementar todavía como objetivo principal:

* selector de calendario nuevo;
* selector de mes;
* flechas laterales de mes;
* filtro del ojo;
* mostrar solo filas aplicables al día;
* casillas grises no programadas;
* separación visual semanal;
* estadísticas;
* gráficas;
* rachas;
* premios;
* porcentaje diario;
* porcentaje semanal;
* porcentaje mensual;
* backend;
* PostgreSQL;
* Flask;
* API;
* autenticación;
* despliegue;
* historial autocompletable de PlanItems;
* subactividades;
* hábitos tipo logro;
* hábitos puntuales;
* tiempos reales.

Estas funciones están reservadas para:

* MVP 04.0.2;
* MVP posteriores;
* roadmap pendiente.

---

# Modularización

Mantener responsabilidades pequeñas y comprensibles.

No concentrar nuevamente toda la aplicación en:

```text
app.js
```

---

# app.js

Debe continuar actuando principalmente como:

```text
coordinador
```

No debe convertirse en:

* store;
* materializador;
* detector de conflictos;
* dominio de clasificación;
* motor de estados;
* renderer completo.

---

# Organización sugerida

Puede evolucionarse hacia algo conceptualmente equivalente a:

```text
js/
├── data/
├── domain/
├── scheduling/
├── state/
├── utils/
├── views/
└── app.js
```

No crear carpetas o archivos sin una responsabilidad real.

---

# Dominio

La lógica de:

* clasificación;
* status;
* bloqueo temporal;
* prioridades;

debe vivir fuera de las vistas.

---

# Scheduling

La lógica de:

* materialización;
* recurrencia;
* horarios por weekday;
* intervalos;
* conflictos;

debe centralizarse.

---

# Store

Debe continuar siendo la única fuente mutable de:

```text
planItems
occurrences
```

Las vistas no deben mutar directamente las colecciones internas.

---

# Consultas mínimas necesarias

El motor/store debe poder resolver como mínimo:

```text
getPlanItemById
getOccurrenceById
getOccurrencesForDate
getOccurrencesForMonth
getOccurrencesForPlanItem
```

Los nombres exactos pueden variar.

---

# Pruebas obligatorias de MVP 04.0.1

Codex debe comprobar al menos:

## Migración

* no existe `statesByDate` como fuente activa;
* no existe `position` persistente;
* la agenda utiliza occurrences;
* la UI sigue renderizando.

## PlanItems

* activity/anchor;
* activity/periodic;
* activity/event;
* activity/unexpected;
* habit/scheduled.

## Materialización weekly

* varios weekdays;
* rango finito;
* indefinido con horizonte;
* override de horario por weekday.

## interval_days

* genera fechas correctas.

## manual_dates

* varias fechas;
* horarios diferentes.

## single_date

* exactamente una aparición.

## Idempotencia

* materializar dos veces no duplica occurrences idénticas.

## Conflictos

* misma fecha + superposición + status bloqueante → conflicto;
* distinta fecha → sin conflicto;
* cancelled → espacio libre;
* not_completed → espacio libre;
* completed → bloquea.

## Estados

* status independiente por occurrence;
* transición hacia status bloqueante valida conflictos.

## Edición

* cambiar horario de una occurrence;
* cambiar fecha;
* conservar id;
* conservar planItemId;
* conservar status.

## Duración

* se calcula;
* no se almacena.

## IDs

* nuevos PlanItems no dependen del name;
* occurrences no dependen de date.

## Regresión

* creación;
* edición;
* estados;
* responsive existente;
* navegación VCS;
* interfaz sin errores graves.

---

# Verificación técnica

Cuando sea posible:

```text
node --check
```

sobre módulos JavaScript.

Comprobar imports mediante servidor HTTP local.

---

# Verificación visual

Si el entorno permite Chromium:

comprobar aproximadamente:

```text
1440 × 900
390 × 844
```

El objetivo visual de 04.0.1 es:

```text
no romper MVP 03
```

No alcanzar todavía el frontend final del MVP 04.

---

# Resultado esperado

Al terminar MVP 04.0.1 debe poder demostrarse:

```text
PlanItem
↓
generationConfig
↓
materialización
↓
Occurrences independientes
↓
status independiente
↓
consulta por fecha
```

Y además:

```text
Occurrence cancelled
        ↓
horario disponible
```

```text
Occurrence not_completed
        ↓
horario disponible
```

```text
Occurrence completed
        ↓
horario continúa ocupado
```

---

# Definición de terminado

MVP 04.0.1 está terminado cuando:

1. El modelo MVP 03 fue migrado completamente.
2. PlanItem y Occurrence son conceptos separados.
3. generationConfig genera futuro.
4. Occurrences son la agenda real.
5. statesByDate dejó de ser fuente de verdad.
6. Cada occurrence posee status propio.
7. cancelled libera horario.
8. not_completed libera horario.
9. completed continúa bloqueando.
10. Los cambios de status respetan integridad temporal.
11. Se soportan los modos de generación definidos.
12. La materialización es idempotente.
13. La interfaz MVP 03 continúa siendo utilizable.
14. No se implementaron funciones fuera del alcance 04.0.1.

Cuando estos criterios se cumplan podrá iniciarse:

**MVP 04.0.2 — Navegación temporal y visualización frontend.**

````

### Algo que quiero que notes

Con esto Codex ya no recibe simplemente:

> “refactoriza los objetos”.

Le estamos diciendo que el resultado de `04.0.1` tiene que demostrar una cadena completa:

```text
Gym
↓
configuración L/X/V
↓
materializador
↓
occurrence lunes
occurrence miércoles
occurrence viernes
↓
cada una independiente
````

Y tu nueva regla queda formalmente metida desde el corazón:

```text
NOT_COMPLETED
y
CANCELLED
↓
liberan horario
```

pero **no desaparecen**, porque siguen siendo historia.

El siguiente que yo haría es **`ACCEPTANCE_CRITERIA_MVP_04.md`**, pero lo escribiría específicamente en dos secciones grandes: primero los criterios de `04.0.1` que Codex tendrá que cumplir ahora, y después dejaríamos explícitamente marcada la sección `04.0.2 — NO EJECUTAR TODAVÍA`. Así podremos reutilizar el mismo archivo cuando hagamos la segunda mitad sin volver a inventar los criterios.
