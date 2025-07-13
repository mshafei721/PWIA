import asyncio
import logging
from typing import Dict, List, Callable, Any, Optional, Set
from collections import defaultdict
from datetime import datetime

from backend.models import WebSocketMessage, WebSocketEventType
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
            "timestamp": datetime.utcnow().isoformat()
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
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if result is not None:
            event_data["result"] = result
        if error is not None:
            event_data["error"] = error
            
        await self.emit_task_event(event_type, task_id, event_data)
    
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