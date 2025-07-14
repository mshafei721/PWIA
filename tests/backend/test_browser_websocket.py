"""Tests for browser automation WebSocket communication."""
import asyncio
import json
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from backend.websocket_manager import ConnectionManager
from backend.event_bus import EventBus
from backend.models import (
    WebSocketMessage, WebSocketEventType, BrowserStatus, CrawlProgress,
    ExtractionResult, BrowserSession, BrowserPerformanceMetrics,
    BrowserWebSocketEvent, BrowserErrorEvent
)


@pytest.fixture
def connection_manager():
    """Create test connection manager."""
    return ConnectionManager(max_message_queue_size=50)


@pytest.fixture
def event_bus():
    """Create test event bus."""
    return EventBus()


@pytest.fixture
def mock_websocket():
    """Create mock WebSocket connection."""
    websocket = Mock()
    websocket.accept = AsyncMock()
    websocket.send_text = AsyncMock()
    websocket.headers = {"user-agent": "test-client"}
    return websocket


@pytest.fixture
def sample_crawl_progress():
    """Create sample crawl progress data."""
    return CrawlProgress(
        session_id="test-session-123",
        task_id="test-task-123",
        status=BrowserStatus.CRAWLING,
        urls_total=10,
        urls_processed=5,
        pages_crawled=4,
        current_url="https://example.com/page5",
        crawl_depth=2,
        completion_percentage=50.0
    )


@pytest.fixture
def sample_extraction_result():
    """Create sample extraction result."""
    return ExtractionResult(
        url="https://example.com/product",
        extracted_data={"title": "Product Name", "price": "$29.99"},
        timestamp=datetime.now(timezone.utc),
        confidence_score=0.85,
        extraction_method="css_selector",
        page_title="Product Page"
    )


@pytest.fixture
def sample_browser_session():
    """Create sample browser session."""
    return BrowserSession(
        session_id="test-session-123",
        task_id="test-task-123",
        status=BrowserStatus.CRAWLING,
        initial_urls=["https://example.com"],
        crawl_config={"headless": True, "timeout": 30}
    )


