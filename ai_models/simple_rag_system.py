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
            return self.retrieval_cache[feature_hash]
        
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
        return {
            "knowledge_base_size": sum(len(v) for v in self.knowledge_base.values()),
            "cache_size": len(self.retrieval_cache),
            "cache_hit_rate": 0.85  # Simulated value
        }
    
    def clear_cache(self):
        """Clear the retrieval cache"""
        self.retrieval_cache.clear()
        logger.info("RAG system cache cleared")
    
    def analyze_detection(self, description: str, anomaly_score: float, anomaly_type: str) -> Dict[str, Any]:
        """
        Analyze a detection using RAG (Retrieval-Augmented Generation)
        
        Args:
            description: Description of the detected event
            anomaly_score: Score from anomaly detector
            anomaly_type: Type of anomaly detected
            
        Returns:
            Dict containing analysis results
        """
        try:
            # Get relevant context from knowledge base
            context = self.get_relevant_context(description, anomaly_type)
            
            # Generate confidence adjustment based on context
            confidence_adjustment = 0.0
            
            # Check if this matches known anomaly patterns
            for pattern in self.knowledge_base.get("anomaly_patterns", []):
                if any(word in description.lower() for word in pattern.lower().split()):
                    confidence_adjustment += 0.1  # Increase confidence
                    
            # Check if this matches normal patterns (reduce confidence for anomalies)
            for pattern in self.knowledge_base.get("normal_patterns", []):
                if any(word in description.lower() for word in pattern.lower().split()):
                    if anomaly_score > 0.5:  # If flagged as anomaly but matches normal pattern
                        confidence_adjustment -= 0.2  # Reduce confidence
            
            # Normalize confidence to 0-1 range
            confidence = max(0.0, min(1.0, 0.5 + confidence_adjustment))
            
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
            
        explanation = f"Detected {anomaly_type} with {severity} severity (score: {anomaly_score:.3f}). "
        
        if context.get("relevant_patterns"):
            explanation += f"This pattern is similar to known {anomaly_type} events. "
            
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
            
        # Add type-specific recommendations
        if anomaly_type == "motion_anomaly":
            recommendations.append("Check for unauthorized access")
        elif anomaly_type == "object_anomaly":
            recommendations.append("Verify object identification")
            
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
    
    def get_relevant_context(self, description: str, anomaly_type: str) -> Dict[str, Any]:
        """
        Get relevant context from the knowledge base
        
        Args:
            description: Description of the detected event
            anomaly_type: Type of anomaly detected
            
        Returns:
            Context information from the knowledge base
        """
        context = {
            "relevant_patterns": [],
            "contextual_factors": [],
            "anomaly_type": anomaly_type
        }
        
        # Simple keyword matching for demo purposes
        if "crowd" in description or "gathering" in description:
            context["relevant_patterns"].append("Unusual crowd gathering")
        if "vehicle" in description and "restricted" in description:
            context["relevant_patterns"].append("Vehicle stopped in restricted area")
        if "person" in description and "restricted" in description:
            context["relevant_patterns"].append("Person in restricted zone")
        if "suspicious" in description or "object" in description:
            context["relevant_patterns"].append("Suspicious object left behind")
        
        # Add contextual factors based on time, location, etc.
        context["contextual_factors"].extend([
            "Time of day: evening",
            "Location: main entrance",
            "Weather: clear",
            "Light conditions: normal"
        ])
        
        return context


def create_rag_system():
    """Factory function to create and initialize the RAG system"""
    return SimpleRAGSystem()
