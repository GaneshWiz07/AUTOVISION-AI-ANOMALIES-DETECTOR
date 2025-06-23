-- ============================================================================
-- AUTOVISION COMPLETE PRODUCTION DATABASE SETUP
-- ============================================================================
-- This script sets up the complete AutoVision database schema for production
-- Run this on a fresh Supabase instance to get everything working
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- 1. USER PROFILES TABLE
-- ============================================================================

-- Create user_profiles table if it doesn't exist
CREATE TABLE IF NOT EXISTS public.user_profiles (
    id UUID REFERENCES auth.users(id) PRIMARY KEY,
    email TEXT NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    is_system_user BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add any missing columns to existing user_profiles
ALTER TABLE public.user_profiles 
    ADD COLUMN IF NOT EXISTS email TEXT,
    ADD COLUMN IF NOT EXISTS full_name TEXT,
    ADD COLUMN IF NOT EXISTS avatar_url TEXT,
    ADD COLUMN IF NOT EXISTS is_system_user BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- ============================================================================
-- 2. VIDEOS TABLE WITH STORAGE SUPPORT
-- ============================================================================

-- Create videos table with all necessary columns
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
    storage_provider TEXT DEFAULT 'local' CHECK (storage_provider IN ('local', 'supabase')),
    storage_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add any missing columns to existing videos table
ALTER TABLE public.videos 
    ADD COLUMN IF NOT EXISTS file_url TEXT,
    ADD COLUMN IF NOT EXISTS storage_provider TEXT DEFAULT 'local',
    ADD COLUMN IF NOT EXISTS storage_id TEXT;

-- Update storage provider constraint if it exists
ALTER TABLE public.videos DROP CONSTRAINT IF EXISTS videos_storage_provider_check;
ALTER TABLE public.videos ADD CONSTRAINT videos_storage_provider_check 
    CHECK (storage_provider IN ('local', 'supabase'));

-- ============================================================================
-- 3. EVENTS TABLE FOR ANOMALY DETECTION
-- ============================================================================

-- Create events table
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
    is_alert BOOLEAN DEFAULT FALSE,
    is_false_positive BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- 4. USER SETTINGS TABLE
-- ============================================================================

-- Create user_settings table
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
-- 5. HISTORICAL PATTERNS TABLE (RAG SYSTEM)
-- ============================================================================

-- Create historical_patterns table for RAG system
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
-- 6. RL TRAINING DATA TABLE
-- ============================================================================

-- Create RL training data table
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
-- 7. LOGS TABLE FOR SYSTEM MONITORING
-- ============================================================================

-- Create logs table
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
-- 8. INDEXES FOR PERFORMANCE
-- ============================================================================

-- User profiles indexes
CREATE INDEX IF NOT EXISTS idx_user_profiles_email ON public.user_profiles(email);

-- Videos indexes
CREATE INDEX IF NOT EXISTS idx_videos_user_id ON public.videos(user_id);
CREATE INDEX IF NOT EXISTS idx_videos_created_at ON public.videos(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_videos_status ON public.videos(upload_status);
CREATE INDEX IF NOT EXISTS idx_videos_storage_provider ON public.videos(storage_provider);

-- Events indexes
CREATE INDEX IF NOT EXISTS idx_events_video_id ON public.events(video_id);
CREATE INDEX IF NOT EXISTS idx_events_user_id ON public.events(user_id);
CREATE INDEX IF NOT EXISTS idx_events_created_at ON public.events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_anomaly_score ON public.events(anomaly_score DESC);
CREATE INDEX IF NOT EXISTS idx_events_event_type ON public.events(event_type);

-- User settings indexes
CREATE INDEX IF NOT EXISTS idx_user_settings_user_id ON public.user_settings(user_id);

-- Historical patterns indexes
CREATE INDEX IF NOT EXISTS idx_patterns_user_id ON public.historical_patterns(user_id);
CREATE INDEX IF NOT EXISTS idx_patterns_type ON public.historical_patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_patterns_frequency ON public.historical_patterns(frequency_count DESC);

-- RL training data indexes
CREATE INDEX IF NOT EXISTS idx_rl_data_user_id ON public.rl_training_data(user_id);
CREATE INDEX IF NOT EXISTS idx_rl_data_created_at ON public.rl_training_data(created_at DESC);

-- Logs indexes
CREATE INDEX IF NOT EXISTS idx_logs_created_at ON public.logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_logs_user_id ON public.logs(user_id);
CREATE INDEX IF NOT EXISTS idx_logs_log_level ON public.logs(log_level);

-- ============================================================================
-- 9. ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.historical_patterns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rl_training_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.logs ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Users can view their own profile" ON public.user_profiles;
DROP POLICY IF EXISTS "Users can update their own profile" ON public.user_profiles;
DROP POLICY IF EXISTS "Users can insert their own profile" ON public.user_profiles;

DROP POLICY IF EXISTS "Users can view their own videos" ON public.videos;
DROP POLICY IF EXISTS "Users can insert their own videos" ON public.videos;
DROP POLICY IF EXISTS "Users can update their own videos" ON public.videos;
DROP POLICY IF EXISTS "Users can delete their own videos" ON public.videos;

DROP POLICY IF EXISTS "Users can view their own events" ON public.events;
DROP POLICY IF EXISTS "Users can insert their own events" ON public.events;
DROP POLICY IF EXISTS "Users can update their own events" ON public.events;

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

-- User profiles policies
CREATE POLICY "Users can view their own profile" ON public.user_profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update their own profile" ON public.user_profiles
    FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Users can insert their own profile" ON public.user_profiles
    FOR INSERT WITH CHECK (auth.uid() = id);

-- Videos policies
CREATE POLICY "Users can view their own videos" ON public.videos
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own videos" ON public.videos
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own videos" ON public.videos
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own videos" ON public.videos
    FOR DELETE USING (auth.uid() = user_id);

-- Events policies
CREATE POLICY "Users can view their own events" ON public.events
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own events" ON public.events
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own events" ON public.events
    FOR UPDATE USING (auth.uid() = user_id);

-- User settings policies
CREATE POLICY "Users can view their own settings" ON public.user_settings
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own settings" ON public.user_settings
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own settings" ON public.user_settings
    FOR UPDATE USING (auth.uid() = user_id);

-- Historical patterns policies
CREATE POLICY "Users can view their own patterns" ON public.historical_patterns
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own patterns" ON public.historical_patterns
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own patterns" ON public.historical_patterns
    FOR UPDATE USING (auth.uid() = user_id);

-- RL training data policies
CREATE POLICY "Users can view their own RL data" ON public.rl_training_data
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own RL data" ON public.rl_training_data
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Logs policies (more permissive for system operations)
CREATE POLICY "Users can view their own logs" ON public.logs
    FOR SELECT USING (auth.uid() = user_id OR user_id IS NULL);

CREATE POLICY "Service role can insert logs" ON public.logs
    FOR INSERT WITH CHECK (true);

-- ============================================================================
-- 10. HELPER FUNCTIONS
-- ============================================================================

-- Function to get user settings with defaults
CREATE OR REPLACE FUNCTION public.get_user_settings(p_user_id UUID)
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

-- Function to get verified user profile
CREATE OR REPLACE FUNCTION public.get_verified_user_profile(p_user_id UUID)
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

-- Function to update video storage info
CREATE OR REPLACE FUNCTION public.update_video_storage(
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

-- ============================================================================
-- 11. STORAGE BUCKET SETUP
-- ============================================================================

-- Note: Storage buckets are typically created via the Supabase Dashboard or API
-- But we can ensure the videos bucket exists with proper configuration

-- Insert bucket if it doesn't exist (this may require superuser privileges)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'videos',
    'videos',
    false,
    104857600, -- 100MB limit
    ARRAY['video/mp4', 'video/avi', 'video/mov', 'video/wmv', 'video/flv', 'video/webm']
)
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- 12. PERMISSIONS AND GRANTS
-- ============================================================================

-- Grant necessary permissions to authenticated users
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;

-- Table permissions
GRANT ALL ON public.user_profiles TO anon, authenticated, service_role;
GRANT ALL ON public.videos TO anon, authenticated, service_role;
GRANT ALL ON public.events TO anon, authenticated, service_role;
GRANT ALL ON public.user_settings TO anon, authenticated, service_role;
GRANT ALL ON public.historical_patterns TO anon, authenticated, service_role;
GRANT ALL ON public.rl_training_data TO anon, authenticated, service_role;
GRANT ALL ON public.logs TO anon, authenticated, service_role;

-- Function permissions
GRANT EXECUTE ON FUNCTION public.get_user_settings(UUID) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_verified_user_profile(UUID) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.update_video_storage(UUID, TEXT, TEXT, TEXT, TEXT) TO anon, authenticated, service_role;

-- Storage permissions
GRANT ALL ON storage.buckets TO anon, authenticated, service_role;
GRANT ALL ON storage.objects TO anon, authenticated, service_role;

-- ============================================================================
-- 13. TRIGGERS FOR AUTOMATIC TIMESTAMPS
-- ============================================================================

-- Create trigger function for updating timestamps
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add triggers for updated_at columns
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
-- 14. VERIFICATION AND TESTING
-- ============================================================================

-- Test the setup by checking table existence and basic functionality
DO $$
DECLARE
    table_count INTEGER;
    function_count INTEGER;
BEGIN
    -- Count tables
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name IN ('user_profiles', 'videos', 'events', 'user_settings', 'historical_patterns', 'rl_training_data', 'logs');
    
    -- Count functions
    SELECT COUNT(*) INTO function_count
    FROM information_schema.routines
    WHERE routine_schema = 'public'
    AND routine_name IN ('get_user_settings', 'get_verified_user_profile', 'update_video_storage');
    
    -- Log results
    RAISE NOTICE 'Setup verification: % tables created, % functions created', table_count, function_count;
    
    IF table_count = 7 AND function_count = 3 THEN
        RAISE NOTICE 'AutoVision database setup completed successfully!';
    ELSE
        RAISE WARNING 'Some components may not have been created properly. Expected 7 tables and 3 functions.';
    END IF;
END $$;

-- ============================================================================
-- 15. FINAL STATUS AND SUMMARY
-- ============================================================================

-- Display summary of what was created
SELECT 'AUTOVISION DATABASE SETUP COMPLETE!' as status;

SELECT 
    schemaname,
    tablename,
    tableowner
FROM pg_tables 
WHERE schemaname = 'public' 
AND tablename IN ('user_profiles', 'videos', 'events', 'user_settings', 'historical_patterns', 'rl_training_data', 'logs')
ORDER BY tablename;

-- Display available functions
SELECT 
    routine_name,
    routine_type
FROM information_schema.routines
WHERE routine_schema = 'public'
AND routine_name IN ('get_user_settings', 'get_verified_user_profile', 'update_video_storage');

-- Final message
SELECT 'AutoVision is now ready for production deployment!' as final_message;
SELECT 'You can now: 1) Sign up users 2) Upload videos 3) Process videos 4) Store events 5) Manage settings' as capabilities;

-- ============================================================================
-- END OF SCRIPT
-- ============================================================================