class TestConnectionManagerBrowserEvents:
    """Test browser automation events in ConnectionManager."""
    
    @pytest.mark.asyncio
    async def test_connect_and_browser_status_update(self, connection_manager, mock_websocket):
        """Test connecting and sending browser status updates."""
        task_id = "test-task-123"
        
        # Connect client
        client_id = await connection_manager.connect(mock_websocket, task_id)
        
        # Verify connection
        assert client_id in connection_manager.websockets
        assert client_id in connection_manager.active_connections[task_id]
        
        # Send browser status update
        await connection_manager.send_browser_status_update(
            task_id, BrowserStatus.CRAWLING, "session-123", "Started crawling"
        )
        
        # Verify WebSocket send was called
        mock_websocket.send_text.assert_called()
        
        # Get the last call and verify message structure
        last_call_args = mock_websocket.send_text.call_args_list[-1][0]
        message_data = json.loads(last_call_args[0])
        
        assert message_data["event_type"] == WebSocketEventType.TASK_UPDATED
        assert message_data["task_id"] == task_id
        assert message_data["data"]["browser_status"] == "crawling"
        assert message_data["data"]["session_id"] == "session-123"
        assert message_data["data"]["message"] == "Started crawling"
    
    @pytest.mark.asyncio
    async def test_send_crawl_progress_update(self, connection_manager, mock_websocket, sample_crawl_progress):
        """Test sending crawl progress updates."""
        task_id = "test-task-123"
        client_id = await connection_manager.connect(mock_websocket, task_id)
        
        
        await connection_manager.send_crawl_progress_update(task_id, sample_crawl_progress)
        
        # Verify message was sent
        mock_websocket.send_text.assert_called()
        
        # Check message content (skip the connection message, get the progress message)
        progress_call = None
        for call in mock_websocket.send_text.call_args_list:
            message_json = call[0][0]
            message_data_temp = json.loads(message_json)
            if message_data_temp.get("event_type") == WebSocketEventType.PROGRESS_UPDATE:
                progress_call = call
                break
        
        assert progress_call is not None, "Progress update message not found"
        message_data = json.loads(progress_call[0][0])
        
        assert message_data["event_type"] == WebSocketEventType.PROGRESS_UPDATE
        assert message_data["data"]["type"] == "crawl_progress"
        assert message_data["data"]["progress"]["completion_percentage"] == 50.0
        assert message_data["data"]["progress"]["pages_crawled"] == 4
    
    @pytest.mark.asyncio
    async def test_send_extraction_result(self, connection_manager, mock_websocket, sample_extraction_result):
        """Test sending extraction results."""
        task_id = "test-task-123"
        client_id = await connection_manager.connect(mock_websocket, task_id)
        
        await connection_manager.send_extraction_result(task_id, sample_extraction_result)
        
        # Verify message was sent
        mock_websocket.send_text.assert_called()
        
        # Check message content
        last_call_args = mock_websocket.send_text.call_args_list[-1][0]
        message_data = json.loads(last_call_args[0])
        
        assert message_data["event_type"] == WebSocketEventType.TASK_UPDATED
        assert message_data["data"]["type"] == "extraction_result"
        assert message_data["data"]["extraction"]["url"] == "https://example.com/product"
        assert message_data["data"]["extraction"]["confidence_score"] == 0.85
    
    @pytest.mark.asyncio
    async def test_send_browser_session_update(self, connection_manager, mock_websocket, sample_browser_session):
        """Test sending browser session updates."""
        task_id = "test-task-123"
        client_id = await connection_manager.connect(mock_websocket, task_id)
        
        await connection_manager.send_browser_session_update(task_id, sample_browser_session)
        
        # Verify message was sent
        mock_websocket.send_text.assert_called()
        
        # Check message content
        last_call_args = mock_websocket.send_text.call_args_list[-1][0]
        message_data = json.loads(last_call_args[0])
        
        assert message_data["event_type"] == WebSocketEventType.TASK_UPDATED
        assert message_data["data"]["type"] == "browser_session"
        assert message_data["data"]["session"]["session_id"] == "test-session-123"
        assert message_data["data"]["session"]["status"] == "crawling"
    
    @pytest.mark.asyncio
    async def test_send_performance_metrics(self, connection_manager, mock_websocket):
        """Test sending performance metrics."""
        task_id = "test-task-123"
        client_id = await connection_manager.connect(mock_websocket, task_id)
        
        metrics = BrowserPerformanceMetrics(
            session_id="test-session-123",
            timestamp=datetime.now(timezone.utc),
            cpu_usage=45.5,
            memory_usage=512.0,
            network_requests=150,
            pages_per_minute=12.5
        )
        
        await connection_manager.send_performance_metrics(task_id, metrics)
        
        # Verify message was sent
        mock_websocket.send_text.assert_called()
        
        # Check message content
        last_call_args = mock_websocket.send_text.call_args_list[-1][0]
        message_data = json.loads(last_call_args[0])
        
        assert message_data["event_type"] == WebSocketEventType.TASK_UPDATED
        assert message_data["data"]["type"] == "performance_metrics"
        assert message_data["data"]["metrics"]["cpu_usage"] == 45.5
        assert message_data["data"]["metrics"]["memory_usage"] == 512.0
    
    @pytest.mark.asyncio
    async def test_send_browser_event(self, connection_manager, mock_websocket):
        """Test sending generic browser events."""
        task_id = "test-task-123"
        client_id = await connection_manager.connect(mock_websocket, task_id)
        
        event = BrowserWebSocketEvent(
            event_type="page.loaded",
            session_id="test-session-123",
            task_id=task_id,
            data={"url": "https://example.com", "load_time": 1.23}
        )
        
        await connection_manager.send_browser_event(task_id, event)
        
        # Verify message was sent
        mock_websocket.send_text.assert_called()
        
        # Check message content
        last_call_args = mock_websocket.send_text.call_args_list[-1][0]
        message_data = json.loads(last_call_args[0])
        
        assert message_data["event_type"] == WebSocketEventType.TASK_UPDATED
        assert message_data["data"]["type"] == "browser_event"
        assert message_data["data"]["event"]["event_type"] == "page.loaded"
        assert message_data["data"]["event"]["data"]["url"] == "https://example.com"
    
    @pytest.mark.asyncio
    async def test_send_browser_error(self, connection_manager, mock_websocket):
        """Test sending browser errors."""
        task_id = "test-task-123"
        client_id = await connection_manager.connect(mock_websocket, task_id)
        
        error = BrowserErrorEvent(
            session_id="test-session-123",
            task_id=task_id,
            error_type="page_load_timeout",
            error_message="Page failed to load within timeout",
            url="https://slow-site.com",
            timestamp=datetime.now(timezone.utc)
        )
        
        await connection_manager.send_browser_error(task_id, error)
        
        # Verify message was sent
        mock_websocket.send_text.assert_called()
        
        # Check message content
        last_call_args = mock_websocket.send_text.call_args_list[-1][0]
        message_data = json.loads(last_call_args[0])
        
        assert message_data["event_type"] == WebSocketEventType.TASK_FAILED
        assert message_data["data"]["type"] == "browser_error"
        assert message_data["data"]["error"]["error_type"] == "page_load_timeout"
        assert message_data["data"]["error"]["error_message"] == "Page failed to load within timeout"
        assert message_data["data"]["error"]["url"] == "https://slow-site.com"
    
    @pytest.mark.asyncio
    async def test_page_load_events(self, connection_manager, mock_websocket):
        """Test sending page load events."""
        task_id = "test-task-123"
        client_id = await connection_manager.connect(mock_websocket, task_id)
        
        # Test successful page load
        await connection_manager.send_page_load_event(
            task_id, "https://example.com", True, 1.23
        )
        
        # Test failed page load
        await connection_manager.send_page_load_event(
            task_id, "https://broken-site.com", False, None, "Connection timeout"
        )
        
        # Should have sent 2 messages (plus connection message)
        assert mock_websocket.send_text.call_count >= 3
    
    @pytest.mark.asyncio
    async def test_data_extraction_events(self, connection_manager, mock_websocket):
        """Test sending data extraction events."""
        task_id = "test-task-123"
        client_id = await connection_manager.connect(mock_websocket, task_id)
        
        await connection_manager.send_data_extraction_event(
            task_id, "https://example.com/product", 5, 88.5
        )
        
        # Verify message was sent
        mock_websocket.send_text.assert_called()
        
        # Check the browser event was created correctly
        last_call_args = mock_websocket.send_text.call_args_list[-1][0]
        message_data = json.loads(last_call_args[0])
        
        event_data = message_data["data"]["event"]["data"]
        assert event_data["url"] == "https://example.com/product"
        assert event_data["fields_extracted"] == 5
        assert event_data["confidence_score"] == 88.5
    
    @pytest.mark.asyncio
    async def test_crawl_lifecycle_events(self, connection_manager, mock_websocket):
        """Test complete crawl lifecycle events."""
        task_id = "test-task-123"
        client_id = await connection_manager.connect(mock_websocket, task_id)
        
        # Start crawl
        await connection_manager.send_crawl_started_event(
            task_id, ["https://example.com", "https://test.com"], 2, 10
        )
        
        # Complete crawl
        await connection_manager.send_crawl_completed_event(
            task_id, 8, 15, 45.5
        )
        
        # Should have sent multiple messages
        assert mock_websocket.send_text.call_count >= 3
        
        # Check completed event
        last_call_args = mock_websocket.send_text.call_args_list[-1][0]
        message_data = json.loads(last_call_args[0])
        
        event_data = message_data["data"]["event"]["data"]
        assert event_data["pages_crawled"] == 8
        assert event_data["data_extracted"] == 15
        assert event_data["duration_seconds"] == 45.5
    
    def test_get_browser_connection_stats(self, connection_manager):
        """Test getting browser connection statistics."""
        stats = connection_manager.get_browser_connection_stats()
        
        assert "total_connections" in stats
        assert "active_tasks" in stats
        assert "browser_connections" in stats
        assert "message_queues" in stats
        
        # All values should be integers
        assert isinstance(stats["total_connections"], int)
        assert isinstance(stats["active_tasks"], int)
        assert isinstance(stats["browser_connections"], int)


