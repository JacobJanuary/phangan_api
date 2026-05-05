--
-- Migration: 0001_baseline
-- Source: pg_dump --schema-only of production DB (ThaiApp)
-- Date: 2026-05-05
--
-- This file represents the schema state at the moment migrations were
-- introduced into the project. On an existing database it MUST be marked
-- as applied without execution (`yoyo mark 0001_baseline.sql`).
-- On a fresh database, applying this file creates the full schema.
--
-- Dumped from database version 16.13 (Ubuntu 16.13-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.13 (Ubuntu 16.13-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: convert_ampm_to_24h(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.convert_ampm_to_24h(t text) RETURNS text
    LANGUAGE plpgsql
    AS $_$
DECLARE
    parts text[];
    result text := '';
    p text;
    h int;
    m text;
    ampm text;
BEGIN
    IF t IS NULL OR t = '' OR t = ' - ' THEN RETURN t; END IF;
    
    -- Split by ' - ' separator
    parts := string_to_array(t, ' - ');
    
    FOR i IN 1..array_length(parts, 1) LOOP
        p := TRIM(parts[i]);
        
        -- Handle 'Midnight'
        IF LOWER(p) = 'midnight' THEN
            IF result != '' THEN result := result || ' - '; END IF;
            result := result || '00:00';
            CONTINUE;
        END IF;
        
        -- Handle 'Noon'
        IF LOWER(p) = 'noon' THEN
            IF result != '' THEN result := result || ' - '; END IF;
            result := result || '12:00';
            CONTINUE;
        END IF;
        
        -- Extract hour:min AM/PM
        IF p ~ '^\d{1,2}:\d{2}\s*(AM|PM)$' THEN
            h := SPLIT_PART(REGEXP_REPLACE(p, '\s*(AM|PM)$', ''), ':', 1)::int;
            m := SPLIT_PART(REGEXP_REPLACE(p, '\s*(AM|PM)$', ''), ':', 2);
            ampm := UPPER(TRIM(REGEXP_REPLACE(p, '^\d{1,2}:\d{2}\s*', '')));
            
            IF ampm = 'PM' AND h != 12 THEN h := h + 12; END IF;
            IF ampm = 'AM' AND h = 12 THEN h := 0; END IF;
            
            IF result != '' THEN result := result || ' - '; END IF;
            result := result || LPAD(h::text, 2, '0') || ':' || m;
        ELSE
            -- Unknown format, keep as-is
            IF result != '' THEN result := result || ' - '; END IF;
            result := result || p;
        END IF;
    END LOOP;
    
    RETURN result;
END;
$_$;


--
-- Name: notify_new_event_outreach(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.notify_new_event_outreach() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NEW.sender_id IS NOT NULL AND NEW.sender_id > 0 AND (NEW.source = 'listener' OR NEW.source LIKE 'TLG:%') THEN
        PERFORM pg_notify('new_event_for_outreach', json_build_object(
            'event_id', NEW.id,
            'sender_id', NEW.sender_id,
            'sender', NEW.sender,
            'title_en', NEW.title->>'en',
            'source_chat_title', NEW.source_chat_title,
            'source_chat_id', NEW.source_chat_id,
            'message_id', NEW.message_id,
            'event_time', NEW.event_time,
            'price_thb', NEW.price_thb,
            'location_name', NEW.location_name
        )::text);
    END IF;
    RETURN NEW;
END;
$$;


--
-- Name: update_modified_column(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_modified_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: app_i18n; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.app_i18n (
    id integer NOT NULL,
    lang character varying(5) NOT NULL,
    screen character varying(50) NOT NULL,
    key character varying(100) NOT NULL,
    value text NOT NULL,
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: app_i18n_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.app_i18n_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: app_i18n_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.app_i18n_id_seq OWNED BY public.app_i18n.id;


--
-- Name: chats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chats (
    id bigint NOT NULL,
    title text NOT NULL,
    type text,
    is_active boolean DEFAULT true,
    added_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: dashboard_users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dashboard_users (
    id integer NOT NULL,
    email text NOT NULL,
    password_hash text NOT NULL,
    name text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_login_at timestamp with time zone
);


--
-- Name: dashboard_users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.dashboard_users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dashboard_users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.dashboard_users_id_seq OWNED BY public.dashboard_users.id;


--
-- Name: discovered_chats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.discovered_chats (
    id integer NOT NULL,
    chat_id bigint,
    username text,
    invite_link text,
    title text,
    type text,
    source_type text NOT NULL,
    found_in_chat_id bigint,
    participants_count integer,
    status text DEFAULT 'new'::text,
    resolved boolean DEFAULT false,
    times_seen integer DEFAULT 1,
    first_seen timestamp with time zone DEFAULT now(),
    last_seen timestamp with time zone DEFAULT now()
);


--
-- Name: discovered_chats_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.discovered_chats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: discovered_chats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.discovered_chats_id_seq OWNED BY public.discovered_chats.id;


--
-- Name: discovery_venues; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.discovery_venues (
    place_id character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    search_keyword character varying(100),
    lat double precision,
    lng double precision,
    google_maps_url text,
    website text,
    phone character varying(50),
    telegram_links jsonb DEFAULT '[]'::jsonb,
    whatsapp_links jsonb DEFAULT '[]'::jsonb,
    instagram_url text,
    schedule_pages jsonb DEFAULT '[]'::jsonb,
    status character varying(50) DEFAULT 'unprocessed'::character varying,
    notes text,
    created_at timestamp without time zone DEFAULT now(),
    scraped_at timestamp without time zone,
    ai_analysis_json jsonb,
    deep_analysis_json jsonb,
    instagram_links jsonb DEFAULT '[]'::jsonb,
    google_rating double precision,
    google_reviews_count integer,
    monitoring_approved boolean,
    ig_bio text,
    ig_bio_contacts jsonb,
    ig_followers integer,
    description text,
    photo_paths jsonb DEFAULT '[]'::jsonb,
    google_reviews jsonb DEFAULT '[]'::jsonb,
    place_types jsonb DEFAULT '[]'::jsonb,
    opening_hours jsonb,
    generative_summary text,
    review_summary text,
    neighborhood_summary text,
    ai_vibe_summary text,
    ai_events_summary text,
    ai_strengths jsonb,
    ai_weaknesses jsonb,
    ai_analyzed_at timestamp with time zone,
    hosts_events boolean,
    community_score smallint,
    event_types jsonb DEFAULT '[]'::jsonb,
    venue_type text,
    is_tourist_spot boolean,
    moderation_status text DEFAULT 'pending'::text,
    moderation_note text,
    moderated_by text,
    moderated_at timestamp with time zone,
    description_ru text,
    ai_vibe_summary_ru text,
    ai_events_summary_ru text,
    ai_strengths_ru jsonb,
    ai_weaknesses_ru jsonb,
    web_spider_done_at timestamp with time zone,
    web_spider_error text,
    email_addresses jsonb DEFAULT '[]'::jsonb,
    name_ru text,
    generative_summary_ru text,
    review_summary_ru text,
    neighborhood_summary_ru text,
    event_types_ru jsonb,
    translated_at timestamp with time zone,
    area character varying(100),
    formatted_address text,
    is_trash boolean DEFAULT false NOT NULL,
    CONSTRAINT discovery_venues_moderation_status_check CHECK ((moderation_status = ANY (ARRAY['pending'::text, 'approved'::text, 'rejected'::text, 'hidden'::text])))
);


--
-- Name: events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.events (
    id integer NOT NULL,
    title jsonb NOT NULL,
    category text,
    event_date date,
    event_time text,
    location_name text,
    venue_id integer,
    price_thb integer DEFAULT 0,
    summary jsonb,
    description jsonb,
    source_chat_id bigint,
    source_chat_title text,
    message_id bigint,
    sender text,
    filter_score integer DEFAULT 0,
    original_text text,
    source text DEFAULT 'listener'::text,
    fingerprint text,
    detected_at timestamp with time zone DEFAULT now(),
    image_path character varying,
    sender_id bigint,
    google_maps_url text,
    recurrence_type character varying(20),
    parent_id integer,
    duration character varying(100),
    CONSTRAINT events_recurrence_type_check CHECK (((recurrence_type)::text = ANY ((ARRAY['daily'::character varying, 'weekly'::character varying])::text[])))
);


--
-- Name: events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.events_id_seq OWNED BY public.events.id;


--
-- Name: harvested_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.harvested_events (
    event_id integer NOT NULL,
    place_id character varying(100),
    source_url text NOT NULL,
    image_url text,
    raw_text text,
    event_name text,
    event_date date,
    event_time character varying(50),
    event_type text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    moderation_status character varying(20) DEFAULT 'pending'::character varying,
    extracted_contacts text,
    content_hash text,
    post_timestamp timestamp with time zone,
    vision_summary text,
    extracted_contacts_json jsonb,
    event_name_ru text,
    event_type_ru text,
    vision_summary_ru text,
    raw_text_ru text,
    translated_at timestamp with time zone
);


--
-- Name: harvested_events_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.harvested_events_event_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: harvested_events_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.harvested_events_event_id_seq OWNED BY public.harvested_events.event_id;


--
-- Name: outreach_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.outreach_log (
    id integer NOT NULL,
    sender_id bigint NOT NULL,
    event_id integer,
    account_idx integer DEFAULT 0 NOT NULL,
    status text DEFAULT 'queued'::text NOT NULL,
    first_msg text,
    reply_text text,
    created_at timestamp with time zone DEFAULT now(),
    sent_at timestamp with time zone,
    replied_at timestamp with time zone,
    dialog_state text DEFAULT 'phase1_queued'::text NOT NULL
);


--
-- Name: outreach_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.outreach_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: outreach_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.outreach_log_id_seq OWNED BY public.outreach_log.id;


--
-- Name: test_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.test_runs (
    id integer NOT NULL,
    elapsed_sec real,
    chats_count integer,
    batch_messages integer,
    batch_filtered integer,
    batch_events integer,
    spider_discovered integer,
    spider_resolved integer,
    live_messages integer,
    live_events integer,
    raw_report jsonb,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: test_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.test_runs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: test_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.test_runs_id_seq OWNED BY public.test_runs.id;


--
-- Name: ui_translations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ui_translations (
    lang_code character varying(5) NOT NULL,
    onboarding jsonb NOT NULL
);


--
-- Name: user_swipes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_swipes (
    id integer NOT NULL,
    user_id integer NOT NULL,
    event_id integer NOT NULL,
    direction character varying(5) NOT NULL,
    swiped_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT user_swipes_direction_check CHECK (((direction)::text = ANY ((ARRAY['right'::character varying, 'left'::character varying])::text[])))
);


--
-- Name: user_swipes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_swipes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_swipes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_swipes_id_seq OWNED BY public.user_swipes.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id integer NOT NULL,
    telegram_id bigint,
    first_name character varying(50) NOT NULL,
    gender character varying(10),
    mood character varying(20),
    avatar_path character varying(255),
    is_phantom boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now(),
    is_aesthetic boolean DEFAULT true,
    language character varying(10) DEFAULT 'en'::character varying,
    updated_at timestamp with time zone DEFAULT now(),
    current_mood character varying(50)
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: venue_aliases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.venue_aliases (
    query character varying(255) NOT NULL,
    venue_id integer,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now())
);


--
-- Name: venues; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.venues (
    id integer NOT NULL,
    name text NOT NULL,
    name_normalized text,
    lat double precision,
    lng double precision,
    google_maps_url text,
    instagram_url text,
    address text,
    description text,
    cached_at timestamp with time zone DEFAULT now()
);


--
-- Name: venues_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.venues_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: venues_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.venues_id_seq OWNED BY public.venues.id;


--
-- Name: vibe_pilot_cache; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vibe_pilot_cache (
    user_id bigint NOT NULL,
    target_date date NOT NULL,
    input_hash text NOT NULL,
    plan_json jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now())
);


--
-- Name: app_i18n id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_i18n ALTER COLUMN id SET DEFAULT nextval('public.app_i18n_id_seq'::regclass);


--
-- Name: dashboard_users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dashboard_users ALTER COLUMN id SET DEFAULT nextval('public.dashboard_users_id_seq'::regclass);


--
-- Name: discovered_chats id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.discovered_chats ALTER COLUMN id SET DEFAULT nextval('public.discovered_chats_id_seq'::regclass);


--
-- Name: events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events ALTER COLUMN id SET DEFAULT nextval('public.events_id_seq'::regclass);


--
-- Name: harvested_events event_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.harvested_events ALTER COLUMN event_id SET DEFAULT nextval('public.harvested_events_event_id_seq'::regclass);


--
-- Name: outreach_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.outreach_log ALTER COLUMN id SET DEFAULT nextval('public.outreach_log_id_seq'::regclass);


--
-- Name: test_runs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.test_runs ALTER COLUMN id SET DEFAULT nextval('public.test_runs_id_seq'::regclass);


--
-- Name: user_swipes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_swipes ALTER COLUMN id SET DEFAULT nextval('public.user_swipes_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: venues id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venues ALTER COLUMN id SET DEFAULT nextval('public.venues_id_seq'::regclass);


--
-- Name: app_i18n app_i18n_lang_screen_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_i18n
    ADD CONSTRAINT app_i18n_lang_screen_key_key UNIQUE (lang, screen, key);


--
-- Name: app_i18n app_i18n_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_i18n
    ADD CONSTRAINT app_i18n_pkey PRIMARY KEY (id);


--
-- Name: chats chats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chats
    ADD CONSTRAINT chats_pkey PRIMARY KEY (id);


--
-- Name: dashboard_users dashboard_users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dashboard_users
    ADD CONSTRAINT dashboard_users_email_key UNIQUE (email);


--
-- Name: dashboard_users dashboard_users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dashboard_users
    ADD CONSTRAINT dashboard_users_pkey PRIMARY KEY (id);


--
-- Name: discovered_chats discovered_chats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.discovered_chats
    ADD CONSTRAINT discovered_chats_pkey PRIMARY KEY (id);


--
-- Name: discovery_venues discovery_venues_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.discovery_venues
    ADD CONSTRAINT discovery_venues_pkey PRIMARY KEY (place_id);


--
-- Name: events events_fingerprint_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_fingerprint_key UNIQUE (fingerprint);


--
-- Name: events events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_pkey PRIMARY KEY (id);


--
-- Name: harvested_events harvested_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.harvested_events
    ADD CONSTRAINT harvested_events_pkey PRIMARY KEY (event_id);


--
-- Name: harvested_events harvested_events_source_url_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.harvested_events
    ADD CONSTRAINT harvested_events_source_url_key UNIQUE (source_url);


--
-- Name: outreach_log outreach_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.outreach_log
    ADD CONSTRAINT outreach_log_pkey PRIMARY KEY (id);


--
-- Name: outreach_log outreach_log_sender_id_event_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.outreach_log
    ADD CONSTRAINT outreach_log_sender_id_event_id_key UNIQUE (sender_id, event_id);


--
-- Name: test_runs test_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.test_runs
    ADD CONSTRAINT test_runs_pkey PRIMARY KEY (id);


--
-- Name: ui_translations ui_translations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ui_translations
    ADD CONSTRAINT ui_translations_pkey PRIMARY KEY (lang_code);


--
-- Name: user_swipes user_swipes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_swipes
    ADD CONSTRAINT user_swipes_pkey PRIMARY KEY (id);


--
-- Name: user_swipes user_swipes_user_id_event_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_swipes
    ADD CONSTRAINT user_swipes_user_id_event_id_key UNIQUE (user_id, event_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_telegram_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_telegram_id_key UNIQUE (telegram_id);


--
-- Name: venue_aliases venue_aliases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venue_aliases
    ADD CONSTRAINT venue_aliases_pkey PRIMARY KEY (query);


--
-- Name: venues venues_name_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venues
    ADD CONSTRAINT venues_name_unique UNIQUE (name);


--
-- Name: venues venues_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venues
    ADD CONSTRAINT venues_pkey PRIMARY KEY (id);


--
-- Name: vibe_pilot_cache vibe_pilot_cache_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vibe_pilot_cache
    ADD CONSTRAINT vibe_pilot_cache_pkey PRIMARY KEY (user_id, target_date);


--
-- Name: idx_discovered_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_discovered_status ON public.discovered_chats USING btree (status) WHERE (status = 'new'::text);


--
-- Name: idx_discovered_unresolved; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_discovered_unresolved ON public.discovered_chats USING btree (resolved) WHERE (resolved = false);


--
-- Name: idx_dv_community_score; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dv_community_score ON public.discovery_venues USING btree (community_score);


--
-- Name: idx_dv_is_trash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dv_is_trash ON public.discovery_venues USING btree (is_trash) WHERE (is_trash = true);


--
-- Name: idx_dv_moderation_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dv_moderation_status ON public.discovery_venues USING btree (moderation_status);


--
-- Name: idx_dv_name_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dv_name_trgm ON public.discovery_venues USING gin (name public.gin_trgm_ops);


--
-- Name: idx_dv_translated_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dv_translated_at ON public.discovery_venues USING btree (translated_at);


--
-- Name: idx_dv_venue_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dv_venue_type ON public.discovery_venues USING btree (venue_type);


--
-- Name: idx_dv_vibe_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dv_vibe_trgm ON public.discovery_venues USING gin (ai_vibe_summary public.gin_trgm_ops);


--
-- Name: idx_dv_web_spider_done; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dv_web_spider_done ON public.discovery_venues USING btree (web_spider_done_at) WHERE (web_spider_done_at IS NULL);


--
-- Name: idx_events_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_events_category ON public.events USING btree (category);


--
-- Name: idx_events_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_events_date ON public.events USING btree (event_date) WHERE (event_date IS NOT NULL);


--
-- Name: idx_events_detected; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_events_detected ON public.events USING btree (detected_at DESC);


--
-- Name: idx_events_original_text_md5; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_events_original_text_md5 ON public.events USING btree (md5(original_text));


--
-- Name: idx_events_trgm_en; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_events_trgm_en ON public.events USING gin (((title ->> 'en'::text)) public.gin_trgm_ops);


--
-- Name: idx_events_trgm_ru; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_events_trgm_ru ON public.events USING gin (((title ->> 'ru'::text)) public.gin_trgm_ops);


--
-- Name: idx_harvested_content_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_harvested_content_hash ON public.harvested_events USING btree (content_hash) WHERE (content_hash IS NOT NULL);


--
-- Name: idx_he_translated_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_he_translated_at ON public.harvested_events USING btree (translated_at);


--
-- Name: idx_outreach_sender; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_outreach_sender ON public.outreach_log USING btree (sender_id);


--
-- Name: idx_outreach_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_outreach_state ON public.outreach_log USING btree (dialog_state);


--
-- Name: idx_outreach_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_outreach_status ON public.outreach_log USING btree (status);


--
-- Name: idx_swipes_event_dir; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_swipes_event_dir ON public.user_swipes USING btree (event_id, direction);


--
-- Name: idx_swipes_user_dir; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_swipes_user_dir ON public.user_swipes USING btree (user_id, direction);


--
-- Name: idx_users_phantom_mood; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_phantom_mood ON public.users USING btree (is_phantom, mood, gender);


--
-- Name: idx_venues_normalized; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_venues_normalized ON public.venues USING btree (name_normalized) WHERE (name_normalized IS NOT NULL);


--
-- Name: uq_discovered_chat_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_discovered_chat_id ON public.discovered_chats USING btree (chat_id) WHERE (chat_id IS NOT NULL);


--
-- Name: uq_discovered_invite; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_discovered_invite ON public.discovered_chats USING btree (invite_link) WHERE (invite_link IS NOT NULL);


--
-- Name: uq_discovered_username; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_discovered_username ON public.discovered_chats USING btree (lower(username)) WHERE (username IS NOT NULL);


--
-- Name: uq_venue_name; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_venue_name ON public.venues USING btree (name) WHERE ((name IS NOT NULL) AND (name <> ''::text));


--
-- Name: venues_name_normalized_uniq; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX venues_name_normalized_uniq ON public.venues USING btree (name_normalized);


--
-- Name: chats chats_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER chats_updated_at BEFORE UPDATE ON public.chats FOR EACH ROW EXECUTE FUNCTION public.update_modified_column();


--
-- Name: events trg_new_event_outreach; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_new_event_outreach AFTER INSERT OR UPDATE OF sender_id ON public.events FOR EACH ROW EXECUTE FUNCTION public.notify_new_event_outreach();


--
-- Name: discovered_chats discovered_chats_found_in_chat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.discovered_chats
    ADD CONSTRAINT discovered_chats_found_in_chat_id_fkey FOREIGN KEY (found_in_chat_id) REFERENCES public.chats(id) ON DELETE SET NULL;


--
-- Name: events events_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.events(id) ON DELETE SET NULL;


--
-- Name: events events_venue_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_venue_id_fkey FOREIGN KEY (venue_id) REFERENCES public.venues(id) ON DELETE SET NULL;


--
-- Name: harvested_events harvested_events_place_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.harvested_events
    ADD CONSTRAINT harvested_events_place_id_fkey FOREIGN KEY (place_id) REFERENCES public.discovery_venues(place_id);


--
-- Name: outreach_log outreach_log_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.outreach_log
    ADD CONSTRAINT outreach_log_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.events(id);


--
-- Name: user_swipes user_swipes_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_swipes
    ADD CONSTRAINT user_swipes_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.events(id) ON DELETE CASCADE;


--
-- Name: user_swipes user_swipes_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_swipes
    ADD CONSTRAINT user_swipes_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: venue_aliases venue_aliases_venue_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venue_aliases
    ADD CONSTRAINT venue_aliases_venue_id_fkey FOREIGN KEY (venue_id) REFERENCES public.venues(id) ON DELETE CASCADE;


--
-- Name: vibe_pilot_cache vibe_pilot_cache_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vibe_pilot_cache
    ADD CONSTRAINT vibe_pilot_cache_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--


