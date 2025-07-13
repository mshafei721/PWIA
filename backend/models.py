from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class TaskStatus(str, Enum):
    """Task status enumeration"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"

class SubTask(BaseModel):
    """Individual subtask within a task"""
    id: str
    title: str
    completed: bool = False
    description: Optional[str] = None
    file: Optional[str] = None
    
    model_config = {"json_schema_extra": {
            "example": {
                "id": "create_report",
                "title": "Creating the updated Design and Analysis of Algorithms report.",
                "completed": False,
                "description": "Generate comprehensive teaching report",
                "file": None
            }}
        }

class TaskSection(BaseModel):
    """Section containing multiple subtasks"""
    id: str
    title: str
    subtasks: List[SubTask] = []
    
    model_config = {"json_schema_extra": {
            "example": {
                "id": "design_analysis",
                "title": "Knowledge recalled(2)",
                "subtasks": []
            }}
        }

class Task(BaseModel):
    """Main task model matching Frontend TaskDetailPanel structure"""
    id: str = Field(..., description="Unique task identifier")
    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Task description")
    status: TaskStatus = TaskStatus.PENDING
    subtasks: List[TaskSection] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    agent_id: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Agent confidence score")
    
    model_config = {"json_schema_extra": {
            "example": {
                "id": "task_001",
                "title": "Update Teaching Plans Using Latest Free Resources",
                "description": "Create updated Design and Analysis of Algorithms teaching report with 14-week plan",
                "status": "in_progress",
                "subtasks": [],
                "created_at": "2024-01-13T10:30:00Z",
                "updated_at": "2024-01-13T10:30:00Z",
                "agent_id": "agent_001",
                "confidence": 0.85
            }}
        }

class MessageType(str, Enum):
    """Message types for agent communication"""
    USER_MESSAGE = "user_message"
    AGENT_MESSAGE = "agent_message"
    SYSTEM_MESSAGE = "system_message"
    TOOL_CALL = "tool_call"
    ERROR = "error"

class Message(BaseModel):
    """Message model for chat communication"""
    id: str
    task_id: str
    type: MessageType
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = None
    
    model_config = {"json_schema_extra": {
            "example": {
                "id": "msg_001",
                "task_id": "task_001",
                "type": "agent_message",
                "content": "I'm starting to analyze the teaching requirements for the Design and Analysis of Algorithms course.",
                "timestamp": "2024-01-13T10:30:00Z",
                "metadata": {"confidence": 0.9, "source": "planner"}}
            }
        }

class AgentStatus(str, Enum):
    """Agent status enumeration"""
    IDLE = "idle"
    WORKING = "working"
    PAUSED = "paused"
    ERROR = "error"
    OFFLINE = "offline"

class Agent(BaseModel):
    """Agent model for tracking agent state"""
    id: str
    name: str
    status: AgentStatus = AgentStatus.IDLE
    current_task_id: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    capabilities: List[str] = []
    metadata: Optional[Dict[str, Any]] = None
    
    model_config = {"json_schema_extra": {
            "example": {
                "id": "agent_001",
                "name": "PWIA Web Intelligence Agent",
                "status": "working",
                "current_task_id": "task_001",
                "confidence": 0.85,
                "last_activity": "2024-01-13T10:30:00Z",
                "capabilities": ["web_browsing", "data_extraction", "report_generation"],
                "metadata": {"model": "gpt-4", "version": "1.0"}}
            }
        }

# Request/Response models for API endpoints

class TaskCreate(BaseModel):
    """Model for creating new tasks"""
    title: str
    description: str
    agent_id: Optional[str] = None
    
class TaskUpdate(BaseModel):
    """Model for updating tasks"""
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)

class TaskResponse(BaseModel):
    """Response model for task operations"""
    success: bool
    message: str
    task: Optional[Task] = None

class TaskListResponse(BaseModel):
    """Response model for task list operations"""
    success: bool
    message: str
    tasks: List[Task] = []
    total: int = 0