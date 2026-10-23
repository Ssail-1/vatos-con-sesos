# Funcionamiento del Gestor de hábitos

[Presentación](/README.md) · [Instalación local](/docs/instalacion-local.md) · [Modelo PostgreSQL](/modules/gestor_de_habitos/db/README.md)

Esta guía describe el flujo conectado a Flask y PostgreSQL del código de referencia
`810c153`. Los ejemplos son ficticios. El proyecto conserva funciones y pruebas de
etapas anteriores en memoria: su existencia no implica que estén disponibles en
la interfaz conectada. Las diferencias relevantes se señalan al final.

## 1. Una actividad, varias apariciones

La actividad y su ejecución en una fecha determinada tienen identidades distintas.
Por ejemplo, «Lectura» puede programarse varios días sin crear una actividad nueva
cada vez.

| Concepto | Qué representa | Ejemplo |
| --- | --- | --- |
| `PlanItem` | Identidad de una actividad o hábito | «Lectura» |
| `GenerationConfig` | Modalidad, fechas y reglas de repetición | Semanal, con fecha inicial y sin fecha final |
| `GenerationSlot` | Un horario de esa configuración | Lunes de 18:00 a 19:00; otro slot para miércoles |
| `Occurrence` | Aparición concreta en el calendario | Lectura del lunes seleccionado |
| `OccurrenceSegment` | Tramo continuo de esa aparición, con estado propio | 18:00–18:20 y 18:35–19:00 |

Una aparición puede contener huecos entre segmentos. Su rango general delimita
dónde pueden estar esos segmentos; no significa que todo ese rango esté ocupado.
Los segmentos deben tener duración positiva, permanecer dentro del rango general
y no superponerse entre sí. La aplicación exige al menos uno.

Los tipos actuales son `activity` y `habit`. Una actividad tiene uno de los subtipos
`anchor`, `periodic`, `event` o `unexpected`; el hábito implementado es `scheduled`.
No hay todavía un flujo de actividad sin subtipo. Los IDs no dependen del nombre,
del horario ni de la fecha.

### Modalidades de planificación

| Modalidad | Cómo genera apariciones | Ejemplo |
| --- | --- | --- |
| `weekly` | Cada slot corresponde a un día ISO de la semana y un horario; genera en las fechas coincidentes | Lunes 18:00–19:00 y jueves 17:00–18:00 |
| `interval_days` | Desde `startDate`, cada `intervalDays` días; se aplican los slots de cada fecha | Cada tres días, a las 09:00 y a las 17:00 |
| `manual_dates` | Cada entrada define fecha y horario explícitos; su ID corresponde a un slot | Una fecha a las 10:00 y otra a las 16:00 |

La modalidad y la clasificación de la actividad son conceptos distintos. Las
configuraciones semanales y por intervalos admiten fin definido o duración
indefinida. Los slots permiten varios horarios en un mismo día, sin solapamientos
dentro del grupo que valida la creación.

**Generar no significa guardar infinitas filas.** Al crear un PlanItem, el backend
materializa un rango: para planes indefinidos toma el mes actual y el siguiente,
respetando `startDate`; para los finitos utiliza sus fechas inicial y final, y para
las entradas manuales sus fechas explícitas. Cada aparición nueva recibe un
segmento que ocupa su rango completo y comienza en `pending`.

Las exclusiones por fecha o por slot impiden regenerar apariciones retiradas.
`stoppedFromDate` excluye esa fecha y las posteriores; `lastGenerationDate` permite
generar hasta esa fecha inclusive. Son dos límites distintos.

La creación rechaza cualquier aparición dentro del historial congelado. Además,
crear ayer no equivale a corregir una aparición ya existente: el segmento nuevo
nace `pending`, estado que la validación de ayer rechaza. La misma condición se
aplica a creaciones semanales. El registro rápido de historia pasada sigue siendo
una propuesta, no un flujo general implementado.

No se ha implementado un trabajo en segundo plano que extienda indefinidamente
las apariciones persistidas. El arranque conectado reconcilia estados y consulta
datos; navegar a otro mes no llama a un endpoint de ampliación del calendario.

Fuentes: [materializador Python](/modules/gestor_de_habitos/backend/plan_item_materializer.py),
[servicio de creación](/modules/gestor_de_habitos/backend/plan_item_creation_service.py)
y [arranque del frontend](/modules/gestor_de_habitos/js/bootstrap/planner-bootstrap.js).

