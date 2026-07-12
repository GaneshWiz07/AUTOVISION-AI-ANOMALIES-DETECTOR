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

# Score above which an anomaly event is flagged as a high-priority alert.
ALERT_SCORE_THRESHOLD = float(os.getenv("ALERT_SCORE_THRESHOLD", "0.8"))

# Anomaly type classification thresholds. Each of these is checked against a
# genuinely measured, independent signal from ai_models/ml_anomaly_detector.py
# (real per-class object counts/labels from the COCO detector when it's
# available, else distinct moving-region count, real pixel/second
# displacement of the tracked region, real elapsed dwell time in one spot) -
# NOT slices of a single combined anomaly_score, which can't actually
# distinguish a crowd from a sprinting person from a loitering one.
NORMAL_SCORE_CEILING = float(os.getenv("NORMAL_SCORE_CEILING", "0.3"))
CROWD_PERSON_THRESHOLD = int(os.getenv("CROWD_PERSON_THRESHOLD", "3"))
CROWD_CONTOUR_THRESHOLD = int(os.getenv("CROWD_CONTOUR_THRESHOLD", "3"))
RUNNING_VELOCITY_PX_PER_SEC = float(os.getenv("RUNNING_VELOCITY_PX_PER_SEC", "150"))
LOITERING_DURATION_SECONDS = float(os.getenv("LOITERING_DURATION_SECONDS", "8"))


