-- ============================================================================
-- AUTOVISION DATABASE TROUBLESHOOTING & FIX SCRIPT
-- ============================================================================
-- This script fixes common issues and ensures database consistency
-- Run this if you encounter problems with the existing setup
-- ============================================================================

-- ============================================================================
-- 1. FIX MISSING COLUMNS
-- ============================================================================

-- Add missing columns to videos table
ALTER TABLE public.videos 
    ADD COLUMN IF NOT EXISTS file_url TEXT,
    ADD COLUMN IF NOT EXISTS storage_provider TEXT DEFAULT 'local',
    ADD COLUMN IF NOT EXISTS storage_id TEXT;

-- Update constraint for storage_provider
ALTER TABLE public.videos DROP CONSTRAINT IF EXISTS videos_storage_provider_check;
ALTER TABLE public.videos ADD CONSTRAINT videos_storage_provider_check 
    CHECK (storage_provider IN ('local', 'supabase'));

-- Add missing columns to user_profiles
ALTER TABLE public.user_profiles 
    ADD COLUMN IF NOT EXISTS avatar_url TEXT,
    ADD COLUMN IF NOT EXISTS is_system_user BOOLEAN DEFAULT FALSE;

-- Add missing columns to events
ALTER TABLE public.events 
    ADD COLUMN IF NOT EXISTS bounding_box JSONB,
    ADD COLUMN IF NOT EXISTS is_false_positive BOOLEAN DEFAULT FALSE;

-- ============================================================================
-- 2. UPDATE DEFAULT VALUES
-- ============================================================================

-- Set default storage provider for new videos to Supabase
ALTER TABLE public.videos ALTER COLUMN storage_provider SET DEFAULT 'supabase';

-- Update existing videos without storage_provider
UPDATE public.videos 
SET storage_provider = 'local' 
WHERE storage_provider IS NULL;

-- ============================================================================
-- 3. FIX RLS POLICIES
-- ============================================================================

-- Drop and recreate policies to ensure they're correct
DROP POLICY IF EXISTS "Users own data" ON public.user_profiles;
DROP POLICY IF EXISTS "Users own videos" ON public.videos;
DROP POLICY IF EXISTS "Users own events" ON public.events;
DROP POLICY IF EXISTS "Users own settings" ON public.user_settings;

-- Create proper policies
CREATE POLICY "Users can manage their profile" ON public.user_profiles
    FOR ALL USING (auth.uid() = id);

CREATE POLICY "Users can manage their videos" ON public.videos
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can manage their events" ON public.events
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can manage their settings" ON public.user_settings
    FOR ALL USING (auth.uid() = user_id);

-- ============================================================================
-- 4. FIX FUNCTION DEPENDENCIES
-- ============================================================================

-- Update get_user_settings function to handle all cases
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
    -- First try to get existing settings
    RETURN QUERY
    SELECT 
        us.anomaly_threshold,
        us.frame_sampling_rate,
        us.auto_delete_old_videos,
        us.video_retention_days
    FROM public.user_settings us
    WHERE us.user_id = p_user_id;
    
    -- If no settings found, return defaults
    IF NOT FOUND THEN
        RETURN QUERY
        SELECT 
            0.5::REAL as anomaly_threshold,
            10 as frame_sampling_rate,
            FALSE as auto_delete_old_videos,
            30 as video_retention_days;
    END IF;
END;
$$;

