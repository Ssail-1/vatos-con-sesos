# Fixes

## Incidencias observadas no reproducibles

### Edición de una semana pasada

Durante una prueba de MVP 04, al modificar el patrón de una semana anterior,
las celdas afectadas aparecieron temporalmente vacías.

Al repetir exactamente la prueba, el comportamiento fue correcto y no volvió
a reproducirse.

Estado:

- No reproducible actualmente.
- No bloquea MVP 04.
- Revisar si vuelve a aparecer durante uso real.

## Conflict resolution, displacement provenance and recovery

### Objetivo general

Permitir que el usuario resuelva conflictos temporales sin obligarlo a
abandonar el flujo actual de creación o edición.

Cuando una nueva occurrence o una occurrence editada entre en conflicto con
otras occurrences, la UI debe mostrar cuáles son y permitir resolverlas de
forma explícita.

Principio:

```text
el sistema detecta el conflicto
el usuario decide qué hacer
el backend vuelve a validar
la operación se ejecuta atómicamente
```

No realizar desplazamientos silenciosos.

---

### 1. Dos conceptos diferentes de desplazamiento

Distinguir:

```text
priority override
```

de:

```text
user-authorized displacement
```

#### Priority override

Ocurre cuando las reglas de prioridad permiten que una occurrence de mayor
jerarquía desplace otra.

Ejemplo:

```text
UNEXPECTED 300
desplaza
NORMAL 100
```

Puede conservar una razón equivalente a:

```text
priority_override
```

#### User-authorized displacement

El usuario puede decidir conscientemente desplazar una occurrence en
conflicto incluso si la nueva occurrence posee igual o menor prioridad.

Ejemplo:

```text
Nueva occurrence NORMAL 100
entra en conflicto con EVENT 200

usuario revisa el conflicto
→ decide desplazar EVENT
→ operación permitida si ninguna otra regla de dominio lo prohíbe
```

La prioridad deja de ser la razón del desplazamiento.

Debe existir una razón distinta equivalente conceptualmente a:

```text
user_conflict_resolution
```

El nombre definitivo se decidirá al implementar.

La autorización explícita del usuario NO debe saltarse restricciones duras
del dominio que se definan como inmutables.

---

### 2. Cancelled no significa deleted

Una occurrence con:

```text
status = cancelled
```

continúa:

```text
existiendo
visible
editable dentro de su ventana temporal
conservando su ID
conservando su historia
```

Cancelar nunca equivale a eliminar.

---

### 3. Estados que no ocupan espacio temporal

Como mínimo:

```text
cancelled
not_completed
```

NO deben bloquear la creación o reprogramación de otras occurrences encima
del mismo intervalo.

Es decir:

```text
cancelled occurrence
+
new occurrence same time
→ permitido
```

y:

```text
not_completed occurrence
+
new occurrence same time
→ permitido
```

La política exacta para otros estados, especialmente:

```text
not_finished
```

debe revisarse al implementar.

---

### 4. Una occurrence desplazada sigue siendo editable

Dentro de la ventana temporal permitida, una occurrence desplazada puede
ser corregida manualmente.

Ejemplo:

```text
08:00–10:00 Estudiar
→ cancelled por conflicto
```

Después el usuario recuerda:

```text
realmente estudié de 07:00–07:45
```

Debe poder editar:

```text
08:00–10:00
→
07:00–07:45
```

sin que el sistema restaure automáticamente su status.

Resultado inmediato:

```text
07:00–07:45
status = cancelled
```

hasta que el usuario cambie explícitamente el estado.

No comportamiento mágico.

---

### 5. Recuperación manual de una occurrence desplazada

Después de mover una occurrence desplazada a un intervalo compatible, el
usuario puede cambiar manualmente su status según las reglas válidas.

Ejemplos conceptuales:

```text
cancelled
→ completed
```

```text
cancelled
→ not_completed
```

```text
cancelled
→ not_finished
```

si la política temporal/status correspondiente lo permite.

El sistema no debe inferir automáticamente:

```text
mover → completed
```

ni:

```text
desapareció el conflicto → pending
```

El usuario conserva control explícito.

---

### 6. Una occurrence puede ser desplazada por múltiples occurrences

El modelo actual basado conceptualmente en:

```text
sourceOccurrenceId
```

solo puede representar una fuente.

Eso no basta para casos reales.

Ejemplo:

```text
Uber
14:00–17:00
```

puede solaparse con:

```text
A 14:00–14:30
B 16:00–16:30
C 14:44–15:30
```

Uber puede estar desplazada por:

```text
A
B
C
```

simultáneamente.

Por tanto, la futura representación debe permitir:

```text
0..N source occurrences
```

y no únicamente una.

No decidir todavía si esto se implementará como:

```text
array en contexto
```

o preferentemente una relación normalizada como:

```text
occurrence_displacement_sources
```

La estructura física se diseñará cuando esta feature entre en fase activa.

No crear migration anticipadamente solo por esta nota.

---

### 7. Provenance de conflictos

