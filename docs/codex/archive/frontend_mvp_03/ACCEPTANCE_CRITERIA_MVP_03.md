# Criterios de aceptación — Frontend MVP 03

## Nombre de la entrega

**Integridad temporal, registros tipados y acciones contextuales**

---

# Propósito

Este documento define las condiciones objetivas que deben cumplirse para considerar terminada la tercera entrega frontend del submódulo:

```text
Gestor de hábitos
└── Plan del día
```

El MVP 03 amplía el Frontend MVP 02 mediante:

1. Integridad temporal.
2. Clasificación de registros.
3. Edición.
4. Acciones contextuales mejoradas.
5. Navegación hacia Vatos con Sesos.
6. Preservación completa de las funciones existentes.

La entrega no se considera terminada únicamente porque:

* el código compile;
* aparezcan los controles;
* exista el formulario;
* la interfaz se vea correctamente.

Debe demostrarse funcionalmente cada criterio principal descrito en este documento.

---

# 1. Área autorizada de trabajo

Todo cambio de código debe permanecer dentro de:

```text
modules/gestor_de_habitos/
```

Codex puede:

* crear archivos;
* modificar archivos;
* mover archivos;
* eliminar archivos obsoletos;

únicamente dentro de ese módulo.

No debe modificar:

```text
/index.html
/css/
/js/
/docs/
/modules/dev_notes/
/README.md
/.gitignore
/AGENTS.md
```

ni ningún otro archivo externo.

El enlace hacia Vatos con Sesos debe implementarse exclusivamente desde el módulo mediante una ruta relativa.

---

# 2. Git

Codex no debe ejecutar:

```text
git commit
git push
git merge
git switch
git checkout
git reset
git restore
git clean
```

No debe:

* cambiar de rama;
* modificar historial;
* eliminar commits;
* crear tags;
* publicar cambios.

Puede utilizar comandos no destructivos como:

```text
git status
git diff
git diff --check
```

cuando sean necesarios para inspección.

---

# 3. Tecnologías

La entrega debe continuar utilizando exclusivamente:

* HTML;
* CSS;
* JavaScript nativo;
* módulos ES;
* APIs nativas del navegador;
* datos almacenados en memoria.

No debe utilizar:

* Flask;
* Python;
* PostgreSQL;
* Supabase;
* backend;
* APIs remotas;
* `localStorage`;
* `sessionStorage`;
* IndexedDB;
* archivos JSON externos;
* npm;
* React;
* Vue;
* Angular;
* frameworks CSS;
* librerías de iconos;
* dependencias externas;
* servicios externos.

---

# 4. Regresión completa del MVP 02

Antes de considerar implementadas las nuevas funciones, debe comprobarse que el comportamiento aprobado del MVP 02 continúa funcionando.

Debe conservarse:

* tema oscuro;
* paleta actual;
* acentos dorados;
* encabezado principal;
* título `Hábitos`;
* nombre del mes;
* matriz mensual;
* siete registros iniciales;
* orden temporal;
* cálculo de duración;
* todos los días del mes en escritorio;
* una sola fecha en vista compacta;
* navegación anterior y siguiente;
* límites del mes;
* día actual resaltado;
* fecha seleccionada;
* cinco estados;
* ciclo multestado;
* leyenda;
* creación normal;
* inserción contextual;
* selección de filas;
* formulario mediante `<dialog>`;
* persistencia solamente en memoria;
* navegación mediante teclado;
* foco visible;
* ausencia de scroll horizontal global.

La entrega falla si una función anterior deja de funcionar a causa del MVP 03.

---

# 5. Estructura de datos

Cada registro debe respetar el contrato definido en:

```text
/docs/codex/MOCK_DATA_CONTRACT_MVP_03.md
```

Debe contener únicamente:

```text
id
name
recordKind
recordSubtype
position
plannedStartTime
plannedEndTime
statesByDate
```

No deben añadirse propiedades futuras sin autorización.

---

# 6. `recordKind`

Los únicos valores permitidos son:

```text
activity
habit
```

No deben existir otros valores.

---

# 7. `recordSubtype`

Los únicos valores permitidos son:

```text
anchor
periodic
unexpected
scheduled
```

Las combinaciones válidas son:

```text
activity + anchor
activity + periodic
activity + unexpected
habit + scheduled
```

---

# 8. Combinaciones inválidas

