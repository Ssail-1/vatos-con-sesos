# Tarea actual

## Nombre

**Frontend MVP 03 — Integridad temporal, registros tipados y acciones contextuales**

---

# Estado previo

El Frontend MVP 02 está implementado y constituye la base estable de esta entrega.

Actualmente el submódulo **Plan del día** permite:

* mostrar una matriz mensual;
* visualizar todos los días del mes en escritorio;
* visualizar únicamente el día seleccionado en vista compacta;
* navegar entre días en vista compacta;
* mostrar actividades ordenadas por hora;
* calcular duración estimada;
* manejar cinco estados por actividad y fecha;
* crear actividades nuevas en memoria;
* insertar actividades tomando una fila como referencia;
* seleccionar filas;
* mostrar un botón contextual `+`;
* utilizar un formulario mediante `<dialog>`;
* validar nombre, hora inicial y hora final;
* funcionar mediante módulos ES;
* conservar todos los cambios únicamente en memoria.

El MVP 03 debe construirse sobre esta implementación.

No se autoriza sustituirla por una interfaz diferente ni rehacer el módulo desde cero.

---

# Objetivo general

Fortalecer el submódulo **Plan del día** mediante cuatro mejoras principales:

1. Garantizar la integridad temporal de los registros.
2. Introducir una clasificación semántica inicial para actividades y hábitos programados.
3. Incorporar edición y mejorar las acciones contextuales de cada fila.
4. Integrar visualmente el submódulo con la aplicación principal **Vatos con Sesos**.

Esta entrega continúa siendo exclusivamente frontend y todos los datos permanecerán en memoria.

---

# Nombre funcional del submódulo

La aplicación completa se denomina:

```text
Vatos con Sesos
```

Dentro de ella existe:

```text
Gestor de hábitos
```

La vista que actualmente se está construyendo representa específicamente:

```text
Plan del día
```

`Plan del día` contiene registros que ocupan un espacio temporal dentro del día.

Los hábitos sin una posición temporal concreta, como logros diarios, no forman parte de esta entrega.

---

# Resultado visible esperado

Al terminar el MVP 03, el usuario podrá:

1. Abrir `Plan del día`.
2. Mantener todas las funciones del MVP 02.
3. Crear un registro indicando si es:

   * una actividad;
   * un hábito programado.
4. Si es una actividad, indicar si es:

   * ancla;
   * periódica;
   * imprevista.
5. Crear registros únicamente cuando su horario no se superponga con otro.
6. Seleccionar una fila.
7. Ver acciones contextuales únicamente para esa fila:

   * agregar antes;
   * editar;
   * eliminar, solo como control visual todavía.
8. Editar el nombre, tipo y horario de un registro existente.
9. Conservar sus estados históricos en memoria después de editarlo.
10. Volver a la página principal de **Vatos con Sesos** mediante un enlace dentro del encabezado.

---

# Integridad temporal

## Regla principal

Dos registros del `Plan del día` no pueden ocupar simultáneamente el mismo intervalo de tiempo.

Se considera conflicto cuando:

```text
nuevo_inicio < final_existente
Y
nuevo_final > inicio_existente
```

Debe validarse contra **todos los registros existentes**, no solamente contra el registro anterior o posterior.

---

# Horarios contiguos

Los registros pueden tocarse sin producir conflicto.

Ejemplo válido:

```text
Actividad A
19:15 → 20:15

Actividad B
20:15 → 20:40
```

Esto debe permitirse.

---

# Ejemplos de conflicto

Ejemplo inválido:

```text
Actividad existente:
19:15 → 20:15

Nueva actividad:
20:00 → 20:40
```

Existe superposición.

Otro ejemplo inválido:

```text
Preparación del día siguiente:
21:15 → 21:45

Dormir:
21:43 → 22:43
```

La segunda actividad comienza antes de que termine la primera.

---

# Mensaje de conflicto

Cuando exista una superposición, el formulario debe permanecer abierto y mostrar un mensaje comprensible.

Ejemplo:

```text
El horario se cruza con “Preparación del día siguiente” (21:15–21:45).
```

Si existen varios conflictos, puede mostrarse el primero encontrado o una lista breve.

No se debe crear ni modificar el registro mientras exista un conflicto.

---

# Validación al crear

La detección de conflictos debe aplicarse tanto a:

* creación normal;
* inserción contextual.

El botón contextual `+` no permite saltarse las reglas temporales.

La referencia visual indica dónde desea insertar el usuario, pero la hora sigue determinando la posición cronológica real.

---

# Validación al editar

Cuando se edite un registro existente:

* debe comprobarse nuevamente su horario;
* debe compararse contra todos los demás registros;
* debe ignorarse el propio registro durante la búsqueda de conflictos.

Ejemplo:

Al editar `Gym`, la validación no debe considerar al `Gym` original como un conflicto consigo mismo.

---

# Validación en dos niveles

La integridad temporal debe protegerse en dos lugares.

## Formulario

Debe detectar el problema y proporcionar retroalimentación inmediata al usuario.

## Store

Debe validar defensivamente antes de insertar o actualizar los datos.

Esto evita que otra parte del frontend pueda introducir accidentalmente un registro inválido.

---

# Clasificación semántica de registros

Cada registro de `Plan del día` debe tener una clasificación básica.

## Tipo principal

Los únicos valores permitidos en esta entrega son:

```text
activity
habit
```

Conceptualmente:

```text
Actividad
Hábito programado
```

---

# Actividad

Cuando el usuario seleccione:

```text
Actividad
```

debe seleccionar también uno de estos subtipos:

```text
anchor
periodic
unexpected
```

Representación visible:

```text
Ancla
Periódica
Imprevista
```

---

# Actividad ancla

Representa un bloque relativamente fijo alrededor del cual se organiza el día.

Ejemplos:

* trabajo;
* escuela;
* cita importante;
* horario fijo.

En este MVP el subtipo solamente se registra.

Todavía no modifica automáticamente el comportamiento temporal ni protege el bloque contra futuros reajustes automáticos.

---

# Actividad periódica

Representa una actividad que normalmente se planea con anticipación y puede repetirse en el futuro.

Ejemplos:

* gimnasio;
* estudiar;
* hacer compras;
* realizar una tarea doméstica.

La recurrencia real todavía no se implementa.

---

# Actividad imprevista

Representa una actividad que surge dentro de un día y que originalmente no formaba parte del plan.

Ejemplos:

* reparar una ponchadura;
* atender un trámite inesperado;
* resolver una emergencia.

En esta entrega solamente se registra el subtipo.

---

# Hábito programado

Cuando el usuario seleccione:

```text
Hábito
```

el único subtipo permitido en este MVP será:

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
* tomar agua en un momento planeado;
* prepararse para dormir.

Todos los hábitos programados incluidos en `Plan del día` continúan ocupando un intervalo de tiempo y deben tener:

* hora inicial;
* hora final.

También deben respetar las reglas de no superposición.

---

# Hábitos tipo logro

Los hábitos basados en cumplimiento diario sin horario concreto quedan expresamente fuera de `Plan del día`.

Ejemplos:

* hoy no fumé;
* hoy no tomé alcohol;
* hoy no hice FAP;
* cumplí mi cantidad diaria de agua;
* leí cierta cantidad de páginas.

Estos pertenecen a un futuro submódulo del Gestor de hábitos, provisionalmente denominado:

```text
Logros diarios
```

No implementar sus datos, campos ni interfaz en esta entrega.

---

# Formulario de creación

El formulario actual debe ampliarse.

Debe incluir:

* nombre;
* tipo principal;
* subtipo cuando corresponda;
* hora inicial;
* hora final.

---

# Selector de tipo principal

Debe permitir:

```text
Actividad
Hábito programado
```

Puede implementarse mediante:

* `<select>`;
* radio buttons;
* otro control nativo accesible.

La decisión visual debe mantener el diseño existente.

---

# Selector de subtipo

## Si el tipo es `activity`

Debe mostrarse:

```text
Ancla
Periódica
Imprevista
```

## Si el tipo es `habit`

Debe establecerse:

```text
scheduled
```

No es obligatorio mostrar un segundo selector si solamente existe un subtipo de hábito.

Puede mostrarse simplemente una indicación:

```text
Hábito programado
```

---

# Valores iniciales sugeridos

Para reducir fricción, el formulario puede iniciar con:

```text
Tipo: Actividad
Subtipo: Periódica
```

Siempre que el usuario pueda modificarlos antes de guardar.

---

# Edición de registros

El mismo `<dialog>` utilizado para crear debe reutilizarse para editar.

No debe existir un segundo formulario completamente diferente.

El formulario tendrá al menos estos modos conceptuales:

```text
create
insert_before
edit
```

---

# Modo editar

Al pulsar el botón de edición:

1. Se obtiene el registro correspondiente.
2. Se abre el diálogo.
3. Los campos se rellenan con los valores actuales.
4. El encabezado indica claramente que se está editando.
5. Guardar modifica el registro existente.
6. No se genera un nuevo identificador.
7. No se crea una segunda actividad.
8. La matriz vuelve a ordenarse si cambia la hora.
9. Las posiciones se renumeran.
10. El registro permanece seleccionado cuando sea razonable.

