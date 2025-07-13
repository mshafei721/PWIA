from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response, StreamingResponse
from typing import List
from datetime import datetime
import uuid
import io

from backend.models import (
    Task, TaskCreate, TaskUpdate, TaskResponse, TaskListResponse,
    TaskStatus, TaskSection, SubTask
)
from backend.file_export import file_exporter

router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
    responses={404: {"description": "Task not found"}},
)

# Mock data for development - matches Frontend structure exactly
MOCK_TASKS = [
    Task(
        id="task_001",
        title="Update Teaching Plans Using Latest Free Resources",
        description="Create updated Design and Analysis of Algorithms teaching report with 14-week plan",
        status=TaskStatus.IN_PROGRESS,
        subtasks=[
            TaskSection(
                id="design_analysis",
                title="Knowledge recalled(2)",
                subtasks=[
                    SubTask(
                        id="create_report",
                        title="Creating the updated Design and Analysis of Algorithms report.",
                        completed=False
                    ),
                    SubTask(
                        id="creating_file",
                        title="Creating file",
                        description="Updated_Design_and_Analysis_of_Algorithms_Report.md",
                        completed=True,
                        file="Updated_Design_and_Analysis_of_Algorithms_Report.md"
                    ),
                    SubTask(
                        id="marking_complete",
                        title="Marking Design and Analysis of Algorithms report creation as complete.",
                        completed=True
                    ),
                    SubTask(
                        id="editing_file",
                        title="Editing file",
                        description="todo.md",
                        completed=True,
                        file="todo.md"
                    )
                ]
            ),
            TaskSection(
                id="reports",
                title="Deliver final updated reports to user",
                subtasks=[
                    SubTask(
                        id="knowledge_recalled",
                        title="Knowledge recalled(4)",
                        completed=False
                    )
                ]
            )
        ],
        created_at=datetime(2024, 1, 13, 10, 30, 0),
        updated_at=datetime(2024, 1, 13, 10, 30, 0),
        agent_id="agent_001",
        confidence=0.85
    ),
    Task(
        id="task_002",
        title="Market Research Analysis",
        description="Analyze competitive landscape for educational technology tools",
        status=TaskStatus.PENDING,
        subtasks=[
            TaskSection(
                id="research_phase",
                title="Research Phase",
                subtasks=[
                    SubTask(
                        id="competitor_analysis",
                        title="Competitor analysis",
                        completed=False
                    ),
                    SubTask(
                        id="market_sizing",
                        title="Market sizing research",
                        completed=False
                    )
                ]
            )
        ],
        created_at=datetime(2024, 1, 13, 9, 15, 0),
        updated_at=datetime(2024, 1, 13, 9, 15, 0),
        agent_id="agent_002",
        confidence=0.0
    )
]

@router.get("/", response_model=TaskListResponse)
async def get_tasks():
    """
    Get all tasks
    
    Returns a list of all tasks in the system.
    """
    return TaskListResponse(
        success=True,
        message="Tasks retrieved successfully",
        tasks=MOCK_TASKS,
        total=len(MOCK_TASKS)
    )

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """
    Get a specific task by ID
    
    Args:
        task_id: The unique identifier of the task
        
    Returns:
        The task details if found
        
    Raises:
        HTTPException: 404 if task not found
    """
    task = next((task for task in MOCK_TASKS if task.id == task_id), None)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id '{task_id}' not found"
        )
    
    return TaskResponse(
        success=True,
        message="Task retrieved successfully",
        task=task
    )

@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(task_data: TaskCreate):
    """
    Create a new task
    
    Args:
        task_data: The task creation data
        
    Returns:
        The created task
    """
    new_task = Task(
        id=str(uuid.uuid4()),
        title=task_data.title,
        description=task_data.description,
        status=TaskStatus.PENDING,
        subtasks=[],
        agent_id=task_data.agent_id,
        confidence=0.0
    )
    
    # Add to mock data (in real implementation, this would save to database)
    MOCK_TASKS.append(new_task)
    
    return TaskResponse(
        success=True,
        message="Task created successfully",
        task=new_task
    )