class TestEventBusBrowserEvents:
    """Test browser automation events in EventBus."""
    
    @pytest.mark.asyncio
    async def test_emit_browser_status_change(self, event_bus):
        """Test emitting browser status changes."""
        task_id = "test-task-123"
        
        # Mock the connection manager
        with patch('backend.event_bus.connection_manager') as mock_cm:
            mock_cm.send_browser_status_update = AsyncMock()
            
            await event_bus.emit_browser_status_change(
                task_id, BrowserStatus.CRAWLING, "session-123", "Starting crawl"
            )
            
            # Verify connection manager was called
            mock_cm.send_browser_status_update.assert_called_once_with(
                task_id, BrowserStatus.CRAWLING, "session-123", "Starting crawl"
            )
            
            # Check event was added to history
            assert len(event_bus.event_history) == 1
            event = event_bus.event_history[0]
            assert event.task_id == task_id
            assert event.data["type"] == "browser_status"
            assert event.data["browser_status"] == "crawling"
    
    @pytest.mark.asyncio
    async def test_emit_crawl_progress(self, event_bus, sample_crawl_progress):
        """Test emitting crawl progress."""
        task_id = "test-task-123"
        
        with patch('backend.event_bus.connection_manager') as mock_cm:
            mock_cm.send_crawl_progress_update = AsyncMock()
            
            await event_bus.emit_crawl_progress(task_id, sample_crawl_progress)
            
            # Verify connection manager was called
            mock_cm.send_crawl_progress_update.assert_called_once_with(
                task_id, sample_crawl_progress
            )
            
            # Check event was added to history
            assert len(event_bus.event_history) == 1
            event = event_bus.event_history[0]
            assert event.data["type"] == "crawl_progress"
    
    @pytest.mark.asyncio
    async def test_emit_extraction_result(self, event_bus, sample_extraction_result):
        """Test emitting extraction results."""
        task_id = "test-task-123"
        
        with patch('backend.event_bus.connection_manager') as mock_cm:
            mock_cm.send_extraction_result = AsyncMock()
            
            await event_bus.emit_extraction_result(task_id, sample_extraction_result)
            
            # Verify connection manager was called
            mock_cm.send_extraction_result.assert_called_once_with(
                task_id, sample_extraction_result
            )
            
            # Check event was added to history
            assert len(event_bus.event_history) == 1
            event = event_bus.event_history[0]
            assert event.event_type == WebSocketEventType.TASK_UPDATED
    
    @pytest.mark.asyncio
    async def test_emit_page_loaded(self, event_bus):
        """Test emitting page loaded events."""
        task_id = "test-task-123"
        
        with patch('backend.event_bus.connection_manager') as mock_cm:
            mock_cm.send_browser_event = AsyncMock()
            
            await event_bus.emit_page_loaded(
                task_id, "https://example.com", True, 1.23
            )
            
            # Verify connection manager was called
            mock_cm.send_browser_event.assert_called_once()
            
            # Check the event structure
            call_args = mock_cm.send_browser_event.call_args[0]
            assert call_args[0] == task_id
            browser_event = call_args[1]
            assert browser_event.event_type == "page.loaded"
            assert browser_event.data["url"] == "https://example.com"
            assert browser_event.data["success"] == True
            assert browser_event.data["load_time"] == 1.23
    
    @pytest.mark.asyncio
    async def test_emit_data_extracted(self, event_bus):
        """Test emitting data extracted events."""
        task_id = "test-task-123"
        
        with patch('backend.event_bus.connection_manager') as mock_cm:
            mock_cm.send_browser_event = AsyncMock()
            
            extracted_data = {"title": "Test Product", "price": "$19.99"}
            
            await event_bus.emit_data_extracted(
                task_id, "https://example.com/product", 2, 92.5, extracted_data
            )
            
            # Verify connection manager was called
            mock_cm.send_browser_event.assert_called_once()
            
            # Check the event structure
            call_args = mock_cm.send_browser_event.call_args[0]
            browser_event = call_args[1]
            assert browser_event.event_type == "data.extracted"
            assert browser_event.data["fields_extracted"] == 2
            assert browser_event.data["confidence_score"] == 92.5
            assert browser_event.data["extracted_data"] == extracted_data
    
    @pytest.mark.asyncio
    async def test_emit_crawl_lifecycle(self, event_bus):
        """Test emitting complete crawl lifecycle."""
        task_id = "test-task-123"
        
        with patch('backend.event_bus.connection_manager') as mock_cm:
            mock_cm.send_browser_status_update = AsyncMock()
            mock_cm.send_browser_event = AsyncMock()
            
            # Start crawl
            urls = ["https://example.com", "https://test.com"]
            await event_bus.emit_crawl_started(task_id, urls, 2, 10)
            
            # Complete crawl  
            await event_bus.emit_crawl_completed(task_id, 8, 15, 45.5)
            
            # Should have called status updates
            assert mock_cm.send_browser_status_update.call_count == 2
            
            # Check status changes
            status_calls = mock_cm.send_browser_status_update.call_args_list
            assert status_calls[0][0][1] == BrowserStatus.CRAWLING  # Start
            assert status_calls[1][0][1] == BrowserStatus.COMPLETED  # Complete
            
            # Should have called browser events
            assert mock_cm.send_browser_event.call_count == 2
    
    @pytest.mark.asyncio
    async def test_emit_browser_launched_closed(self, event_bus):
        """Test emitting browser launched and closed events."""
        task_id = "test-task-123"
        session_id = "session-123"
        
        with patch('backend.event_bus.connection_manager') as mock_cm:
            mock_cm.send_browser_status_update = AsyncMock()
            mock_cm.send_browser_event = AsyncMock()
            
            # Launch browser
            await event_bus.emit_browser_launched(task_id, session_id, "chromium")
            
            # Close browser
            await event_bus.emit_browser_closed(task_id, session_id)
            
            # Should have called status updates
            assert mock_cm.send_browser_status_update.call_count == 2
            
            # Check status changes
            status_calls = mock_cm.send_browser_status_update.call_args_list
            assert status_calls[0][0][1] == BrowserStatus.LAUNCHING  # Launch
            assert status_calls[1][0][1] == BrowserStatus.IDLE  # Close
    
    @pytest.mark.asyncio
    async def test_browser_event_handlers(self, event_bus):
        """Test subscribing to browser events."""
        task_id = "test-task-123"
        received_events = []
        
        async def browser_event_handler(message):
            received_events.append(message)
        
        # Subscribe to task updates
        event_bus.subscribe(WebSocketEventType.TASK_UPDATED, browser_event_handler, task_id)
        
        with patch('backend.event_bus.connection_manager'):
            # Emit browser status change
            await event_bus.emit_browser_status_change(
                task_id, BrowserStatus.CRAWLING, message="Test message"
            )
        
        # Should have received the event
        assert len(received_events) == 1
        event = received_events[0]
        assert event.task_id == task_id
        assert event.data["type"] == "browser_status"
        assert event.data["browser_status"] == "crawling"
    
    def test_event_history_filtering(self, event_bus):
        """Test filtering event history."""
        # Add some mock events
        for i in range(5):
            message = WebSocketMessage(
                event_type=WebSocketEventType.TASK_UPDATED,
                task_id=f"task-{i}",
                data={"type": "browser_status", "status": "crawling"}
            )
            event_bus.event_history.append(message)
        
        # Test filtering by task_id
        task_events = event_bus.get_event_history(task_id="task-2")
        assert len(task_events) == 1
        assert task_events[0].task_id == "task-2"
        
        # Test filtering by event_type
        type_events = event_bus.get_event_history(event_type=WebSocketEventType.TASK_UPDATED)
        assert len(type_events) == 5
        
        # Test limit
        limited_events = event_bus.get_event_history(limit=3)
        assert len(limited_events) == 3


