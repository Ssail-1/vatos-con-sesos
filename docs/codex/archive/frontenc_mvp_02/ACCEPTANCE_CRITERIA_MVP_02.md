# Criterios de aceptación — Frontend MVP 02

## Nombre de la entrega

**Creación e inserción de actividades con refactor modular**

---

# Propósito

Este documento establece las condiciones objetivas que deben cumplirse
para considerar terminada la segunda entrega frontend del módulo:

```text
modules/gestor_de_habitos/
```

La entrega combina:

1. Conservación completa del Frontend MVP 01.
2. Refactor modular del JavaScript.
3. Creación de actividades en memoria.
4. Inserción normal.
5. Inserción contextual antes de una fila.
6. Validaciones del formulario.
7. Comportamiento responsive.
8. Accesibilidad básica.

Crear únicamente archivos, formularios o estructuras internas no significa
que la entrega esté terminada.

Debe existir un flujo funcional completo y comprobable.

---

# 1. Límites del área de trabajo

La entrega cumple este apartado cuando:

- Todo el código creado o modificado se encuentra dentro de:

```text
modules/gestor_de_habitos/
```

- No se modificó el `index.html` principal del repositorio.
- No se modificó el CSS principal.
- No se modificó el JavaScript principal.
- No se modificó `modules/dev_notes/`.
- No se modificaron los documentos de `docs/`.
- No se modificó `AGENTS.md`.
- No se modificó `.gitignore`.
- No se modificó `README.md`.
- No se realizaron cambios en otros módulos.
- No se realizaron commits.
- No se realizó `git push`.
- No se cambió de rama.
- No se ejecutaron comandos destructivos.

Cualquier necesidad de cambio externo debe informarse sin ejecutarse.

---

# 2. Tecnologías

La entrega cumple este apartado cuando utiliza exclusivamente:

- HTML;
- CSS;
- JavaScript nativo;
- módulos ES;
- datos almacenados temporalmente en memoria;
- elementos nativos del navegador.

Debe utilizar:

```html
<script type="module" src="./js/app.js"></script>
```

No debe utilizar:

- Flask;
- Python;
- PostgreSQL;
- Supabase;
- API;
- `localStorage`;
- `sessionStorage`;
- IndexedDB;
- archivos JSON externos;
- React;
- Vue;
- Angular;
- frameworks CSS;
- npm;
- librerías externas;
- servicios externos;
- herramientas de compilación.

---

# 3. Preservación visual del Frontend MVP 01

La entrega cumple este apartado cuando conserva:

- el fondo oscuro;
- la paleta actual;
- los acentos dorados;
- el encabezado de `Hábitos`;
- el nombre del mes actual;
- el panel de la matriz;
- la leyenda de estados;
- la estructura compacta de las filas;
- la identidad visual aprobada;
- el día actual resaltado;
- la fecha seleccionada resaltada;
- la apariencia de escritorio;
- la apariencia compacta;
- la ausencia de scroll horizontal global.

No debe existir un rediseño general.

Se permiten únicamente ajustes visuales necesarios para integrar:

- el botón general;
- la selección de filas;
- el botón contextual;
- el diálogo.

Los cambios nuevos deben mantener la personalidad visual existente.

---

# 4. Regresión funcional del Frontend MVP 01

Después del refactor deben continuar funcionando:

- obtención del mes local actual;
- generación correcta de todos los días del mes;
- encabezados abreviados de cada día;
- renderizado de las siete actividades originales;
- orden por hora y posición;
- cálculo de duración estimada;
- resaltado del día actual;
- resaltado del día seleccionado;
- visualización mensual completa en escritorio;
- visualización de una sola fecha en vista compacta;
- navegación al día anterior;
- navegación al día siguiente;
- límites al principio y al final del mes;
- leyenda de estados;
- control multestado;
- uso mediante teclado;
- aviso de persistencia temporal.

La refactorización falla si alguna función anterior deja de operar,
aunque la interfaz continúe viéndose correctamente.

---

# 5. Arquitectura modular

La estructura final debe ser equivalente a:

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

Se acepta un ajuste menor únicamente cuando:

- exista una justificación técnica;
- no agregue capas innecesarias;
- respete la separación por responsabilidades;
- sea explicado en el resumen final.

---

# 6. Responsabilidades de los módulos

## `data/mock-activities.js`

Debe:

- contener los siete datos iniciales;
- conservar sus nombres;
- conservar sus horarios;
- conservar sus estados demostrativos;
- exportar datos iniciales;
- evitar manipulación directa del DOM.

