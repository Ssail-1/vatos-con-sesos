# Frontend MVP 03

## Nombre de la entrega

**Integridad temporal, registros tipados y acciones contextuales**

---

# Propósito

El Frontend MVP 03 fortalece el submódulo:

```text
Gestor de hábitos
└── Plan del día
```

La entrega parte del Frontend MVP 02 y añade:

* clasificación básica de los registros;
* validación real de conflictos temporales;
* edición de registros existentes;
* acciones contextuales mejoradas;
* navegación hacia Vatos con Sesos.

Esta entrega continúa utilizando exclusivamente:

* HTML;
* CSS;
* JavaScript nativo;
* módulos ES;
* datos almacenados en memoria.

No existe todavía persistencia.

---

# Principio de conservación

El Frontend MVP 02 ya está aprobado visual y funcionalmente.

El MVP 03 debe conservar:

* diseño oscuro;
* paleta actual;
* acentos dorados;
* encabezado;
* matriz mensual;
* nombre del mes;
* todos los días del mes en escritorio;
* una sola fecha en vista compacta;
* navegación compacta;
* fecha seleccionada;
* resaltado del día actual;
* siete registros iniciales;
* orden temporal;
* duración calculada;
* cinco estados;
* ciclo multestado;
* leyenda;
* selección de filas;
* botón general `+ Agregar actividad`;
* diálogo de creación;
* funcionamiento mediante teclado;
* accesibilidad básica;
* ausencia de scroll horizontal global.

No realizar un rediseño general.

Los cambios visuales deben limitarse a integrar las nuevas funciones.

---

# Identidad del submódulo

La aplicación completa se denomina:

```text
Vatos con Sesos
```

Dentro de ella existe:

```text
Gestor de hábitos
```

El componente que actualmente se está desarrollando se denomina:

```text
Plan del día
```

`Plan del día` representa elementos que ocupan un espacio temporal dentro de una jornada.

Por esta razón, todos los registros pertenecientes a esta vista deben tener:

* hora planeada de inicio;
* hora planeada de finalización.

---

# Tipos de registros

El formulario debe permitir distinguir entre:

```text
Actividad
Hábito programado
```

Estos conceptos representan la primera clasificación semántica del sistema.

No deben confundirse con los estados:

```text
Pendiente
En progreso
Completada
No realizada
Cancelada
```

La clasificación describe **qué es el registro**.

El estado describe **qué ocurrió con él en una fecha determinada**.

---

# Actividades

Cuando el usuario seleccione:

```text
Actividad
```

debe elegir uno de tres subtipos.

## Ancla

Valor conceptual:

```text
anchor
```

Representación visible:

```text
Ancla
```

Representa una actividad relativamente fija alrededor de la cual se organiza el día.

Ejemplos:

* entrada al trabajo;
* escuela;
* una cita;
* una clase con horario fijo.

En el MVP 03 este subtipo solamente se registra.

Todavía no modifica automáticamente el comportamiento de los horarios.

---

## Periódica

Valor conceptual:

```text
periodic
```

Representación visible:

```text
Periódica
```

Representa una actividad planeada que normalmente vuelve a realizarse.

Ejemplos:

* gimnasio;
* estudiar;
* hacer compras;
* realizar tareas domésticas.

La recurrencia todavía no se implementa.

---

## Imprevista

Valor conceptual:

```text
unexpected
```

Representación visible:

```text
Imprevista
```

Representa una actividad que apareció fuera de la planificación original.

Ejemplos:

* reparar una llanta;
* realizar un trámite inesperado;
* atender una emergencia.

En esta entrega únicamente se registra su clasificación.

---

# Hábito programado

Cuando el usuario seleccione:

```text
Hábito
```

el único subtipo disponible en esta entrega será:

```text
scheduled
```

Representación visible:

```text
Hábito programado
```

Ejemplos:

* despertarse;
* cepillarse los dientes;
* tomar agua a una hora determinada;
* prepararse para dormir.

Un hábito programado ocupa un espacio temporal dentro del día.

Por tanto, debe tener:

* hora inicial;
* hora final.

También debe respetar las reglas de integridad temporal.

---

# Hábitos fuera de Plan del día

Los hábitos que representan logros diarios sin una ubicación temporal concreta no deben implementarse aquí.

Ejemplos:

