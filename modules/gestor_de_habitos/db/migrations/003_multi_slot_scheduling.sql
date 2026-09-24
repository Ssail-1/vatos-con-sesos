BEGIN;

-- Evita descartar silenciosamente detalles legacy asociados a un modo
-- incompatible. Ante datos fuera del contrato MVP 05.5, toda la migración
-- falla y la transacción conserva intacto el esquema anterior.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM public.generation_weekdays AS weekdays
        JOIN public.generation_configs AS configs
            ON configs.plan_item_id = weekdays.plan_item_id
        WHERE configs.mode <> 'weekly'
    ) THEN
        RAISE EXCEPTION
            '003 cannot migrate generation_weekdays owned by a non-weekly config';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.generation_date_entries AS entries
        JOIN public.generation_configs AS configs
            ON configs.plan_item_id = entries.plan_item_id
        WHERE configs.mode <> 'manual_dates'
    ) THEN
        RAISE EXCEPTION
            '003 cannot migrate generation_date_entries owned by a non-manual config';
    END IF;
END
$$;

-- ============================================================
-- GENERATION SLOTS
-- Horarios explícitos que pertenecen a una configuración.
-- ============================================================

CREATE TABLE public.generation_slots (
    id UUID NOT NULL,
    plan_item_id UUID NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,

    CONSTRAINT generation_slots_pkey
        PRIMARY KEY (id),

    CONSTRAINT chk_generation_slot_time_range
        CHECK (start_time < end_time),

    CONSTRAINT fk_generation_slots_generation_configs
        FOREIGN KEY (plan_item_id)
        REFERENCES public.generation_configs(plan_item_id)
        ON DELETE CASCADE
);

CREATE INDEX idx_generation_slots_plan_item_id
    ON public.generation_slots(plan_item_id);


-- ============================================================
-- SLOT DETAILS
-- Weekly usa weekday; manual_dates usa entry_date.
-- Interval_days no necesita una fila de detalle.
-- ============================================================

CREATE TABLE public.generation_slot_weekdays (
    slot_id UUID NOT NULL,
    iso_weekday SMALLINT NOT NULL,

    CONSTRAINT generation_slot_weekdays_pkey
        PRIMARY KEY (slot_id),

    CONSTRAINT chk_generation_slot_iso_weekday
        CHECK (iso_weekday BETWEEN 1 AND 7),

    CONSTRAINT fk_generation_slot_weekdays_slot
        FOREIGN KEY (slot_id)
        REFERENCES public.generation_slots(id)
        ON DELETE CASCADE
);

CREATE TABLE public.generation_slot_dates (
    slot_id UUID NOT NULL,
    entry_date DATE NOT NULL,

    CONSTRAINT generation_slot_dates_pkey
        PRIMARY KEY (slot_id),

    CONSTRAINT fk_generation_slot_dates_slot
        FOREIGN KEY (slot_id)
        REFERENCES public.generation_slots(id)
        ON DELETE CASCADE
);

CREATE TABLE public.generation_slot_excluded_dates (
    slot_id UUID NOT NULL,
    excluded_date DATE NOT NULL,

    CONSTRAINT generation_slot_excluded_dates_pkey
        PRIMARY KEY (slot_id, excluded_date),

    CONSTRAINT fk_generation_slot_excluded_dates_slot
        FOREIGN KEY (slot_id)
        REFERENCES public.generation_slots(id)
        ON DELETE CASCADE
);


-- ============================================================
-- OCCURRENCE PROVENANCE
-- Nullable porque la historia no depende del slot y porque no toda
-- occurrence legacy tiene una procedencia demostrable.
-- ============================================================

ALTER TABLE public.occurrences
    ADD COLUMN source_generation_slot_id UUID;

ALTER TABLE public.occurrences
    ADD CONSTRAINT fk_occurrence_source_generation_slot
    FOREIGN KEY (source_generation_slot_id)
    REFERENCES public.generation_slots(id)
    ON DELETE SET NULL;


-- ============================================================
-- LEGACY SLOT MAPPINGS
-- Las tablas temporales conservan la relación exacta entre cada fila
-- legacy y su UUID nuevo mientras se realiza el backfill.
-- ============================================================

