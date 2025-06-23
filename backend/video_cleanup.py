"""
Video cleanup module for AutoVision
Handles automatic deletion of old videos based on user settings
"""

import os
import shutil
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from loguru import logger
from pathlib import Path

from backend.autovision_client import supabase_client


class VideoCleanupService:
    """Service for cleaning up old videos based on user settings"""
    
    def __init__(self):
        self.client = supabase_client.get_admin_client()
        logger.info("Video cleanup service initialized")
    
    async def cleanup_old_videos(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Clean up old videos based on user settings
        
        Args:
            user_id: If provided, cleanup only for this user. Otherwise cleanup for all users.
            
        Returns:
            Dict with cleanup statistics
        """
        try:
            cleanup_stats = {
                "users_processed": 0,
                "videos_deleted": 0,
                "files_deleted": 0,
                "space_freed_mb": 0,
                "errors": []
            }
            
            # Get users with auto-delete enabled
            if user_id:
                users_query = self.client.table("user_settings").select("user_id, video_retention_days").eq("user_id", user_id).eq("auto_delete_old_videos", True)
            else:
                users_query = self.client.table("user_settings").select("user_id, video_retention_days").eq("auto_delete_old_videos", True)
            
            users_result = users_query.execute()
            
            if not users_result.data:
                logger.info("No users with auto-delete enabled found")
                return cleanup_stats
            
            for user_settings in users_result.data:
                user_id = user_settings["user_id"]
                retention_days = user_settings["video_retention_days"]
                
                try:
                    user_stats = await self._cleanup_user_videos(user_id, retention_days)
                    cleanup_stats["users_processed"] += 1
                    cleanup_stats["videos_deleted"] += user_stats["videos_deleted"]
                    cleanup_stats["files_deleted"] += user_stats["files_deleted"]
                    cleanup_stats["space_freed_mb"] += user_stats["space_freed_mb"]
                    
                except Exception as e:
                    error_msg = f"Failed to cleanup videos for user {user_id}: {e}"
                    logger.error(error_msg)
                    cleanup_stats["errors"].append(error_msg)
            
            logger.info(f"Video cleanup completed: {cleanup_stats}")
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"Error in video cleanup: {e}")
            raise
    
    async def _cleanup_user_videos(self, user_id: str, retention_days: int) -> Dict[str, Any]:
        """Clean up videos for a specific user"""
        
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        cutoff_str = cutoff_date.isoformat()
        
        logger.info(f"Cleaning up videos for user {user_id} older than {cutoff_str}")
        
        # Get old videos for this user
        videos_result = self.client.table("videos").select("*").eq("user_id", user_id).lt("created_at", cutoff_str).execute()
        
        if not videos_result.data:
            logger.info(f"No old videos found for user {user_id}")
            return {"videos_deleted": 0, "files_deleted": 0, "space_freed_mb": 0}
        
        stats = {"videos_deleted": 0, "files_deleted": 0, "space_freed_mb": 0}
        
        for video in videos_result.data:
            try:
                video_id = video["id"]
                file_path = video.get("file_path")
                file_size = video.get("file_size", 0)
                
                # Delete associated events first
                self.client.table("events").delete().eq("video_id", video_id).execute()
                logger.info(f"Deleted events for video {video_id}")
                  # Delete video file based on storage provider
                storage_provider = video.get("storage_provider")
                
                if storage_provider == "supabase" and file_path:
                    try:
                        # Parse the storage path (format: "bucket/path")
                        storage_parts = file_path.split('/', 1)
                        if len(storage_parts) == 2:
                            bucket = storage_parts[0]
                            path = storage_parts[1]
                            
                            # Delete from Supabase Storage
                            self.client.storage.from_(bucket).remove(path)
                            stats["files_deleted"] += 1
                            stats["space_freed_mb"] += file_size / (1024 * 1024)  # Convert to MB
                            logger.info(f"Deleted file from Supabase Storage: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to delete file from Supabase Storage {file_path}: {e}")
                # Fallback for local files (backward compatibility)
                elif file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        stats["files_deleted"] += 1
                        stats["space_freed_mb"] += file_size / (1024 * 1024)  # Convert to MB
                        logger.info(f"Deleted local file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to delete local file {file_path}: {e}")
                
                # Delete video record from database
                self.client.table("videos").delete().eq("id", video_id).execute()
                stats["videos_deleted"] += 1
                logger.info(f"Deleted video record: {video_id}")
                
            except Exception as e:
                logger.error(f"Failed to delete video {video.get('id', 'unknown')}: {e}")
                continue
        
        logger.info(f"User {user_id} cleanup completed: {stats}")
        return stats
    
    async def cleanup_user_videos_manual(self, user_id: str) -> Dict[str, Any]:
        """Manually trigger cleanup for a specific user"""
        try:
            # Get user settings
            settings_result = self.client.table("user_settings").select("video_retention_days, auto_delete_old_videos").eq("user_id", user_id).execute()
            
            if not settings_result.data:
                raise ValueError("User settings not found")
            
            settings = settings_result.data[0]
            
            if not settings.get("auto_delete_old_videos", False):
                raise ValueError("Auto-delete is not enabled for this user")
            
            retention_days = settings.get("video_retention_days", 30)
            
            return await self._cleanup_user_videos(user_id, retention_days)
            
        except Exception as e:
            logger.error(f"Error in manual cleanup for user {user_id}: {e}")
            raise
    
    async def get_cleanup_preview(self, user_id: str) -> Dict[str, Any]:
        """Get a preview of what would be cleaned up without actually deleting"""
        try:
            # Get user settings
            settings_result = self.client.table("user_settings").select("video_retention_days, auto_delete_old_videos").eq("user_id", user_id).execute()
            
            if not settings_result.data:
                return {"error": "User settings not found"}
            
            settings = settings_result.data[0]
            
            if not settings.get("auto_delete_old_videos", False):
                return {"videos_to_delete": 0, "space_to_free_mb": 0, "message": "Auto-delete is not enabled"}
            
            retention_days = settings.get("video_retention_days", 30)
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            cutoff_str = cutoff_date.isoformat()
            
            # Get old videos for this user
            videos_result = self.client.table("videos").select("id, original_name, file_size, created_at").eq("user_id", user_id).lt("created_at", cutoff_str).execute()
            
            if not videos_result.data:
                return {"videos_to_delete": 0, "space_to_free_mb": 0, "message": "No old videos to delete"}
            
            total_size = sum(video.get("file_size", 0) for video in videos_result.data)
            
            return {
                "videos_to_delete": len(videos_result.data),
                "space_to_free_mb": round(total_size / (1024 * 1024), 2),
                "cutoff_date": cutoff_str,
                "retention_days": retention_days,
                "videos": [
                    {
                        "id": video["id"],
                        "name": video["original_name"],
                        "size_mb": round(video.get("file_size", 0) / (1024 * 1024), 2),
                        "created_at": video["created_at"]
                    }
                    for video in videos_result.data
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting cleanup preview for user {user_id}: {e}")
            return {"error": str(e)}


# Global instance
video_cleanup_service = VideoCleanupService()


async def run_scheduled_cleanup():
    """Run scheduled cleanup for all users with auto-delete enabled"""
    logger.info("Starting scheduled video cleanup")
    try:
        result = await video_cleanup_service.cleanup_old_videos()
        logger.info(f"Scheduled cleanup completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Scheduled cleanup failed: {e}")
        raise
