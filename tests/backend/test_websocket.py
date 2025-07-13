import pytest
import json
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

from fastapi.testclient import TestClient
from fastapi import WebSocket

from backend.main import app
from backend.websocket_manager import ConnectionManager, connection_manager
from backend.event_bus import EventBus, event_bus
from backend.models import WebSocketMessage, WebSocketEventType, ConnectionInfo

@pytest.fixture
def clean_connection_manager():
    """Fixture to provide a clean ConnectionManager for each test"""
    manager = ConnectionManager()
    yield manager
    # Cleanup after test
    manager.active_connections.clear()
    manager.websockets.clear()
    manager.connection_info.clear()
    manager.message_queues.clear()
    manager.task_subscribers.clear()

@pytest.fixture
def clean_event_bus():
    """Fixture to provide a clean EventBus for each test"""
    bus = EventBus()
    yield bus
    # Cleanup after test
    bus.handlers.clear()
    bus.task_handlers.clear()
    bus.event_history.clear()

@pytest.fixture
def mock_websocket():
    """Fixture to provide a mock WebSocket"""
    websocket = Mock(spec=WebSocket)
    websocket.accept = AsyncMock()
    websocket.send_text = AsyncMock()
    websocket.receive_text = AsyncMock()
    websocket.headers = {"user-agent": "test-client"}
    return websocket

class TestConnectionManager:
    """Test suite for ConnectionManager"""
    
    @pytest.mark.asyncio
    async def test_connect_new_client(self, clean_connection_manager, mock_websocket):
        """Test connecting a new WebSocket client"""
        manager = clean_connection_manager
        task_id = "test_task_001"
        
        client_id = await manager.connect(mock_websocket, task_id)
        
        # Verify connection was established
        assert client_id.startswith("client_")
        assert client_id in manager.websockets
        assert client_id in manager.active_connections[task_id]
        assert client_id in manager.task_subscribers[task_id]
        assert client_id in manager.connection_info
        
        # Verify WebSocket was accepted and initial message sent
        mock_websocket.accept.assert_called_once()
        mock_websocket.send_text.assert_called()
    
    @pytest.mark.asyncio
    async def test_connect_with_custom_client_id(self, clean_connection_manager, mock_websocket):
        """Test connecting with a custom client ID"""
        manager = clean_connection_manager
        task_id = "test_task_001"
        custom_client_id = "custom_client_123"
        
        client_id = await manager.connect(mock_websocket, task_id, custom_client_id)
        
        assert client_id == custom_client_id
        assert custom_client_id in manager.websockets
    
    def test_disconnect_client(self, clean_connection_manager, mock_websocket):
        """Test disconnecting a WebSocket client"""
        manager = clean_connection_manager
        task_id = "test_task_001"
        client_id = "test_client"
        
        # Setup connection manually
        manager.websockets[client_id] = mock_websocket
        manager.active_connections[task_id].add(client_id)
        manager.task_subscribers[task_id].add(client_id)
        manager.connection_info[client_id] = ConnectionInfo(
            client_id=client_id,
            task_id=task_id
        )
        
        # Disconnect
        manager.disconnect(client_id)
        
        # Verify cleanup
        assert client_id not in manager.websockets
        assert client_id not in manager.active_connections[task_id]
        assert client_id not in manager.task_subscribers[task_id]
        assert client_id not in manager.connection_info
    
    @pytest.mark.asyncio
    async def test_send_personal_message(self, clean_connection_manager, mock_websocket):
        """Test sending a message to a specific client"""
        manager = clean_connection_manager
        task_id = "test_task_001"
        client_id = "test_client"
        
        # Setup connection
        manager.websockets[client_id] = mock_websocket
        manager.connection_info[client_id] = ConnectionInfo(
            client_id=client_id,
            task_id=task_id
        )
        
        # Create test message
        message = WebSocketMessage(
            event_type=WebSocketEventType.TASK_UPDATED,
            task_id=task_id,
            data={"status": "in_progress"},
            client_id=client_id
        )
        
        # Send message
        await manager.send_personal_message(message, client_id)
        
        # Verify message was sent
        mock_websocket.send_text.assert_called_once()
        sent_data = mock_websocket.send_text.call_args[0][0]
        sent_message = json.loads(sent_data)
        assert sent_message["event_type"] == "task_updated"
        assert sent_message["task_id"] == task_id
    
    @pytest.mark.asyncio
    async def test_broadcast_to_task(self, clean_connection_manager):
        """Test broadcasting a message to all clients subscribed to a task"""
        manager = clean_connection_manager
        task_id = "test_task_001"
        
        # Setup multiple clients
        clients = []
        for i in range(3):
            client_id = f"client_{i}"
            mock_ws = Mock(spec=WebSocket)
            mock_ws.send_text = AsyncMock()
            
            manager.websockets[client_id] = mock_ws
            manager.task_subscribers[task_id].add(client_id)
            clients.append((client_id, mock_ws))
        
        # Create test message
        message = WebSocketMessage(
            event_type=WebSocketEventType.TASK_UPDATED,
            task_id=task_id,
            data={"status": "completed"}
        )
        
        # Broadcast message
        await manager.broadcast_to_task(message, task_id)
        
        # Verify all clients received the message
        for client_id, mock_ws in clients:
            mock_ws.send_text.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_message_queuing_for_offline_client(self, clean_connection_manager):
        """Test that messages are queued for offline clients"""
        manager = clean_connection_manager
        task_id = "test_task_001"
        client_id = "offline_client"
        
        # Create test message for offline client
        message = WebSocketMessage(
            event_type=WebSocketEventType.TASK_UPDATED,
            task_id=task_id,
            data={"status": "started"}
        )
        
        # Send message to offline client
        await manager.send_personal_message(message, client_id)
        
        # Verify message was queued
        assert len(manager.message_queues[client_id]) == 1
        queued_message = manager.message_queues[client_id][0]
        assert queued_message.event_type == WebSocketEventType.TASK_UPDATED
    
    def test_get_task_connections(self, clean_connection_manager):
        """Test getting connections for a specific task"""
        manager = clean_connection_manager
        task_id = "test_task_001"
        
        # Add multiple clients to task
        client_ids = ["client_1", "client_2", "client_3"]
        for client_id in client_ids:
            manager.active_connections[task_id].add(client_id)
        
        # Get task connections
        connections = manager.get_task_connections(task_id)
        
        assert len(connections) == 3
        assert set(connections) == set(client_ids)
    
    def test_connection_info_tracking(self, clean_connection_manager):
        """Test connection info is properly tracked"""
        manager = clean_connection_manager
        task_id = "test_task_001"
        client_id = "test_client"
        
        # Create connection info
        connection_info = ConnectionInfo(
            client_id=client_id,
            task_id=task_id,
            user_agent="test-browser"
        )
        manager.connection_info[client_id] = connection_info
        
        # Test retrieval
        retrieved_info = manager.get_connection_info(client_id)
        assert retrieved_info is not None
        assert retrieved_info.client_id == client_id
        assert retrieved_info.task_id == task_id
        assert retrieved_info.user_agent == "test-browser"

