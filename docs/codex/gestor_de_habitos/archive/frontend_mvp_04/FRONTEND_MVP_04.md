Sí, ya estamos en muy buen punto para escribirlo. Incorporé tus tres ajustes:

* **eliminar** queda contemplado visualmente, pero no voy a forzar todavía la eliminación real en `04.0.1`; para `04.0.2` dejaremos preparada su interfaz y después decidimos la semántica exacta;
* en **ojo abierto**, Inicio y Duración serán `—` cuando el `PlanItem` no tenga `Occurrence` en el día seleccionado;
* la ventana de **edición será una sola interfaz dinámica**, como la describiste: horario → fecha → repetición → alcance del cambio → aceptar.

Y sí: **en `04.0.2` quiero que implementemos todos los formularios por tipo**. Éste es precisamente el momento de descubrir los problemas antes de meter PostgreSQL/backend.

Reemplaza el contenido de:

```text
docs/codex/FRONTEND_MVP_04.md
```

por esto:

````md
# Frontend — MVP 04

## Nombre general

**MVP 04 — Motor de planificación por ocurrencias**

---

# División del MVP

El MVP 04 se construye mediante dos hitos internos:

```text
MVP 04.0.1
Motor temporal, modelo y materialización

MVP 04.0.2
Navegación temporal y experiencia completa de planificación
````

Este documento define el comportamiento visual esperado para ambas etapas.

---

# Principio general

El MVP 04 cambia profundamente el modelo interno de la aplicación.

Eso NO significa que deba rediseñarse la identidad visual construida durante
MVP 01, MVP 02 y MVP 03.

La aplicación actual constituye el baseline visual.

La prioridad es:

```text
nuevo motor
+
misma identidad visual
+
nuevas interacciones coherentes
```

---

# Referencia visual actual

Conservar como base:

* tema oscuro;
* fondos gris/negro;
* acentos dorados;
* bordes discretos;
* tabla mensual;
* encabezado principal;
* título "Hábitos";
* mes visible;
* enlace Vatos con Sesos;
* botones dorados;
* acciones contextuales;
* cinco estados visuales;
* responsive actual.

No realizar un rediseño general de colores, tipografía o identidad.

---

# ============================================================

# MVP 04.0.1 — FRONTEND DE CONSERVACIÓN

# ============================================================

# Objetivo visual

MVP 04.0.1 cambia principalmente:

```text
el motor
```

y no:

```text
la experiencia visual completa
```

Al finalizar 04.0.1 la aplicación debe parecer claramente una evolución del
MVP 03 y no una aplicación diferente.

---

# Cambios mínimos permitidos

Durante MVP 04.0.1 pueden realizarse únicamente cambios visuales necesarios
para adaptar la interfaz al nuevo modelo:

```text
PlanItem
+
Occurrence
```

Ejemplos permitidos:

* actualizar textos técnicos;
* adaptar eventos de botones;
* cambiar origen de datos;
* ajustar renderizado;
* mostrar únicamente Occurrences materializadas;
* modificar errores de validación;
* realizar pequeños ajustes responsive si el nuevo modelo los requiere.

---

# Cambios NO deseados en MVP 04.0.1

No rediseñar:

* header;
* tarjetas;
* tabla;
* paleta;
* botón general;
* botones de estado;
* fila seleccionada;
* botón contextual +;
* botón editar;
* papelera;
* enlace VCS;
* distribución general.

---

# Matriz actual

La matriz mensual debe continuar funcionando sobre:

```text
Occurrences
```

aunque durante 04.0.1 todavía conserve gran parte del comportamiento visual
del MVP 03.

No reconstruir estados mediante:

```text
statesByDate
```

---

# Estados

Los botones multestado continúan utilizando:

```text
pending
in_progress
completed
not_completed
cancelled
```

La representación visual actual debe conservarse.

---

# Cambio importante del frontend de estados

Aunque visualmente continúe existiendo el ciclo:

```text
pending
→ in_progress
→ completed
→ not_completed
→ cancelled
→ pending
```

la vista ya no debe asumir que toda transición es válida.

Si el store rechaza una transición por conflicto:

* conservar el símbolo anterior;
* conservar el color anterior;
* informar el error;
* no representar temporalmente un status inválido.

---

# Cancelled y Not Completed

Visualmente continúan diferenciándose.

Ambos liberan horario para nuevas Occurrences.

Eso significa que puede existir visualmente:

```text
Gym
05:30–07:30
No realizada

