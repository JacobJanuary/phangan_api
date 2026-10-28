-- Hero-card event contract support.
-- Adds conservative event language tags; API-only venue/rating fields use existing tables.

ALTER TABLE public.events
    ADD COLUMN IF NOT EXISTS event_languages text[];

ALTER TABLE public.events
    DROP CONSTRAINT IF EXISTS events_event_languages_known_chk;

ALTER TABLE public.events
    ADD CONSTRAINT events_event_languages_known_chk
    CHECK (
        event_languages IS NULL
        OR event_languages <@ ARRAY['EN', 'RU']::text[]
    );

UPDATE public.events
SET event_languages = array_remove(ARRAY[
    CASE
        WHEN original_text ~* '(en\s*/\s*ru|ru\s*/\s*en|english|англ)'
        THEN 'EN'
    END,
    CASE
        WHEN original_text ~* '(en\s*/\s*ru|ru\s*/\s*en|russian|русск)'
        THEN 'RU'
    END
], NULL)
WHERE event_languages IS NULL
  AND original_text IS NOT NULL
  AND original_text ~* '(en\s*/\s*ru|ru\s*/\s*en|english|russian|англ|русск)';
