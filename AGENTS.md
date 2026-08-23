
# AGENTS.md

# Vatos con Sesos — Reglas para agentes de desarrollo

Este archivo contiene reglas generales y permanentes para cualquier agente de
IA que trabaje dentro de este repositorio.

Las instrucciones específicas de una entrega NO deben añadirse aquí.

El alcance actual siempre debe obtenerse desde:

`/docs/codex/CURRENT_TASK.md`

---

# 1. Antes de modificar código

Antes de realizar cualquier cambio:

1. Leer completamente este archivo.
2. Leer `/docs/codex/CURRENT_TASK.md`.
3. Leer todos los documentos normativos que `CURRENT_TASK.md` indique.
4. Inspeccionar el código existente relacionado con la tarea.
5. Comprender la implementación actual antes de reemplazarla.
6. Revisar `git status`.
7. No comenzar a escribir código hasta entender:
   - qué debe cambiar;
   - qué debe conservarse;
   - qué está fuera de alcance.

No asumir requisitos que no estén definidos.

---

# 2. Fuente de verdad para cada entrega

`CURRENT_TASK.md` define:

- qué se está construyendo;
- qué parte del repositorio puede modificarse;
- qué documentación debe leerse;
- qué funciones están autorizadas;
- qué funciones están aplazadas.

Las instrucciones específicas del MVP actual prevalecen sobre decisiones
históricas.

---

# 3. Jerarquía documental

Interpretar la documentación utilizando aproximadamente este orden:

1. `AGENTS.md`
   - reglas generales del repositorio;

2. `docs/codex/CURRENT_TASK.md`
   - alcance de la entrega actual;

3. documentos normativos indicados por CURRENT_TASK;
   por ejemplo:
   - modelos de dominio;
   - contratos de datos;
   - frontend;
   - criterios de aceptación;
   - referencias de UI;

4. código actualmente aprobado;

5. documentación histórica o de planificación.

Cuando exista una contradicción real entre documentos normativos:

- no decidir silenciosamente;
- no inventar una regla de negocio;
- detener únicamente la parte afectada;
- informar claramente el conflicto.

---

# 4. Documentación normativa y documentación de contexto

No toda la documentación dentro de `/docs/` representa instrucciones.

Los documentos que `CURRENT_TASK.md` enumera explícitamente como normativos
sí deben cumplirse.

Carpetas como:

`/docs/codex/planeacion/`

`/docs/codex/proximas-features/`

`/docs/codex/archive/`

contienen principalmente:

- historia;
- conversación de diseño;
- ideas;
- decisiones anteriores;
- funciones futuras;
- referencias.

Pueden consultarse para comprender el proyecto.

NO deben utilizarse por sí solas para ampliar el alcance actual.

---

# 5. No implementar funciones futuras por iniciativa propia

Si una idea aparece como:

- futura;
- pendiente;
- roadmap;
- aplazada;
- fuera de alcance;

NO implementarla durante la entrega actual.

Es válido preparar una arquitectura que no bloquee su incorporación futura.

No es válido construirla anticipadamente sin autorización.

---

# 6. Área de trabajo

Respetar estrictamente el área autorizada definida en `CURRENT_TASK.md`.

No modificar archivos externos únicamente porque:

- sería más cómodo;
- permitiría una refactorización mayor;
- parecería una arquitectura más limpia;
- existe código relacionado fuera del alcance.

Si una solución requiere modificar un archivo fuera del área autorizada:

1. no modificarlo;
2. explicar por qué sería necesario;
3. continuar con todo lo que sí pueda realizarse dentro del alcance.

---

# 7. No reescribir código funcional sin necesidad

Antes de reemplazar una implementación:

1. entender qué responsabilidad cumple;
2. comprobar si puede reutilizarse;
3. identificar qué problema concreto resuelve el cambio.

Preferir:

`evolucionar`

sobre:

`reescribir desde cero`

cuando el código existente sea correcto y reutilizable.

---

# 8. Preservar comportamiento aprobado

Cada nuevo MVP debe considerarse una evolución del anterior.

No romper funciones existentes que no formen parte explícita del cambio.

Después de modificar arquitectura o dominio, realizar pruebas de regresión
sobre las capacidades previamente aprobadas.

