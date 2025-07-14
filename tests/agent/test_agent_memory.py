"""Tests for agent memory persistence using TinyDB."""
import pytest
import tempfile
import asyncio
from datetime import datetime
from pathlib import Path
from agent.memory import (
    AgentMemory, CrawlState, VisitedURL, ExtractedData, AgentSession
)


class TestAgentMemory:
    """Test AgentMemory class functionality."""
    
    @pytest.fixture
    def temp_memory(self):
        """Create temporary AgentMemory instance for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            memory = AgentMemory(memory_dir=temp_dir)
            yield memory
            memory.close()
    
    @pytest.mark.asyncio
    async def test_crawl_state_operations(self, temp_memory):
        """Test saving and loading crawl state."""
        # Create test crawl state
        crawl_state = CrawlState(
            session_id="test-session-001",
            task_id="test-task-001",
            start_time=datetime.now(),
            current_url="https://example.com",
            urls_to_visit=["https://example.com/page1", "https://example.com/page2"],
            urls_visited=["https://example.com"],
            crawl_depth=1,
            status="active"
        )
        
        # Save crawl state
        success = await temp_memory.save_crawl_state(crawl_state)
        assert success, "Failed to save crawl state"
        
        # Load crawl state
        loaded_state = await temp_memory.load_crawl_state("test-session-001")
        assert loaded_state is not None, "Failed to load crawl state"
        assert loaded_state.session_id == crawl_state.session_id
        assert loaded_state.task_id == crawl_state.task_id
        assert loaded_state.current_url == crawl_state.current_url
        assert loaded_state.urls_to_visit == crawl_state.urls_to_visit
        assert loaded_state.crawl_depth == crawl_state.crawl_depth
        assert loaded_state.status == crawl_state.status
    
    @pytest.mark.asyncio
    async def test_visited_url_operations(self, temp_memory):
        """Test saving and retrieving visited URLs."""
        # Create test visited URL
        visited_url = VisitedURL(
            url="https://example.com/test",
            visited_at=datetime.now(),
            session_id="test-session-001",
            response_status=200,
            content_type="text/html",
            content_length=1024,
            extraction_successful=True
        )
        
        # Save visited URL
        success = await temp_memory.save_visited_url(visited_url)
        assert success, "Failed to save visited URL"
        
        # Get visited URLs for session
        visited_urls = await temp_memory.get_visited_urls("test-session-001")
        assert len(visited_urls) == 1, "Incorrect number of visited URLs"
        assert visited_urls[0] == "https://example.com/test"
        
        # Get specific URL info
        url_info = await temp_memory.get_url_info(
            "https://example.com/test", 
            "test-session-001"
        )
        assert url_info is not None, "Failed to get URL info"
        assert url_info.response_status == 200
        assert url_info.content_type == "text/html"
        assert url_info.extraction_successful is True
    
    @pytest.mark.asyncio
    async def test_extracted_data_operations(self, temp_memory):
        """Test saving and retrieving extracted data."""
        # Create test extracted data
        extracted_data = ExtractedData(
            id="extract-001",
            url="https://example.com/test",
            session_id="test-session-001",
            extraction_type="text",
            data={"title": "Test Page", "content": "Sample content"},
            extracted_at=datetime.now(),
            confidence_score=0.95,
            selectors_used=["h1", "p"],
            processing_time_ms=250
        )
        
        # Save extracted data
        success = await temp_memory.save_extracted_data(extracted_data)
        assert success, "Failed to save extracted data"
        
        # Get extracted data for session
        data_list = await temp_memory.get_extracted_data("test-session-001")
        assert len(data_list) == 1, "Incorrect number of extracted data items"
        
        data_item = data_list[0]
        assert data_item.id == "extract-001"
        assert data_item.extraction_type == "text"
        assert data_item.data["title"] == "Test Page"
        assert data_item.confidence_score == 0.95
        assert data_item.processing_time_ms == 250
        
        # Test filtering by extraction type
        filtered_data = await temp_memory.get_extracted_data(
            "test-session-001", 
            extraction_type="text"
        )
        assert len(filtered_data) == 1, "Filtering by extraction type failed"
    
    @pytest.mark.asyncio
    async def test_session_operations(self, temp_memory):
        """Test saving and retrieving agent sessions."""
        # Create test session
        session = AgentSession(
            session_id="test-session-001",
            task_id="test-task-001",
            agent_type="web_crawler",
            start_time=datetime.now(),
            status="active",
            config={"max_depth": 3, "delay": 1.0},
            metrics={"urls_processed": 5, "extraction_rate": 0.8},
            total_urls_processed=5,
            total_data_extracted=3,
            total_errors=1
        )
        
        # Save session
        success = await temp_memory.save_session(session)
        assert success, "Failed to save session"
        
        # Get session
        loaded_session = await temp_memory.get_session("test-session-001")
        assert loaded_session is not None, "Failed to load session"
        assert loaded_session.session_id == session.session_id
        assert loaded_session.task_id == session.task_id
        assert loaded_session.agent_type == session.agent_type
        assert loaded_session.status == session.status
        assert loaded_session.config == session.config
        assert loaded_session.total_urls_processed == 5
        
        # Get active sessions
        active_sessions = await temp_memory.get_active_sessions()
        assert len(active_sessions) == 1, "Incorrect number of active sessions"
        assert active_sessions[0].session_id == "test-session-001"
    
    @pytest.mark.asyncio
    async def test_memory_stats(self, temp_memory):
        """Test memory statistics functionality."""
        # Add some test data
        crawl_state = CrawlState(
            session_id="stats-test",
            task_id="stats-task",
            start_time=datetime.now()
        )
        await temp_memory.save_crawl_state(crawl_state)
        
        visited_url = VisitedURL(
            url="https://stats.example.com",
            visited_at=datetime.now(),
            session_id="stats-test",
            response_status=200
        )
        await temp_memory.save_visited_url(visited_url)
        
        # Get memory stats
        stats = await temp_memory.get_memory_stats()
        
        assert "crawl_states" in stats, "Missing crawl_states in stats"
        assert "visited_urls" in stats, "Missing visited_urls in stats"
        assert "extracted_data" in stats, "Missing extracted_data in stats"
        assert "sessions" in stats, "Missing sessions in stats"
        assert "memory_dir" in stats, "Missing memory_dir in stats"
        assert "db_files" in stats, "Missing db_files in stats"
        
        # Check that we have some data
        assert stats["crawl_states"] >= 1, "No crawl states recorded"
        assert stats["visited_urls"] >= 1, "No visited URLs recorded"
        assert len(stats["db_files"]) > 0, "No database files found"
    
    @pytest.mark.asyncio
    async def test_data_export(self, temp_memory):
        """Test data export functionality."""
        # Add test data
        session = AgentSession(
            session_id="export-test",
            task_id="export-task",
            start_time=datetime.now()
        )
        await temp_memory.save_session(session)
        
        crawl_state = CrawlState(
            session_id="export-test",
            task_id="export-task",
            start_time=datetime.now()
        )
        await temp_memory.save_crawl_state(crawl_state)
        
        with tempfile.TemporaryDirectory() as export_dir:
            # Export data
            success = await temp_memory.export_data(export_dir, session_id="export-test")
            assert success, "Failed to export data"
            
            # Check exported files
            export_path = Path(export_dir)
            expected_files = [
                "crawl_states.json",
                "visited_urls.json", 
                "extracted_data.json",
                "sessions.json"
            ]
            
            for filename in expected_files:
                file_path = export_path / filename
                assert file_path.exists(), f"Export file {filename} not created"
                assert file_path.stat().st_size > 0, f"Export file {filename} is empty"
    
    @pytest.mark.asyncio
    async def test_nonexistent_data_retrieval(self, temp_memory):
        """Test retrieving non-existent data returns appropriate defaults."""
        # Test loading non-existent crawl state
        crawl_state = await temp_memory.load_crawl_state("nonexistent-session")
        assert crawl_state is None, "Should return None for non-existent crawl state"
        
        # Test getting URLs for non-existent session
        visited_urls = await temp_memory.get_visited_urls("nonexistent-session")
        assert visited_urls == [], "Should return empty list for non-existent session"
        
        # Test getting non-existent URL info
        url_info = await temp_memory.get_url_info("https://nonexistent.com", "nonexistent")
        assert url_info is None, "Should return None for non-existent URL info"
        
        # Test getting data for non-existent session
        extracted_data = await temp_memory.get_extracted_data("nonexistent-session")
        assert extracted_data == [], "Should return empty list for non-existent session"
        
        # Test getting non-existent session
        session = await temp_memory.get_session("nonexistent-session")
        assert session is None, "Should return None for non-existent session"
    
    @pytest.mark.asyncio
    async def test_update_operations(self, temp_memory):
        """Test update operations for existing data."""
        # Create and save initial crawl state
        initial_state = CrawlState(
            session_id="update-test",
            task_id="update-task",
            start_time=datetime.now(),
            status="active",
            crawl_depth=1
        )
        await temp_memory.save_crawl_state(initial_state)
        
        # Update the crawl state
        updated_state = CrawlState(
            session_id="update-test",
            task_id="update-task", 
            start_time=initial_state.start_time,
            status="completed",
            crawl_depth=3,
            urls_visited=["https://example.com", "https://example.com/page1"]
        )
        await temp_memory.save_crawl_state(updated_state)
        
        # Load and verify the update
        loaded_state = await temp_memory.load_crawl_state("update-test")
        assert loaded_state is not None, "Failed to load updated state"
        assert loaded_state.status == "completed", "Status not updated"
        assert loaded_state.crawl_depth == 3, "Crawl depth not updated"
        assert len(loaded_state.urls_visited) == 2, "URLs visited not updated"
    
    @pytest.mark.asyncio
    async def test_multiple_sessions(self, temp_memory):
        """Test handling multiple concurrent sessions."""
        sessions_data = [
            ("session-1", "task-1", "active"),
            ("session-2", "task-2", "completed"),
            ("session-3", "task-3", "active")
        ]
        
        # Create multiple sessions
        for session_id, task_id, status in sessions_data:
            session = AgentSession(
                session_id=session_id,
                task_id=task_id,
                start_time=datetime.now(),
                status=status
            )
            await temp_memory.save_session(session)
        
        # Test getting all active sessions
        active_sessions = await temp_memory.get_active_sessions()
        assert len(active_sessions) == 2, "Incorrect number of active sessions"
        
        active_ids = {session.session_id for session in active_sessions}
        assert "session-1" in active_ids, "session-1 should be active"
        assert "session-3" in active_ids, "session-3 should be active"
        assert "session-2" not in active_ids, "session-2 should not be active"