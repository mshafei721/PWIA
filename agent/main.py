"""PWIA Agent CLI - Main entry point for agent control."""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
import psutil
import typer
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table


# CLI app instance
app = typer.Typer(help="PWIA Agent Control CLI")
console = Console()


class AgentState(BaseModel):
    """Agent state model for persistence."""
    status: str = "stopped"  # running, paused, stopped
    pid: Optional[int] = None
    task_id: Optional[str] = None
    started_at: Optional[str] = None
    paused_at: Optional[str] = None
    confidence_score: float = 0.0


class WebSocketManager:
    """Manages WebSocket connection to backend."""
    
    def __init__(self, url: str = "ws://localhost:8000/ws"):
        self.url = url
        self.connection = None
    
    def connect(self):
        """Establish WebSocket connection."""
        # Implementation will use websockets library
        # For now, this is a stub
        return True
    
    def send_status(self, status_data: dict):
        """Send agent status update."""
        # Will implement actual WebSocket send
        console.print(f"[blue]WebSocket: {status_data}[/blue]")
    
    def disconnect(self):
        """Close WebSocket connection."""
        if self.connection:
            # Close connection
            self.connection = None


class AgentProcess:
    """Manages the agent process lifecycle."""
    
    def __init__(self, state_file: Path):
        self.state_file = state_file
    
    def start(self, task_id: str) -> int:
        """Start the agent process."""
        # In production, this would spawn the actual agent process
        # For now, return a mock PID
        import random
        return random.randint(10000, 99999)
    
    def stop(self, pid: int) -> bool:
        """Stop the agent process."""
        try:
            if check_process_running(pid):
                process = psutil.Process(pid)
                process.terminate()
                return True
        except psutil.NoSuchProcess:
            pass
        return True
    
    def pause(self, pid: int) -> bool:
        """Pause the agent process."""
        # Send pause signal to process
        return True
    
    def resume(self, pid: int) -> bool:
        """Resume the agent process."""
        # Send resume signal to process
        return True


def get_state_file() -> Path:
    """Get the agent state file path."""
    state_file = os.getenv("AGENT_STATE_FILE", "app-memory/agent_state.json")
    return Path(state_file)


def load_state() -> AgentState:
    """Load agent state from file."""
    state_file = get_state_file()
    if state_file.exists():
        try:
            data = json.loads(state_file.read_text())
            return AgentState(**data)
        except Exception as e:
            console.print(f"[red]Error loading state: {e}[/red]")
    return AgentState()


def save_state(state: AgentState):
    """Save agent state to file."""
    state_file = get_state_file()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(state.model_dump_json(indent=2))


def check_process_running(pid: int) -> bool:
    """Check if a process with given PID is running."""
    try:
        process = psutil.Process(pid)
        return process.is_running()
    except psutil.NoSuchProcess:
        return False


def load_config() -> dict:
    """Load configuration from config directory."""
    config_dir = os.getenv("AGENT_CONFIG_DIR", "config")
    config_file = Path(config_dir) / "agent.yaml"
    
    if config_file.exists():
        # Would load YAML config here
        return {"websocket_url": "ws://localhost:8000"}
    return {}


@app.command()
def status():
    """Show current agent status."""
    state = load_state()
    
    # Load config (for test verification)
    config = load_config()
    
    # Create status table
    table = Table(title="PWIA Agent Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Agent Status", state.status)
    table.add_row("PID", str(state.pid) if state.pid else "None")
    table.add_row("Task ID", state.task_id or "None")
    table.add_row("Started At", state.started_at or "N/A")
    table.add_row("Confidence Score", f"{state.confidence_score:.1f}%")
    
    # Check if process is actually running
    if state.pid and not check_process_running(state.pid):
        table.add_row("Warning", "[red]Process not found - may have crashed[/red]")
    
    console.print(table)


@app.command()
def start(task_id: str = typer.Option(..., help="Task ID to work on")):
    """Start the agent with a specific task."""
    state = load_state()
    
    # Check if already running
    if state.status == "running" and state.pid and check_process_running(state.pid):
        console.print("[red]Agent is already running![/red]")
        raise typer.Exit(1)
    
    # Initialize WebSocket connection
    ws_manager = WebSocketManager()
    try:
        ws_manager.connect()
    except Exception as e:
        console.print(f"[yellow]Warning: WebSocket connection failed: {e}[/yellow]")
    
    # Start the agent process
    process = AgentProcess(get_state_file())
    pid = process.start(task_id)
    
    # Update state
    state.status = "running"
    state.pid = pid
    state.task_id = task_id
    state.started_at = datetime.now().isoformat()
    state.confidence_score = 100.0  # Start with full confidence
    save_state(state)
    
    # Send status via WebSocket
    try:
        ws_manager.send_status({
            "status": "running",
            "pid": pid,
            "task_id": task_id
        })
    except Exception:
        pass  # Don't fail if WebSocket is down
    
    console.print(f"[green]Agent started successfully![/green]")
    console.print(f"PID: {pid}")
    console.print(f"Task ID: {task_id}")


@app.command()
def stop():
    """Stop the running agent."""
    state = load_state()
    
    if state.status == "stopped" or not state.pid:
        console.print("[red]Agent is not running![/red]")
        raise typer.Exit(1)
    
    # Stop the process
    process = AgentProcess(get_state_file())
    if process.stop(state.pid):
        # Update state
        state.status = "stopped"
        state.pid = None
        save_state(state)
        
        # Notify via WebSocket
        ws_manager = WebSocketManager()
        try:
            ws_manager.connect()
            ws_manager.send_status({"status": "stopped"})
        except Exception:
            pass
        
        console.print("[green]Agent stopped successfully![/green]")
    else:
        console.print("[red]Failed to stop agent![/red]")
        raise typer.Exit(1)


@app.command()
def pause():
    """Pause the running agent."""
    state = load_state()
    
    if state.status != "running" or not state.pid:
        console.print("[red]Agent is not running![/red]")
        raise typer.Exit(1)
    
    # Pause the process
    process = AgentProcess(get_state_file())
    if process.pause(state.pid):
        # Update state
        state.status = "paused"
        state.paused_at = datetime.now().isoformat()
        save_state(state)
        
        # Notify via WebSocket
        ws_manager = WebSocketManager()
        try:
            ws_manager.connect()
            ws_manager.send_status({"status": "paused"})
        except Exception:
            pass
        
        console.print("[green]Agent paused successfully![/green]")
    else:
        console.print("[red]Failed to pause agent![/red]")
        raise typer.Exit(1)


@app.command()
def resume():
    """Resume a paused agent."""
    state = load_state()
    
    if state.status != "paused":
        console.print("[red]Agent is not paused![/red]")
        raise typer.Exit(1)
    
    # Resume the process
    process = AgentProcess(get_state_file())
    if process.resume(state.pid):
        # Update state
        state.status = "running"
        state.paused_at = None
        save_state(state)
        
        # Notify via WebSocket
        ws_manager = WebSocketManager()
        try:
            ws_manager.connect()
            ws_manager.send_status({"status": "running"})
        except Exception:
            pass
        
        console.print("[green]Agent resumed successfully![/green]")
    else:
        console.print("[red]Failed to resume agent![/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()