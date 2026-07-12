"""
Simple RAG (Retrieval-Augmented Generation) system for AutoVision
Uses basic techniques for contextual anomaly analysis
"""

import numpy as np
from typing import Dict, Any, List, Optional
from loguru import logger
import time
import json


class SimpleRAGSystem:
    """
    Simple RAG system implementation for AutoVision
    
    Uses basic retrieval and generation techniques to provide context for anomaly detection
    """
    
    def __init__(self):
        """Initialize the RAG system"""
        # Knowledge base (simplified for demo)
        self.knowledge_base = {
            "normal_patterns": [
                "Regular pedestrian movement",
                "Normal vehicle traffic",
                "Standard lighting conditions",
                "Typical weather patterns"
            ],
            "anomaly_patterns": [
                "Unusual crowd gathering",
                "Vehicle stopped in restricted area",
                "Person in restricted zone",
                "Suspicious object left behind",
                "Irregular lighting changes",
                "Weather-related visibility issues"
            ],
            "context_rules": [
                "Higher threshold during busy hours",
                "Lower threshold in restricted areas",
                "Adjust for weather conditions",
                "Consider time of day patterns"
            ]
        }
        
        # Simple retrieval cache
        self.retrieval_cache = {}
        self.cache_max_size = 100
        self.cache_hits = 0
        self.cache_misses = 0

        logger.info("Simple RAG system initialized")

    def retrieve_context(self, features: np.ndarray, anomaly_score: float) -> Dict[str, Any]:
        """
        Retrieve relevant context for anomaly analysis

        Args:
            features: Feature vector from the frame
            anomaly_score: Current anomaly score

        Returns:
            Context information for analysis
        """
        # Simple feature-based retrieval (demo)
        feature_hash = hash(features.tobytes()) % 1000

        # Check cache first
        if feature_hash in self.retrieval_cache:
            self.cache_hits += 1
            return self.retrieval_cache[feature_hash]
        self.cache_misses += 1

        # Generate context based on anomaly score
        if anomaly_score > 0.7:
            relevant_patterns = self.knowledge_base["anomaly_patterns"]
            context_type = "high_anomaly"
        elif anomaly_score > 0.4:
            relevant_patterns = self.knowledge_base["anomaly_patterns"][:2] + self.knowledge_base["normal_patterns"][:2]
            context_type = "medium_anomaly"
        else:
            relevant_patterns = self.knowledge_base["normal_patterns"]
            context_type = "normal"
        
        context = {
            "type": context_type,
            "relevant_patterns": relevant_patterns,
            "confidence": min(0.9, 0.5 + anomaly_score * 0.4),
            "recommendations": self._generate_recommendations(anomaly_score)
        }
        
        # Cache the result
        if len(self.retrieval_cache) >= self.cache_max_size:
            # Remove oldest entry
            oldest_key = next(iter(self.retrieval_cache))
            del self.retrieval_cache[oldest_key]
        
        self.retrieval_cache[feature_hash] = context
        return context
    
    def _generate_recommendations(self, anomaly_score: float) -> List[str]:
        """Generate recommendations based on anomaly score"""
        recommendations = []
        
        if anomaly_score > 0.8:
            recommendations.extend([
                "Immediate attention required",
                "Consider alerting security personnel",
                "Review related camera feeds"
            ])
        elif anomaly_score > 0.6:
            recommendations.extend([
                "Monitor situation closely",
                "Check for pattern continuation",
                "Review historical data"
            ])
        elif anomaly_score > 0.4:
            recommendations.extend([
                "Continue monitoring",
                "Log for pattern analysis"
            ])
        else:
            recommendations.append("Normal operation")
        
        return recommendations
    
    def generate_summary(self, context: Dict[str, Any], anomaly_info: Dict[str, Any]) -> str:
        """
        Generate a human-readable summary of the anomaly analysis
        
        Args:
            context: Context from retrieve_context
            anomaly_info: Anomaly detection results
            
        Returns:
            Human-readable summary
        """
        anomaly_score = anomaly_info.get("anomaly_score", 0.0)
        is_anomaly = anomaly_info.get("is_anomaly", False)
        confidence = anomaly_info.get("anomaly_confidence", 0.0)
        
        if is_anomaly:
            severity = "high" if anomaly_score > 0.7 else "medium" if anomaly_score > 0.5 else "low"
            summary = f"Anomaly detected with {severity} severity (score: {anomaly_score:.3f}, confidence: {confidence:.3f}). "
        else:
            summary = f"Normal activity detected (score: {anomaly_score:.3f}). "
        
        # Add context information
        if context.get("relevant_patterns"):
            patterns = ", ".join(context["relevant_patterns"][:2])
            summary += f"Similar to: {patterns}. "
        
        # Add recommendations
        if context.get("recommendations"):
            rec = context["recommendations"][0]
            summary += f"Recommendation: {rec}"
        
        return summary
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get system statistics"""
        total_lookups = self.cache_hits + self.cache_misses
        return {
            "knowledge_base_size": sum(len(v) for v in self.knowledge_base.values()),
            "cache_size": len(self.retrieval_cache),
            "cache_hit_rate": (self.cache_hits / total_lookups) if total_lookups > 0 else 0.0
        }

    def get_pattern_stats(self) -> Dict[str, Any]:
        """Get a per-pattern-type breakdown of the knowledge base"""
        return {
            "pattern_types": {
                pattern_type: len(entries)
                for pattern_type, entries in self.knowledge_base.items()
            },
            "total_patterns": sum(len(v) for v in self.knowledge_base.values()),
            "cache_size": len(self.retrieval_cache),
        }

    def generate_pattern_summary(self, pattern_type: Optional[str] = None) -> Dict[str, Any]:
        """Summarize known patterns, optionally filtered to a single pattern_type"""
        if pattern_type:
            entries = self.knowledge_base.get(pattern_type, [])
            return {
                "pattern_type": pattern_type,
                "count": len(entries),
                "examples": entries[-10:],
            }

        return {
            "pattern_type": None,
            "summary": {
                pattern_type: {"count": len(entries), "examples": entries[-5:]}
                for pattern_type, entries in self.knowledge_base.items()
            },
        }

    def clear_cache(self):
        """Clear the retrieval cache"""
        self.retrieval_cache.clear()
        logger.info("RAG system cache cleared")
    
    def analyze_detection(self, description: str, anomaly_score: float, anomaly_type: str,
                           signals: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyze a detection using RAG (Retrieval-Augmented Generation)

        Args:
            description: Description of the detected event
            anomaly_score: Score from anomaly detector
            anomaly_type: Type of anomaly detected (already derived by the
                caller from real measured signals - see
                backend/video_processor.py's _classify_anomaly_type)
            signals: the real measurements behind that classification
                (contour_count, velocity_px_per_sec, loiter_duration_seconds,
                motion_score, appearance_score). Used to ground confidence
                and context in actual numbers instead of keyword-matching
                the description string (which would be circular - that
                string was generated from anomaly_type in the first place).

        Returns:
            Dict containing analysis results
        """
        try:
            signals = signals or {}
            context = self.get_relevant_context(anomaly_type, signals)

            # Confidence scales with how strongly the real signal that drove
            # this classification exceeded a "just barely" reading, not with
            # keyword overlap against a self-generated description.
            if anomaly_type == "crowd_gathering":
                crowd_count = signals.get("person_count", 0) or signals.get("contour_count", 0)
                confidence = min(0.95, 0.5 + 0.1 * crowd_count)
            elif anomaly_type == "running":
                confidence = min(0.95, 0.5 + signals.get("velocity_px_per_sec", 0.0) / 500.0)
            elif anomaly_type == "loitering":
                confidence = min(0.95, 0.5 + signals.get("loiter_duration_seconds", 0.0) / 60.0)
            elif anomaly_type.endswith("_detected"):
                # This label came from a real object-detector confidence
                # score in the first place - use it directly.
                confidence = min(0.95, max(0.5, signals.get("top_object_confidence", 0.5)))
            else:
                confidence = min(0.95, max(0.05, anomaly_score))

            # Generate explanation
            explanation = self._generate_explanation(description, anomaly_score, anomaly_type, context)

            # Generate recommendations
            recommendations = self._generate_recommendations(anomaly_score, anomaly_type)
            
            result = {
                "confidence": confidence,
                "explanation": explanation,
                "recommendations": recommendations,
                "context": context,
                "analysis_type": "rag_enhanced"
            }
            
            logger.debug(f"RAG analysis completed for {anomaly_type}: confidence={confidence:.3f}")
            return result
            
        except Exception as e:
            logger.error(f"Error in RAG analysis: {e}")
            # Return default values on error
            return {
                "confidence": 0.5,
                "explanation": "Basic anomaly detection without context analysis",
                "recommendations": ["Review detection manually"],
                "context": {},
                "analysis_type": "fallback"
            }
    
    def _generate_explanation(self, description: str, anomaly_score: float,
                            anomaly_type: str, context: Dict[str, Any]) -> str:
        """Generate explanation for the detection"""
        if anomaly_score > 0.7:
            severity = "high"
        elif anomaly_score > 0.4:
            severity = "moderate"
        else:
            severity = "low"

        readable_type = (
            anomaly_type[: -len("_detected")].replace("_", " ")
            if anomaly_type.endswith("_detected") else anomaly_type.replace("_", " ")
        )
        explanation = f"Detected {readable_type} with {severity} severity (score: {anomaly_score:.3f}). "

        if context.get("relevant_patterns") and not anomaly_type.endswith("_detected"):
            explanation += f"This pattern is similar to known {readable_type} events. "

        if anomaly_score > 0.6:
            explanation += "Requires immediate attention."
        elif anomaly_score > 0.3:
            explanation += "Monitor for further development."
        else:
            explanation += "Likely normal activity."
            
        return explanation
    
    def _generate_recommendations(self, anomaly_score: float, anomaly_type: str) -> List[str]:
        """Generate recommendations based on the detection"""
        recommendations = []
        
        if anomaly_score > 0.8:
            recommendations.extend([
                "Alert security personnel immediately",
                "Review live video feed",
                "Consider activating emergency protocols"
            ])
        elif anomaly_score > 0.5:
            recommendations.extend([
                "Monitor situation closely",
                "Review historical data for patterns",
                "Consider manual verification"
            ])
        else:
            recommendations.extend([
                "Log for statistical analysis",
                "Continue normal monitoring"
            ])
            
        # Add type-specific recommendations (matches the real taxonomy
        # produced by backend/video_processor.py's _classify_anomaly_type)
        if anomaly_type == "crowd_gathering":
            recommendations.append("Check for overcrowding or a gathering forming")
        elif anomaly_type == "running":
            recommendations.append("Check whether the subject is fleeing or in distress")
        elif anomaly_type == "loitering":
            recommendations.append("Check whether the subject is authorized to be in this area")
        elif anomaly_type.endswith("_detected"):
            label = anomaly_type[: -len("_detected")].replace("_", " ")
            recommendations.append(f"Verify the recognized {label} and whether it belongs in this area")

        return recommendations[:3]  # Limit to 3 recommendations
    
    def add_pattern(self, pattern_type: str, description: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Add a new pattern to the knowledge base
        
        Args:
            pattern_type: Type of pattern (e.g., anomaly type)
            description: Description of the pattern
            metadata: Additional metadata about the pattern
        """
        try:
            # For this simple implementation, we just log the pattern
            # In a production system, this would add to a vector database
            logger.debug(f"Adding pattern to RAG system: {pattern_type} - {description}")
            
            # Add to our simple knowledge base
            if pattern_type not in self.knowledge_base:
                self.knowledge_base[pattern_type] = []
            
            # Avoid duplicates
            if description not in self.knowledge_base[pattern_type]:
                self.knowledge_base[pattern_type].append(description)
                
            # Keep knowledge base size manageable
            if len(self.knowledge_base[pattern_type]) > 20:
                self.knowledge_base[pattern_type] = self.knowledge_base[pattern_type][-20:]
                
            # Create a simple embedding (in production, use proper embeddings)
            embedding = [hash(description) % 1000 / 1000.0 for _ in range(5)]
            
            # Cache the pattern for quick retrieval
            cache_key = f"{pattern_type}_{hash(description)}"
            self.retrieval_cache[cache_key] = {
                "description": description,
                "pattern_type": pattern_type,
                "metadata": metadata or {},
                "embedding": embedding,
                "frequency": 1
            }
            
            # Manage cache size
            if len(self.retrieval_cache) > self.cache_max_size:
                # Remove oldest entries
                oldest_key = next(iter(self.retrieval_cache))
                del self.retrieval_cache[oldest_key]
                
        except Exception as e:
            logger.error(f"Error adding pattern to RAG system: {e}")
    
    def get_relevant_context(self, anomaly_type: str, signals: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get relevant context for a detection, grounded in the real measured
        signals that produced anomaly_type (contour_count, velocity,
        loiter_duration - see backend/video_processor.py's
        _classify_anomaly_type). Previously this matched keywords against a
        description string that was itself generated from anomaly_type,
        which only ever confirmed the label already knew - it never
        touched the actual frame data.

        Args:
            anomaly_type: Type of anomaly detected
            signals: real measurements behind that classification

        Returns:
            Context information for analysis
        """
        signals = signals or {}
        context = {
            "relevant_patterns": [],
            "contextual_factors": [],
            "anomaly_type": anomaly_type
        }

        if anomaly_type == "crowd_gathering":
            person_count = signals.get("person_count", 0)
            if person_count:
                context["relevant_patterns"].append("Unusual crowd gathering")
                context["contextual_factors"].append(f"{person_count} people detected in frame")
            else:
                context["relevant_patterns"].append("Unusual crowd gathering")
                context["contextual_factors"].append(
                    f"{signals.get('contour_count', 0)} distinct moving regions detected in frame"
                )
        elif anomaly_type == "running":
            context["relevant_patterns"].append("Fast-moving subject")
            context["contextual_factors"].append(
                f"Measured displacement speed ~{signals.get('velocity_px_per_sec', 0.0):.0f} px/sec"
            )
        elif anomaly_type == "loitering":
            context["relevant_patterns"].append("Extended dwell time in one area")
            context["contextual_factors"].append(
                f"Subject remained in the same area for ~{signals.get('loiter_duration_seconds', 0.0):.0f}s"
            )
        elif anomaly_type.endswith("_detected"):
            label = anomaly_type[: -len("_detected")].replace("_", " ")
            context["relevant_patterns"].append(f"Recognized object: {label}")
            context["contextual_factors"].append(
                f"Object detector confidence ~{signals.get('top_object_confidence', 0.0):.2f}"
            )
            object_counts = signals.get("object_counts") or {}
            if len(object_counts) > 1:
                others = ", ".join(f"{c} {l}" for l, c in object_counts.items() if l != label)
                if others:
                    context["contextual_factors"].append(f"Also visible: {others}")
        elif anomaly_type == "motion_anomaly":
            context["relevant_patterns"].append("Unclassified motion or appearance deviation")
            context["contextual_factors"].append(
                f"motion_score={signals.get('motion_score', 0.0):.2f}, "
                f"appearance_score={signals.get('appearance_score', 0.0):.2f}"
            )

        return context


def create_rag_system():
    """Factory function to create and initialize the RAG system"""
    return SimpleRAGSystem()
