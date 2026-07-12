"""
Simple anomaly detector for AutoVision
Legacy/demo fallback only. The active detector is MLAnomalyDetector
(ai_models/ml_anomaly_detector.py), selected by create_anomaly_detector()
whenever USE_PRETRAINED_MODELS is enabled (the default).
"""

import numpy as np
from typing import Dict, Any, List
import os
from loguru import logger
import time


class SimpleAnomalyDetector:
    """
    Legacy demo anomaly detector implementation for AutoVision

    Uses random scores for demo purposes only and ignores the actual frame.
    Kept solely as an opt-out fallback (USE_PRETRAINED_MODELS=false) for
    environments where the ML detector's dependencies are unavailable.
    """
    
    def __init__(self):
        """Initialize the anomaly detector"""
        # Configuration
        self.threshold = float(os.getenv("ANOMALY_THRESHOLD", "0.5"))
        self.min_score = float(os.getenv("MIN_ANOMALY_SCORE", "0.1"))
        
        # Model would be loaded here in a real application
        logger.info(f"Simple anomaly detector initialized with threshold {self.threshold}")
    
    def detect_anomaly(self, frame: np.ndarray, video_id: str = None,
                        threshold: float = None, frame_number: int = None,
                        fps: float = None) -> Dict[str, Any]:
        """
        Detect anomalies in a video frame

        Args:
            frame: BGR video frame
            video_id, frame_number, fps: unused here, accepted for interface
                parity with MLAnomalyDetector
            threshold: overrides self.threshold when provided (e.g. from the RL controller)

        Returns:
            Dict with detection results
        """
        if threshold is not None:
            self.threshold = threshold
        # In a real model, we'd process the frame here
        # For demo, use a pseudo-random score with some time-based variation
        time_factor = (int(time.time()) % 60) / 60.0  # Value between 0-1 that changes every minute
        
        # Generate a score that varies over time but stays somewhat consistent
        # for short periods (simulates detection of actual events)
        anomaly_score = max(self.min_score, min(0.9, 
                          0.3 + 0.4 * np.sin(time_factor * np.pi * 2) + 0.2 * np.random.random()))
        
        # Add some randomness for occasional anomalies
        if np.random.random() < 0.05:  # 5% chance of spike
            anomaly_score = min(1.0, anomaly_score + 0.3)
        
        # Determine if this is an anomaly
        is_anomaly = anomaly_score > self.threshold
        
        # Calculate confidence (how certain we are about this classification)
        confidence = abs(anomaly_score - self.threshold) * 1.5
        confidence = min(0.95, max(0.5, confidence))  # Limit to 0.5-0.95 range
        
        return {
            "anomaly_score": anomaly_score,
            "is_anomaly": is_anomaly,
            "anomaly_confidence": confidence,
            "bounding_box": None,
            "motion_score": 0.0,
            "appearance_score": 0.0,
            "contour_count": 0,
            "velocity_px_per_sec": 0.0,
            "loiter_duration_seconds": 0.0,
            "detected_objects": [],
            "object_counts": {},
        }
    
    def extract_features(self, frame: np.ndarray) -> np.ndarray:
        """Extract feature vector from frame for RAG analysis"""
        # In a real implementation, this would extract meaningful features
        # For demo purposes, return random features
        return np.random.random(100)  # Return 100-dimensional feature vector


def create_anomaly_detector():
    """
    Factory function to create and initialize the anomaly detector.

    Returns the real MLAnomalyDetector (MobileNetV2 appearance embedding +
    OpenCV motion analysis) unless explicitly disabled via
    USE_PRETRAINED_MODELS=false, in which case the legacy random-score demo
    detector above is used instead.
    """
    use_pretrained = os.getenv("USE_PRETRAINED_MODELS", "true").strip().lower() in ("true", "1", "yes")
    if use_pretrained:
        from ai_models.ml_anomaly_detector import create_ml_anomaly_detector
        return create_ml_anomaly_detector()
    logger.warning("USE_PRETRAINED_MODELS disabled - using legacy random-score demo detector")
    return SimpleAnomalyDetector()
