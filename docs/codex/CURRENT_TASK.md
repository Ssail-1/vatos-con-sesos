
# Current Task

## Entrega actual

**MVP 04.0.1 — Motor temporal, modelo y materialización por ocurrencias**

---

# Proyecto

**Vatos con Sesos**

Submódulo actual:

```text
Vatos con Sesos
└── Gestor de hábitos
    └── Plan del día
```

---

# Contexto

MVP 03 constituye el último checkpoint funcional aprobado.

Actualmente el módulo ya permite:

* visualizar una matriz mensual;
* trabajar en escritorio y pantalla compacta;
* crear registros;
* editar registros;
* seleccionar filas;
* utilizar acciones contextuales;
* manejar cinco estados;
* validar conflictos temporales;
* clasificar actividades y hábitos;
* navegar hacia Vatos con Sesos;
* trabajar exclusivamente en memoria.

MVP 04 introduce un cambio estructural importante en el motor temporal.

---

# División del MVP 04

El MVP 04 está dividido en dos entregas internas.

```text
MVP 04.0.1
Motor temporal, modelo y materialización

MVP 04.0.2
Navegación temporal y experiencia frontend completa
```

La tarea actualmente autorizada es únicamente:

```text
MVP 04.0.1
```

No implementar anticipadamente las funciones reservadas para MVP 04.0.2.

---

# Objetivo principal

Migrar el modelo temporal del MVP 03 hacia una arquitectura basada en:

```text
PlanItem
+
generationConfig
+
Occurrence
```

La nueva arquitectura debe permitir:

```text
automatización de planificación
+
independencia por fecha
+
conservación de historial
+
replanificación futura
```

sin introducir todavía backend ni persistencia.

---

# Principio central

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

Una Occurrence ya materializada es independiente.

No debe reconstruirse automáticamente desde generationConfig cada vez que la
interfaz se renderiza.

---

# Documentación normativa

Antes de modificar código, leer completamente en este orden:

1. `/AGENTS.md`
2. `/docs/codex/CURRENT_TASK.md`
3. `/docs/codex/SCHEDULE_MODEL_MVP_04.md`
4. `/docs/codex/MOCK_DATA_CONTRACT_MVP_04.md`
5. `/docs/codex/FRONTEND_MVP_04.md`
6. `/docs/codex/UI_REFERENCE.md`
7. `/docs/codex/ACCEPTANCE_CRITERIA_MVP_04.md`

Los documentos anteriores deben considerarse en conjunto.

Si existe una contradicción real entre documentos normativos que implique
inventar una regla de negocio:

* no tomar una decisión silenciosa;
* detener únicamente la parte afectada;
* informar claramente la contradicción.

---

# Documentación no normativa

Las carpetas:

```text
/docs/codex/planeacion/
/docs/codex/proximas-features/
/docs/codex/archive/
```

contienen:

* historia;
* conversaciones;
* ideas;
* decisiones futuras;
* funciones aplazadas;
* documentación antigua.

Pueden utilizarse para comprender contexto.

NO deben utilizarse para ampliar el alcance actual.

En particular:

```text
/docs/codex/planeacion/ROADMAP_PENDING_FEATURES.md
```

sirve exclusivamente para no olvidar funciones futuras.

No autoriza su implementación.

---

# Referencias visuales

Las referencias específicas del MVP 04 se encuentran principalmente en:

```text
/docs/codex/assets/assets-MVP04/
```

Su interpretación debe seguir:

```text
/docs/codex/UI_REFERENCE.md
```

Una imagen nunca amplía por sí sola el alcance de esta tarea.

---

# Área autorizada

Codex puede crear, modificar, mover o eliminar código únicamente dentro de:

```text
/modules/gestor_de_habitos/
```

---

# No modificar

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

ni ningún otro archivo fuera del módulo autorizado.

Los archivos externos pueden leerse cuando sea necesario.

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

Puede utilizarse inspección no destructiva:

```text
git status
git diff
git diff --check
git log
```

---

# Tecnologías autorizadas

Continuar utilizando:

* HTML;
* CSS;
* JavaScript nativo;
* módulos ES;
* APIs nativas del navegador;
* almacenamiento exclusivamente en memoria.

No introducir todavía:

* Flask;
* Python como backend;
* PostgreSQL;
* Supabase;
* API;
* localStorage;
* sessionStorage;
* IndexedDB;
* React;
* Vue;
* Angular;
* npm;
* frameworks;
* librerías externas;
* servicios remotos.

---

# Cambio estructural obligatorio

El modelo activo del MVP 03:

```text
Record
├── id
├── name
├── recordKind
├── recordSubtype
├── position
├── plannedStartTime
├── plannedEndTime
└── statesByDate
```

debe migrarse conceptualmente hacia:

```text
PlanItem
├── id
├── name
├── kind
├── activityType / habitType
└── generationConfig

Occurrence
├── id
├── planItemId
├── date
├── startTime
├── endTime
└── status
```

---

# Fuente canónica en memoria

La fuente mutable debe representar conceptualmente:

```js
{
    planItems: [],
    occurrences: []
}
```

Puede existir encapsulación dentro del store.

La obligación es que:

```text
PlanItems
```

y:

```text
Occurrences
```

sean conceptos separados.

---

# No mantener dos modelos activos

Después de la migración no debe existir:

```text
statesByDate
```

como segunda fuente de verdad.

Tampoco debe conservarse:

```text
position
```

como propiedad persistente del dominio.

---

# PlanItem

PlanItem representa:

```text
qué cosa es
```

Ejemplos:

```text
Gym
Trabajo
Meditar
CCNA / Estudio
Boda de Efrén
Ponchadura de llanta
```

El PlanItem no representa una fecha concreta.

---

# Identidad de PlanItem

El id debe ser independiente de:

* nombre;
* fecha;
* horario;
* posición.

Renombrar:

```text
Gym
↓
Gimnasio
```

no debe cambiar el id.

Los nuevos PlanItems deben utilizar preferentemente:

```js
crypto.randomUUID()
```

con fallback local cuando resulte necesario.

---

# kind

Valores:

```text
activity
habit
```

---

# Activity

Cuando:

```text
kind === "activity"
```

debe existir:

```text
activityType
```

Valores permitidos:

```text
anchor
periodic
event
unexpected
```

`event` debe incorporarse durante MVP 04.

---

# Habit

Cuando:

```text
kind === "habit"
```

debe existir:

```text
habitType
```

Durante MVP 04 únicamente:

```text
scheduled
```

---

# No utilizar propiedades nulas innecesarias

Un Activity no debe contener:

```text
habitType: null
```

Un Habit no debe contener:

```text
activityType: null
```

Utilizar un modelo discriminado.

---

# generationConfig

generationConfig representa:

```text
la configuración ACTUAL utilizada para generar Occurrences futuras
```

No representa:

* una plantilla del usuario;
* una occurrence;
* una entidad histórica independiente;
* una versión almacenada de planificación.

---

# No crear ScheduleRule

Durante MVP 04 NO crear como entidad independiente:

```text
ScheduleRule
```

No agregar:

```text
scheduleId
scheduleVersionId
```

a Occurrence.

---

# Modos de generationConfig

El motor debe soportar:

```text
weekly
interval_days
manual_dates
single_date
```

según:

```text
SCHEDULE_MODEL_MVP_04.md
MOCK_DATA_CONTRACT_MVP_04.md
```

---

# Weekly

Debe soportar:

```text
startDate
endDate / indefinite
weekdays
defaultStartTime
defaultEndTime
weekdayTimeOverrides
```

---

# Días de semana

Utilizar representación ISO:

```text
1 = lunes
2 = martes
3 = miércoles
4 = jueves
5 = viernes
6 = sábado
7 = domingo
```

No utilizar `0 = domingo` como representación persistente del dominio.

Las conversiones de JavaScript deben quedar encapsuladas en utilidades.

---

# interval_days

Debe soportar:

```text
cada N días
```

a partir de:

```text
startDate
```

---

# manual_dates

Debe soportar:

```text
varias fechas explícitas
+
horario independiente por entrada
```

---

# single_date

Debe soportar:

```text
una fecha concreta
+
horario
```

y servir de base principalmente para:

```text
event
unexpected
```

---

# Occurrence

Occurrence representa:

```text
una aparición concreta de un PlanItem dentro de la agenda
```

Ejemplo:

```text
Gym
20 agosto 2026
05:30–07:15
completed
```

---

# Contrato conceptual de Occurrence

Cada occurrence debe contener:

```text
id
planItemId
date
startTime
endTime
status
```

---

# Identity de Occurrence

Occurrence.id debe ser independiente de:

* date;
* startTime;
* endTime.

Mover una occurrence de fecha u horario no debe modificar su identidad.

---

# Más de una Occurrence por fecha

La arquitectura NO debe asumir:

```text
un PlanItem
=
máximo una occurrence por día
```

Debe permitir conceptualmente:

```text
Medicamento
08:00

Medicamento
20:00
```

en la misma fecha.

---

# Horario

Durante MVP 04 utilizar:

```text
startTime
endTime
```

por occurrence.

No introducir todavía:

```text
actualStartTime
actualEndTime
```

---

# Replanificación

Modificar una occurrence de:

```text
05:30–07:00
```

a:

```text
06:00–08:00
```

representa:

```text
replanificar esa aparición concreta
```

No representa todavía seguimiento de tiempo real.

---

# Status

Cada occurrence contiene directamente:

```text
status
```

Valores:

```text
pending
in_progress
completed
not_completed
cancelled
```

---

# Eliminación de statesByDate

No conservar:

```text
statesByDate
```

como mecanismo activo.

La relación antigua:

```text
registro
↓
fecha → status
```

se reemplaza por:

```text
Occurrence
↓
status
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

# Significado de cancelled

`cancelled` significa:

```text
estaba planeada
pero fue cancelada
```

La occurrence permanece en historial.

Su intervalo queda disponible para otra occurrence.

---

# Significado de not_completed

`not_completed` significa:

```text
estaba planeada
pero no se realizó
```

La occurrence permanece en historial.

Su intervalo también queda disponible.

---

# Ejemplo obligatorio

Debe ser válido:

```text
Gym
05:30–07:30
not_completed

Desayuno
06:00–06:30
pending
```

en la misma fecha.

---

# completed

Una occurrence:

```text
completed
```

continúa bloqueando el intervalo.

No permitir superponer silenciosamente otra occurrence activa sobre algo
registrado como realizado.

---

# Regla centralizada de bloqueo

Debe existir una responsabilidad de dominio equivalente a:

```js
blocksSchedule(occurrence)
```

No duplicar esta regla de forma incompatible entre vistas y store.

---

# Conflictos temporales

Existe conflicto únicamente cuando:

1. las occurrences pertenecen a la misma fecha;
2. ambas bloquean horario;
3. los intervalos se superponen.

Regla:

```text
newStart < existingEnd
AND
newEnd > existingStart
```

---

# Fechas diferentes

No existe conflicto temporal entre:

```text
Lunes
05:30–07:00
```

y:

```text
Martes
05:30–07:00
```

---

# Intervalos contiguos

Debe permitirse:

```text
08:00–09:00
09:00–10:00
```

---

# Validación de cambios de status

La integridad temporal ya no se valida únicamente al:

* crear;
* editar.

También debe validarse cuando una transición de status vuelve a convertir una
occurrence en bloqueante.

---

# Ejemplo obligatorio

Estado:

```text
Gym
05:30–07:30
not_completed