Desayuno
06:00–06:30
Pendiente
```

sin considerarse un error de layout ni de dominio.

La occurrence no realizada debe continuar siendo visible como historial.

---

# ============================================================

# MVP 04.0.2 — EXPERIENCIA TEMPORAL

# ============================================================

# Objetivo

MVP 04.0.2 debe convertir el nuevo motor temporal en una experiencia de uso
centrada en:

```text
fecha seleccionada
↓
Occurrences reales de esa fecha
↓
Plan del día
```

El usuario debe poder navegar su planificación sin pensar directamente en:

* generationConfig;
* materialización;
* IDs;
* estructuras internas.

---

# Estado temporal principal

La interfaz mantendrá conceptualmente:

```js
selectedDate
visibleMonth
showAllMonthRecords
```

Estos valores son estado de interfaz.

No forman parte de PlanItem ni Occurrence.

---

# Carga inicial

Al abrir la aplicación:

```text
selectedDate
=
fecha local actual
```

y:

```text
visibleMonth
=
mes de selectedDate
```

---

# showAllMonthRecords

Valor inicial:

```js
false
```

Cada recarga debe comenzar en modo:

```text
Plan del día
```

y no en modo mensual completo.

---

# ============================================================

# SELECCIÓN DE FECHA — ESCRITORIO

# ============================================================

En vista amplia todos los encabezados de fecha deben convertirse en controles
interactivos.

Ejemplo:

```text
SÁB  DOM  LUN  MAR  MIÉ  JUE ...
 1    2    3    4    5    6
