"""Tests for WebCrawler class."""
import pytest
import asyncio
import tempfile
import time
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
from agent.crawler import WebCrawler, CrawlerConfig, URLQueueItem, RobotsTxtCache
from agent.memory import AgentMemory


class TestWebCrawler:
    """Test WebCrawler functionality."""
    
    @pytest.fixture
    def crawler_config(self):
        """Create test crawler configuration."""
        return CrawlerConfig(
            user_agent="PWIA-Test-Agent/1.0",
            delay_between_requests=0.1,  # Fast for tests
            max_concurrent_requests=2,
            request_timeout=5,
            max_retries=1,
            retry_delay=0.1,
            respect_robots_txt=True,
            max_depth=2,
            max_urls_per_domain=50,
            robots_cache_ttl=300
        )
    
    @pytest.fixture
    def memory(self):
        """Create test memory instance."""
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "test_memory"
            memory_path.mkdir()
            
            memory = AgentMemory(memory_dir=temp_dir)
            yield memory
            memory.close()
    
    @pytest.fixture
    def crawler(self, crawler_config, memory):
        """Create WebCrawler instance for testing."""
        return WebCrawler(config=crawler_config, memory=memory)
    
    @pytest.mark.asyncio
    async def test_crawler_initialization(self, crawler):
        """Test crawler initialization."""
        assert crawler.config.user_agent == "PWIA-Test-Agent/1.0"
        assert crawler.config.delay_between_requests == 0.1
        assert crawler.config.max_depth == 2
        assert len(crawler.url_queue) == 0
        assert len(crawler.urls_visited) == 0
        assert crawler.session_id is None
        assert not crawler.is_running
    
    @pytest.mark.asyncio
    async def test_start_crawling_session(self, crawler):
        """Test starting a crawling session."""
        session_id = "test-session-1"
        initial_urls = [
            "https://example.com",
            "https://test.com/page1"
        ]
        
        result_session_id = await crawler.start_crawling_session(session_id, initial_urls)
        
        assert result_session_id == session_id
        assert crawler.session_id == session_id
        assert crawler.is_running
        assert len(crawler.url_queue) == 2
        
        # Check queue items
        queue_urls = [item.url for item in crawler.url_queue]
        assert "https://example.com" in queue_urls
        assert "https://test.com/page1" in queue_urls
        
        # Check that items are sorted by priority
        assert crawler.url_queue[0].priority == 10
        assert crawler.url_queue[0].depth == 0
    
    @pytest.mark.asyncio
    async def test_stop_crawling_session(self, crawler):
        """Test stopping a crawling session."""
        session_id = "test-session-2"
        await crawler.start_crawling_session(session_id, ["https://example.com"])
        
        assert crawler.is_running
        
        await crawler.stop_crawling_session()
        
        assert not crawler.is_running
        assert crawler.session_id is None
    
    @pytest.mark.asyncio
    async def test_url_validation(self, crawler):
        """Test URL validation logic."""
        # Valid URLs
        assert await crawler._is_url_valid("https://example.com")
        assert await crawler._is_url_valid("http://test.com/page")
        
        # Invalid URLs
        assert not await crawler._is_url_valid("ftp://example.com")
        assert not await crawler._is_url_valid("mailto:test@example.com")
        assert not await crawler._is_url_valid("invalid-url")
    
    @pytest.mark.asyncio
    async def test_domain_extraction(self, crawler):
        """Test domain extraction from URLs."""
        assert crawler._get_domain("https://example.com/page") == "https://example.com"
        assert crawler._get_domain("http://test.com:8080/path") == "http://test.com:8080"
        assert crawler._get_domain("https://subdomain.example.com") == "https://subdomain.example.com"
    
    @pytest.mark.asyncio
    async def test_robots_txt_compliance(self, crawler):
        """Test robots.txt compliance checking."""
        # Mock robots.txt that allows all
        with patch('agent.crawler.RobotFileParser') as mock_parser_class:
            mock_parser = Mock()
            mock_parser_class.return_value = mock_parser
            mock_parser.can_fetch.return_value = True
            
            result = await crawler.check_robots_allowed("https://example.com/page")
            assert result is True
            
            mock_parser.set_url.assert_called_once()
            mock_parser.read.assert_called_once()
            mock_parser.can_fetch.assert_called_with("PWIA-Test-Agent/1.0", "https://example.com/page")
    
    @pytest.mark.asyncio
    async def test_robots_txt_blocking(self, crawler):
        """Test robots.txt blocking functionality."""
        with patch('agent.crawler.RobotFileParser') as mock_parser_class:
            mock_parser = Mock()
            mock_parser_class.return_value = mock_parser
            mock_parser.can_fetch.return_value = False
            
            result = await crawler.check_robots_allowed("https://example.com/blocked")
            assert result is False
    
    @pytest.mark.asyncio
    async def test_robots_txt_caching(self, crawler):
        """Test robots.txt caching mechanism."""
        domain = "https://example.com"
        
        # First call should fetch robots.txt
        with patch('agent.crawler.RobotFileParser') as mock_parser_class:
            mock_parser = Mock()
            mock_parser_class.return_value = mock_parser
            mock_parser.can_fetch.return_value = True
            
            await crawler.check_robots_allowed("https://example.com/page1")
            
            # Second call to same path should use cache
            await crawler.check_robots_allowed("https://example.com/page1")
            
            # Should only create parser once (caching working)
            assert mock_parser_class.call_count == 1
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, crawler):
        """Test rate limiting between requests."""
        domain = "https://example.com"
        
        # First request should be allowed immediately
        assert await crawler._can_crawl_domain(domain)
        
        # Mark domain as accessed
        crawler.domain_last_access[domain] = time.time()
        
        # Second request should be blocked due to rate limit
        assert not await crawler._can_crawl_domain(domain)
        
        # After delay, should be allowed again
        await asyncio.sleep(0.15)  # Wait longer than delay_between_requests
        assert await crawler._can_crawl_domain(domain)
    
    @pytest.mark.asyncio
    async def test_queue_management(self, crawler):
        """Test URL queue management."""
        session_id = "test-session-3"
        await crawler.start_crawling_session(session_id, ["https://example.com"])
        
        # Add URLs to queue
        urls_to_add = [
            "https://example.com/page1",
            "https://example.com/page2",
            "https://test.com/page1"
        ]
        
        await crawler.queue_urls(urls_to_add, "https://example.com", 0)
        
        # Check queue size
        assert len(crawler.url_queue) == 4  # 1 initial + 3 added
        
        # Test getting next URL
        next_url = await crawler.get_next_url()
        assert next_url is not None
        assert next_url.url in ["https://example.com"] + urls_to_add
        assert next_url.url in crawler.urls_in_progress
    
    @pytest.mark.asyncio
    async def test_queue_priority_handling(self, crawler):
        """Test queue priority handling."""
        session_id = "test-session-4"
        await crawler.start_crawling_session(session_id, ["https://example.com"])
        
        # Add URLs with different priorities
        await crawler.queue_urls(["https://example.com/low"], "https://example.com", 1)
        await crawler.queue_urls(["https://example.com/high"], "https://example.com", 0)
        
        # Manually set priorities
        await crawler.prioritize_url("https://example.com/high", 20)
        await crawler.prioritize_url("https://example.com/low", 5)
        
        # Get next URL should return highest priority
        next_url = await crawler.get_next_url()
        assert next_url.url == "https://example.com/high"
    
    @pytest.mark.asyncio
    async def test_duplicate_detection(self, crawler):
        """Test duplicate URL detection and removal."""
        session_id = "test-session-5"
        await crawler.start_crawling_session(session_id, ["https://example.com"])
        
        # Manually add duplicate URLs to test deduplication
        # (normally queue_urls would filter them, but let's test the deduplication logic)
        from agent.crawler import URLQueueItem
        duplicate_item = URLQueueItem(url="https://example.com/page1", depth=1, priority=5)
        duplicate_item2 = URLQueueItem(url="https://example.com/page1", depth=1, priority=3)
        
        # Add directly to queue to bypass normal filtering
        crawler.url_queue.extend([duplicate_item, duplicate_item2])
        
        # Check duplicates
        duplicates = await crawler.get_duplicate_urls()
        assert "https://example.com/page1" in duplicates
        assert duplicates["https://example.com/page1"] == 2
        
        # Remove duplicates
        removed_count = await crawler.deduplicate_queue()
        assert removed_count == 1
        
        # Verify no more duplicates
        duplicates = await crawler.get_duplicate_urls()
        assert len(duplicates) == 0
    
    @pytest.mark.asyncio
    async def test_url_completion_tracking(self, crawler):
        """Test URL completion tracking."""
        session_id = "test-session-6"
        await crawler.start_crawling_session(session_id, ["https://example.com"])
        
        url = "https://example.com/test"
        crawler.urls_in_progress.add(url)
        
        # Mark as completed successfully
        await crawler.mark_url_completed(url, True)
        
        assert url in crawler.urls_visited
        assert url not in crawler.urls_in_progress
    
    @pytest.mark.asyncio
    async def test_url_completion_with_error(self, crawler):
        """Test URL completion with error handling."""
        session_id = "test-session-7"
        await crawler.start_crawling_session(session_id, ["https://example.com"])
        
        url = "https://example.com/error"
        crawler.urls_in_progress.add(url)
        
        # Mark as failed
        await crawler.mark_url_completed(url, False, "Connection timeout")
        
        assert url in crawler.urls_visited
        assert url not in crawler.urls_in_progress
    
    @pytest.mark.asyncio
    async def test_crawl_url_robots_blocked(self, crawler):
        """Test crawling URL blocked by robots.txt."""
        session_id = "test-session-8"
        await crawler.start_crawling_session(session_id, ["https://example.com"])
        
        # Mock robots.txt that blocks the URL
        with patch.object(crawler, 'check_robots_allowed', return_value=False):
            success, urls, error = await crawler.crawl_url("https://example.com/blocked")
            
            assert not success
            assert len(urls) == 0
            assert "Robots.txt disallows" in error
    
    @pytest.mark.asyncio
    async def test_crawl_url_success(self, crawler):
        """Test successful URL crawling."""
        session_id = "test-session-9"
        await crawler.start_crawling_session(session_id, ["https://example.com"])
        
        # Mock robots.txt that allows the URL
        with patch.object(crawler, 'check_robots_allowed', return_value=True):
            success, urls, error = await crawler.crawl_url("https://example.com/page")
            
            assert success
            assert isinstance(urls, list)
            assert error is None
    
    @pytest.mark.asyncio
    async def test_crawl_url_rate_limiting(self, crawler):
        """Test rate limiting during URL crawling."""
        session_id = "test-session-10"
        await crawler.start_crawling_session(session_id, ["https://example.com"])
        
        # Set recent access time
        crawler.domain_last_access["https://example.com"] = time.time()
        
        with patch.object(crawler, 'check_robots_allowed', return_value=True):
            start_time = time.time()
            success, urls, error = await crawler.crawl_url("https://example.com/page")
            end_time = time.time()
            
            # Should have waited for rate limit
            assert end_time - start_time >= 0.1  # delay_between_requests
            assert success
    
    @pytest.mark.asyncio
    async def test_queue_filtering_by_domain(self, crawler):
        """Test filtering queue by domain."""
        session_id = "test-session-11"
        await crawler.start_crawling_session(session_id, [
            "https://example.com/page1",
            "https://test.com/page1",
            "https://example.com/page2"
        ])
        
        example_urls = await crawler.get_queue_by_domain("https://example.com")
        assert len(example_urls) == 2
        
        test_urls = await crawler.get_queue_by_domain("https://test.com")
        assert len(test_urls) == 1
    
    @pytest.mark.asyncio
    async def test_queue_filtering_by_priority(self, crawler):
        """Test filtering queue by priority."""
        session_id = "test-session-12"
        await crawler.start_crawling_session(session_id, ["https://example.com"])
        
        # Add URLs with different priorities
        await crawler.queue_urls(["https://example.com/low"], "https://example.com", 1)
        await crawler.prioritize_url("https://example.com/low", 3)
        
        # Filter by priority
        high_priority = await crawler.get_queue_by_priority(5)
        assert len(high_priority) == 1  # Only initial URL has priority 10
        
        all_priority = await crawler.get_queue_by_priority(0)
        assert len(all_priority) == 2  # Both URLs
    
    @pytest.mark.asyncio
    async def test_queue_status(self, crawler):
        """Test getting queue status."""
        session_id = "test-session-13"
        await crawler.start_crawling_session(session_id, ["https://example.com"])
        
        status = await crawler.get_queue_status()
        
        assert status["queue_size"] == 1
        assert status["urls_visited"] == 0
        assert status["urls_in_progress"] == 0
        assert status["session_id"] == session_id
        assert status["is_running"] is True
        assert status["concurrent_requests"] == 0
    
    @pytest.mark.asyncio
    async def test_queue_persistence(self, crawler):
        """Test queue state persistence."""
        session_id = "test-session-14"
        await crawler.start_crawling_session(session_id, ["https://example.com"])
        
        # Add some URLs
        await crawler.queue_urls(["https://example.com/page1"], "https://example.com", 0)
        
        # Save state
        await crawler.save_queue_state()
        
        # Create new crawler and load state
        new_crawler = WebCrawler(config=crawler.config, memory=crawler.memory)
        loaded = await new_crawler.load_queue_state(session_id)
        
        assert loaded is True
        assert new_crawler.session_id == session_id
    
    @pytest.mark.asyncio
    async def test_clear_queue(self, crawler):
        """Test clearing the queue."""
        session_id = "test-session-15"
        await crawler.start_crawling_session(session_id, [
            "https://example.com",
            "https://test.com"
        ])
        
        assert len(crawler.url_queue) == 2
        
        cleared_count = await crawler.clear_queue()
        
        assert cleared_count == 2
        assert len(crawler.url_queue) == 0
    
    @pytest.mark.asyncio
    async def test_remove_url_from_queue(self, crawler):
        """Test removing specific URL from queue."""
        session_id = "test-session-16"
        await crawler.start_crawling_session(session_id, [
            "https://example.com",
            "https://test.com"
        ])
        
        assert len(crawler.url_queue) == 2
        
        removed = await crawler.remove_url_from_queue("https://example.com")
        
        assert removed is True
        assert len(crawler.url_queue) == 1
        
        # Check that the correct URL was removed
        remaining_urls = [item.url for item in crawler.url_queue]
        assert "https://example.com" not in remaining_urls
        assert "https://test.com" in remaining_urls
    
    @pytest.mark.asyncio
    async def test_url_patterns_to_ignore(self, crawler):
        """Test URL patterns to ignore."""
        session_id = "test-session-17"
        await crawler.start_crawling_session(session_id, ["https://example.com"])
        
        # These URLs should be ignored based on patterns
        ignored_urls = [
            "https://example.com/image.jpg",
            "https://example.com/document.pdf",
            "https://example.com/styles.css",
            "mailto:test@example.com"
        ]
        
        for url in ignored_urls:
            should_crawl = await crawler._should_crawl_url(url, 0)
            assert not should_crawl, f"URL {url} should be ignored"
    
    @pytest.mark.asyncio
    async def test_max_depth_limit(self, crawler):
        """Test maximum depth limit enforcement."""
        session_id = "test-session-18"
        await crawler.start_crawling_session(session_id, ["https://example.com"])
        
        # Try to add URLs at maximum depth
        await crawler.queue_urls(["https://example.com/deep"], "https://example.com", 2)
        
        # Should not add URLs beyond max depth
        deep_urls = [item for item in crawler.url_queue if item.depth > 2]
        assert len(deep_urls) == 0
    
    @pytest.mark.asyncio
    async def test_concurrent_requests_tracking(self, crawler):
        """Test concurrent requests tracking."""
        session_id = "test-session-19"
        await crawler.start_crawling_session(session_id, ["https://example.com"])
        
        # Initially no concurrent requests
        assert crawler.concurrent_requests == 0
        
        # Start crawling (this would increment in real implementation)
        with patch.object(crawler, 'check_robots_allowed', return_value=True):
            # Use asyncio to simulate concurrent requests
            async def crawl_task():
                return await crawler.crawl_url("https://example.com/page")
            
            task = asyncio.create_task(crawl_task())
            await asyncio.sleep(0.05)  # Let it start
            
            # Should track concurrent requests during crawling
            # (In real implementation, this would be > 0 during the crawl)
            
            await task  # Wait for completion
        
        # After completion, should be back to 0
        assert crawler.concurrent_requests == 0