```text
Hoy no fumé
Hoy no bebí alcohol
Hoy no hice FAP
Cumplí mi meta diaria de agua
Leí determinada cantidad
```

Estos pertenecen a un futuro submódulo:

```text
Gestor de hábitos
└── Logros diarios
```

No crear todavía:

* interfaz;
* campos;
* estados especiales;
* cantidades;
* objetivos;
* métricas;

para este tipo de hábitos.

---

# Formulario de creación

El diálogo existente debe ampliarse.

Debe continuar utilizando:

```html
<dialog>
```

El formulario debe incluir:

1. Nombre.
2. Tipo de registro.
3. Subtipo cuando corresponda.
4. Hora de inicio.
5. Hora de finalización.
6. Región accesible de errores.
7. Guardar.
8. Cancelar.

---

# Nombre

Debe continuar utilizando:

```html
<input type="text">
```

Reglas:

* obligatorio;
* máximo 80 caracteres;
* eliminar espacios exteriores;
* no aceptar únicamente espacios.

Ejemplo:

```text
"   Gimnasio   "
```

debe almacenarse como:

```text
"Gimnasio"
```

---

# Selector de tipo

Debe permitir elegir entre:

```text
Actividad
Hábito
```

La implementación puede utilizar:

* `<select>`;
* radio buttons;
* otro elemento HTML nativo accesible.

No utilizar librerías externas.

---

# Comportamiento al seleccionar Actividad

Cuando el usuario seleccione:

```text
Actividad
```

debe aparecer o habilitarse la selección:

```text
Ancla
Periódica
Imprevista
```

Por defecto puede seleccionarse:

```text
Periódica
```

El usuario debe poder cambiarlo.

---

# Comportamiento al seleccionar Hábito

Cuando el usuario seleccione:

```text
Hábito
```

el subtipo debe convertirse automáticamente en:

```text
Hábito programado
```

Como en esta entrega solo existe un subtipo de hábito, no es obligatorio mostrar un selector con una única opción.

Puede mostrarse únicamente un texto informativo.

---

# Horas

Los campos de horario continúan utilizando:

```html
<input type="time">
```

Debe existir:

* hora inicial;
* hora final.

Ambas son obligatorias.

La hora final debe ser posterior a la inicial.

No se permiten cruces de medianoche.

---

# Integridad temporal

## Regla fundamental

Dentro de `Plan del día` no pueden existir dos registros cuyos intervalos se superpongan.

La validación se aplica a:

* actividades ancla;
* actividades periódicas;
* actividades imprevistas;
* hábitos programados.

No existen excepciones por clasificación dentro del MVP 03.

---

# Regla de detección

Conceptualmente existe superposición cuando:

```text
nuevo_inicio < final_existente
Y
nuevo_final > inicio_existente
```

---

# Ejemplo válido

```text
Trabajo
08:00 → 12:00

Comida
12:00 → 12:30
```

Los intervalos son contiguos.

No existe conflicto.

---

# Ejemplo inválido

```text
Trabajo
08:00 → 12:00

Comida
11:45 → 12:30
```

Existe superposición.

El registro no debe guardarse.

---

# Segundo ejemplo inválido

```text
Preparación del día siguiente
21:15 → 21:45

Dormir
21:43 → 22:43
```

El segundo registro comienza antes de que termine el primero.

Debe rechazarse.

---

# Tercer ejemplo inválido

```text
CCNA / Estudio
19:15 → 20:15

Trabajo
14:31 → 20:20
```

Aunque `Trabajo` comience mucho antes, su intervalo contiene parcialmente el horario de `CCNA / Estudio`.

Debe rechazarse.

---

# Comparación contra todos los registros

La aplicación no debe comprobar únicamente:

* el registro anterior;
* el registro posterior;
* la fila seleccionada.

Debe comprobar el intervalo contra todos los registros existentes.

---

# Mensaje de conflicto

Cuando exista conflicto, el diálogo debe permanecer abierto.

Debe mostrarse un mensaje equivalente a:

```text
El horario se cruza con “CCNA / Estudio” (19:15–20:15).
```

El mensaje debe:

* identificar el registro conflictivo;
* mostrar su intervalo;
* ser accesible;
* no utilizar únicamente `alert()`.

---

# Creación normal

La validación temporal debe ejecutarse cuando el usuario crea mediante:

```text
+ Agregar actividad
```

No debe agregarse nada al store mientras exista conflicto.

---

# Inserción contextual

