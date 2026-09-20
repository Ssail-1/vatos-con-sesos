BEGIN;

-- btree_gist permite combinar igualdad UUID con overlap de rangos en una
-- exclusion constraint. Es una extensión trusted de PostgreSQL y forma parte
-- de la estrategia verificada para PostgreSQL 16 de esta migración.
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- Las constraints de 001/002 ya protegen estas invariantes. Esta comprobación
-- explícita evita iniciar el cambio semántico si el schema de entrada fue
-- alterado o contiene datos que no corresponden al modelo pre-004.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM public.occurrences
        WHERE start_time >= end_time
    ) THEN
        RAISE EXCEPTION
            '004 cannot migrate occurrences with a non-positive time range';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.occurrences
        WHERE status NOT IN (
            'pending',
            'in_progress',
            'completed',
            'not_completed',
            'not_finished',
            'cancelled'
        )
    ) THEN
        RAISE EXCEPTION
            '004 cannot migrate occurrences with an invalid status';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.occurrences
        WHERE
            (
                status_reason IS NULL
                AND source_occurrence_id IS NOT NULL
            )
            OR
            (
                status_reason IS NOT NULL
                AND (
                    status_reason <> 'priority_override'
                    OR source_occurrence_id IS NULL
                )
            )
    ) THEN
        RAISE EXCEPTION
            '004 cannot migrate an invalid occurrence status context';
    END IF;
END
$$;

-- ============================================================
-- OCCURRENCE CONFLICT / ORIGIN METADATA
-- El reason deja de describir únicamente el status: conserva el último
-- conflicto que modificó el estado o la estructura de la occurrence.
-- ============================================================

ALTER TABLE public.occurrences
    DROP CONSTRAINT chk_occurrence_status_context,
    DROP CONSTRAINT chk_occurrence_override_status;

ALTER TABLE public.occurrences
    RENAME COLUMN status_reason TO conflict_reason;

ALTER TABLE public.occurrences
    ADD COLUMN origin_reason VARCHAR(30),
    ADD COLUMN last_conflict_action VARCHAR(30),

    ADD CONSTRAINT chk_occurrence_conflict_reason
        CHECK (
            conflict_reason IS NULL
            OR conflict_reason IN (
                'priority_override',
                'user_forced_override'
            )
        ),

    ADD CONSTRAINT chk_occurrence_conflict_context
        CHECK (
            (
                conflict_reason IS NULL
                AND source_occurrence_id IS NULL
            )
            OR
            (
                conflict_reason IS NOT NULL
                AND source_occurrence_id IS NOT NULL
            )
        ),

    ADD CONSTRAINT chk_occurrence_origin_reason
        CHECK (
            origin_reason IS NULL
            OR origin_reason = 'conflict_insertion'
        ),

    ADD CONSTRAINT chk_occurrence_last_conflict_action
        CHECK (
            last_conflict_action IS NULL
            OR last_conflict_action IN (
                'conflict_insertion',
                'conflict_move'
            )
        );


-- ============================================================
-- OCCURRENCE SEGMENTS
-- Cada segment pertenece a una sola occurrence y conserva su propio
-- intervalo/status. Los bounds respecto del parent y la existencia de al
-- menos un segment permanecen como validación de estado final del dominio.
-- ============================================================

CREATE TABLE public.occurrence_segments (
    id UUID NOT NULL,
    occurrence_id UUID NOT NULL,

    start_time TIME NOT NULL,
    end_time TIME NOT NULL,

    status VARCHAR(30) NOT NULL,

    CONSTRAINT occurrence_segments_pkey
        PRIMARY KEY (id),

    CONSTRAINT chk_occurrence_segment_time_range
        CHECK (start_time < end_time),

    CONSTRAINT chk_occurrence_segment_status
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

    CONSTRAINT fk_occurrence_segments_occurrence
        FOREIGN KEY (occurrence_id)
        REFERENCES public.occurrences(id)
        ON DELETE CASCADE,

    -- PostgreSQL no incluye un timerange built-in. Anclar ambos TIME al mismo
    -- día produce un tsrange exacto y conserva la semántica [start, end): los
    -- segmentos adyacentes no se superponen.
    CONSTRAINT excl_occurrence_segments_sibling_overlap
        EXCLUDE USING gist (
            occurrence_id WITH =,
            (
                tsrange(
                    DATE '2000-01-01' + start_time,
                    DATE '2000-01-01' + end_time,
                    '[)'
                )
            ) WITH &&
        )
        DEFERRABLE INITIALLY DEFERRED
);

CREATE INDEX idx_occurrence_segments_occurrence_time
    ON public.occurrence_segments (
        occurrence_id,
        start_time,
        end_time,
        id
    );


-- ============================================================
-- LEGACY OCCURRENCE BACKFILL
-- El modelo anterior solo demuestra un intervalo/status por occurrence.
-- No se infieren pausas, splits, interrupciones ni tiempo efectivo.
-- ============================================================

INSERT INTO public.occurrence_segments (
    id,
    occurrence_id,
    start_time,
    end_time,
    status
)
SELECT
    gen_random_uuid(),
    occurrences.id,
    occurrences.start_time,
    occurrences.end_time,
    occurrences.status
FROM public.occurrences AS occurrences;


-- Un fallo en cualquiera de estas comprobaciones aborta la transacción
-- completa, incluyendo extensión, rename, metadata, tabla y backfill.
DO $$
BEGIN
    IF (
        SELECT COUNT(*)
        FROM public.occurrences
    ) <> (
        SELECT COUNT(*)
        FROM public.occurrence_segments
    ) THEN
        RAISE EXCEPTION
            '004 backfill count does not match the legacy occurrence count';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.occurrences AS occurrences
        LEFT JOIN public.occurrence_segments AS segments
            ON segments.occurrence_id = occurrences.id
        WHERE segments.id IS NULL
    ) THEN
        RAISE EXCEPTION
            '004 backfill left a legacy occurrence without a segment';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.occurrence_segments AS segments
        LEFT JOIN public.occurrences AS occurrences
            ON occurrences.id = segments.occurrence_id
        WHERE occurrences.id IS NULL
    ) THEN
        RAISE EXCEPTION
            '004 backfill created an orphan occurrence segment';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.occurrence_segments AS segments
        JOIN public.occurrences AS occurrences
            ON occurrences.id = segments.occurrence_id
        WHERE segments.start_time IS DISTINCT FROM occurrences.start_time
            OR segments.end_time IS DISTINCT FROM occurrences.end_time
            OR segments.status IS DISTINCT FROM occurrences.status
    ) THEN
        RAISE EXCEPTION
            '004 backfill does not exactly match legacy occurrence values';
    END IF;
END
$$;

COMMIT;