Una occurrence desplazada debe poder conocer qué occurrences activas
explican actualmente su desplazamiento.

Conceptualmente:

```text
target occurrence
← source A
← source B
← source C
```

Cada relación puede necesitar distinguir el motivo:

```text
priority_override
user_conflict_resolution
```

u otros motivos futuros si aparecen.

No asumir que el statusContext actual de una sola fuente será suficiente
para este modelo.

---

### 8. Sources que dejan de ser activas

Si una occurrence que servía como fuente de desplazamiento termina en:

```text
cancelled
```

o:

```text
not_completed
```

esa occurrence deja de representar una razón activa para ocupar ese espacio
temporal.

Por tanto, ya no debe considerarse un blocker activo de la occurrence
desplazada.

Ejemplo:

```text
Uber cancelled
por A + B + C
```

si:

```text
A → cancelled
B → completed
C → not_completed
```

la única fuente activa relevante queda siendo:

```text
B
```

---

### 9. No restauración automática

Eliminar/inactivar todas las fuentes de desplazamiento NO debe restaurar
automáticamente la occurrence desplazada.

Ejemplo:

```text
Uber = cancelled
sources = A, B, C
```

después:

```text
A = cancelled
B = not_completed
C = cancelled
```

aunque ya no exista ninguna fuente activa:

```text
Uber sigue cancelled
```

hasta una acción explícita del usuario.

Esto permite que el usuario utilice deliberadamente el sistema de forma
flexible y evita comportamiento mágico.

---

### 10. Limpieza de provenance

La relación de desplazamiento representa fuentes relevantes del conflicto,
no necesariamente una explicación eterna del status actual.

Si una source occurrence pasa a un estado que ya no ocupa tiempo:

```text
cancelled
not_completed
```

debe dejar de contarse como source activa.

Debe definirse al implementar si:

```text
la relación se elimina físicamente
```

o:

```text
se conserva como provenance histórica pero queda inactiva
```

Preferir el modelo más simple que preserve las necesidades reales del
producto.

No crear historial/versionado por iniciativa propia.

---

### 11. Cierre de ventana temporal

Cuando la ventana de edición expire, las relaciones de conflicto que ya no
sean relevantes deben quedar normalizadas/coherentes.

Especialmente:

```text
una occurrence no debería seguir apareciendo como cancelada "por X"
si X finalmente quedó cancelled o not_completed
```

La occurrence desplazada NO se restaura.

Solo deja de mantener una relación activa que ya no explica un bloqueo real.

La política exacta de limpieza debe definirse antes de implementar jobs,
reconciliation o frozen-history cleanup.

---

### 12. StatusContext vs conflict provenance

El modelo actual:

```js
statusContext = {
  reason: "priority_override",
  sourceOccurrenceId: "..."
}
```

probablemente no sea suficiente para representar:

```text
múltiples sources
+
priority displacement
+
user-authorized displacement
```

Al diseñar esta feature debe separarse conceptualmente:

```text
status actual de la occurrenc## Conflict resolution, displacement provenance and recovery

### Objetivo general

Permitir que el usuario resuelva conflictos temporales sin obligarlo a
abandonar el flujo actual de creación o edición.

Cuando una nueva occurrence o una occurrence editada entre en conflicto con
otras occurrences, la UI debe mostrar cuáles son y permitir resolverlas de
forma explícita.

Principio:

```text
el sistema detecta el conflicto
el usuario decide qué hacer
el backend vuelve a validar
la operación se ejecuta atómicamente
```

No realizar desplazamientos silenciosos.

---

### 1. Dos conceptos diferentes de desplazamiento

Distinguir:

```text
priority override
```

de:

```text
user-authorized displacement
```

#### Priority override

Ocurre cuando las reglas de prioridad permiten que una occurrence de mayor
jerarquía desplace otra.

Ejemplo:

```text
UNEXPECTED 300
desplaza
NORMAL 100
```

Puede conservar una razón equivalente a:

```text
priority_override
```

#### User-authorized displacement

El usuario puede decidir conscientemente desplazar una occurrence en
conflicto incluso si la nueva occurrence posee igual o menor prioridad.

Ejemplo:

```text
Nueva occurrence NORMAL 100
entra en conflicto con EVENT 200

