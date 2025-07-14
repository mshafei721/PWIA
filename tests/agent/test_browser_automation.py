"""Tests for browser automation orchestration functionality."""
import pytest
import asyncio
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile
import json

from agent.browser_automation import (
    BrowserAutomation, AutomationConfig, WorkflowState, PerformanceMetrics
)
from agent.integration import IntegrationLayer, TaskProgress, TaskResult
from agent.memory import AgentMemory
from backend.websocket_manager import ConnectionManager
from backend.models import TaskMessage, ProgressUpdate


class TestBrowserAutomationInitialization:
    """Test BrowserAutomation initialization and configuration."""
    
    @pytest.mark.asyncio
    async def test_initialization_with_defaults(self):
        """Test BrowserAutomation initializes with default configuration."""
        automation = BrowserAutomation()
        
        assert automation.config is not None
        assert isinstance(automation.config, AutomationConfig)
        assert automation.memory is not None
        assert automation.integration is not None
        assert automation.websocket_manager is None
        assert len(automation.active_workflows) == 0
        assert len(automation.workflow_tasks) == 0
        assert len(automation.performance_metrics) == 0
    
    @pytest.mark.asyncio
    async def test_initialization_with_custom_config(self):
        """Test BrowserAutomation initializes with custom configuration."""
        config = AutomationConfig(
            enable_websocket_updates=False,
            auto_start_crawling=False,
            export_format="csv"
        )
        memory = AgentMemory()
        websocket_manager = MagicMock()
        
        automation = BrowserAutomation(
            config=config,
            memory=memory,
            websocket_manager=websocket_manager
        )
        
        assert automation.config == config
        assert automation.memory == memory
        assert automation.websocket_manager == websocket_manager
        assert not automation.config.enable_websocket_updates
        assert not automation.config.auto_start_crawling
        assert automation.config.export_format == "csv"
    
    @pytest.mark.asyncio
    async def test_export_directory_creation(self):
        """Test export directory is created during initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            export_dir = Path(temp_dir) / "test_exports"
            config = AutomationConfig(export_directory=export_dir)
            
            automation = BrowserAutomation(config=config)
            
            assert export_dir.exists()
            assert export_dir.is_dir()


class TestBrowserAutomationWorkflowManagement:
    """Test workflow lifecycle management."""
    
    @pytest.fixture
    async def mock_automation(self):
        """Create BrowserAutomation with mocked dependencies."""
        config = AutomationConfig(enable_websocket_updates=False, enable_performance_monitoring=False)
        memory = AsyncMock()
        websocket_manager = AsyncMock()
        
        automation = BrowserAutomation(config=config, memory=memory, websocket_manager=websocket_manager)
        automation.integration = AsyncMock()
        
        return automation
    
    @pytest.mark.asyncio
    async def test_start_session_success(self, mock_automation):
        """Test successful session start."""
        task_id = "test_task_123"
        initial_urls = ["https://example.com", "https://test.com"]
        
        workflow_id = await mock_automation.start_session(
            task_id=task_id,
            initial_urls=initial_urls
        )
        
        assert workflow_id in mock_automation.active_workflows
        workflow_state = mock_automation.active_workflows[workflow_id]
        assert workflow_state.task_id == task_id
        assert workflow_state.status == "initializing"
        assert workflow_id in mock_automation.workflow_tasks
    
    @pytest.mark.asyncio
    async def test_start_session_with_extraction_rules(self, mock_automation):
        """Test session start with extraction rules and config."""
        task_id = "test_task_456"
        initial_urls = ["https://example.com"]
        extraction_rules = {"selector": "h1", "attribute": "text"}
        task_config = {"timeout": 30}
        
        workflow_id = await mock_automation.start_session(
            task_id=task_id,
            initial_urls=initial_urls,
            extraction_rules=extraction_rules,
            task_config=task_config
        )
        
        assert workflow_id in mock_automation.active_workflows
        workflow_state = mock_automation.active_workflows[workflow_id]
        assert workflow_state.task_id == task_id
    
    @pytest.mark.asyncio
    async def test_pause_workflow_success(self, mock_automation):
        """Test successful workflow pause."""
        # Setup workflow
        workflow_id = str(uuid.uuid4())
        task_id = "test_task"
        workflow_state = WorkflowState(
            workflow_id=workflow_id,
            task_id=task_id,
            status="running"
        )
        mock_automation.active_workflows[workflow_id] = workflow_state
        mock_automation.integration.task_progress[task_id] = TaskProgress(
            task_id=task_id,
            session_id="session_123",
            start_time=datetime.now()
        )
        mock_automation.integration.pause_task = AsyncMock()
        
        await mock_automation.pause_workflow(workflow_id)
        
        assert workflow_state.status == "paused"
        mock_automation.integration.pause_task.assert_called_once_with(task_id)
    
    @pytest.mark.asyncio
    async def test_pause_workflow_not_found(self, mock_automation):
        """Test pause workflow with invalid workflow ID."""
        with pytest.raises(ValueError, match="Workflow invalid_id not found"):
            await mock_automation.pause_workflow("invalid_id")
    
    @pytest.mark.asyncio
    async def test_resume_workflow_success(self, mock_automation):
        """Test successful workflow resume."""
        # Setup paused workflow
        workflow_id = str(uuid.uuid4())
        task_id = "test_task"
        workflow_state = WorkflowState(
            workflow_id=workflow_id,
            task_id=task_id,
            status="paused"
        )
        mock_automation.active_workflows[workflow_id] = workflow_state
        mock_automation.integration.task_progress[task_id] = TaskProgress(
            task_id=task_id,
            session_id="session_123",
            start_time=datetime.now()
        )
        mock_automation.integration.resume_task = AsyncMock()
        
        await mock_automation.resume_workflow(workflow_id)
        
        assert workflow_state.status == "running"
        mock_automation.integration.resume_task.assert_called_once_with(task_id)
    
    @pytest.mark.asyncio
    async def test_resume_workflow_not_paused(self, mock_automation):
        """Test resume workflow that is not paused."""
        workflow_id = str(uuid.uuid4())
        workflow_state = WorkflowState(
            workflow_id=workflow_id,
            task_id="test_task",
            status="running"
        )
        mock_automation.active_workflows[workflow_id] = workflow_state
        
        with pytest.raises(RuntimeError, match="is not paused"):
            await mock_automation.resume_workflow(workflow_id)
    
    @pytest.mark.asyncio
    async def test_stop_workflow_success(self, mock_automation):
        """Test successful workflow stop."""
        workflow_id = str(uuid.uuid4())
        task_id = "test_task"
        workflow_state = WorkflowState(
            workflow_id=workflow_id,
            task_id=task_id,
            status="running"
        )
        mock_automation.active_workflows[workflow_id] = workflow_state
        
        # Mock workflow task
        workflow_task = AsyncMock()
        workflow_task.done.return_value = False
        mock_automation.workflow_tasks[workflow_id] = workflow_task
        
        mock_automation.integration.task_progress[task_id] = TaskProgress(
            task_id=task_id,
            session_id="session_123",
            start_time=datetime.now()
        )
        mock_automation.integration.cancel_task = AsyncMock()
        
        await mock_automation.stop_workflow(workflow_id)
        
        assert workflow_state.status == "stopped"
        assert workflow_state.end_time is not None
        workflow_task.cancel.assert_called_once()
        mock_automation.integration.cancel_task.assert_called_once_with(task_id)


class TestBrowserAutomationWorkflowExecution:
    """Test workflow execution and coordination."""
    
    @pytest.fixture
    async def mock_automation_with_execution(self):
        """Create BrowserAutomation with execution mocks."""
        config = AutomationConfig(
            enable_websocket_updates=False,
            enable_performance_monitoring=False,
            auto_export_results=False
        )
        memory = AsyncMock()
        
        automation = BrowserAutomation(config=config, memory=memory)
        automation.integration = AsyncMock()
        
        # Mock integration execute_task
        mock_result = TaskResult(
            task_id="test_task",
            session_id="session_123",
            success=True,
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration_seconds=30.0,
            urls_processed=5,
            urls_successful=4,
            urls_failed=1,
            data_extracted=10
        )
        automation.integration.execute_task.return_value = mock_result
        
        return automation
    
    @pytest.mark.asyncio
    async def test_execute_crawl_with_completion(self, mock_automation_with_execution):
        """Test crawl execution with wait for completion."""
        # Setup workflow
        workflow_id = await mock_automation_with_execution.start_session(
            task_id="test_task",
            initial_urls=["https://example.com"]
        )
        
        # Mock the workflow task to complete immediately
        workflow_task = AsyncMock()
        mock_automation_with_execution.workflow_tasks[workflow_id] = workflow_task
        
        # Setup progress in integration layer
        progress = TaskProgress(
            task_id="test_task",
            session_id="session_123",
            start_time=datetime.now(),
            urls_processed=5,
            urls_successful=4
        )
        mock_automation_with_execution.integration.task_progress["test_task"] = progress
        
        result = await mock_automation_with_execution.execute_crawl(
            workflow_id=workflow_id,
            wait_for_completion=True
        )
        
        assert result is not None
        assert result.task_id == "test_task"
    
    @pytest.mark.asyncio
    async def test_execute_crawl_with_timeout(self, mock_automation_with_execution):
        """Test crawl execution with timeout."""
        # Setup workflow
        workflow_id = await mock_automation_with_execution.start_session(
            task_id="test_task",
            initial_urls=["https://example.com"]
        )
        
        # Mock workflow task that never completes
        workflow_task = AsyncMock()
        workflow_task.side_effect = asyncio.sleep(10)  # Long running task
        mock_automation_with_execution.workflow_tasks[workflow_id] = workflow_task
        
        with pytest.raises(asyncio.TimeoutError):
            await mock_automation_with_execution.execute_crawl(
                workflow_id=workflow_id,
                wait_for_completion=True,
                timeout=1  # 1 second timeout
            )
    
    @pytest.mark.asyncio
    async def test_execute_crawl_workflow_error(self, mock_automation_with_execution):
        """Test crawl execution with workflow error."""
        # Setup workflow
        workflow_id = await mock_automation_with_execution.start_session(
            task_id="test_task",
            initial_urls=["https://example.com"]
        )
        
        # Mock workflow task that raises exception
        workflow_task = AsyncMock()
        workflow_task.side_effect = Exception("Test error")
        mock_automation_with_execution.workflow_tasks[workflow_id] = workflow_task
        
        with pytest.raises(Exception, match="Test error"):
            await mock_automation_with_execution.execute_crawl(
                workflow_id=workflow_id,
                wait_for_completion=True
            )
        
        # Check workflow state was updated
        workflow_state = mock_automation_with_execution.active_workflows[workflow_id]
        assert workflow_state.status == "failed"
        assert len(workflow_state.errors) > 0


class TestBrowserAutomationResultsProcessing:
    """Test results processing and export functionality."""
    
    @pytest.fixture
    async def mock_automation_with_results(self):
        """Create BrowserAutomation with results mocks."""
        with tempfile.TemporaryDirectory() as temp_dir:
            export_dir = Path(temp_dir) / "exports"
            config = AutomationConfig(
                export_directory=export_dir,
                auto_export_results=True,
                export_format="json"
            )
            memory = AsyncMock()
            
            automation = BrowserAutomation(config=config, memory=memory)
            
            # Mock extracted data
            mock_data = [
                MagicMock(dict=lambda: {"url": "https://example.com", "title": "Example"}),
                MagicMock(dict=lambda: {"url": "https://test.com", "title": "Test"})
            ]
            memory.query_extracted_data.return_value = mock_data
            
            yield automation
    
    @pytest.mark.asyncio
    async def test_process_results_json_export(self, mock_automation_with_results):
        """Test results processing with JSON export."""
        # Setup workflow
        workflow_id = str(uuid.uuid4())
        workflow_state = WorkflowState(
            workflow_id=workflow_id,
            task_id="test_task",
            session_id="session_123",
            status="completed"
        )
        mock_automation_with_results.active_workflows[workflow_id] = workflow_state
        
        export_data = await mock_automation_with_results.process_results(workflow_id)
        
        assert export_data["workflow_id"] == workflow_id
        assert export_data["task_id"] == "test_task"
        assert len(export_data["extracted_data"]) == 2
        
        # Check file was created
        export_files = list(mock_automation_with_results.config.export_directory.glob("*.json"))
        assert len(export_files) == 1
    
    @pytest.mark.asyncio
    async def test_process_results_custom_export_path(self, mock_automation_with_results):
        """Test results processing with custom export path."""
        workflow_id = str(uuid.uuid4())
        workflow_state = WorkflowState(
            workflow_id=workflow_id,
            task_id="test_task",
            session_id="session_123"
        )
        mock_automation_with_results.active_workflows[workflow_id] = workflow_state
        
        custom_path = mock_automation_with_results.config.export_directory / "custom_export.json"
        
        export_data = await mock_automation_with_results.process_results(
            workflow_id,
            export_path=custom_path
        )
        
        assert export_data["workflow_id"] == workflow_id
        assert custom_path.exists()
    
    @pytest.mark.asyncio
    async def test_process_results_workflow_not_found(self, mock_automation_with_results):
        """Test results processing with invalid workflow ID."""
        with pytest.raises(ValueError, match="Workflow invalid_id not found"):
            await mock_automation_with_results.process_results("invalid_id")


class TestBrowserAutomationSessionRecovery:
    """Test session recovery functionality."""
    
    @pytest.fixture
    async def mock_automation_recovery(self):
        """Create BrowserAutomation with recovery mocks."""
        config = AutomationConfig(
            auto_recover_sessions=True,
            max_recovery_attempts=3
        )
        memory = AsyncMock()
        
        automation = BrowserAutomation(config=config, memory=memory)
        automation.integration = AsyncMock()
        
        return automation
    
    @pytest.mark.asyncio
    async def test_recover_session_success(self, mock_automation_recovery):
        """Test successful session recovery."""
        session_id = "session_123"
        
        # Mock recovery info
        from agent.integration import SessionRecoveryInfo
        recovery_info = SessionRecoveryInfo(
            session_id=session_id,
            task_id="test_task",
            last_checkpoint=datetime.now(),
            last_heartbeat=datetime.now(),
            status="crashed",
            recovery_possible=True,
            estimated_progress=0.5,
            urls_remaining=10
        )
        mock_automation_recovery.integration.get_session_recovery_info.return_value = recovery_info
        mock_automation_recovery.integration.recover_session = AsyncMock()
        
        workflow_id = await mock_automation_recovery.recover_session(session_id)
        
        assert workflow_id in mock_automation_recovery.active_workflows
        workflow_state = mock_automation_recovery.active_workflows[workflow_id]
        assert workflow_state.session_id == session_id
        assert workflow_state.task_id == "test_task"
        assert workflow_state.status == "running"
        
        mock_automation_recovery.integration.recover_session.assert_called_once_with(
            session_id, "resume"
        )
    
    @pytest.mark.asyncio
    async def test_recover_session_not_recoverable(self, mock_automation_recovery):
        """Test session recovery when session is not recoverable."""
        session_id = "session_456"
        
        # Mock non-recoverable session
        from agent.integration import SessionRecoveryInfo
        recovery_info = SessionRecoveryInfo(
            session_id=session_id,
            task_id="test_task",
            last_checkpoint=datetime.now(),
            last_heartbeat=datetime.now(),
            status="corrupted",
            recovery_possible=False,
            estimated_progress=0.0,
            urls_remaining=0,
            crash_reason="Data corruption"
        )
        mock_automation_recovery.integration.get_session_recovery_info.return_value = recovery_info
        
        with pytest.raises(RuntimeError, match="cannot be recovered.*Data corruption"):
            await mock_automation_recovery.recover_session(session_id)
    
    @pytest.mark.asyncio
    async def test_recover_session_integration_failure(self, mock_automation_recovery):
        """Test session recovery when integration layer fails."""
        session_id = "session_789"
        
        # Mock recoverable session
        from agent.integration import SessionRecoveryInfo
        recovery_info = SessionRecoveryInfo(
            session_id=session_id,
            task_id="test_task",
            last_checkpoint=datetime.now(),
            last_heartbeat=datetime.now(),
            status="crashed",
            recovery_possible=True,
            estimated_progress=0.3,
            urls_remaining=5
        )
        mock_automation_recovery.integration.get_session_recovery_info.return_value = recovery_info
        mock_automation_recovery.integration.recover_session.side_effect = Exception("Recovery failed")
        
        with pytest.raises(Exception, match="Recovery failed"):
            await mock_automation_recovery.recover_session(session_id)
        
        # Check workflow state shows failed recovery
        workflow_states = list(mock_automation_recovery.active_workflows.values())
        assert len(workflow_states) == 1
        workflow_state = workflow_states[0]
        assert workflow_state.status == "failed"
        assert any("Recovery failed" in error["error"] for error in workflow_state.errors)


class TestBrowserAutomationWebSocketIntegration:
    """Test WebSocket communication and updates."""
    
    @pytest.fixture
    async def mock_automation_websocket(self):
        """Create BrowserAutomation with WebSocket mocks."""
        config = AutomationConfig(
            enable_websocket_updates=True,
            websocket_update_interval=0.1,  # Fast for testing
            websocket_batch_size=2
        )
        websocket_manager = AsyncMock()
        
        automation = BrowserAutomation(config=config, websocket_manager=websocket_manager)
        automation.integration = AsyncMock()
        
        return automation
    
    @pytest.mark.asyncio
    async def test_websocket_updates_enabled(self, mock_automation_websocket):
        """Test WebSocket updates are sent when enabled."""
        # Start session to trigger WebSocket task
        workflow_id = await mock_automation_websocket.start_session(
            task_id="test_task",
            initial_urls=["https://example.com"]
        )
        
        # Wait briefly for WebSocket task to start
        await asyncio.sleep(0.2)
        
        assert mock_automation_websocket._websocket_task is not None
        assert not mock_automation_websocket._websocket_task.done()
        
        # Clean up
        await mock_automation_websocket.shutdown()
    
    @pytest.mark.asyncio
    async def test_websocket_message_sending(self, mock_automation_websocket):
        """Test WebSocket messages are sent correctly."""
        # Start session
        workflow_id = await mock_automation_websocket.start_session(
            task_id="test_task",
            initial_urls=["https://example.com"]
        )
        
        # Send a test message
        test_message = TaskMessage(
            task_id="test_task",
            type="test_message",
            data={"test": "data"}
        )
        await mock_automation_websocket._send_websocket_update(test_message)
        
        # Wait for message processing
        await asyncio.sleep(0.2)
        
        # Clean up
        await mock_automation_websocket.shutdown()
    
    @pytest.mark.asyncio
    async def test_websocket_disabled(self):
        """Test WebSocket functionality when disabled."""
        config = AutomationConfig(enable_websocket_updates=False)
        automation = BrowserAutomation(config=config)
        
        # Start session should not create WebSocket task
        workflow_id = await automation.start_session(
            task_id="test_task",
            initial_urls=["https://example.com"]
        )
        
        assert automation._websocket_task is None
        
        # Clean up
        await automation.shutdown()


class TestBrowserAutomationPerformanceMonitoring:
    """Test performance monitoring functionality."""
    
    @pytest.fixture
    async def mock_automation_monitoring(self):
        """Create BrowserAutomation with monitoring mocks."""
        config = AutomationConfig(
            enable_performance_monitoring=True,
            performance_sample_interval=0.1,  # Fast for testing
            enable_resource_alerts=True,
            resource_alert_threshold=0.8
        )
        
        automation = BrowserAutomation(config=config)
        
        return automation
    
    @pytest.mark.asyncio
    async def test_performance_monitoring_enabled(self, mock_automation_monitoring):
        """Test performance monitoring starts when enabled."""
        # Start session to trigger monitoring
        workflow_id = await mock_automation_monitoring.start_session(
            task_id="test_task",
            initial_urls=["https://example.com"]
        )
        
        # Wait for monitoring to start
        await asyncio.sleep(0.2)
        
        assert mock_automation_monitoring._monitoring_task is not None
        assert not mock_automation_monitoring._monitoring_task.done()
        
        # Check metrics are being collected
        assert len(mock_automation_monitoring.performance_metrics) > 0
        
        # Clean up
        await mock_automation_monitoring.shutdown()
    
    @pytest.mark.asyncio
    async def test_performance_metrics_collection(self, mock_automation_monitoring):
        """Test performance metrics are collected correctly."""
        # Start monitoring
        workflow_id = await mock_automation_monitoring.start_session(
            task_id="test_task",
            initial_urls=["https://example.com"]
        )
        
        # Wait for several samples
        await asyncio.sleep(0.3)
        
        metrics = mock_automation_monitoring.get_performance_metrics()
        await asyncio.sleep(0.1)  # Allow the coroutine to resolve
        metrics_list = await metrics
        
        assert len(metrics_list) > 0
        
        for metric in metrics_list:
            assert isinstance(metric, PerformanceMetrics)
            assert metric.timestamp is not None
        
        # Clean up
        await mock_automation_monitoring.shutdown()
    
    @pytest.mark.asyncio
    async def test_performance_monitoring_disabled(self):
        """Test performance monitoring when disabled."""
        config = AutomationConfig(enable_performance_monitoring=False)
        automation = BrowserAutomation(config=config)
        
        # Start session should not create monitoring task
        workflow_id = await automation.start_session(
            task_id="test_task",
            initial_urls=["https://example.com"]
        )
        
        assert automation._monitoring_task is None
        assert len(automation.performance_metrics) == 0
        
        # Clean up
        await automation.shutdown()


class TestBrowserAutomationStatusAndListing:
    """Test status reporting and workflow listing."""
    
    @pytest.fixture
    async def mock_automation_status(self):
        """Create BrowserAutomation with status mocks."""
        config = AutomationConfig(enable_websocket_updates=False, enable_performance_monitoring=False)
        automation = BrowserAutomation(config=config)
        automation.integration = AsyncMock()
        
        return automation
    
    @pytest.mark.asyncio
    async def test_get_workflow_status_success(self, mock_automation_status):
        """Test getting workflow status."""
        # Setup workflow
        workflow_id = str(uuid.uuid4())
        workflow_state = WorkflowState(
            workflow_id=workflow_id,
            task_id="test_task",
            session_id="session_123",
            status="running",
            current_phase="crawling"
        )
        mock_automation_status.active_workflows[workflow_id] = workflow_state
        
        # Mock progress
        progress = TaskProgress(
            task_id="test_task",
            session_id="session_123",
            start_time=datetime.now(),
            urls_processed=5,
            urls_successful=4
        )
        mock_automation_status.integration.task_progress["test_task"] = progress
        
        status = await mock_automation_status.get_workflow_status(workflow_id)
        
        assert status["workflow_id"] == workflow_id
        assert status["task_id"] == "test_task"
        assert status["status"] == "running"
        assert status["current_phase"] == "crawling"
        assert status["progress"] is not None
    
    @pytest.mark.asyncio
    async def test_get_workflow_status_not_found(self, mock_automation_status):
        """Test getting status for non-existent workflow."""
        with pytest.raises(ValueError, match="Workflow invalid_id not found"):
            await mock_automation_status.get_workflow_status("invalid_id")
    
    @pytest.mark.asyncio
    async def test_list_workflows_empty(self, mock_automation_status):
        """Test listing workflows when none exist."""
        workflows = await mock_automation_status.list_workflows()
        
        assert isinstance(workflows, list)
        assert len(workflows) == 0
    
    @pytest.mark.asyncio
    async def test_list_workflows_with_data(self, mock_automation_status):
        """Test listing workflows with existing workflows."""
        # Setup multiple workflows
        workflow1_id = str(uuid.uuid4())
        workflow2_id = str(uuid.uuid4())
        
        workflow1 = WorkflowState(
            workflow_id=workflow1_id,
            task_id="task_1",
            status="running",
            current_phase="crawling"
        )
        workflow2 = WorkflowState(
            workflow_id=workflow2_id,
            task_id="task_2",
            status="completed",
            current_phase="completed"
        )
        
        mock_automation_status.active_workflows[workflow1_id] = workflow1
        mock_automation_status.active_workflows[workflow2_id] = workflow2
        
        workflows = await mock_automation_status.list_workflows()
        
        assert len(workflows) == 2
        
        # Check workflow data
        workflow_ids = [w["workflow_id"] for w in workflows]
        assert workflow1_id in workflow_ids
        assert workflow2_id in workflow_ids
        
        for workflow in workflows:
            assert "workflow_id" in workflow
            assert "task_id" in workflow
            assert "status" in workflow
            assert "start_time" in workflow
            assert "current_phase" in workflow


class TestBrowserAutomationShutdown:
    """Test graceful shutdown functionality."""
    
    @pytest.mark.asyncio
    async def test_shutdown_with_active_workflows(self):
        """Test shutdown with active workflows."""
        config = AutomationConfig(enable_websocket_updates=False, enable_performance_monitoring=False)
        automation = BrowserAutomation(config=config)
        automation.integration = AsyncMock()
        automation.integration.close = AsyncMock()
        
        # Start a workflow
        workflow_id = await automation.start_session(
            task_id="test_task",
            initial_urls=["https://example.com"]
        )
        
        # Mock stop_workflow to avoid actual stopping
        automation.stop_workflow = AsyncMock()
        
        await automation.shutdown()
        
        # Check shutdown tasks were called
        automation.stop_workflow.assert_called_once_with(workflow_id)
        automation.integration.close.assert_called_once()
        assert automation._shutdown_event.is_set()
    
    @pytest.mark.asyncio
    async def test_shutdown_with_background_tasks(self):
        """Test shutdown with background tasks running."""
        config = AutomationConfig(
            enable_websocket_updates=True,
            enable_performance_monitoring=True
        )
        automation = BrowserAutomation(config=config)
        automation.integration = AsyncMock()
        automation.integration.close = AsyncMock()
        
        # Start session to trigger background tasks
        workflow_id = await automation.start_session(
            task_id="test_task",
            initial_urls=["https://example.com"]
        )
        
        # Wait for tasks to start
        await asyncio.sleep(0.1)
        
        # Mock stop_workflow
        automation.stop_workflow = AsyncMock()
        
        await automation.shutdown()
        
        # Check tasks were cancelled
        if automation._websocket_task:
            assert automation._websocket_task.cancelled() or automation._websocket_task.done()
        if automation._monitoring_task:
            assert automation._monitoring_task.cancelled() or automation._monitoring_task.done()
        
        assert automation._shutdown_event.is_set()
    
    @pytest.mark.asyncio
    async def test_cleanup_old_sessions(self):
        """Test old session cleanup functionality."""
        config = AutomationConfig(enable_websocket_updates=False, enable_performance_monitoring=False)
        automation = BrowserAutomation(config=config)
        automation.integration = AsyncMock()
        automation.integration.cleanup_old_sessions.return_value = 5
        
        cleanup_count = await automation.cleanup_old_sessions(max_age_days=7)
        
        assert cleanup_count == 5
        automation.integration.cleanup_old_sessions.assert_called_once_with(7)


class TestBrowserAutomationErrorHandling:
    """Test error handling and edge cases."""
    
    @pytest.mark.asyncio
    async def test_workflow_execution_with_integration_error(self):
        """Test workflow execution when integration layer fails."""
        config = AutomationConfig(enable_websocket_updates=False, enable_performance_monitoring=False)
        automation = BrowserAutomation(config=config)
        automation.integration = AsyncMock()
        automation.integration.execute_task.side_effect = Exception("Integration error")
        
        workflow_id = await automation.start_session(
            task_id="test_task",
            initial_urls=["https://example.com"]
        )
        
        # Wait for workflow to complete with error
        workflow_task = automation.workflow_tasks[workflow_id]
        try:
            await workflow_task
        except Exception:
            pass  # Expected to fail
        
        workflow_state = automation.active_workflows[workflow_id]
        assert workflow_state.status == "failed"
        assert len(workflow_state.errors) > 0
        assert "Integration error" in workflow_state.errors[0]["error"]
    
    @pytest.mark.asyncio
    async def test_invalid_workflow_operations(self):
        """Test operations on invalid workflow IDs."""
        config = AutomationConfig(enable_websocket_updates=False, enable_performance_monitoring=False)
        automation = BrowserAutomation(config=config)
        
        invalid_id = "invalid_workflow_123"
        
        with pytest.raises(ValueError):
            await automation.execute_crawl(invalid_id)
        
        with pytest.raises(ValueError):
            await automation.pause_workflow(invalid_id)
        
        with pytest.raises(ValueError):
            await automation.resume_workflow(invalid_id)
        
        with pytest.raises(ValueError):
            await automation.stop_workflow(invalid_id)
        
        with pytest.raises(ValueError):
            await automation.get_workflow_status(invalid_id)
        
        with pytest.raises(ValueError):
            await automation.process_results(invalid_id)
    
    @pytest.mark.asyncio
    async def test_websocket_error_handling(self):
        """Test WebSocket error handling."""
        config = AutomationConfig(enable_websocket_updates=True)
        websocket_manager = AsyncMock()
        websocket_manager.broadcast_to_task.side_effect = Exception("WebSocket error")
        
        automation = BrowserAutomation(config=config, websocket_manager=websocket_manager)
        
        # Start session to trigger WebSocket task
        workflow_id = await automation.start_session(
            task_id="test_task",
            initial_urls=["https://example.com"]
        )
        
        # Send message that will cause error
        test_message = TaskMessage(
            task_id="test_task",
            type="test_message",
            data={"test": "data"}
        )
        await automation._send_websocket_update(test_message)
        
        # Wait for error handling
        await asyncio.sleep(0.2)
        
        # WebSocket task should still be running despite errors
        assert automation._websocket_task is not None
        assert not automation._websocket_task.cancelled()
        
        # Clean up
        await automation.shutdown()