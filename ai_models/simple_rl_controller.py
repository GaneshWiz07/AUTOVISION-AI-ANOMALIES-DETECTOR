"""
Simple reinforcement learning controller for AutoVision
Uses basic RL techniques to optimize anomaly detection thresholds
"""

import numpy as np
import os
from typing import Dict, Any, List
from loguru import logger
import time


class SimpleRLController:
    """
    RL controller with Q-learning for AutoVision
    
    Uses Q-learning to optimize anomaly detection thresholds based on feedback
    """
    
    def __init__(self, supabase_client=None, user_id=None):
        """Initialize the RL controller"""
        # Store Supabase client for database persistence
        self.supabase_client = supabase_client
        self.user_id = user_id
        
        # Configuration
        self.initial_threshold = float(os.getenv("ANOMALY_THRESHOLD", "0.5"))
        self.learning_rate = float(os.getenv("RL_LEARNING_RATE", "0.01"))
        self.discount_factor = 0.95  # Gamma for Q-learning
        self.exploration_rate = 0.1  # Epsilon for epsilon-greedy
        
        # State management
        self.current_threshold = self.initial_threshold
        self.adjustment_count = 0
        
        # Q-table for threshold adjustment (simplified discrete actions)
        # Actions: 0=decrease threshold, 1=keep same, 2=increase threshold
        self.q_table = {}
        self.num_actions = 3
        
        # State representation (discretized)
        self.current_state = self._get_initial_state()
        
        # Performance tracking
        self.false_positives = 0
        self.false_negatives = 0
        self.true_positives = 0
        self.true_negatives = 0
        
        # Training statistics
        self.training_episodes = 0
        self.total_reward = 0.0
        self.data_saved_count = 0
        
        logger.info(f"RL controller initialized with Q-learning (DB: {supabase_client is not None}, User: {user_id})")
    
    def get_current_threshold(self) -> float:
        """Get the current anomaly detection threshold"""
        return self.current_threshold
    
    def _get_initial_state(self) -> tuple:
        """Get initial state representation"""
        return (self._discretize_threshold(self.current_threshold), 0, 0)
    
    def _discretize_threshold(self, threshold: float) -> int:
        """Discretize threshold into bins for state representation"""
        bins = [0.0, 0.3, 0.5, 0.7, 1.0]
        for i in range(len(bins) - 1):
            if bins[i] <= threshold < bins[i + 1]:
                return i
        return len(bins) - 2
    
    def _get_state(self) -> tuple:
        """Get current state representation"""
        threshold_bin = self._discretize_threshold(self.current_threshold)
        fp_bin = min(self.false_positives // 5, 5)  # Bin false positives
        fn_bin = min(self.false_negatives // 5, 5)  # Bin false negatives
        return (threshold_bin, fp_bin, fn_bin)
    
    def _get_q_value(self, state: tuple, action: int) -> float:
        """Get Q-value for state-action pair"""
        return self.q_table.get((state, action), 0.0)
    
    def _update_q_value(self, state: tuple, action: int, reward: float, next_state: tuple):
        """Update Q-value using Q-learning update rule"""
        current_q = self._get_q_value(state, action)
        max_next_q = max([self._get_q_value(next_state, a) for a in range(self.num_actions)])
        new_q = current_q + self.learning_rate * (reward + self.discount_factor * max_next_q - current_q)
        self.q_table[(state, action)] = new_q
    
    def _select_action(self, state: tuple) -> int:
        """Select action using epsilon-greedy policy"""
        if np.random.random() < self.exploration_rate:
            return np.random.randint(0, self.num_actions)  # Explore
        else:
            # Exploit: choose action with highest Q-value
            q_values = [self._get_q_value(state, a) for a in range(self.num_actions)]
            return int(np.argmax(q_values))
    
    def _apply_action(self, action: int):
        """Apply the selected action to adjust threshold"""
        if action == 0:  # Decrease threshold
            self.current_threshold = max(0.1, self.current_threshold - 0.05)
        elif action == 1:  # Keep same
            pass
        elif action == 2:  # Increase threshold
            self.current_threshold = min(0.9, self.current_threshold + 0.05)
    
    def _calculate_reward(self, feedback: Dict[str, Any]) -> float:
        """Calculate reward based on feedback"""
        reward = 0.0
        
        if feedback.get("false_positive", False):
            reward = -1.0  # Penalty for false positive
            self.false_positives += 1
        elif feedback.get("false_negative", False):
            reward = -1.5  # Larger penalty for false negative (missing real anomaly)
            self.false_negatives += 1
        elif feedback.get("true_positive", False):
            reward = 2.0  # Reward for correct detection
            self.true_positives += 1
        elif feedback.get("true_negative", False):
            reward = 0.5  # Small reward for correct normal classification
            self.true_negatives += 1
        else:
            # Use score-based reward if no explicit feedback
            score = feedback.get("score", 0.5)
            reward = (score - 0.5) * 0.5  # Small reward/penalty based on confidence
        
        return reward
    
    def adjust_threshold(self, feedback: Dict[str, Any]) -> float:
        """Adjust threshold using Q-learning based on feedback"""
        # Get current state
        current_state = self._get_state()
        
        # Calculate reward
        reward = self._calculate_reward(feedback)
        self.total_reward += reward
        
        # Select and apply action
        action = self._select_action(current_state)
        self._apply_action(action)
        
        # Get next state
        next_state = self._get_state()
        
        # Update Q-value
        self._update_q_value(current_state, action, reward, next_state)
        
        # Update state
        self.current_state = next_state
        self.adjustment_count += 1
        self.training_episodes += 1
        
        # Persist training data to database
        if self.supabase_client and self.user_id:
            try:
                import asyncio
                state_vector = list(current_state) + [self.current_threshold]
                next_state_vector = list(next_state) + [self.current_threshold]
                
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._save_training_data(
                        state_vector, action, reward, next_state_vector, False
                    ))
                else:
                    loop.run_until_complete(self._save_training_data(
                        state_vector, action, reward, next_state_vector, False
                    ))
                self.data_saved_count += 1
            except Exception as e:
                logger.error(f"Failed to save RL training data: {e}")
        
        # Log adjustment periodically
        if self.adjustment_count % 10 == 0:
            logger.info(f"RL threshold adjusted to {self.current_threshold:.3f} "
                       f"(FP: {self.false_positives}, FN: {self.false_negatives}, "
                       f"TP: {self.true_positives}, Reward: {self.total_reward:.2f})")
        
        return self.current_threshold
    
    async def _save_training_data(self, state_vector: List[float], action: int, 
                                   reward: float, next_state_vector: List[float], done: bool):
        """Save training data to Supabase"""
        try:
            await self.supabase_client.save_rl_training_data(
                user_id=self.user_id,
                state_vector=state_vector,
                action=action,
                reward=reward,
                next_state_vector=next_state_vector,
                done=done
            )
        except Exception as e:
            logger.error(f"Error saving RL training data to database: {e}")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        total_predictions = self.true_positives + self.true_negatives + self.false_positives + self.false_negatives
        accuracy = 0.0
        precision = 0.0
        recall = 0.0
        
        if total_predictions > 0:
            accuracy = (self.true_positives + self.true_negatives) / total_predictions
        
        if (self.true_positives + self.false_positives) > 0:
            precision = self.true_positives / (self.true_positives + self.false_positives)
        
        if (self.true_positives + self.false_negatives) > 0:
            recall = self.true_positives / (self.true_positives + self.false_negatives)
        
        f1_score = 0.0
        if (precision + recall) > 0:
            f1_score = 2 * (precision * recall) / (precision + recall)
        
        return {
            "current_threshold": self.current_threshold,
            "total_adjustments": self.adjustment_count,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "true_positives": self.true_positives,
            "true_negatives": self.true_negatives,
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score,
            "total_reward": self.total_reward,
            "avg_reward": self.total_reward / max(1, self.training_episodes),
            "q_table_size": len(self.q_table),
            "data_saved": self.data_saved_count
        }
    
    def reset(self):
        """Reset the controller to initial state"""
        self.current_threshold = self.initial_threshold
        self.false_positives = 0
        self.false_negatives = 0
        self.adjustment_count = 0
        logger.info("Simple RL controller reset to initial state")
    
    def get_training_summary(self) -> Dict[str, Any]:
        """Get training summary for system status"""
        metrics = self.get_performance_metrics()
        return {
            "model_type": "Q-Learning RL Controller",
            "algorithm": "Q-Learning with epsilon-greedy",
            "current_threshold": self.current_threshold,
            "total_adjustments": self.adjustment_count,
            "training_episodes": self.training_episodes,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "true_positives": self.true_positives,
            "accuracy": metrics["accuracy"],
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1_score": metrics["f1_score"],
            "total_reward": self.total_reward,
            "avg_reward_per_episode": metrics["avg_reward"],
            "q_table_size": len(self.q_table),
            "exploration_rate": self.exploration_rate,
            "learning_rate": self.learning_rate,
            "training_status": "active" if self.adjustment_count > 0 else "idle",
            "data_persisted": self.data_saved_count,
            "last_updated": int(time.time())
        }


def create_rl_controller(supabase_client=None, user_id=None):
    """Factory function to create and initialize the RL controller"""
    return SimpleRLController(supabase_client=supabase_client, user_id=user_id)