usuario revisa el conflicto
→ decide desplazar EVENT
→ operación permitida si ninguna otra regla de dominio lo prohíbe
```

La prioridad deja de ser la razón del desplazamiento.

Debe existir una razón distinta equivalente conceptualmente a:

```text
user_conflict_resolution
```

El nombre definitivo se decidirá al implementar.

La autorización explícita del usuario NO debe saltarse restricciones duras
del dominio que se definan como inmutables.

---

### 2. Cancelled no significa deleted

Una occurrence con:

```text
status = cancelled
```

continúa:

```text
existiendo
visible
editable dentro de su ventana temporal
conservando su ID
conservando su historia
```

Cancelar nunca equivale a eliminar.

---

### 3. Estados que no ocupan espacio temporal

Como mínimo:

```text
cancelled
not_completed
```

NO deben bloquear la creación o reprogramación de otras occurrences encima
del mismo intervalo.

Es decir:

```text
cancelled occurrence
+
new occurrence same time
→ permitido
```

y:

```text
not_completed occurrence
+
new occurrence same time
→ permitido
```

La política exacta para otros estados, especialmente:

```text
not_finished
```

debe revisarse al implementar.

---

### 4. Una occurrence desplazada sigue siendo editable

Dentro de la ventana temporal permitida, una occurrence desplazada puede
ser corregida manualmente.

Ejemplo:

```text
08:00–10:00 Estudiar
→ cancelled por conflicto
```

Después el usuario recuerda:

```text
realmente estudié de 07:00–07:45
```

Debe poder editar:

```text
08:00–10:00
→
07:00–07:45
```

sin que el sistema restaure automáticamente su status.

Resultado inmediato:

```text
07:00–07:45
status = cancelled
```

hasta que el usuario cambie explícitamente el estado.

No comportamiento mágico.

---

### 5. Recuperación manual de una occurrence desplazada

Después de mover una occurrence desplazada a un intervalo compatible, el
usuario puede cambiar manualmente su status según las reglas válidas.

Ejemplos conceptuales:

```text
cancelled
→ completed
```

```text
cancelled
→ not_completed
```

```text
cancelled
→ not_finished
```

si la política temporal/status correspondiente lo permite.

El sistema no debe inferir automáticamente:

```text
mover → completed
```

ni:

```text
desapareció el conflicto → pending
```

El usuario conserva control explícito.

---

### 6. Una occurrence puede ser desplazada por múltiples occurrences

El modelo actual basado conceptualmente en:

```text
sourceOccurrenceId
```

solo puede representar una fuente.

Eso no basta para casos reales.

Ejemplo:

```text
Uber
14:00–17:00
```

puede solaparse con:

```text
A 14:00–14:30
B 16:00–16:30
C 14:44–15:30
```

Uber puede estar desplazada por:

```text
A
B
C
```

simultáneamente.

Por tanto, la futura representación debe permitir:

```text
0..N source occurrences
```

y no únicamente una.

No decidir todavía si esto se implementará como:

```text
array en contexto
```

o preferentemente una relación normalizada como:

```text
occurrence_displacement_sources
```

La estructura física se diseñará cuando esta feature entre en fase activa.

No crear migration anticipadamente solo por esta nota.

---

### 7. Provenance de conflictos

Una occurrence desplazada debe poder conocer qué occurrences activas
explican actualmente su desplazamiento.

Conceptualmente:

```text
target occurrence
← source A
← source B
← source C
```

Cada relación puede necesitar distinguir el motivo:

```text
priority_override
user_conflict_resolution
```

u otros motivos futuros si aparecen.

No asumir que el statusContext actual de una sola fuente será suficiente
para este modelo.

---

### 8. Sources que dejan de ser activas

Si una occurrence que servía como fuente de desplazamiento termina en:

```text
cancelled
```

o:

```text
not_completed
```

esa occurrence deja de representar una razón activa para ocupar ese espacio
temporal.

Por tanto, ya no debe considerarse un blocker activo de la occurrence
desplazada.

Ejemplo:

```text
Uber cancelled
por A + B + C
```

si:

```text
A → cancelled
B → completed
C → not_completed
```

la única fuente activa relevante queda siendo:

```text
B
```

---

### 9. No restauración automática

Eliminar/inactivar todas las fuentes de desplazamiento NO debe restaurar
automáticamente la occurrence desplazada.

Ejemplo:

```text
Uber = cancelled
sources = A, B, C
```

después:

```text
A = cancelled
B = not_completed
C = cancelled
```

aunque ya no exista ninguna fuente activa:

```text
Uber sigue cancelled
```

hasta una acción explícita del usuario.

Esto permite que el usuario utilice deliberadamente el sistema de forma
flexible y evita comportamiento mágico.

---

### 10. Limpieza de provenance

La relación de desplazamiento representa fuentes relevantes del conflicto,
no necesariamente una explicación eterna del status actual.

Si una source occurrence pasa a un estado que ya no ocupa tiempo:

```text
cancelled
not_completed
```

debe dejar de contarse como source activa.

Debe definirse al implementar si:

```text
la relación se elimina físicamente
```

o:

```text
se conserva como provenance histórica pero queda inactiva
```

Preferir el modelo más simple que preserve las necesidades reales del
producto.

No crear historial/versionado por iniciativa propia.

---

### 11. Cierre de ventana temporal

Cuando la ventana de edición expire, las relaciones de conflicto que ya no
sean relevantes deben quedar normalizadas/coherentes.

Especialmente:

```text
una occurrence no debería seguir apareciendo como cancelada "por X"
si X finalmente quedó cancelled o not_completed
```

La occurrence desplazada NO se restaura.

Solo deja de mantener una relación activa que ya no explica un bloqueo real.

La política exacta de limpieza debe definirse antes de implementar jobs,
reconciliation o frozen-history cleanup.

---

### 12. StatusContext vs conflict provenance

El modelo actual:

```js
statusContext = {
  reason: "priority_override",
  sourceOccurrenceId: "..."
}
```

probablemente no sea suficiente para representar:

```text
múltiples sources
+
priority displacement
+
user-authorized displacement
```

Al diseñar esta feature debe separarse conceptualmente:

```text
status actual de la occurrence
```

de:

```text
relaciones de conflicto/desplazamiento
```

Una occurrence puede conservar provenance de conflicto sin que esa
provenance deba describir necesariamente su status actual.

Ejemplo:

```text
Uber fue desplazada por A y B
después el usuario la mueve
después la marca completed
```

No debe quedar semánticamente:

```text
completed because priority_override
```

La razón del status y la provenance del conflicto son conceptos distintos.

---

### 13. Transiciones manuales de occurrences desplazadas

Debe recuperarse y formalizarse la política previamente discutida para
occurrences desplazadas.

Como base:

```text
cancelled
not_completed
not_finished
```

pueden tener determinadas transiciones manuales dentro de la ventana de
edición.

La política exacta todavía requiere definición.

Especialmente revisar:

```text
not_finished
```

cuando una nueva occurrence cubre solo parte de una occurrence existente.

Ejemplo:

```text
original:
08:00–10:00

