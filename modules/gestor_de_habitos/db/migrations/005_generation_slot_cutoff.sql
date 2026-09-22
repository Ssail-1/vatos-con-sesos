BEGIN;

-- Inclusive last day on which a recurring slot may generate. NULL keeps the
-- pre-migration unbounded behavior. Historical slots and their provenance stay.
ALTER TABLE public.generation_slots
    ADD COLUMN last_generation_date DATE;

COMMIT;
