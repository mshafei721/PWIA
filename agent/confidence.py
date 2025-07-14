"""Confidence scoring system for agent performance assessment."""
import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ConfidenceConfig(BaseModel):
    """Configuration for confidence scoring."""
    task_id: str
    intervention_threshold: float = 70.0  # Below this, human intervention suggested
    critical_threshold: float = 40.0      # Below this, immediate intervention required
    weights: Dict[str, float] = Field(default_factory=lambda: {
        "task_completion": 0.3,     # Progress toward task completion
        "error_rate": 0.2,          # Frequency of errors encountered  
        "time_efficiency": 0.2,     # Time taken vs. estimated time
        "output_quality": 0.15,     # Quality of generated outputs
        "uncertainty_level": 0.15   # Agent's expressed uncertainty
    })
    trend_window_size: int = 5      # Number of recent scores for trend analysis


class ScoreFactors(BaseModel):
    """Factors contributing to confidence score."""
    task_completion: float = Field(ge=0.0, le=1.0)    # 0-1: % of task completed
    error_rate: float = Field(ge=0.0, le=1.0)         # 0-1: error frequency
    time_efficiency: float = Field(ge=0.0, le=2.0)    # 0-2: actual/estimated time
    output_quality: float = Field(ge=0.0, le=1.0)     # 0-1: quality assessment
    uncertainty_level: float = Field(ge=0.0, le=1.0)  # 0-1: agent uncertainty


class ConfidenceReport(BaseModel):
    """Comprehensive confidence assessment report."""
    task_id: str
    current_score: float
    trend: str  # "improving", "declining", "stable"
    needs_intervention: bool
    needs_critical_intervention: bool
    last_updated: datetime
    score_history: List[float]
    recommendations: List[str]
    risk_factors: List[str]
    confidence_level: str  # "high", "medium", "low", "critical"