override:
09:30–11:00
```

puede ser razonable que la original represente actividad parcial:

```text
08:00–09:30
not_finished
```

---

### 14. Occurrences en los extremos de un bloque desplazado

Cuando una nueva occurrence desplaza varias occurrences consecutivas, las
occurrences de los extremos pueden tener cobertura parcial.

Ejemplo:

```text
A 08–09
B 09–10
C 10–11

Nueva occurrence:
08:30–10:30
```

Posible interpretación:

```text
A → parcialmente realizada
B → completamente desplazada
C → parcialmente realizada
```

Por tanto, las reglas de:

```text
not_finished
```

pueden diferir entre:

```text
occurrence inicial
occurrence intermedia
occurrence final
```

No formalizar todavía la transición exacta sin diseñar los casos límite.

Añadir tests específicos cuando se implemente.

---

### 15. UI de resolución de conflictos

Cuando Create, Single Day, Apply Week o Apply Future produzcan conflictos,
mostrar una ventana contextual sin sacar al usuario del flujo.

Ejemplo:

```text
Este cambio entra en conflicto con:

08:00–09:00  Desayuno
09:00–10:30  Estudiar
10:00–11:00  Inglés
```

Cada occurrence debe mostrar suficiente contexto:

```text
nombre
horario
status
tipo/prioridad cuando aporte valor
```

---

### 16. Acciones por occurrence dentro del conflicto

Debajo/junto a cada occurrence conflictiva ofrecer acciones contextuales
equivalentes a:

```text
[Ajustar]
[Desplazar]
```

#### Ajustar

Abrir directamente un editor de ESA occurrence sobre el flujo actual.

No obligar al usuario a:

```text
cerrar conflicto
buscar la occurrence
abrir editor
editar
regresar
volver a ejecutar operación
```

Después de guardar el ajuste:

```text
volver al diálogo original
recalcular conflictos
```

#### Desplazar

Autorizar explícitamente que esa occurrence sea desplazada para permitir la
operación actual.

---

### 17. Acción global

Al final del diálogo ofrecer una acción equivalente a:

```text
[Desplazar todas las compatibles]
```

o, si la UX final lo prefiere:

```text
[Cancelar todas las compatibles y continuar]
```

Esta acción:

```text
NO significa cancelEverything=true
```

El cliente envía/autorización explícita de las occurrences concretas que el
usuario vio.

El backend vuelve a recalcular antes de ejecutar.

Si aparece un conflicto nuevo:

```text
pedir confirmación nuevamente
```

No desplazar silenciosamente nuevas occurrences.

---

### 18. Progressive disclosure

Estas opciones NO deben saturar la UI principal.

Solo aparecen cuando el usuario entra en un flujo que realmente las
necesita:

```text
crear
editar
mover
Apply Week
Apply Future
```

y se detecta un conflicto.

Principio UX:

```text
mostrar complejidad únicamente cuando el contexto la requiere
```

Esto permite ofrecer atajos potentes sin hacer más complicada la navegación
normal.

---

### 19. Revalidación obligatoria

Cualquier operación de resolución:

```text
ajustar
desplazar una
desplazar varias
desplazar todas
```

debe terminar con una nueva validación del estado actual.

Nunca confiar únicamente en la lista de conflictos mostrada inicialmente.

Esto protege contra:

```text
cambios concurrentes
nuevo conflicto
occurrence modificada/eliminada
status cambiado
```

---

### 20. Atomicidad

Cuando una creación/edición finalmente sea confirmada con desplazamientos:

```text
nueva mutation
+
status de occurrences desplazadas
+
provenance de displacement
```

deben persistirse de forma coherente/atómica.

No dejar:

```text
occurrences canceladas
```

si finalmente la nueva operation no pudo guardarse.

---

### 21. Relación con próximas fases

Parte de la infraestructura aparecerá naturalmente en:

```text
05.7.3 Single Day persistent
05.7.4 Apply Week / Apply Future persistent
```

La UX común completa debe consolidarse en una fase equivalente a:

```text
05.7.5 Mutation conflict resolution UX
```

No implementar toda esta sección anticipadamente durante una fase más## Conflict resolution, displacement provenance and recovery

### Objetivo general

Permitir que el usuario resuelva conflictos temporales sin obligarlo a
abandonar el flujo actual de creación o edición.

Cuando una nueva occurrence o una occurrence editada entre en conflicto con
otras occurrences, la UI debe mostrar cuáles son y permitir resolverlas de
forma explícita.

Principio:

```text
el sistema detecta el conflicto
el usuario decide qué hacer
el backend vuelve a validar
la operación se ejecuta atómicamente
```

No realizar desplazamientos silenciosos.

---

### 1. Dos conceptos diferentes de desplazamiento

Distinguir:

```text
priority override
```

de:

```text
user-authorized displacement
```

#### Priority override

Ocurre cuando las reglas de prioridad permiten que una occurrence de mayor
jerarquía desplace otra.

Ejemplo:

```text
UNEXPECTED 300
desplaza
NORMAL 100
```

Puede conservar una razón equivalente a:

```text
priority_override
```

#### User-authorized displacement

El usuario puede decidir conscientemente desplazar una occurrence en
conflicto incluso si la nueva occurrence posee igual o menor prioridad.

Ejemplo:

```text
Nueva occurrence NORMAL 100
entra en conflicto con EVENT 200

