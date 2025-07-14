import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Set, Optional
from collections import defaultdict, deque
import asyncio
import logging

from fastapi import WebSocket, WebSocketDisconnect
from backend.models import (
    WebSocketMessage, ConnectionInfo, WebSocketEventType,
    BrowserStatus, CrawlProgress, ExtractionResult, BrowserSession,
    BrowserPerformanceMetrics, BrowserWebSocketEvent, BrowserErrorEvent
)

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages WebSocket connections for real-time communication"""
    
    def __init__(self, max_message_queue_size: int = 100):
        # Active connections: task_id -> set of client_ids
        self.active_connections: Dict[str, Set[str]] = defaultdict(set)
        
        # WebSocket connections: client_id -> WebSocket
        self.websockets: Dict[str, WebSocket] = {}
        
        # Connection info: client_id -> ConnectionInfo
        self.connection_info: Dict[str, ConnectionInfo] = {}
        
        # Message queues for offline clients: client_id -> deque of messages
        self.message_queues: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_message_queue_size))
        
        # Task subscribers: task_id -> set of client_ids
        self.task_subscribers: Dict[str, Set[str]] = defaultdict(set)
        
        self.max_message_queue_size = max_message_queue_size
    
    async def connect(self, websocket: WebSocket, task_id: str, client_id: Optional[str] = None) -> str:
        """Accept a WebSocket connection and register it"""
        await websocket.accept()
        
        # Generate client_id if not provided
        if not client_id:
            client_id = f"client_{uuid.uuid4().hex[:8]}"
        
        # Store connection
        self.websockets[client_id] = websocket
        self.active_connections[task_id].add(client_id)
        self.task_subscribers[task_id].add(client_id)
        
        # Create connection info
        user_agent = websocket.headers.get("user-agent")
        self.connection_info[client_id] = ConnectionInfo(
            client_id=client_id,
            task_id=task_id,
            user_agent=user_agent
        )
        
        # Send queued messages if any
        await self._send_queued_messages(client_id)
        
        # Send connection established event
        connection_message = WebSocketMessage(
            event_type=WebSocketEventType.CONNECTION_ESTABLISHED,
            task_id=task_id,
            data={"client_id": client_id, "connected_at": datetime.now(timezone.utc).isoformat()},
            client_id=client_id
        )
        await self.send_personal_message(connection_message, client_id)
        
        logger.info(f"Client {client_id} connected to task {task_id}")
        return client_id
    
    def disconnect(self, client_id: str):
        """Remove a WebSocket connection"""
        if client_id in self.connection_info:
            task_id = self.connection_info[client_id].task_id
            
            # Remove from active connections
            self.active_connections[task_id].discard(client_id)
            self.task_subscribers[task_id].discard(client_id)
            
            # Clean up empty task entries
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]
            if not self.task_subscribers[task_id]:
                del self.task_subscribers[task_id]
            
            # Remove WebSocket and connection info
            self.websockets.pop(client_id, None)
            self.connection_info.pop(client_id, None)
            
            logger.info(f"Client {client_id} disconnected from task {task_id}")
    
    async def send_personal_message(self, message: WebSocketMessage, client_id: str):
        """Send a message to a specific client"""
        if client_id in self.websockets:
            try:
                websocket = self.websockets[client_id]
                await websocket.send_text(message.model_dump_json())
                
                # Update last heartbeat if this is a heartbeat message
                if message.event_type == WebSocketEventType.HEARTBEAT:
                    if client_id in self.connection_info:
                        self.connection_info[client_id].last_heartbeat = datetime.now(timezone.utc)
                        
            except Exception as e:
                logger.error(f"Error sending message to client {client_id}: {e}")
                # Remove disconnected client
                self.disconnect(client_id)
        else:
            # Queue message for offline client
            self.message_queues[client_id].append(message)
            logger.debug(f"Queued message for offline client {client_id}")
    
    async def broadcast_to_task(self, message: WebSocketMessage, task_id: str):
        """Broadcast a message to all clients subscribed to a task"""
        if task_id in self.task_subscribers:
            clients = self.task_subscribers[task_id].copy()  # Copy to avoid modification during iteration
            
            for client_id in clients:
                await self.send_personal_message(message, client_id)
            
            logger.debug(f"Broadcasted message to {len(clients)} clients for task {task_id}")
    
    async def broadcast_to_all(self, message: WebSocketMessage):
        """Broadcast a message to all connected clients"""
        clients = list(self.websockets.keys())
        
        for client_id in clients:
            await self.send_personal_message(message, client_id)
        
        logger.debug(f"Broadcasted message to {len(clients)} clients")
    
    async def _send_queued_messages(self, client_id: str):
        """Send all queued messages to a newly connected client"""
        if client_id in self.message_queues and self.message_queues[client_id]:
            queue = self.message_queues[client_id]
            
            while queue:
                message = queue.popleft()
                await self.send_personal_message(message, client_id)
            
            logger.info(f"Sent queued messages to client {client_id}")
    
    def get_task_connections(self, task_id: str) -> List[str]:
        """Get list of client IDs connected to a specific task"""
        return list(self.active_connections.get(task_id, set()))
    
    def get_connection_info(self, client_id: str) -> Optional[ConnectionInfo]:
        """Get connection information for a client"""
        return self.connection_info.get(client_id)
    
    def get_all_connections(self) -> Dict[str, ConnectionInfo]:
        """Get all connection information"""
        return self.connection_info.copy()
    
    def is_client_connected(self, client_id: str) -> bool:
        """Check if a client is currently connected"""
        return client_id in self.websockets
    
    async def send_heartbeat(self, client_id: str):
        """Send heartbeat to a specific client"""
        if client_id in self.connection_info:
            task_id = self.connection_info[client_id].task_id
            heartbeat_message = WebSocketMessage(
                event_type=WebSocketEventType.HEARTBEAT,
                task_id=task_id,
                data={"timestamp": datetime.now(timezone.utc).isoformat()},
                client_id=client_id
            )
            await self.send_personal_message(heartbeat_message, client_id)
    
    async def cleanup_stale_connections(self, timeout_minutes: int = 5):
        """Remove connections that haven't sent heartbeat within timeout"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
        stale_clients = []
        
        for client_id, info in self.connection_info.items():
            if info.last_heartbeat < cutoff_time:
                stale_clients.append(client_id)
        
        for client_id in stale_clients:
            logger.warning(f"Removing stale connection: {client_id}")
            self.disconnect(client_id)
        
        return len(stale_clients)
    
    # Browser Automation Specific Methods
    
    async def send_browser_status_update(self, task_id: str, browser_status: BrowserStatus, 
                                       session_id: str = None, message: str = None):
        """Send browser status update to all subscribers of a task."""
        status_message = WebSocketMessage(
            event_type=WebSocketEventType.TASK_UPDATED,
            task_id=task_id,
            data={
                "browser_status": browser_status.value,
                "session_id": session_id,
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        await self.broadcast_to_task(status_message, task_id)
        logger.info(f"Sent browser status update to task {task_id}: {browser_status}")
    
    async def send_crawl_progress_update(self, task_id: str, progress: CrawlProgress):
        """Send crawling progress update to task subscribers."""
        progress_message = WebSocketMessage(
            event_type=WebSocketEventType.PROGRESS_UPDATE,
            task_id=task_id,
            data={
                "type": "crawl_progress",
                "progress": progress.model_dump(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        await self.broadcast_to_task(progress_message, task_id)
        logger.debug(f"Sent crawl progress update to task {task_id}: {progress.completion_percentage}%")
    
    async def send_extraction_result(self, task_id: str, extraction: ExtractionResult):
        """Send data extraction result to task subscribers."""
        extraction_message = WebSocketMessage(
            event_type=WebSocketEventType.TASK_UPDATED,
            task_id=task_id,
            data={
                "type": "extraction_result",
                "extraction": extraction.model_dump(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        await self.broadcast_to_task(extraction_message, task_id)
        logger.info(f"Sent extraction result to task {task_id}: {extraction.url}")
    
    async def send_browser_session_update(self, task_id: str, session: BrowserSession):
        """Send browser session information update."""
        session_message = WebSocketMessage(
            event_type=WebSocketEventType.TASK_UPDATED,
            task_id=task_id,
            data={
                "type": "browser_session",
                "session": session.model_dump(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        await self.broadcast_to_task(session_message, task_id)
        logger.debug(f"Sent browser session update to task {task_id}: {session.session_id}")
    
    async def send_performance_metrics(self, task_id: str, metrics: BrowserPerformanceMetrics):
        """Send browser performance metrics to task subscribers."""
        metrics_message = WebSocketMessage(
            event_type=WebSocketEventType.TASK_UPDATED,
            task_id=task_id,
            data={
                "type": "performance_metrics",
                "metrics": metrics.model_dump(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        await self.broadcast_to_task(metrics_message, task_id)
        logger.debug(f"Sent performance metrics to task {task_id}")
    
    async def send_browser_event(self, task_id: str, event: BrowserWebSocketEvent):
        """Send generic browser automation event."""
        event_message = WebSocketMessage(
            event_type=WebSocketEventType.TASK_UPDATED,
            task_id=task_id,
            data={
                "type": "browser_event",
                "event": event.model_dump(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        await self.broadcast_to_task(event_message, task_id)
        logger.info(f"Sent browser event to task {task_id}: {event.event_type}")
    
    async def send_browser_error(self, task_id: str, error: BrowserErrorEvent):
        """Send browser automation error to task subscribers."""
        error_message = WebSocketMessage(
            event_type=WebSocketEventType.TASK_FAILED,
            task_id=task_id,
            data={
                "type": "browser_error",
                "error": error.model_dump(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        await self.broadcast_to_task(error_message, task_id)
        logger.error(f"Sent browser error to task {task_id}: {error.error_type} - {error.error_message}")
    
    async def send_page_load_event(self, task_id: str, url: str, success: bool, 
                                 load_time: float = None, error_message: str = None):
        """Send page load event to task subscribers."""
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
        await self.send_browser_event(task_id, event)
    
    async def send_data_extraction_event(self, task_id: str, url: str, 
                                       fields_extracted: int, confidence_score: float):
        """Send data extraction event to task subscribers."""
        event = BrowserWebSocketEvent(
            event_type="data.extracted",
            session_id="system",  # Default session for data extraction events
            task_id=task_id,
            data={
                "url": url,
                "fields_extracted": fields_extracted,
                "confidence_score": confidence_score
            }
        )
        await self.send_browser_event(task_id, event)
    
    async def send_crawl_started_event(self, task_id: str, urls: List[str], 
                                     max_depth: int, max_pages: int):
        """Send crawl started event to task subscribers."""
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
        await self.send_browser_event(task_id, event)
    
    async def send_crawl_completed_event(self, task_id: str, pages_crawled: int, 
                                       data_extracted: int, duration_seconds: float):
        """Send crawl completed event to task subscribers."""
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
        await self.send_browser_event(task_id, event)
    
    def get_task_browser_subscribers(self, task_id: str) -> List[str]:
        """Get list of clients subscribed to browser events for a task."""
        return self.get_task_connections(task_id)
    
    def get_browser_connection_stats(self) -> Dict[str, int]:
        """Get statistics about browser automation connections."""
        total_connections = len(self.websockets)
        task_count = len(self.active_connections)
        
        # Count connections with browser sessions
        browser_connections = 0
        for client_id, info in self.connection_info.items():
            # Check if this connection is receiving browser updates
            if any("browser" in queue_msg.get("type", "") 
                  for queue_msg in list(self.message_queues.get(client_id, []))):
                browser_connections += 1
        
        return {
            "total_connections": total_connections,
            "active_tasks": task_count,
            "browser_connections": browser_connections,
            "message_queues": len([q for q in self.message_queues.values() if q])
        }

# Global connection manager instance
connection_manager = ConnectionManager()