---

# 9. Modularización

El proyecto busca ser comprensible para una persona que continúa aprendiendo
desarrollo de software.

Favorecer módulos con responsabilidades claras.

Evitar archivos que concentren:

- estado;
- dominio;
- renderizado;
- validaciones;
- eventos;
- acceso a datos;

simultáneamente.

---

# 10. No modularizar por modularizar

Crear un archivo nuevo solamente cuando exista una responsabilidad real que
justifique su existencia.

Evitar:

- archivos de unas pocas líneas sin valor arquitectónico;
- wrappers innecesarios;
- abstracciones prematuras;
- fragmentación excesiva.

La modularización debe aumentar:

- comprensión;
- mantenibilidad;
- capacidad de prueba.

No aumentar complejidad accidental.

---

# 11. `app.js`

Cuando exista un archivo coordinador como:

`app.js`

debe actuar principalmente como punto de composición y coordinación.

No convertirlo en un archivo monolítico que implemente directamente:

- almacenamiento;
- reglas completas de dominio;
- materialización;
- renderizado completo;
- validaciones extensas;
- utilidades de fecha.

---

# 12. Separación conceptual

Cuando corresponda, favorecer responsabilidades equivalentes a:

`data`
→ datos iniciales o fixtures;

`domain`
→ reglas del negocio;

`state`
→ fuente mutable de estado;

`scheduling`
→ planificación temporal;

`utils`
→ utilidades puras reutilizables;

`views`
→ representación e interacción;

`app`
→ coordinación.

Esta estructura es una guía.

No crear carpetas vacías para cumplirla literalmente.

---

# 13. Fuente única de verdad

Evitar mantener dos representaciones mutables de la misma información.

Si un MVP reemplaza una estructura anterior:

- migrar su responsabilidad;
- actualizar consumidores;
- eliminar la antigua fuente de verdad cuando sea seguro.

No mantener compatibilidad temporal indefinida mediante datos duplicados.

---

# 14. Datos derivados

No almacenar información que pueda derivarse de manera confiable salvo que
exista una razón explícita.

Ejemplos generales:

- duración derivada de inicio y final;
- posición derivada del orden;
- mes derivado de fecha;
- año derivado de fecha;
- estado visual derivado del dominio.

Preferir una fuente de verdad y calcular el resto.

---

# 15. Reglas de negocio

Las reglas del negocio deben vivir fuera de la interfaz cuando sea razonable.

La vista debe preguntar al dominio o al store:

`¿puedo hacer esto?`

en lugar de implementar por separado una versión propia de la regla.

Evitar repetir la misma condición en múltiples archivos.

---

# 16. Validaciones

Validar en la capa adecuada.

La interfaz puede proporcionar feedback temprano.

La capa propietaria de los datos debe mantener defensivamente la integridad.

Nunca depender únicamente del HTML o de la vista para garantizar que los
datos sean válidos.

---

# 17. Operaciones coherentes

Una operación compuesta no debe dejar datos parcialmente modificados cuando
falla.

Cuando sea posible:

1. construir el cambio;
2. validar completamente;
3. aplicar el cambio.

Evitar:

`guardar primero`
→
`validar después`
→
`intentar reparar`

---

# 18. Identidad

No utilizar nombres visibles como identidad técnica definitiva.

Los IDs deben ser independientes de:

- nombre;
- etiqueta visible;
- posición;
- fecha;
- horario;

salvo que un documento normativo indique expresamente otra cosa.

---

# 19. JavaScript

Mientras el proyecto continúe utilizando JavaScript nativo:

- utilizar módulos ES cuando corresponda;
- evitar variables globales innecesarias;
- preferir `const` cuando una referencia no cambia;
- utilizar `let` cuando exista reasignación;
- evitar `var`;
- utilizar nombres descriptivos;
- mantener funciones enfocadas;
- evitar efectos secundarios innecesarios.

---

# 20. Código comprensible

La solución no debe optimizarse exclusivamente para producir menos líneas.

Preferir:

`código explícito y comprensible`

sobre:

`código inteligente pero difícil de seguir`.

No introducir patrones avanzados únicamente para demostrar sofisticación.

