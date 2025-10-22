"""
Video processing module for AutoVision
Handles video upload, frame extraction, and anomaly detection
"""

import os
import cv2
import numpy as np
from typing import List, Dict, Optional, Tuple, Any
import asyncio
from pathlib import Path
import tempfile
import shutil
from datetime import datetime
import uuid
from loguru import logger
import json

from ai_models.simple_anomaly_detector import create_anomaly_detector
from ai_models.simple_rl_controller import create_rl_controller
from ai_models.simple_rag_system import create_rag_system
from backend.autovision_client import supabase_client
# Define simple anomaly types for demo
class AnomalyTypes:
    NORMAL = "normal"
    UNKNOWN = "unknown"
    RUNNING = "running"
    CROWD = "crowd"
    INTRUSION = "intrusion"
    LOITERING = "loitering"

# Removed EventStream import to simplify processing


class VideoMetadata:
    """Video metadata container"""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        
        # Extract video properties
        cap = cv2.VideoCapture(filepath)
        self.fps = cap.get(cv2.CAP_PROP_FPS)
        self.frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.duration = self.frame_count / self.fps if self.fps > 0 else 0
        self.file_size = os.path.getsize(filepath)
        cap.release()
        
        logger.info(f"Video metadata: {self.filename} - {self.width}x{self.height}, {self.fps:.2f}fps, {self.duration:.2f}s")


class FrameProcessor:
    """Processes individual video frames"""
    
    def __init__(self, anomaly_detector, rl_controller, rag_system):
        self.anomaly_detector = anomaly_detector
        self.rl_controller = rl_controller
        self.rag_system = rag_system
        self.frame_sampling_rate = int(os.getenv("FRAME_SAMPLING_RATE", "5"))
    
    async def process_frame(self, frame: np.ndarray, frame_number: int, 
                          video_id: str, user_id: str, fps: float = 30.0) -> Dict[str, Any]:
        """Process a single frame and return detection results"""
        
        try:
            # Get current threshold from RL controller
            current_threshold = self.rl_controller.get_current_threshold()
            
            # Detect anomaly
            detection_result = self.anomaly_detector.detect_anomaly(frame)
            
            # Extract features for RAG
            frame_features = self.anomaly_detector.extract_features(frame)
            
            # Determine anomaly type based on score and confidence
            anomaly_type = self._classify_anomaly_type(detection_result)
              # Create description for RAG analysis
            description = self._create_frame_description(detection_result, anomaly_type)
            
            # Analyze with RAG system (with fallback for missing method)
            if hasattr(self.rag_system, 'analyze_detection'):
                rag_analysis = self.rag_system.analyze_detection(
                    description, 
                    detection_result["anomaly_score"],
                    anomaly_type
                )
            else:
                # Fallback implementation
                logger.warning("RAG system missing analyze_detection method, using fallback")
                rag_analysis = {
                    "confidence": 0.5,
                    "explanation": f"Detected {anomaly_type} with score {detection_result['anomaly_score']:.3f}",
                    "recommendations": ["Review detection manually"],
                    "context": {},
                    "analysis_type": "fallback"
                }
              # Adjust confidence based on RAG analysis
            confidence_adjustment = rag_analysis.get("confidence", 0.0) - 0.5  # Convert to adjustment (-0.5 to +0.5)
            adjusted_confidence = min(1.0, max(0.0, detection_result["anomaly_confidence"] + confidence_adjustment))
            
            # Get current RL threshold (don't adjust during processing)
            # RL adjustment happens during feedback, not during detection
            current_threshold = self.rl_controller.get_current_threshold()            # Prepare result
            result = {
                "frame_number": frame_number,
                "timestamp_seconds": frame_number / fps,  # Use actual video FPS
                "anomaly_score": detection_result["anomaly_score"],
                "is_anomaly": detection_result["is_anomaly"],
                "anomaly_type": anomaly_type,
                "confidence": adjusted_confidence,
                "original_confidence": detection_result["anomaly_confidence"],
                "threshold_used": current_threshold,
                "rag_analysis": rag_analysis,
                "features": frame_features.tolist()[:50]  # Limit feature size for storage
            }            # Add to historical patterns if anomaly detected
            # Ensure is_anomaly is a boolean
            is_anomaly_bool = bool(detection_result["is_anomaly"])
            if is_anomaly_bool:
                if hasattr(self.rag_system, 'add_pattern'):
                    self.rag_system.add_pattern(
                        pattern_type=anomaly_type,
                        description=description,
                        metadata={
                            "video_id": video_id,
                            "frame_number": frame_number,
                            "anomaly_score": detection_result["anomaly_score"],
                            "confidence": adjusted_confidence
                        }
                    )
                else:
                    logger.warning("RAG system missing add_pattern method, skipping pattern addition")
            
            return result
            
        except Exception as e:
            import traceback
            logger.error(f"Error processing frame {frame_number}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "frame_number": frame_number,
                "timestamp_seconds": frame_number / fps,
                "anomaly_score": 0.0,
                "is_anomaly": False,
                "anomaly_type": AnomalyTypes.UNKNOWN,
                "confidence": 0.0,
                "error": str(e)            }
    
    def _classify_anomaly_type(self, detection_result: Dict[str, Any]) -> str:
        """Classify the type of anomaly based on detection results"""
        
        anomaly_score = detection_result["anomaly_score"]
        
        # Simple rule-based classification (in production, use more sophisticated methods)
        if anomaly_score < 0.3:
            return AnomalyTypes.NORMAL
        elif anomaly_score < 0.5:
            return AnomalyTypes.LOITERING
        elif anomaly_score < 0.7:
            return AnomalyTypes.RUNNING
        elif anomaly_score < 0.8:
            return "crowd_gathering"
        elif anomaly_score < 0.9:
            return AnomalyTypes.INTRUSION
        else:
            return "fighting"
    
    def _create_frame_description(self, detection_result: Dict[str, Any], anomaly_type: str) -> str:
        """Create a textual description of the frame for RAG analysis"""
        
        score = detection_result["anomaly_score"]
        confidence = detection_result["anomaly_confidence"]
        
        if anomaly_type == AnomalyTypes.NORMAL:
            return f"Normal surveillance scene with low anomaly score ({score:.2f})"
        else:
            return f"{anomaly_type.replace('_', ' ').title()} detected with score {score:.2f} and confidence {confidence:.2f}"