```

El usuario puede seleccionar una fecha mediante click.

---

# Encabezado completo interactivo

El control corresponde conceptualmente a:

```text
LUN
17
```

como una unidad.

No únicamente al número.

Debe utilizar un elemento accesible equivalente a:

```html
<button>
```

aunque visualmente continúe pareciendo un encabezado de tabla.

---

# Resultado del click

Al seleccionar:

```text
LUN 17
```

debe actualizarse:

```js
selectedDate
```

y posteriormente:

* resaltado de columna;
* contenido del Plan del día;
* Inicio;
* Duración;
* Occurrences visibles;
* estados correspondientes.

---

# Resaltado de fecha

La fecha seleccionada debe continuar utilizando el lenguaje visual dorado
actual.

Debe distinguirse claramente sin depender únicamente del color.

---

# ============================================================

# SELECCIÓN DE FECHA — COMPACTO

# ============================================================

La vista compacta mantiene conceptualmente:

```text
←        Lunes, 17 de Agosto        →
```

Las flechas continúan siendo navegación diaria.

---

# Flecha izquierda

Debe realizar:

```text
selectedDate - 1 día
```

---

# Flecha derecha

Debe realizar:

```text
selectedDate + 1 día
```

---

# Cruce de mes

Ejemplo:

```text
31 agosto
↓
→
↓
1 septiembre
```

debe actualizar automáticamente:

```text
selectedDate
visibleMonth
```

---

# Celda compacta de fecha

La columna actualmente visible:

```text
LUN
17
```

debe ser interactiva.

Al activarla debe abrir un selector de fecha.

---

# ============================================================

# SELECTOR DE FECHA

# ============================================================

La experiencia deseada se encuentra ilustrada en:

```text
/docs/codex/assets/assets-MVP04/selector-fecha-desktop.png
/docs/codex/assets/assets-MVP04/selector-fecha-mobile.png
```

Estas imágenes representan:

```text
la experiencia esperada
```

NO:

```text
un diseño a copiar píxel por píxel
```

---

# Preferencia por selector nativo

Utilizar preferentemente:

```html
<input type="date">
```

La aplicación puede mantener el input:

* visualmente integrado;
* oculto de manera accesible cuando corresponda;
* asociado al control visible de fecha.

---

# showPicker

Cuando exista soporte puede utilizarse:

```js
dateInput.showPicker()
```

Debe existir comportamiento alternativo cuando:

```text
showPicker
```

no esté disponible.

---

# No construir calendario complejo propio

No crear manualmente durante MVP 04:

* cálculo visual de meses;
* cuadrícula completa de calendario;
* navegación interna de años;
* gestión propia de años bisiestos;
* teclado personalizado del calendario;

si el navegador ya puede resolverlo de forma robusta.

---

# ============================================================

# NAVEGACIÓN POR MESES — ESCRITORIO

# ============================================================

La navegación por mes es distinta a la navegación diaria.

Debe existir conceptualmente:

```text
‹                                      ›
┌────────────────────────────────────────────┐
│              MATRIZ DEL MES               │
└────────────────────────────────────────────┘
```

Referencia:

```text
/docs/codex/assets/assets-MVP04/
flechas-para-navegar-meses-en-pantalla-completa.png
```

---

# Flechas mensuales

Las flechas laterales:

```text
‹
›
```

navegan entre meses.

NO representan:

```text
día anterior
día siguiente
```

---

# ============================================================

# NAVEGACIÓN POR MESES — COMPACTO

# ============================================================

En vista pequeña la navegación mensual debe integrarse alrededor del texto del
mes.

Conceptualmente:

```text
‹     Agosto de 2026     ›
```

Referencia:

```text
/docs/codex/assets/assets-MVP04/
flechas-para-navegar-meses-en-pantalla-pequeña.png
```

---

# Nombre del mes interactivo

El texto:

```text
Agosto de 2026
```

puede convertirse en control para seleccionar directamente otro mes.

---

# Selector de mes

Puede utilizarse preferentemente:

```html
<input type="month">
```

cuando exista soporte adecuado.

Puede utilizarse un selector de fecha como fallback.

---

# Navegación inteligente

Las flechas mensuales podrán utilizarse para navegar hacia planificación
existente.

Si no existe planificación en el mes inmediatamente siguiente pero sí en uno
posterior, la aplicación puede saltar al siguiente mes con planificación.

---

# Planificación indefinida

Si existe un PlanItem con:

```text
generationConfig.indefinite = true
```

debe considerarse que existe futuro conceptual aunque todavía no se haya
materializado.

La navegación puede solicitar la extensión del horizonte.

---

# Mes vacío seleccionado manualmente

El usuario debe poder seleccionar manualmente un mes vacío.

En ese caso mostrar un estado equivalente a:

```text
No hay registros programados.
```

No impedir la navegación.

---

# ============================================================

# PLAN DEL DÍA — MODO FILTRADO

# ============================================================

El comportamiento por defecto corresponde conceptualmente a:

```text
ojo cerrado
```

o:

```js
showAllMonthRecords = false
```

---

# Regla de visibilidad

Mostrar únicamente PlanItems que tengan al menos una Occurrence cuya:

```js
occurrence.date === selectedDate
```

---

# Ejemplo

Lunes:

```text
Despertar
Cepillado
Gym
Comida
CCNA
Dormir
```

Martes:

```text
Despertar
Cepillado
Comida
Dormir
```

Si:

```text
selectedDate = martes
```

Gym y CCNA no deben aparecer en modo filtrado.

---

# Fuente de verdad

La visibilidad se determina mediante:

```text
Occurrences
```

NO consultando directamente:

```text
generationConfig.weekdays
```

---

# Orden

Las Occurrences del día deben mostrarse por:

```text
startTime
```

---

# ============================================================

# MODO MENSUAL — OJO ABIERTO

# ============================================================

Debe existir un control visual equivalente a:

```text
ojo cerrado
↔
ojo abierto
```

El diseño exacto puede utilizar:

* icono;
* botón;
* símbolo accesible;

sin depender exclusivamente de la imagen del ojo.

---

# Ojo cerrado

Significa:

```text
Mostrar únicamente el Plan del día seleccionado.
```

---

# Ojo abierto

Significa:

```text
Mostrar todos los PlanItems con al menos una Occurrence dentro del mes visible.
```

---

# Estado inicial

Siempre:

```text
ojo cerrado
```

al recargar.

---

# PlanItem sin Occurrence en selectedDate

Supongamos:

```text
Gym
```

ocurre:

```text
lunes
miércoles
viernes
```

y selectedDate es martes.

Con ojo abierto:

Gym aparece porque existe dentro del mes.

Pero Inicio y Duración deben mostrar:

```text
—
—
```

No utilizar el horario de otro día.

---

# Razón

Un PlanItem puede tener:

* horarios diferentes según weekday;
* modificaciones individuales;
* excepciones;
* replanificaciones.

Mostrar un horario perteneciente a otra fecha sería información incorrecta.

---

# ============================================================

# CELDAS NO PROGRAMADAS

# ============================================================

Cuando un PlanItem no tenga Occurrence para una fecha:

la celda correspondiente debe representar:

```text
NO PROGRAMADO
```

---

# Estilo

Debe visualizarse aproximadamente como:

```text
fondo gris
sin símbolo
sin interacción
```

---

# Diferencia semántica

No programado:

```text
NO existe Occurrence
```

Cancelled:

```text
SÍ existe Occurrence
status = cancelled
```

Not completed:

```text
SÍ existe Occurrence
status = not_completed
```

Pending:

```text
SÍ existe Occurrence
status = pending
```

---

# No crear datos visuales

No crear:

```text
status = disabled
```

para representar esta celda.

La celda deshabilitada se deriva de:

```text
ausencia de Occurrence
```

---

# Interacción

Una celda no programada:

* no recorre estados;
* no crea Occurrence al hacer click;
* no debe parecer pending.

---

# Accesibilidad

Debe comunicar algo equivalente a:

```text
Gym no está programado para el martes 18 de agosto.
```

---

# ============================================================

# HORARIOS POR OCCURRENCE

# ============================================================

Inicio y Duración siempre deben resolverse a partir de:

```text
Occurrence seleccionada
```

NO:

```text
generationConfig
```

---

# Ejemplo

Gym:

```text
Lunes
05:30–07:00

