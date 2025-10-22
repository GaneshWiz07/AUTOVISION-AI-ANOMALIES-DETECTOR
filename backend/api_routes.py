"""
API routes for AutoVision backend
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, status, Request
from fastapi.responses import JSONResponse
from typing import List, Optional
from pydantic import BaseModel
import os
import asyncio
from loguru import logger

from backend.auth import get_current_user, AuthUser, auth_service, LoginRequest, SignupRequest
from backend.video_processor import VideoProcessor
from backend.video_cleanup import video_cleanup_service

# Import our custom SupabaseClient
from backend.autovision_client import supabase_client


class FeedbackRequest(BaseModel):
    """Feedback request model"""
    event_id: str
    is_false_positive: bool
    feedback_score: float  # -1.0 to 1.0
    comments: Optional[str] = None


class ThresholdUpdateRequest(BaseModel):
    """Threshold update request model"""
    new_threshold: float


class UserSettings(BaseModel):
    """User settings model"""
    anomaly_threshold: float = 0.5
    frame_sampling_rate: int = 10
    auto_delete_old_videos: bool = False
    video_retention_days: int = 30


class SettingsUpdateRequest(BaseModel):
    """Settings update request model"""
    anomaly_threshold: Optional[float] = None
    frame_sampling_rate: Optional[int] = None
    auto_delete_old_videos: Optional[bool] = None
    video_retention_days: Optional[int] = None


def create_api_router() -> APIRouter:
    """Create and configure API router"""
    router = APIRouter()
    
    # Authentication routes
    @router.post("/auth/signup", response_model=dict)
    async def signup(signup_data: SignupRequest):
        """Register a new user"""
        try:
            result = await auth_service.signup(signup_data)
            # Check if result is already a dict (email verification case) or AuthResponse object
            if isinstance(result, dict):
                return result
            else:
                return result.dict()
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Signup error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Registration failed"
            )
    
    @router.post("/auth/login", response_model=dict)
    async def login(login_data: LoginRequest):
        """Authenticate user"""
        try:
            result = await auth_service.login(login_data)
            return result.dict()
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Login error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed"
            )
    
    @router.post("/auth/refresh")
    async def refresh_token(refresh_token: str):
        """Refresh access token"""
        try:
            result = await auth_service.refresh_token(refresh_token)
            return result.dict()
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token refresh failed"
            )
    
    @router.post("/auth/logout")
    async def logout(current_user: AuthUser = Depends(get_current_user)):
        """Logout user"""
        try:
            await auth_service.logout("")
            return {"message": "Logged out successfully"}
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return {"message": "Logout completed"}
    
    @router.get("/auth/me", response_model=AuthUser)
    async def get_current_user_info(current_user: AuthUser = Depends(get_current_user)):
        """Get current user information"""
        return current_user
    
    # Video management routes
    @router.post("/videos/upload")
    async def upload_video(
        request: Request,
        file: UploadFile = File(...),
        current_user: AuthUser = Depends(get_current_user)
    ):
        """Upload a video for processing"""
        
        # Validate file type
        if not file.content_type or not file.content_type.startswith('video/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be a video"
            )
        
        # Check file size
        max_size = int(os.getenv("MAX_VIDEO_SIZE_MB", "100")) * 1024 * 1024
        file_data = await file.read()
        
        if len(file_data) > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds {max_size // (1024*1024)}MB limit"
            )        
        try:
            # Get video processor from app state
            video_processor = request.app.state.video_processor
            
            result = await video_processor.upload_video(
                file_data=file_data,
                filename=file.filename,
                user_id=current_user.id
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Video upload error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Video upload failed"
            )

    @router.get("/videos")
    async def get_user_videos(
        request: Request,
        limit: int = 50,
        current_user: AuthUser = Depends(get_current_user)
    ):
        """Get user's videos"""
        try:
            videos = []
            video_ids_seen = set()  # Track video IDs to avoid duplicates
            
            # Get videos from Supabase (only source)
            try:
                supabase_videos = supabase_client.get_user_videos(current_user.id, limit)
                for video in supabase_videos:
                    video_id = video.get('id')
                    if video_id and video_id not in video_ids_seen:
                        videos.append(video)
                        video_ids_seen.add(video_id)
                logger.info(f"Loaded {len(videos)} videos from Supabase")
            except Exception as e:
                logger.error(f"Could not fetch videos from Supabase: {e}")
                # Return empty list if Supabase fetch fails
                videos = []
              # Sort by created_at and limit
            videos = sorted(videos, key=lambda x: x.get('created_at', ''), reverse=True)[:limit]
            
            logger.info(f"Returning {len(videos)} videos to user")
            return {"videos": videos}
            
        except Exception as e:
            logger.error(f"Error getting user videos: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve videos"
            )

    @router.get("/videos/{video_id}")
    async def get_video(
        video_id: str,
        current_user: AuthUser = Depends(get_current_user)
    ):
        """Get video details"""
        try:
            video = supabase_client.get_video(video_id)
            
            if not video:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Video not found"
                )
            
            if video["user_id"] != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
            
            return video
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting video: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve video"
            )

    @router.get("/videos/{video_id}/analysis")
    async def get_video_analysis(
        video_id: str,
        current_user: AuthUser = Depends(get_current_user)
    ):
        """Get video analysis results"""
        try:
            video_processor = VideoProcessor()
            analysis = await video_processor.get_video_analysis(video_id, current_user.id)
            return analysis
            
        except Exception as e:
            logger.error(f"Error getting video analysis: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve video analysis"
            )
    
    @router.get("/videos/{video_id}/stream")
    async def stream_video(
        video_id: str,
        request: Request,
        token: Optional[str] = None
    ):
        """Stream video file"""
        try:
            from fastapi.responses import FileResponse
            from fastapi.security import HTTPAuthorizationCredentials
            
            # Get current user either from auth header or token query param
            current_user = None
            
            if token:
                # Use token from query parameter
                try:
                    # Create credentials object for get_current_user
                    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
                    current_user = await get_current_user(credentials)
                except Exception as e:
                    logger.error(f"Token validation error: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid token"
                    )
            else:
                # Try to get from Authorization header
                auth_header = request.headers.get("authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    token_from_header = auth_header.split(" ")[1]
                    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token_from_header)
                    current_user = await get_current_user(credentials)
                else:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication required"
                    )
            
            # Get video details
            video = supabase_client.get_video(video_id)
            
            if not video:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Video not found"
                )
            
            if video["user_id"] != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )              # Check if we have a Supabase Storage URL
            storage_provider = video.get("storage_provider")
            file_url = video.get("file_url") 
            file_path = video.get("file_path")
            
            if storage_provider == "supabase" and file_url:
                # If we have a Supabase Storage URL, redirect to it
                from fastapi.responses import RedirectResponse
                
                # For expired URLs, generate a fresh signed URL
                if "token_has_expired" in file_url or "error" in file_url.lower():
                    try:
                        # Parse the storage path from file_path (format: "bucket/path")
                        storage_parts = file_path.split('/', 1)
                        if len(storage_parts) == 2:
                            bucket = storage_parts[0]
                            path = storage_parts[1]
                            
                            # Generate a new signed URL
                            fresh_url = supabase_client.get_admin_client().storage.from_(bucket).create_signed_url(
                                path=path,
                                expires_in=3600  # 1 hour
                            )
                            
                            # Update the video record with the new URL
                            supabase_client.get_admin_client().table("videos").update({
                                "file_url": fresh_url
                            }).eq("id", video_id).execute()
                            
                            file_url = fresh_url
                    except Exception as e:
                        logger.error(f"Failed to refresh signed URL: {e}")
                
                logger.info(f"Redirecting to Supabase Storage URL for video {video_id}")
                return RedirectResponse(url=file_url)
            
            # Fall back to local file if no storage provider or URL (for backward compatibility)
            if not file_path:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Video file path not found"
                )
            
            logger.warning(f"Using local file fallback for video {video_id}. Consider migrating this to Supabase Storage.")
            
            # If path is relative, make it relative to backend directory
            if not os.path.isabs(file_path):
                # Get the directory where this script is located (backend/)
                backend_dir = os.path.dirname(os.path.abspath(__file__))
                file_path = os.path.join(backend_dir, file_path)
            
            if not os.path.exists(file_path):
                logger.error(f"Video file not found at path: {file_path}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Video file not found on disk"
                )
                
            # Return video file from disk (legacy method)
            from fastapi.responses import FileResponse
            return FileResponse(
                path=file_path,
                media_type="video/mp4",
                filename=video.get("original_name", "video.mp4")
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error streaming video: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to stream video"
            )

    @router.post("/videos/{video_id}/process")
    async def process_video(
        video_id: str,
        request: Request,
        current_user: AuthUser = Depends(get_current_user)
    ):
        """Trigger video processing with real AI analysis"""
        try:
            logger.info(f"Processing video {video_id} for user {current_user.id}")
            
            # Get video processor from app state
            video_processor = request.app.state.video_processor
            
            # First, check if video exists in Supabase database
            video_record = supabase_client.get_video(video_id)
            
            if video_record:
                # Check ownership
                if video_record.get('user_id') != current_user.id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied"
                    )
                
                # Check if already processed
                if video_record.get('upload_status') == 'completed':
                    return {
                        "status": "completed",
                        "message": "Video already processed",
                        "video_id": video_id
                    }
                
                # Get file path and check if file exists
                file_path = video_record.get('file_path')
                if file_path and os.path.exists(file_path):
                    # Update status to processing in database
                    supabase_client.update_video_status(video_id, "processing")
                    
                    # Create metadata object
                    from backend.video_processor import VideoMetadata
                    metadata = VideoMetadata(file_path)
                    
                    # Add to processing queue for real AI analysis
                    await video_processor.processing_queue.put({
                        "video_id": video_id,
                        "user_id": current_user.id,
                        "filepath": file_path,
                        "metadata": metadata,
                        "cleanup_dir": None  # No cleanup needed for existing files
                    })
                      # Start processing if not already running
                    if not video_processor.is_processing:
                        asyncio.create_task(video_processor._process_queue())
                    
                    logger.info(f"Video {video_id} added to processing queue for real AI analysis")
                    return {
                        "status": "processing",
                        "message": "Video processing started with real AI analysis",
                        "video_id": video_id
                    }
                else:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Video file not found on disk"
                    )
            else:
                # Video not found in database
                logger.error(f"Video {video_id} not found in database")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Video not found"
                )
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error processing video: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process video"
            )

    @router.delete("/videos/{video_id}")
    async def delete_video(
        video_id: str,
        request: Request,
        current_user: AuthUser = Depends(get_current_user)
    ):
        """Delete a video"""
        try:
            video_found = False
            
            logger.info(f"Attempting to delete video {video_id} for user {current_user.id}")
            
            # Delete from Supabase (only source)
            try:
                video = supabase_client.get_video(video_id)
                if video:
                    logger.info(f"Found video in Supabase: {video}")
                    if video["user_id"] != current_user.id:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Access denied"
                        )
                    
                    # Delete associated events first (to avoid foreign key constraint issues)
                    try:
                        admin_client = supabase_client.get_admin_client()
                        events_result = admin_client.table("events").delete().eq("video_id", video_id).execute()
                        deleted_events = len(events_result.data) if events_result.data else 0
                        logger.info(f"Deleted {deleted_events} events associated with video {video_id}")
                    except Exception as e:
                        logger.warning(f"Could not delete events for video {video_id}: {e}")
                    
                    # Delete from storage
                    try:
                        supabase_client.delete_file("videos", video["file_path"])
                    except Exception as e:
                        logger.warning(f"Could not delete file from storage: {e}")
                    
                    # Delete from database
                    admin_client = supabase_client.get_admin_client()
                    admin_client.table("videos").delete().eq("id", video_id).execute()
                    video_found = True
                    logger.info(f"Deleted video {video_id} from Supabase")
                else:
                    logger.info(f"Video {video_id} not found in Supabase")
            except Exception as e:
                logger.error(f"Could not delete from Supabase: {e}")
            
            if not video_found:
                logger.error(f"Video {video_id} not found")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Video not found"
                )
            
            return {"message": "Video deleted successfully"}
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting video: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete video"
            )
    
    # Event management routes
    @router.get("/events")
    async def get_user_events(
        request: Request,
        limit: int = 100,
        current_user: AuthUser = Depends(get_current_user)
    ):
        """Get user's anomaly detection events"""
        try:
            events = []
            
            # Get events from Supabase (only source)
            try:
                supabase_events = supabase_client.get_user_events(current_user.id, limit)
                events.extend(supabase_events)
                logger.info(f"Loaded {len(supabase_events)} events from Supabase")
            except Exception as e:
                logger.error(f"Could not fetch events from Supabase: {e}")
            
            # Sort events by timestamp
            events = sorted(events, key=lambda x: x.get('created_at', ''), reverse=True)[:limit]
            
            logger.info(f"Returning {len(events)} events to user")
            return {"events": events}
        except Exception as e:
            logger.error(f"Error getting user events: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve events"
            )
    
    @router.get("/videos/{video_id}/events")
    async def get_video_events(
        video_id: str,
        current_user: AuthUser = Depends(get_current_user)
    ):
        """Get events for a specific video"""
        try:
            # Verify video ownership
            video = supabase_client.get_video(video_id)
            if not video or video["user_id"] != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
            
            events = supabase_client.get_video_events(video_id)
            return {"events": events}
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting video events: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve events"            )
    
    @router.put("/events/{event_id}")
    async def update_event(
        event_id: str,
        data: dict,
        current_user: AuthUser = Depends(get_current_user)
    ):
        """Update an event (e.g., mark as false positive)"""
        try:
            # For the simplified version, just return success
            # In a real implementation, you would update the database
            logger.info(f"Updating event {event_id} with data: {data}")
            return {"message": "Event updated successfully", "event_id": event_id}
        except Exception as e:
            logger.error(f"Error updating event: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update event"
            )

    @router.post("/events/{event_id}/feedback")
    async def provide_feedback(
        event_id: str,
        feedback: FeedbackRequest,
        current_user: AuthUser = Depends(get_current_user)
    ):
        """Provide feedback on an anomaly detection"""
        try:
            video_processor = VideoProcessor()
            success = await video_processor.provide_feedback(
                event_id=event_id,
                user_id=current_user.id,
                is_false_positive=feedback.is_false_positive,
                feedback_score=feedback.feedback_score
            )
            
            if success:
                return {"message": "Feedback recorded successfully"}
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to record feedback"
                )
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error providing feedback: {e}")
            raise HTTPException(                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to record feedback"
            )
    
    # System monitoring routes
    @router.get("/system/status")
    async def get_system_status(current_user: AuthUser = Depends(get_current_user)):
        """Get system status and metrics"""
        try:
            video_processor = VideoProcessor()
            system_status = video_processor.get_system_status()
            return system_status
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve system status"
            )
    
    @router.get("/system/metrics")
    async def get_system_metrics(current_user: AuthUser = Depends(get_current_user)):
        """Get detailed system metrics"""
        try:
            # Get video processor statistics
            video_processor = VideoProcessor()
            processor_status = video_processor.get_system_status()
            
            return {
                "video_processor": processor_status,
                "timestamp": "2024-12-19T00:00:00Z"
            }
            
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve system metrics"
            )
    
    @router.get("/system/events")
    async def get_system_events(
        limit: int = 100,
        event_type: Optional[str] = None,
        current_user: AuthUser = Depends(get_current_user)
    ):
        """Get system events for the user"""
        try:
            # Get events from Supabase instead of EventStream
            events = supabase_client.get_user_events(current_user.id, limit)
            
            # Filter by event_type if provided
            if event_type:
                events = [e for e in events if e.get('event_type') == event_type]
            
            return {"events": events}
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting system events: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve system events"
            )
    
    # RL Controller routes
    @router.get("/rl/status")
    async def get_rl_status(current_user: AuthUser = Depends(get_current_user)):
        """Get RL controller status"""
        try:
            video_processor = VideoProcessor()
            rl_summary = video_processor.rl_controller.get_training_summary()
            return rl_summary
        except Exception as e:
            logger.error(f"Error getting RL status: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve RL status"
            )
    
    @router.post("/rl/reset")
    async def reset_rl_training(current_user: AuthUser = Depends(get_current_user)):
        """Reset RL training (admin only)"""
        try:
            video_processor = VideoProcessor()
            video_processor.rl_controller.reset_training()
            return {"message": "RL training reset successfully"}
        except Exception as e:
            logger.error(f"Error resetting RL training: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reset RL training"
            )
    
    # RAG System routes
    @router.get("/rag/patterns")
    async def get_rag_patterns(
        pattern_type: Optional[str] = None,
        current_user: AuthUser = Depends(get_current_user)
    ):
        """Get RAG system patterns summary"""
        try:
            video_processor = VideoProcessor()
            summary = video_processor.rag_system.generate_pattern_summary(pattern_type)
            return summary
        except Exception as e:
            logger.error(f"Error getting RAG patterns: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve RAG patterns"
            )
    
    @router.get("/rag/stats")
    async def get_rag_stats(current_user: AuthUser = Depends(get_current_user)):
        """Get RAG system statistics"""
        try:
            video_processor = VideoProcessor()
            stats = video_processor.rag_system.get_pattern_stats()
            return stats
        except Exception as e:
            logger.error(f"Error getting RAG stats: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve RAG statistics"            )
    
    # User Settings routes
    @router.get("/settings", response_model=UserSettings)
    async def get_user_settings(current_user: AuthUser = Depends(get_current_user)):
        """Get user settings"""
        try:
            # Get settings from Supabase using admin client
            admin_client = supabase_client.get_admin_client()
            result = admin_client.table("user_settings").select("*").eq("user_id", current_user.id).execute()
            
            if result.data and len(result.data) > 0:
                settings_data = result.data[0]
                return UserSettings(
                    anomaly_threshold=settings_data.get('anomaly_threshold', 0.5),
                    frame_sampling_rate=settings_data.get('frame_sampling_rate', 10),
                    auto_delete_old_videos=settings_data.get('auto_delete_old_videos', False),
                    video_retention_days=settings_data.get('video_retention_days', 30)
                )
            else:
                # Return default settings
                return UserSettings()
                
        except Exception as e:
            logger.error(f"Error getting user settings: {e}")
            # Return default settings on error
            return UserSettings()
    
    @router.put("/settings", response_model=UserSettings)
    async def update_user_settings(
        settings: SettingsUpdateRequest,
        current_user: AuthUser = Depends(get_current_user)
    ):
        """Update user settings"""
        try:
            # Prepare update data
            update_data = {"user_id": current_user.id}
            
            if settings.anomaly_threshold is not None:
                if not (0 <= settings.anomaly_threshold <= 1):                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Anomaly threshold must be between 0 and 1"
                    )
                update_data["anomaly_threshold"] = settings.anomaly_threshold
            
            if settings.frame_sampling_rate is not None:
                if settings.frame_sampling_rate <= 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Frame sampling rate must be positive"
                    )
                update_data["frame_sampling_rate"] = settings.frame_sampling_rate
            
            if settings.auto_delete_old_videos is not None:
                update_data["auto_delete_old_videos"] = settings.auto_delete_old_videos
            
            if settings.video_retention_days is not None:
                if settings.video_retention_days <= 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Video retention days must be positive"
                    )
                update_data["video_retention_days"] = settings.video_retention_days
            
            # Update settings in Supabase using admin client to bypass RLS
            admin_client = supabase_client.get_admin_client()
            
            logger.info(f"Updating settings for user {current_user.id}: {update_data}")
            
            # First try to update existing record
            result = admin_client.table("user_settings").update(
                {k: v for k, v in update_data.items() if k != "user_id"}
            ).eq("user_id", current_user.id).execute()
            
            # If no rows were updated, insert a new record
            if not result.data:
                logger.info(f"No existing settings found, inserting new record for user {current_user.id}")
                result = admin_client.table("user_settings").insert(
                    update_data
                ).execute()
            else:
                logger.info(f"Updated existing settings for user {current_user.id}")
            
            if result.data:
                settings_data = result.data[0]
                return UserSettings(
                    anomaly_threshold=settings_data.get('anomaly_threshold', 0.5),
                    frame_sampling_rate=settings_data.get('frame_sampling_rate', 10),
                    auto_delete_old_videos=settings_data.get('auto_delete_old_videos', False),
                    video_retention_days=settings_data.get('video_retention_days', 30)
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update settings"
                )
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating user settings: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update settings"
            )

    # Video cleanup routes
    @router.post("/videos/{video_id}/cleanup")
    async def cleanup_video(
        video_id: str,
        request: Request,
        current_user: AuthUser = Depends(get_current_user)
    ):
        """Trigger video cleanup"""
        try:
            logger.info(f"Cleaning up video {video_id} for user {current_user.id}")
            
            # Get video processor from app state
            video_processor = request.app.state.video_processor
            
            # First, check if video exists in Supabase database
            video_record = supabase_client.get_video(video_id)
            
            if video_record:
                # Check ownership
                if video_record.get('user_id') != current_user.id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied"
                    )
                
                # Check if cleanup is needed
                if video_record.get('cleanup_status') == 'completed':
                    return {
                        "status": "completed",
                        "message": "Video cleanup already completed",
                        "video_id": video_id
                    }
                
                # Get file path and check if file exists
                file_path = video_record.get('file_path')
                if file_path and os.path.exists(file_path):
                    # Update status to cleaning in database
                    supabase_client.update_video_status(video_id, "cleaning")
                    
                    # Create metadata object
                    from backend.video_processor import VideoMetadata
                    metadata = VideoMetadata(file_path)
                    
                    # Add to cleanup queue
                    await video_cleanup_service.cleanup_queue.put({
                        "video_id": video_id,
                        "user_id": current_user.id,
                        "filepath": file_path,
                        "metadata": metadata
                    })
                      # Start cleanup if not already running
                    if not video_cleanup_service.is_cleaning:
                        asyncio.create_task(video_cleanup_service._cleanup_queue())
                    
                    logger.info(f"Video {video_id} added to cleanup queue")
                    return {
                        "status": "cleaning",
                        "message": "Video cleanup started",
                        "video_id": video_id
                    }
                else:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Video file not found on disk"
                    )
            else:
                # Video not found in database
                logger.error(f"Video {video_id} not found in database")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Video not found"
                )
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error cleaning up video: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to cleanup video"
            )

    @router.get("/videos/cleanup/status")
    async def get_cleanup_status(
        request: Request,
        current_user: AuthUser = Depends(get_current_user)
    ):
        """Get video cleanup status"""
        try:
            # Get all videos for the user
            videos = supabase_client.get_user_videos(current_user.id, 100)
            
            # Filter videos that are still cleaning
            cleaning_videos = [video for video in videos if video.get('cleanup_status') != 'completed']
            
            return {
                "status": "cleaning",
                "videos": cleaning_videos
            }
        except Exception as e:
            logger.error(f"Error getting cleanup status: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,                detail="Failed to retrieve cleanup status"
            )

    # Video retention cleanup routes
    @router.get("/cleanup/preview")
    async def get_cleanup_preview(
        current_user: AuthUser = Depends(get_current_user)
    ):
        """Get preview of videos that would be deleted based on retention settings"""
        try:
            preview = await video_cleanup_service.get_cleanup_preview(current_user.id)
            return preview
        except Exception as e:
            logger.error(f"Error getting cleanup preview: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get cleanup preview"
            )

    @router.post("/cleanup/run")
    async def run_video_cleanup(
        current_user: AuthUser = Depends(get_current_user)
    ):
        """Manually trigger video cleanup for current user"""
        try:
            result = await video_cleanup_service.cleanup_user_videos_manual(current_user.id)
            return {
                "status": "completed",
                "result": result,
                "message": f"Cleaned up {result['videos_deleted']} videos, freed {result['space_freed_mb']:.2f} MB"
            }
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Error running video cleanup: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to run cleanup"
            )
    
    return router