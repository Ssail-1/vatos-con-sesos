# CURRENT TASK

## MVP 05.6.2 — PostgreSQL migration 003 + relational multi-slot model

### Documento normativo

La especificación global de multi-slot está en:

`docs/codex/gestor_de_habitos/planeacion/MVP_05_6/MULTI_SLOT_SCHEDULING.md`

Este `CURRENT_TASK.md` define únicamente la fase activa:

```text
MVP 05.6.2
PostgreSQL migration 003 + relational multi-slot model
```

MVP 05.6.1 ya dejó implementado el contrato multi-slot local en
frontend/domain.

En esta fase se adapta exclusivamente PostgreSQL.

---

# 1. Objetivo

Crear:

```text
003_multi_slot_scheduling.sql
```

para transformar el esquema persistente MVP 05.5 al modelo relacional
multi-slot definido para MVP 05.6.

La migración debe:

- preservar datos existentes;
- introducir `generation_slots`;
- introducir detalles de slot por modo;
- introducir exclusiones por slot;
- relacionar opcionalmente occurrences con su slot de origen;
- retirar la estructura temporal antigua que ya no será fuente de verdad;
- conservar las occurrences históricas;
- ser completamente transaccional.

---

# 2. Alcance de esta fase

Modificar únicamente lo necesario dentro de:

```text
modules/gestor_de_habitos/db/
```

Principalmente:

```text
migrations/003_multi_slot_scheduling.sql
```

Puede actualizarse documentación específica de DB si es necesario para
reflejar el nuevo esquema.

NO modificar frontend.

NO modificar backend Flask/Python.

NO modificar PostgreSQL `vcs_dev`.

---

# 3. Migraciones anteriores son inmutables

NO modificar:

```text
001_initial_schema.sql
002_fix_occurrence_status_context.sql
```

La historia debe permanecer:

```text
001
→ esquema inicial

002
→ corrección de status context

003
→ evolución multi-slot
```

Cualquier cambio necesario debe estar exclusivamente en `003`.

---

# 4. Modelo relacional objetivo

El núcleo debe evolucionar a:

```text
plan_items
    │
    ├──────────────< occurrences
    │                    │
    │                    └── source_generation_slot_id
    │
    └── generation_configs
             │
             ├────< generation_slots
             │          │
             │          ├── generation_slot_weekdays
             │          ├── generation_slot_dates
             │          └── generation_slot_excluded_dates
             │
             └────< generation_excluded_dates
```

---

# 5. generation_slots

Crear una tabla conceptual equivalente a:

```text
generation_slots

id              UUID PRIMARY KEY
plan_item_id    UUID NOT NULL
start_time      TIME NOT NULL
end_time        TIME NOT NULL
```

Debe relacionarse con la configuración propietaria mediante:

```text
plan_item_id
→ generation_configs(plan_item_id)
```

Usar:

```text
ON DELETE CASCADE
```

porque un slot no puede existir sin la configuración de su PlanItem.

Debe existir:

```text
CHECK (start_time < end_time)
```

NO crear:

```text
UNIQUE(plan_item_id, start_time, end_time)
```

porque el mismo intervalo puede existir en diferentes weekdays o fechas.

---

# 6. generation_slot_weekdays

Crear:

```text
generation_slot_weekdays
```

con estructura conceptual:

```text
slot_id         UUID PRIMARY KEY
iso_weekday     SMALLINT NOT NULL
```

FK:

```text
slot_id
→ generation_slots(id)
ON DELETE CASCADE
```

Constraint:

```text
iso_weekday BETWEEN 1 AND 7
```

Cada slot weekly tiene exactamente un weekday.

Las invariantes entre `mode` y presencia de esta fila se validarán
principalmente en dominio/backend, no mediante triggers en esta fase.

---

# 7. generation_slot_dates

Crear:

```text
generation_slot_dates
```

con estructura conceptual:

```text
slot_id       UUID PRIMARY KEY
entry_date    DATE NOT NULL
```

FK:

```text
slot_id
→ generation_slots(id)
ON DELETE CASCADE
```

Cada slot `manual_dates` tiene exactamente una fecha explícita.

---

# 8. generation_slot_excluded_dates

Crear:

```text
generation_slot_excluded_dates
```

con:

```text
slot_id          UUID NOT NULL
excluded_date    DATE NOT NULL
```

PK compuesta:

```text
(slot_id, excluded_date)
```

FK:

```text
slot_id
→ generation_slots(id)
ON DELETE CASCADE
```

Esta tabla representa:

> excluir únicamente este slot en esta fecha.

No sustituye:

```text
generation_excluded_dates
```

La tabla existente continúa significando:

> excluir TODO el PlanItem en esta fecha.

---

# 9. occurrences.source_generation_slot_id

Agregar a:

```text
occurrences
```

la columna nullable:

```text
source_generation_slot_id UUID NULL
```

FK:

```text
source_generation_slot_id
→ generation_slots(id)
ON DELETE SET NULL
```

La relación representa procedencia.

NO dependencia de la occurrence hacia la configuración.

Una occurrence continúa conservando de forma independiente:

```text
occurrence_date
start_time
end_time
status
```

---

# 10. Idempotencia persistente

La invariante del dominio es:

```text
un GenerationSlot
→ como máximo una occurrence por fecha
```

Implementar protección relacional mediante un índice único parcial
equivalente a:

```sql
UNIQUE (
    source_generation_slot_id,
    occurrence_date
)
WHERE source_generation_slot_id IS NOT NULL
```

NO introducir:

```text
UNIQUE(plan_item_id, occurrence_date)
```

porque múltiples slots del mismo PlanItem pueden producir múltiples
occurrences válidas el mismo día.

Antes de crear el índice, la migración debe garantizar que el backfill
no produzca duplicados incompatibles.

---

# 11. generation_configs en el nuevo modelo

`generation_configs` conserva los datos estructurales de generación:

```text
plan_item_id
mode
start_date
end_date
indefinite
interval_days
stopped_from_date
```

El nuevo modelo deja de utilizar como fuente persistente de verdad:

```text
default_start_time
default_end_time
```

Después de migrar correctamente los datos, estas columnas deben
eliminarse.

Las constraints existentes que dependan de ellas deben revisarse y
reemplazarse.

NO adivinar nombres de constraints.

Inspeccionar `001_initial_schema.sql` y operar sobre los nombres reales.

---

# 12. Reemplazar generation_weekdays

La estructura antigua:

```text
generation_weekdays
```

contiene actualmente:

```text
plan_item_id
iso_weekday
override_start_time
override_end_time
```

Debe utilizarse como fuente para migrar datos weekly.

Después de migrar correctamente:

```text
generation_weekdays
```

deja de formar parte del esquema objetivo y debe eliminarse.

Su reemplazo es:

```text
generation_slots
+
generation_slot_weekdays
```

---

# 13. Reemplazar generation_date_entries

La estructura antigua:

```text
generation_date_entries
```

debe utilizarse como fuente para migrar `manual_dates`.

Después de migrar correctamente deja de formar parte del esquema objetivo.

Su reemplazo es:

```text
generation_slots
+
generation_slot_dates
```

---

# 14. Migración de datos weekly existentes

Para cada:

```text
generation_weekdays
```

existente debe crearse un `GenerationSlot`.

El horario efectivo se obtiene así:

```text
si existe override válido
→ override_start_time / override_end_time

si no existe override
→ generation_configs.default_start_time /
  generation_configs.default_end_time
```

Ejemplo legado:

```text
default:
08:00–11:00

lunes:
sin override

martes:
09:00–12:00 override
```

debe convertirse a:

```text
Slot A
lunes
08:00–11:00

Slot B
martes
09:00–12:00
```

Cada slot weekly migrado recibe:

```text
generation_slots
+
generation_slot_weekdays
```

---

# 15. IDs para weekly legado

Los registros weekly antiguos no tienen `GenerationSlot.id`.

Por tanto, la migración 003 puede generar UUIDs nuevos para esos datos
legados.

Esto NO contradice la regla futura de que:

```text
frontend genera GenerationSlot.id
```

porque estos son datos creados ANTES de existir la entidad GenerationSlot.

Para datos nuevos después de MVP 05.6.3:

```text
frontend UUID
→ backend preserva
→ PostgreSQL persiste
```

Para datos legacy migrados por 003:

```text
migration genera UUID una sola vez
```

No derivar el UUID de horario o weekday.

Usar una función UUID adecuada disponible en PostgreSQL 16.

No introducir una extensión innecesaria si PostgreSQL ya proporciona la
función requerida.

---

# 16. Migración de interval_days existentes

Cada configuración legacy:

```text
mode = interval_days
```

posee actualmente un solo:

```text
default_start_time
default_end_time
```

Debe convertirse en exactamente un:

```text
GenerationSlot
```

con ese intervalo.

No necesita:

```text
generation_slot_weekdays
generation_slot_dates
```

porque la fecha se deriva mediante:

```text
start_date + interval_days
```

---

# 17. IDs para interval_days legado

Igual que weekly:

```text
interval_days legacy
```

no posee Slot ID.

La migración genera un UUID nuevo para su GenerationSlot.

Ese UUID se convierte desde entonces en su identidad persistente.

---

# 18. Migración de manual_dates existentes

Cada fila existente de:

```text
generation_date_entries
```

representa conceptualmente un slot explícito.

Debe convertirse a:

```text
generation_slots
+
generation_slot_dates
```

La fila legacy ya posee:

```text
id UUID
```

Preferir reutilizar ese mismo UUID como:

```text
generation_slots.id
```

para conservar identidad cuando no exista una razón técnica real que lo
impida.

Mapeo:

```text
generation_date_entries.id
→ generation_slots.id

generation_date_entries.plan_item_id
→ generation_slots.plan_item_id

start_time/end_time
→ generation_slots

entry_date
→ generation_slot_dates
```

---

# 19. generation_excluded_dates

La tabla existente:

```text
generation_excluded_dates
```

se conserva.

Su semántica sigue siendo:

```text
PlanItem completo
+
fecha
→ no generar ninguna occurrence
```

No migrar sus filas a exclusiones por slot.

No alterar su significado.

---

# 20. Backfill de occurrences

Después de crear los GenerationSlots legacy debe intentarse completar:

```text
occurrences.source_generation_slot_id
```

solo cuando la procedencia pueda determinarse de manera segura.

Principio:

```text
si es inequívoco
→ asignar slot ID

si existe cualquier ambigüedad
→ NULL
```

NO inventar procedencia.

---

# 21. Backfill weekly

El modelo legacy weekly permitía como máximo un horario efectivo por
weekday para cada PlanItem.

Por tanto, una occurrence weekly puede asociarse a su slot cuando la
relación legacy lo haga inequívoco.

Considerar:

```text
plan_item_id
weekday de occurrence_date
mode = weekly
```

y cualquier otra condición necesaria para evitar falsos positivos.

Una occurrence editada individualmente puede tener horario distinto del
slot original.

No exigir igualdad de horario si la procedencia sigue siendo
inequívocamente determinable por la estructura legacy.

Si no puede demostrarse con seguridad:

```text
NULL
```

---

# 22. Backfill interval_days

El modelo legacy `interval_days` posee exactamente un horario generador
por PlanItem.

Si la occurrence pertenece inequívocamente a ese PlanItem/configuración:

```text
source_generation_slot_id
→ slot interval_days migrado
```

No inferir relaciones de otro modo.

---

# 23. Backfill manual_dates

`manual_dates` puede contener más de una entry en una misma fecha.

Por tanto, debe utilizarse una estrategia conservadora.

Puede asociarse una occurrence cuando exista una única entry candidata
inequívoca.

Puede utilizarse:

```text
plan_item_id
entry_date
start/end cuando ayuden a desambiguar
```

Si una occurrence editada o varios candidatos hacen imposible determinar
qué entry la originó:

```text
source_generation_slot_id = NULL
```

Eso es correcto.

La historia continúa siendo válida aunque se pierda la procedencia.

---

# 24. Occurrences ad-hoc / no asociables

No todas las occurrences legacy tienen que recibir:

```text
source_generation_slot_id
```

`NULL` es un estado válido.

La migración prioriza:

```text
integridad
```

sobre:

```text
adivinar procedencia
```

---

# 25. Constraints de generation_configs

Inspeccionar las constraints reales definidas por 001.

Reemplazar las que dependan del modelo antiguo.

El esquema nuevo debe validar al menos:

## weekly

```text
start_date IS NOT NULL

interval_days IS NULL

rango finito válido
OR
indefinite = true
```

NO exigir ya:

```text
default_start_time
default_end_time
```

## interval_days

```text
start_date IS NOT NULL
interval_days > 0

rango finito válido
OR
indefinite = true
```

NO exigir default times.

## manual_dates

Debe conservar la semántica estructural apropiada:

```text
start_date IS NULL
end_date IS NULL
indefinite = false
interval_days IS NULL
```

Los horarios/fechas viven ahora en slots y slot dates.

---

# 26. Invariantes multi-tabla

No introducir triggers para exigir en PostgreSQL cosas como:

```text
weekly debe tener >= 1 slot
weekly slot debe tener weekday
manual slot debe tener date
interval slot no debe tener weekday/date
```

Estas invariantes requieren varias tablas y serán protegidas por
backend/domain en MVP 05.6.3.

