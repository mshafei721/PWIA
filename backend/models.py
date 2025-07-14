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

class WebSocketEventType(str, Enum):
    """WebSocket event types for real-time communication"""
    # Basic WebSocket events
    CONNECTION_ESTABLISHED = "connection_established"
    CONNECTION_CLOSED = "connection_closed"
    HEARTBEAT = "heartbeat"
    
    # Task-related events
    TASK_STARTED = "task_started"
    TASK_UPDATED = "task_updated"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_PAUSED = "task_paused"
    
    # Agent communication events (AG-UI Protocol foundation)
    MESSAGE_DELTA = "message.delta"
    TOOL_CALL_START = "tool_call.start"
    TOOL_CALL_END = "tool_call.end"
    STATE_PATCH = "state.patch"
    AGENT_STATUS_CHANGE = "agent_status_change"
    
    # Progress events
    PROGRESS_UPDATE = "progress_update"
    CONFIDENCE_UPDATE = "confidence_update"

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

# WebSocket Models

class WebSocketMessage(BaseModel):
    """WebSocket message model for real-time communication"""
    event_type: WebSocketEventType
    task_id: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    client_id: Optional[str] = None
    
    model_config = {"json_schema_extra": {
            "example": {
                "event_type": "task_updated",
                "task_id": "task_001",
                "data": {
                    "status": "in_progress",
                    "confidence": 0.85,
                    "message": "Processing document extraction..."
                },
                "timestamp": "2024-01-13T10:30:00Z",
                "client_id": "client_123"
            }}
        }

class TaskMessage(BaseModel):
    """Message for task-specific updates through WebSocket"""
    task_id: str
    type: str  # e.g., "automation_started", "workflow_completed", "workflow_error"
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {"json_schema_extra": {
            "example": {
                "task_id": "task_001",
                "type": "automation_started",
                "data": {
                    "workflow_id": "wf_123",
                    "session_id": "sess_456",
                    "initial_urls": ["https://example.com"]
                },
                "timestamp": "2024-01-13T10:30:00Z"
            }}
        }

class ProgressUpdate(BaseModel):
    """Progress update for browser automation tasks"""
    task_id: str
    urls_processed: int = 0
    urls_total: int = 0
    current_url: Optional[str] = None
    status: str = "running"
    completion_percentage: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {"json_schema_extra": {
            "example": {
                "task_id": "task_001",
                "urls_processed": 5,
                "urls_total": 10,
                "current_url": "https://example.com/page5",
                "status": "running",
                "completion_percentage": 50.0,
                "timestamp": "2024-01-13T10:35:00Z"
            }}
        }

class ConnectionInfo(BaseModel):
    """Information about a WebSocket connection"""
    client_id: str
    task_id: str
    connected_at: datetime = Field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = Field(default_factory=datetime.utcnow)
    user_agent: Optional[str] = None

# Browser Automation Models

class BrowserStatus(str, Enum):
    """Browser automation status enumeration"""
    IDLE = "idle"
    LAUNCHING = "launching"
    READY = "ready"
    CRAWLING = "crawling"
    EXTRACTING = "extracting"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PAUSED = "paused"
    ERROR = "error"
    SHUTDOWN = "shutdown"

class CrawlProgress(BaseModel):
    """Progress information for web crawling operations"""
    session_id: str
    task_id: str
    status: BrowserStatus = BrowserStatus.IDLE
    current_url: Optional[str] = None
    urls_discovered: int = 0
    urls_processed: int = 0
    urls_total: int = 0
    pages_crawled: int = 0
    data_extracted: int = 0
    errors_encountered: int = 0
    completion_percentage: float = 0.0
    crawl_depth: int = 0
    max_depth: int = 2
    started_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    estimated_completion: Optional[datetime] = None
    
    model_config = {"json_schema_extra": {
        "example": {
            "session_id": "sess_12345",
            "task_id": "task_001",
            "status": "crawling",
            "current_url": "https://example.com/page2",
            "urls_discovered": 25,
            "urls_processed": 8,
            "urls_total": 50,
            "pages_crawled": 8,
            "data_extracted": 45,
            "errors_encountered": 1,
            "completion_percentage": 16.0,
            "crawl_depth": 2,
            "max_depth": 3,
            "started_at": "2024-01-13T10:30:00Z",
            "updated_at": "2024-01-13T10:45:00Z",
            "estimated_completion": "2024-01-13T11:15:00Z"
        }
    }}