CREATE TEMPORARY TABLE migration_003_weekly_slots (
    plan_item_id UUID NOT NULL,
    iso_weekday SMALLINT NOT NULL,
    slot_id UUID NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,

    PRIMARY KEY (plan_item_id, iso_weekday),
    UNIQUE (slot_id)
) ON COMMIT DROP;

INSERT INTO migration_003_weekly_slots (
    plan_item_id,
    iso_weekday,
    slot_id,
    start_time,
    end_time
)
SELECT
    weekdays.plan_item_id,
    weekdays.iso_weekday,
    gen_random_uuid(),
    COALESCE(
        weekdays.override_start_time,
        configs.default_start_time
    ),
    COALESCE(
        weekdays.override_end_time,
        configs.default_end_time
    )
FROM public.generation_weekdays AS weekdays
JOIN public.generation_configs AS configs
    ON configs.plan_item_id = weekdays.plan_item_id
WHERE configs.mode = 'weekly';

INSERT INTO public.generation_slots (
    id,
    plan_item_id,
    start_time,
    end_time
)
SELECT
    slot_id,
    plan_item_id,
    start_time,
    end_time
FROM migration_003_weekly_slots;

INSERT INTO public.generation_slot_weekdays (
    slot_id,
    iso_weekday
)
SELECT
    slot_id,
    iso_weekday
FROM migration_003_weekly_slots;


CREATE TEMPORARY TABLE migration_003_interval_slots (
    plan_item_id UUID NOT NULL,
    slot_id UUID NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,

    PRIMARY KEY (plan_item_id),
    UNIQUE (slot_id)
) ON COMMIT DROP;

INSERT INTO migration_003_interval_slots (
    plan_item_id,
    slot_id,
    start_time,
    end_time
)
SELECT
    plan_item_id,
    gen_random_uuid(),
    default_start_time,
    default_end_time
FROM public.generation_configs
WHERE mode = 'interval_days';

INSERT INTO public.generation_slots (
    id,
    plan_item_id,
    start_time,
    end_time
)
SELECT
    slot_id,
    plan_item_id,
    start_time,
    end_time
FROM migration_003_interval_slots;


-- Cada entry manual legacy ya posee identidad UUID y se convierte
-- directamente en un slot con esa misma identidad.
INSERT INTO public.generation_slots (
    id,
    plan_item_id,
    start_time,
    end_time
)
SELECT
    entries.id,
    entries.plan_item_id,
    entries.start_time,
    entries.end_time
FROM public.generation_date_entries AS entries
JOIN public.generation_configs AS configs
    ON configs.plan_item_id = entries.plan_item_id
WHERE configs.mode = 'manual_dates';

INSERT INTO public.generation_slot_dates (
    slot_id,
    entry_date
)
SELECT
    entries.id,
    entries.entry_date
FROM public.generation_date_entries AS entries
JOIN public.generation_configs AS configs
    ON configs.plan_item_id = entries.plan_item_id
WHERE configs.mode = 'manual_dates';


-- ============================================================
-- OCCURRENCE BACKFILL
-- Weekly se identifica por PlanItem + weekday; interval_days por su
-- único slot legacy; manual_dates usa el horario para desambiguar solo
-- cuando existe más de una entry en la misma fecha.
-- Si dos occurrences competirían por slot + fecha, la relación no es
-- segura para la nueva invariante y ambas conservan NULL.
-- ============================================================

WITH weekly_candidates AS (
    SELECT
        occurrences.id AS occurrence_id,
        slots.slot_id,
        occurrences.occurrence_date,
        COUNT(*) OVER (
            PARTITION BY slots.slot_id, occurrences.occurrence_date
        ) AS occurrences_for_slot_date
    FROM public.occurrences AS occurrences
    JOIN migration_003_weekly_slots AS slots
        ON slots.plan_item_id = occurrences.plan_item_id
        AND slots.iso_weekday = EXTRACT(
            ISODOW FROM occurrences.occurrence_date
        )::SMALLINT
)
UPDATE public.occurrences AS occurrences
SET source_generation_slot_id = candidates.slot_id
FROM weekly_candidates AS candidates
WHERE occurrences.id = candidates.occurrence_id
    AND candidates.occurrences_for_slot_date = 1;