## 2. Los seis estados implementados

Los segmentos y las apariciones utilizan exactamente estos **seis valores**.
Las etiquetas de la interfaz se mantienen en femenino por referirse a la aparición.

| Valor | Etiqueta de la interfaz | Interpretación del segmento | ¿Ocupa horario para el backend? |
| --- | --- | --- | --- |
| `pending` | Pendiente | Está planificado, sin cumplimiento registrado | Sí |
| `in_progress` | En progreso | Se ha marcado como iniciado | Sí |
| `completed` | Completada | Se ha registrado como terminado | Sí |
| `not_completed` | No realizada | Se ha registrado que no se realizó | No |
| `not_finished` | No terminada | Se inició o representa tiempo realizado, pero no se terminó | Sí |
| `cancelled` | Cancelada | Se conserva el registro, sin ocupar el horario | No |

No hay estados adicionales como «pausada». El sistema no es un cronómetro que
deduzca por sí solo el tiempo efectivo: `not_finished` sigue ocupando el intervalo
guardado del segmento. Marcar cancelada conserva la fila; eliminar la aparición
la retira junto con sus segmentos.

### Cambios de estado

El backend valida **el estado de destino, la fase temporal y los conflictos**.
No impone una secuencia obligatoria según el estado de origen: se puede corregir
un estado anterior si el destino cumple esas condiciones. No permite completar
un segmento antes de su hora final; exactamente a esa hora sí se admite.

La interfaz usa un botón que recorre las opciones en este orden y vuelve al inicio:

- Hoy: `pending → in_progress → completed → not_completed → not_finished → cancelled`.
- Ayer: `completed → not_completed → not_finished → cancelled`.
- Futuro: `pending ↔ cancelled`.
- Historial congelado: control deshabilitado.

El botón no garantiza que el siguiente estado sea aceptado: por ejemplo, pasar a
`completed` antes de terminar el horario o volver a un estado ocupante que choque
con otro segmento devuelve un rechazo del backend. La interfaz filtra por día;
el servidor comprueba también la hora final y los solapamientos.

### Estado agregado de la aparición

Se cambia el estado del **segmento**. El backend recalcula y persiste el resumen de
su aparición en la misma transacción; no se edita ese resumen directamente.
Si todos los segmentos tienen el mismo estado, ese estado prevalece. Para mezclas:

| Fase | Regla de agregación, en orden de prioridad |
| --- | --- |
| Futuro | Mezcla de `pending` y `cancelled` → `pending`; otros estados mixtos son inválidos |
| Hoy | Si hay `completed`, `in_progress` o `not_finished` → `in_progress`; si no, si hay `pending` → `pending`; después `not_completed`; por último `cancelled` |
| Días anteriores, reconciliados | Si hay `completed` o `not_finished` → `not_finished`; si no, si hay `not_completed` → `not_completed`; por último `cancelled` |

Por ejemplo, dos segmentos `completed` resumen `completed`. Uno `completed` y
otro `cancelled` resumen `in_progress` hoy y `not_finished` al pasar a un día
anterior. Ese resumen no significa que haya necesariamente un segmento ejecutándose
en ese instante. La agregación no reemplaza la validación temporal de cada segmento.

Fuentes: [reglas de estado y agregación](/modules/gestor_de_habitos/backend/occurrence_segment_domain.py),
[servicio de estados](/modules/gestor_de_habitos/backend/occurrence_segment_service.py)
y [etiquetas y ciclo de la interfaz](/modules/gestor_de_habitos/js/domain/occurrence-status.js).

## 3. Ventanas temporales

`HISTORY_EDIT_WINDOW_DAYS = 1`: la ventana comprende **hoy y el día calendario
anterior**, no las últimas 24 horas. Si hoy fuera día 20, ayer sería el 19 y el
historial congelado comenzaría en el 18 hacia atrás.

El backend distingue cuatro fases: `current_day`, `previous_editable_day`,
`frozen_history` y `future`. El frontend agrupa hoy y ayer en `editable`, por lo
que su clasificación general tiene tres zonas: `editable`, `frozen` y `future`.

