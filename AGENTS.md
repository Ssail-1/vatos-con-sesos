# AGENTS.md

## Proyecto

Este repositorio contiene la aplicación **Vatos con Sesos**.

Vatos con Sesos crecerá como un gestor personal compuesto por módulos y submódulos.

Actualmente existen:

```text
Vatos con Sesos
├── Dev Notes
└── Gestor de hábitos
    └── Plan del día
```

La tarea vigente corresponde exclusivamente al desarrollo del siguiente incremento frontend de:

```text
modules/gestor_de_habitos/
```

La entrega actual es:

```text
Frontend MVP 03 — Integridad temporal, registros tipados y acciones contextuales
```

---

# Fuentes de instrucciones vigentes

Antes de modificar código, debes leer completamente los documentos vigentes en este orden:

1. `/AGENTS.md`
2. `/docs/codex/CURRENT_TASK.md`
3. `/docs/codex/FRONTEND_MVP_03.md`
4. `/docs/codex/MOCK_DATA_CONTRACT_MVP_03.md`
5. `/docs/codex/UI_REFERENCE.md`
6. `/docs/codex/ACCEPTANCE_CRITERIA_MVP_03.md`

También debes consultar las referencias visuales relevantes dentro de:

```text
/docs/codex/assets/
```

Especialmente:

```text
/docs/codex/assets/acciones-contextuales-fila.png
```

para la composición visual de las acciones de una fila seleccionada.

---

# Documentos archivados

La carpeta:

```text
/docs/codex/archive/
```

contiene documentación de entregas anteriores.

Puede utilizarse para comprender:

* decisiones pasadas;
* comportamiento que debe conservarse;
* evolución del módulo.

Pero sus documentos:

* no son instrucciones vigentes;
* no deben ampliar el alcance actual;
* pueden contener decisiones reemplazadas.

Cuando exista contradicción, tienen prioridad los documentos normativos del MVP 03.

---

# Documentos de planeación

La carpeta:

```text
/docs/codex/planeacion/
```

contiene:

* razonamiento del proyecto;
* conversaciones de diseño;
* ideas;
* mapas;
* notas del desarrollador;
* decisiones en evaluación;
* funciones futuras.

Estos documentos son exclusivamente contexto.

No constituyen instrucciones de implementación.

Pueden contener:

* contradicciones;
* ideas descartadas;
* funciones todavía no autorizadas.

No debes implementar algo solamente porque aparezca dentro de `planeacion/`.

---

# Área autorizada

Puedes crear, modificar, mover o eliminar código únicamente dentro de:

```text
modules/gestor_de_habitos/
```

No debes modificar:

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

ni ningún otro archivo fuera del módulo autorizado.

Puedes leer esos archivos para comprender el proyecto.

---

# Excepción: navegación a la aplicación principal

El MVP 03 debe crear dentro del propio módulo un enlace hacia:

```text
../../index.html
```

Esto no autoriza modificar el `index.html` raíz.

Si el enlace requiere cambios externos para funcionar, debes:

1. No modificar el archivo externo.
2. Informarlo.
3. Explicar la causa.
4. Esperar autorización.

---

# Estado estable que debe conservarse

El MVP 02 constituye la base funcional.

No se debe eliminar ni deteriorar:

* el tema oscuro;
* la paleta;
* los acentos dorados;
* el encabezado;
* la matriz mensual;
* los siete registros iniciales;
* las duraciones calculadas;
* el mes actual;
* todos los días del mes en escritorio;
* una sola fecha en vista compacta;
* navegación entre días;
* resaltado del día actual;
* resaltado de la fecha seleccionada;
* selección de filas;
* botón general para crear;
* formulario mediante `<dialog>`;
* creación en memoria;
* inserción contextual;
* cinco estados;
* ciclo multestado;
* leyenda;
* foco visible;
* navegación mediante teclado;
* ausencia de scroll horizontal global;
* separación modular del JavaScript.

