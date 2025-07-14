"""Integration tests for agent components including the IntegrationLayer."""
import asyncio
import json
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import pytest

from agent.main import AgentState
from agent.llm_agent import LLMAgent, AgentConfig
from agent.planner import TaskPlanner, TaskConfig, PlanningContext
from agent.confidence import ConfidenceScorer, ConfidenceConfig, ScoreFactors
from agent.utils import setup_logging, get_logger, ErrorHandler

# Import IntegrationLayer components for comprehensive testing
from agent.integration import (
    IntegrationLayer, IntegrationConfig, TaskProgress, TaskResult,
    SessionCheckpoint, SessionRecoveryInfo, SessionHeartbeat
)
from agent.browser import BrowserManager, BrowserConfig, BrowserSession
from agent.crawler import WebCrawler, CrawlerConfig, URLQueueItem
from agent.scraper import DataScraper, ScraperConfig, ExtractionResult
from agent.memory import AgentMemory, CrawlState, VisitedURL, ExtractedData, AgentSession


@pytest.fixture
def temp_workspace(tmp_path):
    """Create temporary workspace for integration tests."""
    workspace = tmp_path / "integration_test_workspace"
    workspace.mkdir(parents=True)
    return workspace


@pytest.fixture
def integration_configs(temp_workspace):
    """Create configurations for all components."""
    task_id = "integration-test-task"
    
    configs = {
        "task": TaskConfig(
            task_id=task_id,
            description="Integration test task",
            workspace_dir=str(temp_workspace),
            auto_save=False  # Disable for testing
        ),
        "agent": AgentConfig(
            api_key="test-key",
            model="gpt-4-turbo-preview",
            system_prompt="Test agent for integration testing"
        ),
        "confidence": ConfidenceConfig(
            task_id=task_id,
            intervention_threshold=60.0,
            critical_threshold=30.0
        )
    }
    
    return configs