| Acción | Historial anterior a ayer | Ayer | Hoy | Futuro |
| --- | --- | --- | --- | --- |
| Consultar | Sí | Sí | Sí | Sí, para apariciones disponibles |
| Cambiar estado de un segmento | No | Solo `completed`, `not_completed`, `not_finished`, `cancelled` | Los seis; `completed` exige hora final alcanzada | Solo `pending`, `cancelled` |
| Editar horarios o segmentos existentes | No | Sí, con estados ya reconciliados y límites válidos | Sí, con validación de estados, horarios y conflictos | Sí, manteniendo estados válidos de futuro |
| Eliminar individualmente una aparición | No | Sí, sin prohibición por estado | Sí, sin prohibición por estado | Sí, sin prohibición por estado |
| Detener planificación o eliminar todo después de la fecha elegida | No | No | Sí | Sí |
| Eliminar dentro de Apply Week | No | Exige `pending`, que no es válido tras reconciliar ayer | Solo `pending` | Solo `pending` o `cancelled` |

«Sí» significa que la ventana lo permite, no que se omitan las demás validaciones.
La última entrada manual y las referencias desde otras apariciones pueden bloquear
la eliminación individual. Los cambios recurrentes tienen además límites por modo,
semana, procedencia y cortes de planificación.

La fecha y hora autoritativas son las del servidor en calendario local. Los
campos de horario no tienen zona horaria. El navegador también usa su fecha local
para presentar opciones; no existe una zona horaria configurable por usuario.
Relojes o zonas diferentes pueden hacer que el servidor rechace una opción visible.

### Qué ocurre al cambiar de día

Al abrir el gestor se ejecuta `POST /api/planner/reconcile` antes de
`GET /api/planner-state`. Se revisan **todos los días anteriores a hoy**, incluido
ayer y también días congelados que pudieran haber quedado pendientes:

- `pending → not_completed`.
- `in_progress → not_finished`.
- Los cuatro estados restantes se conservan.
- Se recalcula el estado agregado de cada aparición.

Esta normalización persistente es idempotente: repetirla sin cambios no vuelve a
transformar los estados. No modifica estados de hoy ni de futuro. La protección
del historial limita las correcciones manuales; no impide esta reconciliación.
Tampoco implica que exista un proceso automático a medianoche mientras la página
permanece abierta: el flujo documentado es el arranque o reintento de carga.

Fuentes: [política temporal backend](/modules/gestor_de_habitos/backend/scheduling_policy.py),
[política temporal frontend](/modules/gestor_de_habitos/js/domain/temporal-integrity.js)
y [pruebas de fases, estados y agregados](/modules/gestor_de_habitos/backend/test_occurrence_segment_domain.py).

## 4. Edición de apariciones y recurrencia

| Alcance | Qué cambia | Qué conserva o restringe |
| --- | --- | --- |
| Trasladar una aparición (`translate`) | Desplaza todos sus segmentos por el mismo intervalo | Conserva fecha, duración general, IDs, estados y huecos; no cruza medianoche |
| Editar estructura (`structure`) | Ajusta el rango general y el conjunto final de segmentos | Permite agregar, recortar o quitar segmentos, sin dejar cero ni superposiciones; un segmento existente conserva su estado |
| Restablecer (`reset-segmentation`) | Reemplaza los segmentos por uno que ocupa el rango indicado | Nuevo ID de segmento, con el estado agregado anterior, sujeto a validación temporal |
| Aplicar a esta semana (`apply-week`) | Crea, modifica o elimina apariciones en la semana de la fecha ancla, de lunes a domingo | Solo `weekly`/`interval_days`; no reemplaza la regla recurrente; valida todo el lote antes de guardarlo |
| Aplicar a futuro (`apply-future`) | Sustituye la configuración recurrente y ajusta su planificación desde `futureConfig.startDate`, inclusive | Solo `weekly`/`interval_days`; no afecta fechas anteriores al corte; conserva excepciones y apariciones que no son una base pendiente reemplazable |

Ejemplo: mover la lectura del lunes de 18:00 a 19:00 mediante `translate` cambia
esa aparición. Aplicar ajustes a esa semana modifica las apariciones de esa semana.
Aplicarlos a futuro cambia la regla a partir de la fecha inicial elegida.

En Apply Future, el corte no puede caer en historial congelado. La reconciliación
del nuevo plan usa la procedencia `slot + fecha`, conserva apariciones ad hoc,
excepciones y bases no pendientes. Una aparición pendiente que aún coincide con
la regla anterior puede actualizarse o retirarse; las anteriores a la fecha
efectiva se mantienen. No equivale a borrar todo y generar desde cero.