class TestIntegrationBrowserWebSocket:
    """Integration tests for browser automation WebSocket communication."""
    
    @pytest.mark.asyncio
    async def test_full_browser_workflow(self, connection_manager, event_bus, mock_websocket):
        """Test complete browser automation workflow with WebSocket updates."""
        task_id = "integration-test-123"
        
        # Connect client
        client_id = await connection_manager.connect(mock_websocket, task_id)
        
        with patch('backend.event_bus.connection_manager', connection_manager):
            # 1. Browser launched
            await event_bus.emit_browser_launched(task_id, "session-123", "chromium")
            
            # 2. Crawl started
            await event_bus.emit_crawl_started(task_id, ["https://example.com"], 1, 5)
            
            # 3. Page loaded
            await event_bus.emit_page_loaded(task_id, "https://example.com", True, 1.2)
            
            # 4. Data extracted
            await event_bus.emit_data_extracted(task_id, "https://example.com", 3, 85.0)
            
            # 5. Crawl completed
            await event_bus.emit_crawl_completed(task_id, 1, 1, 5.0)
            
            # 6. Browser closed
            await event_bus.emit_browser_closed(task_id, "session-123")
        
        # Should have sent multiple WebSocket messages
        assert mock_websocket.send_text.call_count >= 7  # 1 connection + 6 events
        
        # Check that all events were recorded in event bus
        assert len(event_bus.event_history) >= 6
        
        # Verify final status is idle
        final_events = [e for e in event_bus.event_history if e.data.get("type") == "browser_status"]
        final_status = final_events[-1].data["browser_status"]
        assert final_status == "idle"