class AnomalyTypes:
    NORMAL = "normal"
    UNKNOWN = "unknown"
    RUNNING = "running"
    CROWD = "crowd_gathering"
    LOITERING = "loitering"
    MOTION_ANOMALY = "motion_anomaly"

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
            # Get current threshold from RL controller - this is the value
            # actually applied to the detection below, so RL feedback
            # (adjust_threshold) has a real effect on subsequent frames.
            current_threshold = self.rl_controller.get_current_threshold()

            # Detect anomaly (real per-video baseline, not a shared/global one).
            # frame_number/fps let the detector compute real elapsed time
            # between sampled frames, for genuine velocity/dwell-time tracking.
            detection_result = self.anomaly_detector.detect_anomaly(
                frame, video_id=video_id, threshold=current_threshold,
                frame_number=frame_number, fps=fps
            )

            # Extract features for RAG
            frame_features = self.anomaly_detector.extract_features(frame)
            
            # Determine anomaly type based on score and confidence
            anomaly_type = self._classify_anomaly_type(detection_result)
              # Create description for RAG analysis
            description = self._create_frame_description(detection_result, anomaly_type)
            
            # Analyze with RAG system (with fallback for missing method).
            # Pass the real measured signals through so RAG grounds its
            # confidence/context in them instead of re-deriving anything
            # from the description text.
            if hasattr(self.rag_system, 'analyze_detection'):
                detected_objects = detection_result.get("detected_objects") or []
                non_person_objects = [o for o in detected_objects if o["label"] != "person"]
                top_object_confidence = (
                    max((o["confidence"] for o in non_person_objects), default=0.0)
                )
                rag_analysis = self.rag_system.analyze_detection(
                    description,
                    detection_result["anomaly_score"],
                    anomaly_type,
                    signals={
                        "motion_score": detection_result.get("motion_score", 0.0),
                        "appearance_score": detection_result.get("appearance_score", 0.0),
                        "contour_count": detection_result.get("contour_count", 0),
                        "velocity_px_per_sec": detection_result.get("velocity_px_per_sec", 0.0),
                        "loiter_duration_seconds": detection_result.get("loiter_duration_seconds", 0.0),
                        "object_counts": detection_result.get("object_counts", {}),
                        "person_count": detection_result.get("object_counts", {}).get("person", 0),
                        "top_object_confidence": top_object_confidence,
                    }
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

            # Prepare result
            result = {
                "frame_number": frame_number,
                "timestamp_seconds": frame_number / fps,  # Use actual video FPS
                "anomaly_score": detection_result["anomaly_score"],
                "is_anomaly": detection_result["is_anomaly"],
                "anomaly_type": anomaly_type,
                "confidence": adjusted_confidence,
                "original_confidence": detection_result["anomaly_confidence"],
                "threshold_used": current_threshold,
                "bounding_box": detection_result.get("bounding_box"),
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

                # Persist the pattern (with its real embedding) so RAG retrieval
                # survives restarts and can be shared across videos for this user.
                try:
                    await supabase_client.save_historical_pattern(
                        user_id=user_id,
                        pattern_type=anomaly_type,
                        embedding=frame_features.tolist(),
                        description=f"{anomaly_type} pattern",
                        metadata={
                            "video_id": video_id,
                            "frame_number": frame_number,
                            "anomaly_score": detection_result["anomaly_score"]
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to persist historical pattern: {e}")

                # Surface real, persisted similar-pattern history (ranked by
                # cosine similarity of the actual frame embedding) into the
                # analysis context, rather than only the in-process cache.
                try:
                    similar_patterns = supabase_client.search_similar_patterns(
                        user_id=user_id,
                        embedding=frame_features.tolist(),
                        pattern_type=anomaly_type,
                        limit=3
                    )
                    if similar_patterns:
                        result["rag_analysis"].setdefault("context", {})["similar_historical_patterns"] = [
                            {
                                "description": p.get("description"),
                                "frequency_count": p.get("frequency_count"),
                                "last_seen": p.get("last_seen"),
                            }
                            for p in similar_patterns
                        ]
                except Exception as e:
                    logger.warning(f"Failed to retrieve similar historical patterns: {e}")

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
        """
        Classify the type of anomaly from genuinely distinguishable signals -
        never guessed from where the combined anomaly_score happens to fall.

        Priority order:
        1. Verified person-count/behavior (crowd/running/loitering), using
           the real COCO object detector's "person" count when it's
           available - falling back to generic moving-region count only if
           the detector couldn't load.
        2. Any *other* real object the detector confidently recognized
           (car, dog, backpack, knife, suitcase, ...) - reported by its
           actual label, open-ended across all ~90 COCO categories, not a
           fixed enum of guessed behaviors.
        3. An honest "normal" / "motion_anomaly" catch-all when nothing
           specific was recognized.
        """
        anomaly_score = detection_result["anomaly_score"]
        contour_count = detection_result.get("contour_count", 0)
        velocity = detection_result.get("velocity_px_per_sec", 0.0)
        loiter_duration = detection_result.get("loiter_duration_seconds", 0.0)
        object_counts = detection_result.get("object_counts", {}) or {}
        detected_objects = detection_result.get("detected_objects", []) or []

        person_count = object_counts.get("person", 0)
        objects_available = bool(object_counts) or "detected_objects" in detection_result

        if person_count > 0:
            if person_count >= CROWD_PERSON_THRESHOLD:
                return AnomalyTypes.CROWD
            if velocity >= RUNNING_VELOCITY_PX_PER_SEC:
                return AnomalyTypes.RUNNING
            if loiter_duration >= LOITERING_DURATION_SECONDS:
                return AnomalyTypes.LOITERING
        elif not objects_available and contour_count >= CROWD_CONTOUR_THRESHOLD:
            # Object detector unavailable (e.g. model download failed) -
            # fall back to counting distinct moving regions, same as before.
            return AnomalyTypes.CROWD

        # No specific person-behavior pattern - but did the detector
        # recognize some *other* real object worth naming directly?
        non_person = [o for o in detected_objects if o["label"] != "person"]
        if non_person:
            top = max(non_person, key=lambda o: o["confidence"])
            return f"{top['label']}_detected"

        if velocity >= RUNNING_VELOCITY_PX_PER_SEC:
            return AnomalyTypes.RUNNING
        if loiter_duration >= LOITERING_DURATION_SECONDS:
            return AnomalyTypes.LOITERING
        if anomaly_score < NORMAL_SCORE_CEILING:
            return AnomalyTypes.NORMAL
        # Something measurably changed (motion and/or appearance drift) but
        # doesn't match a more specific pattern above - an honest catch-all
        # rather than forcing it into "intrusion"/"fighting" with no basis.
        return AnomalyTypes.MOTION_ANOMALY
    
    def _create_frame_description(self, detection_result: Dict[str, Any], anomaly_type: str) -> str:
        """Create a textual description of the frame for RAG analysis"""

        score = detection_result["anomaly_score"]
        confidence = detection_result["anomaly_confidence"]
        object_counts = detection_result.get("object_counts") or {}
        objects_summary = ", ".join(f"{count} {label}" for label, count in object_counts.items())

        if anomaly_type == AnomalyTypes.NORMAL:
            return f"Normal surveillance scene with low anomaly score ({score:.2f})"
        if anomaly_type.endswith("_detected"):
            label = anomaly_type[: -len("_detected")].replace("_", " ")
            return (f"Recognized {label} in frame with score {score:.2f} and confidence "
                    f"{confidence:.2f}" + (f" (also visible: {objects_summary})" if objects_summary else ""))
        base = f"{anomaly_type.replace('_', ' ').title()} detected with score {score:.2f} and confidence {confidence:.2f}"
        return base + (f" ({objects_summary})" if objects_summary else "")


class VideoProcessor:
    """Main video processing class"""
    
    def __init__(self):
        # Initialize AI models. VideoProcessor is a long-lived singleton
        # (created once in main.py's lifespan and stored in app.state), so
        # this only runs once per process - RL/RAG state persists across
        # requests instead of being rebuilt (and reloaded) on every call.
        self.anomaly_detector = create_anomaly_detector()
        self.rl_controller = create_rl_controller()
        self.rag_system = create_rag_system()
        self._hydrate_rl_threshold()

        if not hasattr(self.rag_system, 'analyze_detection'):
            logger.error("RAG system missing analyze_detection method!")

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

    def _hydrate_rl_threshold(self):
        """
        Restore the RL controller's threshold from the last persisted
        training step, so it survives process restarts instead of always
        resetting to the static ANOMALY_THRESHOLD env default. The RL
        controller is a single process-wide instance (not per-user), so this
        pulls the single most recent step across all users.
        """
        try:
            result = supabase_client.get_admin_client().table("rl_training_data") \
                .select("next_state_vector").order("created_at", desc=True).limit(1).execute()
            if result.data and result.data[0].get("next_state_vector"):
                restored = float(result.data[0]["next_state_vector"][0])
                self.rl_controller.current_threshold = restored
                logger.info(f"Restored RL threshold from persisted training data: {restored:.3f}")
        except Exception as e:
            logger.warning(f"Could not restore RL threshold from history, using default: {e}")

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
                    "storage_provider": storage_result['storage_provider'],  # Use provider from storage result
                    "storage_id": storage_result.get('storage_id')
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
            
            logger.info(f"Video uploaded event for user {user_id}, video {video_id}, filename {filename}")
            await supabase_client.create_log(
                message=f"Video uploaded: {filename}",
                log_level="INFO",
                user_id=user_id,
                video_id=video_id
            )

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

            logger.info(f"Video processing started for video {video_id}")
            await supabase_client.create_log(
                message=f"Video processing started: {video_id}",
                log_level="INFO", user_id=user_id, video_id=video_id
            )

            # Use the user's configured frame sampling rate, falling back to
            # the process-wide default (FRAME_SAMPLING_RATE env) if unset.
            frame_sampling_rate = self.frame_processor.frame_sampling_rate
            try:
                settings_result = supabase_client.get_admin_client().table("user_settings") \
                    .select("frame_sampling_rate").eq("user_id", user_id).execute()
                if settings_result.data and settings_result.data[0].get("frame_sampling_rate"):
                    frame_sampling_rate = settings_result.data[0]["frame_sampling_rate"]
            except Exception as e:
                logger.warning(f"Could not load user frame sampling rate, using default: {e}")

            # Process video frames
            results = await self._process_video_frames(
                filepath, video_id, user_id, metadata, frame_sampling_rate
            )

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

            logger.info(f"Video processing completed for video {video_id}")

            # Update statistics
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            anomalies_detected = sum(1 for r in results if r.get("is_anomaly", False))
            self.stats["videos_processed"] += 1
            self.stats["frames_processed"] += len(results)
            self.stats["anomalies_detected"] += anomalies_detected
            self.stats["processing_time_total"] += processing_time

            logger.info(f"Video processing completed: {video_id} in {processing_time:.2f}s")
            await supabase_client.create_log(
                message=f"Video processing completed: {len(results)} frames, {anomalies_detected} anomalies",
                log_level="INFO", user_id=user_id, video_id=video_id
            )

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

            logger.error(f"Video processing failed for video {video_id}: {str(e)}")
            await supabase_client.create_log(
                message=f"Video processing failed: {str(e)}",
                log_level="ERROR", user_id=user_id, video_id=video_id
            )

        finally:
            # Release the detector's per-video baseline/background model now
            # that this video is done, so memory doesn't grow unbounded.
            if hasattr(self.anomaly_detector, "finalize_video"):
                self.anomaly_detector.finalize_video(video_id)

            # Cleanup temporary files
            if cleanup_dir:
                try:
                    shutil.rmtree(cleanup_dir)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp directory: {e}")
    
    async def _process_video_frames(self, filepath: str, video_id: str, user_id: str,
                                  metadata: VideoMetadata,
                                  frame_sampling_rate: Optional[int] = None) -> List[Dict[str, Any]]:
        """Process all frames in a video"""

        sampling_rate = frame_sampling_rate or self.frame_processor.frame_sampling_rate

        results = []
        cap = cv2.VideoCapture(filepath)
        try:
            frame_number = 0
            total_frames = metadata.frame_count

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Sample frames based on the user's configured sampling rate
                if frame_number % sampling_rate == 0:
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
                    "bounding_box": result.get("bounding_box"),
                    "description": f"Anomaly detected: {result['anomaly_type']} with score {result['anomaly_score']:.2f}",
                    "is_alert": float(result["anomaly_score"]) > ALERT_SCORE_THRESHOLD
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
                    "duration": video.get("duration_seconds", 0),
                    "fps": video.get("fps", 0),
                    "resolution": video.get("resolution", ""),
                    "upload_status": video["upload_status"]
                },
                "analysis_summary": {
                    "total_events": total_events,
                    "anomaly_types": anomaly_types,
                    "max_anomaly_score": max_score,
                    "avg_anomaly_score": avg_score,
                    "high_risk_events": sum(1 for e in events if float(e["anomaly_score"]) > ALERT_SCORE_THRESHOLD)
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
            # Verify the event exists and belongs to this user before mutating it
            event = supabase_client.get_admin_client().table("events") \
                .select("id, user_id").eq("id", event_id).execute()
            if not event.data:
                logger.warning(f"Feedback rejected: event {event_id} not found")
                return False
            if event.data[0]["user_id"] != user_id:
                logger.warning(f"Feedback rejected: event {event_id} does not belong to user {user_id}")
                return False

            # Persist the feedback on the event itself
            updated = supabase_client.update_event_feedback(event_id, is_false_positive)
            if not updated:
                return False

            threshold_before = self.rl_controller.get_current_threshold()

            # Update RL controller with proper feedback format
            feedback = {
                "false_positive": is_false_positive,
                "false_negative": False,  # We don't have this info from current feedback
                "score": feedback_score
            }
            threshold_after = self.rl_controller.adjust_threshold(feedback)

            # Persist the RL step so training state survives restarts and can
            # be inspected/replayed later.
            try:
                await supabase_client.save_rl_training_data(
                    user_id=user_id,
                    state_vector=[threshold_before],
                    action=1 if is_false_positive else 0,
                    reward=feedback_score,
                    next_state_vector=[threshold_after],
                    done=False
                )
            except Exception as e:
                logger.warning(f"Failed to persist RL training data: {e}")

            # Update RAG system (if method exists)
            if hasattr(self.rag_system, 'update_pattern_from_feedback'):
                self.rag_system.update_pattern_from_feedback(
                    event_id, feedback_score, {"is_false_positive": is_false_positive}
                )

            logger.info(f"Feedback processed for event {event_id}: {feedback_score}")
            await supabase_client.create_log(
                message=f"Feedback recorded for event {event_id}: false_positive={is_false_positive}, score={feedback_score}",
                log_level="INFO", user_id=user_id, event_id=event_id
            )
            return True

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