Las apariciones con un único segmento que ocupa todo su rango admiten cambios de
duración en las operaciones recurrentes. Si la estructura está personalizada
(varios segmentos, o uno que no cubre todo el rango), un desplazamiento dentro
del mismo día conserva IDs y huecos; cambiar su duración o moverla a otra fecha
requiere resolución manual y se rechaza con un error específico.

Apply Week puede crear apariciones ad hoc, sin slot de origen, y añadir exclusiones
cuando retira o mueve una generada. No puede mover una aparición de un slot más
allá de su corte, ni crear después del corte global. Apply Future se rechaza si
algún slot ya tiene `lastGenerationDate`: todavía no existe un contrato para
reiniciar esa planificación.

Los endpoints individuales de estructura no cambian la fecha de la aparición.
El antiguo `PATCH /api/occurrences/<id>` devuelve `410`; no debe confundirse con
la edición vigente de segmentos ni con los cambios de fecha admitidos por Apply Week.

Fuentes: [estructura](/modules/gestor_de_habitos/backend/occurrence_structure_service.py),
[edición semanal](/modules/gestor_de_habitos/backend/week_mutation_service.py),
[edición futura](/modules/gestor_de_habitos/backend/future_schedule_service.py)
y [reglas recurrentes de segmentos](/modules/gestor_de_habitos/backend/recurring_segment_policy.py).

## 5. Conflictos de horario

El backend compara segmentos ocupantes de la misma fecha. Dos intervalos
adyacentes, por ejemplo 09:00–10:00 y 10:00–11:00, no chocan: se usa `[inicio, fin)`.
Los huecos entre segmentos no ocupan tiempo. Bloquean `pending`, `in_progress`,
`completed` y `not_finished`; `not_completed` y `cancelled` no bloquean.

En creación y edición estructural, un conflicto devuelve `409` sin conservar
cambios parciales. La interfaz muestra las consecuencias y pide confirmación.
Al confirmar, el backend vuelve a comprobar IDs, horarios y estados: si cambió
el registro que bloqueaba el horario, la confirmación anterior deja de servir.

Las prioridades son: actividad `unexpected` (300), actividad `event` (200) y los
demás tipos (100). Una prioridad mayor no autoriza un cambio silencioso. El motivo
es `priority_override` únicamente si la prioridad es mayor y el tiempo afectado
no está realizado; en los demás casos se utiliza `user_forced_override`.
Corregir segmentos `completed` o `not_finished` exige una confirmación adicional
de modificación de tiempo realizado. No son roles ni permisos de usuario.

Según la intersección, la resolución puede recortar un segmento, dividirlo en
fragmentos o conservarlo como cancelado si queda completamente cubierto. Por
ejemplo, introducir 10:00–11:00 en una reserva pendiente 09:00–12:00 puede dejar
dos segmentos: 09:00–10:00 y 11:00–12:00.

Un segmento `in_progress` tiene restricciones especiales: al conservar solo el
fragmento inicial pasa a `not_finished`; si solo queda el final puede conservar
`in_progress` hoy. Dividirlo internamente o cubrirlo por completo se rechaza porque
el contrato no define una resolución única. No se corrige historial congelado.

Cambiar un estado, Apply Week y Apply Future detectan y **rechazan** los conflictos;
no usan este flujo para modificar automáticamente los segmentos que bloquean.
Los solapamientos internos inválidos también se rechazan.

Fuentes: [dominio de conflictos](/modules/gestor_de_habitos/backend/segment_conflict_domain.py),
[resolución transaccional](/modules/gestor_de_habitos/backend/segment_conflict_service.py)
y [contrato HTTP](/modules/gestor_de_habitos/docs/segment_conflict_api.md).

## 6. Eliminar o detener planificación

Las acciones se anclan a una aparición seleccionada, no al nombre ni al segmento
visible. Para los tres cortes posteriores se exige que su fecha `D` sea hoy o
futura; `D` y los días anteriores se conservan.

| Acción | Resultado |
| --- | --- |
| Eliminar solo esta aparición | Retira esa aparición y sus segmentos. Si procede de un slot recurrente, guarda una exclusión `slot + fecha`; si procede de una entrada manual, retira también ese slot |
| Detener este horario después de D | Fija un corte inclusivo en el slot y retira solo las apariciones posteriores procedentes de ese slot |
| Detener toda la planificación recurrente después de D | Corta los slots y la configuración; retira las apariciones posteriores con procedencia de slot y conserva las ad hoc sin slot |
| Eliminar todas las apariciones después de D | Corta la planificación y retira todas las apariciones posteriores del PlanItem, incluidas las ad hoc |