Miércoles
06:00–08:00
```

Seleccionar lunes muestra:

```text
05:30
1h 30min
```

Seleccionar miércoles muestra:

```text
06:00
2h
```

---

# ============================================================

# VISUALIZACIÓN SEMANAL

# ============================================================

Referencia:

```text
/docs/codex/assets/assets-MVP04/Visualizacion-por-semanas.png
```

La matriz mensual continúa siendo:

```text
UNA SOLA TABLA
```

No crear cinco tablas independientes.

---

# Semana lógica

La división visual utiliza:

```text
lunes → domingo
```

---

# Ejemplo

Si el mes comienza sábado:

```text
SÁB  DOM ║ LUN MAR MIÉ JUE VIE SÁB DOM ║ LUN...
 1    2  ║  3   4   5   6   7   8   9 ║ 10...
```

El primer bloque es parcial.

---

# Recursos visuales permitidos

La división semanal puede utilizar:

* borde vertical ligeramente más fuerte;
* cambio discreto de fondo;
* alternancia sutil de opacidad;
* degradados muy suaves.

Debe conservar la identidad oscura actual.

---

# Fondos alternos

Puede utilizarse una estrategia similar a hojas de cálculo:

```text
semana A
fondo base

semana B
mismo color con variación ligera de opacidad

