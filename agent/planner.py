"""Task planner for decomposing high-level tasks into manageable subtasks."""
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from agent.llm_agent import LLMAgent, AgentConfig


class TaskConfig(BaseModel):
    """Configuration for task planning."""
    task_id: str
    description: str
    workspace_dir: str
    max_subtasks: int = 20
    confidence_threshold: float = 70.0
    auto_save: bool = True


class PlanningContext(BaseModel):
    """Context information for task planning."""
    user_prompt: str
    search_constraints: List[str] = []
    output_format: str = "markdown"
    time_limit_minutes: int = 60
    additional_context: Optional[str] = None


class SubTask(BaseModel):
    """Represents a single subtask in the plan."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str
    description: str
    status: str = "pending"  # pending, in_progress, completed, failed, skipped
    priority: str = "medium"  # low, medium, high, critical
    estimated_duration: int = 15  # minutes
    progress: float = 0.0  # 0-100%
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    dependencies: List[str] = []  # IDs of required subtasks
    outputs: List[str] = []  # Files or data produced
    notes: Optional[str] = None


class TaskPlanner:
    """Plans and manages task decomposition into subtasks."""
    
    def __init__(self, config: TaskConfig):
        """Initialize the task planner."""
        self.config = config
        self.subtasks: List[SubTask] = []
        self.current_subtask_index = 0
        self.is_plan_complete = False
        self.llm_agent: Optional[LLMAgent] = None
        self.planning_history: List[Dict[str, Any]] = []
        self._subtask_counter = 0  # Counter for unique IDs
        
        # Ensure workspace exists
        self.ensure_workspace_exists()
    
    async def decompose_task(self, context: PlanningContext) -> List[SubTask]:
        """Decompose high-level task into manageable subtasks."""
        if not self.llm_agent:
            agent_config = AgentConfig(
                system_prompt="""You are a task planning assistant. 
                Break down high-level tasks into specific, actionable subtasks.
                Each subtask should be:
                1. Specific and measurable
                2. Achievable in 10-30 minutes
                3. Have clear success criteria
                4. Be logically ordered
                
                Respond with a numbered list of subtasks."""
            )
            self.llm_agent = LLMAgent(agent_config)
        
        # Create planning prompt
        planning_prompt = f"""
        Task: {self.config.description}
        User Requirements: {context.user_prompt}
        Constraints: {', '.join(context.search_constraints)}
        Output Format: {context.output_format}
        Time Limit: {context.time_limit_minutes} minutes
        
        Please break this down into {self.config.max_subtasks} or fewer specific subtasks.
        Each subtask should be actionable and have clear deliverables.
        """
        
        # Get decomposition from LLM
        response = await self.llm_agent.send_message(planning_prompt)
        
        # Parse response into subtasks
        subtasks = self._parse_subtasks_from_response(response)
        
        # Add to our list
        for subtask in subtasks:
            self.add_subtask(subtask)
        
        # Save plan
        if self.config.auto_save:
            self.generate_todo_file()
        
        return subtasks
    
    def _parse_subtasks_from_response(self, response: str) -> List[SubTask]:
        """Parse LLM response into SubTask objects."""
        subtasks = []
        lines = response.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            # Look for numbered items
            match = re.match(r'^\d+\.\s*(.+)', line)
            if match:
                title = match.group(1).strip()
                # Estimate duration based on complexity
                duration = self._estimate_duration(title)
                
                subtask = SubTask(
                    id=f"{self.config.task_id}-{len(subtasks)+1:02d}",
                    title=title,
                    description=f"Execute: {title}",
                    estimated_duration=duration
                )
                subtasks.append(subtask)
        
        return subtasks
    
    def _estimate_duration(self, task_title: str) -> int:
        """Estimate task duration based on title complexity."""
        title_lower = task_title.lower()
        
        # Keywords that suggest longer tasks
        if any(word in title_lower for word in ['analyze', 'compare', 'research', 'study']):
            return 25
        elif any(word in title_lower for word in ['create', 'write', 'generate', 'build']):
            return 20
        elif any(word in title_lower for word in ['search', 'find', 'lookup', 'check']):
            return 10
        else:
            return 15  # Default
    
    def create_subtask(self, title: str, description: str, 
                      estimated_duration: int = 15, priority: str = "medium") -> SubTask:
        """Create a new subtask."""
        # Use counter for unique IDs
        self._subtask_counter += 1
        subtask_id = f"{self.config.task_id}-{self._subtask_counter:02d}"
        
        return SubTask(
            id=subtask_id,
            title=title,
            description=description,
            estimated_duration=estimated_duration,
            priority=priority
        )
    
    def add_subtask(self, subtask: SubTask):
        """Add a subtask to the plan."""
        self.subtasks.append(subtask)
    
    def get_subtask(self, subtask_id: str) -> Optional[SubTask]:
        """Get a subtask by ID."""
        for subtask in self.subtasks:
            if subtask.id == subtask_id:
                return subtask
        return None
    
    def update_subtask_progress(self, subtask_id: str, progress: float, status: str = None):
        """Update subtask progress and status."""
        for i, subtask in enumerate(self.subtasks):
            if subtask.id == subtask_id:
                # Update progress
                self.subtasks[i].progress = progress
                
                if status:
                    self.subtasks[i].status = status
                    
                    # Update timestamps
                    if status == "in_progress" and not subtask.started_at:
                        self.subtasks[i].started_at = datetime.now()
                    elif status == "completed":
                        self.subtasks[i].completed_at = datetime.now()
                
                # Auto-save if enabled
                if self.config.auto_save:
                    self.generate_todo_file()
                break
    
    def get_current_subtask(self) -> Optional[SubTask]:
        """Get the current active subtask."""
        # Look for in_progress tasks first
        for subtask in self.subtasks:
            if subtask.status == "in_progress":
                return subtask
        
        # Then look for pending tasks
        for subtask in self.subtasks:
            if subtask.status == "pending":
                return subtask
        
        return None
    
    def calculate_overall_progress(self) -> float:
        """Calculate overall progress across all subtasks."""
        if not self.subtasks:
            return 0.0
        
        total_progress = sum(subtask.progress for subtask in self.subtasks)
        return total_progress / len(self.subtasks)
    
    def generate_todo_file(self) -> Path:
        """Generate todo.md file in workspace."""
        workspace = Path(self.config.workspace_dir)
        todo_path = workspace / "todo.md"
        
        # Calculate overall progress
        overall_progress = self.calculate_overall_progress()
        
        # Generate markdown content
        content = f"""# Task Plan: {self.config.description}

