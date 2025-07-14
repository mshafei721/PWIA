"""Confidence scoring system for agent performance assessment."""
import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
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


class BrowserScoreFactors(BaseModel):
    """Browser automation specific confidence factors."""
    # Core factors (inherited from ScoreFactors)
    task_completion: float = Field(ge=0.0, le=1.0)
    error_rate: float = Field(ge=0.0, le=1.0)
    time_efficiency: float = Field(ge=0.0, le=2.0)
    output_quality: float = Field(ge=0.0, le=1.0)
    uncertainty_level: float = Field(ge=0.0, le=1.0)
    
    # Browser-specific factors
    page_load_success_rate: float = Field(ge=0.0, le=1.0)    # % of pages loaded successfully
    robots_txt_compliance: float = Field(ge=0.0, le=1.0)     # % compliance with robots.txt
    data_extraction_accuracy: float = Field(ge=0.0, le=1.0)  # % of expected data extracted
    crawl_depth_efficiency: float = Field(ge=0.0, le=1.0)    # efficiency vs planned depth
    rate_limit_adherence: float = Field(ge=0.0, le=1.0)      # adherence to rate limits
    structured_data_quality: float = Field(ge=0.0, le=1.0)   # quality of extracted structured data
    browser_stability: float = Field(ge=0.0, le=1.0)         # browser crash/error frequency
    network_resilience: float = Field(ge=0.0, le=1.0)        # handling of network issues


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