semana C
fondo base
```

El contraste debe ser discreto.

No convertir la tabla en una cuadrícula multicolor.

---

# ============================================================

# ACCIONES CONTEXTUALES

# ============================================================

La fila seleccionada conserva:

```text
+
✎
🗑
```

como acciones contextuales.

Referencia histórica:

```text
/docs/codex/assets/acciones-contextuales-fila.png
```

---

# Botón +

Continúa representando:

```text
insertar / agregar alrededor de esta posición temporal
```

Debe conservar su colocación contextual actual.

---

# Botón editar

El lápiz abre:

```text
UN SOLO DIÁLOGO DINÁMICO
```

No abrir una cadena de tres modales consecutivos.

---

# Botón eliminar

La papelera debe continuar reservada visualmente.

MVP 04 debe dejar preparada su futura experiencia.

La eliminación real no debe inventarse sin una regla de negocio clara.

Debe documentarse en:

```text
/docs/codex/planeacion/ROADMAP_PENDING_FEATURES.md
```

---

# Futuro de eliminación

La interfaz futura deberá poder distinguir al menos entre conceptos como:

```text
quitar esta aparición
detener planificación futura
cancelar
```

porque:

```text
eliminar
≠
cancelar
```

No implementar todavía una eliminación destructiva de historial salvo que los
criterios normativos se amplíen explícitamente.

---

# ============================================================

# DIÁLOGO DE EDICIÓN

# ============================================================

El lápiz debe abrir una única interfaz.

El contenido se adapta dinámicamente al PlanItem y la Occurrence seleccionada.

---

# Jerarquía visual

La jerarquía principal será:

```text
1. Horario
2. Fecha
3. Repetición
4. Alcance del cambio cuando corresponda
5. Aceptar
```

---

# Encabezado

Ejemplo:

```text
Editar — Gym
```

Debe permitir identificar claramente qué registro se está modificando.

---

# ============================================================

# 1. HORARIO

# ============================================================

Los primeros controles principales son:

```text
Hora de inicio
Hora de finalización
```

Representan la Occurrence actualmente seleccionada.

---

# Cambio de horario simple

Si únicamente cambia el horario:

```text
05:30–07:00
↓
06:00–08:00
```

y no cambia la recurrencia:

el alcance por defecto es:

```text
Solo esta fecha
```

---

# Validación

Antes de aceptar debe comprobarse:

* formato;
* endTime > startTime;
* conflictos de la fecha correspondiente;
* status bloqueantes.

---

# ============================================================

# 2. FECHA

# ============================================================

Después del horario debe existir:

```text
Fecha
```

La fecha debe poder modificarse para cualquier Occurrence.

---

# Cambio de fecha

Ejemplo:

```text
Evento
20 agosto
↓
22 agosto
```

o:

```text
Actividad periódica
20 agosto
↓
21 agosto
```

---

# Significado

Mover fecha mediante:

```text
Solo esta fecha
```

NO modifica automáticamente generationConfig.

Representa una excepción individual.

---

# Validación del cambio de fecha

Antes de aceptar:

* consultar Occurrences de la nueva fecha;
* detectar conflictos;
* aplicar reglas de prioridad cuando corresponda.

---

# ============================================================

# 3. REPETICIÓN

# ============================================================

Debajo de fecha y horario se muestra la programación/repetición cuando el
PlanItem tenga generationConfig compatible.

---

# Weekly

Para una planificación semanal debe mostrarse una banda equivalente a:

```text
L   M   X   J   V   S   D
```

Cada día debe comunicar:

1. si forma parte de la recurrencia;
2. cuál está actualmente seleccionado para edición.

---

# Día activo

Un día perteneciente a:

```text
generationConfig.weekdays
```

debe visualizarse como activo.

---

# Día inactivo

Un día no perteneciente a la recurrencia debe verse atenuado.

---

# Día actualmente editado

Debe existir un segundo indicador visual que comunique:

```text
este es el día cuyos datos estoy viendo/editando
```

No depender únicamente del mismo estilo usado para "activo".

---

# Interacción recomendada

Cada weekday puede separar conceptualmente:

```text
checkbox
→ pertenece o no a la recurrencia

label / botón del día
→ selecciona qué día se está editando
```

Esto evita confundir:

```text
seleccionar día
```

con:

```text
activar/desactivar repetición
```

---

# Cambio entre días activos

Ejemplo:

```text
L ✓
X ✓
V ✓
```

El usuario está editando lunes.

Hace click en:

```text
X
```

La interfaz carga:

```text
la Occurrence correspondiente al miércoles de esa semana
```

cuando exista.

Los controles superiores:

```text
Hora
Fecha
```

pasan a representar esa Occurrence.

---

# Día activo sin Occurrence materializada

Si generationConfig indica un weekday activo pero todavía no existe una
Occurrence materializada dentro de la semana observada:

la interfaz no debe inventar silenciosamente una occurrence modificada.

Debe utilizar las operaciones del motor previstas para crear/materializarla
cuando corresponda.

---

# Modificar días de repetición

Si el usuario cambia:

```text
L X V
```

por:

```text
L J
```

ha modificado:

```text
la configuración de recurrencia
```

y ya no basta con un simple:

```text
Aceptar esta fecha
```

---

# ============================================================

# 4. ALCANCE DEL CAMBIO

# ============================================================

Los controles de alcance deben ser dinámicos.

No mostrar opciones innecesarias cuando únicamente se está editando una
Occurrence individual.

---

# Sin cambio de recurrencia

Si únicamente se modifica:

* hora;
* fecha;

de la Occurrence actual:

el botón final:

```text
Aceptar
```

aplica conceptualmente:

```text
Solo esta fecha
```

---

# Con cambio de recurrencia

Si se modifica:

* weekdays;
* patrón;
* configuración futura;

deben aparecer antes del botón Aceptar dos opciones:

```text
Aplicar solo esta semana

