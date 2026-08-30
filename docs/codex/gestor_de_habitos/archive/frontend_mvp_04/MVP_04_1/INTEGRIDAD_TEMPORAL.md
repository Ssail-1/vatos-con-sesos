MVP 04.1.1 — Integridad temporal y cierre del modelo de estados

NO hagas commit.
NO hagas push.
NO cambies de rama.

Antes de modificar:

1. Lee AGENTS.md.
2. Lee CURRENT_TASK.md.
3. Lee la documentación normativa vigente del módulo.
4. Inspecciona occurrence-status.js.
5. Inspecciona scheduling-priority.js.
6. Inspecciona conflict-detector.js.
7. Inspecciona planner-store.js.
8. Inspecciona app.js y planner-matrix.js.
9. Ejecuta todos los tests actuales antes de modificar.

No implementar eliminación todavía.

==================================================
1. NUEVO ESTADO: not_finished
==================================================

Agregar:

not_finished

Semántica:

"La actividad comenzó, pero no terminó."

Actualizar toda fuente de verdad de estados.

not_finished:

- es un estado histórico;
- NO bloquea horario;
- NO debe tratarse como pending;
- posteriormente NO será eliminable;
- debe ser soportado por matriz, store y tests.

Visualmente:

usar como base el indicador actual de in_progress y agregar un signo "!"
claramente visible en rojo.

No depender únicamente del color para comunicar estado.

==================================================
2. HISTORY_EDIT_WINDOW_DAYS
==================================================

Crear una única fuente configurable equivalente conceptualmente a:

HISTORY_EDIT_WINDOW_DAYS = 1

Unidad:

DÍAS CALENDARIO.

No horas.

Con referenceDate = 2026-09-29 y window = 1:

29 → editable
28 → editable
27 → frozen
26 → frozen

Debe ser sencillo cambiar posteriormente a 0, 3, 7, etc.

==================================================
3. CURRENT DATE
==================================================

La frontera depende exclusivamente de currentDate.

NO depende de selectedDate.

Las funciones de dominio deben aceptar/injectar referenceDate para tests
deterministas.

No usar conversiones UTC que puedan cambiar accidentalmente el día local.

==================================================
4. RECONCILIACIÓN AL CONGELARSE
==================================================

Cuando una Occurrence sale de la ventana editable:

pending
→ not_completed

in_progress
→ not_finished

completed
→ completed

not_completed
→ not_completed

not_finished
→ not_finished

cancelled
→ cancelled

Preservar:

id
planItemId
date
startTime
endTime

La operación debe ser idempotente.

==================================================
5. HISTORIAL FROZEN
==================================================

Una Occurrence frozen es de solo lectura.

No permitir:

- cambiar status;
- editar horario;
- cambiar fecha;
- Apply week desde esa fecha;
- Apply future desde esa fecha;
- Agregar solo este día desde esa fecha;
- cualquier futura operación destructiva.

Sí permitir:

- navegar;
- consultar;
- mostrar;
- utilizar posteriormente para estadísticas.

==================================================
6. FUTURO
==================================================

Para:

occurrence.date > currentDate

los únicos estados modificables manualmente son:

pending
cancelled

Flujo:

pending ↔ cancelled

No permitir manualmente en futuro:

in_progress
completed
not_completed
not_finished

==================================================
7. REACTIVAR CANCELLED FUTURO
==================================================

Al intentar:

cancelled → pending

revalidar conflictos.

Si existe conflicto:

- permanecer cancelled;
- mostrar feedback;
- NO utilizar fallback a not_completed;
- NO utilizar fallback a not_finished.

El fallback histórico cancelled → not_completed existente debe quedar
restringido a contextos temporales donde not_completed sea un estado válido.

==================================================
8. PRESENTE / PASADO EDITABLE
==================================================

currentDate y fechas dentro de HISTORY_EDIT_WINDOW_DAYS pueden seguir
corrigiendo estados según las reglas actuales.

Integrar not_finished al flujo.

No permitir que estas reglas afecten al futuro ni al historial frozen.

==================================================
9. PRIORITY OVERRIDE + in_progress
==================================================

No inventar que una actividad comenzó solamente por geometría temporal.

Si una Occurrence desplazada por prioridad está:

pending
→ cancelled

Si está:

in_progress
→ not_finished

completed
→ continúa protegida y rechaza override.

Esto utiliza evidencia real del estado del usuario.

==================================================
10. PROCEDENCIA DE CANCELACIÓN
==================================================

El nuevo requisito necesita distinguir:

- cancelación manual;
- cancelación causada por priority override.

Implementar la representación mínima coherente para conservar esa procedencia.

Puede ser conceptualmente algo como:

statusContext: {
    reason: "priority_override",
    sourceOccurrenceId: "..."
}