class VideoProcessor:
    """Main video processing class"""
    
    def __init__(self):
        # Force reload of AI models to get latest changes
        import importlib
        import ai_models.simple_anomaly_detector
        import ai_models.simple_rl_controller  
        import ai_models.simple_rag_system
        
        importlib.reload(ai_models.simple_anomaly_detector)
        importlib.reload(ai_models.simple_rl_controller)
        importlib.reload(ai_models.simple_rag_system)
        
        # Re-import create functions after reload
        from ai_models.simple_anomaly_detector import create_anomaly_detector
        from ai_models.simple_rl_controller import create_rl_controller
        from ai_models.simple_rag_system import create_rag_system
        
        # Initialize AI models
        self.anomaly_detector = create_anomaly_detector()
        self.rl_controller = create_rl_controller()
        self.rag_system = create_rag_system()
        
        # Verify the RAG system has the required method
        if not hasattr(self.rag_system, 'analyze_detection'):
            logger.error("RAG system still missing analyze_detection method after reload!")
        else:
            logger.info("RAG system successfully loaded with analyze_detection method")
        
        # Initialize frame processor
        self.frame_processor = FrameProcessor(
            self.anomaly_detector,
            self.rl_controller,
            self.rag_system
        )
          # Processing queue
        self.processing_queue = asyncio.Queue()
        self.is_processing = False
        
        # Statistics
        self.stats = {
            "videos_processed": 0,
            "frames_processed": 0,
            "anomalies_detected": 0,
            "processing_time_total": 0.0
        }
        
        logger.info("Video processor initialized")
    
    def start_processing(self):
        """Start the background video processing task"""
        if not self.is_processing:
            asyncio.create_task(self._process_queue())
            logger.info("Video processing queue started")
    
    async def upload_video(self, file_data: bytes, filename: str, user_id: str) -> Dict[str, Any]:
        """Upload and process a video file"""
        
        try:
            # Generate unique IDs
            video_id = str(uuid.uuid4())
            file_extension = Path(filename).suffix
            unique_filename = f"{video_id}{file_extension}"
            
            # Save file temporarily for metadata extraction
            temp_dir = tempfile.mkdtemp()
            temp_filepath = os.path.join(temp_dir, unique_filename)
            
            with open(temp_filepath, "wb") as f:
                f.write(file_data)
            
            # Extract metadata
            metadata = VideoMetadata(temp_filepath)
            
            # Upload to Supabase Storage
            storage_result = await supabase_client.upload_video_to_storage(
                file_data=file_data,
                user_id=user_id,
                filename=filename
            )
            
            logger.info(f"Video uploaded to storage: {storage_result['storage_path']} (provider: {storage_result['storage_provider']})")
            
            # Save video record to Supabase database
            try:
                supabase_video_data = {
                    "id": video_id,
                    "user_id": user_id,
                    "filename": unique_filename,
                    "original_name": filename,
                    "file_path": storage_result['storage_path'],
                    "file_url": storage_result['public_url'],
                    "file_size": len(file_data),
                    "duration_seconds": metadata.duration,
                    "fps": metadata.fps,
                    "resolution": f"{metadata.width}x{metadata.height}" if metadata.width and metadata.height else None,
                    "upload_status": "uploaded",
                    "storage_provider": storage_result['storage_provider']  # Use provider from storage result
                }
                supabase_client.get_admin_client().table("videos").insert(supabase_video_data).execute()
                logger.info(f"Video record saved to Supabase: {video_id}")
                
            except Exception as e:
                logger.error(f"Failed to save video record to Supabase: {e}")
                # Try to clean up storage if database insert fails
                try:
                    # Extract bucket and path from storage path (format: "bucket/path")
                    storage_parts = storage_result['storage_path'].split('/', 1)
                    if len(storage_parts) == 2:
                        bucket = storage_parts[0]
                        path = storage_parts[1]
                        supabase_client.get_admin_client().storage.from_(bucket).remove(path)
                        logger.info(f"Cleaned up orphaned storage file: {storage_result['storage_path']}")
                except Exception as cleanup_error:
                    logger.error(f"Failed to clean up storage after error: {cleanup_error}")
                
                raise Exception(f"Failed to save video record: {e}")
            
            # Create video uploaded event (removed EventStream dependency)
            logger.info(f"Video uploaded event for user {user_id}, video {video_id}, filename {filename}")
            
            # Add to processing queue BEFORE cleaning up temporary file
            await self.processing_queue.put({
                "video_id": video_id,
                "user_id": user_id,
                "filepath": temp_filepath,
                "metadata": metadata,
                "cleanup_dir": temp_dir
            })
            
            logger.info(f"Video queued for processing: {video_id}")
            
            # Don't clean up temp file here - it will be cleaned up after processing
            
            # Start processing if not already running
            if not self.is_processing:
                asyncio.create_task(self._process_queue())
                logger.info(f"Started processing queue for video {video_id}")
            
            return {
                "video_id": video_id,
                "filename": unique_filename,
                "original_name": filename,
                "status": "uploaded",
                "metadata": {
                    "duration": metadata.duration,
                    "fps": metadata.fps,
                    "resolution": f"{metadata.width}x{metadata.height}",                    "file_size": metadata.file_size
                }
            }
            
        except Exception as e:
            logger.error(f"Error uploading video: {e}")
            raise
    
    async def _process_queue(self):
        """Process videos in the queue"""
        
        if self.is_processing:
            return
        
        self.is_processing = True
        logger.info("Started video processing queue")
        
        try:
            while not self.processing_queue.empty():
                job = await self.processing_queue.get()
                await self._process_video_job(job)
                
        except Exception as e:
            logger.error(f"Error in processing queue: {e}")
        finally:
            self.is_processing = False
            logger.info("Video processing queue completed")
    
    async def _process_video_job(self, job: Dict[str, Any]):
        """Process a single video job"""
        
        video_id = job["video_id"]
        user_id = job["user_id"]
        filepath = job["filepath"]
        metadata = job["metadata"]
        cleanup_dir = job["cleanup_dir"]
        
        start_time = datetime.utcnow()
        
        try:
            # Update video status in Supabase
            try:
                supabase_client.get_admin_client().table("videos").update({"upload_status": "processing"}).eq("id", video_id).execute()
                logger.info(f"Updated video status in Supabase: {video_id} -> processing")
            except Exception as e:
                logger.error(f"Failed to update video status in Supabase: {e}")
                # Continue processing despite database update failure
            
            # Send processing update via logger (WebSocket removed)
            logger.info(f"Video processing started for video {video_id}")
            
            # Process video frames
            results = await self._process_video_frames(filepath, video_id, user_id, metadata)
            
            # Save results to database
            await self._save_processing_results(video_id, user_id, results)
            
            # Update video status in Supabase
            processing_results = {
                "frames_processed": len(results),
                "anomalies_detected": sum(1 for r in results if r.get("is_anomaly", False)),
                "processing_completed_at": datetime.utcnow().isoformat()
            }
            
            # Update video status in Supabase using admin client
            try:
                supabase_client.get_admin_client().table("videos").update({
                    "upload_status": "completed",
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", video_id).execute()
                logger.info(f"Updated video status in Supabase: {video_id} -> completed")
            except Exception as supabase_error:
                logger.error(f"Failed to update video status in Supabase: {supabase_error}")
            
            # Log completion update (WebSocket removed)
            logger.info(f"Video processing completed for video {video_id}")
            
            # Update statistics
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            self.stats["videos_processed"] += 1
            self.stats["frames_processed"] += len(results)
            self.stats["anomalies_detected"] += sum(1 for r in results if r.get("is_anomaly", False))
            self.stats["processing_time_total"] += processing_time
            
            logger.info(f"Video processing completed: {video_id} in {processing_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Error processing video {video_id}: {e}")
            
            # Update video status to failed
            try:
                supabase_client.get_admin_client().table("videos").update({
                    "upload_status": "failed",
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", video_id).execute()
                logger.info(f"Updated video status in Supabase: {video_id} -> failed")
            except Exception as supabase_error:
                logger.error(f"Failed to update video status in Supabase: {supabase_error}")
              # Log error update (WebSocket removed)
            logger.error(f"Video processing failed for video {video_id}: {str(e)}")
            
        finally:
            # Cleanup temporary files
            if cleanup_dir:
                try:
                    shutil.rmtree(cleanup_dir)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp directory: {e}")
    
    async def _process_video_frames(self, filepath: str, video_id: str, user_id: str, 
                                  metadata: VideoMetadata) -> List[Dict[str, Any]]:
        """Process all frames in a video"""
        
        results = []
        cap = cv2.VideoCapture(filepath)        
        try:
            frame_number = 0
            total_frames = metadata.frame_count
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Sample frames based on sampling rate
                if frame_number % self.frame_processor.frame_sampling_rate == 0:
                    # Process frame
                    result = await self.frame_processor.process_frame(
                        frame, frame_number, video_id, user_id, metadata.fps
                    )
                    results.append(result)
                    
                    # Log frame processed event (removed EventStream dependency)
                    logger.debug(f"Frame {frame_number} processed for video {video_id}: anomaly_score={result['anomaly_score']:.3f}")
                    
                    # Log progress (WebSocket removed)
                    if frame_number % 100 == 0:  # Log every 100 frames
                        progress = (frame_number / total_frames) * 100 if total_frames > 0 else 0
                        logger.info(f"Processing video {video_id}: {progress:.1f}% complete ({frame_number}/{total_frames} frames)")
                
                frame_number += 1
                
                # Yield control to allow other tasks
                if frame_number % 100 == 0:
                    await asyncio.sleep(0.01)
        finally:
            cap.release()
            
        return results
    
    async def _save_processing_results(self, video_id: str, user_id: str, 
                                     results: List[Dict[str, Any]]):
        """Save processing results to database"""
        
        for result in results:
            if result.get("is_anomaly", False):
                # Create event data
                event_data = {
                    "video_id": video_id,
                    "user_id": user_id,
                    "event_type": result["anomaly_type"],
                    "anomaly_score": result["anomaly_score"],
                    "confidence": result["confidence"],
                    "timestamp_seconds": result["timestamp_seconds"],
                    "frame_number": result["frame_number"],
                    "description": f"Anomaly detected: {result['anomaly_type']} with score {result['anomaly_score']:.2f}",                    "is_alert": float(result["anomaly_score"]) > 0.8
                }
                
                # Save to Supabase
                try:
                    # Insert event into Supabase events table using admin client to bypass RLS
                    supabase_client.get_admin_client().table("events").insert(event_data).execute()
                    logger.info(f"Event saved to Supabase: {event_data}")
                except Exception as e:
                    logger.error(f"Failed to save event to Supabase: {e}")
                    # Continue processing even if individual event save fails
                    logger.warning(f"Continuing processing despite event save failure")
    
    async def get_video_analysis(self, video_id: str, user_id: str) -> Dict[str, Any]:
        """Get analysis results for a video"""        
        try:
            # Get video record from Supabase
            video = supabase_client.get_video(video_id)
            if not video:
                raise Exception("Video not found")
            
            if video.get("user_id") != user_id:
                raise Exception("Access denied")
            
            # Get events from Supabase
            events = []
            try:
                # Query events table for this video
                response = supabase_client.get_admin_client() \
                    .table("events") \
                    .select("*") \
                    .eq("video_id", video_id) \
                    .order("timestamp_seconds", desc=False) \
                    .execute()
                
                if response.data:
                    events = response.data
                    logger.info(f"Retrieved {len(events)} events from Supabase for video {video_id}")
                else:
                    logger.info(f"No events found in Supabase for video {video_id}")
            except Exception as e:
                logger.error(f"Failed to fetch events from Supabase: {e}")
                # Return empty events list if fetch fails
                events = []
            # Calculate statistics
            total_events = len(events)
            anomaly_types = {}
            max_score = 0.0
            avg_score = 0.0
            
            for event in events:
                event_type = event["event_type"]
                anomaly_types[event_type] = anomaly_types.get(event_type, 0) + 1
                max_score = max(max_score, event["anomaly_score"])
                avg_score += event["anomaly_score"]
            
            if total_events > 0:
                avg_score /= total_events
              # Get current RL controller metrics
            rl_metrics = self.rl_controller.get_performance_metrics()
            
            # Get RAG system statistics
            rag_stats = self.rag_system.get_statistics()
            
            return {
                "video_id": video_id,
                "video_info": {
                    "filename": video["original_name"],
                    "duration": video.get("metadata", {}).get("duration", 0),
                    "fps": video.get("metadata", {}).get("fps", 0),
                    "resolution": f"{video.get('metadata', {}).get('width', 0)}x{video.get('metadata', {}).get('height', 0)}",
                    "upload_status": video["upload_status"]
                },
                "analysis_summary": {
                    "total_events": total_events,
                    "anomaly_types": anomaly_types,
                    "max_anomaly_score": max_score,
                    "avg_anomaly_score": avg_score,
                    "high_risk_events": sum(1 for e in events if float(e["anomaly_score"]) > 0.8)
                },
                "events": events,
                "rl_metrics": rl_metrics,
                "rag_stats": rag_stats
            }
            
        except Exception as e:
            logger.error(f"Error getting video analysis: {e}")
            raise
    
    async def provide_feedback(self, event_id: str, user_id: str, 
                             is_false_positive: bool, feedback_score: float) -> bool:
        """Provide feedback on an anomaly detection"""
        
        try:
            # Update event with feedback
            # Update event feedback (simplified - just log for demo)            logger.info(f"Event feedback updated: {event_id}, false_positive: {is_false_positive}")
            success = True
            
            if success:
                # Update RL controller with proper feedback format
                feedback = {
                    "false_positive": is_false_positive,
                    "false_negative": False,  # We don't have this info from current feedback
                    "score": feedback_score
                }
                self.rl_controller.adjust_threshold(feedback)
                
                # Update RAG system (if method exists)
                if hasattr(self.rag_system, 'update_pattern_from_feedback'):
                    self.rag_system.update_pattern_from_feedback(
                        event_id, feedback_score, {"is_false_positive": is_false_positive}
                    )
                
                logger.info(f"Feedback processed for event {event_id}: {feedback_score}")
                return True            
            return False
            
        except Exception as e:
            logger.error(f"Error processing feedback: {e}")
            return False
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status and metrics"""
        
        return {
            "status": "running",
            "queue_size": self.processing_queue.qsize(),
            "is_processing": self.is_processing,
            "statistics": self.stats,
            "rl_controller": self.rl_controller.get_training_summary(),
            "rag_system": self.rag_system.get_statistics(),
            "current_threshold": self.rl_controller.get_current_threshold()
        }


def get_system_status() -> Dict[str, Any]:
    """Get system status (utility function)"""
    return {
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "anomaly_detector": "loaded",
            "rl_controller": "active",
            "rag_system": "active"
        }
    }