class TestAgentIntegration:
    """Integration tests for agent system."""
    
    @pytest.mark.asyncio
    async def test_complete_agent_workflow(self, integration_configs, temp_workspace):
        """Test complete workflow: planning -> execution -> confidence assessment."""
        
        # Setup logging
        setup_logging(log_dir=str(temp_workspace / "logs"))
        logger = get_logger("integration_test")
        
        # Initialize components
        planner = TaskPlanner(integration_configs["task"])
        confidence_scorer = ConfidenceScorer(integration_configs["confidence"])
        error_handler = ErrorHandler("integration_test")
        
        # Mock LLM agent
        with patch('agent.planner.LLMAgent') as mock_llm_class:
            mock_llm = Mock()
            mock_llm.send_message = AsyncMock(return_value="""
            1. Research the topic thoroughly
            2. Extract key information
            3. Analyze findings
            4. Generate summary report
            """)
            mock_llm_class.return_value = mock_llm
            
            # Step 1: Task Planning
            planning_context = PlanningContext(
                user_prompt="Research Python web frameworks",
                search_constraints=["performance", "ease of use"],
                output_format="markdown"
            )
            
            subtasks = await planner.decompose_task(planning_context)
            
            assert len(subtasks) == 4
            assert planner.calculate_overall_progress() == 0.0
            
            # Step 2: Simulate task execution with progress updates
            for i, subtask in enumerate(subtasks):
                # Simulate starting subtask
                planner.update_subtask_progress(subtask.id, 0.0, "in_progress")
                
                # Simulate gradual progress
                for progress in [25.0, 50.0, 75.0, 100.0]:
                    planner.update_subtask_progress(subtask.id, progress)
                    
                    # Update confidence based on progress
                    factors = ScoreFactors(
                        task_completion=progress / 100.0,
                        error_rate=0.05,  # Low error rate
                        time_efficiency=0.8,
                        output_quality=0.9,
                        uncertainty_level=0.1
                    )
                    confidence_scorer.update_confidence_score(factors)
                
                # Mark as completed
                planner.update_subtask_progress(subtask.id, 100.0, "completed")
            
            # Step 3: Verify final state
            assert planner.calculate_overall_progress() == 100.0
            assert confidence_scorer.current_score > 80.0  # Should be high confidence
            assert not confidence_scorer.needs_intervention()
            
            # Step 4: Generate reports
            confidence_report = confidence_scorer.generate_report()
            plan_json = planner.export_plan_json()
            
            assert confidence_report.confidence_level == "high"
            assert confidence_report.trend in ["improving", "stable"]
            
            plan_data = json.loads(plan_json)
            assert plan_data["overall_progress"] == 100.0
            assert len(plan_data["subtasks"]) == 4
    
    def test_error_handling_integration(self, integration_configs):
        """Test error handling across components."""
        error_handler = ErrorHandler("integration_test")
        
        # Test different error scenarios
        errors_to_test = [
            ConnectionError("Network connection failed"),
            FileNotFoundError("Config file missing"),
            ValueError("Invalid input data"),
            MemoryError("Out of memory")
        ]
        
        for error in errors_to_test:
            error_handler.handle_error(error, context={"component": "test"})
        
        # Verify error tracking
        assert error_handler.error_count == 4
        assert len(error_handler.error_history) == 4
        
        # Test recovery suggestions
        for error in errors_to_test:
            suggestions = error_handler.get_recovery_suggestions(error)
            assert len(suggestions) > 0
            assert all(isinstance(s, str) for s in suggestions)
    
    @pytest.mark.asyncio
    async def test_confidence_driven_replanning(self, integration_configs, temp_workspace):
        """Test replanning when confidence drops below threshold."""
        
        planner = TaskPlanner(integration_configs["task"])
        confidence_scorer = ConfidenceScorer(integration_configs["confidence"])
        
        # Mock LLM for replanning
        with patch('agent.planner.LLMAgent') as mock_llm_class:
            mock_llm = Mock()
            mock_llm.send_message = AsyncMock(return_value="Adjusted plan based on low confidence")
            mock_llm_class.return_value = mock_llm
            
            # Create initial plan
            planning_context = PlanningContext(
                user_prompt="Complex research task",
                output_format="markdown"
            )
            
            # Add mock response for initial planning
            mock_llm.send_message = AsyncMock(side_effect=[
                "1. Initial subtask\n2. Another subtask",  # Initial planning
                "Adjusted plan due to low confidence"       # Replanning
            ])
            
            await planner.decompose_task(planning_context)
            
            # Simulate low confidence scenario
            low_confidence_factors = ScoreFactors(
                task_completion=0.2,
                error_rate=0.4,
                time_efficiency=0.3,
                output_quality=0.4,
                uncertainty_level=0.7
            )
            
            confidence_scorer.update_confidence_score(low_confidence_factors)
            
            # Should trigger replanning
            assert confidence_scorer.needs_intervention()
            
            # Test replanning
            needs_replan = await planner.adjust_plan_dynamically(
                current_findings="Encountering many errors",
                confidence_score=confidence_scorer.current_score
            )
            
            assert needs_replan is True
            assert len(planner.planning_history) > 0
    
    def test_cli_integration_with_state_persistence(self, temp_workspace):
        """Test CLI integration with state file persistence."""
        from agent.main import save_state, load_state, get_state_file
        
        # Set custom state file path
        state_file = temp_workspace / "test_agent_state.json"
        
        with patch('agent.main.get_state_file', return_value=state_file):
            # Create and save initial state
            initial_state = AgentState(
                status="running",
                pid=12345,
                task_id="test-task",
                confidence_score=85.5
            )
            save_state(initial_state)
            
            # Verify file was created
            assert state_file.exists()
            
            # Load state and verify
            loaded_state = load_state()
            assert loaded_state.status == "running"
            assert loaded_state.pid == 12345
            assert loaded_state.task_id == "test-task"
            assert loaded_state.confidence_score == 85.5
    
    def test_workspace_organization(self, integration_configs, temp_workspace):
        """Test workspace organization and file management."""
        planner = TaskPlanner(integration_configs["task"])
        
        # Verify workspace structure
        workspace_path = Path(integration_configs["task"].workspace_dir)
        assert workspace_path.exists()
        assert (workspace_path / "logs").exists()
        assert (workspace_path / "outputs").exists()
        
        # Create subtasks and verify directories
        subtask1 = planner.create_subtask("Task 1", "First task")
        subtask2 = planner.create_subtask("Task 2", "Second task")
        
        planner.add_subtask(subtask1)
        planner.add_subtask(subtask2)
        
        # Get subtask workspaces
        subtask1_dir = planner.get_subtask_workspace(subtask1.id)
        subtask2_dir = planner.get_subtask_workspace(subtask2.id)
        
        assert subtask1_dir.exists()
        assert subtask2_dir.exists()
        assert subtask1_dir != subtask2_dir
        
        # Generate todo file
        todo_path = planner.generate_todo_file()
        assert todo_path.exists()
        
        # Verify todo file content
        content = todo_path.read_text()
        assert "Task 1" in content
        assert "Task 2" in content
        assert integration_configs["task"].task_id in content
    
    @pytest.mark.asyncio
    async def test_real_time_monitoring_simulation(self, integration_configs):
        """Test real-time monitoring and status updates."""
        confidence_scorer = ConfidenceScorer(integration_configs["confidence"])
        
        # Simulate real-time updates over time
        scenarios = [
            # Start with good performance
            ScoreFactors(task_completion=0.1, error_rate=0.0, time_efficiency=1.0, output_quality=1.0, uncertainty_level=0.0),
            ScoreFactors(task_completion=0.3, error_rate=0.05, time_efficiency=0.9, output_quality=0.95, uncertainty_level=0.1),
            ScoreFactors(task_completion=0.5, error_rate=0.1, time_efficiency=0.8, output_quality=0.9, uncertainty_level=0.15),
            
            # Encounter some issues
            ScoreFactors(task_completion=0.6, error_rate=0.2, time_efficiency=0.6, output_quality=0.8, uncertainty_level=0.3),
            ScoreFactors(task_completion=0.7, error_rate=0.25, time_efficiency=0.5, output_quality=0.7, uncertainty_level=0.4),
            
            # Recovery
            ScoreFactors(task_completion=0.8, error_rate=0.15, time_efficiency=0.7, output_quality=0.85, uncertainty_level=0.2),
            ScoreFactors(task_completion=1.0, error_rate=0.1, time_efficiency=0.8, output_quality=0.9, uncertainty_level=0.1),
        ]
        
        confidence_history = []
        
        for factors in scenarios:
            confidence_scorer.update_confidence_score(factors)
            confidence_history.append(confidence_scorer.current_score)
            
            # Generate report at each step
            report = confidence_scorer.generate_report()
            assert report.current_score > 0
            assert len(report.recommendations) > 0
        
        # Verify trend analysis
        trend = confidence_scorer.get_confidence_trend()
        assert trend in ["improving", "declining", "stable"]
        
        # Verify we have full history
        assert len(confidence_scorer.score_history) == len(scenarios)
    
    def test_component_isolation_and_mocking(self, integration_configs):
        """Test that components can work independently with mocked dependencies."""
        
        # Test planner in isolation
        planner = TaskPlanner(integration_configs["task"])
        
        subtask = planner.create_subtask("Isolated test", "Test description")
        planner.add_subtask(subtask)
        
        assert len(planner.subtasks) == 1
        assert planner.calculate_overall_progress() == 0.0
        
        # Test confidence scorer in isolation
        confidence_scorer = ConfidenceScorer(integration_configs["confidence"])
        
        factors = ScoreFactors(
            task_completion=0.8,
            error_rate=0.1,
            time_efficiency=0.9,
            output_quality=0.85,
            uncertainty_level=0.15
        )
        
        confidence_scorer.update_confidence_score(factors)
        assert confidence_scorer.current_score > 70.0
        
        # Verify components don't interfere with each other
        planner.update_subtask_progress(subtask.id, 50.0)
        assert planner.calculate_overall_progress() == 50.0
        assert confidence_scorer.current_score > 70.0  # Unchanged