La validación también se aplica cuando se utiliza el botón contextual:

```text
+
```

La intención:

```text
Agregar antes de esta actividad
```

no permite crear un horario inválido.

---

# Sugerencia contextual

Cuando el usuario utiliza el botón `+` sobre una fila, el formulario puede sugerir horarios tomando como referencia la actividad seleccionada.

Una estrategia permitida es:

```text
hora final sugerida
=
hora inicial de la actividad seleccionada
```

La aplicación también puede utilizar el final del registro inmediatamente anterior como referencia para el inicio.

Estas sugerencias no deben guardar automáticamente nada.

El usuario puede modificarlas.

La validación final tiene la última palabra.

---

# Orden cronológico

Después de crear o editar, el orden continúa siendo:

1. Hora de inicio.
2. Posición como criterio secundario.

Con la nueva regla de no superposición, normalmente no existirán dos registros simultáneos con intervalos coincidentes.

No modificar automáticamente el horario de otros registros para hacer espacio.

---

# Edición de registros

El MVP 03 debe permitir editar.

La edición reutiliza el mismo `<dialog>`.

No crear un formulario de edición completamente separado.

---

# Modos del diálogo

El diálogo tendrá conceptualmente al menos:

```text
create
insert_before
edit
```

---

# Modo create

Se abre mediante:

```text
+ Agregar actividad
```

El formulario inicia limpio.

No existe registro de referencia.

---

# Modo insert_before

Se abre mediante el botón contextual `+`.

Debe mostrar una referencia equivalente a:

```text
Agregar antes de: SQL
```

Puede proponer horarios relacionados con esa actividad.

---

# Modo edit

Se abre mediante el botón:

```text
✎
```

Debe mostrar un título equivalente a:

```text
Editar actividad
```

o:

```text
Editar: SQL
```

---

# Datos al editar

El formulario debe rellenarse con:

* nombre actual;
* tipo actual;
* subtipo actual;
* hora inicial actual;
* hora final actual.

---

# Guardar edición

Al guardar:

* no crear un registro nuevo;
* mantener el mismo identificador;
* mantener los estados existentes;
* actualizar únicamente los datos editables;
* validar el horario;
* volver a ordenar;
* renumerar posiciones;
* volver a renderizar.

---

# Validación temporal al editar

Durante la validación debe ignorarse el propio registro.

Ejemplo:

Si se está editando:

```text
Gym
05:30 → 07:15
```

la aplicación no debe detectar al mismo `Gym` como conflicto consigo mismo.

Sí debe compararlo contra todos los demás registros.

---

# Estados al editar

Editar un registro no debe modificar:

```text
statesByDate
```

Ejemplo:

Si un registro estaba:

```text
Lunes → completed
Martes → pending
Miércoles → not_completed
```

debe conservar esos estados aunque:

* cambie de nombre;
* cambie su horario;
* cambie de tipo.

---

# Fila seleccionada

El comportamiento existente de selección se mantiene.

Solo una fila puede estar seleccionada.

La fila seleccionada:

* recibe una distinción visual;
* muestra las acciones contextuales;
* conserva sus controles de estado.

---

# Acciones contextuales

Cuando una fila esté seleccionada deben aparecer:

```text
+
✎
🗑
```

Cuando no esté seleccionada:

* no deben ocupar espacio visual innecesario;
* no deben mostrarse.

---

# Referencia visual

La composición de las acciones contextuales debe inspirarse directamente en:

```text
/docs/codex/assets/acciones-contextuales-fila.png
```

Esta imagen es una referencia normativa para la disposición general.

No se exige una reproducción pixel por pixel.

---

# Composición esperada

Conceptualmente:

```text
                     +        
                     │        
┌──────────┬─────────┴─────────────────────────────────────────┐
│ 20:20    │ 20min   │ NOMBRE DE ACTIVIDAD              ✎   🗑 │
└──────────┴─────────┴─────────────────────────────────────────┘
```

---

# Botón contextual `+`

## Posición

Debe asociarse específicamente con la celda del nombre.

Su centro debe quedar aproximadamente encima de:

```text
esquina superior izquierda de la celda del nombre
```

No debe estar encima de:

* posición;
* hora;
* duración.

---

# Tamaño

Debe ser menor al utilizado en MVP 02.

Tamaño visual objetivo aproximado:

```text
22px – 28px
```