El store debe rechazar combinaciones como:

```text
activity + scheduled
habit + anchor
habit + periodic
habit + unexpected
```

No debe guardarse un registro semánticamente inválido aunque el formulario tenga un error.

---

# 9. Datos iniciales

Los siete registros originales deben continuar existiendo.

Deben recibir una clasificación válida.

Clasificación esperada:

```text
Gym - Pecho
→ activity / periodic

Cepillado de dientes
→ habit / scheduled

Meditar
→ habit / scheduled

Hybridge - Programación
→ activity / anchor

Comida
→ habit / scheduled

CCNA / Estudio
→ activity / periodic

Preparación del día siguiente
→ habit / scheduled
```

Las clasificaciones iniciales pueden ajustarse únicamente si existe una razón documentada y no altera el alcance.

---

# 10. Formulario ampliado

El `<dialog>` existente debe permitir registrar:

* nombre;
* tipo principal;
* subtipo;
* hora inicial;
* hora final.

Debe conservar:

* botón Guardar;
* botón Cancelar;
* región accesible para errores.

---

# 11. Selección de tipo

Debe ser posible elegir entre:

```text
Actividad
Hábito
```

El control debe:

* ser nativo o accesible;
* funcionar mediante teclado;
* mostrar foco;
* tener etiqueta asociada.

---

# 12. Subtipo de actividad

Cuando el tipo principal sea:

```text
Actividad
```

debe poder elegirse:

```text
Ancla
Periódica
Imprevista
```

Debe existir siempre una opción válida seleccionada antes de guardar.

Puede utilizarse:

```text
Periódica
```

como valor inicial.

---

# 13. Subtipo de hábito

Cuando el tipo principal sea:

```text
Hábito
```

el subtipo debe convertirse automáticamente en:

```text
scheduled
```

La interfaz debe representar esto como:

```text
Hábito programado
```

No deben aparecer opciones de hábitos tipo logro.

---

# 14. Cambio entre tipos

Si el usuario cambia:

```text
Actividad → Hábito
```

el subtipo anterior debe dejar de aplicarse y convertirse en:

```text
scheduled
```

Si posteriormente cambia:

```text
Hábito → Actividad
```

debe volver a existir un subtipo de actividad válido.

La interfaz no debe dejar combinaciones incoherentes ocultas.

---

# 15. Nombre

Continúan vigentes estas reglas:

* obligatorio;
* máximo 80 caracteres;
* eliminar espacios exteriores;
* rechazar únicamente espacios.

Ejemplo:

```text
"   SQL   "
```

debe almacenarse como:

```text
"SQL"
```

---

# 16. Validaciones básicas de tiempo

Debe rechazarse:

* inicio vacío;
* final vacío;
* horas iguales;
* hora final anterior a la inicial;
* cruce de medianoche;
* `24:00`.

Debe permitirse:

```text
08:00 → 08:01
```

si no existe conflicto con otro registro.

---

# 17. Regla general de superposición

Dos intervalos entran en conflicto cuando:

```text
newStart < existingEnd
AND
newEnd > existingStart
```

La validación debe realizarse contra todos los registros existentes.

---

# 18. Intervalos contiguos

Debe permitirse:

```text
Registro A
19:15 → 20:15

Registro B
20:15 → 20:40
```

No existe superposición.

---

# 19. Superposición parcial al inicio

Debe rechazarse:

```text
Existente:
19:15 → 20:15

Nuevo:
20:00 → 20:40
```

---

# 20. Superposición parcial al final

Debe rechazarse:

```text
Existente:
19:15 → 20:15

Nuevo:
19:00 → 19:30
```

---

# 21. Intervalo contenido

Debe rechazarse:

```text
Existente:
19:15 → 20:15

Nuevo:
19:30 → 20:00
```

---

# 22. Intervalo contenedor

Debe rechazarse:

```text
Existente:
19:15 → 20:15

Nuevo:
19:00 → 20:30
```

---

# 23. Superposición exacta

Debe rechazarse:

```text
Existente:
19:15 → 20:15

Nuevo:
19:15 → 20:15
```

---

# 24. Comparación global

La validación no debe limitarse a:

* registro anterior;
* registro posterior;
* fila seleccionada;
* referencia contextual.

Debe comprobar todos los registros existentes.

---

# 25. Mensaje de conflicto

Cuando exista una superposición:

* no se guarda;
* el diálogo permanece abierto;
* el store no cambia;
* se muestra un mensaje accesible.

El mensaje debe identificar, como mínimo:

* nombre del registro conflictivo;
* hora inicial;
* hora final.

Ejemplo:

```text
El horario se cruza con “CCNA / Estudio” (19:15–20:15).
```

---

# 26. Validación en formulario y store

La interfaz debe validar antes de solicitar el guardado.

El store debe volver a validar defensivamente.

Un llamado directo al store con datos inválidos no debe permitir insertar o actualizar un registro incorrecto.

---

# 27. Creación normal válida

Debe poder crearse un registro válido mediante el botón general.

Ejemplo:

```text
Nombre: SQL
Tipo: Actividad
Subtipo: Periódica
Inicio: 20:20
Final: 20:40
```

si ese intervalo está libre.

Después de guardar:

* aparece sin recargar;
* recibe un `id`;
* recibe posición;
* posee `statesByDate: {}`;
* se ordena;
* se renumeran posiciones;
* inicia visualmente en `pending`.

---

# 28. Creación normal con conflicto

Si el usuario intenta crear dentro del intervalo de otro registro:

* debe rechazarse;
* no debe agregarse parcialmente;
* las posiciones existentes no deben cambiar;
* los estados existentes no deben cambiar.

---

# 29. Inserción contextual válida

El botón contextual `+` debe continuar abriendo el formulario en modo de inserción.

Debe identificarse la referencia.

Si existe espacio disponible antes de ella, debe poder crearse el registro.

Ejemplo:

```text
Registro anterior:
07:50 → 07:55

Referencia:
08:00 → 08:15

Nuevo:
07:55 → 08:00
```

Debe permitirse.

---

# 30. Inserción contextual con conflicto

Ejemplo:

```text
Referencia:
08:00 → 08:15

Nuevo:
08:00 → 08:05
```

Debe rechazarse por superposición.

La intención contextual no puede ignorar la integridad temporal.

---

# 31. Regla anterior del MVP 02 reemplazada

Ya no debe permitirse insertar dos registros con la misma hora inicial si sus intervalos se superponen.

La posición secundaria no puede justificar una colisión temporal.

---

# 32. Selección de filas

Debe conservarse:

* una única fila seleccionada;
* resaltado visual;
* selección mediante clic en zona no interactiva;
* comportamiento con teclado cuando ya exista;
* cambio de referencia al seleccionar otra fila.

---

# 33. Acciones contextuales

Una fila seleccionada debe mostrar:

```text
+
✎
🗑
```

Una fila no seleccionada no debe mostrar esas acciones de manera permanente.

---

# 34. Posición del botón `+`

Debe seguir la referencia:

```text
/docs/codex/assets/acciones-contextuales-fila.png
```

El centro del botón debe quedar aproximadamente sobre la esquina superior izquierda de la celda del nombre.

No debe quedar:

* al inicio completo del renglón;
* sobre posición;
* sobre hora;
* sobre duración.

---

# 35. Tamaño del botón `+`

Debe reducirse respecto al MVP 02.

Objetivo visual aproximado:

```text
22px – 28px
```

Puede existir una superficie interactiva ligeramente mayor si se requiere para accesibilidad, siempre que visualmente no domine la fila.

---

# 36. Superposición visual del `+`

El botón puede superponerse parcialmente al borde de la celda.

No debe:

* cortar el nombre;
* ocultar hora;
* ocultar duración;
* deformar la altura de todas las filas.

El nombre puede desplazarse ligeramente hacia la derecha cuando la fila esté seleccionada.

---

# 37. Botón editar

Debe existir un control visible equivalente a:

```text
✎
```

cuando la fila esté seleccionada.

Debe:

* estar dentro de la celda del nombre;
* ubicarse hacia la derecha;
* ser un `<button>`;
* funcionar con clic;
* funcionar con teclado;
* mostrar foco;
* tener `aria-label`.

Ejemplo:

```text
Editar SQL
```

---

# 38. Botón eliminar

Debe existir visualmente junto a editar.

Debe:

* mostrarse únicamente en la fila seleccionada;
* representar una papelera;
* tener nombre accesible.

En esta entrega no debe eliminar.

---

# 39. Estado disabled de eliminar

La implementación preferida debe utilizar un botón deshabilitado.

Debe comunicar algo equivalente a:

```text
Eliminar SQL — disponible próximamente
```

No debe:

* modificar datos;
* abrir confirmación;
* cambiar estado;
* eliminar fila.

---

# 40. Propagación de eventos

Pulsar:

```text
+
✎
🗑
```

no debe:

* cambiar el estado multestado;
* seleccionar otra fila;
* deseleccionar accidentalmente;
* ejecutar simultáneamente otra acción.

Pulsar un botón de estado tampoco debe abrir edición ni inserción.

---

# 41. Edición

El botón `✎` debe abrir el mismo `<dialog>` existente en modo edición.

No debe existir un segundo formulario independiente salvo justificación técnica extraordinaria.

---

# 42. Datos precargados al editar

Debe cargarse:

* nombre actual;
* tipo actual;
* subtipo actual;
* hora inicial;
* hora final.

El título debe indicar que se está editando.

---

# 43. Identidad después de editar

El registro debe conservar exactamente el mismo:

```text
id
```

No generar uno nuevo.

---

# 44. Estados después de editar

Debe conservar íntegramente:

```text
statesByDate
```

Editar no debe reiniciar los estados.

---

# 45. Edición del nombre

Debe poder cambiarse el nombre respetando:

* trim;
* longitud;
* obligatoriedad.

La modificación debe aparecer sin recargar.

---

# 46. Edición de clasificación

Debe poder cambiarse:

```text
activity / periodic
```

por ejemplo a:

```text
activity / anchor
```

o:

```text
habit / scheduled
```

siempre que la combinación final sea válida.

---

# 47. Edición de horario válida

Si se cambia a un intervalo libre:

* se guarda;
* recalcula duración;
* reordena;
* renumera posiciones.

---

# 48. Edición de horario inválida

Si el nuevo horario se cruza con otro registro:

* se rechaza;
* el diálogo permanece abierto;
* no se altera el registro original;
* no se pierden estados.

---

# 49. El propio registro no cuenta como conflicto

Al editar, debe ignorarse el registro actual durante la detección de superposiciones.

Mantener exactamente el mismo horario debe poder guardarse si los demás campos cambian.

---

# 50. Duración después de editar

La duración continúa siendo calculada.

Cambiar:

```text
20:20 → 20:40
```

a:

```text
20:20 → 21:00
```

debe actualizar la duración automáticamente.

No agregar una propiedad persistente de duración.

---

# 51. Orden después de editar

Si cambia la hora inicial, el registro debe moverse a su nueva posición cronológica.

Después deben existir posiciones:

```text
1, 2, 3, 4...
```

sin duplicados.

---

# 52. Selección después de editar

Cuando resulte razonable, el registro editado debe permanecer seleccionado incluso si cambia de posición.

Si técnicamente se limpia la selección después de editar, Codex debe explicarlo y el flujo no debe quedar inconsistente.

La preferencia es conservar la selección.

---

# 53. Botón general

Debe continuar existiendo.

Puede mantener:

```text
+ Agregar actividad
```

o cambiar a:

```text
+ Agregar registro
```

si Codex considera que representa mejor la nueva clasificación.

Si cambia el texto:

* debe conservar diseño;
* debe explicarlo en el informe final;
* no debe alterar otros componentes innecesariamente.

---

# 54. Navegación a Vatos con Sesos

Debe añadirse un enlace real:

```html
<a>
```

desde el encabezado.

Debe apuntar a:

```text
../../index.html
```

desde el módulo actual.

---

# 55. Ruta correcta

El enlace debe probarse mediante servidor local.

Debe regresar correctamente a la página principal.

No debe depender de una ruta absoluta específica del equipo.

No utilizar:

```text
/home/ssail/...
```

como `href`.

---

# 56. Apariencia en escritorio

Debe mostrar conceptualmente:

```text
⌂ Vatos con Sesos
```

en una zona central del encabezado.

Debe integrarse al diseño existente.

---

# 57. Apariencia compacta

En vista reducida debe representar:

```text
⌂ VCS
```

para ahorrar espacio.

No debe causar superposición con:

* `Hábitos`;
* mes;
* otros elementos del encabezado.

---

# 58. Accesibilidad del enlace

Debe contar con:

* foco visible;
* uso mediante teclado;
* texto accesible.

Ejemplo:

```text
Volver a la página principal de Vatos con Sesos
```

El icono de casa no puede ser la única descripción para tecnologías asistivas.