---

# 21. Comentarios

Los comentarios deben explicar principalmente:

- intención;
- regla;
- razón;
- restricción no evidente.

Evitar comentarios que solamente traduzcan literalmente el código.

Ejemplo innecesario:

```js
// Suma uno
count += 1;
```

Ejemplo útil:

```js
// Una occurrence cancelada conserva historial,
// pero deja de bloquear el intervalo temporal.
```

---

# 22. Nombres

Utilizar nombres consistentes con el dominio definido por la documentación.

No introducir sinónimos innecesarios para conceptos ya establecidos.

Si el dominio utiliza:

`Occurrence`

no crear simultáneamente conceptos equivalentes llamados:

`Execution`
`Instance`
`DailyRecord`

sin una razón explícita.

---

# 23. Dependencias

No añadir:

* frameworks;
* paquetes;
* librerías externas;
* servicios remotos;

sin autorización explícita del MVP actual.

Antes de introducir una dependencia debe existir una necesidad concreta.

Preferir capacidades nativas cuando resuelvan adecuadamente el problema.

---

# 24. Frontend

Preservar la identidad visual aprobada salvo que la tarea actual autorice un
rediseño.

No cambiar colores, layout o componentes únicamente por preferencia del
agente.

Las nuevas funciones deben integrarse con el lenguaje visual existente.

---

# 25. Responsive

Toda nueva funcionalidad visible debe considerar como mínimo:

* escritorio;
* pantalla compacta.

Evitar:

* scroll horizontal global accidental;
* controles superpuestos;
* botones fuera del viewport;
* diálogos imposibles de cerrar;
* texto inaccesible.

---

# 26. Accesibilidad

Preferir HTML semántico.

Para interacción utilizar normalmente:

* `button`;
* `input`;
* `select`;
* `dialog`;
* `a`;

en lugar de convertir elementos genéricos en controles.

Mantener:

* foco visible;
* navegación mediante teclado;
* labels;
* nombres accesibles;
* comportamiento mediante Enter/Space cuando corresponda.

No comunicar estados únicamente mediante color.

---

# 27. Referencias visuales

Las imágenes de `/docs/codex/assets/` son referencias.

Su categoría e interpretación deben obtenerse desde:

`/docs/codex/UI_REFERENCE.md`

cuando ese archivo forme parte de la documentación normativa actual.

No asumir que una función visible en una captura está autorizada.

---

# 28. Datos simulados

Los mocks deben servir para:

* demostrar reglas;
* probar estados;
* cubrir casos importantes;
* facilitar validación visual.

No hardcodear reglas del sistema a partir de un mock específico.

Ejemplo:

si los mocks utilizan agosto de 2026, el algoritmo no debe funcionar solamente
para agosto de 2026.

---

# 29. Fechas y horas

No asumir automáticamente UTC cuando el dominio trabaja con calendario local.

Las reglas exactas deben seguir la documentación vigente.

Evitar conversiones innecesarias entre:

* string local;
* Date;
* UTC;

que puedan cambiar de día debido a timezone.

---

# 30. Manejo de errores

Cuando una operación falla:

* no dejar estado parcial;
* no ocultar silenciosamente el error;
* proporcionar feedback comprensible;
* conservar los datos anteriores cuando sea posible.

---

# 31. No inventar decisiones de producto

Cuando exista una ambigüedad que afecte:

* historial;
* eliminación;
* recurrencia;
* identidad;
* prioridades;
* persistencia;
* reglas de negocio;

no seleccionar arbitrariamente la opción que resulte más sencilla de
programar.

Informar la ambigüedad.

---

# 32. No sobreingeniería

La arquitectura debe permitir crecer.

Eso NO significa construir ahora:

* microservicios;
* event sourcing;
* repositorios genéricos;
* factories complejas;
* patrones empresariales;
* capas sin necesidad actual.

Construir para el problema real del MVP presente.

---

# 33. Futuro backend

Mientras el proyecto siga en frontend en memoria, evitar introducir
abstracciones falsas de backend únicamente para anticipar Flask o PostgreSQL.

Sí debe evitarse una arquitectura que imposibilite posteriormente separar:

Frontend
↓
API
↓
Backend
↓
Base de datos

La adaptación debe ser razonable, no prematura.

---

# 34. Git — política general

El usuario controla:

* commits;
* pushes;
* merges;
* tags;
* ramas;
* rollback.

Un agente NO debe realizar operaciones destructivas o publicar cambios salvo
que el usuario lo solicite explícitamente y el alcance actual lo permita.

---

# 35. Durante tareas de Codex

Salvo autorización expresa, NO ejecutar:

```bash
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

---

# 36. Inspección de Git

Se permiten normalmente operaciones no destructivas como:

```bash
git status
git diff
git diff --check
git log
```

cuando ayuden a verificar el trabajo.

---

# 37. No arreglar cambios ajenos

Si `git status` muestra modificaciones que no pertenecen a la tarea actual:

* no revertirlas;
* no formatearlas;
* no incluirlas en refactors;
* no eliminarlas.

Trabajar alrededor de ellas.

---

# 38. Verificación antes de terminar

Antes de declarar una tarea terminada:

1. comprobar sintaxis;
2. comprobar imports;
3. probar las funciones modificadas;
4. ejecutar casos límite relevantes;
5. revisar regresiones;
6. revisar `git diff`;
7. ejecutar `git diff --check` cuando corresponda;
8. verificar que no se modificaron archivos fuera del alcance.

---

# 39. Navegador

Cuando exista un navegador disponible y la tarea afecte interfaz:

realizar comprobación visual real.

No afirmar que una interfaz funciona correctamente basándose únicamente en
inspección del código.

---

# 40. Responsive real

Cuando sea posible comprobar aproximadamente:

```text
1440 × 900
390 × 844
```

o dimensiones equivalentes de escritorio y móvil.

---

# 41. Pruebas

No afirmar que algo fue probado si solamente fue razonado.

Distinguir claramente entre:

* comprobado automáticamente;
* comprobado visualmente;
* inspeccionado;
* no comprobado.

---

# 42. Informe final

Al terminar una implementación, presentar un resumen que incluya como mínimo:

* archivos creados;
* archivos modificados;
* archivos eliminados;
* comportamiento implementado;
* decisiones arquitectónicas relevantes;
* pruebas realizadas;
* problemas encontrados;
* limitaciones conocidas;
* funcionalidades deliberadamente aplazadas.

---

# 43. Transparencia

Si algo no pudo verificarse:

decirlo.

Si una prueba falló:

decirlo.

Si una parte quedó incompleta:

decirlo.

No presentar una tarea como terminada únicamente porque el código fue escrito.

---

# 44. No hacer commits automáticamente

Al finalizar:

dejar los cambios disponibles para que el usuario:

1. los revise;
2. pruebe;
3. decida si realizar commit.

El agente no debe asumir que un resultado correcto debe guardarse
automáticamente en Git.

---

# 45. Filosofía del proyecto

Vatos con Sesos se está construyendo de manera incremental.

Cada entrega debe buscar:

```text
algo pequeño
+
funcional
+
comprensible
+
probable
+
reversible
```

antes de añadir la siguiente capa.

---

# 46. Objetivo técnico

La arquitectura debe favorecer simultáneamente:

* control del usuario;
* automatización;
* historial;
* extensibilidad;
* comprensión del código;
* mantenibilidad.

---

# 47. Objetivo de aprendizaje

El código también forma parte del proceso de aprendizaje del propietario del
proyecto.

Por ello:

* modularizar con intención;
* utilizar nombres claros;
* evitar magia innecesaria;
* mantener reglas localizables;
* permitir identificar fácilmente dónde modificar cada comportamiento.

El objetivo no es únicamente:

`que funcione`.

También es:

`que pueda entenderse, mantenerse y evolucionar`.

---

# Regla final

Antes de tomar una decisión técnica preguntar conceptualmente:

```text
¿Está autorizada por la tarea actual?

¿Conserva el comportamiento aprobado?

¿Existe una solución más simple?

¿Mantiene una sola fuente de verdad?

¿Puedo explicar claramente por qué existe?
```

Si la respuesta no está clara:

no inventar silenciosamente.

Revisar la documentación o informar la duda.
