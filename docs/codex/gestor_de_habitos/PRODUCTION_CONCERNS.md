# Production Concerns

Aspectos deliberadamente no implementados que deben reconsiderarse al
evolucionar la arquitectura.

## Timezone

- `currentDate` deberá calcularse usando la timezone efectiva del usuario.
- Evitar utilizar UTC directamente como fecha calendario del usuario.
- Futuro modelo conceptual: `user.timezone`.
- Considerar cambio de timezone y viajes.

## Reconciliación temporal

La reconciliación actual ocurre en el cliente/store.

Cuando exista backend evaluar:
- reconciliación autoritativa en servidor;
- aplicación abierta durante cambio de día;
- múltiples dispositivos;
- jobs programados si fueran necesarios.

## Concurrencia

Overrides, reconciliación histórica y operaciones destructivas deberán
ejecutarse mediante transacciones atómicas al migrar a PostgreSQL.

## Estado

No implementar estos puntos hasta que un futuro CURRENT_TASK los incorpore
explícitamente.