# ===================== INTEGRATION LAYER COMPREHENSIVE TESTS =====================

class TestIntegrationLayerInitialization:
    """Test IntegrationLayer initialization and component setup."""
    
    @pytest.fixture
    def temp_memory_dir(self):
        """Create temporary directory for memory operations."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    async def mock_memory(self, temp_memory_dir):
        """Create mock AgentMemory."""
        memory = AgentMemory(str(temp_memory_dir))
        await memory.initialize()
        return memory
    
    @pytest.fixture
    def integration_config(self):
        """Create test integration configuration."""
        return IntegrationConfig(
            session_timeout=60,
            max_concurrent_pages=2,
            page_load_timeout=5000,
            extraction_timeout=3000,
            max_retry_attempts=2,
            batch_size=5,
            progress_report_interval=1,
            circuit_breaker_threshold=3,
            session_checkpoint_interval=10,
            enable_session_persistence=True
        )
    
    @pytest.mark.asyncio
    async def test_initialization_default_config(self, mock_memory):
        """Test IntegrationLayer initialization with default configuration."""
        integration = IntegrationLayer(memory=mock_memory)
        
        assert integration.memory == mock_memory
        assert isinstance(integration.config, IntegrationConfig)
        assert isinstance(integration.browser_manager, BrowserManager)
        assert isinstance(integration.crawler, WebCrawler)
        assert isinstance(integration.scraper, DataScraper)
        assert integration.active_sessions == {}
        assert integration.task_progress == {}
        assert integration.session_browsers == {}
        assert integration._session_persistence_dir.exists()
        
        await integration.close()
    
    @pytest.mark.asyncio
    async def test_initialization_custom_config(self, mock_memory, integration_config):
        """Test IntegrationLayer initialization with custom configuration."""
        browser_config = BrowserConfig(headless=True, browser_type="chromium")
        crawler_config = CrawlerConfig(max_concurrent_requests=2)
        scraper_config = ScraperConfig(enable_structured_data=False)
        
        integration = IntegrationLayer(
            browser_config=browser_config,
            crawler_config=crawler_config,
            scraper_config=scraper_config,
            integration_config=integration_config,
            memory=mock_memory
        )
        
        assert integration.config == integration_config
        assert integration.config.max_concurrent_pages == 2
        assert integration.config.session_timeout == 60
        assert integration.browser_manager.config == browser_config
        
        await integration.close()


class TestIntegrationLayerTaskExecution:
    """Test complete task execution workflow."""
    
    @pytest.fixture
    async def integration_with_mocks(self, temp_memory_dir):
        """Create IntegrationLayer with mocked components."""
        memory = AgentMemory(str(temp_memory_dir))
        await memory.initialize()
        
        config = IntegrationConfig(
            max_concurrent_pages=2,
            page_load_timeout=5000,
            extraction_timeout=3000,
            max_retry_attempts=2
        )
        
        integration = IntegrationLayer(
            integration_config=config,
            memory=memory
        )
        
        # Mock components
        integration.browser_manager = AsyncMock()
        integration.crawler = AsyncMock()
        integration.scraper = AsyncMock()
        
        # Mock browser session
        mock_browser_session = MagicMock()
        mock_browser_session.session_id = "test_browser_session"
        integration.browser_manager.create_context.return_value = mock_browser_session
        
        # Mock crawler session
        integration.crawler.start_crawling_session.return_value = "test_crawl_session"
        integration.crawler.get_next_url.side_effect = [
            URLQueueItem(url="https://example.com", priority=1, metadata={}),
            None  # End of queue
        ]
        integration.crawler.mark_url_completed.return_value = None
        
        # Mock scraper
        mock_extraction = ExtractionResult(
            url="https://example.com",
            timestamp=datetime.now(),
            data={"title": "Test Page", "content": "Test content"},
            extraction_type="basic",
            success=True,
            selectors_used=["h1", "p"],
            processing_time=0.5
        )
        integration.scraper.extract_data.return_value = mock_extraction
        
        yield integration
        await integration.close()
    
    @pytest.mark.asyncio
    async def test_execute_task_success(self, integration_with_mocks):
        """Test successful task execution."""
        integration = integration_with_mocks
        
        result = await integration.execute_task(
            task_id="test_task",
            initial_urls=["https://example.com"],
            extraction_rules={"selectors": ["h1", "p"]}
        )
        
        assert result.success is True
        assert result.task_id == "test_task"
        assert result.urls_processed == 1
        assert result.urls_successful == 1
        assert result.urls_failed == 0
        assert result.data_extracted == 1
        assert len(result.extraction_results) == 1
        
        # Verify component interactions
        integration.browser_manager.create_context.assert_called_once()
        integration.crawler.start_crawling_session.assert_called_once()
        integration.scraper.extract_data.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_task_with_failures(self, integration_with_mocks):
        """Test task execution with partial failures."""
        integration = integration_with_mocks
        
        # Setup crawler to return multiple URLs
        integration.crawler.get_next_url.side_effect = [
            URLQueueItem(url="https://example.com", priority=1, metadata={}),
            URLQueueItem(url="https://fail.com", priority=1, metadata={}),
            None
        ]
        
        # Make scraper fail for second URL
        def mock_extract_data(browser_session, url, rules):
            if url == "https://fail.com":
                raise Exception("Extraction failed")
            return ExtractionResult(
                url=url,
                timestamp=datetime.now(),
                data={"title": "Test Page"},
                extraction_type="basic",
                success=True,
                selectors_used=["h1"],
                processing_time=0.5
            )
        
        integration.scraper.extract_data.side_effect = mock_extract_data
        
        result = await integration.execute_task(
            task_id="test_task_failures",
            initial_urls=["https://example.com", "https://fail.com"]
        )
        
        assert result.success is True  # Task completes even with partial failures
        assert result.urls_processed == 2
        assert result.urls_successful == 1
        assert result.urls_failed == 1
        assert result.data_extracted == 1
        assert len(result.failed_urls) == 1
        assert result.failed_urls[0]["url"] == "https://fail.com"


class TestIntegrationLayerComponentCoordination:
    """Test coordination between browser, crawler, and scraper components."""
    
    @pytest.fixture
    async def integration_setup(self, temp_memory_dir):
        """Setup integration layer for coordination testing."""
        memory = AgentMemory(str(temp_memory_dir))
        await memory.initialize()
        
        config = IntegrationConfig(max_concurrent_pages=2)
        integration = IntegrationLayer(
            integration_config=config,
            memory=memory
        )
        
        # Mock components but keep coordination logic
        integration.browser_manager = AsyncMock()
        integration.crawler = AsyncMock()
        integration.scraper = AsyncMock()
        
        yield integration
        await integration.close()
    
    @pytest.mark.asyncio
    async def test_coordinate_components_success(self, integration_setup):
        """Test successful component coordination for single URL."""
        integration = integration_setup
        
        # Setup mocks
        mock_browser_session = MagicMock()
        mock_browser_session.session_id = "browser_123"
        
        mock_page = AsyncMock()
        mock_page.url = "https://example.com"
        integration.browser_manager.get_page.return_value = mock_page
        
        mock_extraction = ExtractionResult(
            url="https://example.com",
            timestamp=datetime.now(),
            data={"title": "Test"},
            extraction_type="basic",
            success=True,
            selectors_used=["h1"],
            processing_time=0.3
        )
        integration.scraper.extract_data.return_value = mock_extraction
        
        # Test coordination
        url_item = URLQueueItem(url="https://example.com", priority=1, metadata={})
        result = await integration.coordinate_components(
            browser_session=mock_browser_session,
            url_item=url_item,
            extraction_rules={"selectors": ["h1"]}
        )
        
        assert result.success is True
        assert result.url == "https://example.com"
        assert result.data == {"title": "Test"}
        
        # Verify component calls
        integration.browser_manager.get_page.assert_called_once()
        integration.scraper.extract_data.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_coordinate_components_navigation_failure(self, integration_setup):
        """Test coordination when navigation fails."""
        integration = integration_setup
        
        mock_browser_session = MagicMock()
        integration.browser_manager.get_page.side_effect = Exception("Navigation failed")
        
        url_item = URLQueueItem(url="https://fail.com", priority=1, metadata={})
        result = await integration.coordinate_components(
            browser_session=mock_browser_session,
            url_item=url_item,
            extraction_rules={}
        )
        
        assert result.success is False
        assert "Navigation failed" in result.error_message
        integration.scraper.extract_data.assert_not_called()


class TestIntegrationLayerErrorHandling:
    """Test error handling, circuit breaker, and retry mechanisms."""
    
    @pytest.fixture
    async def integration_for_errors(self, temp_memory_dir):
        """Setup integration layer for error testing."""
        memory = AgentMemory(str(temp_memory_dir))
        await memory.initialize()
        
        config = IntegrationConfig(
            circuit_breaker_threshold=2,
            circuit_breaker_timeout=1,
            max_retry_attempts=2,
            enable_adaptive_delays=True,
            max_adaptive_delay=5
        )
        
        integration = IntegrationLayer(
            integration_config=config,
            memory=memory
        )
        
        integration.browser_manager = AsyncMock()
        integration.crawler = AsyncMock()
        integration.scraper = AsyncMock()
        
        yield integration
        await integration.close()
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_activation(self, integration_for_errors):
        """Test circuit breaker activation after threshold failures."""
        integration = integration_for_errors
        domain = "fail.com"
        
        # Simulate failures to trigger circuit breaker
        for _ in range(3):
            integration._record_failure(domain)
        
        assert integration._is_circuit_breaker_open(domain) is True
        assert domain in integration._circuit_breaker_opened
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_reset(self, integration_for_errors):
        """Test circuit breaker reset after timeout."""
        integration = integration_for_errors
        domain = "example.com"
        
        # Trigger circuit breaker
        for _ in range(3):
            integration._record_failure(domain)
        
        assert integration._is_circuit_breaker_open(domain) is True
        
        # Manually set open time to past
        integration._circuit_breaker_opened[domain] = datetime.now() - timedelta(seconds=2)
        
        # Should be closed now
        assert integration._is_circuit_breaker_open(domain) is False
        
        # Record success should reset failure count
        integration._record_success(domain)
        assert integration._circuit_breaker_failures.get(domain, 0) == 0


class TestIntegrationLayerSessionManagement:
    """Test session management, persistence, and recovery."""
    
    @pytest.fixture
    async def integration_with_sessions(self, temp_memory_dir, tmp_path):
        """Setup integration layer for session testing."""
        memory = AgentMemory(str(temp_memory_dir))
        await memory.initialize()
        
        config = IntegrationConfig(
            enable_session_persistence=True,
            session_checkpoint_interval=1,
            session_heartbeat_interval=1,
            auto_session_cleanup_age=3600
        )
        
        integration = IntegrationLayer(
            integration_config=config,
            memory=memory
        )
        
        # Override session directory to use tmp_path
        integration._session_persistence_dir = tmp_path / "sessions"
        integration._session_persistence_dir.mkdir(exist_ok=True)
        
        yield integration
        await integration.close()
    
    @pytest.mark.asyncio
    async def test_create_session_checkpoint(self, integration_with_sessions):
        """Test creating session checkpoints."""
        integration = integration_with_sessions
        
        # Setup session data
        session_id = "test_session_123"
        task_id = "test_task_456"
        
        # Create checkpoint
        checkpoint = await integration.create_session_checkpoint(
            session_id=session_id,
            task_id=task_id,
            progress_data={"processed": 5, "remaining": 10},
            crawler_state={"current_depth": 2},
            active_urls=["https://example.com"]
        )
        
        assert checkpoint.session_id == session_id
        assert checkpoint.task_id == task_id
        assert checkpoint.progress_snapshot["processed"] == 5
        assert "https://example.com" in checkpoint.active_urls
        
        # Verify checkpoint saved to disk
        checkpoint_file = integration._session_persistence_dir / f"checkpoint_{session_id}.json"
        assert checkpoint_file.exists()
        
        # Verify checkpoint content
        with open(checkpoint_file) as f:
            saved_data = json.load(f)
        assert saved_data["session_id"] == session_id
        assert saved_data["task_id"] == task_id
    
    @pytest.mark.asyncio
    async def test_session_recovery_analysis(self, integration_with_sessions):
        """Test session recovery feasibility analysis."""
        integration = integration_with_sessions
        
        session_id = "recovery_test_123"
        
        # Create a checkpoint
        checkpoint = SessionCheckpoint(
            session_id=session_id,
            task_id="test_task",
            checkpoint_time=datetime.now() - timedelta(minutes=5),
            progress_snapshot={"processed": 10, "total": 50},
            crawler_state={},
            circuit_breaker_state={},
            adaptive_delays_state={},
            active_urls=["https://example.com"],
            completed_urls=["https://done.com"] * 10,
            failed_urls=[],
            extraction_results=["result1", "result2"]
        )
        
        # Save checkpoint to disk
        await integration._save_checkpoint_to_disk(checkpoint)
        
        # Create heartbeat
        heartbeat = SessionHeartbeat(
            session_id=session_id,
            timestamp=datetime.now() - timedelta(minutes=10),
            status="crashed",
            urls_processed=10,
            urls_remaining=40,
            memory_usage_mb=256.0,
            browser_pages_active=0,
            health_score=0.0
        )
        
        await integration._save_heartbeat_to_disk(heartbeat)
        
        # Analyze recovery
        recovery_info = await integration._analyze_session_recovery(session_id)
        
        assert recovery_info.session_id == session_id
        assert recovery_info.recovery_possible is True
        assert recovery_info.status == "recoverable"
        assert recovery_info.estimated_progress == 0.2  # 10/50
        assert recovery_info.urls_remaining == 40


class TestIntegrationLayerProgressTracking:
    """Test task progress tracking and reporting."""
    
    @pytest.fixture
    async def integration_with_progress(self, temp_memory_dir):
        """Setup integration layer for progress testing."""
        memory = AgentMemory(str(temp_memory_dir))
        await memory.initialize()
        
        config = IntegrationConfig(progress_report_interval=0.1)  # Fast reporting
        integration = IntegrationLayer(
            integration_config=config,
            memory=memory
        )
        
        yield integration
        await integration.close()
    
    @pytest.mark.asyncio
    async def test_task_progress_tracking(self, integration_with_progress):
        """Test task progress tracking and updates."""
        integration = integration_with_progress
        
        task_id = "progress_test"
        initial_progress = TaskProgress(
            task_id=task_id,
            session_id="session_123",
            start_time=datetime.now(),
            urls_queued=10,
            status="running"
        )
        
        integration.task_progress[task_id] = initial_progress
        
        # Get initial progress
        progress = integration.get_task_progress(task_id)
        assert progress.task_id == task_id
        assert progress.urls_queued == 10
        assert progress.urls_processed == 0
        assert progress.completion_percentage == 0.0
        
        # Update progress
        progress.urls_processed = 5
        progress.urls_successful = 4
        progress.urls_failed = 1
        progress.data_extracted = 4
        
        updated_progress = integration.get_task_progress(task_id)
        assert updated_progress.urls_processed == 5
        assert updated_progress.completion_percentage == 50.0  # 5/10
    
    @pytest.mark.asyncio
    async def test_task_pause_resume(self, integration_with_progress):
        """Test task pause and resume functionality."""
        integration = integration_with_progress
        
        task_id = "pause_test"
        progress = TaskProgress(
            task_id=task_id,
            session_id="session_123",
            start_time=datetime.now(),
            status="running"
        )
        integration.task_progress[task_id] = progress
        
        # Pause task
        result = await integration.pause_task(task_id)
        assert result is True
        assert integration.task_progress[task_id].status == "paused"
        
        # Resume task
        result = await integration.resume_task(task_id)
        assert result is True
        assert integration.task_progress[task_id].status == "running"


class TestIntegrationLayerConcurrency:
    """Test concurrent processing and performance features."""
    
    @pytest.fixture
    async def integration_concurrent(self, temp_memory_dir):
        """Setup integration layer for concurrency testing."""
        memory = AgentMemory(str(temp_memory_dir))
        await memory.initialize()
        
        config = IntegrationConfig(
            max_concurrent_pages=2,
            max_memory_usage_mb=100  # Low limit for testing
        )
        integration = IntegrationLayer(
            integration_config=config,
            memory=memory
        )
        
        yield integration
        await integration.close()
    
    @pytest.mark.asyncio
    async def test_concurrent_processing_semaphore(self, integration_concurrent):
        """Test that concurrent processing respects semaphore limits."""
        integration = integration_concurrent
        
        # Verify semaphore is created with correct limit
        assert integration._processing_semaphore._value == 2
        
        # Test semaphore acquisition
        acquired = []
        
        async def acquire_semaphore(i):
            async with integration._processing_semaphore:
                acquired.append(i)
                await asyncio.sleep(0.1)
                acquired.append(f"done_{i}")
        
        # Try to acquire more than the limit
        tasks = [acquire_semaphore(i) for i in range(4)]
        await asyncio.gather(*tasks)
        
        # Verify order respects concurrency limit
        assert len(acquired) == 8  # 4 acquisitions + 4 completions
        
        # First two should start before any complete
        assert acquired[0] in [0, 1]
        assert acquired[1] in [0, 1]
    
    @pytest.mark.asyncio
    async def test_memory_usage_monitoring(self, integration_concurrent):
        """Test memory usage monitoring."""
        integration = integration_concurrent
        
        # Test memory check
        memory_mb = integration._get_memory_usage_mb()
        assert isinstance(memory_mb, float)
        assert memory_mb > 0
        
        # Test memory threshold check
        is_over_limit = integration._is_memory_over_limit()
        assert isinstance(is_over_limit, bool)
    
    @pytest.mark.asyncio
    async def test_health_score_calculation(self, integration_concurrent):
        """Test session health score calculation."""
        integration = integration_concurrent
        
        # Test health score with good metrics
        score = integration._calculate_session_health(
            success_rate=0.9,
            memory_usage_mb=50.0,
            active_pages=1,
            processing_rate=2.0
        )
        assert 0.8 <= score <= 1.0  # Should be high
        
        # Test health score with poor metrics
        score = integration._calculate_session_health(
            success_rate=0.3,
            memory_usage_mb=150.0,  # Over limit
            active_pages=5,  # Over limit
            processing_rate=0.1  # Very slow
        )
        assert 0.0 <= score <= 0.3  # Should be low


class TestIntegrationLayerEdgeCases:
    """Test edge cases and error scenarios."""
    
    @pytest.mark.asyncio
    async def test_integration_close_cleanup(self, temp_memory_dir):
        """Test proper cleanup when integration layer is closed."""
        memory = AgentMemory(str(temp_memory_dir))
        await memory.initialize()
        
        integration = IntegrationLayer(memory=memory)
        
        # Start some background tasks
        integration._progress_task = asyncio.create_task(asyncio.sleep(10))
        integration._health_check_task = asyncio.create_task(asyncio.sleep(10))
        integration._checkpoint_task = asyncio.create_task(asyncio.sleep(10))
        integration._heartbeat_task = asyncio.create_task(asyncio.sleep(10))
        
        # Close integration
        await integration.close()
        
        # Verify tasks are cancelled
        assert integration._progress_task.cancelled()
        assert integration._health_check_task.cancelled()
        assert integration._checkpoint_task.cancelled()
        assert integration._heartbeat_task.cancelled()
        
        # Verify shutdown event is set
        assert integration._shutdown_event.is_set()
    
    @pytest.mark.asyncio
    async def test_session_heartbeat_update(self, temp_memory_dir):
        """Test session heartbeat updates."""
        memory = AgentMemory(str(temp_memory_dir))
        await memory.initialize()
        
        integration = IntegrationLayer(memory=memory)
        
        session_id = "heartbeat_test"
        
        # Update heartbeat
        await integration._update_session_heartbeat(
            session_id=session_id,
            status="running",
            urls_processed=10,
            urls_remaining=5,
            current_url="https://example.com"
        )
        
        # Verify heartbeat created
        assert session_id in integration._session_heartbeats
        heartbeat = integration._session_heartbeats[session_id]
        
        assert heartbeat.session_id == session_id
        assert heartbeat.status == "running"
        assert heartbeat.urls_processed == 10
        assert heartbeat.urls_remaining == 5
        assert heartbeat.current_url == "https://example.com"
        assert 0.0 <= heartbeat.health_score <= 1.0
        
        await integration.close()


# Fixture for all IntegrationLayer tests that need memory
@pytest.fixture
def temp_memory_dir():
    """Create temporary directory for memory operations."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)