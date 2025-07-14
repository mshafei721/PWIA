"""Browser automation orchestration for complete workflow integration."""
import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Union
from pydantic import BaseModel, Field, validator

from agent.integration import (
    IntegrationLayer, IntegrationConfig, TaskProgress, TaskResult,
    SessionCheckpoint, SessionRecoveryInfo, SessionHeartbeat
)
from agent.browser import BrowserConfig
from agent.crawler import CrawlerConfig
from agent.scraper import ScraperConfig
from agent.memory import AgentMemory
from agent.utils import setup_logging, retry_with_backoff
from backend.websocket_manager import ConnectionManager
from backend.models import TaskStatus, TaskMessage, ProgressUpdate

logger = logging.getLogger(__name__)


class AutomationConfig(BaseModel):
    """Configuration for browser automation orchestration."""
    # Integration settings
    integration_config: IntegrationConfig = Field(default_factory=IntegrationConfig)
    browser_config: BrowserConfig = Field(default_factory=BrowserConfig)
    crawler_config: CrawlerConfig = Field(default_factory=CrawlerConfig)
    scraper_config: ScraperConfig = Field(default_factory=ScraperConfig)
    
    # WebSocket settings
    enable_websocket_updates: bool = True
    websocket_update_interval: float = 1.0  # seconds between updates
    websocket_batch_size: int = 10  # messages to batch before sending
    
    # Workflow settings
    auto_start_crawling: bool = True
    auto_export_results: bool = True
    export_format: str = "json"  # json, csv, markdown
    export_directory: Path = Field(default_factory=lambda: Path("workspace/exports"))
    
    # Monitoring settings
    enable_performance_monitoring: bool = True
    performance_sample_interval: int = 5  # seconds
    enable_resource_alerts: bool = True
    resource_alert_threshold: float = 0.8  # 80% resource usage
    
    # Recovery settings
    auto_recover_sessions: bool = True
    max_recovery_attempts: int = 3
    recovery_delay: int = 5  # seconds between recovery attempts
    
    @validator('export_directory')
    def ensure_export_directory(cls, v):
        """Ensure export directory exists."""
        v.mkdir(parents=True, exist_ok=True)
        return v


class WorkflowState(BaseModel):
    """State of an automation workflow."""
    workflow_id: str
    task_id: str
    session_id: str
    status: str = "initializing"  # initializing, crawling, extracting, exporting, completed, failed
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    current_phase: str = "setup"
    phases_completed: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    websocket_connected: bool = False
    last_update_sent: Optional[datetime] = None


class PerformanceMetrics(BaseModel):
    """Performance metrics for browser automation."""
    timestamp: datetime = Field(default_factory=datetime.now)
    cpu_usage_percent: float = 0.0
    memory_usage_mb: float = 0.0
    active_browser_pages: int = 0
    urls_per_minute: float = 0.0
    extraction_success_rate: float = 0.0
    average_page_load_time: float = 0.0
    average_extraction_time: float = 0.0
    network_requests_count: int = 0
    cache_hit_rate: float = 0.0
    error_rate: float = 0.0


