

# 3. No todo necesita convertirse en herencia

Tu sospecha es correcta:

> `AnchorActivity`, `PeriodicActivity` y `UnforeseenActivity` parecen más reglas de negocio que clases con atributos propios.

Yo **no crearía una tabla o subclase para cada una**.

Usaría una sola definición con clasificaciones:

```text
kind
├── ACTIVITY
└── HABIT
```

```text
activity_type
├── ANCHOR
├── PERIODIC
└── UNFORESEEN
```

```text
measurement_type
├── CHECK
├── TIME
└── QUANTITY
```

Eso permite combinaciones claras.

| Ejemplo             | kind     | activity_type | measurement_type |
| ------------------- | -------- | ------------- | ---------------- |
| Trabajo             | ACTIVITY | ANCHOR        | TIME             |
| Cortarse el cabello | ACTIVITY | PERIODIC      | TIME             |
| Ponchadura          | ACTIVITY | UNFORESEEN    | TIME             |
| Despertarse         | HABIT    | —             | TIME             |
| No fumar            | HABIT    | —             | QUANTITY         |
| Leer diariamente    | HABIT    | —             | CHECK o QUANTITY |

Para el hábito “no fumar”:

```text
unit = cigarrillos
target_quantity = 0
```

Pero la cantidad real fumada pertenece al registro del día:

```text
DailyOccurrence.actual_quantity = 3
```

No a la definición general.

---