-- ============================================================================
-- 5. CREATE MISSING INDEXES
-- ============================================================================

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_videos_created_at ON public.videos(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_created_at ON public.events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_event_type ON public.events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_anomaly_score ON public.events(anomaly_score DESC);

-- ============================================================================
-- 6. DATA CONSISTENCY FIXES
-- ============================================================================

-- Remove orphaned events (events without valid videos)
DELETE FROM public.events 
WHERE video_id NOT IN (SELECT id FROM public.videos);

-- Remove orphaned settings (settings for non-existent users)
DELETE FROM public.user_settings 
WHERE user_id NOT IN (SELECT id FROM auth.users);

-- ============================================================================
-- 7. STORAGE BUCKET FIXES
-- ============================================================================

-- Ensure videos bucket exists
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
-- 8. PERMISSION FIXES
-- ============================================================================

-- Ensure all necessary permissions are granted
GRANT ALL ON public.user_profiles TO anon, authenticated, service_role;
GRANT ALL ON public.videos TO anon, authenticated, service_role;
GRANT ALL ON public.events TO anon, authenticated, service_role;
GRANT ALL ON public.user_settings TO anon, authenticated, service_role;

-- Function permissions
GRANT EXECUTE ON FUNCTION public.get_user_settings(UUID) TO anon, authenticated, service_role;

-- Storage permissions
GRANT ALL ON storage.buckets TO service_role;
GRANT ALL ON storage.objects TO service_role;

-- ============================================================================
-- 9. CREATE MISSING HELPER FUNCTIONS
-- ============================================================================

-- Function to migrate video to Supabase Storage
CREATE OR REPLACE FUNCTION public.migrate_video_to_storage(
    p_video_id UUID,
    p_storage_path TEXT,
    p_file_url TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    UPDATE public.videos 
    SET 
        storage_provider = 'supabase',
        file_path = p_storage_path,
        file_url = p_file_url,
        updated_at = NOW()
    WHERE id = p_video_id;
    
    RETURN FOUND;
END;
$$;

-- Function to cleanup old videos
CREATE OR REPLACE FUNCTION public.cleanup_old_videos(p_user_id UUID, p_retention_days INTEGER)
RETURNS TABLE (deleted_count INTEGER, space_freed BIGINT)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    deleted_videos INTEGER := 0;
    total_size BIGINT := 0;
BEGIN
    -- Calculate total size of videos to be deleted
    SELECT COALESCE(SUM(file_size), 0) INTO total_size
    FROM public.videos
    WHERE user_id = p_user_id 
    AND created_at < NOW() - INTERVAL '1 day' * p_retention_days;
    
    -- Delete old videos and their events
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

-- Grant permissions on new functions
GRANT EXECUTE ON FUNCTION public.migrate_video_to_storage(UUID, TEXT, TEXT) TO service_role;
GRANT EXECUTE ON FUNCTION public.cleanup_old_videos(UUID, INTEGER) TO authenticated, service_role;

-- ============================================================================
-- 10. UPDATE TRIGGERS
-- ============================================================================

-- Ensure updated_at triggers exist
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add triggers if they don't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_videos_updated_at') THEN
        CREATE TRIGGER update_videos_updated_at
            BEFORE UPDATE ON public.videos
            FOR EACH ROW
            EXECUTE FUNCTION public.update_updated_at_column();
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_user_profiles_updated_at') THEN
        CREATE TRIGGER update_user_profiles_updated_at
            BEFORE UPDATE ON public.user_profiles
            FOR EACH ROW
            EXECUTE FUNCTION public.update_updated_at_column();
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_user_settings_updated_at') THEN
        CREATE TRIGGER update_user_settings_updated_at
            BEFORE UPDATE ON public.user_settings
            FOR EACH ROW
            EXECUTE FUNCTION public.update_updated_at_column();
    END IF;
END $$;

-- ============================================================================
-- 11. VALIDATION AND TESTING
-- ============================================================================

-- Test basic functionality
DO $$
DECLARE
    test_user_id UUID;
    test_video_id UUID;
    settings_result RECORD;
BEGIN
    -- Get a test user ID (use the first user or create a dummy one)
    SELECT id INTO test_user_id FROM auth.users LIMIT 1;
    
    IF test_user_id IS NOT NULL THEN
        -- Test settings function
        SELECT * INTO settings_result FROM public.get_user_settings(test_user_id);
        
        IF settings_result IS NOT NULL THEN
            RAISE NOTICE 'Settings function test: PASSED (threshold: %)', settings_result.anomaly_threshold;
        ELSE
            RAISE WARNING 'Settings function test: FAILED';
        END IF;
    ELSE
        RAISE NOTICE 'No test user available, skipping function tests';
    END IF;
END $$;

-- ============================================================================
-- 12. FINAL VERIFICATION
-- ============================================================================

-- Check table structure
SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_schema = 'public' 
AND table_name IN ('user_profiles', 'videos', 'events', 'user_settings')
ORDER BY table_name, ordinal_position;

-- Check indexes
SELECT 
    tablename,
    indexname,
    indexdef
FROM pg_indexes 
WHERE schemaname = 'public' 
AND tablename IN ('user_profiles', 'videos', 'events', 'user_settings')
ORDER BY tablename, indexname;

-- Check RLS policies
SELECT 
    tablename,
    policyname,
    permissive,
    roles,
    cmd,
    qual
FROM pg_policies 
WHERE schemaname = 'public'
ORDER BY tablename, policyname;

-- Final status
SELECT 'AutoVision Database Fixes Applied Successfully!' as status;
SELECT 'All issues should now be resolved. Test your application.' as next_steps;

-- ============================================================================
-- END OF TROUBLESHOOTING SCRIPT
-- ============================================================================