No debe:

- renderizar;
- abrir formularios;
- manejar la fecha seleccionada;
- modificar estados durante la interacción.

---

## `domain/activity-status.js`

Debe:

- declarar los cinco estados;
- declarar sus símbolos;
- declarar sus etiquetas;
- conservar sus colores actuales;
- definir el ciclo de estados;
- permitir obtener el siguiente estado;
- proporcionar información accesible.

No debe:

- almacenar actividades;
- modificar el arreglo principal;
- renderizar la matriz completa.

---

## `state/activity-store.js`

Debe:

- recibir una copia de los datos iniciales;
- poseer la colección mutable de actividades;
- obtener actividades sin exponer innecesariamente el arreglo interno;
- buscar una actividad por identificador;
- agregar una actividad;
- insertar antes de una referencia;
- cambiar el estado de una actividad y fecha;
- ordenar actividades;
- renumerar posiciones;
- validar defensivamente datos estructurales.

Las vistas no deben modificar directamente:

```js
statesByDate
```

ni utilizar:

```js
activities.push(...)
```

sobre la colección interna.

---

## `utils/date-time.js`

Debe encargarse de:

- claves locales `YYYY-MM-DD`;
- cálculo de días del mes;
- comparación de fechas;
- formateo de mes;
- formateo de fecha seleccionada;
- abreviación de días;
- conversión de hora a minutos;
- cálculo de duración;
- validación del orden de horas.

No debe:

- manipular el DOM;
- mantener la colección de actividades;
- abrir el diálogo.

---

## `views/activity-matrix.js`

Debe encargarse de:

- encabezado mensual;
- encabezados de fechas;
- creación de filas;
- información temporal;
- nombres;
- controles multestado;
- leyenda;
- día actual;
- día seleccionado;
- selección visual de una fila;
- botón contextual;
- actualización visual de la matriz.

Debe comunicar acciones mediante callbacks.

No debe modificar directamente el store.

---

## `views/activity-form.js`

Debe encargarse de:

- abrir el diálogo;
- mostrar modo normal;
- mostrar modo contextual;
- indicar la actividad de referencia;
- leer campos;
- mostrar errores;
- limpiar errores;
- reiniciar campos;
- cancelar;
- cerrar;
- gestionar el foco;
- entregar un borrador validado.

No debe agregar directamente la actividad al store.

---

## `app.js`

Debe:

- inicializar el store;
- mantener la fecha seleccionada;
- mantener la fila seleccionada cuando corresponda;
- conectar store y vistas;
- coordinar eventos;
- recibir borradores del formulario;
- decidir entre inserción normal o contextual;
- pedir al store la creación;
- solicitar un nuevo renderizado;
- conservar el flujo general comprensible.

`app.js` no debe volver a concentrar todas las funciones anteriores.

---

# 7. Eliminación de implementaciones duplicadas

La entrega cumple este apartado cuando:

- el HTML carga solamente `app.js` como módulo;
- `mock-data.js` anterior ya no está activo;
- `status-control.js` anterior ya no está activo;
- no existen dos ciclos de estados distintos;
- no existen dos fuentes de datos simultáneas;
- no existen dos funciones activas para renderizar la misma matriz;
- los archivos obsoletos se eliminan después de migrar su funcionalidad;
- no permanecen scripts muertos cargados por el HTML.

No se considera correcta una modularización que simplemente copie el
código anterior y deje ambas versiones funcionando.

---

# 8. Datos iniciales

Al abrir la página deben mostrarse exactamente siete actividades iniciales:

1. Gym - Pecho
2. Cepillado de dientes
3. Meditar
4. Hybridge - Programación
5. Comida
6. CCNA / Estudio
7. Preparación del día siguiente

Deben conservar:

- horarios originales;
- duraciones originales;
- orden cronológico;
- estados de demostración;
- posiciones consecutivas.

La colección mutable no debe dañar permanentemente la definición inicial.

Al recargar deben restaurarse los datos originales.

---

# 9. Botón general de agregar

Debe existir un botón visible con texto equivalente a:

```text
+ Agregar actividad
```

Debe:

- ser un `<button>`;
- encontrarse en una zona coherente;
- verse en escritorio;
- verse en vista compacta;
- mantener la identidad visual;
- funcionar con clic;
- funcionar mediante teclado;
- mostrar foco visible;
- tener un nombre accesible;
- abrir el formulario en modo normal.

