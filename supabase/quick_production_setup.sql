-- ============================================================================
-- AUTOVISION QUICK PRODUCTION SETUP
-- ============================================================================
-- Minimal script for quick deployment - includes only essential components
-- Run this first, then use complete_production_setup.sql for full features
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- ESSENTIAL TABLES
-- ============================================================================

-- 1. User profiles (required for authentication)
CREATE TABLE IF NOT EXISTS public.user_profiles (
    id UUID REFERENCES auth.users(id) PRIMARY KEY,
    email TEXT NOT NULL,
    full_name TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Videos (core functionality)
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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Events (anomaly detection results)
CREATE TABLE IF NOT EXISTS public.events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    video_id UUID REFERENCES public.videos(id) ON DELETE CASCADE NOT NULL,
    user_id UUID REFERENCES auth.users(id) NOT NULL,
    event_type TEXT NOT NULL,
    anomaly_score REAL NOT NULL DEFAULT 0.0,
    confidence REAL NOT NULL DEFAULT 0.0,
    timestamp_seconds REAL NOT NULL,
    frame_number INTEGER NOT NULL,
    description TEXT,
    is_alert BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. User settings (essential for operation)
CREATE TABLE IF NOT EXISTS public.user_settings (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) UNIQUE NOT NULL,
    anomaly_threshold REAL DEFAULT 0.5,
    frame_sampling_rate INTEGER DEFAULT 10,
    auto_delete_old_videos BOOLEAN DEFAULT FALSE,
    video_retention_days INTEGER DEFAULT 30,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- ESSENTIAL INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_videos_user_id ON public.videos(user_id);
CREATE INDEX IF NOT EXISTS idx_videos_status ON public.videos(upload_status);
CREATE INDEX IF NOT EXISTS idx_events_video_id ON public.events(video_id);
CREATE INDEX IF NOT EXISTS idx_events_user_id ON public.events(user_id);
CREATE INDEX IF NOT EXISTS idx_user_settings_user_id ON public.user_settings(user_id);

-- ============================================================================
-- ROW LEVEL SECURITY
-- ============================================================================

ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_settings ENABLE ROW LEVEL SECURITY;

-- Simple RLS policies
CREATE POLICY "Users own data" ON public.user_profiles FOR ALL USING (auth.uid() = id);
CREATE POLICY "Users own videos" ON public.videos FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users own events" ON public.events FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users own settings" ON public.user_settings FOR ALL USING (auth.uid() = user_id);

-- ============================================================================
-- ESSENTIAL FUNCTIONS
-- ============================================================================

-- Get user settings with defaults
CREATE OR REPLACE FUNCTION public.get_user_settings(p_user_id UUID)
RETURNS TABLE (
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
        COALESCE(us.anomaly_threshold, 0.5::REAL),
        COALESCE(us.frame_sampling_rate, 10),
        COALESCE(us.auto_delete_old_videos, FALSE),
        COALESCE(us.video_retention_days, 30)
    FROM public.user_settings us
    WHERE us.user_id = p_user_id
    UNION ALL
    SELECT 0.5::REAL, 10, FALSE, 30
    WHERE NOT EXISTS (SELECT 1 FROM public.user_settings WHERE user_id = p_user_id)
    LIMIT 1;
END;
$$;

-- ============================================================================
-- PERMISSIONS
-- ============================================================================

GRANT ALL ON public.user_profiles TO anon, authenticated, service_role;
GRANT ALL ON public.videos TO anon, authenticated, service_role;
GRANT ALL ON public.events TO anon, authenticated, service_role;
GRANT ALL ON public.user_settings TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_user_settings(UUID) TO anon, authenticated, service_role;

-- ============================================================================
-- STORAGE BUCKET
-- ============================================================================

-- Create videos bucket (may require dashboard/API)
INSERT INTO storage.buckets (id, name, public)
VALUES ('videos', 'videos', false)
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

SELECT 'AutoVision Quick Setup Complete!' as status;
SELECT COUNT(*) as tables_created FROM information_schema.tables 
WHERE table_schema = 'public' AND table_name IN ('user_profiles', 'videos', 'events', 'user_settings');

-- ============================================================================
-- READY FOR PRODUCTION
-- ============================================================================
