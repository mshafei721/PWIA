"""Tests for agent CLI commands."""
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest
from typer.testing import CliRunner
from agent.main import app, AgentState


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def temp_state_file(tmp_path):
    """Create a temporary state file for testing."""
    state_dir = tmp_path / "app-memory"
    state_dir.mkdir(exist_ok=True)
    state_file = state_dir / "agent_state.json"
    return state_file


@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection."""
    with patch('agent.main.WebSocketManager') as mock:
        ws_instance = Mock()
        ws_instance.connect = Mock(return_value=True)
        ws_instance.send_status = Mock()
        ws_instance.disconnect = Mock()
        mock.return_value = ws_instance
        yield ws_instance


class TestAgentCLI:
    """Test suite for agent CLI commands."""
    
    def test_status_when_not_running(self, runner, temp_state_file, monkeypatch):
        """Test status command when agent is not running."""
        monkeypatch.setenv("AGENT_STATE_FILE", str(temp_state_file))
        
        result = runner.invoke(app, ["status"])
        
        assert result.exit_code == 0
        # Check for table content - Rich formats it with box characters
        assert "stopped" in result.stdout
        assert "None" in result.stdout
    
    def test_start_command(self, runner, temp_state_file, mock_websocket, monkeypatch):
        """Test starting the agent."""
        monkeypatch.setenv("AGENT_STATE_FILE", str(temp_state_file))
        
        with patch('agent.main.AgentProcess') as mock_process:
            mock_process.return_value.start = Mock(return_value=12345)
            
            result = runner.invoke(app, ["start", "--task-id", "test-task-123"])
            
            assert result.exit_code == 0
            assert "Agent started successfully" in result.stdout
            assert "PID: 12345" in result.stdout
            
            # Verify state file was created
            assert temp_state_file.exists()
            state = json.loads(temp_state_file.read_text())
            assert state["status"] == "running"
            assert state["pid"] == 12345
            assert state["task_id"] == "test-task-123"
            
            # Verify WebSocket notification
            mock_websocket.send_status.assert_called_with({
                "status": "running",
                "pid": 12345,
                "task_id": "test-task-123"
            })
    
    def test_start_when_already_running(self, runner, temp_state_file, monkeypatch):
        """Test starting when agent is already running."""
        monkeypatch.setenv("AGENT_STATE_FILE", str(temp_state_file))
        
        # Create existing state
        state = AgentState(status="running", pid=12345, task_id="existing-task")
        temp_state_file.write_text(state.model_dump_json())
        
        with patch('agent.main.check_process_running', return_value=True):
            result = runner.invoke(app, ["start", "--task-id", "new-task"])
            
            assert result.exit_code == 1
            assert "Agent is already running" in result.stdout
    
    def test_stop_command(self, runner, temp_state_file, mock_websocket, monkeypatch):
        """Test stopping the agent."""
        monkeypatch.setenv("AGENT_STATE_FILE", str(temp_state_file))
        
        # Create running state
        state = AgentState(status="running", pid=12345, task_id="test-task")
        temp_state_file.write_text(state.model_dump_json())
        
        with patch('agent.main.AgentProcess') as mock_process:
            mock_process.return_value.stop = Mock(return_value=True)
            
            result = runner.invoke(app, ["stop"])
            
            assert result.exit_code == 0
            assert "Agent stopped successfully" in result.stdout
            
            # Verify state was updated
            updated_state = json.loads(temp_state_file.read_text())
            assert updated_state["status"] == "stopped"
            assert updated_state["pid"] is None
    
    def test_stop_when_not_running(self, runner, temp_state_file, monkeypatch):
        """Test stopping when agent is not running."""
        monkeypatch.setenv("AGENT_STATE_FILE", str(temp_state_file))
        
        result = runner.invoke(app, ["stop"])
        
        assert result.exit_code == 1
        assert "Agent is not running" in result.stdout
    
    def test_pause_command(self, runner, temp_state_file, mock_websocket, monkeypatch):
        """Test pausing the agent."""
        monkeypatch.setenv("AGENT_STATE_FILE", str(temp_state_file))
        
        # Create running state
        state = AgentState(status="running", pid=12345, task_id="test-task")
        temp_state_file.write_text(state.model_dump_json())
        
        with patch('agent.main.AgentProcess') as mock_process:
            mock_process.return_value.pause = Mock(return_value=True)
            
            result = runner.invoke(app, ["pause"])
            
            assert result.exit_code == 0
            assert "Agent paused successfully" in result.stdout
            
            # Verify state was updated
            updated_state = json.loads(temp_state_file.read_text())
            assert updated_state["status"] == "paused"
    
    def test_resume_command(self, runner, temp_state_file, mock_websocket, monkeypatch):
        """Test resuming the agent."""
        monkeypatch.setenv("AGENT_STATE_FILE", str(temp_state_file))
        
        # Create paused state
        state = AgentState(status="paused", pid=12345, task_id="test-task")
        temp_state_file.write_text(state.model_dump_json())
        
        with patch('agent.main.AgentProcess') as mock_process:
            mock_process.return_value.resume = Mock(return_value=True)
            
            result = runner.invoke(app, ["resume"])
            
            assert result.exit_code == 0
            assert "Agent resumed successfully" in result.stdout
            
            # Verify state was updated
            updated_state = json.loads(temp_state_file.read_text())
            assert updated_state["status"] == "running"
    
    def test_resume_when_not_paused(self, runner, temp_state_file, monkeypatch):
        """Test resuming when agent is not paused."""
        monkeypatch.setenv("AGENT_STATE_FILE", str(temp_state_file))
        
        # Create running state
        state = AgentState(status="running", pid=12345, task_id="test-task")
        temp_state_file.write_text(state.model_dump_json())
        
        result = runner.invoke(app, ["resume"])
        
        assert result.exit_code == 1
        assert "Agent is not paused" in result.stdout
    
    def test_websocket_connection_failure(self, runner, temp_state_file, monkeypatch):
        """Test handling WebSocket connection failure."""
        monkeypatch.setenv("AGENT_STATE_FILE", str(temp_state_file))
        
        with patch('agent.main.WebSocketManager') as mock_ws:
            mock_ws.return_value.connect.side_effect = Exception("Connection failed")
            
            # Should not fail the command, just log warning
            result = runner.invoke(app, ["start", "--task-id", "test-task"])
            
            # Command should still succeed even if WebSocket fails
            assert "Agent started successfully" in result.stdout
    
    def test_config_loading(self, runner, temp_state_file, tmp_path, monkeypatch):
        """Test configuration loading from config directory."""
        monkeypatch.setenv("AGENT_STATE_FILE", str(temp_state_file))
        
        # Create config file
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "agent.yaml"
        config_file.write_text("websocket_url: ws://localhost:8000")
        
        monkeypatch.setenv("AGENT_CONFIG_DIR", str(config_dir))
        
        with patch('agent.main.load_config') as mock_config:
            mock_config.return_value = {"websocket_url": "ws://localhost:8000"}
            
            result = runner.invoke(app, ["status"])
            
            assert result.exit_code == 0
            mock_config.assert_called_once()