## Task ID: {self.config.task_id}
## Progress: {overall_progress:.1f}%
## Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

### Subtasks:
"""
        
        for subtask in self.subtasks:
            # Status icon
            if subtask.status == "completed":
                icon = "[x]"
            elif subtask.status == "in_progress":
                icon = "[⏳]"
            elif subtask.status == "failed":
                icon = "[❌]"
            elif subtask.status == "skipped":
                icon = "[⏭️]"
            else:  # pending
                icon = "[ ]"
            
            content += f"- {icon} {subtask.title} ({subtask.status}) - {subtask.progress:.1f}%\n"
            content += f"  - **Duration:** {subtask.estimated_duration}min\n"
            content += f"  - **Priority:** {subtask.priority}\n"
            content += f"  - **Description:** {subtask.description}\n"
            
            if subtask.notes:
                content += f"  - **Notes:** {subtask.notes}\n"
            
            content += "\n"
        
        # Add metadata
        content += f"""
### Planning Metadata:
- **Total Subtasks:** {len(self.subtasks)}
- **Completed:** {len([s for s in self.subtasks if s.status == 'completed'])}
- **In Progress:** {len([s for s in self.subtasks if s.status == 'in_progress'])}
- **Pending:** {len([s for s in self.subtasks if s.status == 'pending'])}
- **Estimated Total Time:** {sum(s.estimated_duration for s in self.subtasks)}min

### Current Status:
{self._get_status_summary()}
"""
        
        # Write file
        todo_path.write_text(content)
        return todo_path
    
    def _get_status_summary(self) -> str:
        """Get current status summary."""
        current = self.get_current_subtask()
        if current:
            return f"Working on: {current.title} ({current.progress:.1f}% complete)"
        elif all(s.status == "completed" for s in self.subtasks):
            return "✅ All subtasks completed!"
        else:
            return "⏸️ Planning phase"
    
    def load_existing_plan(self) -> bool:
        """Load existing plan from todo.md file."""
        workspace = Path(self.config.workspace_dir)
        todo_path = workspace / "todo.md"
        
        if not todo_path.exists():
            return False
        
        try:
            content = todo_path.read_text()
            # Basic parsing - in production would be more robust
            return True
        except Exception:
            return False
    
    def should_replan(self, confidence_score: float) -> bool:
        """Determine if replanning is needed based on confidence."""
        return confidence_score < self.config.confidence_threshold
    
    async def adjust_plan_dynamically(self, current_findings: str, 
                                    confidence_score: float) -> bool:
        """Adjust plan based on current progress and findings."""
        if not self.should_replan(confidence_score):
            return False
        
        if not self.llm_agent:
            agent_config = AgentConfig()
            self.llm_agent = LLMAgent(agent_config)
        
        adjustment_prompt = f"""
        Current task: {self.config.description}
        Current findings: {current_findings}
        Confidence score: {confidence_score}%
        
        The current plan may need adjustment. Please suggest modifications
        to improve the plan based on the findings so far.
        """
        
        # Get adjustment suggestions
        response = await self.llm_agent.send_message(adjustment_prompt)
        
        # Store in planning history
        self.planning_history.append({
            "timestamp": datetime.now().isoformat(),
            "type": "adjustment",
            "confidence_score": confidence_score,
            "findings": current_findings,
            "suggestions": response
        })
        
        return True
    
    def export_plan_json(self) -> str:
        """Export plan to JSON format."""
        plan_data = {
            "task_id": self.config.task_id,
            "description": self.config.description,
            "overall_progress": self.calculate_overall_progress(),
            "subtasks": [
                {
                    "id": s.id,
                    "title": s.title,
                    "description": s.description,
                    "status": s.status,
                    "priority": s.priority,
                    "progress": s.progress,
                    "estimated_duration": s.estimated_duration,
                    "created_at": s.created_at.isoformat(),
                    "started_at": s.started_at.isoformat() if s.started_at else None,
                    "completed_at": s.completed_at.isoformat() if s.completed_at else None
                }
                for s in self.subtasks
            ],
            "planning_history": self.planning_history,
            "generated_at": datetime.now().isoformat()
        }
        
        return json.dumps(plan_data, indent=2)
    
    def ensure_workspace_exists(self):
        """Ensure workspace directory structure exists."""
        workspace = Path(self.config.workspace_dir)
        workspace.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (workspace / "logs").mkdir(exist_ok=True)
        (workspace / "outputs").mkdir(exist_ok=True)
    
    def get_subtask_workspace(self, subtask_id: str) -> Path:
        """Get workspace directory for a specific subtask."""
        workspace = Path(self.config.workspace_dir)
        subtask_dir = workspace / subtask_id
        subtask_dir.mkdir(exist_ok=True)
        return subtask_dir