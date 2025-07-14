import asyncio
import logging
from typing import Dict, List, Callable, Any, Optional, Set
from collections import defaultdict
from datetime import datetime, timezone

from backend.models import (
    WebSocketMessage, WebSocketEventType, BrowserStatus, CrawlProgress,
    ExtractionResult, BrowserSession, BrowserPerformanceMetrics, 
    BrowserWebSocketEvent, BrowserErrorEvent
)
from backend.websocket_manager import connection_manager

logger = logging.getLogger(__name__)

class EventBus:
    """Central event bus for routing agent events to WebSocket clients and other components"""
    
    def __init__(self):
        # Event handlers: event_type -> list of async handlers
        self.handlers: Dict[WebSocketEventType, List[Callable]] = defaultdict(list)
        
        # Task-specific handlers: (task_id, event_type) -> list of async handlers  
        self.task_handlers: Dict[tuple, List[Callable]] = defaultdict(list)
        
        # Event history for debugging (limited size)
        self.event_history: List[WebSocketMessage] = []
        self.max_history_size = 1000
        
    def subscribe(self, event_type: WebSocketEventType, handler: Callable, task_id: Optional[str] = None):
        """Subscribe to events of a specific type
        
        Args:
            event_type: The type of event to listen for
            handler: Async function to handle the event (receives WebSocketMessage)
            task_id: If specified, only handle events for this specific task
        """
        if task_id:
            key = (task_id, event_type)
            self.task_handlers[key].append(handler)
            logger.debug(f"Subscribed handler to {event_type} for task {task_id}")
        else:
            self.handlers[event_type].append(handler)
            logger.debug(f"Subscribed handler to {event_type} globally")
    
    def unsubscribe(self, event_type: WebSocketEventType, handler: Callable, task_id: Optional[str] = None):
        """Unsubscribe from events
        
        Args:
            event_type: The type of event to stop listening for
            handler: The handler function to remove
            task_id: If specified, remove only task-specific subscription
        """
        try:
            if task_id:
                key = (task_id, event_type)
                self.task_handlers[key].remove(handler)
                if not self.task_handlers[key]:
                    del self.task_handlers[key]
            else:
                self.handlers[event_type].remove(handler)
        except ValueError:
            logger.warning(f"Handler not found for unsubscribe: {event_type}")
    
    async def emit(self, message: WebSocketMessage):
        """Emit an event to all subscribed handlers and WebSocket clients
        
        Args:
            message: The WebSocketMessage to emit
        """
        # Add to event history
        self.event_history.append(message)
        if len(self.event_history) > self.max_history_size:
            self.event_history.pop(0)
        
        logger.debug(f"Emitting event {message.event_type} for task {message.task_id}")
        
        # Send to WebSocket clients first
        await self._broadcast_to_websockets(message)
        
        # Execute global handlers
        handlers = self.handlers.get(message.event_type, [])
        for handler in handlers:
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"Error in global handler for {message.event_type}: {e}")
        
        # Execute task-specific handlers
        task_key = (message.task_id, message.event_type)
        task_handlers = self.task_handlers.get(task_key, [])
        for handler in task_handlers:
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"Error in task handler for {message.event_type}: {e}")
    
    async def emit_task_event(self, 
                             event_type: WebSocketEventType, 
                             task_id: str, 
                             data: Dict[str, Any],
                             client_id: Optional[str] = None):
        """Convenience method to emit a task-related event
        
        Args:
            event_type: The type of event
            task_id: The task ID this event relates to  
            data: The event data payload
            client_id: Optional specific client ID
        """
        message = WebSocketMessage(
            event_type=event_type,
            task_id=task_id,
            data=data,
            client_id=client_id
        )
        await self.emit(message)
    
    async def emit_agent_status_change(self, agent_id: str, status: str, task_id: str, data: Optional[Dict] = None):
        """Convenience method for agent status changes"""
        event_data = {
            "agent_id": agent_id,
            "status": status,
            **(data or {})
        }
        await self.emit_task_event(
            WebSocketEventType.AGENT_STATUS_CHANGE,
            task_id,
            event_data
        )
    
    async def emit_progress_update(self, task_id: str, progress: float, message: str, confidence: Optional[float] = None):
        """Convenience method for progress updates"""
        event_data = {
            "progress": progress,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        if confidence is not None:
            event_data["confidence"] = confidence
            
        await self.emit_task_event(
            WebSocketEventType.PROGRESS_UPDATE,
            task_id,
            event_data
        )
    
    async def emit_tool_call(self, task_id: str, tool_name: str, args: Dict, result: Optional[Any] = None, error: Optional[str] = None):
        """Convenience method for tool call events"""
        event_type = WebSocketEventType.TOOL_CALL_START if result is None and error is None else WebSocketEventType.TOOL_CALL_END
        
        event_data = {
            "tool_name": tool_name,
            "args": args,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        if result is not None:
            event_data["result"] = result
        if error is not None:
            event_data["error"] = error
            
        await self.emit_task_event(event_type, task_id, event_data)
    
    # Browser Automation Event Methods
    
    async def emit_browser_status_change(self, task_id: str, status: BrowserStatus, 
                                       session_id: str = None, message: str = None):
        """Emit browser status change event."""
        await self.emit_task_event(
            WebSocketEventType.TASK_UPDATED,
            task_id,
            {
                "type": "browser_status",
                "browser_status": status.value,
                "session_id": session_id,
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
        # Also send via connection manager for direct WebSocket delivery
        await connection_manager.send_browser_status_update(task_id, status, session_id, message)
    
    async def emit_crawl_progress(self, task_id: str, progress: CrawlProgress):
        """Emit crawling progress update."""
        await self.emit_task_event(
            WebSocketEventType.PROGRESS_UPDATE,
            task_id,
            {
                "type": "crawl_progress",
                "progress": progress.model_dump(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
        # Also send via connection manager
        await connection_manager.send_crawl_progress_update(task_id, progress)
    
    async def emit_extraction_result(self, task_id: str, extraction: ExtractionResult):
        """Emit data extraction result."""
        await self.emit_task_event(
            WebSocketEventType.TASK_UPDATED,
            task_id,
            {
                "type": "extraction_result",
                "extraction": extraction.model_dump(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
        # Also send via connection manager
        await connection_manager.send_extraction_result(task_id, extraction)
    
    async def emit_browser_session_update(self, task_id: str, session: BrowserSession):
        """Emit browser session update."""
        await self.emit_task_event(
            WebSocketEventType.TASK_UPDATED,
            task_id,
            {
                "type": "browser_session",
                "session": session.model_dump(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
        # Also send via connection manager
        await connection_manager.send_browser_session_update(task_id, session)
    
    async def emit_performance_metrics(self, task_id: str, metrics: BrowserPerformanceMetrics):
        """Emit browser performance metrics."""
        await self.emit_task_event(
            WebSocketEventType.TASK_UPDATED,
            task_id,
            {
                "type": "performance_metrics",
                "metrics": metrics.model_dump(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
        # Also send via connection manager
        await connection_manager.send_performance_metrics(task_id, metrics)
    
    async def emit_browser_event(self, task_id: str, event: BrowserWebSocketEvent):
        """Emit generic browser automation event."""
        await self.emit_task_event(
            WebSocketEventType.TASK_UPDATED,
            task_id,
            {
                "type": "browser_event",
                "event": event.model_dump(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
        # Also send via connection manager
        await connection_manager.send_browser_event(task_id, event)
    
    async def emit_browser_error(self, task_id: str, error: BrowserErrorEvent):
        """Emit browser automation error."""
        await self.emit_task_event(
            WebSocketEventType.TASK_FAILED,
            task_id,
            {
                "type": "browser_error",
                "error": error.model_dump(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
        # Also send via connection manager
        await connection_manager.send_browser_error(task_id, error)
    
    async def emit_page_loaded(self, task_id: str, url: str, success: bool, 
                             load_time: float = None, error_message: str = None):
        """Emit page load event."""
        event = BrowserWebSocketEvent(
            event_type="page.loaded" if success else "page.load_failed",
            session_id="system",  # Default session for page load events
            task_id=task_id,
            data={
                "url": url,
                "success": success,
                "load_time": load_time,
                "error_message": error_message
            }
        )
        await self.emit_browser_event(task_id, event)
    
    async def emit_data_extracted(self, task_id: str, url: str, 
                                fields_extracted: int, confidence_score: float,
                                extracted_data: Dict[str, Any] = None):
        """Emit data extraction event."""
        event = BrowserWebSocketEvent(
            event_type="data.extracted",
            session_id="system",  # Default session for data extraction events
            task_id=task_id,
            data={
                "url": url,
                "fields_extracted": fields_extracted,
                "confidence_score": confidence_score,
                "extracted_data": extracted_data
            }
        )
        await self.emit_browser_event(task_id, event)
    
    async def emit_crawl_started(self, task_id: str, urls: List[str], 
                               max_depth: int, max_pages: int):
        """Emit crawl started event."""
        # Update browser status
        await self.emit_browser_status_change(task_id, BrowserStatus.CRAWLING, 
                                            message=f"Started crawling {len(urls)} URLs")
        
        # Send specific crawl started event
        event = BrowserWebSocketEvent(
            event_type="crawl.started",
            session_id="system",  # Default session for crawl events
            task_id=task_id,
            data={
                "urls": urls,
                "max_depth": max_depth,
                "max_pages": max_pages,
                "start_time": datetime.now(timezone.utc).isoformat()
            }
        )
        await self.emit_browser_event(task_id, event)
    
    async def emit_crawl_completed(self, task_id: str, pages_crawled: int, 
                                 data_extracted: int, duration_seconds: float):
        """Emit crawl completed event."""
        # Update browser status
        await self.emit_browser_status_change(task_id, BrowserStatus.COMPLETED,
                                            message=f"Crawled {pages_crawled} pages, extracted {data_extracted} items")
        
        # Send specific crawl completed event
        event = BrowserWebSocketEvent(
            event_type="crawl.completed",
            session_id="system",  # Default session for crawl events
            task_id=task_id,
            data={
                "pages_crawled": pages_crawled,
                "data_extracted": data_extracted,
                "duration_seconds": duration_seconds,
                "completion_time": datetime.now(timezone.utc).isoformat()
            }
        )
        await self.emit_browser_event(task_id, event)
    
    async def emit_browser_launched(self, task_id: str, session_id: str, browser_type: str):
        """Emit browser launched event."""
        await self.emit_browser_status_change(task_id, BrowserStatus.LAUNCHING,
                                            session_id=session_id,
                                            message=f"Launched {browser_type} browser")
        
        event = BrowserWebSocketEvent(
            event_type="browser.launched",
            session_id=session_id,
            task_id=task_id,
            data={
                "session_id": session_id,
                "browser_type": browser_type,
                "launch_time": datetime.now(timezone.utc).isoformat()
            }
        )
        await self.emit_browser_event(task_id, event)
    
    async def emit_browser_closed(self, task_id: str, session_id: str):
        """Emit browser closed event."""
        await self.emit_browser_status_change(task_id, BrowserStatus.IDLE,
                                            session_id=session_id,
                                            message="Browser session closed")
        
        event = BrowserWebSocketEvent(
            event_type="browser.closed",
            session_id=session_id,
            task_id=task_id,
            data={
                "session_id": session_id,
                "close_time": datetime.now(timezone.utc).isoformat()
            }
        )
        await self.emit_browser_event(task_id, event)
    
    async def _broadcast_to_websockets(self, message: WebSocketMessage):
        """Send message to appropriate WebSocket clients"""
        try:
            # Send to all clients subscribed to this task
            await connection_manager.broadcast_to_task(message, message.task_id)
        except Exception as e:
            logger.error(f"Error broadcasting to WebSocket clients: {e}")
    
    def get_event_history(self, task_id: Optional[str] = None, event_type: Optional[WebSocketEventType] = None, limit: int = 100) -> List[WebSocketMessage]:
        """Get event history with optional filtering
        
        Args:
            task_id: Filter by task ID
            event_type: Filter by event type
            limit: Maximum number of events to return
        """
        filtered_events = self.event_history
        
        if task_id:
            filtered_events = [e for e in filtered_events if e.task_id == task_id]
        
        if event_type:
            filtered_events = [e for e in filtered_events if e.event_type == event_type]
        
        return filtered_events[-limit:] if limit else filtered_events
    
    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics"""
        return {
            "total_handlers": sum(len(handlers) for handlers in self.handlers.values()),
            "task_handlers": sum(len(handlers) for handlers in self.task_handlers.values()),
            "event_history_size": len(self.event_history),
            "handler_types": list(self.handlers.keys()),
            "active_task_subscriptions": list(set(key[0] for key in self.task_handlers.keys()))
        }

# Global event bus instance
event_bus = EventBus()

# Pre-configured event handlers for common scenarios

async def log_all_events(message: WebSocketMessage):
    """Default event logger"""
    logger.info(f"Event: {message.event_type} | Task: {message.task_id} | Data: {message.data}")

async def handle_task_completion(message: WebSocketMessage):
    """Handle task completion events"""
    if message.event_type == WebSocketEventType.TASK_COMPLETED:
        logger.info(f"Task {message.task_id} completed successfully")
        # Could trigger cleanup, notifications, etc.

async def handle_task_failure(message: WebSocketMessage):
    """Handle task failure events"""
    if message.event_type == WebSocketEventType.TASK_FAILED:
        logger.error(f"Task {message.task_id} failed: {message.data}")
        # Could trigger error reporting, cleanup, etc.

# Subscribe default handlers
event_bus.subscribe(WebSocketEventType.TASK_COMPLETED, handle_task_completion)
event_bus.subscribe(WebSocketEventType.TASK_FAILED, handle_task_failure)

# Optional: Subscribe logger for debugging (uncomment for verbose logging)
# for event_type in WebSocketEventType:
#     event_bus.subscribe(event_type, log_all_events)