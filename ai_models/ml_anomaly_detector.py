"""
ML-based anomaly detector for AutoVision.

Combines three real, independent signals per sampled frame:
  1. Appearance drift - a frozen MobileNetV2 (ONNX Runtime, CPU) embedding
     compared against a running per-video baseline.
  2. Motion - OpenCV background subtraction (contours -> bounding box,
     region count, tracked centroid -> real displacement speed and dwell
     time).
  3. Object identity - a small COCO-trained SSD detector (ONNX Runtime, CPU)
     that recognizes 90 real object categories (person, car, bicycle, dog,
     backpack, knife, ...) with actual per-class counts and boxes, not a
     fixed enum of guessed behaviors.

The anomaly *type* (see backend/video_processor.py's _classify_anomaly_type)
is decided from these measured signals - never from slicing a single
combined score, and never randomly generated.

Chosen specifically to fit free-tier hosting memory limits (~512MB): ONNX
Runtime + MobileNetV2 + the (int8-quantized) SSD detector together add
roughly 200-350MB RSS, versus 800MB+ for a PyTorch/ViT-based equivalent. If
either model's weights are unavailable (no onnxruntime installed, or the
one-time download fails because the host has no outbound network access),
that piece degrades gracefully - appearance falls back to a grayscale
histogram, object identity is simply omitted - so scoring is always derived
from real frame pixels and never randomized, just less detailed.
"""

import os
import threading
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
from loguru import logger

# Official ONNX Model Zoo release asset - a small (~13.6MB), CPU-friendly
# pretrained classifier used purely as a frozen feature extractor.
MOBILENET_ONNX_URL = (
    "https://github.com/onnx/models/raw/main/validated/vision/classification/"
    "mobilenet/model/mobilenetv2-7.onnx"
)
MOBILENET_FILENAME = "mobilenetv2-7.onnx"
EMBEDDING_DIM = 100  # matches the historical feature-vector contract used elsewhere
INPUT_SIZE = 224
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

# Official ONNX Model Zoo release asset, int8-quantized (~9.5MB vs ~28MB for
# the fp32 version) - a COCO-trained SSD-MobileNetV1 object detector. NMS is
# already baked into the exported graph, and it accepts raw uint8 frames at
# their native resolution (no manual resize/normalization needed).
OBJECT_DETECTOR_ONNX_URL = (
    "https://github.com/onnx/models/raw/main/validated/vision/object_detection_segmentation/"
    "ssd-mobilenetv1/model/ssd_mobilenet_v1_12-int8.onnx"
)
OBJECT_DETECTOR_FILENAME = "ssd_mobilenet_v1_12-int8.onnx"
OBJECT_DETECTION_MIN_CONFIDENCE = float(os.getenv("OBJECT_DETECTION_MIN_CONFIDENCE", "0.5"))

# The standard 90-class COCO label map (note: IDs 12, 26, 29, 30, 45, 66, 68,
# 69, 71, 83 are genuinely absent - a long-standing artifact of the original
# COCO category list this model was trained against).
COCO_LABELS = {
    1: "person", 2: "bicycle", 3: "car", 4: "motorcycle", 5: "airplane", 6: "bus",
    7: "train", 8: "truck", 9: "boat", 10: "traffic light", 11: "fire hydrant",
    13: "stop sign", 14: "parking meter", 15: "bench", 16: "bird", 17: "cat",
    18: "dog", 19: "horse", 20: "sheep", 21: "cow", 22: "elephant", 23: "bear",
    24: "zebra", 25: "giraffe", 27: "backpack", 28: "umbrella", 31: "handbag",
    32: "tie", 33: "suitcase", 34: "frisbee", 35: "skis", 36: "snowboard",
    37: "sports ball", 38: "kite", 39: "baseball bat", 40: "baseball glove",
    41: "skateboard", 42: "surfboard", 43: "tennis racket", 44: "bottle",
    46: "wine glass", 47: "cup", 48: "fork", 49: "knife", 50: "spoon",
    51: "bowl", 52: "banana", 53: "apple", 54: "sandwich", 55: "orange",
    56: "broccoli", 57: "carrot", 58: "hot dog", 59: "pizza", 60: "donut",
    61: "cake", 62: "chair", 63: "couch", 64: "potted plant", 65: "bed",
    67: "dining table", 70: "toilet", 72: "tv", 73: "laptop", 74: "mouse",
    75: "remote", 76: "keyboard", 77: "cell phone", 78: "microwave", 79: "oven",
    80: "toaster", 81: "sink", 82: "refrigerator", 84: "book", 85: "clock",
    86: "vase", 87: "scissors", 88: "teddy bear", 89: "hair drier", 90: "toothbrush",
}