Aplicar de aquí en adelante
```

---

# Comportamiento como selección de alcance

Estos controles representan el alcance de la operación.

No deben ejecutar inmediatamente el cambio.

El flujo recomendado es:

```text
modificar
↓
elegir alcance
↓
Aceptar
```

---

# Aplicar solo esta semana

Afecta:

```text
lunes → domingo
```

de la semana correspondiente.

Modifica únicamente las Occurrences del mismo PlanItem dentro de ese rango.

NO modifica permanentemente generationConfig para semanas posteriores.

---

# Aplicar de aquí en adelante

Afecta:

```text
generationConfig
```

desde la fecha efectiva correspondiente.

Debe:

* preservar pasado;
* preservar historia;
* retirar futuro pendiente regenerable;
* generar la nueva planificación.

---

# Aceptar

El botón Aceptar siempre aparece al final de la jerarquía.

Si existe un cambio de recurrencia y no se ha elegido alcance:

```text
Aceptar
```

debe permanecer deshabilitado o solicitar explícitamente la elección.

No seleccionar silenciosamente un alcance destructivo.

---

# Cancelar

Debe continuar disponible.

Cerrar mediante:

```text
Cancelar
Escape
```

no modifica datos.

---

# Retorno de foco

Al cerrar:

el foco debe regresar de forma coherente al control que abrió el diálogo.

---

# ============================================================

# CREACIÓN DINÁMICA POR TIPO

# ============================================================

Durante MVP 04.0.2 deben implementarse los formularios correspondientes a
todos los tipos actualmente aceptados por el dominio.

Este es el momento previsto para descubrir incompatibilidades antes de añadir
backend y base de datos.

---

# Flujo inicial

El diálogo comienza permitiendo seleccionar:

```text
Actividad
Hábito
```

---

# Activity

Si se selecciona:

```text
Actividad
```

mostrar:

```text
Ancla
Periódica
Evento
Imprevista
```

---

# Habit

Si se selecciona:

```text
Hábito
```

durante MVP 04 mostrar únicamente:

```text
Hábito programado
```

---

# ============================================================

# FORMULARIO — ACTIVITY / ANCHOR

# ============================================================

Debe estar orientado principalmente a:

```text
weekly
```

Campos principales:

```text
Nombre

Fecha inicial

Repetición:
L M X J V S D

Horario general:
Inicio
Final

Personalización opcional por weekday

Finalización:
○ Fecha determinada
○ Indefinidamente
```

---

# Horarios diferentes por día

Debe poder activarse una sección que permita:

```text
Lunes
05:30–07:00

Miércoles
05:30–07:00

Viernes
06:30–08:00
```

No obligar al usuario a escribir todos los horarios desde cero.

El horario general sirve inicialmente como valor base.

---

# ============================================================

# FORMULARIO — ACTIVITY / PERIODIC

# ============================================================

Debe permitir elegir el modo de programación.

Opciones:

```text
○ Días de la semana
○ Cada N días
○ Fechas específicas
```

---

# Periodic / Weekly

Utiliza:

```text
weekly
```

con el mismo concepto de weekdays.

---

# Periodic / Cada N días

Utiliza:

```text
interval_days
```

Campos:

```text
Fecha inicial
Cada [N] días
Hora inicio
Hora final
Fecha final o indefinido
```

---

# Periodic / Fechas específicas

Utiliza:

```text
manual_dates
```

Debe permitir agregar varias entradas:

```text
Fecha
Hora inicio
Hora final
```

---

# ============================================================

# FORMULARIO — ACTIVITY / EVENT

# ============================================================

Debe orientarse a fechas conocidas con anticipación.

Ejemplos:

* boda;
* concierto;
* viaje;
* graduación.

---

# Event simple

Debe permitir:

```text
Nombre
Fecha
Inicio
Final
```

utilizando:

```text
single_date
```

---

# Event con varias fechas

Puede permitir:

```text
manual_dates
```

cuando se necesitan varias fechas concretas.

---

# Event no usa recurrencia semanal automática

Durante MVP 04 no ofrecer:

```text
repetir todos los lunes
```

como comportamiento principal de Event.

---

# ============================================================

# FORMULARIO — ACTIVITY / UNEXPECTED

# ============================================================

Debe representar un imprevisto.

Ejemplos:

* ponchadura;
* emergencia;
* trámite inesperado.

---

# Fecha inicial sugerida

Debe comenzar preferentemente con:

```text
selectedDate
```

---

# Campos

```text
Nombre
Fecha
Inicio
Final
```

Utiliza principalmente:

```text
single_date
```

---

# ============================================================

# FORMULARIO — HABIT / SCHEDULED

# ============================================================

Durante MVP 04 continúa siendo un bloque temporal.

Debe permitir principalmente:

```text
weekly
```

Campos equivalentes a:

```text
Nombre

