"""
Supabase client configuration and utilities for AutoVision
"""
import os
from typing import Optional, Dict, Any, List
from supabase import create_client, Client
from loguru import logger
import json
from datetime import datetime


class SupabaseClient:
    """Supabase client wrapper with AutoVision-specific methods"""
    
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_ANON_KEY")
        
        logger.info(f"Initializing Supabase client with URL: {self.url is not None}, KEY: {self.key is not None}")
        
        if not self.url or not self.key:
            logger.error(f"Missing Supabase credentials - URL: {bool(self.url)}, KEY: {bool(self.key)}")
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set")
        
        try:
            self.client: Client = create_client(self.url, self.key)
            logger.info("Supabase client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            raise
    
    def get_client(self) -> Client:
        """Get the raw Supabase client"""
        return self.client
    
    # User Management
    async def create_user_profile(self, user_id: str, email: str, full_name: Optional[str] = None) -> Dict[str, Any]:
        """Create or update user profile"""
        try:
            data = {
                "id": user_id,
                "email": email,
                "full_name": full_name,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            result = self.client.table("user_profiles").upsert(data).execute()
            logger.info(f"User profile created/updated for {email}")
            return result.data[0] if result.data else {}
        except Exception as e:
            logger.error(f"Error creating user profile: {e}")
            raise
    
    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile by ID"""
        try:
            result = self.client.table("user_profiles").select("*").eq("id", user_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return None
    
    # Video Management
    async def create_video_record(self, user_id: str, filename: str, original_name: str, 
                                file_path: str, file_size: int, duration: Optional[float] = None,
                                fps: Optional[float] = None, resolution: Optional[str] = None) -> Dict[str, Any]:
        """Create video record in database"""
        try:
            data = {
                "user_id": user_id,
                "filename": filename,
                "original_name": original_name,
                "file_path": file_path,
                "file_size": file_size,
                "duration_seconds": duration,
                "fps": fps,
                "resolution": resolution,
                "upload_status": "pending"
            }
            
            result = self.client.table("videos").insert(data).execute()
            logger.info(f"Video record created: {filename}")
            return result.data[0] if result.data else {}
        except Exception as e:
            logger.error(f"Error creating video record: {e}")
            raise
    
    def update_video_status(self, video_id: str, status: str, metadata: Optional[Dict] = None) -> bool:
        """Update video processing status"""
        try:
            data = {"upload_status": status}
            if metadata:
                data.update(metadata)
            
            result = self.client.table("videos").update(data).eq("id", video_id).execute()
            logger.info(f"Video status updated: {video_id} -> {status}")
            return True
        except Exception as e:
            logger.error(f"Error updating video status: {e}")
            return False
    
    def get_user_videos(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get user's videos"""
        try:
            result = (self.client.table("videos")
                     .select("*")
                     .eq("user_id", user_id)
                     .order("created_at", desc=True)
                     .limit(limit)
                     .execute())
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting user videos: {e}")
            return []
    
    def get_video(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get video by ID"""
        try:
            result = self.client.table("videos").select("*").eq("id", video_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error getting video: {e}")
            return None
    
    # Event Management
    async def create_event(self, video_id: str, user_id: str, event_type: str, 
                          anomaly_score: float, confidence: float, timestamp_seconds: float,
                          frame_number: int, bounding_box: Optional[Dict] = None,
                          description: Optional[str] = None, is_alert: bool = False) -> Dict[str, Any]:
        """Create anomaly detection event"""
        try:
            data = {
                "video_id": video_id,
                "user_id": user_id,
                "event_type": event_type,
                "anomaly_score": anomaly_score,
                "confidence": confidence,
                "timestamp_seconds": timestamp_seconds,
                "frame_number": frame_number,
                "bounding_box": bounding_box,
                "description": description,
                "is_alert": is_alert
            }
            
            result = self.client.table("events").insert(data).execute()
            logger.info(f"Event created: {event_type} at {timestamp_seconds}s")
            return result.data[0] if result.data else {}
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            raise
    
    def get_video_events(self, video_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get events for a video"""
        try:
            result = (self.client.table("events")
                     .select("*")
                     .eq("video_id", video_id)
                     .order("timestamp_seconds", desc=False)
                     .limit(limit)
                     .execute())
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting video events: {e}")
            return []
    
    def get_user_events(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get user's recent events"""
        try:
            result = (self.client.table("events")
                     .select("*, videos(filename, original_name)")
                     .eq("user_id", user_id)
                     .order("created_at", desc=True)
                     .limit(limit)
                     .execute())
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting user events: {e}")
            return []
    
    def update_event_feedback(self, event_id: str, is_false_positive: bool) -> bool:
        """Update event with user feedback"""
        try:
            result = (self.client.table("events")
                     .update({"is_false_positive": is_false_positive})
                     .eq("id", event_id)
                     .execute())
            logger.info(f"Event feedback updated: {event_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating event feedback: {e}")
            return False
    
    # Logging
    async def create_log(self, message: str, log_level: str = "INFO", 
                        user_id: Optional[str] = None, video_id: Optional[str] = None,
                        event_id: Optional[str] = None, metadata: Optional[Dict] = None) -> bool:
        """Create system log entry"""
        try:
            data = {
                "message": message,
                "log_level": log_level,
                "user_id": user_id,
                "video_id": video_id,
                "event_id": event_id,
                "metadata": metadata
            }
            
            result = self.client.table("logs").insert(data).execute()
            return True
        except Exception as e:
            logger.error(f"Error creating log: {e}")
            return False
    
    # RL Training Data
    async def save_rl_training_data(self, user_id: str, state_vector: List[float], 
                                   action: int, reward: float, 
                                   next_state_vector: Optional[List[float]] = None,
                                   done: bool = False) -> bool:
        """Save RL training data"""
        try:
            data = {
                "user_id": user_id,
                "state_vector": state_vector,
                "action": action,
                "reward": reward,
                "next_state_vector": next_state_vector,
                "done": done
            }
            
            result = self.client.table("rl_training_data").insert(data).execute()
            return True
        except Exception as e:
            logger.error(f"Error saving RL training data: {e}")
            return False
    
    def get_rl_training_data(self, user_id: str, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get RL training data for user"""
        try:
            result = (self.client.table("rl_training_data")
                     .select("*")
                     .eq("user_id", user_id)
                     .order("created_at", desc=True)
                     .limit(limit)
                     .execute())
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting RL training data: {e}")
            return []
    
    # Historical Patterns for RAG
    async def save_historical_pattern(self, user_id: str, pattern_type: str, 
                                     embedding: List[float], description: str,
                                     metadata: Optional[Dict] = None) -> bool:
        """Save historical pattern for RAG"""
        try:
            # Check if pattern already exists
            existing = (self.client.table("historical_patterns")
                       .select("id, frequency_count")
                       .eq("user_id", user_id)
                       .eq("pattern_type", pattern_type)
                       .eq("description", description)
                       .execute())
            
            if existing.data:
                # Update frequency
                pattern_id = existing.data[0]["id"]
                new_count = existing.data[0]["frequency_count"] + 1
                self.client.table("historical_patterns").update({
                    "frequency_count": new_count,
                    "last_seen": datetime.utcnow().isoformat()
                }).eq("id", pattern_id).execute()
            else:
                # Create new pattern
                data = {
                    "user_id": user_id,
                    "pattern_type": pattern_type,
                    "embedding": embedding,
                    "description": description,
                    "metadata": metadata,
                    "frequency_count": 1
                }
                self.client.table("historical_patterns").insert(data).execute()
            
            return True
        except Exception as e:
            logger.error(f"Error saving historical pattern: {e}")
            return False
    
    def search_similar_patterns(self, user_id: str, embedding: List[float], 
                               pattern_type: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for similar historical patterns using vector similarity"""
        try:
            query = self.client.table("historical_patterns").select("*").eq("user_id", user_id)
            
            if pattern_type:
                query = query.eq("pattern_type", pattern_type)
            
            result = query.order("frequency_count", desc=True).limit(limit * 2).execute()
            
            # For now, return most frequent patterns
            # In production, you'd use vector similarity search
            return result.data[:limit] if result.data else []
        except Exception as e:
            logger.error(f"Error searching similar patterns: {e}")
            return []
    
    # File Storage
    def upload_file(self, bucket: str, file_path: str, file_data: bytes) -> Optional[str]:
        """Upload file to Supabase storage"""
        try:
            result = self.client.storage.from_(bucket).upload(file_path, file_data)
            if result:
                logger.info(f"File uploaded: {file_path}")
                return file_path
            return None
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return None
    
    def get_file_url(self, bucket: str, file_path: str) -> Optional[str]:
        """Get public URL for file"""
        try:
            result = self.client.storage.from_(bucket).get_public_url(file_path)
            return result
        except Exception as e:
            logger.error(f"Error getting file URL: {e}")
            return None
    
    def delete_file(self, bucket: str, file_path: str) -> bool:
        """Delete file from storage"""
        try:
            result = self.client.storage.from_(bucket).remove([file_path])
            logger.info(f"File deleted: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False


# Global instance
supabase_client = SupabaseClient()