Al abrirse desde este botón:

- no existe actividad de referencia;
- el título indica creación normal;
- el formulario inicia limpio.

---

# 10. Diálogo de creación

Debe existir un elemento:

```html
<dialog>
```

Debe contener:

- título;
- formulario;
- campo de nombre;
- campo de hora inicial;
- campo de hora final;
- región para errores;
- botón Guardar;
- botón Cancelar.

El diálogo debe:

- abrirse correctamente;
- recibir foco;
- mantener el foco dentro del flujo nativo razonable;
- cerrarse al guardar;
- cerrarse al cancelar;
- poder cerrarse con Escape;
- limpiar el estado después del cierre;
- devolver el foco al elemento que lo abrió.

No debe depender de `alert()` para informar errores.

---

# 11. Campo de nombre

El campo de nombre debe:

- utilizar `input type="text"`;
- tener `label`;
- ser obligatorio;
- aceptar caracteres en español;
- eliminar espacios exteriores;
- rechazar un valor vacío;
- rechazar espacios únicamente;
- limitarse a un máximo razonable de 80 caracteres.

Casos que deben rechazarse:

```text
""
"     "
```

Caso que debe normalizarse:

```text
"   Leer documentación   "
```

Resultado:

```text
"Leer documentación"
```

---

# 12. Campos de tiempo

La hora inicial y final deben:

- usar `input type="time"`;
- ser obligatorias;
- entregar un valor `HH:MM`;
- validarse antes de guardar.

Deben rechazarse:

- hora inicial vacía;
- hora final vacía;
- horas iguales;
- hora final anterior a la inicial;
- actividad que cruce medianoche;
- valor `24:00`.

Ejemplo válido:

```text
10:00 → 10:30
```

Ejemplos inválidos:

```text
10:00 → 10:00
10:30 → 10:00
23:30 → 00:30
```

---

# 13. Mensajes de validación

Los errores deben aparecer dentro del diálogo.

Debe existir una región accesible mediante:

```text
role="alert"
```

o:

```text
aria-live
```

Los mensajes deben ser comprensibles.

Ejemplos:

```text
Escribe el nombre de la actividad.
Selecciona una hora de inicio.
Selecciona una hora de finalización.
La hora final debe ser posterior a la hora inicial.
```

Cuando exista un error:

- no se agrega la actividad;
- el diálogo permanece abierto;
- no se modifica el store;
- el primer campo inválido recibe foco cuando sea razonable.

---

# 14. Creación normal de actividad

Al guardar una actividad válida desde el botón general:

- se genera un identificador único;
- se limpia el nombre;
- se conservan las horas;
- se crea `statesByDate: {}`;
- se asigna una posición;
- se agrega al store;
- se ordena cronológicamente;
- se renumeran las posiciones;
- se cierra el diálogo;
- se vuelve a renderizar;
- aparece la actividad sin recargar;
- sus estados comienzan en `pending`;
- sus botones multestado funcionan.

La actividad nueva no debe requerir estados explícitos para cada fecha.

---

# 15. Identificador único

Debe utilizarse preferentemente:

```js
crypto.randomUUID()
```

Debe existir una alternativa cuando no esté disponible.

El identificador:

- debe ser texto;
- no debe depender exclusivamente del nombre;
- no debe repetirse dentro de la sesión;
- debe mantenerse estable durante la sesión.

---

# 16. Selección de filas

Debe poder seleccionarse una fila mediante clic en una zona no interactiva.

Al seleccionar:

- se almacena el identificador de referencia;
- la fila recibe `is-selected`;
- aparece una distinción visual;
- solo una fila permanece seleccionada;
- seleccionar otra elimina la selección anterior.

La selección no debe:

- modificar estados;
- alterar horarios;
- cambiar posiciones;
- abrir el diálogo automáticamente;
- deformar la tabla.

Pulsar un botón de estado no debe seleccionar accidentalmente la fila.

Pulsar el botón contextual no debe disparar también la selección de la fila.

---

# 17. Botón contextual `+`

Cuando una fila está seleccionada debe aparecer un botón circular `+`.

Debe:

- ser un `<button>`;
- tener forma circular;
- tener borde visible;
- tener contraste suficiente;
- mantener el diseño actual;
- aparecer cerca del inicio de la fila;
- no tapar hora, duración, nombre o estado;
- no crear una columna permanente;
- funcionar mediante teclado;
- mostrar foco;
- incluir un `aria-label` descriptivo.