Desayuno
06:00–06:30
pending
```

Si el usuario intenta cambiar Gym a:

```text
pending
```

debe rechazarse porque produciría una superposición activa.

---

# Transición inválida

Cuando una transición de status sea rechazada:

* conservar status anterior;
* conservar datos anteriores;
* informar el conflicto;
* no producir un estado inválido temporal.

---

# Prioridades

La prioridad NO se almacena dentro de PlanItem ni Occurrence.

Debe derivarse desde el dominio.

Conceptualmente:

```text
NORMAL      = 100
EVENT       = 200
UNEXPECTED  = 300
```

---

# Clasificación de prioridad

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

# Override

La arquitectura debe quedar preparada para que Event y Unexpected puedan
resolver conflictos mediante una confirmación explícita del usuario.

No cancelar otra occurrence silenciosamente.

La interfaz completa de esta función puede quedar para MVP 04.0.2 según los
criterios normativos.

---

# Materialización

Debe existir una responsabilidad separada que transforme:

```text
PlanItem
+
generationConfig
+
rango temporal
```

en:

```text
Occurrence drafts
```

---

# Regla de materialización

El proceso debe:

```text
calcular fechas
↓
resolver horario
↓
construir drafts
↓
validar
↓
insertar Occurrences
```

---

# Atomicidad conceptual

Cuando una operación genera varias occurrences:

```text
validar el conjunto
antes de modificar definitivamente el store
```

No dejar una creación parcialmente aplicada sin un comportamiento explícito.

---

# Materialización idempotente

Ejecutar repetidamente:

```text
mismo PlanItem
+
mismo rango
```

no debe crear occurrences automáticas idénticas duplicadas.

Puede utilizarse para detectar duplicados:

```text
planItemId
date
startTime
endTime
```

sin convertir esa combinación en Occurrence.id.

---

# Materialización indefinida

Nunca intentar generar infinitamente.

Utilizar un horizonte finito.

---

# Horizonte mínimo inicial

La regla inicial será:

```text
resto del mes de referencia
+
mes siguiente completo
```

Ejemplo:

```text
23 agosto 2026
↓
materializar al menos hasta
30 septiembre 2026
```

El cálculo debe ser genérico.

---

# Extensión del horizonte

Cuando exista planificación explícita futura posterior al horizonte actual,
las recurrencias indefinidas deben poder extenderse hasta el final del mes de
esa planificación.

Ejemplo:

```text
Evento:
10 julio 2027
```

puede provocar materialización hasta:

```text
31 julio 2027
```

---

# Futuro e historial

Principio:

```text
pasado / historia
→ preservar

futuro pendiente
→ puede regenerarse
```

---

# Regeneración futura

Las principales occurrences candidatas a regeneración automática son:

```text
fecha futura
+
status === pending
```

No eliminar automáticamente occurrences históricas con:

```text
completed
not_completed
cancelled
in_progress
```

---

# Edición individual obligatoria

MVP 04.0.1 debe soportar como mínimo:

```text
editar una Occurrence concreta
```

Debe poder cambiar:

```text
date
startTime
endTime
```

preservando:

```text
id
planItemId
status
```

---

# Edición por semana y futuro

Los alcances:

```text
Solo esta semana
De aquí en adelante
```

deben estar soportados por la arquitectura.

Su experiencia completa corresponde principalmente a:

```text
MVP 04.0.2
```

No adelantar UI innecesaria durante 04.0.1.

---

# Position

Eliminar como propiedad persistente:

```text
position
```

La numeración visible debe derivarse después de ordenar las occurrences.

---

# Duración

No almacenar:

```text
duration
```

Calcular:

```text
endTime - startTime
```

---

# Datos iniciales

Migrar los siete registros demostrativos del MVP 03 hacia PlanItems.

Los mocks deben demostrar que:

```text
NO todos los PlanItems ocurren todos los días
```

Por ejemplo:

```text
Gym
L / X / V

CCNA
L / X / V