---

# Datos que se pueden editar

En esta entrega se permite modificar:

* nombre;
* tipo principal;
* subtipo;
* hora inicial;
* hora final.

No se permite editar mediante este diálogo:

* estados históricos;
* comentarios;
* tiempos reales;
* subactividades;
* recurrencia.

---

# Conservación de identidad

Al editar debe conservarse:

```text
id
```

El registro sigue siendo la misma entidad.

---

# Conservación de estados

Al editar también debe conservarse completamente:

```text
statesByDate
```

Ejemplo:

Si `Gym` estaba completado el lunes y pendiente el martes, cambiar su nombre u horario no debe borrar esos estados.

---

# Acciones contextuales de fila

Las acciones contextuales deben aparecer únicamente cuando una fila esté seleccionada.

Las acciones serán:

```text
+
✎
🗑
```

Conceptualmente:

```text
Agregar antes
Editar
Eliminar
```

---

# Referencia visual normativa

Debe consultarse:

```text
/docs/codex/assets/acciones-contextuales-fila.png
```

Esta imagen define la intención visual principal de las acciones contextuales.

No debe interpretarse como una exigencia de reproducción pixel por pixel, pero sí debe respetarse su composición.

---

# Botón contextual `+`

El botón `+` debe modificarse respecto al MVP 02.

## Posición deseada

Su centro debe ubicarse aproximadamente sobre:

> la esquina superior izquierda de la celda que contiene el nombre de la actividad.

No debe ubicarse:

* al inicio completo del renglón;
* sobre la celda de posición;
* sobre la celda de hora;
* sobre la celda de duración.

Debe asociarse visualmente con la **celda del nombre**.

---

# Representación conceptual

```text
                     +        
                     │        
┌──────────┬─────────+─────────────────────────────────────┐
│ 20:20    │ 20min   │ SQL                         ✎   🗑   │
└──────────┴─────────┴─────────────────────────────────────┘
```

---

# Tamaño del botón `+`

Debe ser más pequeño que en el MVP 02.

El diámetro visual esperado es aproximadamente:

```text
22px – 28px
```

Puede ajustarse ligeramente si es necesario para:

* accesibilidad;
* foco visible;
* responsive;
* legibilidad.

No debe dominar visualmente la fila.

---

# Superposición y nombre

El botón puede posicionarse mediante CSS de forma absoluta respecto a la celda del nombre.

Si al aparecer necesita ocupar espacio visual sobre el nombre:

* el texto del nombre puede recibir padding adicional;
* puede desplazarse ligeramente hacia la derecha.

Esto es preferible a que el botón cubra el texto.

---

# Botón editar

El botón de edición debe aparecer:

* únicamente cuando la fila está seleccionada;
* dentro de la celda del nombre;
* hacia el extremo derecho;
* antes del botón de eliminar.

Debe usar un símbolo equivalente a:

```text
✎
```

o un icono similar creado sin dependencias externas.

Debe:

* ser un `<button>`;
* funcionar con teclado;
* mostrar foco;
* tener un `aria-label`.

Ejemplo:

```text
Editar SQL
```

---

# Botón eliminar

También debe aparecer únicamente cuando la fila está seleccionada.

Debe ubicarse:

* dentro de la celda del nombre;
* al extremo derecho;
* después del botón editar.

Puede utilizar:

```text
🗑
```

o un símbolo equivalente sin dependencia externa.

---

# Eliminación no funcional

En el MVP 03 el botón eliminar es únicamente una preparación visual.

No debe:

* eliminar registros;
* modificar el store;
* abrir confirmaciones;
* cambiar estados.

Debe mostrarse visualmente como no disponible.

Preferentemente utilizar:

```html
disabled
```

y un texto accesible equivalente a:

```text
Eliminar SQL — disponible próximamente
```

Puede incluir un `title` equivalente a:

```text
Eliminar actividad — próximamente
```

---

# Selección de fila

El comportamiento del MVP 02 debe conservarse.

Solo una fila puede estar seleccionada a la vez.

Cuando una fila está seleccionada:

* aparece el `+`;
* aparece editar;
* aparece eliminar;
* la fila conserva su resaltado visual.

Pulsar cualquiera de esos controles no debe provocar accidentalmente:

* cambio de estado;
* deselección;
* selección de otra fila.

---

# Navegación hacia Vatos con Sesos

El encabezado debe incorporar un enlace hacia la página principal del proyecto.