usuario revisa el conflicto
→ decide desplazar EVENT
→ operación permitida si ninguna otra regla de dominio lo prohíbe
```

La prioridad deja de ser la razón del desplazamiento.

Debe existir una razón distinta equivalente conceptualmente a:

```text
user_conflict_resolution
```

El nombre definitivo se decidirá al implementar.

La autorización explícita del usuario NO debe saltarse restricciones duras
del dominio que se definan como inmutables.

---

### 2. Cancelled no significa deleted

Una occurrence con:

```text
status = cancelled
```

continúa:

```text
existiendo
visible
editable dentro de su ventana temporal
conservando su ID
conservando su historia
```

Cancelar nunca equivale a eliminar.

---

### 3. Estados que no ocupan espacio temporal

Como mínimo:

```text
cancelled
not_completed
```

NO deben bloquear la creación o reprogramación de otras occurrences encima
del mismo intervalo.

Es decir:

```text
cancelled occurrence
+
new occurrence same time
→ permitido
```

y:

```text
not_completed occurrence
+
new occurrence same time
→ permitido
```

La política exacta para otros estados, especialmente:

```text
not_finished
```

debe revisarse al implementar.

---

### 4. Una occurrence desplazada sigue siendo editable

Dentro de la ventana temporal permitida, una occurrence desplazada puede
ser corregida manualmente.

Ejemplo:

```text
08:00–10:00 Estudiar
→ cancelled por conflicto
```

Después el usuario recuerda:

```text
realmente estudié de 07:00–07:45
```

Debe poder editar:

```text
08:00–10:00
→
07:00–07:45
```

sin que el sistema restaure automáticamente su status.

Resultado inmediato:

```text
07:00–07:45
status = cancelled
```

hasta que el usuario cambie explícitamente el estado.

No comportamiento mágico.

---

### 5. Recuperación manual de una occurrence desplazada

Después de mover una occurrence desplazada a un intervalo compatible, el
usuario puede cambiar manualmente su status según las reglas válidas.

Ejemplos conceptuales:

```text
cancelled
→ completed
```

```text
cancelled
→ not_completed
```

```text
cancelled
→ not_finished
```

si la política temporal/status correspondiente lo permite.

El sistema no debe inferir automáticamente:

```text
mover → completed
```

ni:

```text
desapareció el conflicto → pending
```

El usuario conserva control explícito.

---

### 6. Una occurrence puede ser desplazada por múltiples occurrences

El modelo actual basado conceptualmente en:

```text
sourceOccurrenceId
```

solo puede representar una fuente.

Eso no basta para casos reales.

Ejemplo:

```text
Uber
14:00–17:00
```

puede solaparse con:

```text
A 14:00–14:30
B 16:00–16:30
C 14:44–15:30
```

Uber puede estar desplazada por:

```text
A
B
C
```

simultáneamente.

Por tanto, la futura representación debe permitir:

```text
0..N source occurrences
```

y no únicamente una.

No decidir todavía si esto se implementará como:

```text
array en contexto
```

o preferentemente una relación normalizada como:

```text
occurrence_displacement_sources
```

La estructura física se diseñará cuando esta feature entre en fase activa.

No crear migration anticipadamente solo por esta nota.

---

### 7. Provenance de conflictos

Una occurrence desplazada debe poder conocer qué occurrences activas
explican actualmente su desplazamiento.

Conceptualmente:

```text
target occurrence
← source A
← source B
← source C
```

Cada relación puede necesitar distinguir el motivo:

```text
priority_override
user_conflict_resolution
```

u otros motivos futuros si aparecen.

No asumir que el statusContext actual de una sola fuente será suficiente
para este modelo.

---

### 8. Sources que dejan de ser activas

Si una occurrence que servía como fuente de desplazamiento termina en:

```text
cancelled
```

o:

```text
not_completed
```

esa occurrence deja de representar una razón activa para ocupar ese espacio
temporal.

Por tanto, ya no debe considerarse un blocker activo de la occurrence
desplazada.

Ejemplo:

```text
Uber cancelled
por A + B + C
```

si:

```text
A → cancelled
B → completed
C → not_completed
```

la única fuente activa relevante queda siendo:

```text
B
```

---

### 9. No restauración automática

Eliminar/inactivar todas las fuentes de desplazamiento NO debe restaurar
automáticamente la occurrence desplazada.

Ejemplo:

```text
Uber = cancelled
sources = A, B, C
```

después:

```text
A = cancelled
B = not_completed
C = cancelled
```

aunque ya no exista ninguna fuente activa:

```text
Uber sigue cancelled
```

hasta una acción explícita del usuario.

Esto permite que el usuario utilice deliberadamente el sistema de forma
flexible y evita comportamiento mágico.

---

### 10. Limpieza de provenance

La relación de desplazamiento representa fuentes relevantes del conflicto,
no necesariamente una explicación eterna del status actual.

Si una source occurrence pasa a un estado que ya no ocupa tiempo:

```text
cancelled
not_completed
```

debe dejar de contarse como source activa.

Debe definirse al implementar si:

```text
la relación se elimina físicamente
```

o:

```text
se conserva como provenance histórica pero queda inactiva
```

Preferir el modelo más simple que preserve las necesidades reales del
producto.

No crear historial/versionado por iniciativa propia.

---

### 11. Cierre de ventana temporal

Cuando la ventana de edición expire, las relaciones de conflicto que ya no
sean relevantes deben quedar normalizadas/coherentes.

Especialmente:

```text
una occurrence no debería seguir apareciendo como cancelada "por X"
si X finalmente quedó cancelled o not_completed
```

La occurrence desplazada NO se restaura.

Solo deja de mantener una relación activa que ya no explica un bloqueo real.

La política exacta de limpieza debe definirse antes de implementar jobs,
reconciliation o frozen-history cleanup.

---

### 12. StatusContext vs conflict provenance

El modelo actual:

```js
statusContext = {
  reason: "priority_override",
  sourceOccurrenceId: "..."
}
```

probablemente no sea suficiente para representar:

```text
múltiples sources
+
priority displacement
+
user-authorized displacement
```

Al diseñar esta feature debe separarse conceptualmente:

```text
status actual de la occurrence
```

de:

```text
relaciones de conflicto/desplazamiento
```

Una occurrence puede conservar provenance de conflicto sin que esa
provenance deba describir necesariamente su status actual.

Ejemplo:

```text
Uber fue desplazada por A y B
después el usuario la mueve
después la marca completed
```

No debe quedar semánticamente:

```text
completed because priority_override
```

La razón del status y la provenance del conflicto son conceptos distintos.

---

### 13. Transiciones manuales de occurrences desplazadas

Debe recuperarse y formalizarse la política previamente discutida para
occurrences desplazadas.

Como base:

```text
cancelled
not_completed
not_finished
```

pueden tener determinadas transiciones manuales dentro de la ventana de
edición.

La política exacta todavía requiere definición.

Especialmente revisar:

```text
not_finished
```

cuando una nueva occurrence cubre solo parte de una occurrence existente.

Ejemplo:

```text
original:
08:00–10:00