Cepillado
todos los días
```

La configuración exacta se encuentra en:

```text
MOCK_DATA_CONTRACT_MVP_04.md
```

---

# Status de demostración

Migrar los estados visuales anteriores hacia:

```text
Occurrence.status
```

No crear Occurrences ficticias únicamente para aplicar un fixture de status.

---

# Store

El store debe ser la única fuente mutable de:

```text
planItems
occurrences
```

Las vistas no deben mutar directamente esas colecciones.

---

# Consultas mínimas

Debe poder resolverse conceptualmente:

```text
getPlanItemById
getOccurrenceById
getOccurrencesForDate
getOccurrencesForMonth
getOccurrencesForPlanItem
```

Los nombres exactos pueden variar.

---

# Scheduling

Las responsabilidades relacionadas con:

* materialización;
* recurrencia;
* resolución de horarios;
* conflictos temporales;

deben quedar fuera de las vistas.

---

# Domain

Las responsabilidades relacionadas con:

* clasificación;
* status;
* bloqueo temporal;
* prioridades;

deben quedar centralizadas fuera de la UI.

---

# app.js

Debe continuar actuando principalmente como:

```text
coordinador
```

No convertirlo en:

* store;
* materializador;
* detector de conflictos completo;
* módulo de clasificación;
* renderer monolítico.

---

# Frontend durante MVP 04.0.1

La interfaz del MVP 03 es el baseline.

Durante esta entrega:

```text
cambiar el motor
```

sin realizar todavía:

```text
el rediseño completo de navegación temporal
```

---

# Debe conservarse visualmente

En la medida compatible con la migración:

* tema oscuro;
* paleta;
* matriz;
* encabezado;
* acciones contextuales;
* diálogo;
* estados;
* responsive;
* enlace VCS.

---

# NO implementar como objetivo de 04.0.1

No implementar todavía como objetivo principal:

```text
click completo en encabezados de fecha
selector de calendario nuevo
selector de mes
flechas mensuales nuevas
ojo abierto / cerrado
filtrado completo por selectedDate
celdas grises no programadas
separaciones visuales semanales
editor completo por alcance
formularios finales de todos los generation modes
estadísticas
gráficas
porcentajes
rachas
premios
```

Estas funciones pertenecen principalmente a:

```text
MVP 04.0.2
```

---

# Funciones completamente fuera de MVP 04.0.1

No implementar:

* backend;
* Flask;
* PostgreSQL;
* Supabase;
* API;
* autenticación;
* usuarios;
* despliegue;
* localStorage;
* estadísticas;
* subactividades;
* hábitos tipo logro;
* hábitos puntuales;
* tiempos reales;
* comentarios;
* autocompletado histórico de PlanItems;
* eliminación destructiva del historial.

---

# Eliminación

Conservar la papelera visual existente.

No implementar todavía eliminación destructiva sin una definición de negocio
completa.

La eliminación futura deberá distinguir conceptos como:

```text
quitar occurrence
cancelar
detener recurrencia
retirar planificación futura
```

---

# ROADMAP

Las funciones deliberadamente aplazadas deben conservarse en:

```text
/docs/codex/planeacion/ROADMAP_PENDING_FEATURES.md
```

Ese archivo NO autoriza implementación.

---

# Regresión

Después de la migración debe seguir siendo posible:

* abrir la aplicación;
* visualizar los registros;
* crear;
* editar;
* cambiar estados;
* seleccionar filas;
* utilizar acciones contextuales;
* utilizar la interfaz responsive;
* regresar a Vatos con Sesos.

---

# Pruebas obligatorias

La implementación debe contrastarse completamente contra la sección:

```text
MVP 04.0.1 — CRITERIOS OBLIGATORIOS
```

de:

```text
/docs/codex/ACCEPTANCE_CRITERIA_MVP_04.md
```

La sección:

```text
MVP 04.0.2 — NO EJECUTAR TODAVÍA
```

es únicamente contexto para esta ejecución.

---

# Verificación técnica

Cuando resulte aplicable:

```text
node --check
```

sobre los módulos JavaScript.

Probar imports mediante servidor HTTP local.

---

# Verificación visual

Cuando el entorno lo permita comprobar aproximadamente:

```text
1440 × 900
390 × 844
```

El objetivo visual de 04.0.1 es:

```text
no romper MVP 03
```

no implementar todavía toda la interfaz final de MVP 04.

---

# Informe final

Al terminar Codex debe informar como mínimo:

1. archivos creados;
2. archivos modificados;
3. archivos eliminados;
4. estructura final;
5. cómo quedó PlanItem;
6. cómo quedó Occurrence;
7. cómo quedó generationConfig;
8. cómo migró desde MVP 03;
9. cómo eliminó statesByDate;
10. cómo eliminó position;
11. materialización weekly;
12. materialización interval_days;
13. materialización manual_dates;
14. materialización single_date;
15. weekday overrides;
16. horizonte de materialización;
17. idempotencia;
18. detección de conflictos;
19. comportamiento de cancelled;
20. comportamiento de not_completed;
21. comportamiento de completed;
22. validación de transiciones de status;
23. edición individual de Occurrence;
24. pruebas de regresión;
25. pruebas visuales;
26. criterios no comprobados;
27. limitaciones conocidas;
28. instrucciones exactas para abrir y probar.

No declarar una función terminada si no fue implementada o comprobada.

---

# Definición de terminado — MVP 04.0.1

La entrega está terminada cuando puede demostrarse:

```text
PlanItem
        ↓
generationConfig
        ↓
materializador
        ↓
Occurrences
        ↓
agenda por fecha
```

y:

```text
Occurrence
        ↓
status propio
```

además:

```text
cancelled
not_completed
        ↓
liberan horario
```

mientras:

```text
pending
in_progress
completed
        ↓
bloquean horario
```

y todo esto ocurre sin destruir la funcionalidad aprobada del MVP 03.
