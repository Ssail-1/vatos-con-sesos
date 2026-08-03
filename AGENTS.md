# AGENTS.md

## Proyecto

Este repositorio contiene la aplicación **Vatos con Sesos**.

El proyecto crecerá como un gestor personal compuesto por módulos independientes.

Los módulos actuales son:

- `modules/dev_notes/`
- `modules/gestor_de_habitos/`

La tarea actual consiste exclusivamente en desarrollar el primer prototipo frontend del módulo:

```text
modules/gestor_de_habitos/
```

---

# Fuentes de instrucciones

Antes de modificar código, debes leer los documentos vigentes en este orden:

1. `/AGENTS.md`
2. `/docs/codex/CURRENT_TASK.md`
3. `/docs/codex/FRONTEND_MVP_01.md`
4. `/docs/codex/UI_REFERENCE.md`
5. `/docs/codex/MOCK_DATA_CONTRACT.md`
6. `/docs/codex/ACCEPTANCE_CRITERIA_MVP_01.md`

## Documentos de planeación

La carpeta:

```text
/docs/codex/planeacion/
```

contiene únicamente contexto histórico, ideas, preguntas y decisiones consideradas durante el diseño.

Los documentos de esa carpeta:

- no son instrucciones vigentes;
- pueden contener contradicciones;
- pueden mencionar funciones futuras;
- pueden contener ideas descartadas;
- no deben ampliar automáticamente el alcance actual.

En caso de contradicción, siempre tienen prioridad los documentos normativos enumerados anteriormente.

---

# Área autorizada

Puedes crear o modificar archivos únicamente dentro de:

```text
modules/gestor_de_habitos/
```

No debes modificar archivos fuera de esa carpeta.

Esto incluye, entre otros:

```text
/index.html
/css/
/js/
/modules/dev_notes/
/docs/
/README.md
/.gitignore
```

Puedes leer esos archivos cuando sea necesario para comprender el estilo o la estructura del proyecto, pero no puedes modificarlos.

## Cambios externos necesarios

Si consideras necesario modificar un archivo fuera del módulo autorizado:

1. no realices el cambio;
2. describe el archivo afectado;
3. explica el cambio propuesto;
4. explica por qué sería necesario;
5. espera autorización explícita.

---

# Tarea actual

La tarea vigente es:

```text
Frontend MVP 01 — Matriz mensual responsive con foco en el día actual
```

Debes implementar exclusivamente lo descrito en:

```text
/docs/codex/CURRENT_TASK.md
```

No agregues funciones futuras aunque aparezcan dentro de los documentos históricos.

---

# Tecnologías permitidas en esta entrega

Utiliza únicamente:

- HTML;
- CSS;
- JavaScript nativo;
- datos simulados en memoria.

No utilices:

- Flask;
- Python;
- PostgreSQL;
- Supabase;
- API;
- `localStorage`;
- React;
- Vue;
- Angular;
- frameworks CSS;
- librerías externas;
- herramientas de compilación;
- dependencias de npm.

---

# Forma de trabajo

Antes de escribir código debes:

1. leer los documentos normativos;
2. inspeccionar `modules/gestor_de_habitos/`;
3. resumir tu comprensión de la entrega;
4. enumerar los archivos que crearás o modificarás;
5. explicar el comportamiento en escritorio;
6. explicar el comportamiento en vista compacta;
7. explicar cómo implementarás el control multestado.

Si el usuario solicita primero un plan, no modifiques archivos hasta recibir autorización.

Durante la implementación:

1. trabaja por bloques pequeños;
2. conserva el alcance de la entrega;
3. evita agregar arquitectura innecesaria;
4. prueba cada interacción;
5. no modifiques la aplicación principal.

Al finalizar debes informar:

- archivos creados;
- archivos modificados;
- comportamiento implementado;
- pasos para abrir y probar;
- limitaciones conocidas;
- funcionalidades deliberadamente aplazadas.

---

# Estilo de código

## Organización