WITH interval_candidates AS (
    SELECT
        occurrences.id AS occurrence_id,
        slots.slot_id,
        occurrences.occurrence_date,
        COUNT(*) OVER (
            PARTITION BY slots.slot_id, occurrences.occurrence_date
        ) AS occurrences_for_slot_date
    FROM public.occurrences AS occurrences
    JOIN migration_003_interval_slots AS slots
        ON slots.plan_item_id = occurrences.plan_item_id
)
UPDATE public.occurrences AS occurrences
SET source_generation_slot_id = candidates.slot_id
FROM interval_candidates AS candidates
WHERE occurrences.id = candidates.occurrence_id
    AND candidates.occurrences_for_slot_date = 1;

WITH manual_candidate_pairs AS (
    SELECT
        occurrences.id AS occurrence_id,
        entries.id AS slot_id,
        occurrences.occurrence_date,
        (
            entries.start_time = occurrences.start_time
            AND entries.end_time = occurrences.end_time
        ) AS exact_time_match
    FROM public.occurrences AS occurrences
    JOIN public.generation_date_entries AS entries
        ON entries.plan_item_id = occurrences.plan_item_id
        AND entries.entry_date = occurrences.occurrence_date
),
manual_ranked_candidates AS (
    SELECT
        occurrence_id,
        slot_id,
        occurrence_date,
        exact_time_match,
        COUNT(*) OVER (
            PARTITION BY occurrence_id
        ) AS slots_on_date,
        COUNT(*) FILTER (
            WHERE exact_time_match
        ) OVER (
            PARTITION BY occurrence_id
        ) AS exact_time_matches
    FROM manual_candidate_pairs
),
manual_eligible_candidates AS (
    SELECT
        occurrence_id,
        slot_id,
        occurrence_date
    FROM manual_ranked_candidates
    WHERE slots_on_date = 1
        OR (
            exact_time_match
            AND exact_time_matches = 1
        )
),
manual_candidates AS (
    SELECT
        occurrence_id,
        slot_id,
        occurrence_date,
        COUNT(*) OVER (
            PARTITION BY slot_id, occurrence_date
        ) AS occurrences_for_slot_date
    FROM manual_eligible_candidates
)
UPDATE public.occurrences AS occurrences
SET source_generation_slot_id = candidates.slot_id
FROM manual_candidates AS candidates
WHERE occurrences.id = candidates.occurrence_id
    AND candidates.occurrences_for_slot_date = 1;


-- Un slot puede producir como máximo una occurrence por fecha. Los NULL
-- permanecen fuera de esta invariante para history/ad-hoc legacy.
CREATE UNIQUE INDEX uq_occurrences_source_generation_slot_date
    ON public.occurrences (
        source_generation_slot_id,
        occurrence_date
    )
    WHERE source_generation_slot_id IS NOT NULL;


-- ============================================================
-- GENERATION CONFIGS WITHOUT LEGACY DEFAULT TIMES
-- El rango de fechas continúa protegido por chk_generation_date_range.
-- ============================================================

ALTER TABLE public.generation_configs
    DROP CONSTRAINT chk_generation_default_time_range,
    DROP CONSTRAINT chk_generation_mode_rules;

ALTER TABLE public.generation_configs
    DROP COLUMN default_start_time,
    DROP COLUMN default_end_time;

ALTER TABLE public.generation_configs
    ADD CONSTRAINT chk_generation_mode_rules
    CHECK (
        (
            mode = 'weekly'
            AND start_date IS NOT NULL
            AND interval_days IS NULL
            AND (
                (
                    indefinite = TRUE
                    AND end_date IS NULL
                )
                OR
                (
                    indefinite = FALSE
                    AND end_date IS NOT NULL
                )
            )
        )
        OR
        (
            mode = 'interval_days'
            AND start_date IS NOT NULL
            AND interval_days IS NOT NULL
            AND interval_days > 0
            AND (
                (
                    indefinite = TRUE
                    AND end_date IS NULL
                )
                OR
                (
                    indefinite = FALSE
                    AND end_date IS NOT NULL
                )
            )
        )
        OR
        (
            mode = 'manual_dates'
            AND start_date IS NULL
            AND end_date IS NULL
            AND indefinite = FALSE
            AND interval_days IS NULL
        )
    );


-- La información legacy ya fue copiada y deja de ser fuente de verdad.
DROP TABLE public.generation_weekdays;
DROP TABLE public.generation_date_entries;

COMMIT;