MAX_TRACKED_VIDEOS = 8  # bound memory for per-video background models


class _MobileNetFeatureExtractor:
    """Lazily-loaded singleton ONNX Runtime session wrapping MobileNetV2."""

    _lock = threading.Lock()
    _instance: Optional["_MobileNetFeatureExtractor"] = None

    def __init__(self):
        self.session = None
        self.input_name = None
        self.available = False
        self._load()

    @classmethod
    def get(cls) -> "_MobileNetFeatureExtractor":
        with cls._lock:
            if cls._instance is None:
                cls._instance = _MobileNetFeatureExtractor()
            return cls._instance

    def _model_path(self) -> str:
        cache_dir = os.getenv("MODEL_CACHE_DIR", "./models")
        os.makedirs(cache_dir, exist_ok=True)
        return os.path.join(cache_dir, MOBILENET_FILENAME)

    def _download(self, path: str) -> bool:
        try:
            import requests

            logger.info(f"Downloading MobileNetV2 ONNX model to {path}...")
            response = requests.get(MOBILENET_ONNX_URL, timeout=30, stream=True)
            response.raise_for_status()
            with open(path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1 << 16):
                    f.write(chunk)
            logger.info("MobileNetV2 model downloaded successfully")
            return True
        except Exception as e:
            logger.warning(f"Could not download MobileNetV2 model ({e}); "
                            f"falling back to classical CV feature extraction")
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
            return False

    def _load(self):
        try:
            import onnxruntime as ort
        except ImportError:
            logger.warning("onnxruntime not installed; using classical CV fallback for detection")
            return

        path = self._model_path()
        if not os.path.exists(path):
            if not self._download(path):
                return

        try:
            options = ort.SessionOptions()
            options.intra_op_num_threads = 1
            options.inter_op_num_threads = 1
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self.session = ort.InferenceSession(path, sess_options=options,
                                                 providers=["CPUExecutionProvider"])
            self.input_name = self.session.get_inputs()[0].name
            self.available = True
            logger.info("MobileNetV2 ONNX model loaded for anomaly feature extraction")
        except Exception as e:
            logger.warning(f"Failed to initialize ONNX Runtime session ({e}); "
                            f"falling back to classical CV feature extraction")
            self.session = None
            self.available = False

    def embed(self, frame_bgr: np.ndarray) -> Optional[np.ndarray]:
        """Run the frame through MobileNetV2 and return a reduced 100-d probability vector."""
        if not self.available or self.session is None:
            return None

        try:
            resized = cv2.resize(frame_bgr, (INPUT_SIZE, INPUT_SIZE), interpolation=cv2.INTER_AREA)
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            normalized = (rgb - IMAGENET_MEAN) / IMAGENET_STD
            nchw = np.transpose(normalized, (2, 0, 1))[np.newaxis, ...].astype(np.float32)

            logits = self.session.run(None, {self.input_name: nchw})[0].reshape(-1)
            # softmax
            exp = np.exp(logits - np.max(logits))
            probs = exp / np.sum(exp)

            # Deterministically reduce the 1000-class distribution to a fixed
            # 100-d vector by averaging consecutive chunks.
            chunk_size = len(probs) // EMBEDDING_DIM
            if chunk_size == 0:
                return probs[:EMBEDDING_DIM]
            trimmed = probs[: chunk_size * EMBEDDING_DIM]
            return trimmed.reshape(EMBEDDING_DIM, chunk_size).mean(axis=1)
        except Exception as e:
            logger.error(f"MobileNetV2 inference failed on frame: {e}")
            return None