override:
09:30–11:00
```

puede ser razonable que la original represente actividad parcial:

```text
08:00–09:30
not_finished
```

---

### 14. Occurrences en los extremos de un bloque desplazado

Cuando una nueva occurrence desplaza varias occurrences consecutivas, las
occurrences de los extremos pueden tener cobertura parcial.

Ejemplo:

```text
A 08–09
B 09–10
C 10–11

Nueva occurrence:
08:30–10:30
```

Posible interpretación:

```text
A → parcialmente realizada
B → completamente desplazada
C → parcialmente realizada
```

Por tanto, las reglas de:

```text
not_finished
```

pueden diferir entre:

```text
occurrence inicial
occurrence intermedia
occurrence final
```

No formalizar todavía la transición exacta sin diseñar los casos límite.

Añadir tests específicos cuando se implemente.

---

### 15. UI de resolución de conflictos

Cuando Create, Single Day, Apply Week o Apply Future produzcan conflictos,
mostrar una ventana contextual sin sacar al usuario del flujo.

Ejemplo:

```text
Este cambio entra en conflicto con:

08:00–09:00  Desayuno
09:00–10:30  Estudiar
10:00–11:00  Inglés
```

Cada occurrence debe mostrar suficiente contexto:

```text
nombre
horario
status
tipo/prioridad cuando aporte valor
```

---

### 16. Acciones por occurrence dentro del conflicto

Debajo/junto a cada occurrence conflictiva ofrecer acciones contextuales
equivalentes a:

```text
[Ajustar]
[Desplazar]
```

#### Ajustar

Abrir directamente un editor de ESA occurrence sobre el flujo actual.

No obligar al usuario a:

```text
cerrar conflicto
buscar la occurrence
abrir editor
editar
regresar
volver a ejecutar operación
```

Después de guardar el ajuste:

```text
volver al diálogo original
recalcular conflictos
```

#### Desplazar

Autorizar explícitamente que esa occurrence sea desplazada para permitir la
operación actual.

---

### 17. Acción global

Al final del diálogo ofrecer una acción equivalente a:

```text
[Desplazar todas las compatibles]
```

o, si la UX final lo prefiere:

```text
[Cancelar todas las compatibles y continuar]
```

Esta acción:

```text
NO significa cancelEverything=true
```

El cliente envía/autorización explícita de las occurrences concretas que el
usuario vio.

El backend vuelve a recalcular antes de ejecutar.

Si aparece un conflicto nuevo:

```text
pedir confirmación nuevamente
```

No desplazar silenciosamente nuevas occurrences.

---

### 18. Progressive disclosure

Estas opciones NO deben saturar la UI principal.

Solo aparecen cuando el usuario entra en un flujo que realmente las
necesita:

```text
crear
editar
mover
Apply Week
Apply Future
```

y se detecta un conflicto.

Principio UX:

```text
mostrar complejidad únicamente cuando el contexto la requiere
```

Esto permite ofrecer atajos potentes sin hacer más complicada la navegación
normal.

---

### 19. Revalidación obligatoria

Cualquier operación de resolución:

```text
ajustar
desplazar una
desplazar varias
desplazar todas
```

debe terminar con una nueva validación del estado actual.

Nunca confiar únicamente en la lista de conflictos mostrada inicialmente.

Esto protege contra:

```text
cambios concurrentes
nuevo conflicto
occurrence modificada/eliminada
status cambiado
```

---

### 20. Atomicidad

Cuando una creación/edición finalmente sea confirmada con desplazamientos:

```text
nueva mutation
+
status de occurrences desplazadas
+
provenance de displacement
```

deben persistirse de forma coherente/atómica.

No dejar:

```text
occurrences canceladas
```

si finalmente la nueva operation no pudo guardarse.

---

### 21. Relación con próximas fases

Parte de la infraestructura aparecerá naturalmente en:

```text
05.7.3 Single Day persistent
05.7.4 Apply Week / Apply Future persistent
```

La UX común completa debe consolidarse en una fase equivalente a:

```text
05.7.5 Mutation conflict resolution UX
```

No implementar toda esta sección anticipadamente durante una fase más
pequeña.

---

### 22. Decisiones todavía pendientes

Definir antes de implementar definitivamente:

```text
estructura física para múltiples displacement sources
```

```text
si provenance inactiva se elimina o se conserva históricamente
```

```text
reglas exactas cancelled ↔ not_completed ↔ not_finished
```

```text
qué estados además de cancelled/not_completed dejan de ocupar espacio
```

```text
reglas de cobertura parcial para primera/última occurrence
```

```text
momento exacto de cleanup al congelar historia
```

```text
nombres definitivos:
priority_override
user_conflict_resolution
conflict/displacement provenance
```

No decidir estas cuestiones por accidente durante otra feature.
pequeña.

---

### 22. Decisiones todavía pendientes

Definir antes de implementar definitivamente:

```text
estructura física para múltiples displacement sources
```

```text
si provenance inactiva se elimina o se conserva históricamente
```

```text
reglas exactas cancelled ↔ not_completed ↔ not_finished
```

```text
qué estados además de cancelled/not_completed dejan de ocupar espacio
```

```text
reglas de cobertura parcial para primera/última occurrence
```

```text
momento exacto de cleanup al congelar historia
```

```text
nombres definitivos:
priority_override
user_conflict_resolution
conflict/displacement provenance
```

No decidir estas cuestiones por accidente durante otra feature.e
```

