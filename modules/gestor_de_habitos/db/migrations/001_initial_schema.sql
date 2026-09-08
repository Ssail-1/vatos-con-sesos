BEGIN;

-- ============================================================
-- PLAN ITEMS
-- Identidad principal de actividades y hábitos.
-- ============================================================

CREATE TABLE public.plan_items (
    id UUID NOT NULL,
    name VARCHAR(150) NOT NULL,
    kind VARCHAR(20) NOT NULL,
    subtype VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT plan_items_pkey
        PRIMARY KEY (id),

    CONSTRAINT chk_plan_item_kind
        CHECK (
            kind IN (
                'activity',
                'habit'
            )
        ),

    CONSTRAINT chk_plan_item_kind_subtype
        CHECK (
            (
                kind = 'activity'
                AND subtype IN (
                    'anchor',
                    'periodic',
                    'event',
                    'unexpected'
                )
            )
            OR
            (
                kind = 'habit'
                AND subtype = 'scheduled'
            )
        )
);


-- ============================================================
-- GENERATION CONFIGS
-- Regla de generación vigente de cada PlanItem.
-- Relación 1:1 con plan_items.
-- ============================================================

CREATE TABLE public.generation_configs (
    plan_item_id UUID NOT NULL,

    mode VARCHAR(30) NOT NULL,

    start_date DATE,
    end_date DATE,

    indefinite BOOLEAN NOT NULL DEFAULT FALSE,

    default_start_time TIME,
    default_end_time TIME,

    interval_days INTEGER,

    stopped_from_date DATE,

    CONSTRAINT generation_configs_pkey
        PRIMARY KEY (plan_item_id),

    CONSTRAINT chk_generation_mode
        CHECK (
            mode IN (
                'weekly',
                'interval_days',
                'manual_dates'
            )
        ),

    CONSTRAINT chk_generation_date_range
        CHECK (
            end_date IS NULL
            OR (
                start_date IS NOT NULL
                AND end_date >= start_date
            )
        ),

    CONSTRAINT chk_generation_default_time_range
        CHECK (
            (
                default_start_time IS NULL
                AND default_end_time IS NULL
            )
            OR
            (
                default_start_time IS NOT NULL
                AND default_end_time IS NOT NULL
                AND default_start_time < default_end_time
            )
        ),

    CONSTRAINT chk_generation_mode_rules
        CHECK (
            (
                mode = 'weekly'

                AND start_date IS NOT NULL

                AND default_start_time IS NOT NULL
                AND default_end_time IS NOT NULL

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

                AND default_start_time IS NOT NULL
                AND default_end_time IS NOT NULL

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

                AND default_start_time IS NULL
                AND default_end_time IS NULL

                AND interval_days IS NULL
            )
        ),

    CONSTRAINT fk_generation_config_plan_item
        FOREIGN KEY (plan_item_id)
        REFERENCES public.plan_items(id)
);


-- ============================================================
-- OCCURRENCES
-- Apariciones materializadas en el calendario e historial.
-- ============================================================

CREATE TABLE public.occurrences (
    id UUID NOT NULL,
    plan_item_id UUID NOT NULL,

    occurrence_date DATE NOT NULL,

    start_time TIME NOT NULL,
    end_time TIME NOT NULL,

    status VARCHAR(30) NOT NULL,

    status_reason VARCHAR(30),
    source_occurrence_id UUID,

    CONSTRAINT occurrences_pkey
        PRIMARY KEY (id),

    CONSTRAINT chk_occurrence_time_range
        CHECK (
            start_time < end_time
        ),

    CONSTRAINT chk_occurrence_status
        CHECK (
            status IN (
                'pending',
                'in_progress',
                'completed',
                'not_completed',
                'not_finished',
                'cancelled'
            )
        ),

    CONSTRAINT chk_occurrence_status_context
        CHECK (
            (
                status_reason IS NULL
                AND source_occurrence_id IS NULL
            )
            OR
            (
                status_reason = 'priority_override'
                AND source_occurrence_id IS NOT NULL
            )
        ),

    CONSTRAINT chk_occurrence_override_status
        CHECK (
            status_reason IS NULL
            OR status IN (
                'cancelled',
                'not_finished'
            )
        ),

    CONSTRAINT chk_occurrence_source_not_self
        CHECK (
            source_occurrence_id IS NULL
            OR source_occurrence_id <> id
        ),

    CONSTRAINT fk_occurrence_plan_item
        FOREIGN KEY (plan_item_id)
        REFERENCES public.plan_items(id),

    CONSTRAINT fk_occurrence_source
        FOREIGN KEY (source_occurrence_id)
        REFERENCES public.occurrences(id)
);


-- ============================================================
-- GENERATION WEEKDAYS
-- Días ISO utilizados por mode = weekly.
-- 1 = lunes ... 7 = domingo.
-- ============================================================

CREATE TABLE public.generation_weekdays (
    plan_item_id UUID NOT NULL,
    iso_weekday SMALLINT NOT NULL,

    override_start_time TIME,
    override_end_time TIME,

    CONSTRAINT pk_generation_weekdays
        PRIMARY KEY (
            plan_item_id,
            iso_weekday
        ),

    CONSTRAINT chk_range_iso_weekday
        CHECK (
            iso_weekday BETWEEN 1 AND 7
        ),

    CONSTRAINT chk_overrides_rule
        CHECK (
            (
                override_start_time IS NULL
                AND override_end_time IS NULL
            )
            OR
            (
                override_start_time IS NOT NULL
                AND override_end_time IS NOT NULL
                AND override_start_time < override_end_time
            )
        ),

    CONSTRAINT fk_generation_weekdays_generation_configs
        FOREIGN KEY (plan_item_id)
        REFERENCES public.generation_configs(plan_item_id)
);


-- ============================================================
-- GENERATION DATE ENTRIES
-- Fechas explícitas utilizadas por mode = manual_dates.
-- ============================================================

CREATE TABLE public.generation_date_entries (
    id UUID NOT NULL,
    plan_item_id UUID NOT NULL,

    entry_date DATE NOT NULL,

    start_time TIME NOT NULL,
    end_time TIME NOT NULL,

    CONSTRAINT generation_date_entries_pkey
        PRIMARY KEY (id),

    CONSTRAINT chk_generation_time
        CHECK (
            start_time < end_time
        ),

    CONSTRAINT uq_generation_date_entry
        UNIQUE (
            plan_item_id,
            entry_date,
            start_time,
            end_time
        ),

    CONSTRAINT fk_generation_date_entries_generation_configs
        FOREIGN KEY (plan_item_id)
        REFERENCES public.generation_configs(plan_item_id)
);


-- ============================================================
-- GENERATION EXCLUDED DATES
-- Excepciones de generación para weekly e interval_days.
-- ============================================================

CREATE TABLE public.generation_excluded_dates (
    plan_item_id UUID NOT NULL,
    excluded_date DATE NOT NULL,

    CONSTRAINT pk_generation_excluded_dates
        PRIMARY KEY (
            plan_item_id,
            excluded_date
        ),

    CONSTRAINT fk_generation_excluded_dates_generation_configs
        FOREIGN KEY (plan_item_id)
        REFERENCES public.generation_configs(plan_item_id)
);

COMMIT;