class ExtractionResult(BaseModel):
    """Result of data extraction from a webpage"""
    url: str
    title: Optional[str] = None
    text_content: Optional[str] = None
    links: List[str] = []
    images: List[str] = []
    structured_data: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow)
    extraction_success: bool = True
    extraction_errors: List[str] = []
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    
    model_config = {"json_schema_extra": {
        "example": {
            "url": "https://example.com/article",
            "title": "Example Article Title",
            "text_content": "This is the main content of the article...",
            "links": ["https://example.com/link1", "https://example.com/link2"],
            "images": ["https://example.com/image1.jpg"],
            "structured_data": {
                "type": "article",
                "author": "John Doe",
                "published": "2024-01-13",
                "category": "technology"
            },
            "metadata": {
                "word_count": 1250,
                "reading_time": "5 minutes",
                "language": "en"
            },
            "extraction_timestamp": "2024-01-13T10:30:00Z",
            "extraction_success": True,
            "extraction_errors": [],
            "confidence_score": 0.95
        }
    }}

class BrowserPerformanceMetrics(BaseModel):
    """Performance metrics for browser automation"""
    session_id: str
    cpu_usage: float = 0.0  # Percentage
    memory_usage: float = 0.0  # MB
    network_requests: int = 0
    pages_per_minute: float = 0.0
    average_page_load_time: float = 0.0  # seconds
    success_rate: float = 0.0  # percentage
    errors_per_hour: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {"json_schema_extra": {
        "example": {
            "session_id": "sess_12345",
            "cpu_usage": 45.2,
            "memory_usage": 512.8,
            "network_requests": 150,
            "pages_per_minute": 2.5,
            "average_page_load_time": 3.2,
            "success_rate": 94.5,
            "errors_per_hour": 0.8,
            "timestamp": "2024-01-13T10:30:00Z"
        }
    }}

class BrowserSession(BaseModel):
    """Browser automation session information"""
    session_id: str
    task_id: str
    status: BrowserStatus = BrowserStatus.IDLE
    initial_urls: List[str] = []
    crawl_config: Dict[str, Any] = {}
    progress: CrawlProgress = Field(default_factory=lambda: CrawlProgress(session_id="", task_id=""))
    performance_metrics: Optional[BrowserPerformanceMetrics] = None
    results: List[ExtractionResult] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    model_config = {"json_schema_extra": {
        "example": {
            "session_id": "sess_12345",
            "task_id": "task_001",
            "status": "crawling",
            "initial_urls": ["https://example.com", "https://test.com"],
            "crawl_config": {
                "max_depth": 3,
                "max_pages": 50,
                "respect_robots": True,
                "delay": 1.0
            },
            "progress": {},
            "performance_metrics": {},
            "results": [],
            "created_at": "2024-01-13T10:30:00Z",
            "updated_at": "2024-01-13T10:45:00Z",
            "completed_at": None
        }
    }}

# Browser WebSocket Event Models

class BrowserWebSocketEvent(BaseModel):
    """WebSocket event for browser automation updates"""
    event_type: str  # e.g., "browser.started", "page.loaded", "data.extracted"
    session_id: str
    task_id: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {"json_schema_extra": {
        "example": {
            "event_type": "page.loaded",
            "session_id": "sess_12345",
            "task_id": "task_001",
            "data": {
                "url": "https://example.com/page1",
                "title": "Example Page",
                "load_time": 2.3,
                "status_code": 200
            },
            "timestamp": "2024-01-13T10:30:00Z"
        }
    }}

class BrowserErrorEvent(BaseModel):
    """Error event for browser automation failures"""
    session_id: str
    task_id: str
    error_type: str
    error_message: str
    url: Optional[str] = None
    stack_trace: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    recoverable: bool = True
    
    model_config = {"json_schema_extra": {
        "example": {
            "session_id": "sess_12345",
            "task_id": "task_001",
            "error_type": "TimeoutError",
            "error_message": "Page load timeout after 30 seconds",
            "url": "https://example.com/slow-page",
            "stack_trace": "Traceback (most recent call last)...",
            "timestamp": "2024-01-13T10:30:00Z",
            "recoverable": True
        }
    }}