de:

```text
relaciones de conflicto/desplazamiento
```

Una occurrence puede conservar provenance de conflicto sin que esa
provenance deba describir necesariamente su status actual.

Ejemplo:

```text
Uber fue desplazada por A y B
después el usuario la mueve
después la marca completed
```

No debe quedar semánticamente:

```text
completed because priority_override
```

La razón del status y la provenance del conflicto son conceptos distintos.

---

### 13. Transiciones manuales de occurrences desplazadas

Debe recuperarse y formalizarse la política previamente discutida para
occurrences desplazadas.

Como base:

```text
cancelled
not_completed
not_finished
```

pueden tener determinadas transiciones manuales dentro de la ventana de
edición.

La política exacta todavía requiere definición.

Especialmente revisar:

```text
not_finished
```

cuando una nueva occurrence cubre solo parte de una occurrence existente.

Ejemplo:

```text
original:
08:00–10:00

override:
09:30–11:00
```

puede ser razonable que la original represente actividad parcial:

```text
08:00–09:30
not_finished
```

---

### 14. Occurrences en los extremos de un bloque desplazado

Cuando una nueva occurrence desplaza varias occurrences consecutivas, las
occurrences de los extremos pueden tener cobertura parcial.

Ejemplo:

```text
A 08–09
B 09–10
C 10–11

Nueva occurrence:
08:30–10:30
```

