# Frontend MVP 02

## Nombre de la entrega

**Creación e inserción de actividades con refactor modular**

---

# Propósito

Esta entrega ampliará el prototipo existente para permitir crear nuevas
actividades desde la interfaz.

También reorganizará el JavaScript actual mediante módulos ES, separando:

- datos;
- estado de la aplicación;
- reglas de estados;
- fechas y tiempos;
- renderizado de la matriz;
- formulario;
- coordinación general.

La aplicación continuará funcionando exclusivamente en el navegador y
los cambios permanecerán únicamente en memoria.

---

# Principio de conservación

El Frontend MVP 01 ya funciona correctamente y su apariencia visual fue
aprobada.

Esta entrega no debe rediseñar la aplicación.

Debe conservar:

- la paleta actual;
- el fondo oscuro;
- los acentos dorados;
- la matriz mensual;
- el encabezado;
- la leyenda;
- el resaltado del día actual;
- la vista completa de escritorio;
- la vista compacta;
- la navegación entre días;
- los cinco estados;
- los símbolos actuales;
- el ciclo de estados;
- el uso mediante teclado;
- la ausencia de desplazamiento horizontal global.

Los nuevos controles deben integrarse con la identidad visual existente.

---

# Resultado visible esperado

Al terminar esta entrega, la interfaz permitirá:

1. Consultar la matriz existente.
2. Cambiar los estados de cada actividad y fecha.
3. Pulsar un botón general `Agregar actividad`.
4. Abrir un formulario mediante un diálogo.
5. Registrar nombre, hora inicial y hora final.
6. Validar los datos antes de guardarlos.
7. Agregar la actividad a la matriz sin recargar.
8. Seleccionar una fila existente.
9. Mostrar un botón contextual circular `+`.
10. Insertar una actividad tomando una fila como referencia.
11. Mantener todas las actividades ordenadas cronológicamente.
12. Continuar funcionando en escritorio y vista compacta.

---

# Arquitectura modular

La estructura JavaScript esperada es:

```text
modules/gestor_de_habitos/
├── index.html
├── css/
│   └── gestor_habitos.css
└── js/
    ├── data/
    │   └── mock-activities.js
    ├── domain/
    │   └── activity-status.js
    ├── state/
    │   └── activity-store.js
    ├── utils/
    │   └── date-time.js
    ├── views/
    │   ├── activity-matrix.js
    │   └── activity-form.js
    └── app.js
```

## Entrada de JavaScript

El HTML debe cargar únicamente:

```html
<script type="module" src="./js/app.js"></script>
```

Los demás archivos se conectarán mediante:

```js
import
export
```

Los scripts anteriores que ya no se utilicen deberán eliminarse después
de trasladar correctamente su funcionalidad.

No deben existir dos implementaciones activas del mismo comportamiento.

---

# Responsabilidades

## `data/mock-activities.js`

Debe contener exclusivamente:

- actividades iniciales;
- estados iniciales de demostración;
- datos necesarios para comprobar los cinco estados.

No debe:

- manipular el DOM;
- mantener la fecha seleccionada;
- contener funciones de renderizado;
- abrir formularios.

---

## `domain/activity-status.js`

Debe contener:

- estados permitidos;
- orden del ciclo;
- símbolos;
- etiquetas visibles;
- información accesible;
- función para obtener el siguiente estado;
- función o datos necesarios para representar un estado.

Estados:

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

No debe contener la lista de actividades.

---

## `state/activity-store.js`

Debe ser la única parte autorizada para modificar la colección de
actividades en memoria.

Debe encargarse de:

- inicializar actividades;
- obtener actividades;
- ordenar actividades;
- agregar una actividad al final lógico;
- insertar una actividad antes de una referencia;
- cambiar el estado de una actividad en una fecha;
- renumerar posiciones;
- buscar una actividad por identificador.

Las vistas no deben modificar directamente:

```js
statesByDate
```

ni insertar objetos directamente dentro del arreglo.

---

## `utils/date-time.js`

Debe contener funciones relacionadas con fechas y horas:

- crear claves locales `YYYY-MM-DD`;
- obtener los días de un mes;
- comparar fechas locales;
- formatear nombre de mes;
- formatear nombre del día;
- calcular duración;
- validar que una hora final sea posterior a la inicial;
- convertir una hora `HH:MM` a minutos cuando sea necesario.

No debe:

- manipular el DOM;
- modificar actividades;
- mantener selección visual.

---

## `views/activity-matrix.js`

Debe encargarse de representar:

- encabezado de la matriz;
- columnas del mes;
- filas de actividades;
- hora;
- duración;
- nombre;
- controles multestado;
- día actual;
- día seleccionado;
- fila seleccionada;
- botón contextual `+`;
- leyenda de estados.

Debe comunicar las acciones mediante callbacks o funciones proporcionadas
por `app.js`.

No debe modificar directamente el store.

---

## `views/activity-form.js`

Debe encargarse de:

- abrir el diálogo;
- configurar modo normal;
- configurar modo de inserción contextual;
- mostrar la actividad de referencia;
- rellenar sugerencias;
- leer valores del formulario;
- mostrar errores;
- limpiar errores;
- reiniciar campos;
- cerrar el diálogo;
- restaurar el foco.

No debe agregar directamente una actividad al store.

Debe entregar los datos validados a `app.js`.

---

## `app.js`

Debe coordinar la aplicación.

Debe:

1. Inicializar el store.
2. Configurar la fecha actual.
3. Mantener la fecha seleccionada.
4. Inicializar las vistas.
5. Conectar los eventos.
6. Solicitar actividades al store.
7. Solicitar renderizados.
8. Recibir datos del formulario.
9. Enviar la actividad nueva al store.
10. Volver a renderizar.
11. Mantener la fecha seleccionada después de cada cambio.

No debe contener todas las funciones de renderizado ni todas las reglas
de fechas.

Debe servir como mapa general del funcionamiento.

---

# Botón general `Agregar actividad`

Debe añadirse un botón visible con texto:

```text
+ Agregar actividad
```

Puede integrarse dentro de:

- el encabezado de la matriz; o
- la zona introductoria de `Plan del día`.

Debe:

- mantener la identidad visual existente;
- ser visible en escritorio;
- ser visible en vista compacta;
- ser un `<button>`;
- funcionar con clic;
- funcionar con teclado;
- tener foco visible;
- abrir el diálogo en modo normal.

En modo normal no existe una actividad de referencia.

La nueva actividad se agrega al store y después se ordena por horario.

---

# Selección de filas

Cada fila debe poder seleccionarse mediante clic en una zona no interactiva.

Solo una fila puede estar seleccionada.

La fila seleccionada debe recibir una clase:

```text
is-selected
```

Su diseño puede utilizar:

- un fondo ligeramente diferente;
- un borde;
- un acento dorado;
- una combinación sutil de estos recursos.

No debe:

- cambiar el ancho de la tabla;
- mover columnas;
- ocultar contenido;
- activar un estado;
- modificar los datos.

## Interacciones que no seleccionan una fila

Pulsar estos controles no debe seleccionar ni deseleccionar accidentalmente
la fila:

- botón multestado;
- botón contextual `+`;
- cualquier control futuro dentro de la fila.

Los eventos deberán manejarse correctamente para evitar propagación
involuntaria.

## Segunda selección

Cuando el usuario seleccione otra fila:

- la selección anterior desaparece;
- la nueva fila recibe `is-selected`;
- el botón contextual pasa a la nueva referencia.

Pulsar nuevamente la fila ya seleccionada puede deseleccionarla, siempre
que el comportamiento se implemente de forma consistente.

---

# Botón contextual `+`

Cuando una fila esté seleccionada debe aparecer un botón circular:

```text
+
```

Su significado es:

> Agregar una nueva actividad antes de esta actividad.

## Apariencia

Debe:

- tener forma circular;
- mostrar borde visible;
- utilizar un fondo contrastante;
- integrarse con la paleta actual;
- ser visible sin tapar la información;
- aparecer cerca del comienzo superior de la fila;
- no aumentar permanentemente el ancho de todas las filas.

La posición exacta puede adaptarse a las limitaciones semánticas de una
tabla HTML.

## Accesibilidad

Debe ser un botón real.

Debe incluir una etiqueta equivalente a:

```text
Agregar una actividad antes de Gym - Pecho
```

Debe:

- funcionar mediante teclado;
- mostrar foco;
- no depender únicamente del símbolo `+`.

## Comportamiento

Al activarlo:

1. Se conserva el identificador de la fila de referencia.
2. Se abre el formulario.
3. El formulario entra en modo `insert-before`.
4. Se informa al usuario dónde se insertará.
5. Puede sugerirse la hora inicial de la referencia.
6. El usuario puede cambiar libremente las horas.
7. Guardar envía la intención de inserción al store.

---

# Regla de orden e inserción

El orden visual final siempre será:

1. `plannedStartTime`;
2. `position`.

La intención `insert-before` sirve como criterio secundario.

## Caso con la misma hora

Ejemplo:

```text
07:50 — Nueva actividad
07:50 — Cepillado de dientes
```

La nueva actividad debe aparecer antes de la referencia mediante su
posición secundaria.

## Caso con hora anterior

Ejemplo:

```text
07:30 — Nueva actividad
07:50 — Cepillado de dientes
```

La nueva actividad aparece antes por orden cronológico.

## Caso con hora posterior

Ejemplo:

```text
08:10 — Nueva actividad
07:50 — Cepillado de dientes
```

Aunque el formulario se haya abierto desde `Cepillado de dientes`, la
actividad nueva debe aparecer después porque la hora tiene prioridad.

No se deben modificar automáticamente las horas de otras actividades.

---

# Diálogo de creación

Debe utilizar:

```html
<dialog>
```

El diálogo debe contener un formulario semántico.

## Encabezado

En modo normal puede mostrar:

```text
Agregar actividad
```

En modo contextual puede mostrar:

```text
Agregar antes de: Gym - Pecho
```

---

# Campos

## Nombre

Utilizar:

```html
<input type="text">
```

Debe tener:

- `label`;
- atributo `required`;
- longitud máxima razonable;
- ayuda o error asociado.

La aplicación debe:

- eliminar espacios exteriores;
- rechazar un valor vacío;
- rechazar un valor formado solamente por espacios.

Longitud máxima recomendada:

```text
80 caracteres
```

---

## Hora inicial

Utilizar:

```html
<input type="time">
```

Debe:

- ser obligatorio;
- usar el formato nativo del navegador;
- producir un valor conceptual `HH:MM`.

---

## Hora final

Utilizar:

```html
<input type="time">
```

Debe:

- ser obligatorio;
- ser posterior a la hora inicial;
- pertenecer al mismo día;
- no permitir una duración igual a cero;
- no permitir una actividad que cruce medianoche.

---

# Validaciones

La aplicación debe detectar:

1. Nombre vacío.
2. Nombre con espacios únicamente.
3. Hora inicial vacía.
4. Hora final vacía.
5. Hora final igual a la inicial.
6. Hora final anterior a la inicial.

Los mensajes deben mostrarse dentro del diálogo.

No utilizar únicamente:

```js
alert()
```

Debe existir una región accesible, por ejemplo:

```html
<div role="alert" aria-live="polite"></div>
```

Cuando exista un error:

- no se crea la actividad;
- el diálogo permanece abierto;
- el primer campo inválido recibe foco cuando sea razonable.

---

# Botones del formulario

Debe incluir:

```text
Guardar
Cancelar
```

## Guardar

Debe:

- validar;
- crear un objeto válido;
- enviarlo a `app.js`;
- cerrar el diálogo después de guardar;
- limpiar el formulario;
- devolver el foco al botón que abrió el diálogo.

## Cancelar

Debe:

- cerrar el diálogo;
- no crear actividades;
- no modificar el store;
- borrar mensajes de error;
- borrar los campos;
- limpiar la referencia contextual;
- devolver el foco al control de origen.

## Tecla Escape

El comportamiento nativo de `dialog` puede permitir cerrar mediante
`Escape`.

Al cerrarse así deben limpiarse:

- campos;
- errores;
- modo contextual;
- referencia de actividad.

No se necesita todavía advertencia por cambios sin guardar.

---

# Creación de identificadores

Cada actividad nueva necesita un identificador único.

Debe intentarse primero:

```js
crypto.randomUUID()
```

