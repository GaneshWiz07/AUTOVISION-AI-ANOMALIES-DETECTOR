"""
Supabase client configuration and utilities for AutoVision
"""
import os
from typing import Optional, Dict, Any, List
from supabase import create_client, Client
from loguru import logger
import json
from datetime import datetime
import uuid
from pathlib import Path
import tempfile
import requests


class SupabaseClient:
    """Supabase client wrapper with AutoVision-specific methods"""
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.anon_key = os.getenv("SUPABASE_ANON_KEY")
        self.service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        logger.info(f"Initializing Supabase client with URL: {self.url is not None}, ANON_KEY: {self.anon_key is not None}, SERVICE_KEY: {self.service_key is not None}")
        
        if not self.url or not self.anon_key or not self.service_key:
            logger.error(f"Missing Supabase credentials - URL: {bool(self.url)}, ANON_KEY: {bool(self.anon_key)}, SERVICE_KEY: {bool(self.service_key)}")
            raise ValueError("SUPABASE_URL, SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY must be set")
        
        try:
            # Initialize two clients - one with anon key and one with service role key
            self.client: Client = create_client(self.url, self.anon_key)
            self.admin_client: Client = create_client(self.url, self.service_key)
            logger.info("Supabase clients initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            raise
    
    def get_client(self) -> Client:
        """Get the raw Supabase client"""
        return self.client
    
    def get_admin_client(self) -> Client:
        """Get the Supabase client with service role key for admin operations
        
        This client bypasses RLS policies and should only be used for server-side operations
        """
        return self.admin_client
    
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
    # Storage methods
    async def upload_video_to_storage(self, file_data: bytes, user_id: str, filename: str) -> Dict[str, Any]:
        """
        Upload video to Supabase Storage using the correct API format
        
        Args:
            file_data: Raw video file data
            user_id: User ID who uploaded the video
            filename: Original filename
            
        Returns:
            Dict containing storage path and public URL
        """
        try:
            # Create a unique filename
            unique_id = str(uuid.uuid4())
            file_extension = Path(filename).suffix
            storage_filename = f"{unique_id}{file_extension}"
            
            bucket_name = "videos"
            storage_path = f"{user_id}/{storage_filename}"
              # First, ensure bucket exists with proper configuration
            try:
                bucket_info = self.admin_client.storage.get_bucket(bucket_name)
                logger.info(f"Bucket '{bucket_name}' already exists")
            except Exception as e:
                logger.info(f"Bucket '{bucket_name}' not found, creating it. Error: {e}")
                try:
                    # Create bucket with minimal settings first
                    bucket_response = self.admin_client.storage.create_bucket(bucket_name)
                    logger.info(f"Bucket created successfully: {bucket_response}")
                except Exception as bucket_error:
                    logger.error(f"Failed to create bucket: {bucket_error}")
                    # Try creating with public access if private fails
                    try:
                        bucket_response = self.admin_client.storage.create_bucket(
                            bucket_name, 
                            {"public": True}
                        )
                        logger.info(f"Public bucket created successfully: {bucket_response}")
                    except Exception as public_bucket_error:
                        logger.error(f"Failed to create public bucket: {public_bucket_error}")
                        raise Exception(f"Could not create bucket: {public_bucket_error}")
            
            # Wait a moment for bucket to be fully created
            import time
            time.sleep(1)
            
            logger.info(f"Uploading to Supabase Storage: {storage_path}")
            
            # Try the BytesIO method first (most likely to work)
            from io import BytesIO
            
            # Create a BytesIO object that mimics a file
            file_buffer = BytesIO(file_data)
            file_buffer.name = storage_filename  # This is crucial for the API
            
            response = None
            upload_successful = False
            
            try:
                response = self.admin_client.storage.from_(bucket_name).upload(
                    path=storage_path,
                    file=file_buffer,
                    file_options={"content-type": "video/mp4"}
                )
                upload_successful = True
                logger.info("Upload successful with BytesIO method")
                
            except Exception as e1:
                logger.warning(f"BytesIO method failed: {e1}")
                
                # If BytesIO fails, try direct REST API with corrected URL
                try:
                    import json
                    
                    # Get the storage URL and credentials
                    supabase_url = os.getenv("SUPABASE_URL")
                    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
                    
                    # Correct REST API endpoint format
                    upload_url = f"{supabase_url}/storage/v1/object/{bucket_name}/{storage_path}"
                    
                    headers = {
                        "Authorization": f"Bearer {service_key}",
                        "Content-Type": "video/mp4",
                        "x-upsert": "true"
                    }
                    
                    logger.info(f"Trying REST API upload to: {upload_url}")
                    
                    # Direct REST API upload
                    rest_response = requests.post(
                        upload_url,
                        data=file_data,
                        headers=headers
                    )
                    
                    logger.info(f"REST API response status: {rest_response.status_code}")
                    logger.debug(f"REST API response: {rest_response.text}")
                    
                    if rest_response.status_code in [200, 201]:
                        response = rest_response.json() if rest_response.text else {"success": True}
                        upload_successful = True
                        logger.info("Upload successful with REST API method")
                    else:
                        raise Exception(f"REST API upload failed: {rest_response.status_code} - {rest_response.text}")
                        
                except Exception as e2:
                    logger.error(f"REST API method also failed: {e2}")
                    raise Exception(f"All upload methods failed: {e2}")
            
            if not upload_successful:
                raise Exception("Upload failed with all methods")
            
            logger.info("Supabase upload successful, creating signed URL...")
            
            # Get signed URL
            try:
                signed_url_response = self.admin_client.storage.from_(bucket_name).create_signed_url(
                    path=storage_path,
                    expires_in=3600 * 24 * 7  # 7 days
                )
                
                logger.debug(f"Signed URL response: {signed_url_response}")
                
                # Handle different response formats
                if isinstance(signed_url_response, dict):
                    if 'signedURL' in signed_url_response:
                        public_url = signed_url_response['signedURL']
                    elif 'data' in signed_url_response and isinstance(signed_url_response['data'], dict):
                        public_url = signed_url_response['data'].get('signedURL', str(signed_url_response))
                    else:
                        public_url = str(signed_url_response)
                else:
                    public_url = str(signed_url_response)
                    
            except Exception as url_error:
                logger.warning(f"Failed to create signed URL: {url_error}")
                # Use public URL format as fallback
                supabase_url = os.getenv("SUPABASE_URL")
                public_url = f"{supabase_url}/storage/v1/object/public/{bucket_name}/{storage_path}"
            
            logger.info(f"Supabase Storage upload completed: {storage_path}")
            return {
                "storage_path": f"{bucket_name}/{storage_path}",
                "public_url": public_url,
                "storage_id": unique_id,
                "storage_provider": "supabase"
            }
            
        except Exception as e:
            logger.error(f"Supabase Storage upload failed: {e}")
            raise Exception(f"Storage upload failed: {e}")
    
    async def refresh_video_url(self, video_id: str) -> Optional[str]:
        """
        Refresh the signed URL for a video stored in Supabase Storage
        
        Args:
            video_id: ID of the video
            
        Returns:
            Fresh signed URL or None if failed
        """
        try:
            # Get the video record
            video = self.get_video(video_id)
            if not video:
                logger.error(f"Video not found for refresh: {video_id}")
                return None
                
            # Check if it uses Supabase Storage
            if video.get("storage_provider") != "supabase":
                logger.warning(f"Video {video_id} does not use Supabase Storage")
                return None
                
            file_path = video.get("file_path")
            if not file_path:
                logger.error(f"Video {video_id} has no file path")
                return None
                
            # Parse the storage path (format: "bucket/path")
            storage_parts = file_path.split('/', 1)
            if len(storage_parts) != 2:
                logger.error(f"Invalid storage path format: {file_path}")
                return None
                
            bucket = storage_parts[0]
            path = storage_parts[1]
            
            # Generate a new signed URL
            fresh_url = self.admin_client.storage.from_(bucket).create_signed_url(
                path=path,
                expires_in=3600 * 24  # 24 hours
            )
            
            # Update the video record with the new URL
            self.admin_client.table("videos").update({
                "file_url": fresh_url
            }).eq("id", video_id).execute()
            
            logger.info(f"Refreshed signed URL for video {video_id}")
            return fresh_url
            
        except Exception as e:
            logger.error(f"Error refreshing video URL: {e}")
            return None


# Global instance
supabase_client = SupabaseClient()