PostgreSQL debe proteger correctamente:

```text
tipos
FKs
PKs
CHECKs locales
unicidad local
```

sin sobrecomplicar el esquema.

---

# 27. Eliminación de estructura legacy

Solo DESPUÉS de completar correctamente los backfills necesarios se puede
retirar:

```text
generation_weekdays
generation_date_entries
generation_configs.default_start_time
generation_configs.default_end_time
```

Ordenar las operaciones para no destruir la información antes de usarla.

La migración completa debe estar dentro de una transacción.

Ante cualquier error:

```text
ROLLBACK
```

y el esquema legacy debe permanecer íntegro.

---

# 28. Orden de migración

El orden conceptual debe ser seguro.

Algo equivalente a:

```text
BEGIN

1. crear tablas multi-slot
2. agregar source_generation_slot_id
3. crear GenerationSlots desde legacy
4. crear weekday/date details
5. backfill sourceGenerationSlotId donde sea seguro
6. adaptar constraints generation_configs
7. retirar tablas/columnas legacy
8. crear FKs/índices/constraints finales necesarios
9. validar estado final

COMMIT
```

Codex puede ajustar el orden SQL exacto cuando sea necesario para respetar
dependencias.

No alterar la semántica para seguir literalmente esta numeración.

---

# 29. Índices

Agregar únicamente índices justificados por:

```text
FK lookup
materialización
idempotencia
```

El índice único parcial:

```text
(source_generation_slot_id, occurrence_date)
WHERE source_generation_slot_id IS NOT NULL
```

sí forma parte de esta fase.

No crear índices especulativos sin una consulta o integridad concreta que
los justifique.

---

# 30. No tocar vcs_dev

Codex NO debe ejecutar 003 contra:

```text
vcs_dev
```

No utilizar las credenciales reales del usuario.

No borrar, truncar ni modificar sus datos.

La aplicación manual sobre `vcs_dev` se hará después de revisar el
reporte.

---

# 31. Datos reales de vcs_dev

Actualmente `vcs_dev` puede contener datos creados durante MVP 05.5.

Eso es deliberado.

NO asumir que la base real está vacía.

La migración debe estar preparada para transformar datos legacy válidos.

No modificar esos datos durante desarrollo de 05.6.2.

---

# 32. Pruebas con PostgreSQL aislado

Cuando el entorno lo permita, utilizar PostgreSQL 16 efímero/aislado.

NO utilizar `vcs_dev`.

Probar al menos dos escenarios:

```text
A. Base vacía:
001
002
003

B. Base legacy con datos:
001
002
insert fixtures legacy
003
```

---

# 33. Fixture legacy weekly

Crear datos de prueba que incluyan:

```text
weekly
default time
varios weekdays
weekday sin override
weekday con override
occurrences relacionadas
```

Después de 003 verificar:

```text
un slot por weekday
horario efectivo correcto
slot weekday correcto
plan_item intacto
occurrences intactas
source slot backfilled cuando sea seguro
```

---

# 34. Fixture legacy interval_days

Probar:

```text
interval_days
default time
interval_days > 0
occurrences
```

Después:

```text
exactamente un GenerationSlot
hora correcta
sin weekday/date detail
occurrences preservadas
source slot correcto cuando sea inequívoco
```

---

# 35. Fixture legacy manual_dates

Probar:

```text
una fecha
varias fechas
más de una entry en la misma fecha
occurrences
```

Verificar:

```text
cada old entry → GenerationSlot
UUID de old entry reutilizado
cada slot → generation_slot_dates
fechas/horas intactas
```

También probar una situación ambigua donde:

```text
source_generation_slot_id
```

deba quedar `NULL`.

---

# 36. Preservación de historia

Después de 003 verificar explícitamente que ninguna occurrence pierde:

```text
id
plan_item_id
occurrence_date
start_time
end_time
status
status_reason
source_occurrence_id
```

La única columna nueva es:

```text
source_generation_slot_id
```

y puede ser NULL.

---

# 37. ON DELETE SET NULL

Probar que eliminar un GenerationSlot en el esquema migrado:

```text
NO elimina occurrence histórica
```

Debe resultar:

```text
occurrence permanece
source_generation_slot_id → NULL
```

---

# 38. Exclusión por slot

Probar integridad de:

```text
generation_slot_excluded_dates
```

incluyendo:

```text
PK compuesta
FK
ON DELETE CASCADE
```

Todavía no es necesario poblarla desde datos legacy porque no existía un
equivalente anterior.

---

# 39. Idempotencia de occurrence

