"""Integration tests for agent components."""
import asyncio
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import pytest
from agent.main import AgentState
from agent.llm_agent import LLMAgent, AgentConfig
from agent.planner import TaskPlanner, TaskConfig, PlanningContext
from agent.confidence import ConfidenceScorer, ConfidenceConfig, ScoreFactors
from agent.utils import setup_logging, get_logger, ErrorHandler


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