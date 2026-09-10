BEGIN;

ALTER TABLE public.occurrences
    DROP CONSTRAINT chk_occurrence_status_context;

ALTER TABLE public.occurrences
    ADD CONSTRAINT chk_occurrence_status_context
    CHECK (
        (
            status_reason IS NULL
            AND source_occurrence_id IS NULL
        )
        OR
        (
            status_reason IS NOT NULL
            AND status_reason = 'priority_override'
            AND source_occurrence_id IS NOT NULL
        )
    );

COMMIT;