class ConfidenceScorer:
    """Manages confidence scoring and intervention decisions."""
    
    def __init__(self, config: ConfidenceConfig):
        """Initialize the confidence scorer."""
        self.config = config
        self.current_score = 100.0  # Start with full confidence
        self.score_history: List[Dict[str, Any]] = []
        self.last_updated: Optional[datetime] = None
        self._calibration_data: List[Dict[str, Any]] = []
    
    def calculate_base_score(self, factors: ScoreFactors) -> float:
        """Calculate base confidence score from factors."""
        weights = self.config.weights
        
        # Calculate weighted score (0-100)
        score = (
            factors.task_completion * weights["task_completion"] +
            (1.0 - factors.error_rate) * weights["error_rate"] +  # Invert error rate
            min(factors.time_efficiency, 1.0) * weights["time_efficiency"] +  # Cap at 1.0
            factors.output_quality * weights["output_quality"] +
            (1.0 - factors.uncertainty_level) * weights["uncertainty_level"]  # Invert uncertainty
        ) * 100
        
        return max(0.0, min(100.0, score))  # Clamp to 0-100
    
    def update_confidence_score(self, factors: ScoreFactors):
        """Update confidence score with new factors."""
        new_score = self.calculate_base_score(factors)
        
        # Apply momentum - don't change too drastically
        if self.score_history:
            momentum_factor = 0.7  # 70% new score, 30% previous
            self.current_score = (new_score * momentum_factor + 
                                self.current_score * (1 - momentum_factor))
        else:
            self.current_score = new_score
        
        # Record in history
        self.score_history.append({
            "timestamp": datetime.now().isoformat(),
            "score": self.current_score,
            "factors": factors.model_dump()
        })
        
        self.last_updated = datetime.now()
        
        # Limit history size
        if len(self.score_history) > 100:
            self.score_history = self.score_history[-100:]
    
    def needs_intervention(self) -> bool:
        """Check if human intervention is recommended."""
        return self.current_score < self.config.intervention_threshold
    
    def needs_critical_intervention(self) -> bool:
        """Check if immediate intervention is required."""
        return self.current_score < self.config.critical_threshold
    
    def get_confidence_trend(self, window_size: Optional[int] = None) -> str:
        """Analyze confidence trend over recent scores."""
        window = window_size or self.config.trend_window_size
        
        if len(self.score_history) < 2:
            return "insufficient_data"
        
        # Get recent scores
        recent_scores = [entry["score"] for entry in self.score_history[-window:]]
        
        if len(recent_scores) < 2:
            return "stable"
        
        # Calculate trend
        first_half = recent_scores[:len(recent_scores)//2]
        second_half = recent_scores[len(recent_scores)//2:]
        
        first_avg = statistics.mean(first_half)
        second_avg = statistics.mean(second_half)
        
        change = second_avg - first_avg
        
        if abs(change) < 2.0:  # Less than 2% change
            return "stable"
        elif change > 0:
            return "improving"
        else:
            return "declining"
    
    def adjust_thresholds_for_complexity(self, complexity_factor: float):
        """Adjust intervention thresholds based on task complexity."""
        # Higher complexity -> lower thresholds (more sensitive)
        base_intervention = 70.0
        base_critical = 40.0
        
        # Complexity factor: 0.0 (simple) to 1.0 (very complex)
        adjustment = complexity_factor * 15.0  # Up to 15 point adjustment
        
        self.config.intervention_threshold = base_intervention - adjustment
        self.config.critical_threshold = base_critical - adjustment
        
        # Ensure thresholds stay reasonable
        self.config.intervention_threshold = max(50.0, self.config.intervention_threshold)
        self.config.critical_threshold = max(20.0, self.config.critical_threshold)
    
    def generate_report(self) -> ConfidenceReport:
        """Generate comprehensive confidence report."""
        trend = self.get_confidence_trend()
        needs_intervention = self.needs_intervention()
        needs_critical = self.needs_critical_intervention()
        
        # Determine confidence level
        if self.current_score >= 80:
            confidence_level = "high"
        elif self.current_score >= 60:
            confidence_level = "medium"
        elif self.current_score >= 40:
            confidence_level = "low"
        else:
            confidence_level = "critical"
        
        # Generate recommendations
        recommendations = self._generate_recommendations()
        risk_factors = self._identify_risk_factors()
        
        return ConfidenceReport(
            task_id=self.config.task_id,
            current_score=self.current_score,
            trend=trend,
            needs_intervention=needs_intervention,
            needs_critical_intervention=needs_critical,
            last_updated=self.last_updated or datetime.now(),
            score_history=[entry["score"] for entry in self.score_history[-10:]],
            recommendations=recommendations,
            risk_factors=risk_factors,
            confidence_level=confidence_level
        )
    
    def _generate_recommendations(self) -> List[str]:
        """Generate actionable recommendations based on current state."""
        recommendations = []
        
        if not self.score_history:
            return ["Insufficient data for recommendations"]
        
        latest = self.score_history[-1]
        factors = ScoreFactors(**latest["factors"])
        
        # Analyze each factor
        if factors.task_completion < 0.3:
            recommendations.append("Consider breaking down the task into smaller, more manageable subtasks")
        
        if factors.error_rate > 0.2:
            recommendations.append("Review error patterns and implement additional validation steps")
        
        if factors.time_efficiency < 0.6:
            recommendations.append("Optimize time allocation or extend task deadlines")
        
        if factors.output_quality < 0.7:
            recommendations.append("Implement quality checkpoints and review processes")
        
        if factors.uncertainty_level > 0.4:
            recommendations.append("Seek clarification on ambiguous requirements or provide additional context")
        
        # Trend-based recommendations
        trend = self.get_confidence_trend()
        if trend == "declining":
            recommendations.append("Consider pausing to reassess approach - confidence is declining")
        elif trend == "stable" and self.current_score < 60:
            recommendations.append("Current approach may not be effective - consider alternative strategies")
        
        return recommendations or ["Continue current approach - performance is satisfactory"]
    
    def _identify_risk_factors(self) -> List[str]:
        """Identify current risk factors affecting confidence."""
        risk_factors = []
        
        if not self.score_history:
            return risk_factors
        
        latest = self.score_history[-1]
        factors = ScoreFactors(**latest["factors"])
        
        if factors.error_rate > 0.3:
            risk_factors.append("High error rate may indicate systemic issues")
        
        if factors.time_efficiency < 0.4:
            risk_factors.append("Severe time inefficiency suggests scope or approach problems")
        
        if factors.uncertainty_level > 0.6:
            risk_factors.append("High uncertainty level indicates unclear requirements or approach")
        
        if self.get_confidence_trend() == "declining":
            risk_factors.append("Declining confidence trend suggests increasing problems")
        
        if len(self.score_history) > 5:
            recent_scores = [entry["score"] for entry in self.score_history[-5:]]
            if all(score < 50 for score in recent_scores):
                risk_factors.append("Consistently low confidence over multiple evaluations")
        
        return risk_factors
    
    def save_scores(self, file_path: Path):
        """Save confidence scores to file."""
        data = {
            "config": self.config.model_dump(),
            "current_score": self.current_score,
            "score_history": self.score_history,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None
        }
        
        file_path.write_text(json.dumps(data, indent=2))
    
    def load_scores(self, file_path: Path):
        """Load confidence scores from file."""
        if not file_path.exists():
            return
        
        data = json.loads(file_path.read_text())
        
        self.current_score = data.get("current_score", 100.0)
        self.score_history = data.get("score_history", [])
        
        if data.get("last_updated"):
            self.last_updated = datetime.fromisoformat(data["last_updated"])
    
    def add_calibration_data(self, predicted_confidence: float, actual_outcome: bool):
        """Add data for confidence calibration."""
        self._calibration_data.append({
            "timestamp": datetime.now().isoformat(),
            "predicted_confidence": predicted_confidence,
            "actual_outcome": actual_outcome
        })
    
    def get_calibration_accuracy(self) -> float:
        """Calculate calibration accuracy."""
        if len(self._calibration_data) < 10:
            return 0.0  # Need sufficient data
        
        correct_predictions = 0
        for data in self._calibration_data:
            predicted_success = data["predicted_confidence"] > 70.0
            actual_success = data["actual_outcome"]
            if predicted_success == actual_success:
                correct_predictions += 1
        
        return correct_predictions / len(self._calibration_data)
    
    def reset_scores(self):
        """Reset all scores and history."""
        self.current_score = 100.0
        self.score_history = []
        self.last_updated = None