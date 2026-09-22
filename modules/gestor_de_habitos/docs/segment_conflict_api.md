# Contrato provisional de conflictos segmentarios (05.7.5.10)

Se aplica a `POST /api/plan-items`, `POST /api/occurrences/<id>/translate`,
`PUT /api/occurrences/<id>/structure` y
`POST /api/occurrences/<id>/reset-segmentation`. La primera solicitud conserva
el payload normal y, si encuentra blockers, devuelve HTTP 409 sin escrituras:

```json
{
  "status": "error",
  "code": "segment_conflict_resolution_required",
  "message": "La operación requiere resolver conflictos de horario.",
  "conflicts": [{
    "blocker": {
      "occurrenceId": "<uuid>",
      "segmentId": "<uuid>",
      "planItemId": "<uuid>",
      "date": "2026-09-21",
      "startTime": "13:00",
      "endTime": "15:00",
      "status": "pending"
    },
    "requiredAuthorization": "priority_override",
    "resolutionKind": "split_segment",
    "requiresRealizedTimeConfirmation": false
  }]
}
```

El cliente repite **la misma operación** y añade:

```json
{
  "conflictResolution": {
    "confirmations": [{
      "blocker": {
        "occurrenceId": "<uuid>",
        "segmentId": "<uuid>",
        "startTime": "13:00",
        "endTime": "15:00",
        "status": "pending"
      },
      "confirmed": true
    }]
  }
}
```

Para `completed` y `not_finished`, cada entrada correspondiente exige además
`"confirmRealizedTimeCorrection": true`. Esa confirmación fuerte se liga al
mismo snapshot; no autoriza un segment que cambió de ID, horario o status.

El backend recalcula prioridad y blockers dentro de una transacción
`SERIALIZABLE`; `priority_override` se asigna únicamente a source de mayor
prioridad contra tiempo no realizado. Igual/menor prioridad y toda corrección
de tiempo realizado usan `user_forced_override`. Ninguno permite modificación
sin confirmación. Un blocker nuevo devuelve otro 409 con el conjunto actual;
un snapshot cambiado o desaparecido devuelve `conflict_resolution_stale`.

Los resultados `resolutionKind` actuales son `trim_segment`, `split_segment`,
`cancel_segment`, `interrupt_in_progress` y `undefined_in_progress`. La división
interna o cobertura total de `in_progress` permanece rechazada con
`segment_resolution_undefined`: la norma no fija un único status para sus
fragments. No hay resolución implícita ni escritura parcial para ese caso.

`PATCH /api/occurrence-segments/<id>/status`, Apply Week y Apply Future
continúan detectando y rechazando conflictos sin modificar blockers. La UX
definitiva de confirmación queda fuera de esta fase.