Ejemplo:

```text
Agregar una actividad antes de Gym - Pecho
```

Al activarse:

- abre el diálogo;
- utiliza modo `insert_before`;
- conserva el identificador de referencia;
- informa al usuario la referencia;
- puede sugerir la hora inicial de la fila.

---

# 18. Inserción antes de una referencia

Cuando se guarda desde el modo contextual:

- se crea la actividad;
- se localiza la referencia;
- se conserva la intención de inserción;
- se respeta la prioridad cronológica;
- se renumeran posiciones;
- se vuelve a renderizar;
- no se modifican actividades existentes.

## Misma hora

Referencia:

```text
07:50 — Cepillado de dientes
```

Nueva:

```text
07:50 — Tomar agua
```

Resultado:

```text
07:50 — Tomar agua
07:50 — Cepillado de dientes
```

## Hora anterior

Referencia:

```text
07:50 — Cepillado de dientes
```

Nueva:

```text
07:30 — Preparar mochila
```

Resultado:

```text
07:30 — Preparar mochila
07:50 — Cepillado de dientes
```

## Hora posterior

Referencia:

```text
07:50 — Cepillado de dientes
```

Nueva:

```text
08:10 — Tomar vitaminas
```

Resultado:

```text
07:50 — Cepillado de dientes
08:10 — Tomar vitaminas
```

La referencia no puede romper el orden cronológico.

---

# 19. Referencia inexistente

Si una inserción contextual recibe un identificador que ya no existe:

- la aplicación no debe romperse;
- no debe producir un error no controlado;
- puede degradarse a creación normal;
- debe crear una actividad válida;
- debe ordenar y renumerar.

El comportamiento elegido debe explicarse en el resumen final.

---

# 20. Posiciones

Después de cualquier creación:

- las posiciones comienzan en `1`;
- son números enteros;
- son consecutivas;
- no existen duplicados;
- no quedan posiciones decimales;
- reflejan el orden visual final.

Ejemplo:

```text
1, 2, 3, 4, 5...
```

No deben quedar resultados como:

```text
1, 1.5, 2, 4
```

---

# 21. Duración

La duración estimada:

- se calcula desde la hora inicial y final;
- no se guarda como propiedad;
- conserva el formato actual.

Ejemplos:

```text
05:30 → 07:15 = 1h 45min
07:50 → 07:55 = 5min
08:45 → 09:45 = 1h
```

Las actividades nuevas deben mostrar correctamente su duración.

---

# 22. Estados después del renderizado

Después de agregar una actividad:

- los botones anteriores siguen funcionando;
- los botones nuevos funcionan;
- el ciclo conserva los cinco estados;
- cada actividad y fecha mantiene independencia;
- el store controla el cambio;
- volver a `pending` puede eliminar la clave del objeto;
- `aria-label` y `title` se actualizan;
- símbolos y colores se conservan.

Ciclo obligatorio:

```text
pending
→ in_progress
→ completed
→ not_completed
→ cancelled
→ pending
```

---

# 23. Cancelación del formulario

Al pulsar Cancelar:

- no se agrega actividad;
- no cambia el store;
- no cambia la matriz;
- se cierra el diálogo;
- se limpian campos;
- se limpian errores;
- se limpia el modo contextual;
- se limpia la referencia;
- se devuelve el foco al control que abrió el diálogo.

El mismo resultado debe producirse al cerrar mediante Escape.

No se requiere todavía confirmación por cambios sin guardar.

---

# 24. Conservación de la fecha seleccionada

Después de:

- agregar una actividad;
- insertar una actividad;
- cambiar un estado;
- volver a renderizar;

la fecha seleccionada debe permanecer igual.

La aplicación no debe regresar automáticamente al día actual después de
cada modificación.

---

# 25. Vista de escritorio

En un ancho amplio debe:

- mostrarse el mes completo;
- mostrarse todos los días;
- conservarse el encabezado;
- conservarse la información temporal;
- mostrarse el botón general;
- permitir seleccionar filas;
- mostrar el botón contextual;
- permitir abrir el diálogo;
- evitar deformación de columnas;
- evitar superposición;
- evitar scroll horizontal global.

---

# 26. Vista compacta

En una pantalla compacta debe:

- mostrarse solamente la fecha seleccionada;
- conservar la navegación;
- conservar posición;
- conservar hora;
- conservar duración;
- conservar nombre;
- conservar estado;
- mostrar el botón general;
- permitir seleccionar una fila;
- mostrar el botón contextual sin tapar contenido;
- abrir un diálogo que quepa en el viewport;
- evitar scroll horizontal global.

El diálogo puede utilizar desplazamiento vertical interno cuando resulte
necesario.

---

# 27. Teclado y foco

Debe comprobarse que:

- `Tab` alcanza el botón general;
- `Enter` o barra espaciadora abre el diálogo;
- `Tab` recorre los campos;
- Guardar funciona con teclado;
- Cancelar funciona con teclado;
- Escape cierra el diálogo;
- el foco vuelve al control de origen;
- los botones multestado siguen operando con teclado;
- el botón contextual es alcanzable;
- el foco visible se conserva.

---

# 28. Consola y errores

La entrega debe abrir sin:

- errores JavaScript;
- errores de importación;
- rutas de módulos rotas;
- excepciones no controladas;
- referencias a archivos eliminados;
- solicitudes a recursos inexistentes.

Los módulos deben cargar correctamente mediante Live Server.

---

# 29. Calidad de código

El código debe:

- utilizar nombres descriptivos;
- separar responsabilidades;
- evitar duplicación;
- evitar variables globales innecesarias;
- mantener funciones pequeñas;
- comentar por bloques funcionales;
- evitar comentarios obvios;
- evitar clases innecesarias;
- evitar arquitectura preparada para funciones futuras no autorizadas;
- conservar un flujo comprensible.

`app.js` debe funcionar como coordinador y no volver a convertirse en un
archivo monolítico.

---

# 30. Funciones que no deben aparecer

La entrega falla por ampliación de alcance si incorpora:

- edición de actividades;
- eliminación;
- persistencia;
- `localStorage`;
- comentarios;
- subactividades;
- tiempos reales;
- seguimiento temporal expandido;
- recorrimiento de horarios;
- recurrencias;
- categorías;
- tipos de actividad;
- estadísticas;
- porcentajes;
- rachas;
- autenticación;
- Flask;
- PostgreSQL;
- API;
- integración con el índice principal;
- despliegue.

---

# 31. Pruebas mínimas obligatorias

Codex debe probar y reportar:

## Regresión

- carga inicial;
- siete actividades;
- mes actual;
- días del mes;
- orden;
- duración;
- navegación compacta;
- cinco estados.

## Creación válida

- nombre normal;
- horas válidas;
- renderizado inmediato;
- duración correcta;
- botón de estado funcional.

## Validaciones

- nombre vacío;
- espacios únicamente;
- inicio vacío;
- final vacío;
- horas iguales;
- final anterior.

## Inserción contextual

- misma hora;
- hora anterior;
- hora posterior;
- referencia inexistente;
- renumeración.

## Cancelación

- botón Cancelar;
- Escape;
- ausencia de cambios.

## Responsive

- escritorio amplio;
- vista compacta;
- diálogo;
- ausencia de scroll horizontal.

## Teclado

- apertura;
- campos;
- guardado;
- cancelación;
- estados;
- botón contextual;
- retorno del foco.

---

# 32. Informe final

Al concluir, Codex debe informar:

1. Archivos creados.
2. Archivos movidos.
3. Archivos eliminados.
4. Archivos modificados.
5. Estructura final.
6. Responsabilidad de cada módulo.
7. Pruebas de regresión.
8. Pruebas de creación.
9. Pruebas de inserción.
10. Pruebas de validación.
11. Pruebas responsive.
12. Pruebas de teclado.
13. Criterios que no pudo comprobar.
14. Limitaciones conocidas.
15. Pasos exactos para abrir y probar.

No debe declarar la entrega como terminada si algún criterio principal no
fue implementado o verificado.

---

# Definición final de terminado

El Frontend MVP 02 se considera terminado cuando se demuestra este flujo:

```text
Usuario abre el gestor
        ↓
Conserva todas las funciones del MVP 01
        ↓
Abre el formulario
        ↓
Ingresa y valida una actividad
        ↓
El store la agrega
        ↓
La matriz se actualiza
        ↓
La actividad se ordena y renumera
        ↓
El usuario cambia su estado
```

Y también:

```text
Usuario selecciona una fila
        ↓
Aparece el botón contextual
        ↓
Abre el formulario en modo insert-before
        ↓
Crea una actividad
        ↓
Se respeta la hora y la referencia
        ↓
La matriz se actualiza correctamente
```