Fecha inicial

Días:
L M X J V S D

Inicio
Final

Fecha final
o
Indefinidamente
```

---

# Hábito puntual

NO implementar todavía una modalidad sin endTime.

Debe permanecer registrada en:

```text
ROADMAP_PENDING_FEATURES.md
```

para una entrega posterior.

---

# ============================================================

# CONFLICTOS Y PRIORIDADES EN FRONTEND

# ============================================================

La interfaz no debe cancelar otras Occurrences silenciosamente.

---

# Activity normal

Anchor, Periodic y Habit Scheduled utilizan prioridad normal.

Un conflicto con otra occurrence bloqueante normal debe rechazarse.

---

# Event

Un Event tiene mayor prioridad conceptual.

Si entra en conflicto con una occurrence normal debe mostrarse una
confirmación.

---

# Unexpected

Tiene prioridad conceptual superior.

También requiere confirmación.

---

# Ejemplo de confirmación

```text
Este evento entra en conflicto con:

Trabajo
08:00–17:00

Si continúas, Trabajo será cancelado únicamente para esta fecha.

[Volver]
[Continuar]
```

---

# No cancelar sin consentimiento

No modificar:

```text
status = cancelled
```

de otra occurrence sin una confirmación explícita.

---

# Conflicto con completed

No permitir override automático sobre:

```text
completed
```

durante MVP 04.

Mostrar error y detener operación.

---

# Conflicto con cancelled

No existe bloqueo temporal.

Puede utilizarse el horario.

---

# Conflicto con not_completed

Tampoco existe bloqueo temporal.

Puede utilizarse el horario.

---

# ============================================================

# ELIMINACIÓN — PREPARACIÓN

# ============================================================

La papelera continúa siendo una acción contextual importante.

Sin embargo, eliminar dentro de un sistema con historial requiere distinguir:

```text
eliminar
cancelar
detener repetición
retirar planificación futura
```

No deben tratarse como la misma operación.

---

# MVP 04

Durante MVP 04 puede prepararse:

* estilo;
* botón;
* foco;
* diálogo visual futuro;
* estructura necesaria para conectar la acción posteriormente.

No realizar una eliminación destructiva del historial sin criterios de negocio
específicos.

---

# Futuro diálogo de eliminación

Conceptualmente podrá ofrecer opciones como:

```text
Quitar solo esta aparición

Detener de aquí en adelante