La implementación puede variar ligeramente para conservar una superficie de interacción accesible.

---

# Posicionamiento

Puede utilizarse:

```css
position: absolute;
```

respecto a un contenedor apropiado dentro de la celda del nombre.

La solución no debe:

* deformar toda la tabla;
* agregar una columna;
* mover permanentemente las demás filas.

---

# Nombre desplazado

Cuando aparezca el botón `+`, el nombre puede recibir espacio adicional a la izquierda.

Ejemplo conceptual:

```text
+    SQL
```

El desplazamiento debe existir únicamente cuando sea necesario para evitar que el botón cubra el texto.

---

# Botón editar

Debe aparecer dentro de la celda del nombre.

Posición:

```text
extremo derecho
```

antes del botón eliminar.

Representación:

```text
✎
```

Puede utilizar otro símbolo visual equivalente siempre que:

* no requiera librerías;
* sea reconocible;
* tenga texto accesible.

Debe ser un `<button>`.

Ejemplo de `aria-label`:

```text
Editar SQL
```

---

# Botón eliminar

Debe aparecer después de editar.

Representación deseada:

```text
🗑
```

Puede utilizarse un símbolo equivalente sin recursos externos.

---

# Estado del botón eliminar

En esta entrega el botón eliminar no tiene comportamiento destructivo.

Debe ser visualmente reconocible, pero no debe eliminar nada.

La implementación preferida es:

```html
disabled
```

Debe comunicar su estado.

Ejemplo de ayuda:

```text
Eliminar SQL — disponible próximamente
```

Puede utilizar:

```text
title
```

o una etiqueta accesible equivalente.

---

# Interacción con estados

Pulsar:

```text
+
✎
🗑
```

no debe cambiar accidentalmente el estado del registro.

Pulsar el botón multestado tampoco debe abrir el formulario ni activar una acción contextual accidentalmente.

Debe manejarse correctamente la propagación de eventos.

---

# Botón general

El botón existente:

```text
+ Agregar actividad
```

debe conservarse.

Aunque ahora también permita crear hábitos programados, puede conservar temporalmente ese texto para no rediseñar el encabezado.

Preferentemente, durante este MVP puede actualizarse a:

```text
+ Agregar registro
```

si el cambio se integra naturalmente con el diseño.

La decisión debe explicarse en el informe final.

No cambiar otros elementos visuales solo para acompañar este texto.

---

# Navegación a Vatos con Sesos

Debe añadirse un enlace dentro del encabezado.

El enlace apunta conceptualmente a:

```text
../../index.html
```

La ruta debe comprobarse desde:

```text
modules/gestor_de_habitos/index.html
```

utilizando servidor local.

---

# Escritorio

En una pantalla amplia se espera una composición equivalente a:

```text
Hábitos           ⌂ Vatos con Sesos           Agosto de 2026
```

La posición central puede ajustarse según el layout.

Debe mantener:

* balance visual;
* legibilidad;
* diseño actual.

---

# Vista compacta

Cuando el espacio sea reducido debe mostrarse:

```text
⌂ VCS
```

en lugar del texto largo.

Puede utilizarse:

```html
<span class="full-label">Vatos con Sesos</span>
<span class="compact-label">VCS</span>
```

y alternarse mediante CSS.

No es obligatorio utilizar exactamente esas clases.

---

# Símbolo de casa

Puede utilizarse un símbolo textual equivalente a:

```text
⌂
```

No utilizar librerías de iconos.

El símbolo no debe ser la única descripción del enlace.

---

# Accesibilidad del enlace

Debe utilizarse:

```html
<a>
```

No un `<button>` que simule navegación.

Debe tener un nombre accesible equivalente a:

```text
Volver a la página principal de Vatos con Sesos
```

Debe:

* funcionar con teclado;
* mostrar foco;
* mantener contraste suficiente.

---

# Estados

Los cinco estados existentes se conservan exactamente:

```text
pending
in_progress
completed
not_completed
cancelled
```

Ciclo:

```text
pending
→ in_progress
→ completed
→ not_completed
→ cancelled
→ pending
```

La implementación del MVP 03 no debe modificar:

* significado;
* símbolos;
* colores;
* etiquetas;
* accesibilidad.

---

# Duración

La duración continúa siendo calculada.

No debe almacenarse como propiedad.

Se obtiene desde:

```text
plannedEndTime - plannedStartTime
```