Desde:

```text
modules/gestor_de_habitos/index.html
```

la ruta esperada es conceptualmente:

```text
../../index.html
```

Debe comprobarse que la ruta realmente funcione desde el servidor local.

---

# Escritorio

En una pantalla amplia, el encabezado debe mostrar conceptualmente:

```text
Hábitos       ⌂ Vatos con Sesos       Agosto de 2026
```

El enlace a Vatos con Sesos debe ocupar una zona central razonable.

No es obligatorio que quede matemáticamente centrado si eso rompe el responsive.

---

# Vista compacta

En una pantalla reducida, el enlace debe adaptarse conceptualmente a:

```text
⌂ VCS
```

La abreviación evita saturar el encabezado.

Puede implementarse mediante CSS mostrando u ocultando textos diferentes.

---

# Accesibilidad del enlace

Debe ser un `<a>` real.

Debe:

* funcionar con teclado;
* tener foco visible;
* conservar contraste;
* incluir un nombre accesible.

Ejemplo:

```text
Volver a la página principal de Vatos con Sesos
```

El símbolo de casa no debe ser la única información accesible.

---

# Store

El store continúa siendo la única fuente mutable de actividades.

Debe ampliarse para soportar conceptualmente una operación equivalente a:

```js
updateActivity(activityId, activityDraft)
```

Debe conservar:

* identificador;
* estados existentes.

Debe modificar:

* nombre;
* tipo;
* subtipo;
* inicio;
* final.

Después debe:

* validar;
* ordenar;
* renumerar;
* devolver el registro actualizado.

---

# Detección de conflictos en el store

El store debe proporcionar o utilizar una regla equivalente a:

```text
hasTimeConflict(start, end, ignoredActivityId?)
```

Al crear:

```text
ignoredActivityId = null
```

Al editar:

```text
ignoredActivityId = id del propio registro
```

No es obligatorio utilizar exactamente ese nombre de función.

Sí es obligatorio conservar esa responsabilidad.

---

# Responsive

Todas las funciones del MVP 02 deben seguir funcionando en:

* escritorio amplio;
* vista compacta.

Los nuevos controles contextuales deben adaptarse sin:

* superponer texto;
* provocar scroll horizontal global;
* deformar columnas;
* hacer inaccesibles los controles de estado.

---

# Persistencia

La aplicación continúa utilizando solamente memoria.

Al recargar:

* desaparecen registros creados;
* desaparecen modificaciones;
* regresan los datos iniciales;
* regresan los estados de demostración originales.

Esto es correcto para esta entrega.

---

# Fuera de alcance

No implementar todavía:

* eliminación real;
* confirmación de eliminación;
* recurrencia semanal;
* semana ideal;
* comentarios;
* subactividades;
* tiempos reales;
* seguimiento temporal expandido;
* hábitos tipo logro;
* hábitos cuantitativos;
* reajuste automático de horarios;
* backend;
* API;
* PostgreSQL;
* Supabase;
* autenticación;
* estadísticas;
* rachas;
* porcentajes;
* notificaciones;
* despliegue.

---

# Resultado esperado

El MVP 03 debe demostrar este flujo:

```text
Usuario crea o edita un registro
        ↓
Selecciona su clasificación
        ↓
Introduce un intervalo temporal
        ↓
El frontend valida el formulario
        ↓
El store comprueba que no exista superposición
        ↓
El registro se crea o actualiza
        ↓
La matriz se ordena y renumera
        ↓
Los estados anteriores permanecen intactos
```

Y también:

```text
Usuario selecciona una fila
        ↓
Aparecen +, editar y eliminar
        ↓
+ crea antes de la referencia
✎ permite editar
🗑 se muestra como función futura
```

Y:

```text
Usuario pulsa ⌂ Vatos con Sesos
        ↓
Regresa al index principal de la aplicación
```

---

# Entrega de Codex

Al finalizar Codex debe informar:

1. Archivos modificados.
2. Archivos creados.
3. Archivos eliminados.
4. Estructura final.
5. Cambios realizados al contrato de datos.
6. Implementación de validación temporal.
7. Implementación de edición.
8. Implementación de tipos y subtipos.
9. Implementación de acciones contextuales.
10. Implementación del enlace a Vatos con Sesos.
11. Pruebas de regresión del MVP 02.
12. Pruebas de creación.
13. Pruebas de edición.
14. Pruebas de superposición.
15. Pruebas responsive.
16. Pruebas de teclado.
17. Criterios que no pudo verificar.
18. Limitaciones conocidas.

No debe declarar completada una función que no haya implementado o verificado.