Probar el índice único parcial.

Debe rechazarse:

```text
mismo source_generation_slot_id
+
misma occurrence_date
```

dos veces.

Debe permitirse:

```text
slot A + 2026-09-15
slot B + 2026-09-15
```

para el mismo PlanItem.

Debe permitirse también más de una occurrence con:

```text
source_generation_slot_id = NULL
```

cuando las demás reglas lo permitan.

---

# 40. Esquema final esperado

Después de 003 deben existir al menos:

```text
plan_items
generation_configs
generation_slots
generation_slot_weekdays
generation_slot_dates
generation_excluded_dates
generation_slot_excluded_dates
occurrences
```

No deben continuar como fuente activa:

```text
generation_weekdays
generation_date_entries
```

Ni deben continuar las columnas:

```text
generation_configs.default_start_time
generation_configs.default_end_time
```

---

# 41. Backend deliberadamente incompatible

Al terminar MVP 05.6.2:

```text
Frontend
→ multi-slot

PostgreSQL
→ multi-slot

Backend Python
→ todavía MVP 05.5
```

Esta incompatibilidad temporal es ESPERADA.

NO modificar backend para resolverla.

MVP 05.6.3 se encargará de:

```text
GET planner-state multi-slot
POST plan-items multi-slot
Python materializer
JS/Python parity
```

---

# 42. Frontend no se modifica

MVP 05.6.1 ya está cerrado.

NO modificar:

```text
index.html
CSS
JavaScript
frontend tests
```

para adaptar esta migración.

Si se detecta una incompatibilidad conceptual real con el contrato
frontend, detenerse y reportarla antes de cambiar la especificación.

---

# 43. No implementar todavía

Fuera de alcance:

```text
Flask multi-slot
Python materializer multi-slot
POST multi-slot
GET planner-state multi-slot
PATCH
DELETE persistente
Apply Future persistente multi-slot
slot editing API
auth
multiusuario
Supabase
deployment
```

---

# 44. Validaciones requeridas

Además de pruebas PostgreSQL, ejecutar:

```text
git diff --check
```

Si existen herramientas SQL locales apropiadas, validar sintaxis sin
tocar `vcs_dev`.

No modificar dependencias del proyecto únicamente para ejecutar esta
fase.

---

# 45. CURRENT_TASK y documentación

No reescribir la especificación global por iniciativa propia.

Si durante implementación aparece un defecto real en:

```text
MULTI_SLOT_SCHEDULING.md
```

detenerse y reportarlo.

No redefinir silenciosamente la arquitectura mediante SQL.

---

# 46. Git

Codex NO debe:

```text
commit
push
merge
cambiar de rama
```

El usuario controla Git.

---

# 47. Criterios de aceptación

MVP 05.6.2 se considera completo cuando:

```text
001 + 002 + 003
```

pueden construir desde cero el esquema multi-slot.

Además:

```text
una DB MVP 05.5 válida
+
003
```

debe migrar al nuevo modelo sin perder datos.

Debe cumplirse:

```text
weekly legacy
→ slots por weekday

interval_days legacy
→ slot

manual_dates legacy
→ slots con fecha

occurrences
→ preservadas

source_generation_slot_id
→ backfilled solo cuando sea seguro

legacy time columns
→ retiradas

legacy generation tables
→ retiradas

global exclusions
→ preservadas

slot exclusions
→ disponibles

history
→ preservada
```

---

# 48. Reporte requerido

Al terminar, reportar:

1. archivos creados/modificados;
2. estructura exacta final de `generation_slots`;
3. estructura exacta de `generation_slot_weekdays`;
4. estructura exacta de `generation_slot_dates`;
5. estructura exacta de `generation_slot_excluded_dates`;
6. cambio exacto en `occurrences`;
7. índice de idempotencia creado;
8. constraints modificadas en `generation_configs`;
9. cómo se migran weekly legacy;
10. cómo se migran interval_days legacy;
11. cómo se migran manual_dates legacy;
12. política exacta de UUID durante migración;
13. estrategia exacta de backfill de `source_generation_slot_id`;
14. situaciones donde queda NULL;
15. qué objetos legacy se eliminan;
16. pruebas ejecutadas;
17. resultados de migración desde DB vacía;
18. resultados de migración con fixtures legacy;
19. evidencia de preservación de occurrences;
20. cualquier limitación o riesgo encontrado.

Confirmar explícitamente:

```text
vcs_dev no fue modificado
backend no fue modificado
frontend no fue modificado
no se hizo commit/push/merge
```