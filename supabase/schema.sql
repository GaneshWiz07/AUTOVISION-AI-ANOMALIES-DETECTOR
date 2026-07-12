-- ============================================================================
-- AUTOVISION CANONICAL DATABASE SCHEMA
-- ============================================================================
-- This is the single source of truth for the AutoVision database.
-- It supersedes complete_production_setup.sql, quick_production_setup.sql,
-- and troubleshooting_fixes.sql (see supabase/deprecated/).
--
-- Safe to run repeatedly (idempotent): existing tables/columns are preserved,
-- policies and functions are dropped and recreated to guarantee a single,
-- consistent definition.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- 1. USER PROFILES
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.user_profiles (
    id UUID REFERENCES auth.users(id) PRIMARY KEY,
    email TEXT NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    is_system_user BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE public.user_profiles
    ADD COLUMN IF NOT EXISTS avatar_url TEXT,
    ADD COLUMN IF NOT EXISTS is_system_user BOOLEAN NOT NULL DEFAULT FALSE;

-- ============================================================================
-- 2. VIDEOS
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.videos (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) NOT NULL,
    filename TEXT NOT NULL,
    original_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_url TEXT,
    file_size BIGINT NOT NULL DEFAULT 0,
    duration_seconds REAL,
    fps REAL,
    resolution TEXT,
    upload_status TEXT DEFAULT 'uploaded' CHECK (upload_status IN ('uploaded', 'processing', 'completed', 'failed')),
    storage_provider TEXT DEFAULT 'supabase' CHECK (storage_provider IN ('local', 'supabase')),
    storage_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE public.videos
    ADD COLUMN IF NOT EXISTS file_url TEXT,
    ADD COLUMN IF NOT EXISTS storage_provider TEXT DEFAULT 'supabase',
    ADD COLUMN IF NOT EXISTS storage_id TEXT;

ALTER TABLE public.videos ALTER COLUMN storage_provider SET DEFAULT 'supabase';

ALTER TABLE public.videos DROP CONSTRAINT IF EXISTS videos_storage_provider_check;
ALTER TABLE public.videos ADD CONSTRAINT videos_storage_provider_check
    CHECK (storage_provider IN ('local', 'supabase'));

ALTER TABLE public.videos DROP CONSTRAINT IF EXISTS videos_upload_status_check;
ALTER TABLE public.videos ADD CONSTRAINT videos_upload_status_check
    CHECK (upload_status IN ('uploaded', 'processing', 'completed', 'failed'));

-- ============================================================================
-- 3. EVENTS (anomaly detections)
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    video_id UUID REFERENCES public.videos(id) ON DELETE CASCADE NOT NULL,
    user_id UUID REFERENCES auth.users(id) NOT NULL,
    event_type TEXT NOT NULL,
    anomaly_score REAL NOT NULL DEFAULT 0.0,
    confidence REAL NOT NULL DEFAULT 0.0,
    timestamp_seconds REAL NOT NULL,
    frame_number INTEGER NOT NULL,
    bounding_box JSONB,
    description TEXT,
    explanation TEXT,
    recommendations JSONB,
    is_alert BOOLEAN DEFAULT FALSE,
    is_false_positive BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE public.events
    ADD COLUMN IF NOT EXISTS bounding_box JSONB,
    ADD COLUMN IF NOT EXISTS is_false_positive BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS explanation TEXT,
    ADD COLUMN IF NOT EXISTS recommendations JSONB;

-- ============================================================================
-- 4. USER SETTINGS
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.user_settings (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) UNIQUE NOT NULL,
    anomaly_threshold REAL DEFAULT 0.5 CHECK (anomaly_threshold >= 0 AND anomaly_threshold <= 1),
    frame_sampling_rate INTEGER DEFAULT 10 CHECK (frame_sampling_rate > 0),
    auto_delete_old_videos BOOLEAN DEFAULT FALSE,
    video_retention_days INTEGER DEFAULT 30 CHECK (video_retention_days > 0),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- 5. HISTORICAL PATTERNS (RAG retrieval store)
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.historical_patterns (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) NOT NULL,
    pattern_type TEXT NOT NULL,
    embedding REAL[] NOT NULL,
    description TEXT NOT NULL,
    metadata JSONB,
    frequency_count INTEGER DEFAULT 1,
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- 6. RL TRAINING DATA
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.rl_training_data (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) NOT NULL,
    state_vector REAL[] NOT NULL,
    action INTEGER NOT NULL,
    reward REAL NOT NULL,
    next_state_vector REAL[],
    done BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- 7. LOGS (system/event log sink)
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    message TEXT NOT NULL,
    log_level TEXT DEFAULT 'INFO' CHECK (log_level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')),
    user_id UUID REFERENCES auth.users(id),
    video_id UUID REFERENCES public.videos(id),
    event_id UUID REFERENCES public.events(id),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- 8. INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_user_profiles_email ON public.user_profiles(email);

CREATE INDEX IF NOT EXISTS idx_videos_user_id ON public.videos(user_id);
CREATE INDEX IF NOT EXISTS idx_videos_created_at ON public.videos(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_videos_status ON public.videos(upload_status);
CREATE INDEX IF NOT EXISTS idx_videos_storage_provider ON public.videos(storage_provider);

CREATE INDEX IF NOT EXISTS idx_events_video_id ON public.events(video_id);
CREATE INDEX IF NOT EXISTS idx_events_user_id ON public.events(user_id);
CREATE INDEX IF NOT EXISTS idx_events_created_at ON public.events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_anomaly_score ON public.events(anomaly_score DESC);
CREATE INDEX IF NOT EXISTS idx_events_event_type ON public.events(event_type);

CREATE INDEX IF NOT EXISTS idx_user_settings_user_id ON public.user_settings(user_id);

CREATE INDEX IF NOT EXISTS idx_patterns_user_id ON public.historical_patterns(user_id);
CREATE INDEX IF NOT EXISTS idx_patterns_type ON public.historical_patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_patterns_frequency ON public.historical_patterns(frequency_count DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_patterns_dedup
    ON public.historical_patterns(user_id, pattern_type, description);

CREATE INDEX IF NOT EXISTS idx_rl_data_user_id ON public.rl_training_data(user_id);
CREATE INDEX IF NOT EXISTS idx_rl_data_created_at ON public.rl_training_data(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_logs_created_at ON public.logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_logs_user_id ON public.logs(user_id);
CREATE INDEX IF NOT EXISTS idx_logs_log_level ON public.logs(log_level);

-- ============================================================================
-- 9. ROW LEVEL SECURITY
-- ============================================================================

ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.historical_patterns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rl_training_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.logs ENABLE ROW LEVEL SECURITY;

-- Drop every policy name used across all historical versions of this schema
-- (quick_production_setup.sql, troubleshooting_fixes.sql, complete_production_setup.sql)
-- so re-running this script always converges on one consistent set.
DROP POLICY IF EXISTS "Users own data" ON public.user_profiles;
DROP POLICY IF EXISTS "Users can manage their profile" ON public.user_profiles;
DROP POLICY IF EXISTS "Users can view their own profile" ON public.user_profiles;
DROP POLICY IF EXISTS "Users can update their own profile" ON public.user_profiles;
DROP POLICY IF EXISTS "Users can insert their own profile" ON public.user_profiles;

DROP POLICY IF EXISTS "Users own videos" ON public.videos;
DROP POLICY IF EXISTS "Users can manage their videos" ON public.videos;
DROP POLICY IF EXISTS "Users can view their own videos" ON public.videos;
DROP POLICY IF EXISTS "Users can insert their own videos" ON public.videos;
DROP POLICY IF EXISTS "Users can update their own videos" ON public.videos;
DROP POLICY IF EXISTS "Users can delete their own videos" ON public.videos;

DROP POLICY IF EXISTS "Users own events" ON public.events;
DROP POLICY IF EXISTS "Users can manage their events" ON public.events;
DROP POLICY IF EXISTS "Users can view their own events" ON public.events;
DROP POLICY IF EXISTS "Users can insert their own events" ON public.events;
DROP POLICY IF EXISTS "Users can update their own events" ON public.events;

DROP POLICY IF EXISTS "Users own settings" ON public.user_settings;
DROP POLICY IF EXISTS "Users can manage their settings" ON public.user_settings;
DROP POLICY IF EXISTS "Users can view their own settings" ON public.user_settings;
DROP POLICY IF EXISTS "Users can insert their own settings" ON public.user_settings;
DROP POLICY IF EXISTS "Users can update their own settings" ON public.user_settings;

DROP POLICY IF EXISTS "Users can view their own patterns" ON public.historical_patterns;
DROP POLICY IF EXISTS "Users can insert their own patterns" ON public.historical_patterns;
DROP POLICY IF EXISTS "Users can update their own patterns" ON public.historical_patterns;

DROP POLICY IF EXISTS "Users can view their own RL data" ON public.rl_training_data;
DROP POLICY IF EXISTS "Users can insert their own RL data" ON public.rl_training_data;

DROP POLICY IF EXISTS "Users can view their own logs" ON public.logs;
DROP POLICY IF EXISTS "Service role can insert logs" ON public.logs;

-- User profiles
CREATE POLICY "Users can view their own profile" ON public.user_profiles
    FOR SELECT USING (auth.uid() = id);
CREATE POLICY "Users can update their own profile" ON public.user_profiles
    FOR UPDATE USING (auth.uid() = id);
CREATE POLICY "Users can insert their own profile" ON public.user_profiles
    FOR INSERT WITH CHECK (auth.uid() = id);

-- Videos
CREATE POLICY "Users can view their own videos" ON public.videos
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert their own videos" ON public.videos
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update their own videos" ON public.videos
    FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete their own videos" ON public.videos
    FOR DELETE USING (auth.uid() = user_id);

-- Events
CREATE POLICY "Users can view their own events" ON public.events
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert their own events" ON public.events
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update their own events" ON public.events
    FOR UPDATE USING (auth.uid() = user_id);

-- User settings
CREATE POLICY "Users can view their own settings" ON public.user_settings
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert their own settings" ON public.user_settings
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update their own settings" ON public.user_settings
    FOR UPDATE USING (auth.uid() = user_id);

-- Historical patterns
CREATE POLICY "Users can view their own patterns" ON public.historical_patterns
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert their own patterns" ON public.historical_patterns
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update their own patterns" ON public.historical_patterns
    FOR UPDATE USING (auth.uid() = user_id);

-- RL training data
CREATE POLICY "Users can view their own RL data" ON public.rl_training_data
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert their own RL data" ON public.rl_training_data
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Logs (server-side inserts use the service-role key and bypass RLS;
-- these policies only govern anon/authenticated access)
CREATE POLICY "Users can view their own logs" ON public.logs
    FOR SELECT USING (auth.uid() = user_id OR user_id IS NULL);
CREATE POLICY "Service role can insert logs" ON public.logs
    FOR INSERT WITH CHECK (true);

-- ============================================================================
-- 10. HELPER FUNCTIONS
-- ============================================================================

-- Single canonical signature: (user_id, anomaly_threshold, frame_sampling_rate,
-- auto_delete_old_videos, video_retention_days). Drop first since prior
-- versions of this script defined different RETURNS TABLE shapes, and
-- Postgres will not let CREATE OR REPLACE change a function's return type.
DROP FUNCTION IF EXISTS public.get_user_settings(UUID);

CREATE FUNCTION public.get_user_settings(p_user_id UUID)
RETURNS TABLE (
    user_id UUID,
    anomaly_threshold REAL,
    frame_sampling_rate INTEGER,
    auto_delete_old_videos BOOLEAN,
    video_retention_days INTEGER
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        COALESCE(us.user_id, p_user_id) as user_id,
        COALESCE(us.anomaly_threshold, 0.5::REAL) as anomaly_threshold,
        COALESCE(us.frame_sampling_rate, 10) as frame_sampling_rate,
        COALESCE(us.auto_delete_old_videos, FALSE) as auto_delete_old_videos,
        COALESCE(us.video_retention_days, 30) as video_retention_days
    FROM public.user_settings us
    WHERE us.user_id = p_user_id
    UNION ALL
    SELECT
        p_user_id as user_id,
        0.5::REAL as anomaly_threshold,
        10 as frame_sampling_rate,
        FALSE as auto_delete_old_videos,
        30 as video_retention_days
    WHERE NOT EXISTS (SELECT 1 FROM public.user_settings WHERE user_id = p_user_id)
    LIMIT 1;
END;
$$;

-- Drop before create for all remaining helper functions too: any of them may
-- already exist in a given database with a different signature from an
-- earlier setup script, and CREATE OR REPLACE cannot change a function's
-- return type (it can only be swapped by dropping it first).
DROP FUNCTION IF EXISTS public.get_verified_user_profile(UUID);

CREATE FUNCTION public.get_verified_user_profile(p_user_id UUID)
RETURNS TABLE (
    id UUID,
    email TEXT,
    full_name TEXT,
    avatar_url TEXT,
    is_system_user BOOLEAN,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        up.id,
        up.email,
        up.full_name,
        up.avatar_url,
        up.is_system_user,
        up.created_at,
        up.updated_at
    FROM public.user_profiles up
    WHERE up.id = p_user_id;
END;
$$;

DROP FUNCTION IF EXISTS public.update_video_storage(UUID, TEXT, TEXT, TEXT, TEXT);

CREATE FUNCTION public.update_video_storage(
    p_video_id UUID,
    p_storage_provider TEXT,
    p_file_path TEXT,
    p_file_url TEXT DEFAULT NULL,
    p_storage_id TEXT DEFAULT NULL
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    UPDATE public.videos
    SET
        storage_provider = p_storage_provider,
        file_path = p_file_path,
        file_url = p_file_url,
        storage_id = p_storage_id,
        updated_at = NOW()
    WHERE id = p_video_id;

    RETURN FOUND;
END;
$$;

DROP FUNCTION IF EXISTS public.cleanup_old_videos(UUID, INTEGER);

CREATE FUNCTION public.cleanup_old_videos(p_user_id UUID, p_retention_days INTEGER)
RETURNS TABLE (deleted_count INTEGER, space_freed BIGINT)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    deleted_videos INTEGER := 0;
    total_size BIGINT := 0;
BEGIN
    SELECT COALESCE(SUM(file_size), 0) INTO total_size
    FROM public.videos
    WHERE user_id = p_user_id
    AND created_at < NOW() - INTERVAL '1 day' * p_retention_days;

    WITH deleted AS (
        DELETE FROM public.videos
        WHERE user_id = p_user_id
        AND created_at < NOW() - INTERVAL '1 day' * p_retention_days
        RETURNING id
    )
    SELECT COUNT(*) INTO deleted_videos FROM deleted;

    RETURN QUERY SELECT deleted_videos, total_size;
END;
$$;

-- ============================================================================
-- 11. STORAGE BUCKET
-- ============================================================================

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'videos',
    'videos',
    false,
    104857600, -- 100MB
    ARRAY['video/mp4', 'video/avi', 'video/mov', 'video/wmv', 'video/flv', 'video/webm']
)
ON CONFLICT (id) DO UPDATE SET
    file_size_limit = EXCLUDED.file_size_limit,
    allowed_mime_types = EXCLUDED.allowed_mime_types;

-- ============================================================================
-- 12. GRANTS
-- ============================================================================

GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;

GRANT ALL ON public.user_profiles TO anon, authenticated, service_role;
GRANT ALL ON public.videos TO anon, authenticated, service_role;
GRANT ALL ON public.events TO anon, authenticated, service_role;
GRANT ALL ON public.user_settings TO anon, authenticated, service_role;
GRANT ALL ON public.historical_patterns TO anon, authenticated, service_role;
GRANT ALL ON public.rl_training_data TO anon, authenticated, service_role;
GRANT ALL ON public.logs TO anon, authenticated, service_role;

GRANT EXECUTE ON FUNCTION public.get_user_settings(UUID) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_verified_user_profile(UUID) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.update_video_storage(UUID, TEXT, TEXT, TEXT, TEXT) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.cleanup_old_videos(UUID, INTEGER) TO authenticated, service_role;

GRANT ALL ON storage.buckets TO service_role;
GRANT ALL ON storage.objects TO service_role;

-- ============================================================================
-- 13. UPDATED_AT TRIGGERS
-- ============================================================================

CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_user_profiles_updated_at ON public.user_profiles;
CREATE TRIGGER update_user_profiles_updated_at
    BEFORE UPDATE ON public.user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_videos_updated_at ON public.videos;
CREATE TRIGGER update_videos_updated_at
    BEFORE UPDATE ON public.videos
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_user_settings_updated_at ON public.user_settings;
CREATE TRIGGER update_user_settings_updated_at
    BEFORE UPDATE ON public.user_settings
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================================
-- 14. VERIFICATION
-- ============================================================================

DO $$
DECLARE
    table_count INTEGER;
    function_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name IN ('user_profiles', 'videos', 'events', 'user_settings', 'historical_patterns', 'rl_training_data', 'logs');

    SELECT COUNT(*) INTO function_count
    FROM information_schema.routines
    WHERE routine_schema = 'public'
    AND routine_name IN ('get_user_settings', 'get_verified_user_profile', 'update_video_storage', 'cleanup_old_videos');

    RAISE NOTICE 'Setup verification: % tables, % functions', table_count, function_count;

    IF table_count = 7 AND function_count = 4 THEN
        RAISE NOTICE 'AutoVision database schema applied successfully!';
    ELSE
        RAISE WARNING 'Expected 7 tables and 4 functions, found % tables and % functions.', table_count, function_count;
    END IF;
END $$;

SELECT 'AUTOVISION SCHEMA APPLIED' as status;

SELECT tablename FROM pg_tables
WHERE schemaname = 'public'
AND tablename IN ('user_profiles', 'videos', 'events', 'user_settings', 'historical_patterns', 'rl_training_data', 'logs')
ORDER BY tablename;

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
