"""Tests for confidence scoring system."""
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import pytest
from agent.confidence import (
    ConfidenceScorer, ConfidenceConfig, ConfidenceReport, ScoreFactors,
    BrowserConfidenceScorer, BrowserScoreFactors
)


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


class TestBrowserConfidenceScorer:
    """Test suite for browser automation confidence scoring."""
    
    @pytest.fixture
    def browser_config(self):
        """Create browser confidence configuration."""
        return ConfidenceConfig(
            task_id="browser-test-123",
            intervention_threshold=65.0,
            critical_threshold=35.0
        )
    
    @pytest.fixture
    def browser_factors(self):
        """Create test browser score factors."""
        return BrowserScoreFactors(
            # Core factors
            task_completion=0.7,
            error_rate=0.1,
            time_efficiency=0.8,
            output_quality=0.85,
            uncertainty_level=0.15,
            # Browser-specific factors
            page_load_success_rate=0.95,
            robots_txt_compliance=1.0,
            data_extraction_accuracy=0.9,
            crawl_depth_efficiency=0.8,
            rate_limit_adherence=1.0,
            structured_data_quality=0.85,
            browser_stability=0.95,
            network_resilience=0.9
        )
    
    def test_browser_scorer_initialization(self, browser_config):
        """Test browser confidence scorer initialization."""
        scorer = BrowserConfidenceScorer(browser_config)
        
        assert scorer.config == browser_config
        assert scorer.score_history == []
        assert scorer.current_score == 100.0
        assert "page_load_success" in scorer.config.weights
        assert "robots_compliance" in scorer.config.weights
        assert "extraction_accuracy" in scorer.config.weights
        
        # Check crawl stats initialization
        assert scorer.crawl_stats["total_pages_attempted"] == 0
        assert scorer.crawl_stats["pages_loaded_successfully"] == 0
        assert scorer.crawl_stats["robots_violations"] == 0
    
    def test_calculate_browser_score(self, browser_config, browser_factors):
        """Test browser-specific score calculation."""
        scorer = BrowserConfidenceScorer(browser_config)
        
        score = scorer.calculate_browser_score(browser_factors)
        
        # Should be high score with good factors
        assert 80 <= score <= 100
        
        # Test with poor browser factors
        poor_factors = BrowserScoreFactors(
            task_completion=0.7,
            error_rate=0.3,  # High error rate
            time_efficiency=0.8,
            output_quality=0.5,  # Poor quality
            uncertainty_level=0.4,  # High uncertainty
            page_load_success_rate=0.6,  # Poor page loading
            robots_txt_compliance=0.8,  # Some violations
            data_extraction_accuracy=0.5,  # Poor extraction
            crawl_depth_efficiency=0.6,
            rate_limit_adherence=0.7,  # Some violations
            structured_data_quality=0.5,
            browser_stability=0.8,
            network_resilience=0.7
        )
        
        poor_score = scorer.calculate_browser_score(poor_factors)
        assert poor_score < score  # Should be lower
        assert poor_score >= 0  # Should never be negative
    
    def test_update_browser_confidence(self, browser_config, browser_factors):
        """Test updating browser confidence with factors."""
        scorer = BrowserConfidenceScorer(browser_config)
        
        # Initial update
        scorer.update_browser_confidence(browser_factors)
        
        assert len(scorer.score_history) == 1
        assert scorer.score_history[0]["type"] == "browser_automation"
        assert scorer.last_updated is not None
        
        # Verify crawl stats were updated
        assert scorer.crawl_stats["extraction_attempts"] == 1
        if browser_factors.data_extraction_accuracy > 0.8:
            assert scorer.crawl_stats["successful_extractions"] == 1
    
    def test_browser_recommendations(self, browser_config):
        """Test browser-specific recommendations."""
        scorer = BrowserConfidenceScorer(browser_config)
        
        # Test with problematic factors
        problem_factors = BrowserScoreFactors(
            task_completion=0.5,
            error_rate=0.2,
            time_efficiency=0.7,
            output_quality=0.6,
            uncertainty_level=0.3,
            page_load_success_rate=0.7,  # Poor page loading
            robots_txt_compliance=0.8,   # Some violations
            data_extraction_accuracy=0.6,  # Poor extraction
            crawl_depth_efficiency=0.5,
            rate_limit_adherence=0.8,    # Some violations
            structured_data_quality=0.6,
            browser_stability=0.7,       # Poor stability
            network_resilience=0.7       # Poor resilience
        )
        
        scorer.update_browser_confidence(problem_factors)
        recommendations = scorer.get_browser_recommendations()
        
        assert len(recommendations) > 0
        assert any("page load" in rec.lower() for rec in recommendations)
        assert any("robots" in rec.lower() for rec in recommendations)
        assert any("extraction" in rec.lower() for rec in recommendations)
        assert any("browser" in rec.lower() for rec in recommendations)
    
    def test_crawl_risk_assessment(self, browser_config):
        """Test crawl risk assessment."""
        scorer = BrowserConfidenceScorer(browser_config)
        
        # Simulate some crawl activity with issues
        scorer.crawl_stats.update({
            "total_pages_attempted": 10,
            "pages_loaded_successfully": 6,  # 60% success rate
            "robots_violations": 2,
            "rate_limit_violations": 3,
            "browser_crashes": 1,
            "extraction_attempts": 8,
            "successful_extractions": 4  # 50% extraction success
        })
        
        risk_assessment = scorer.get_crawl_risk_assessment()
        
        assert risk_assessment["risk_level"] in ["low", "medium", "high"]
        assert len(risk_assessment["risks"]) > 0
        assert "crawl_stats" in risk_assessment
        assert risk_assessment["extraction_success_rate"] == 0.5
        assert "recommendations" in risk_assessment
    
    def test_estimate_extraction_confidence(self, browser_config):
        """Test extraction confidence estimation."""
        scorer = BrowserConfidenceScorer(browser_config)
        
        # Test with complete data
        extracted_data = {
            "title": "Product Name",
            "price": "$29.99",
            "description": "Product description",
            "rating": "4.5"
        }
        expected_fields = ["title", "price", "description", "rating"]
        
        confidence = scorer.estimate_extraction_confidence(
            extracted_data, expected_fields, "https://example.com/product"
        )
        
        assert 80 <= confidence <= 100  # Should be high with complete data
        
        # Test with incomplete data
        incomplete_data = {
            "title": "Product Name",
            "price": "",  # Empty field
            "description": "Product description"
            # Missing rating field
        }
        
        incomplete_confidence = scorer.estimate_extraction_confidence(
            incomplete_data, expected_fields, "https://example.com/product"
        )
        
        assert incomplete_confidence < confidence
        assert incomplete_confidence >= 0
    
    def test_create_browser_factors_from_stats(self, browser_config):
        """Test creating browser factors from crawl statistics."""
        scorer = BrowserConfidenceScorer(browser_config)
        
        # Set up some crawl statistics
        scorer.crawl_stats.update({
            "robots_violations": 1,
            "rate_limit_violations": 0,
            "browser_crashes": 0,
            "network_errors": 1
        })
        
        factors = scorer.create_browser_factors_from_stats(
            task_progress=0.6,
            current_errors=2,
            pages_processed=10,
            successful_pages=9,
            successful_extractions=8
        )
        
        assert isinstance(factors, BrowserScoreFactors)
        assert factors.task_completion == 0.6
        assert factors.page_load_success_rate == 0.9  # 9/10
        assert factors.data_extraction_accuracy == 0.8  # 8/10
        assert factors.error_rate == 0.2  # 2/10
        assert 0.0 <= factors.robots_txt_compliance <= 1.0
    
    def test_browser_momentum_effect(self, browser_config):
        """Test momentum effect in browser confidence scoring."""
        scorer = BrowserConfidenceScorer(browser_config)
        
        # Start with good factors
        good_factors = BrowserScoreFactors(
            task_completion=0.8,
            error_rate=0.05,
            time_efficiency=0.9,
            output_quality=0.95,
            uncertainty_level=0.1,
            page_load_success_rate=0.98,
            robots_txt_compliance=1.0,
            data_extraction_accuracy=0.95,
            crawl_depth_efficiency=0.9,
            rate_limit_adherence=1.0,
            structured_data_quality=0.9,
            browser_stability=0.98,
            network_resilience=0.95
        )
        
        scorer.update_browser_confidence(good_factors)
        first_score = scorer.current_score
        
        # Then update with poor factors
        poor_factors = BrowserScoreFactors(
            task_completion=0.3,
            error_rate=0.5,
            time_efficiency=0.4,
            output_quality=0.3,
            uncertainty_level=0.7,
            page_load_success_rate=0.5,
            robots_txt_compliance=0.6,
            data_extraction_accuracy=0.4,
            crawl_depth_efficiency=0.3,
            rate_limit_adherence=0.5,
            structured_data_quality=0.3,
            browser_stability=0.6,
            network_resilience=0.5
        )
        
        scorer.update_browser_confidence(poor_factors)
        second_score = scorer.current_score
        
        # Score should drop but not drastically due to momentum
        assert second_score < first_score
        assert second_score > scorer.calculate_browser_score(poor_factors)  # Momentum effect
    
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