La eliminación individual admite cualquier estado dentro de la ventana editable
y en futuro, siempre que el grafo sea consistente. Rechaza borrar la última entrada
de un plan `manual_dates`, y también una aparición que sea fuente de conflicto
referenciada por otras. Las acciones de corte rechazan referencias externas al
conjunto que eliminarían; referencias internas al conjunto pueden retirarse juntas.

Ejemplo: si un plan tiene tres slots y se detiene el segundo después de D, los otros
dos continúan. Recargar la página no debe regenerar las apariciones de ese segundo
slot posteriores a D. La interfaz evita ofrecer detener una recurrencia que ya no
puede generar después de la fecha elegida.

Todas estas acciones conservan el PlanItem. No existe aquí una operación para
eliminar completamente su identidad ni para reanudar una planificación detenida.
Los comandos y las escrituras de sus restricciones se realizan en una transacción;
los errores no deben dejar cortes guardados sin la limpieza correspondiente.

Fuentes: [eliminación individual](/modules/gestor_de_habitos/backend/occurrence_mutation_service.py),
[terminación persistente](/modules/gestor_de_habitos/backend/planning_termination_service.py),
[opciones de la interfaz](/modules/gestor_de_habitos/js/domain/deletion-policy.js)
y [contrato de terminación](/modules/gestor_de_habitos/docs/planning_termination_api.md).

## 7. Fuentes, comprobaciones y diferencias históricas

Se contrastaron las reglas con código y pruebas. Las comprobaciones automáticas
de esta documentación se limitan a unidades sin base de datos y pruebas frontend
en Node; no sustituyen una prueba de interfaz o de persistencia en PostgreSQL.

| Tema | Pruebas de referencia |
| --- | --- |
| Seis estados, cuatro fases, agregados y hora final | [Dominio de segmentos](/modules/gestor_de_habitos/backend/test_occurrence_segment_domain.py) |
| Ciclo de estados mostrado al usuario | [Segmentos en frontend](/modules/gestor_de_habitos/tests/occurrence-segments.test.mjs) |
| Límites estructurales y cambios recurrentes | [Estructura](/modules/gestor_de_habitos/backend/test_occurrence_structure_domain.py) y [política recurrente](/modules/gestor_de_habitos/backend/test_recurring_segment_policy.py) |
| Eliminación individual y protección de referencias | [Pruebas con repositorios simulados](/modules/gestor_de_habitos/backend/test_occurrence_mutation.py) |
| Cortes y no regeneración | [Frontend](/modules/gestor_de_habitos/tests/planning-termination.test.mjs) y [pruebas de integración, no ejecutadas aquí](/modules/gestor_de_habitos/backend/test_planning_termination_integration.py) |

Diferencias que requieren tener presente la versión de la documentación:

1. [ELIMINACION.md histórico](/docs/codex/gestor_de_habitos/archive/frontend_mvp_04/MVP_04_1/ELIMINACION.md)
   limita el borrado editable a `pending`. El DELETE individual actual permite
   corregir otros estados; Apply Week/Future conservan políticas más restrictivas.
2. El [contrato de conflictos](/modules/gestor_de_habitos/docs/segment_conflict_api.md)
   deja la UX definitiva fuera de aquella fase. Actualmente existe un
   [diálogo de confirmación conectado](/modules/gestor_de_habitos/js/views/segment-conflict-dialog.js).
3. El [contrato de terminación](/modules/gestor_de_habitos/docs/planning_termination_api.md)
   conserva una nota de rollout pendiente; el [registro de la base de datos](/modules/gestor_de_habitos/db/README.md)
   lo declara completado. Esta guía documenta el código y esquema esperado, no
   confirma el estado actual de una base real.
4. El helper frontend `blocksSchedule` omite `not_finished`, mientras el backend
   segmentario lo incluye. Los helpers y pruebas heredados en memoria no deben
   usarse para deducir los bloqueos efectivos del flujo conectado. Esa diferencia
   queda pendiente de revisión; no se cambió código para ocultarla.
5. Hay pruebas de la función heredada `patch_occurrence`, pero su endpoint está
   retirado en [app.py](/modules/gestor_de_habitos/backend/app.py). Que una función
   interna siga probándose no significa que exista una acción HTTP disponible.

La guía conserva estas distinciones sin modificar contratos históricos ni ampliar
las funcionalidades implementadas.
