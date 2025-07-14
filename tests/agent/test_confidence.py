"""Tests for confidence scoring system."""
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import pytest
from agent.confidence import ConfidenceScorer, ConfidenceConfig, ConfidenceReport, ScoreFactors


@pytest.fixture
def confidence_config():
    """Create test confidence configuration."""
    return ConfidenceConfig(
        task_id="test-task-123",
        intervention_threshold=60.0,
        critical_threshold=30.0,
        weights={
            "task_completion": 0.3,
            "error_rate": 0.2,
            "time_efficiency": 0.2,
            "output_quality": 0.15,
            "uncertainty_level": 0.15
        }
    )


@pytest.fixture
def score_factors():
    """Create test score factors."""
    return ScoreFactors(
        task_completion=0.75,  # 75% complete
        error_rate=0.1,        # 10% error rate
        time_efficiency=0.8,   # 80% efficient
        output_quality=0.9,    # 90% quality
        uncertainty_level=0.2  # 20% uncertain
    )


class TestConfidenceScorer:
    """Test suite for confidence scoring system."""
    
    def test_scorer_initialization(self, confidence_config):
        """Test confidence scorer initialization."""
        scorer = ConfidenceScorer(confidence_config)
        
        assert scorer.config == confidence_config
        assert scorer.score_history == []
        assert scorer.current_score == 100.0  # Starts with full confidence
        assert scorer.last_updated is None
    
    def test_calculate_base_score(self, confidence_config, score_factors):
        """Test base confidence score calculation."""
        scorer = ConfidenceScorer(confidence_config)
        
        score = scorer.calculate_base_score(score_factors)
        
        # Calculate expected score based on weights
        expected = (
            0.75 * 0.3 +      # task_completion
            (1-0.1) * 0.2 +   # error_rate (inverted)
            0.8 * 0.2 +       # time_efficiency  
            0.9 * 0.15 +      # output_quality
            (1-0.2) * 0.15    # uncertainty_level (inverted)
        ) * 100
        
        assert abs(score - expected) < 0.1  # Allow small floating point differences
    
    def test_update_confidence_score(self, confidence_config):
        """Test updating confidence score with new factors."""
        scorer = ConfidenceScorer(confidence_config)
        
        factors = ScoreFactors(
            task_completion=0.5,
            error_rate=0.05,
            time_efficiency=0.9,
            output_quality=0.8,
            uncertainty_level=0.1
        )
        
        old_score = scorer.current_score
        scorer.update_confidence_score(factors)
        
        assert scorer.current_score != old_score
        assert len(scorer.score_history) == 1
        assert scorer.last_updated is not None
    
    def test_intervention_threshold_detection(self, confidence_config):
        """Test detection of intervention thresholds."""
        scorer = ConfidenceScorer(confidence_config)
        
        # High confidence - no intervention needed
        high_factors = ScoreFactors(
            task_completion=0.9,
            error_rate=0.0,
            time_efficiency=0.95,
            output_quality=0.95,
            uncertainty_level=0.05
        )
        
        scorer.update_confidence_score(high_factors)
        assert not scorer.needs_intervention()
        assert not scorer.needs_critical_intervention()
        
        # Medium confidence - needs intervention (use fresh scorer to avoid momentum)
        medium_scorer = ConfidenceScorer(confidence_config)
        medium_factors = ScoreFactors(
            task_completion=0.3,
            error_rate=0.2,
            time_efficiency=0.5,
            output_quality=0.6,
            uncertainty_level=0.4
        )
        
        medium_scorer.update_confidence_score(medium_factors)
        assert medium_scorer.needs_intervention()
        assert not medium_scorer.needs_critical_intervention()
        
        # Low confidence - needs critical intervention (use fresh scorer)
        low_scorer = ConfidenceScorer(confidence_config)
        low_factors = ScoreFactors(
            task_completion=0.1,
            error_rate=0.5,
            time_efficiency=0.2,
            output_quality=0.3,
            uncertainty_level=0.8
        )
        
        low_scorer.update_confidence_score(low_factors)
        assert low_scorer.needs_intervention()
        assert low_scorer.needs_critical_intervention()
    
    def test_confidence_trend_analysis(self, confidence_config):
        """Test confidence trend analysis over time."""
        scorer = ConfidenceScorer(confidence_config)
        
        # Simulate declining confidence
        scores = [90.0, 80.0, 70.0, 60.0, 50.0]
        for score in scores:
            factors = ScoreFactors(
                task_completion=score/100,
                error_rate=0.1,
                time_efficiency=0.8,
                output_quality=0.8,
                uncertainty_level=0.2
            )
            scorer.update_confidence_score(factors)
        
        trend = scorer.get_confidence_trend()
        assert trend == "declining"
        
        # Add improving scores
        improving_scores = [55.0, 65.0, 75.0]
        for score in improving_scores:
            factors = ScoreFactors(
                task_completion=score/100,
                error_rate=0.05,
                time_efficiency=0.85,
                output_quality=0.9,
                uncertainty_level=0.1
            )
            scorer.update_confidence_score(factors)
        
        trend = scorer.get_confidence_trend(window_size=3)
        assert trend == "improving"
    
    def test_error_rate_impact(self, confidence_config):
        """Test how error rate affects confidence."""
        scorer = ConfidenceScorer(confidence_config)
        
        # High error rate should lower confidence
        high_error_factors = ScoreFactors(
            task_completion=0.8,
            error_rate=0.5,  # 50% error rate
            time_efficiency=0.8,
            output_quality=0.8,
            uncertainty_level=0.2
        )
        
        scorer.update_confidence_score(high_error_factors)
        high_error_score = scorer.current_score
        
        # Low error rate should maintain higher confidence
        low_error_factors = ScoreFactors(
            task_completion=0.8,
            error_rate=0.05,  # 5% error rate
            time_efficiency=0.8,
            output_quality=0.8,
            uncertainty_level=0.2
        )
        
        scorer.update_confidence_score(low_error_factors)
        low_error_score = scorer.current_score
        
        assert low_error_score > high_error_score
    
    def test_time_efficiency_scoring(self, confidence_config):
        """Test time efficiency impact on confidence."""
        scorer = ConfidenceScorer(confidence_config)
        
        # Test efficient vs inefficient execution
        efficient_factors = ScoreFactors(
            task_completion=0.7,
            error_rate=0.1,
            time_efficiency=0.95,  # Very efficient
            output_quality=0.8,
            uncertainty_level=0.2
        )
        
        scorer.update_confidence_score(efficient_factors)
        efficient_score = scorer.current_score
        
        inefficient_factors = ScoreFactors(
            task_completion=0.7,
            error_rate=0.1,
            time_efficiency=0.3,  # Very inefficient
            output_quality=0.8,
            uncertainty_level=0.2
        )
        
        scorer.update_confidence_score(inefficient_factors)
        inefficient_score = scorer.current_score
        
        assert efficient_score > inefficient_score
    
    def test_generate_confidence_report(self, confidence_config):
        """Test generating confidence report."""
        scorer = ConfidenceScorer(confidence_config)
        
        # Update with some factors
        factors = ScoreFactors(
            task_completion=0.6,
            error_rate=0.15,
            time_efficiency=0.7,
            output_quality=0.8,
            uncertainty_level=0.3
        )
        
        scorer.update_confidence_score(factors)
        
        report = scorer.generate_report()
        
        assert isinstance(report, ConfidenceReport)
        assert report.task_id == "test-task-123"
        assert 0 <= report.current_score <= 100
        assert report.needs_intervention == scorer.needs_intervention()
        assert report.trend is not None
        assert len(report.recommendations) > 0
    
    def test_adaptive_threshold_adjustment(self, confidence_config):
        """Test adaptive threshold adjustment based on task complexity."""
        scorer = ConfidenceScorer(confidence_config)
        
        # High complexity task should have lower thresholds
        scorer.adjust_thresholds_for_complexity(complexity_factor=0.9)
        
        high_complexity_threshold = scorer.config.intervention_threshold
        
        # Low complexity task should have higher thresholds
        scorer.adjust_thresholds_for_complexity(complexity_factor=0.3)
        
        low_complexity_threshold = scorer.config.intervention_threshold
        
        assert high_complexity_threshold < low_complexity_threshold
    
    def test_score_persistence(self, confidence_config, tmp_path):
        """Test saving and loading confidence scores."""
        scorer = ConfidenceScorer(confidence_config)
        
        # Add some score history
        factors1 = ScoreFactors(task_completion=0.8, error_rate=0.1, 
                               time_efficiency=0.9, output_quality=0.85, 
                               uncertainty_level=0.15)
        factors2 = ScoreFactors(task_completion=0.6, error_rate=0.2,
                               time_efficiency=0.7, output_quality=0.75,
                               uncertainty_level=0.3)
        
        scorer.update_confidence_score(factors1)
        scorer.update_confidence_score(factors2)
        
        # Save to file
        save_path = tmp_path / "confidence_scores.json"
        scorer.save_scores(save_path)
        
        # Create new scorer and load
        new_scorer = ConfidenceScorer(confidence_config)
        new_scorer.load_scores(save_path)
        
        assert new_scorer.current_score == scorer.current_score
        assert len(new_scorer.score_history) == len(scorer.score_history)
    
    def test_real_time_scoring(self, confidence_config):
        """Test real-time confidence scoring during task execution."""
        scorer = ConfidenceScorer(confidence_config)
        
        # Simulate real-time updates
        initial_factors = ScoreFactors(
            task_completion=0.0,
            error_rate=0.0,
            time_efficiency=1.0,
            output_quality=1.0,
            uncertainty_level=0.0
        )
        
        scorer.update_confidence_score(initial_factors)
        initial_score = scorer.current_score
        
        # Simulate progress with some challenges
        progress_factors = ScoreFactors(
            task_completion=0.3,
            error_rate=0.1,
            time_efficiency=0.8,
            output_quality=0.9,
            uncertainty_level=0.2
        )
        
        scorer.update_confidence_score(progress_factors)
        progress_score = scorer.current_score
        
        # Score should reflect the mixed progress
        assert progress_score < initial_score  # Some challenges
        assert progress_score > 50.0  # But still reasonable progress
    
    def test_confidence_calibration(self, confidence_config):
        """Test confidence score calibration against actual outcomes."""
        scorer = ConfidenceScorer(confidence_config)
        
        # Test calibration with known outcomes
        test_cases = [
            (ScoreFactors(task_completion=0.9, error_rate=0.05, time_efficiency=0.95, 
                         output_quality=0.9, uncertainty_level=0.1), True),   # High confidence, success
            (ScoreFactors(task_completion=0.3, error_rate=0.4, time_efficiency=0.4, 
                         output_quality=0.5, uncertainty_level=0.6), False),    # Low confidence, failure
            (ScoreFactors(task_completion=0.7, error_rate=0.15, time_efficiency=0.8, 
                         output_quality=0.8, uncertainty_level=0.2), True),    # Medium confidence, success
        ]
        
        predictions = []
        actual_outcomes = []
        
        for factors, outcome in test_cases:
            scorer.update_confidence_score(factors)
            predictions.append(scorer.current_score > 70.0)  # Predict success if >70%
            actual_outcomes.append(outcome)
        
        # Calculate accuracy
        correct_predictions = sum(p == a for p, a in zip(predictions, actual_outcomes))
        accuracy = correct_predictions / len(test_cases)
        
        assert accuracy >= 0.5  # Should be better than random