@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: str, task_update: TaskUpdate):
    """
    Update an existing task
    
    Args:
        task_id: The unique identifier of the task
        task_update: The task update data
        
    Returns:
        The updated task
        
    Raises:
        HTTPException: 404 if task not found
    """
    task_index = next(
        (i for i, task in enumerate(MOCK_TASKS) if task.id == task_id), None
    )
    
    if task_index is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id '{task_id}' not found"
        )
    
    task = MOCK_TASKS[task_index]
    
    # Update fields if provided
    if task_update.title is not None:
        task.title = task_update.title
    if task_update.description is not None:
        task.description = task_update.description
    if task_update.status is not None:
        task.status = task_update.status
    if task_update.confidence is not None:
        task.confidence = task_update.confidence
    
    task.updated_at = datetime.utcnow()
    
    return TaskResponse(
        success=True,
        message="Task updated successfully",
        task=task
    )

@router.delete("/{task_id}", response_model=TaskResponse)
async def delete_task(task_id: str):
    """
    Delete a task
    
    Args:
        task_id: The unique identifier of the task
        
    Returns:
        Success confirmation
        
    Raises:
        HTTPException: 404 if task not found
    """
    task_index = next(
        (i for i, task in enumerate(MOCK_TASKS) if task.id == task_id), None
    )
    
    if task_index is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id '{task_id}' not found"
        )
    
    deleted_task = MOCK_TASKS.pop(task_index)
    
    return TaskResponse(
        success=True,
        message=f"Task '{deleted_task.title}' deleted successfully",
        task=deleted_task
    )


# Export endpoints

@router.get("/export/{format}")
async def export_all_tasks(format: str):
    """
    Export all tasks in the specified format
    
    Args:
        format: Export format ('csv', 'markdown', 'md', 'zip', 'json')
        
    Returns:
        File download with exported data
        
    Raises:
        HTTPException: 400 if format is unsupported
    """
    try:
        content = file_exporter.export_tasks(MOCK_TASKS, format)
        
        # Determine content type and filename
        format_lower = format.lower()
        if format_lower == 'csv':
            media_type = "text/csv"
            filename = f"pwia_tasks_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        elif format_lower in ['markdown', 'md']:
            media_type = "text/markdown"
            filename = f"pwia_tasks_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        elif format_lower == 'json':
            media_type = "application/json"
            filename = f"pwia_tasks_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        elif format_lower == 'zip':
            media_type = "application/zip"
            filename = f"pwia_tasks_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        # For binary formats (ZIP), return as StreamingResponse
        if format_lower == 'zip':
            return StreamingResponse(
                io.BytesIO(content),
                media_type=media_type,
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        else:
            # For text formats, return as Response
            return Response(
                content=content,
                media_type=media_type,
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
            
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}"
        )

@router.get("/{task_id}/export/{format}")
async def export_task(task_id: str, format: str):
    """
    Export a specific task in the specified format
    
    Args:
        task_id: The unique identifier of the task
        format: Export format ('csv', 'markdown', 'md', 'zip', 'json')
        
    Returns:
        File download with exported task data
        
    Raises:
        HTTPException: 404 if task not found, 400 if format is unsupported
    """
    # Find the task
    task = next((task for task in MOCK_TASKS if task.id == task_id), None)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id '{task_id}' not found"
        )
    
    try:
        content = file_exporter.export_task(task, format)
        
        # Determine content type and filename
        format_lower = format.lower()
        safe_title = task.title.replace(' ', '_').replace('/', '_').lower()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if format_lower == 'csv':
            media_type = "text/csv"
            filename = f"task_{task_id}_{safe_title}_{timestamp}.csv"
        elif format_lower in ['markdown', 'md']:
            media_type = "text/markdown"
            filename = f"task_{task_id}_{safe_title}_{timestamp}.md"
        elif format_lower == 'json':
            media_type = "application/json"
            filename = f"task_{task_id}_{safe_title}_{timestamp}.json"
        elif format_lower == 'zip':
            media_type = "application/zip"
            filename = f"task_{task_id}_{safe_title}_{timestamp}.zip"
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        # For binary formats (ZIP), return as StreamingResponse
        if format_lower == 'zip':
            return StreamingResponse(
                io.BytesIO(content),
                media_type=media_type,
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        else:
            # For text formats, return as Response
            return Response(
                content=content,
                media_type=media_type,
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
            
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}"
        )