class TestEventBus:
    """Test suite for EventBus"""
    
    @pytest.mark.asyncio
    async def test_subscribe_and_emit_global_handler(self, clean_event_bus):
        """Test subscribing to events and receiving them"""
        bus = clean_event_bus
        received_messages = []
        
        async def test_handler(message):
            received_messages.append(message)
        
        # Subscribe to event
        bus.subscribe(WebSocketEventType.TASK_UPDATED, test_handler)
        
        # Emit event
        message = WebSocketMessage(
            event_type=WebSocketEventType.TASK_UPDATED,
            task_id="test_task",
            data={"status": "updated"}
        )
        await bus.emit(message)
        
        # Verify handler was called
        assert len(received_messages) == 1
        assert received_messages[0].event_type == WebSocketEventType.TASK_UPDATED
    
    @pytest.mark.asyncio
    async def test_subscribe_task_specific_handler(self, clean_event_bus):
        """Test task-specific event handlers"""
        bus = clean_event_bus
        received_messages = []
        
        async def task_handler(message):
            received_messages.append(message)
        
        # Subscribe to specific task events
        task_id = "specific_task"
        bus.subscribe(WebSocketEventType.TASK_UPDATED, task_handler, task_id)
        
        # Emit event for the specific task
        message1 = WebSocketMessage(
            event_type=WebSocketEventType.TASK_UPDATED,
            task_id=task_id,
            data={"status": "updated"}
        )
        await bus.emit(message1)
        
        # Emit event for different task
        message2 = WebSocketMessage(
            event_type=WebSocketEventType.TASK_UPDATED,
            task_id="other_task",
            data={"status": "updated"}
        )
        await bus.emit(message2)
        
        # Verify only the specific task event was handled
        assert len(received_messages) == 1
        assert received_messages[0].task_id == task_id
    
    @pytest.mark.asyncio
    async def test_emit_task_event_convenience_method(self, clean_event_bus):
        """Test convenience method for emitting task events"""
        bus = clean_event_bus
        received_messages = []
        
        async def handler(message):
            received_messages.append(message)
        
        bus.subscribe(WebSocketEventType.PROGRESS_UPDATE, handler)
        
        # Use convenience method
        await bus.emit_progress_update(
            task_id="test_task",
            progress=0.5,
            message="Half done",
            confidence=0.8
        )
        
        # Verify event was emitted correctly
        assert len(received_messages) == 1
        message = received_messages[0]
        assert message.event_type == WebSocketEventType.PROGRESS_UPDATE
        assert message.task_id == "test_task"
        assert message.data["progress"] == 0.5
        assert message.data["message"] == "Half done"
        assert message.data["confidence"] == 0.8
    
    @pytest.mark.asyncio
    async def test_emit_agent_status_change(self, clean_event_bus):
        """Test agent status change convenience method"""
        bus = clean_event_bus
        received_messages = []
        
        async def handler(message):
            received_messages.append(message)
        
        bus.subscribe(WebSocketEventType.AGENT_STATUS_CHANGE, handler)
        
        await bus.emit_agent_status_change(
            agent_id="agent_001",
            status="working",
            task_id="test_task",
            data={"confidence": 0.9}
        )
        
        assert len(received_messages) == 1
        message = received_messages[0]
        assert message.data["agent_id"] == "agent_001"
        assert message.data["status"] == "working"
        assert message.data["confidence"] == 0.9
    
    @pytest.mark.asyncio
    async def test_emit_tool_call_events(self, clean_event_bus):
        """Test tool call event convenience methods"""
        bus = clean_event_bus
        received_messages = []
        
        async def handler(message):
            received_messages.append(message)
        
        bus.subscribe(WebSocketEventType.TOOL_CALL_START, handler)
        bus.subscribe(WebSocketEventType.TOOL_CALL_END, handler)
        
        # Tool call start
        await bus.emit_tool_call(
            task_id="test_task",
            tool_name="web_scraper",
            args={"url": "https://example.com"}
        )
        
        # Tool call end
        await bus.emit_tool_call(
            task_id="test_task",
            tool_name="web_scraper",
            args={"url": "https://example.com"},
            result={"status": "success", "data": "scraped_data"}
        )
        
        assert len(received_messages) == 2
        assert received_messages[0].event_type == WebSocketEventType.TOOL_CALL_START
        assert received_messages[1].event_type == WebSocketEventType.TOOL_CALL_END
        assert received_messages[1].data["result"]["status"] == "success"
    
    def test_unsubscribe_handler(self, clean_event_bus):
        """Test unsubscribing event handlers"""
        bus = clean_event_bus
        
        async def handler(message):
            pass
        
        # Subscribe and verify
        bus.subscribe(WebSocketEventType.TASK_UPDATED, handler)
        assert len(bus.handlers[WebSocketEventType.TASK_UPDATED]) == 1
        
        # Unsubscribe and verify
        bus.unsubscribe(WebSocketEventType.TASK_UPDATED, handler)
        assert len(bus.handlers[WebSocketEventType.TASK_UPDATED]) == 0
    
    def test_event_history_tracking(self, clean_event_bus):
        """Test that event history is properly tracked"""
        bus = clean_event_bus
        
        # Emit several events
        for i in range(5):
            message = WebSocketMessage(
                event_type=WebSocketEventType.TASK_UPDATED,
                task_id=f"task_{i}",
                data={"iteration": i}
            )
            asyncio.run(bus.emit(message))
        
        # Check history
        history = bus.get_event_history()
        assert len(history) == 5
        
        # Check filtering by task
        task_history = bus.get_event_history(task_id="task_2")
        assert len(task_history) == 1
        assert task_history[0].task_id == "task_2"
        
        # Check filtering by event type
        type_history = bus.get_event_history(event_type=WebSocketEventType.TASK_UPDATED)
        assert len(type_history) == 5
    
    def test_get_stats(self, clean_event_bus):
        """Test getting event bus statistics"""
        bus = clean_event_bus
        
        async def handler1(message):
            pass
        
        async def handler2(message):
            pass
        
        # Add some handlers
        bus.subscribe(WebSocketEventType.TASK_UPDATED, handler1)
        bus.subscribe(WebSocketEventType.TASK_COMPLETED, handler2)
        bus.subscribe(WebSocketEventType.TASK_UPDATED, handler1, "task_123")
        
        stats = bus.get_stats()
        
        assert stats["total_handlers"] == 2  # Global handlers
        assert stats["task_handlers"] == 1   # Task-specific handlers
        assert WebSocketEventType.TASK_UPDATED in stats["handler_types"]
        assert WebSocketEventType.TASK_COMPLETED in stats["handler_types"]

@pytest.mark.asyncio
async def test_websocket_integration():
    """Integration test for WebSocket functionality with FastAPI"""
    # Note: This would require a test client that supports WebSocket connections
    # For now, we'll test the components in isolation
    
    # Test that the endpoint exists and is properly configured
    from backend.main import app
    
    # Verify the WebSocket route is registered
    websocket_routes = [route for route in app.routes if hasattr(route, 'path') and route.path == "/ws/tasks/{task_id}"]
    assert len(websocket_routes) == 1
    
    # Verify the status endpoint exists
    with TestClient(app) as client:
        response = client.get("/api/v1/websocket/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "total_connections" in data
        assert "event_bus_stats" in data

if __name__ == "__main__":
    pytest.main([__file__, "-v"])