Si no está disponible, debe usarse una alternativa local que combine
elementos como:

- fecha actual;
- número aleatorio;
- contador interno.

No debe utilizarse únicamente el nombre, porque dos actividades pueden
compartirlo.

---

# Estado inicial de una actividad nueva

Una actividad nueva debe tener:

```js
statesByDate: {}
```

Toda fecha sin entrada explícita se interpreta como:

```text
pending
```

No deben crearse manualmente estados `pending` para cada día del mes.

---

# Renderizado después de guardar

Después de agregar una actividad:

1. El store modifica su estado interno.
2. Las actividades se ordenan.
3. Las posiciones se renumeran.
4. La matriz vuelve a renderizarse.
5. Los controles multestado vuelven a conectarse.
6. La fecha seleccionada permanece.
7. El día actual continúa resaltado.
8. El diálogo se cierra.
9. La fila seleccionada puede limpiarse.
10. La actividad nueva puede recibir un resaltado temporal opcional.

El resaltado temporal no es obligatorio.

---

# Comportamiento responsive

## Escritorio amplio

Debe conservar:

- mes completo;
- todos los días;
- lista temporal;
- nombres;
- estados;
- diseño actual.

El botón general debe integrarse sin deformar la matriz.

El botón contextual no debe:

- agregar una columna permanente;
- desplazar todas las fechas;
- tapar botones de estado.

---

## Vista compacta

Debe conservar:

- fecha seleccionada;
- navegación anterior y siguiente;
- posición;
- hora;
- duración;
- actividad;
- estado del día seleccionado.

El botón general debe permanecer visible.

El diálogo debe:

- tener ancho máximo;
- usar el ancho disponible;
- caber dentro del viewport;
- permitir desplazamiento vertical interno cuando sea necesario;
- no producir desplazamiento horizontal.

El botón contextual debe:

- seguir siendo visible;
- no ocultar el nombre;
- no bloquear el estado;
- ser alcanzable mediante teclado.

---

# Accesibilidad

La entrega debe conservar y ampliar la accesibilidad existente.

Debe:

- utilizar HTML semántico;
- utilizar botones nativos;
- asociar `label` con cada campo;
- proporcionar nombres accesibles;
- mantener foco visible;
- manejar foco del diálogo;
- utilizar mensajes de error accesibles;
- no depender únicamente del color;
- mantener símbolos y texto;
- permitir uso mediante `Tab`, `Enter` y barra espaciadora.

---

# Datos en memoria

Todos los cambios permanecerán únicamente durante la sesión actual.

Al recargar:

- regresan las siete actividades iniciales;
- desaparecen actividades nuevas;
- regresan los estados de demostración.

El aviso de memoria temporal debe mantenerse.

No implementar:

- `localStorage`;
- archivos JSON;
- base de datos;
- API.

---

# Funciones aplazadas

No implementar en esta entrega:

- edición de actividades;
- eliminación;
- comentarios;
- subactividades;
- tiempos reales;
- seguimiento temporal expandido;
- reajuste automático;
- recurrencia semanal;
- tipos de actividad;
- estadísticas;
- autenticación;
- backend;
- integración con el índice principal.

---

# Pruebas esperadas

Codex debe comprobar:

## Regresión

- mes actual correcto;
- días correctos;
- siete actividades iniciales;
- orden correcto;
- duraciones correctas;
- navegación compacta;
- ciclo de estados;
- día actual resaltado.

## Creación

- actividad válida al final;
- actividad válida antes de una referencia;
- actividad con hora anterior;
- actividad con hora igual;
- actividad con hora posterior;
- renumeración de posiciones;
- estados funcionales después del renderizado.

## Validación

- nombre vacío;
- nombre con espacios;
- hora inicial vacía;
- hora final vacía;
- horas iguales;
- hora final anterior.

## Cancelación

- botón Cancelar;
- tecla Escape;
- ausencia de modificaciones después de cancelar.

## Responsive

- escritorio amplio;
- vista compacta;
- diálogo dentro del viewport;
- ausencia de scroll horizontal global.

## Accesibilidad básica

- navegación con teclado;
- foco visible;
- etiquetas;
- mensajes de error;
- retorno de foco.