class BrowserAutomation:
    """High-level browser automation orchestrator with WebSocket integration."""
    
    def __init__(
        self,
        config: Optional[AutomationConfig] = None,
        memory: Optional[AgentMemory] = None,
        websocket_manager: Optional[ConnectionManager] = None
    ):
        """Initialize browser automation with configuration."""
        self.config = config or AutomationConfig()
        self.memory = memory or AgentMemory()
        self.websocket_manager = websocket_manager
        
        # Initialize integration layer with component configs
        self.integration = IntegrationLayer(
            browser_config=self.config.browser_config,
            crawler_config=self.config.crawler_config,
            scraper_config=self.config.scraper_config,
            integration_config=self.config.integration_config,
            memory=self.memory
        )
        
        # Workflow state management
        self.active_workflows: Dict[str, WorkflowState] = {}
        self.workflow_tasks: Dict[str, asyncio.Task] = {}
        
        # Performance monitoring
        self.performance_metrics: List[PerformanceMetrics] = []
        self._monitoring_task: Optional[asyncio.Task] = None
        
        # WebSocket update queue
        self._websocket_queue: asyncio.Queue = asyncio.Queue()
        self._websocket_task: Optional[asyncio.Task] = None
        
        # Shutdown handling
        self._shutdown_event = asyncio.Event()
        
        logger.info("BrowserAutomation initialized with full integration stack")
    
    async def start_session(
        self,
        task_id: str,
        initial_urls: List[str],
        extraction_rules: Optional[Dict[str, Any]] = None,
        task_config: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[TaskProgress], None]] = None
    ) -> str:
        """Start a new browser automation session."""
        workflow_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        
        # Create workflow state
        workflow_state = WorkflowState(
            workflow_id=workflow_id,
            task_id=task_id,
            session_id=session_id,
            status="initializing"
        )
        self.active_workflows[workflow_id] = workflow_state
        
        # Start background tasks if enabled
        if self.config.enable_websocket_updates and not self._websocket_task:
            self._websocket_task = asyncio.create_task(self._websocket_update_loop())
        
        if self.config.enable_performance_monitoring and not self._monitoring_task:
            self._monitoring_task = asyncio.create_task(self._performance_monitoring_loop())
        
        # Create workflow task
        workflow_task = asyncio.create_task(
            self._execute_workflow(
                workflow_state,
                initial_urls,
                extraction_rules,
                task_config,
                progress_callback
            )
        )
        self.workflow_tasks[workflow_id] = workflow_task
        
        logger.info(f"Started browser automation session: workflow={workflow_id}, task={task_id}")
        
        # Send initial WebSocket update
        await self._send_websocket_update(
            TaskMessage(
                task_id=task_id,
                type="automation_started",
                data={
                    "workflow_id": workflow_id,
                    "session_id": session_id,
                    "initial_urls": initial_urls,
                    "timestamp": datetime.now().isoformat()
                }
            )
        )
        
        return workflow_id
    
    async def execute_crawl(
        self,
        workflow_id: str,
        wait_for_completion: bool = True,
        timeout: Optional[int] = None
    ) -> Optional[TaskResult]:
        """Execute crawling for a workflow."""
        if workflow_id not in self.active_workflows:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        workflow_state = self.active_workflows[workflow_id]
        workflow_task = self.workflow_tasks.get(workflow_id)
        
        if not workflow_task:
            raise RuntimeError(f"Workflow task {workflow_id} not started")
        
        if wait_for_completion:
            try:
                # Wait for workflow completion with optional timeout
                if timeout:
                    await asyncio.wait_for(workflow_task, timeout=timeout)
                else:
                    await workflow_task
                
                # Get result from integration layer
                if workflow_state.task_id in self.integration.task_progress:
                    progress = self.integration.task_progress[workflow_state.task_id]
                    return await self._create_task_result(workflow_state, progress)
                
            except asyncio.TimeoutError:
                logger.warning(f"Workflow {workflow_id} timed out after {timeout} seconds")
                await self.pause_workflow(workflow_id)
                raise
            except Exception as e:
                logger.error(f"Workflow {workflow_id} failed: {str(e)}")
                workflow_state.status = "failed"
                workflow_state.errors.append({
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
                raise
        
        return None
    
    async def process_results(
        self,
        workflow_id: str,
        export_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """Process and export results from a workflow."""
        if workflow_id not in self.active_workflows:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        workflow_state = self.active_workflows[workflow_id]
        
        # Get extraction results from memory
        extracted_data = await self.memory.query_extracted_data(
            filters={"session_id": workflow_state.session_id}
        )
        
        # Prepare export data
        export_data = {
            "workflow_id": workflow_id,
            "task_id": workflow_state.task_id,
            "session_id": workflow_state.session_id,
            "status": workflow_state.status,
            "start_time": workflow_state.start_time.isoformat(),
            "end_time": workflow_state.end_time.isoformat() if workflow_state.end_time else None,
            "metrics": workflow_state.metrics,
            "extracted_data": [data.dict() for data in extracted_data],
            "export_timestamp": datetime.now().isoformat()
        }
        
        # Export to file if enabled
        if self.config.auto_export_results:
            export_path = export_path or self.config.export_directory / f"{workflow_id}.{self.config.export_format}"
            
            if self.config.export_format == "json":
                with open(export_path, 'w') as f:
                    json.dump(export_data, f, indent=2)
            elif self.config.export_format == "csv":
                # TODO: Implement CSV export
                pass
            elif self.config.export_format == "markdown":
                # TODO: Implement Markdown export
                pass
            
            logger.info(f"Exported results to {export_path}")
            
            # Send WebSocket update
            await self._send_websocket_update(
                TaskMessage(
                    task_id=workflow_state.task_id,
                    type="results_exported",
                    data={
                        "workflow_id": workflow_id,
                        "export_path": str(export_path),
                        "format": self.config.export_format,
                        "data_count": len(extracted_data)
                    }
                )
            )
        
        return export_data
    
    async def pause_workflow(self, workflow_id: str) -> None:
        """Pause a running workflow."""
        if workflow_id not in self.active_workflows:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        workflow_state = self.active_workflows[workflow_id]
        
        # Pause the integration layer task
        if workflow_state.task_id in self.integration.task_progress:
            await self.integration.pause_task(workflow_state.task_id)
        
        workflow_state.status = "paused"
        
        # Send WebSocket update
        await self._send_websocket_update(
            TaskMessage(
                task_id=workflow_state.task_id,
                type="workflow_paused",
                data={
                    "workflow_id": workflow_id,
                    "timestamp": datetime.now().isoformat()
                }
            )
        )
        
        logger.info(f"Paused workflow {workflow_id}")
    
    async def resume_workflow(self, workflow_id: str) -> None:
        """Resume a paused workflow."""
        if workflow_id not in self.active_workflows:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        workflow_state = self.active_workflows[workflow_id]
        
        if workflow_state.status != "paused":
            raise RuntimeError(f"Workflow {workflow_id} is not paused")
        
        # Resume the integration layer task
        if workflow_state.task_id in self.integration.task_progress:
            await self.integration.resume_task(workflow_state.task_id)
        
        workflow_state.status = "running"
        
        # Send WebSocket update
        await self._send_websocket_update(
            TaskMessage(
                task_id=workflow_state.task_id,
                type="workflow_resumed",
                data={
                    "workflow_id": workflow_id,
                    "timestamp": datetime.now().isoformat()
                }
            )
        )
        
        logger.info(f"Resumed workflow {workflow_id}")
    
    async def stop_workflow(self, workflow_id: str) -> None:
        """Stop a running workflow."""
        if workflow_id not in self.active_workflows:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        workflow_state = self.active_workflows[workflow_id]
        workflow_task = self.workflow_tasks.get(workflow_id)
        
        # Cancel the workflow task
        if workflow_task and not workflow_task.done():
            workflow_task.cancel()
        
        # Stop the integration layer task
        if workflow_state.task_id in self.integration.task_progress:
            await self.integration.cancel_task(workflow_state.task_id)
        
        workflow_state.status = "stopped"
        workflow_state.end_time = datetime.now()
        
        # Send WebSocket update
        await self._send_websocket_update(
            TaskMessage(
                task_id=workflow_state.task_id,
                type="workflow_stopped",
                data={
                    "workflow_id": workflow_id,
                    "timestamp": datetime.now().isoformat()
                }
            )
        )
        
        logger.info(f"Stopped workflow {workflow_id}")
    
    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get current status of a workflow."""
        if workflow_id not in self.active_workflows:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        workflow_state = self.active_workflows[workflow_id]
        
        # Get progress from integration layer
        progress = None
        if workflow_state.task_id in self.integration.task_progress:
            progress = self.integration.task_progress[workflow_state.task_id]
        
        return {
            "workflow_id": workflow_id,
            "task_id": workflow_state.task_id,
            "session_id": workflow_state.session_id,
            "status": workflow_state.status,
            "current_phase": workflow_state.current_phase,
            "phases_completed": workflow_state.phases_completed,
            "start_time": workflow_state.start_time.isoformat(),
            "end_time": workflow_state.end_time.isoformat() if workflow_state.end_time else None,
            "progress": progress.dict() if progress else None,
            "metrics": workflow_state.metrics,
            "errors": workflow_state.errors,
            "websocket_connected": workflow_state.websocket_connected
        }
    
    async def list_workflows(self) -> List[Dict[str, Any]]:
        """List all active workflows."""
        workflows = []
        for workflow_id, state in self.active_workflows.items():
            workflows.append({
                "workflow_id": workflow_id,
                "task_id": state.task_id,
                "status": state.status,
                "start_time": state.start_time.isoformat(),
                "current_phase": state.current_phase
            })
        return workflows
    
    async def get_performance_metrics(
        self,
        workflow_id: Optional[str] = None,
        last_n_samples: int = 10
    ) -> List[PerformanceMetrics]:
        """Get performance metrics for workflows."""
        if workflow_id:
            # Filter metrics for specific workflow
            # TODO: Implement workflow-specific metrics filtering
            pass
        
        # Return last N samples
        return self.performance_metrics[-last_n_samples:]
    
    async def recover_session(
        self,
        session_id: str,
        recovery_strategy: str = "resume"
    ) -> str:
        """Recover a crashed or interrupted session."""
        # Get recovery info from integration layer
        recovery_info = await self.integration.get_session_recovery_info(session_id)
        
        if not recovery_info.recovery_possible:
            raise RuntimeError(f"Session {session_id} cannot be recovered: {recovery_info.crash_reason}")
        
        # Create new workflow for recovered session
        workflow_id = str(uuid.uuid4())
        workflow_state = WorkflowState(
            workflow_id=workflow_id,
            task_id=recovery_info.task_id,
            session_id=session_id,
            status="recovering",
            current_phase="recovery"
        )
        self.active_workflows[workflow_id] = workflow_state
        
        # Attempt recovery
        try:
            await self.integration.recover_session(session_id, recovery_strategy)
            workflow_state.status = "running"
            workflow_state.current_phase = "crawling"
            
            # Send WebSocket update
            await self._send_websocket_update(
                TaskMessage(
                    task_id=recovery_info.task_id,
                    type="session_recovered",
                    data={
                        "workflow_id": workflow_id,
                        "session_id": session_id,
                        "recovery_strategy": recovery_strategy,
                        "urls_remaining": recovery_info.urls_remaining
                    }
                )
            )
            
            logger.info(f"Successfully recovered session {session_id} as workflow {workflow_id}")
            return workflow_id
            
        except Exception as e:
            logger.error(f"Failed to recover session {session_id}: {str(e)}")
            workflow_state.status = "failed"
            workflow_state.errors.append({
                "error": f"Recovery failed: {str(e)}",
                "timestamp": datetime.now().isoformat()
            })
            raise
    
    async def cleanup_old_sessions(self, max_age_days: int = 7) -> int:
        """Clean up old sessions and associated data."""
        cleanup_count = await self.integration.cleanup_old_sessions(max_age_days)
        
        # Send WebSocket update
        await self._send_websocket_update(
            TaskMessage(
                task_id="system",
                type="sessions_cleaned",
                data={
                    "sessions_removed": cleanup_count,
                    "max_age_days": max_age_days,
                    "timestamp": datetime.now().isoformat()
                }
            )
        )
        
        logger.info(f"Cleaned up {cleanup_count} old sessions")
        return cleanup_count
    
    async def shutdown(self) -> None:
        """Shutdown browser automation and cleanup resources."""
        logger.info("Shutting down BrowserAutomation")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Stop all active workflows
        for workflow_id in list(self.active_workflows.keys()):
            try:
                await self.stop_workflow(workflow_id)
            except Exception as e:
                logger.error(f"Error stopping workflow {workflow_id}: {str(e)}")
        
        # Cancel background tasks
        if self._websocket_task:
            self._websocket_task.cancel()
        if self._monitoring_task:
            self._monitoring_task.cancel()
        
        # Shutdown integration layer
        await self.integration.close()
        
        logger.info("BrowserAutomation shutdown complete")
    
    # Private helper methods
    
    async def _execute_workflow(
        self,
        workflow_state: WorkflowState,
        initial_urls: List[str],
        extraction_rules: Optional[Dict[str, Any]],
        task_config: Optional[Dict[str, Any]],
        progress_callback: Optional[Callable[[TaskProgress], None]]
    ) -> None:
        """Execute the complete workflow for a browser automation task."""
        try:
            # Phase 1: Initialization
            workflow_state.current_phase = "initialization"
            workflow_state.status = "running"
            
            # Phase 2: Crawling
            workflow_state.current_phase = "crawling"
            
            # Set up progress callback wrapper
            async def progress_wrapper(progress: TaskProgress):
                # Update workflow metrics
                workflow_state.metrics.update({
                    "urls_processed": progress.urls_processed,
                    "urls_successful": progress.urls_successful,
                    "urls_failed": progress.urls_failed,
                    "data_extracted": progress.data_extracted,
                    "completion_percentage": progress.completion_percentage
                })
                
                # Send WebSocket update
                await self._send_websocket_update(
                    ProgressUpdate(
                        task_id=workflow_state.task_id,
                        urls_processed=progress.urls_processed,
                        urls_total=progress.urls_queued,
                        current_url=progress.current_url,
                        status=progress.status,
                        completion_percentage=progress.completion_percentage
                    )
                )
                
                # Call user callback if provided
                if progress_callback:
                    await progress_callback(progress)
            
            # Execute task through integration layer
            result = await self.integration.execute_task(
                task_id=workflow_state.task_id,
                initial_urls=initial_urls,
                extraction_rules=extraction_rules,
                task_config=task_config
            )
            
            # Phase 3: Processing results
            workflow_state.current_phase = "processing"
            workflow_state.phases_completed.append("crawling")
            
            # Phase 4: Export if enabled
            if self.config.auto_export_results:
                workflow_state.current_phase = "exporting"
                await self.process_results(workflow_state.workflow_id)
                workflow_state.phases_completed.append("exporting")
            
            # Mark as completed
            workflow_state.status = "completed"
            workflow_state.end_time = datetime.now()
            workflow_state.phases_completed.append("processing")
            
            # Send completion update
            await self._send_websocket_update(
                TaskMessage(
                    task_id=workflow_state.task_id,
                    type="workflow_completed",
                    data={
                        "workflow_id": workflow_state.workflow_id,
                        "duration_seconds": (workflow_state.end_time - workflow_state.start_time).total_seconds(),
                        "result": result.dict() if result else None
                    }
                )
            )
            
        except Exception as e:
            logger.error(f"Workflow {workflow_state.workflow_id} failed: {str(e)}")
            workflow_state.status = "failed"
            workflow_state.end_time = datetime.now()
            workflow_state.errors.append({
                "phase": workflow_state.current_phase,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
            
            # Send error update
            await self._send_websocket_update(
                TaskMessage(
                    task_id=workflow_state.task_id,
                    type="workflow_error",
                    data={
                        "workflow_id": workflow_state.workflow_id,
                        "error": str(e),
                        "phase": workflow_state.current_phase
                    }
                )
            )
            raise
    
    async def _websocket_update_loop(self) -> None:
        """Background task for sending WebSocket updates."""
        batch = []
        last_send_time = datetime.now()
        
        while not self._shutdown_event.is_set():
            try:
                # Get message from queue with timeout
                message = await asyncio.wait_for(
                    self._websocket_queue.get(),
                    timeout=self.config.websocket_update_interval
                )
                batch.append(message)
                
                # Send batch if full or interval exceeded
                if (len(batch) >= self.config.websocket_batch_size or
                    (datetime.now() - last_send_time).total_seconds() >= self.config.websocket_update_interval):
                    
                    if self.websocket_manager:
                        for msg in batch:
                            await self.websocket_manager.broadcast_to_task(msg, msg.task_id)
                    
                    batch.clear()
                    last_send_time = datetime.now()
                    
            except asyncio.TimeoutError:
                # Send any pending messages
                if batch and self.websocket_manager:
                    for msg in batch:
                        await self.websocket_manager.broadcast_to_task(msg, msg.task_id)
                    batch.clear()
                    last_send_time = datetime.now()
            except Exception as e:
                logger.error(f"Error in WebSocket update loop: {str(e)}")
    
    async def _performance_monitoring_loop(self) -> None:
        """Background task for performance monitoring."""
        while not self._shutdown_event.is_set():
            try:
                # Collect performance metrics
                metrics = await self._collect_performance_metrics()
                self.performance_metrics.append(metrics)
                
                # Limit metrics history
                if len(self.performance_metrics) > 1000:
                    self.performance_metrics = self.performance_metrics[-1000:]
                
                # Check resource alerts
                if self.config.enable_resource_alerts:
                    if metrics.memory_usage_mb > (self.config.integration_config.max_memory_usage_mb * self.config.resource_alert_threshold):
                        await self._send_websocket_update(
                            TaskMessage(
                                task_id="system",
                                type="resource_alert",
                                data={
                                    "alert_type": "memory",
                                    "current_usage_mb": metrics.memory_usage_mb,
                                    "threshold_mb": self.config.integration_config.max_memory_usage_mb * self.config.resource_alert_threshold,
                                    "timestamp": datetime.now().isoformat()
                                }
                            )
                        )
                
                # Wait for next sample
                await asyncio.sleep(self.config.performance_sample_interval)
                
            except Exception as e:
                logger.error(f"Error in performance monitoring: {str(e)}")
                await asyncio.sleep(self.config.performance_sample_interval)
    
    async def _collect_performance_metrics(self) -> PerformanceMetrics:
        """Collect current performance metrics."""
        # TODO: Implement actual metrics collection
        # This would integrate with system monitoring tools
        return PerformanceMetrics(
            cpu_usage_percent=0.0,
            memory_usage_mb=0.0,
            active_browser_pages=len(self.integration.session_browsers),
            urls_per_minute=0.0,
            extraction_success_rate=0.0,
            average_page_load_time=0.0,
            average_extraction_time=0.0,
            network_requests_count=0,
            cache_hit_rate=0.0,
            error_rate=0.0
        )
    
    async def _send_websocket_update(self, message: Union[TaskMessage, ProgressUpdate]) -> None:
        """Send update through WebSocket."""
        if self.config.enable_websocket_updates:
            await self._websocket_queue.put(message)
    
    async def _create_task_result(
        self,
        workflow_state: WorkflowState,
        progress: TaskProgress
    ) -> TaskResult:
        """Create task result from workflow state and progress."""
        return TaskResult(
            task_id=workflow_state.task_id,
            session_id=workflow_state.session_id,
            success=workflow_state.status == "completed",
            start_time=workflow_state.start_time,
            end_time=workflow_state.end_time or datetime.now(),
            duration_seconds=(workflow_state.end_time or datetime.now() - workflow_state.start_time).total_seconds(),
            urls_processed=progress.urls_processed,
            urls_successful=progress.urls_successful,
            urls_failed=progress.urls_failed,
            data_extracted=progress.data_extracted,
            extraction_results=[],  # Will be populated from memory
            failed_urls=[],  # Will be populated from progress tracking
            error_message=workflow_state.errors[-1]["error"] if workflow_state.errors else None,
            metrics=workflow_state.metrics
        )