Cancelar
```

La versión definitiva se diseñará en una entrega posterior.

---

# ============================================================

# RESPONSIVE

# ============================================================

La aplicación debe continuar adaptándose sin scroll horizontal global.

---

# Escritorio

Debe priorizar:

```text
matriz mensual completa
+
selección directa por encabezados
+
acciones contextuales
```

---

# Compacto

Debe priorizar:

```text
una sola fecha
+
navegación diaria
+
selector de calendario
+
navegación mensual compacta
```

---

# Acciones contextuales compactas

Los botones:

```text
+
✎
🗑
```

no deben cubrir:

* nombre;
* horario;
* status.

---

# Diálogos compactos

Todos los formularios deben:

* permanecer dentro del viewport;
* permitir scroll interno cuando sea necesario;
* no generar scroll horizontal;
* mantener accesibles Guardar/Cancelar.

---

# Formulario largo

Los formularios de Anchor y Periodic pueden superar la altura disponible.

En ese caso:

```text
contenido del dialog
→ scroll vertical interno
```

No aumentar el documento completo artificialmente.

---

# ============================================================

# ACCESIBILIDAD

# ============================================================

Todos los controles interactivos deben utilizar elementos semánticos
adecuados.

Preferir:

```html
<button>
<input>
<select>
dialog
```

sobre elementos no interactivos con listeners.

---

# Teclado

Debe funcionar mediante:

```text
Tab
Shift + Tab
Enter
Space
Escape
```

según corresponda.

---

# Foco visible

Todo control interactivo debe mostrar foco claramente.

---

# Color

Ningún estado debe depender exclusivamente del color.

Conservar:

* símbolo;
* texto accesible;
* title/aria-label cuando corresponda.

---

# Encabezado de fecha

Debe tener nombre accesible equivalente a:

```text
Ver planificación del lunes 17 de agosto de 2026
```

---

# Navegación mensual

Las flechas deben comunicar:

```text
Mes anterior con planificación
Mes siguiente con planificación
```

o el comportamiento exacto finalmente implementado.

---

# Botón del ojo

Debe comunicar explícitamente su estado.

Ejemplo:

```text
Mostrar todos los registros del mes
```

y después:

```text
Mostrar solo el plan del día
```

No usar únicamente:

```text
👁
```

sin nombre accesible.

---

# ============================================================

# REFERENCIAS VISUALES MVP 04

# ============================================================

Consultar como referencias de interacción:

```text
/docs/codex/assets/assets-MVP04/
selector-fecha-desktop.png

/docs/codex/assets/assets-MVP04/
selector-fecha-mobile.png

/docs/codex/assets/assets-MVP04/
flechas-para-navegar-meses-en-pantalla-completa.png

/docs/codex/assets/assets-MVP04/
flechas-para-navegar-meses-en-pantalla-pequeña.png

/docs/codex/assets/assets-MVP04/
Visualizacion-por-semanas.png
```

---

# Acciones contextuales

Consultar:

```text
/docs/codex/assets/acciones-contextuales-fila.png
```

---

# Referencias estadísticas

Los siguientes archivos representan exclusivamente visión futura:

```text
/docs/codex/assets/assets-MVP04/
borrador-representación-futura-estadística.png

/docs/codex/assets/assets-MVP04/
objetivo-a-futuro-2.png

/docs/codex/assets/assets-MVP04/
objetivo-a-futuro-3.png
```

---

# IMPORTANTE — NO IMPLEMENTAR ESTADÍSTICAS

Estas imágenes NO autorizan:

* porcentajes;
* barras;
* gráficas;
* rachas;
* premios;
* progreso mensual;
* progreso semanal.

Sirven únicamente para comprobar que las decisiones actuales no cierren la
puerta a esa evolución.

---

# ============================================================

# FUERA DE ALCANCE

# ============================================================

No implementar durante MVP 04 salvo modificación normativa posterior:

* estadísticas;
* rachas;
* premios;
* gráficos;
* porcentajes;
* subactividades;
* hábitos tipo logro;
* hábitos puntuales;
* cantidades;
* tiempos reales;
* comentarios;
* autenticación;
* usuarios;
* Flask;
* PostgreSQL;
* API;
* Supabase;
* despliegue;
* notificaciones;
* autocompletado histórico de PlanItems;
* eliminación destructiva avanzada.

---

# ============================================================

# RESULTADO VISUAL ESPERADO

# ============================================================

MVP 04.0.1 debe sentirse visualmente como:

```text
MVP 03
+
nuevo motor debajo
```

MVP 04.0.2 debe sentirse como:

```text
el mismo producto
+
control real sobre fechas
+
planificación dinámica
+
navegación temporal
```

No como una reconstrucción estética.

---

# Principio final de frontend

El usuario nunca debe necesitar comprender:

```text
PlanItem
Occurrence
generationConfig
materialización
```

para utilizar la aplicación.

Debe experimentar simplemente:

```text
¿Qué tengo planeado este día?

¿Qué tengo planeado este mes?

¿Cuándo quiero que esto se repita?

¿Qué quiero cambiar?

¿Solo hoy?

¿Esta semana?

¿De aquí en adelante?
```

El frontend traduce esas decisiones humanas al motor temporal definido por el
MVP 04.