Posible interpretación:

```text
A → parcialmente realizada
B → completamente desplazada
C → parcialmente realizada
```

Por tanto, las reglas de:

```text
not_finished
```

pueden diferir entre:

```text
occurrence inicial
occurrence intermedia
occurrence final
```

No formalizar todavía la transición exacta sin diseñar los casos límite.

Añadir tests específicos cuando se implemente.

---

### 15. UI de resolución de conflictos

Cuando Create, Single Day, Apply Week o Apply Future produzcan conflictos,
mostrar una ventana contextual sin sacar al usuario del flujo.

Ejemplo:

```text
Este cambio entra en conflicto con:

08:00–09:00  Desayuno
09:00–10:30  Estudiar
10:00–11:00  Inglés
```

Cada occurrence debe mostrar suficiente contexto:

```text
nombre
horario
status
tipo/prioridad cuando aporte valor
```

---

### 16. Acciones por occurrence dentro del conflicto

Debajo/junto a cada occurrence conflictiva ofrecer acciones contextuales
equivalentes a:

```text
[Ajustar]
[Desplazar]
```

#### Ajustar

Abrir directamente un editor de ESA occurrence sobre el flujo actual.

No obligar al usuario a:

```text
cerrar conflicto
buscar la occurrence
abrir editor
editar
regresar
volver a ejecutar operación
```

Después de guardar el ajuste:

```text
volver al diálogo original
recalcular conflictos
```

#### Desplazar

Autorizar explícitamente que esa occurrence sea desplazada para permitir la
operación actual.

---

### 17. Acción global

Al final del diálogo ofrecer una acción equivalente a:

```text
[Desplazar todas las compatibles]
```

o, si la UX final lo prefiere:

```text
[Cancelar todas las compatibles y continuar]
```

Esta acción:

```text
NO significa cancelEverything=true
```

El cliente envía/autorización explícita de las occurrences concretas que el
usuario vio.

El backend vuelve a recalcular antes de ejecutar.

Si aparece un conflicto nuevo:

```text
pedir confirmación nuevamente
```

No desplazar silenciosamente nuevas occurrences.

---

### 18. Progressive disclosure

Estas opciones NO deben saturar la UI principal.

Solo aparecen cuando el usuario entra en un flujo que realmente las
necesita:

```text
crear
editar
mover
Apply Week
Apply Future
```

y se detecta un conflicto.

Principio UX:

```text
mostrar complejidad únicamente cuando el contexto la requiere
```

Esto permite ofrecer atajos potentes sin hacer más complicada la navegación
normal.

---

### 19. Revalidación obligatoria

Cualquier operación de resolución:

```text
ajustar
desplazar una
desplazar varias
desplazar todas
```

debe terminar con una nueva validación del estado actual.

Nunca confiar únicamente en la lista de conflictos mostrada inicialmente.

Esto protege contra:

```text
cambios concurrentes
nuevo conflicto
occurrence modificada/eliminada
status cambiado
```

---

### 20. Atomicidad

Cuando una creación/edición finalmente sea confirmada con desplazamientos:

```text
nueva mutation
+
status de occurrences desplazadas
+
provenance de displacement
```

deben persistirse de forma coherente/atómica.

No dejar:

```text
occurrences canceladas
```

si finalmente la nueva operation no pudo guardarse.

---

### 21. Relación con próximas fases

Parte de la infraestructura aparecerá naturalmente en:

```text
05.7.3 Single Day persistent
05.7.4 Apply Week / Apply Future persistent
```

La UX común completa debe consolidarse en una fase equivalente a:

```text
05.7.5 Mutation conflict resolution UX
```

No implementar toda esta sección anticipadamente durante una fase más
pequeña.

---

### 22. Decisiones todavía pendientes

Definir antes de implementar definitivamente:

```text
estructura física para múltiples displacement sources
```

```text
si provenance inactiva se elimina o se conserva históricamente
```

```text
reglas exactas cancelled ↔ not_completed ↔ not_finished
```

```text
qué estados además de cancelled/not_completed dejan de ocupar espacio
```

```text
reglas de cobertura parcial para primera/última occurrence
```

```text
momento exacto de cleanup al congelar historia
```

```text
nombres definitivos:
priority_override
user_conflict_resolution
conflict/displacement provenance
```

No decidir estas cuestiones por accidente durante otra feature.