---

# 59. Estados multestado

Deben conservarse exactamente:

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

---

# 60. Independencia de estados

Cambiar el estado de:

```text
SQL
2026-08-04
```

no debe cambiar:

* otra fecha de SQL;
* otro registro;
* clasificación;
* horario;
* nombre.

---

# 61. Responsive de escritorio

En escritorio amplio debe continuar mostrándose:

* mes completo;
* todos los días;
* registros;
* estados;
* botón general;
* acciones contextuales;
* enlace VCS.

No debe aparecer scroll horizontal global.

---

# 62. Responsive compacto

En vista compacta debe continuar mostrándose:

* fecha seleccionada;
* controles anterior/siguiente;
* posición;
* inicio;
* duración;
* nombre;
* estado;
* selección;
* acciones contextuales;
* botón general;
* enlace `VCS`.

No debe aparecer superposición grave.

---

# 63. Diálogo compacto

El diálogo ampliado debe:

* caber dentro del viewport;
* poder organizar campos verticalmente;
* permitir desplazamiento vertical interno si resulta necesario;
* no generar scroll horizontal global.

---

# 64. Teclado

Debe comprobarse al menos:

* `Tab` navega por controles;
* `Enter` o barra espaciadora activan botones;
* `Escape` cierra el diálogo;
* Guardar funciona con teclado;
* Cancelar funciona;
* editar funciona;
* insertar funciona;
* controles de estado siguen funcionando;
* enlace VCS es alcanzable;
* foco visible.

---

# 65. Retorno de foco

Después de cerrar el diálogo:

## Creación normal

El foco debe regresar al botón general.

## Inserción contextual

El foco debe regresar al botón contextual o a un elemento razonable asociado a la fila.

## Edición

El foco debe regresar al botón editar o a la fila editada.

La implementación debe evitar perder el foco al `body` sin motivo.

---

# 66. Cancelar

Cancelar:

* no crea;
* no edita;
* no cambia clasificaciones;
* no cambia horarios;
* no cambia estados;
* limpia errores;
* limpia modo del formulario.

---

# 67. Escape

Cerrar mediante Escape debe producir el mismo resultado funcional que Cancelar.

No debe dejar:

* referencias antiguas;
* modo edit activo;
* modo insert activo;
* campos residuales;
* errores anteriores.

---

# 68. Persistencia temporal

Todos los cambios siguen existiendo únicamente en memoria.

Después de recargar:

* desaparecen registros nuevos;
* desaparecen ediciones;
* regresan los datos iniciales;
* regresan estados demostrativos;
* regresan clasificaciones iniciales.

---

# 69. Aviso de temporalidad

Debe conservarse un mensaje equivalente a:

```text
Los cambios son temporales y se perderán al recargar la página.
```

---

# 70. Consola

La página debe cargar sin:

* errores JavaScript;
* errores de módulos;
* imports rotos;
* rutas inexistentes;
* excepciones no controladas.

---

# 71. Calidad modular

`app.js` debe continuar actuando como coordinador.

No debe absorber nuevamente:

* renderizado completo;
* reglas del dominio;
* lógica de store;
* utilidades de fechas;
* validaciones completas.

---

# 72. Store

Debe continuar siendo la única fuente mutable de registros.

Las vistas no deben escribir directamente:

```text
statesByDate
position
recordKind
recordSubtype
plannedStartTime
plannedEndTime
```

sobre la colección interna.

---

# 73. Validación defensiva del store

Debe rechazar al menos:

* nombre inválido;
* clasificación inválida;
* combinación kind/subtype inválida;
* horas inválidas;
* superposición temporal.

---

# 74. Función conceptual de edición

Debe existir una responsabilidad equivalente a:

```text
updateActivity(activityId, activityDraft)
```

o un nombre equivalente.

No debe implementarse la edición manipulando directamente el objeto desde la vista.

---

# 75. Función conceptual de conflicto

Debe existir una responsabilidad equivalente a:

```text
findTimeConflict(...)
```

o:

```text
hasTimeConflict(...)
```

La detección no debe duplicarse de forma inconsistente en varios módulos.

La lógica principal debe centralizarse.

---

# 76. Funciones fuera de alcance

La entrega falla por ampliación indebida si introduce:

* eliminación funcional;
* confirmación de borrado;
* semana ideal;
* recurrencias;
* backend;
* API;
* PostgreSQL;
* Supabase;
* `localStorage`;
* comentarios;
* subactividades;
* horas reales;
* seguimiento temporal expandido;
* reajuste automático;
* hábitos tipo logro;
* cantidades;
* estadísticas;
* rachas;
* porcentajes;
* notificaciones;
* autenticación;
* despliegue.

---

# 77. Pruebas mínimas obligatorias de Codex

Codex debe ejecutar o comprobar como mínimo:

## Regresión

* carga inicial;
* siete registros;
* días del mes;
* navegación compacta;
* creación;
* inserción;
* cinco estados;
* responsive.

## Clasificación

* activity/anchor;
* activity/periodic;
* activity/unexpected;
* habit/scheduled;
* combinación inválida rechazada.

## Integridad temporal

* horario contiguo;
* superposición inicial;
* superposición final;
* contenido;
* contenedor;
* intervalo idéntico.

## Edición

* nombre;
* tipo;
* subtipo;
* horario;
* duración;
* reordenamiento;
* conservación de id;
* conservación de statesByDate;
* conflicto al editar.

## Acciones contextuales

* selección;
* posición visual del `+`;
* editar;
* papelera deshabilitada;
* ausencia de propagación accidental.

## Navegación

* enlace VCS en escritorio;
* enlace VCS en compacto;
* ruta relativa correcta.

## Formulario

* Cancelar;
* Escape;
* errores;
* retorno de foco.

## Responsive

* escritorio amplio;
* vista compacta;
* diálogo;
* ausencia de scroll horizontal global.

---

# 78. Inspección visual

Cuando el entorno lo permita, Codex debe realizar una comprobación visual mediante Chromium local en:

```text
1440 × 900
```

y aproximadamente:

```text
390 × 844
```

o dimensiones equivalentes.

Debe verificar:

* encabezado;
* matriz;
* acciones contextuales;
* diálogo;
* navegación VCS;
* ausencia de desbordamiento.

---

# 79. Verificación de sintaxis

Los módulos JavaScript deben superar una comprobación equivalente a:

```text
node --check
```

cuando resulte aplicable.

Debe comprobarse además que los imports ES carguen correctamente desde servidor local.

---

# 80. Informe final

Al terminar, Codex debe informar:

1. Archivos creados.
2. Archivos modificados.
3. Archivos eliminados.
4. Estructura final.
5. Cambios al contrato de datos.
6. Clasificaciones implementadas.
7. Cómo se valida la superposición.
8. Cómo funciona la edición.
9. Cómo se conserva `id`.
10. Cómo se conserva `statesByDate`.
11. Cómo funciona el botón `+`.
12. Cómo funciona editar.
13. Estado del botón eliminar.
14. Cómo funciona el enlace VCS.
15. Pruebas de regresión.
16. Pruebas de clasificación.
17. Pruebas temporales.
18. Pruebas de edición.
19. Pruebas responsive.
20. Pruebas de teclado.
21. Criterios no comprobados.
22. Limitaciones conocidas.
23. Instrucciones para abrir y probar.

---

# Definición final de terminado

El Frontend MVP 03 se considera terminado cuando puede demostrarse este flujo:

```text
Usuario abre Plan del día
        ↓
Conserva todas las funciones del MVP 02
        ↓
Crea un registro
        ↓
Selecciona Actividad o Hábito
        ↓
Selecciona una clasificación válida
        ↓
Introduce un horario libre
        ↓
El formulario valida
        ↓
El store vuelve a validar
        ↓
El registro aparece ordenado
```

Además:

```text
Usuario intenta crear un horario superpuesto
        ↓
El sistema identifica el conflicto
        ↓
Muestra con qué registro se cruza
        ↓
No modifica los datos
```

Además:

```text
Usuario selecciona una fila
        ↓
Aparecen +, ✎ y 🗑
        ↓
+ permite insertar
✎ permite editar
🗑 comunica que estará disponible después
```

Además:

```text
Usuario edita un registro
        ↓
Conserva su id
        ↓
Conserva statesByDate
        ↓
Valida nuevamente horarios
        ↓
Reordena y recalcula duración
```

Y finalmente:

```text
Usuario activa ⌂ Vatos con Sesos
        ↓
Regresa correctamente al index principal
```

Si estos flujos funcionan sin romper el MVP 02, el Frontend MVP 03 puede considerarse completado.