No se autoriza un rediseño general.

---

# Tecnologías permitidas

Utiliza únicamente:

* HTML;
* CSS;
* JavaScript nativo;
* módulos ES;
* APIs nativas del navegador;
* datos simulados en memoria.

No utilices:

* Flask;
* Python;
* PostgreSQL;
* Supabase;
* backend;
* API externa;
* `localStorage`;
* `sessionStorage`;
* IndexedDB;
* JSON externo;
* React;
* Vue;
* Angular;
* frameworks CSS;
* npm;
* librerías externas;
* servicios remotos;
* recursos externos.

---

# Arquitectura actual

La estructura modular existente debe conservarse conceptualmente:

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

Puedes ampliar alguno de estos módulos cuando sea necesario.

No debes fragmentar el código creando archivos nuevos sin una responsabilidad clara.

Si un archivo nuevo resulta necesario, debes justificarlo brevemente.

---

# Responsabilidades

## Data

```text
js/data/
```

Contiene datos iniciales de demostración.

No manipula DOM.

---

## Domain

```text
js/domain/
```

Contiene conceptos y reglas estables del dominio frontend.

El MVP 03 puede ampliar esta área con reglas relacionadas con:

* tipos;
* subtipos;
* estados.

No debe contener el store mutable.

---

## State

```text
js/state/
```

Es propietario de la colección mutable de registros.

Debe controlar:

* creación;
* edición;
* inserción;
* estados;
* orden;
* posiciones;
* validaciones defensivas.

Las vistas no modifican directamente los datos.

---

## Utils

```text
js/utils/
```

Contiene funciones reutilizables para:

* fechas;
* horas;
* duración;
* comparación temporal;
* validaciones temporales genéricas.

No manipula DOM ni almacena actividades.

---

## Views

```text
js/views/
```

Contiene la representación y las interacciones visuales.

Las vistas comunican intenciones.

No son propietarias del estado persistente en memoria.

---

## App

```text
js/app.js
```

Coordina:

```text
store
↕
views
```

Debe continuar siendo un archivo relativamente pequeño y comprensible.

No debe volver a concentrar toda la lógica del módulo.

---

# Registros del Plan del día

Los registros del submódulo pueden ser:

```text
activity
habit
```

---

# Actividades

Los subtipos permitidos son:

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

# Hábitos

En esta entrega solamente existe:

```text
scheduled
```

Representación visible:

```text
Hábito programado
```

No implementar otros tipos de hábitos.

---

# Logros diarios

No implementar hábitos de cumplimiento diario sin horario.

Ejemplos fuera de alcance:

* no fumar;
* no beber;
* no FAP;
* cantidad diaria de agua;
* cantidad de lectura.

Estos pertenecerán a otro submódulo futuro.

---

# Intervalos temporales

Todos los registros mostrados en `Plan del día` tienen:

```text
plannedStartTime
plannedEndTime
```

La hora final debe ser posterior a la inicial.

No se permiten cruces de medianoche en esta entrega.

---

# Superposición

No se permite que dos registros ocupen simultáneamente el mismo intervalo.

Los intervalos contiguos sí se permiten.

Debe aplicarse la regla definida en:

```text
/docs/codex/CURRENT_TASK.md
```

y posteriormente en:

```text
/docs/codex/FRONTEND_MVP_03.md
```

---

# Validación defensiva

La validación temporal no debe depender únicamente del formulario.

El store debe rechazar:

* actividades inválidas;
* ediciones inválidas;
* horarios superpuestos.

Una interfaz defectuosa no debe poder corromper el estado en memoria.

---

# Edición

La entrega debe permitir editar un registro existente.

Debe conservar:

```text
id
statesByDate
```

No debe tratar una edición como creación.

No debe generar un identificador nuevo.

---

# Acciones contextuales

Cuando una fila esté seleccionada deben aparecer:

```text
+
✎
🗑
```

La referencia visual principal es:

```text
/docs/codex/assets/acciones-contextuales-fila.png
```

---

# Botón `+`

Su centro debe ubicarse aproximadamente sobre la esquina superior izquierda de la celda del nombre.

Debe ser más pequeño que el control del MVP 02.

Puede desplazar ligeramente el texto del nombre para evitar superposición.

---

# Editar

Debe aparecer dentro de la celda del nombre, hacia la derecha.

Debe abrir el formulario en modo edición.

---

# Eliminar

Debe aparecer visualmente junto a editar.

En esta entrega:

```text
NO elimina
```

Debe estar claramente deshabilitado o marcado como función futura.

---

# Navegación principal

El encabezado debe incluir un enlace hacia:

```text
../../index.html
```

En escritorio debe mostrar conceptualmente:

```text
⌂ Vatos con Sesos
```

En vista compacta:

```text
⌂ VCS
```

No modifiques el index principal para implementar este enlace.

---

# Persistencia

Continúa siendo exclusivamente en memoria.

No implementar ningún mecanismo de persistencia.

Al recargar se restaura el estado inicial.

---

# Estilo de código

* Utilizar nombres técnicos en inglés.
* Mantener texto visible en español.
* Mantener funciones pequeñas.
* Evitar duplicación.
* Evitar variables globales innecesarias.
* Evitar clases si funciones u objetos son suficientes.
* No introducir abstracciones para funciones futuras.
* Comentar por bloques funcionales.
* No comentar sintaxis obvia.

---

# Accesibilidad

Toda nueva interacción debe:

* utilizar elementos semánticos;
* funcionar mediante teclado;
* tener foco visible;
* contar con nombre accesible;
* no depender únicamente del color;
* respetar el manejo de foco del diálogo;
* mostrar errores de forma accesible.

---

# Responsive

Debe seguir funcionando correctamente en:

* escritorio amplio;
* vista compacta.

No debe introducir:

* scroll horizontal global;
* superposición de texto;
* controles inaccesibles;
* deformación severa de columnas.

---

# Fuera de alcance

No implementar:

* eliminación real;
* hábitos tipo logro;
* recurrencia;
* semana ideal;
* tiempos reales;
* seguimiento temporal expandido;
* comentarios;
* subactividades;
* estadísticas;
* rachas;
* porcentajes;
* reajuste automático;
* notificaciones;
* autenticación;
* backend;
* base de datos;
* integración completa con el shell principal;
* despliegue.

---

# Forma de trabajo

Antes de modificar código debes:

1. Leer todos los documentos normativos.
2. Inspeccionar el estado actual del módulo.
3. Resumir tu comprensión.
4. Enumerar los archivos que modificarás.
5. Explicar cómo implementarás:

   * conflictos temporales;
   * edición;
   * clasificación;
   * acciones contextuales;
   * enlace hacia VCS.
6. Explicar cómo conservarás el MVP 02.

Después espera autorización, salvo que el prompt del usuario indique explícitamente que puedes comenzar inmediatamente.

---

# Git

No debes ejecutar:

* `git commit`;
* `git push`;
* `git merge`;
* `git switch`;
* `git checkout`;
* `git reset`;
* `git restore`;
* `git clean`.

No debes modificar historial ni cambiar de rama.

Puedes utilizar comandos de inspección y pruebas no destructivas.

---

# Seguridad

No crear:

* credenciales;
* secretos;
* `.env`;
* accesos remotos;
* dependencias externas.

No ejecutar comandos destructivos.

---

# Finalización

La entrega solamente se considera terminada cuando cumple:

```text
/docs/codex/ACCEPTANCE_CRITERIA_MVP_03.md
```

Codex debe ejecutar pruebas de regresión del MVP 02 además de las pruebas propias del MVP 03.

No declarar una función terminada si no fue implementada o verificada.