- Separar HTML, CSS y JavaScript.
- Renderizar las actividades desde datos JavaScript.
- No repetir manualmente filas de actividades en HTML.
- Mantener funciones pequeñas y con una sola responsabilidad.
- Evitar código duplicado.
- Utilizar nombres descriptivos.
- Agrupar constantes relacionadas.
- No crear abstracciones innecesarias.

## Nombres

Utilizar nombres técnicos en inglés dentro del código.

Ejemplos:

```js
selectedDate
plannedStartTime
plannedEndTime
activityStates
renderActivities
getNextStatus
```

El texto visible de la interfaz debe estar en español.

## Comentarios

Comentar por bloques funcionales.

Los comentarios deben explicar:

- el propósito de un bloque;
- una regla de negocio;
- una decisión poco evidente;
- una consideración responsive o de accesibilidad.

Ejemplo adecuado:

```js
// Calcula los días visibles del mes seleccionado
```

Evitar comentarios que solamente repitan la sintaxis:

```js
// Se crea una variable
```

---

# Contrato de datos

La estructura de los datos simulados debe respetar:

```text
/docs/codex/MOCK_DATA_CONTRACT.md
```

No inventes campos adicionales sin necesidad.

La interfaz debe quedar preparada conceptualmente para sustituir los datos simulados por datos obtenidos desde una API en una entrega futura.

---

# Estados de actividad

Los únicos estados permitidos son:

```text
pending
in_progress
completed
not_completed
cancelled
```

El ciclo obligatorio es:

```text
pending
→ in_progress
→ completed
→ not_completed
→ cancelled
→ pending
```

El control debe ser un botón multestado, no un checkbox HTML nativo.

Cada representación debe incluir:

- símbolo;
- color;
- `data-status`;
- `aria-label`;
- ayuda mediante `title` o equivalente;
- foco visible.

La interfaz no debe comunicar el estado únicamente mediante color.

---

# Responsive

## Escritorio amplio

Debe mostrar:

- información resumida de las actividades;
- todos los días del mes;
- una columna de estado por cada fecha;
- el día actual resaltado.

## Vista compacta

Debe mostrar:

- nombre de la actividad;
- hora planeada de inicio;
- duración estimada;
- únicamente la columna de la fecha seleccionada;
- control multestado correspondiente a esa fecha.

No debe existir scroll horizontal global ni superposición de texto.

La matriz completa puede ocultar columnas en la vista compacta, pero los datos deben conservarse en memoria.

---

# Accesibilidad mínima

- Los elementos interactivos deben ser botones reales.
- Deben funcionar mediante teclado.
- El foco debe ser visible.
- Cada control debe tener un nombre accesible.
- Los símbolos decorativos deben ocultarse de lectores de pantalla cuando sea necesario.
- El significado no debe depender solamente del color.
- Debe utilizarse HTML semántico cuando sea razonable.

---

# Restricciones de alcance

No implementar en esta entrega:

- creación de actividades;
- formularios;
- botón contextual `+`;
- modales;
- overlays;
- comentarios;
- subactividades;
- recurrencias;
- seguimiento temporal expandido;
- horas reales;
- persistencia;
- backend;
- base de datos;
- estadísticas;
- porcentajes;
- rachas;
- días activos;
- reajuste automático de horarios;
- autenticación;
- despliegue.

Si una función no está incluida explícitamente en la tarea actual, no debe implementarse.

---

# Git

No debes:

- ejecutar `git push`;
- ejecutar `git merge`;
- modificar la rama `main`;
- cambiar de rama;
- borrar historial;
- utilizar comandos destructivos;
- eliminar archivos ajenos al módulo;
- hacer commits sin autorización explícita.

Puedes consultar el estado del repositorio si es necesario, pero no debes publicar ni integrar cambios.

---

# Seguridad

- No crear credenciales.
- No introducir claves o secretos.
- No crear archivos `.env` reales.
- No añadir datos personales reales.
- No depender de servicios externos.
- No ejecutar comandos destructivos.

---

# Criterio de finalización

La tarea solamente se considera terminada cuando cumple:

```text
/docs/codex/ACCEPTANCE_CRITERIA_MVP_01.md
```

Crear únicamente la estructura de archivos no significa haber terminado.

Debe existir un flujo visual e interactivo comprobable y sin errores de consola.