No es obligatorio usar exactamente esos nombres.

Evitar duplicar estado derivable innecesariamente.

La solución debe permitir responder de forma fiable:

"¿esta Occurrence fue cancelada por una prioridad superior?"

No inferirlo únicamente buscando conflictos actuales en la matriz.

==================================================
11. INTERRUPCIÓN POR PRIORIDAD
==================================================

Dentro de la ventana editable, una Occurrence cancelada por priority override
puede requerir corrección histórica.

Si la Occurrence superior comienza dentro del intervalo de la Occurrence
desplazada, existe una situación compatible con interrupción:

lower.startTime < higher.startTime < lower.endTime

En contexto editable puede permitirse corregir entre:

cancelled
not_completed
not_finished

según las reglas de UI implementadas.

En FUTURO no permitir not_completed/not_finished.

En FROZEN no permitir ninguna modificación.

No inferir automáticamente not_finished si lower estaba pending.

==================================================
12. OVERRIDE DE in_progress
==================================================

Si lower ya estaba explícitamente in_progress cuando ocurre un override válido:

lower
→ not_finished

porque existe evidencia de que había comenzado.

Preservar procedencia del override.

completed continúa completamente protegido.

==================================================
13. BLOQUEO DE HORARIO
==================================================

Confirmar:

BLOQUEAN:
- pending
- in_progress
- completed

NO BLOQUEAN:
- not_completed
- not_finished
- cancelled

Actualizar conflict-detector y tests según corresponda.

==================================================
14. NOT_COMPLETED VISUAL
==================================================

Mantener su rojo actual pero reducir discretamente su intensidad visual.

Objetivo:

seguir comunicando que no se completó sin hacer que el historial negativo
domine visualmente la agenda.

No cambiar su semántica.

not_finished debe continuar siendo claramente diferenciable.

==================================================
15. APLICACIÓN ABIERTA DURANTE CAMBIO DE DÍA
==================================================

La reconciliación debe correr como mínimo al inicializar el planner.

Además, antes de operaciones temporales relevantes debe reevaluarse currentDate
de manera coherente para que dejar la aplicación abierta no mantenga
indefinidamente editable una fecha ya congelada.

No implementar cron/backend.

==================================================
16. NO IMPLEMENTAR
==================================================

No implementar todavía:

- Eliminar solo este día;
- Detener de aquí en adelante;
- eliminar PlanItem;
- PostgreSQL;
- Flask;
- persistencia;
- jobs de servidor;
- timezone por usuario.

==================================================
17. TESTS
==================================================

Agregar cobertura como mínimo para:

referenceDate 2026-09-29, window 1:

29 → editable
28 → editable
27 → frozen

27 pending
→ not_completed

27 in_progress
→ not_finished

27 completed
→ permanece completed

27 not_completed
→ permanece

27 not_finished
→ permanece

27 cancelled
→ permanece

Frozen:
- status rechazado;
- horario rechazado;
- Apply week rechazado;
- Apply future rechazado;
- Agregar solo este día rechazado.

Future:
- pending → cancelled permitido;
- cancelled → pending permitido si no hay conflicto;
- cancelled → pending con conflicto permanece cancelled;
- in_progress rechazado;
- completed rechazado;
- not_completed rechazado;
- not_finished rechazado.

Priority:
- pending desplazada → cancelled;
- in_progress desplazada → not_finished;
- completed protegida;
- procedencia de priority override preservada;
- cancellation manual distinguible de priority override.

not_finished:
- no bloquea horario;
- no rompe matriz;
- funciona con Habit y Activity.

Reconciliación repetida:
→ idempotente.

Cambiar HISTORY_EDIT_WINDOW_DAYS:
→ modifica correctamente cutoff.

Ejecutar además TODOS los tests anteriores.

==================================================
18. QA DE NAVEGADOR
==================================================

Probar:

- currentDate;
- yesterday editable;
- frozen past;
- future;
- pending/cancelled futuro;
- not_finished;
- override sobre in_progress;
- not_completed visual;
- desktop;
- mobile;
- teclado;
- sin overflow;
- sin errores de consola.

==================================================
19. VERIFICACIÓN
==================================================

Ejecutar:

- todos los tests;
- node --check;
- git diff --check.

NO commit.

En el reporte incluir:

- archivos modificados;
- ubicación de HISTORY_EDIT_WINDOW_DAYS;
- cálculo de cutoff;
- obtención de currentDate;
- reconciliación;
- not_finished;
- mutabilidad por zona temporal;
- comportamiento futuro pending/cancelled;
- procedencia de priority override;
- override de in_progress;
- cambio visual;
- tests;
- limitaciones.

No implementar features fuera de esta pasada.