class BrowserConfidenceScorer(ConfidenceScorer):
    """Browser automation specific confidence scorer."""
    
    def __init__(self, config: ConfidenceConfig):
        """Initialize browser confidence scorer with enhanced weights."""
        # Adjust weights for browser automation
        browser_weights = {
            "task_completion": 0.25,           # Core task progress
            "error_rate": 0.15,               # General errors
            "time_efficiency": 0.15,          # Time management
            "output_quality": 0.15,           # General output quality
            "uncertainty_level": 0.10,        # Agent uncertainty
            "page_load_success": 0.05,        # Browser-specific: page loading
            "robots_compliance": 0.05,        # Browser-specific: robots.txt
            "extraction_accuracy": 0.10       # Browser-specific: data extraction
        }
        
        config.weights = browser_weights
        super().__init__(config)
        
        # Browser-specific tracking
        self.crawl_stats = {
            "total_pages_attempted": 0,
            "pages_loaded_successfully": 0,
            "robots_violations": 0,
            "extraction_attempts": 0,
            "successful_extractions": 0,
            "browser_crashes": 0,
            "network_errors": 0,
            "rate_limit_violations": 0
        }
    
    def calculate_browser_score(self, factors: BrowserScoreFactors) -> float:
        """Calculate confidence score with browser-specific factors."""
        weights = self.config.weights
        
        # Core score calculation
        core_score = (
            factors.task_completion * weights["task_completion"] +
            (1.0 - factors.error_rate) * weights["error_rate"] +
            min(factors.time_efficiency, 1.0) * weights["time_efficiency"] +
            factors.output_quality * weights["output_quality"] +
            (1.0 - factors.uncertainty_level) * weights["uncertainty_level"]
        )
        
        # Browser-specific score components
        browser_score = (
            factors.page_load_success_rate * weights.get("page_load_success", 0.05) +
            factors.robots_txt_compliance * weights.get("robots_compliance", 0.05) +
            factors.data_extraction_accuracy * weights.get("extraction_accuracy", 0.10)
        )
        
        total_score = (core_score + browser_score) * 100
        return max(0.0, min(100.0, total_score))
    
    def update_browser_confidence(self, factors: BrowserScoreFactors):
        """Update confidence score with browser-specific factors."""
        new_score = self.calculate_browser_score(factors)
        
        # Apply momentum
        if self.score_history:
            momentum_factor = 0.7
            self.current_score = (new_score * momentum_factor + 
                                self.current_score * (1 - momentum_factor))
        else:
            self.current_score = new_score
        
        # Record in history with browser factors
        self.score_history.append({
            "timestamp": datetime.now().isoformat(),
            "score": self.current_score,
            "factors": factors.model_dump(),
            "type": "browser_automation"
        })
        
        self.last_updated = datetime.now()
        
        # Update crawl stats
        self._update_crawl_statistics(factors)
        
        # Limit history size
        if len(self.score_history) > 100:
            self.score_history = self.score_history[-100:]
    
    def _update_crawl_statistics(self, factors: BrowserScoreFactors):
        """Update internal crawl statistics for trending analysis."""
        # This would be called with real-time data during crawling
        # For now, we estimate based on factors
        
        if hasattr(factors, 'pages_processed'):
            # If we have real metrics, use them
            self.crawl_stats["total_pages_attempted"] += getattr(factors, 'pages_processed', 1)
            self.crawl_stats["pages_loaded_successfully"] += int(
                getattr(factors, 'pages_processed', 1) * factors.page_load_success_rate
            )
        
        # Track extraction performance
        self.crawl_stats["extraction_attempts"] += 1
        if factors.data_extraction_accuracy > 0.8:
            self.crawl_stats["successful_extractions"] += 1
        
        # Track compliance issues
        if factors.robots_txt_compliance < 1.0:
            self.crawl_stats["robots_violations"] += 1
        
        if factors.rate_limit_adherence < 1.0:
            self.crawl_stats["rate_limit_violations"] += 1
        
        if factors.browser_stability < 0.9:
            self.crawl_stats["browser_crashes"] += 1
        
        if factors.network_resilience < 0.9:
            self.crawl_stats["network_errors"] += 1
    
    def get_browser_recommendations(self) -> List[str]:
        """Get browser automation specific recommendations."""
        recommendations = []
        
        if not self.score_history:
            return ["Initialize browser automation monitoring"]
        
        latest = self.score_history[-1]
        if latest.get("type") != "browser_automation":
            return ["No browser automation data available"]
        
        factors = BrowserScoreFactors(**latest["factors"])
        
        # Page loading issues
        if factors.page_load_success_rate < 0.8:
            recommendations.append("Check network connectivity and increase page load timeouts")
        
        # Robots.txt compliance issues
        if factors.robots_txt_compliance < 0.9:
            recommendations.append("Review and improve robots.txt compliance - respect crawl delays")
        
        # Data extraction problems
        if factors.data_extraction_accuracy < 0.7:
            recommendations.append("Review CSS selectors and XPath expressions for data extraction")
        
        # Rate limiting issues
        if factors.rate_limit_adherence < 0.9:
            recommendations.append("Implement more conservative rate limiting to avoid being blocked")
        
        # Browser stability issues
        if factors.browser_stability < 0.8:
            recommendations.append("Consider restarting browser sessions more frequently")
        
        # Network resilience issues
        if factors.network_resilience < 0.8:
            recommendations.append("Implement better retry logic and network error handling")
        
        # Crawl efficiency issues
        if factors.crawl_depth_efficiency < 0.6:
            recommendations.append("Optimize crawl strategy - consider reducing depth or improving link filtering")
        
        # Data quality issues
        if factors.structured_data_quality < 0.7:
            recommendations.append("Improve structured data parsing and validation logic")
        
        return recommendations or ["Browser automation performance is satisfactory"]
    
    def get_crawl_risk_assessment(self) -> Dict[str, Any]:
        """Get browser automation specific risk assessment."""
        risks = []
        risk_level = "low"
        
        stats = self.crawl_stats
        
        # Calculate risk metrics
        if stats["total_pages_attempted"] > 0:
            success_rate = stats["pages_loaded_successfully"] / stats["total_pages_attempted"]
            if success_rate < 0.7:
                risks.append("Low page load success rate may indicate blocking or network issues")
                risk_level = "high"
            elif success_rate < 0.9:
                risks.append("Moderate page load issues detected")
                risk_level = "medium"
        
        if stats["robots_violations"] > 0:
            risks.append(f"{stats['robots_violations']} robots.txt violations detected")
            risk_level = "medium"
        
        if stats["rate_limit_violations"] > 2:
            risks.append("Multiple rate limit violations - risk of IP blocking")
            risk_level = "high"
        
        if stats["browser_crashes"] > 1:
            risks.append("Browser instability detected - consider session management improvements")
            risk_level = "medium"
        
        extraction_rate = 0.0
        if stats["extraction_attempts"] > 0:
            extraction_rate = stats["successful_extractions"] / stats["extraction_attempts"]
            if extraction_rate < 0.6:
                risks.append("Low data extraction success rate")
                risk_level = "high"
        
        return {
            "risk_level": risk_level,
            "risks": risks,
            "crawl_stats": stats,
            "extraction_success_rate": extraction_rate,
            "recommendations": self.get_browser_recommendations()
        }
    
    def estimate_extraction_confidence(self, 
                                     extracted_data: Dict[str, Any],
                                     expected_fields: List[str],
                                     page_url: str) -> float:
        """Estimate confidence for a specific data extraction."""
        if not extracted_data or not expected_fields:
            return 0.0
        
        # Calculate field coverage
        extracted_fields = set(extracted_data.keys())
        expected_fields_set = set(expected_fields)
        
        coverage = len(extracted_fields & expected_fields_set) / len(expected_fields_set)
        
        # Calculate data quality
        non_empty_fields = sum(1 for value in extracted_data.values() 
                             if value and str(value).strip())
        data_quality = non_empty_fields / len(extracted_data) if extracted_data else 0.0
        
        # Calculate overall confidence
        confidence = (coverage * 0.6 + data_quality * 0.4) * 100
        
        return max(0.0, min(100.0, confidence))
    
    def create_browser_factors_from_stats(self, 
                                        task_progress: float = 0.0,
                                        current_errors: int = 0,
                                        pages_processed: int = 0,
                                        successful_pages: int = 0,
                                        successful_extractions: int = 0) -> BrowserScoreFactors:
        """Create BrowserScoreFactors from current crawl statistics."""
        
        # Calculate rates
        page_success_rate = successful_pages / pages_processed if pages_processed > 0 else 1.0
        extraction_rate = successful_extractions / pages_processed if pages_processed > 0 else 1.0
        error_rate = current_errors / max(pages_processed, 1)
        
        # Estimate other factors based on available data
        robots_compliance = 1.0 - (self.crawl_stats["robots_violations"] / max(pages_processed, 1))
        rate_adherence = 1.0 - (self.crawl_stats["rate_limit_violations"] / max(pages_processed, 1))
        browser_stability = 1.0 - (self.crawl_stats["browser_crashes"] / max(pages_processed, 1))
        network_resilience = 1.0 - (self.crawl_stats["network_errors"] / max(pages_processed, 1))
        
        return BrowserScoreFactors(
            task_completion=task_progress,
            error_rate=min(1.0, error_rate),
            time_efficiency=1.0,  # Would need timing data
            output_quality=extraction_rate,
            uncertainty_level=0.1,  # Low uncertainty for automated tasks
            page_load_success_rate=page_success_rate,
            robots_txt_compliance=max(0.0, robots_compliance),
            data_extraction_accuracy=extraction_rate,
            crawl_depth_efficiency=1.0,  # Would need depth analysis
            rate_limit_adherence=max(0.0, rate_adherence),
            structured_data_quality=extraction_rate,  # Simplified
            browser_stability=max(0.0, browser_stability),
            network_resilience=max(0.0, network_resilience)
        )