class _ObjectDetector:
    """Lazily-loaded singleton ONNX Runtime session wrapping a COCO-trained
    SSD-MobileNetV1 detector - real, per-class object recognition (person,
    car, bicycle, dog, backpack, knife, ...) rather than an unlabeled
    motion blob."""

    _lock = threading.Lock()
    _instance: Optional["_ObjectDetector"] = None

    def __init__(self):
        self.session = None
        self.input_name = None
        self.available = False
        self._load()

    @classmethod
    def get(cls) -> "_ObjectDetector":
        with cls._lock:
            if cls._instance is None:
                cls._instance = _ObjectDetector()
            return cls._instance

    def _model_path(self) -> str:
        cache_dir = os.getenv("MODEL_CACHE_DIR", "./models")
        os.makedirs(cache_dir, exist_ok=True)
        return os.path.join(cache_dir, OBJECT_DETECTOR_FILENAME)

    def _download(self, path: str) -> bool:
        try:
            import requests

            logger.info(f"Downloading SSD-MobileNetV1 object detector to {path}...")
            response = requests.get(OBJECT_DETECTOR_ONNX_URL, timeout=60, stream=True)
            response.raise_for_status()
            with open(path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1 << 16):
                    f.write(chunk)
            logger.info("SSD-MobileNetV1 object detector downloaded successfully")
            return True
        except Exception as e:
            logger.warning(f"Could not download object detector model ({e}); "
                            f"object identity will be omitted from detections")
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
            return False

    def _load(self):
        try:
            import onnxruntime as ort
        except ImportError:
            logger.warning("onnxruntime not installed; object detection unavailable")
            return

        path = self._model_path()
        if not os.path.exists(path):
            if not self._download(path):
                return

        try:
            options = ort.SessionOptions()
            options.intra_op_num_threads = 1
            options.inter_op_num_threads = 1
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self.session = ort.InferenceSession(path, sess_options=options,
                                                 providers=["CPUExecutionProvider"])
            self.input_name = self.session.get_inputs()[0].name
            self.available = True
            logger.info("SSD-MobileNetV1 object detector loaded")
        except Exception as e:
            logger.warning(f"Failed to initialize object detector session ({e}); "
                            f"object identity will be omitted from detections")
            self.session = None
            self.available = False

    def detect(self, frame_bgr: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect real objects in a frame. Returns a list of
        {label, confidence, bounding_box} for every detection above
        OBJECT_DETECTION_MIN_CONFIDENCE - an empty list if the model isn't
        available or nothing was confidently detected, never a guess.
        """
        if not self.available or self.session is None:
            return []

        try:
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            height, width = rgb.shape[:2]
            input_tensor = rgb[np.newaxis, ...].astype(np.uint8)

            boxes, classes, scores, num = self.session.run(None, {self.input_name: input_tensor})
            count = int(num[0])

            detections = []
            for i in range(count):
                score = float(scores[0][i])
                if score < OBJECT_DETECTION_MIN_CONFIDENCE:
                    continue
                label = COCO_LABELS.get(int(classes[0][i]))
                if label is None:
                    continue
                # TF SSD boxes are normalized [ymin, xmin, ymax, xmax]
                ymin, xmin, ymax, xmax = boxes[0][i]
                detections.append({
                    "label": label,
                    "confidence": score,
                    "bounding_box": {
                        "x": int(xmin * width),
                        "y": int(ymin * height),
                        "width": int((xmax - xmin) * width),
                        "height": int((ymax - ymin) * height),
                    },
                })
            return detections
        except Exception as e:
            logger.error(f"Object detection failed on frame: {e}")
            return []


class _VideoState:
    """Per-video running baseline + motion model, so scores reflect deviation
    from that specific video's own normal activity rather than drifting
    across unrelated videos processed by the same detector instance."""

    def __init__(self):
        self.baseline: Optional[np.ndarray] = None
        # `history` caps the ceiling of MOG2's *automatic* learning rate
        # (1/min(history, frames_seen)); a fixed learningRate is passed
        # explicitly on every .apply() call instead (see MLAnomalyDetector),
        # so this mostly just needs to not be tiny.
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=16, detectShadows=False
        )
        self.frame_count = 0

        # Real position tracking of the dominant moving region, used to
        # derive genuine displacement speed (-> "running") and dwell time
        # (-> "loitering") instead of guessing a type from a single score.
        self.last_centroid: Optional[tuple] = None
        self.last_timestamp: Optional[float] = None
        self.loiter_anchor: Optional[tuple] = None
        self.loiter_start_timestamp: Optional[float] = None


class MLAnomalyDetector:
    """
    Real anomaly detector: combines a frozen pretrained-CNN appearance
    embedding (semantic drift from a per-video baseline) with OpenCV
    background-subtraction motion analysis. Every score is derived from the
    actual frame pixels; nothing here is randomly generated.
    """

    def __init__(self):
        self.threshold = float(os.getenv("ANOMALY_THRESHOLD", "0.5"))
        self.min_score = float(os.getenv("MIN_ANOMALY_SCORE", "0.05"))
        self.baseline_alpha = 0.05  # EMA rate for adapting to slow scene drift
        self.motion_weight = 0.4
        self.appearance_weight = 0.6
        self.min_contour_area = 500
        self.loiter_radius_px = 40  # max centroid drift still counted as "same spot"
        # Fixed (not "auto") background-model learning rate - see the note
        # in detect_anomaly() on why this matters for loitering detection.
        self.bg_learning_rate = float(os.getenv("BG_LEARNING_RATE", "0.0015"))

        self._feature_extractor = _MobileNetFeatureExtractor.get()
        self._object_detector = _ObjectDetector.get()
        self._video_states: Dict[str, _VideoState] = {}
        self._state_order: List[str] = []

        logger.info(
            f"ML anomaly detector initialized (mobilenet_available="
            f"{self._feature_extractor.available}, object_detector_available="
            f"{self._object_detector.available}, threshold={self.threshold})"
        )

    def _get_state(self, video_id: str) -> _VideoState:
        if video_id not in self._video_states:
            if len(self._state_order) >= MAX_TRACKED_VIDEOS:
                oldest = self._state_order.pop(0)
                self._video_states.pop(oldest, None)
            self._video_states[video_id] = _VideoState()
            self._state_order.append(video_id)
        return self._video_states[video_id]

    def finalize_video(self, video_id: str):
        """Release per-video state once processing for that video is done."""
        self._video_states.pop(video_id, None)
        if video_id in self._state_order:
            self._state_order.remove(video_id)

    def extract_features(self, frame: np.ndarray) -> np.ndarray:
        """Extract a real, frame-dependent 100-d feature vector."""
        embedding = self._feature_extractor.embed(frame)
        if embedding is not None:
            return embedding.astype(np.float32)

        # Classical CV fallback: grayscale intensity histogram, still real
        # per-frame signal, never random.
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        hist = cv2.calcHist([gray], [0], None, [EMBEDDING_DIM], [0, 256]).reshape(-1)
        total = hist.sum()
        return (hist / total if total > 0 else hist).astype(np.float32)

    def detect_anomaly(self, frame: np.ndarray, video_id: Optional[str] = None,
                        threshold: Optional[float] = None,
                        frame_number: Optional[int] = None,
                        fps: Optional[float] = None) -> Dict[str, Any]:
        """
        Detect anomalies in a video frame using real motion + appearance analysis.

        Args:
            frame: BGR video frame
            video_id: identifies the video so baselines don't leak across videos
            threshold: current detection threshold (typically from the RL
                controller); falls back to the static env-configured threshold
                if not provided
            frame_number, fps: used to compute real elapsed time between
                sampled frames, so velocity/dwell-time below are measured in
                actual pixels-per-second and seconds, not frame counts

        Returns:
            Dict with anomaly_score, is_anomaly, anomaly_confidence,
            bounding_box, motion_score, appearance_score, contour_count,
            velocity_px_per_sec, loiter_duration_seconds, detected_objects
            (list of {label, confidence, bounding_box} for every real COCO
            object recognized above OBJECT_DETECTION_MIN_CONFIDENCE), and
            object_counts (label -> count). Every field is derived from the
            actual frame/video, none of it is guessed from a single scalar.
        """
        state = self._get_state(video_id or "default")
        active_threshold = threshold if threshold is not None else self.threshold
        timestamp_seconds = (frame_number / fps) if (frame_number is not None and fps) else None

        # --- Motion analysis (real, from pixel differences) ---
        # A fixed, small learning rate (rather than OpenCV's "auto" -1,
        # which computes ~1/frames_seen_so_far) matters specifically for
        # loitering detection: with "auto", a stationary subject gets
        # absorbed into the background within a few seconds of any video's
        # start (when frames_seen_so_far is still small, the auto rate is
        # large) - erasing the exact foreground signal loitering depends on.
        # A small constant rate keeps someone standing mostly still
        # classified as foreground for tens of seconds, regardless of how
        # early in the video this is.
        fg_mask = state.bg_subtractor.apply(frame, learningRate=self.bg_learning_rate)
        motion_ratio = float(np.count_nonzero(fg_mask)) / fg_mask.size

        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        significant_contours = [c for c in contours if cv2.contourArea(c) >= self.min_contour_area]
        contour_count = len(significant_contours)

        bounding_box = None
        centroid = None
        if significant_contours:
            largest = max(significant_contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(largest)
            bounding_box = {"x": int(x), "y": int(y), "width": int(w), "height": int(h)}
            centroid = (x + w / 2.0, y + h / 2.0)

        motion_score = min(1.0, motion_ratio * 8.0)  # scale so typical activity approaches 1.0

        # --- Object identity (real, per-class - what backend/video_processor.py
        # uses to answer "any kind of thing", not just "something moved") ---
        detected_objects = self._object_detector.detect(frame)
        object_counts: Dict[str, int] = {}
        for obj in detected_objects:
            object_counts[obj["label"]] = object_counts.get(obj["label"], 0) + 1

        # A recognized object's box is more meaningful than a generic motion
        # blob - prefer the highest-confidence detection's box when we have one.
        if detected_objects:
            top_object = max(detected_objects, key=lambda o: o["confidence"])
            bounding_box = top_object["bounding_box"]

        # --- Real position tracking of the dominant moving region ---
        # This is what actually grounds "running" (fast displacement) and
        # "loitering" (staying in one spot) in measured pixel motion, rather
        # than picking a label out of a fixed anomaly_score range.
        velocity_px_per_sec = 0.0
        loiter_duration_seconds = 0.0

        if centroid is not None:
            if (centroid is not None and state.last_centroid is not None
                    and state.last_timestamp is not None and timestamp_seconds is not None):
                dt = timestamp_seconds - state.last_timestamp
                if dt > 0:
                    displacement = float(np.hypot(centroid[0] - state.last_centroid[0],
                                                   centroid[1] - state.last_centroid[1]))
                    velocity_px_per_sec = displacement / dt

            if state.loiter_anchor is None:
                state.loiter_anchor = centroid
                state.loiter_start_timestamp = timestamp_seconds
            else:
                drift = float(np.hypot(centroid[0] - state.loiter_anchor[0],
                                        centroid[1] - state.loiter_anchor[1]))
                if drift <= self.loiter_radius_px:
                    if state.loiter_start_timestamp is not None and timestamp_seconds is not None:
                        loiter_duration_seconds = max(0.0, timestamp_seconds - state.loiter_start_timestamp)
                else:
                    state.loiter_anchor = centroid
                    state.loiter_start_timestamp = timestamp_seconds

            state.last_centroid = centroid
            state.last_timestamp = timestamp_seconds
        else:
            # Nothing moving right now - any in-progress loiter/track resets.
            state.loiter_anchor = None
            state.loiter_start_timestamp = None
            state.last_centroid = None
            state.last_timestamp = timestamp_seconds

        # --- Appearance analysis (real, from the pretrained embedding) ---
        embedding = self.extract_features(frame)
        if state.baseline is None:
            state.baseline = embedding.copy()
            appearance_score = 0.0
        else:
            distance = float(np.linalg.norm(embedding - state.baseline))
            appearance_score = 1.0 - np.exp(-6.0 * distance)  # saturating 0..1
            state.baseline = (1 - self.baseline_alpha) * state.baseline + self.baseline_alpha * embedding

        state.frame_count += 1

        anomaly_score = self.appearance_weight * appearance_score + self.motion_weight * motion_score
        anomaly_score = float(max(self.min_score, min(1.0, anomaly_score)))

        is_anomaly = anomaly_score > active_threshold
        confidence = abs(anomaly_score - active_threshold) * 1.5
        confidence = float(min(0.95, max(0.5, confidence)))

        return {
            "anomaly_score": anomaly_score,
            "is_anomaly": is_anomaly,
            "anomaly_confidence": confidence,
            "bounding_box": bounding_box,
            "motion_score": motion_score,
            "appearance_score": appearance_score,
            "contour_count": contour_count,
            "velocity_px_per_sec": velocity_px_per_sec,
            "loiter_duration_seconds": loiter_duration_seconds,
            "detected_objects": detected_objects,
            "object_counts": object_counts,
        }


def create_ml_anomaly_detector() -> MLAnomalyDetector:
    """Factory function to create and initialize the ML anomaly detector"""
    return MLAnomalyDetector()