Si una edición cambia las horas, la duración debe actualizarse automáticamente.

---

# Responsive

## Escritorio

Debe conservar:

* matriz mensual completa;
* todos los días;
* encabezado actual;
* acciones contextuales;
* botón general;
* enlace a VCS;
* ausencia de scroll horizontal global.

---

## Vista compacta

Debe conservar:

* una sola fecha;
* navegación anterior/siguiente;
* posición;
* inicio;
* duración;
* nombre;
* estado;
* selección;
* acciones contextuales;
* botón general;
* enlace `VCS`.

Las acciones contextuales no deben cubrir permanentemente:

* nombre;
* estado;
* hora;
* duración.

---

# Diálogo responsive

El formulario ampliado debe caber en móvil.

Puede:

* organizar campos verticalmente;
* utilizar ancho máximo;
* permitir scroll vertical interno.

No debe producir scroll horizontal global.

---

# Accesibilidad

Las nuevas funciones deben cumplir como mínimo:

* botones reales;
* enlace real para navegación;
* `label` en campos;
* navegación mediante Tab;
* activación mediante Enter o barra espaciadora;
* foco visible;
* retorno de foco al cerrar diálogo;
* `aria-label` en acciones contextuales;
* mensajes de validación accesibles;
* significado no dependiente únicamente de color.

---

# Persistencia temporal

Todos los cambios continúan viviendo únicamente en memoria.

Al recargar:

* se restauran registros iniciales;
* se pierden registros creados;
* se pierden ediciones;
* se restauran estados demostrativos.

El aviso de temporalidad debe mantenerse.

---

# No implementar en MVP 03

Queda expresamente fuera:

* eliminación real;
* confirmación de eliminación;
* recurrencia;
* semana ideal;
* backend;
* PostgreSQL;
* Supabase;
* API;
* `localStorage`;
* comentarios;
* notas por actividad;
* subactividades;
* tiempos reales;
* seguimiento temporal expandido;
* reajuste automático;
* hábitos tipo logro;
* hábitos cuantitativos;
* estadísticas;
* rachas;
* porcentajes;
* notificaciones;
* autenticación;
* despliegue.

---

# Pruebas esperadas

Codex deberá comprobar al menos los siguientes escenarios.

## Regresión MVP 02

* siete registros iniciales;
* mes actual;
* días correctos;
* navegación compacta;
* creación;
* inserción;
* cinco estados;
* duración;
* responsive.

---

## Clasificación

Crear:

```text
Actividad → Ancla
Actividad → Periódica
Actividad → Imprevista
Hábito → Programado
```

Comprobar que los datos se conservan correctamente.

---

## Conflictos temporales

Comprobar:

### Sin conflicto

```text
19:15–20:15
20:15–20:40
```

Debe permitirse.

### Superposición parcial inicial

```text
19:15–20:15
20:00–20:40
```

Debe rechazarse.

### Superposición parcial final

```text
19:15–20:15
19:00–19:30
```

Debe rechazarse.

### Intervalo contenido

```text
19:15–20:15
19:30–20:00
```

Debe rechazarse.

### Intervalo contenedor

```text
19:15–20:15
19:00–20:30
```

Debe rechazarse.

---

# Edición

Comprobar:

* cambiar nombre;
* cambiar tipo;
* cambiar subtipo;
* cambiar horario sin conflicto;
* cambiar horario con conflicto;
* conservar `id`;
* conservar `statesByDate`;
* recalcular duración;
* reordenar si cambia la hora.

---

# Acciones contextuales

Comprobar:

* selección de una fila;
* aparición del `+`;
* aparición del lápiz;
* aparición de papelera;
* `+` abre inserción;
* lápiz abre edición;
* papelera no elimina;
* controles desaparecen o cambian al seleccionar otra fila;
* controles no modifican estados accidentalmente.

---

# Navegación VCS

Comprobar:

* ruta correcta;
* funcionamiento en escritorio;
* texto largo en escritorio;
* texto `VCS` en compacto;
* navegación mediante teclado;
* foco visible.

---

# Resultado final

El Frontend MVP 03 se considera funcional cuando puede demostrarse:

```text
Crear
+
Clasificar
+
Validar horarios
+
Editar
+
Conservar estados
+
Utilizar acciones contextuales
+
Regresar a Vatos con Sesos
```

sin perder ninguna función aprobada del MVP 02.
