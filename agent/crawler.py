"""Web crawler with robots.txt compliance and rate limiting."""
import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
from urllib.robotparser import RobotFileParser
from urllib.parse import urljoin, urlparse, urlunparse
from pydantic import BaseModel, Field, field_validator
from agent.utils import setup_logging
from agent.memory import AgentMemory, CrawlState, VisitedURL

logger = logging.getLogger(__name__)


class CrawlerConfig(BaseModel):
    """Configuration for web crawler behavior."""
    user_agent: str = "PWIA-Agent/1.0"
    delay_between_requests: float = 1.0  # seconds
    max_concurrent_requests: int = 5
    request_timeout: int = 30  # seconds
    max_retries: int = 3
    retry_delay: float = 2.0  # seconds
    respect_robots_txt: bool = True
    max_depth: int = 3
    max_urls_per_domain: int = 1000
    allowed_domains: List[str] = Field(default_factory=list)
    blocked_domains: List[str] = Field(default_factory=list)
    url_patterns_to_ignore: List[str] = Field(default_factory=lambda: [
        r".*\.(pdf|jpg|jpeg|png|gif|ico|css|js|zip|tar|gz)$",
        r".*mailto:",
        r".*tel:",
        r".*#.*"
    ])
    robots_cache_ttl: int = 3600  # seconds to cache robots.txt


class URLQueueItem(BaseModel):
    """Item in the URL crawling queue."""
    url: str
    depth: int
    parent_url: Optional[str] = None
    priority: int = 0  # Higher numbers = higher priority
    discovered_at: datetime = Field(default_factory=datetime.now)
    retry_count: int = 0
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        """Ensure URL is properly formatted."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v


class RobotsTxtCache(BaseModel):
    """Cache entry for robots.txt data."""
    domain: str
    robots_txt_content: str
    fetched_at: datetime
    can_fetch_cache: Dict[str, bool] = Field(default_factory=dict)
    
    def is_expired(self, ttl: int) -> bool:
        """Check if this cache entry has expired."""
        return (datetime.now() - self.fetched_at).total_seconds() > ttl


class WebCrawler:
    """Web crawler with robots.txt compliance and intelligent queue management."""
    
    def __init__(self, config: CrawlerConfig, memory: AgentMemory):
        """Initialize the web crawler.
        
        Args:
            config: Crawler configuration
            memory: Agent memory for persistence
        """
        self.config = config
        self.memory = memory
        self.url_queue: List[URLQueueItem] = []
        self.urls_visited: Set[str] = set()
        self.urls_in_progress: Set[str] = set()
        self.domain_last_access: Dict[str, float] = {}
        self.robots_cache: Dict[str, RobotsTxtCache] = {}
        self.session_id: Optional[str] = None
        self.is_running: bool = False
        self.concurrent_requests: int = 0
        self._lock = asyncio.Lock()
        
        logger.info(f"WebCrawler initialized with config: {config.model_dump()}")

    async def start_crawling_session(self, session_id: str, initial_urls: List[str]) -> str:
        """Start a new crawling session.
        
        Args:
            session_id: Unique identifier for this crawling session
            initial_urls: List of URLs to start crawling from
            
        Returns:
            Session ID for the started session
        """
        self.session_id = session_id
        self.is_running = True
        
        # Initialize queue with initial URLs
        for url in initial_urls:
            if await self._is_url_valid(url):
                queue_item = URLQueueItem(url=url, depth=0, priority=10)
                self.url_queue.append(queue_item)
                logger.info(f"Added initial URL to queue: {url}")
        
        # Sort queue by priority (higher priority first)
        self.url_queue.sort(key=lambda x: x.priority, reverse=True)
        
        # Save initial crawl state
        crawl_state = CrawlState(
            session_id=session_id,
            task_id=f"crawl_{session_id}",
            start_time=datetime.now(),
            urls_to_visit=[item.url for item in self.url_queue],
            max_depth=self.config.max_depth,
            status="active"
        )
        await self.memory.save_crawl_state(crawl_state)
        
        logger.info(f"Started crawling session {session_id} with {len(initial_urls)} initial URLs")
        return session_id

    async def stop_crawling_session(self) -> None:
        """Stop the current crawling session."""
        if self.session_id:
            self.is_running = False
            
            # Update crawl state
            crawl_state = await self.memory.load_crawl_state(self.session_id)
            if crawl_state:
                crawl_state.status = "completed"
                crawl_state.last_updated = datetime.now()
                await self.memory.save_crawl_state(crawl_state)
            
            logger.info(f"Stopped crawling session {self.session_id}")
            self.session_id = None

    async def crawl_url(self, url: str, depth: int = 0) -> Tuple[bool, List[str], Optional[str]]:
        """Crawl a single URL with robots.txt compliance and rate limiting.
        
        Args:
            url: URL to crawl
            depth: Current crawl depth
            
        Returns:
            Tuple of (success, discovered_urls, error_message)
        """
        if not self.is_running:
            return False, [], "Crawling session not active"
        
        try:
            # Check robots.txt compliance
            if not await self.check_robots_allowed(url):
                error_msg = f"Robots.txt disallows crawling {url}"
                logger.warning(error_msg)
                await self.mark_url_completed(url, False, error_msg)
                return False, [], error_msg
            
            # Apply rate limiting
            domain = self._get_domain(url)
            if not await self._can_crawl_domain(domain):
                # Wait for rate limit to clear
                last_access = self.domain_last_access.get(domain, 0)
                wait_time = self.config.delay_between_requests - (time.time() - last_access)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
            
            # Increment concurrent requests counter
            async with self._lock:
                self.concurrent_requests += 1
            
            try:
                # Simulate URL crawling (in real implementation, this would use the browser)
                # For now, we'll just log and return empty results
                logger.info(f"Crawling URL: {url} (depth: {depth})")
                
                # Simulate crawl delay
                await asyncio.sleep(0.1)
                
                # In real implementation, this would:
                # 1. Use BrowserManager to navigate to URL
                # 2. Extract links and content
                # 3. Return discovered URLs
                
                # For now, return success with no discovered URLs
                discovered_urls = []
                
                await self.mark_url_completed(url, True)
                return True, discovered_urls, None
                
            finally:
                # Decrement concurrent requests counter
                async with self._lock:
                    self.concurrent_requests -= 1
                
        except Exception as e:
            error_msg = f"Failed to crawl {url}: {str(e)}"
            logger.error(error_msg)
            await self.mark_url_completed(url, False, error_msg)
            return False, [], error_msg

    async def get_next_url(self) -> Optional[URLQueueItem]:
        """Get the next URL to crawl from the queue.
        
        Returns:
            Next URL to crawl or None if queue is empty
        """
        async with self._lock:
            # Remove URLs that are already visited or in progress
            self.url_queue = [
                item for item in self.url_queue 
                if item.url not in self.urls_visited and item.url not in self.urls_in_progress
            ]
            
            if not self.url_queue:
                return None
            
            # Sort by priority and get the highest priority item
            self.url_queue.sort(key=lambda x: (x.priority, -x.depth), reverse=True)
            
            # Check if we can crawl from this domain (rate limiting)
            for i, item in enumerate(self.url_queue):
                domain = self._get_domain(item.url)
                
                if await self._can_crawl_domain(domain):
                    # Remove from queue and mark as in progress
                    queue_item = self.url_queue.pop(i)
                    self.urls_in_progress.add(queue_item.url)
                    self.domain_last_access[domain] = time.time()
                    return queue_item
            
            # No URLs available due to rate limiting
            return None

    async def queue_urls(self, urls: List[str], parent_url: str, depth: int) -> None:
        """Add URLs to the crawling queue.
        
        Args:
            urls: List of URLs to add to the queue
            parent_url: URL where these URLs were discovered
            depth: Current crawl depth
        """
        if depth >= self.config.max_depth:
            logger.debug(f"Skipping URLs at depth {depth} (max depth: {self.config.max_depth})")
            return
        
        async with self._lock:
            added_count = 0
            
            for url in urls:
                if await self._should_crawl_url(url, depth):
                    queue_item = URLQueueItem(
                        url=url,
                        depth=depth + 1,
                        parent_url=parent_url,
                        priority=max(0, 10 - depth)  # Higher priority for shallower depth
                    )
                    self.url_queue.append(queue_item)
                    added_count += 1
            
            # Sort queue by priority
            self.url_queue.sort(key=lambda x: x.priority, reverse=True)
            
            logger.info(f"Added {added_count} URLs to queue from {parent_url}")

    async def check_robots_allowed(self, url: str) -> bool:
        """Check if the URL is allowed by robots.txt.
        
        Args:
            url: URL to check
            
        Returns:
            True if crawling is allowed, False otherwise
        """
        if not self.config.respect_robots_txt:
            return True
        
        domain = self._get_domain(url)
        
        # Check cache first
        if domain in self.robots_cache:
            cache_entry = self.robots_cache[domain]
            if not cache_entry.is_expired(self.config.robots_cache_ttl):
                # Check if we have a cached result for this specific path
                parsed_url = urlparse(url)
                path = parsed_url.path or '/'
                
                cache_key = f"{self.config.user_agent}:{path}"
                if cache_key in cache_entry.can_fetch_cache:
                    return cache_entry.can_fetch_cache[cache_key]
        
        # Fetch and parse robots.txt
        robots_url = urljoin(url, '/robots.txt')
        try:
            robots_parser = RobotFileParser()
            robots_parser.set_url(robots_url)
            robots_parser.read()
            
            # Cache the robots.txt content
            self.robots_cache[domain] = RobotsTxtCache(
                domain=domain,
                robots_txt_content=str(robots_parser),
                fetched_at=datetime.now()
            )
            
            # Check if we can fetch this URL
            can_fetch = robots_parser.can_fetch(self.config.user_agent, url)
            
            # Cache the result
            parsed_url = urlparse(url)
            path = parsed_url.path or '/'
            cache_key = f"{self.config.user_agent}:{path}"
            self.robots_cache[domain].can_fetch_cache[cache_key] = can_fetch
            
            logger.debug(f"Robots.txt check for {url}: {'allowed' if can_fetch else 'blocked'}")
            return can_fetch
            
        except Exception as e:
            logger.warning(f"Failed to check robots.txt for {url}: {e}")
            # If robots.txt check fails, allow crawling (conservative approach)
            return True

    async def mark_url_completed(self, url: str, success: bool, error_message: Optional[str] = None) -> None:
        """Mark a URL as completed (successfully crawled or failed).
        
        Args:
            url: URL that was crawled
            success: Whether the crawl was successful
            error_message: Error message if crawl failed
        """
        async with self._lock:
            if url in self.urls_in_progress:
                self.urls_in_progress.remove(url)
            
            self.urls_visited.add(url)
            
            # Save visited URL to memory
            if self.session_id:
                visited_url = VisitedURL(
                    url=url,
                    visited_at=datetime.now(),
                    session_id=self.session_id,
                    response_status=200 if success else 0,
                    extraction_successful=success,
                    error_message=error_message
                )
                await self.memory.save_visited_url(visited_url)
            
            # Update crawl state
            if self.session_id:
                crawl_state = await self.memory.load_crawl_state(self.session_id)
                if crawl_state:
                    if success:
                        crawl_state.urls_visited.append(url)
                    else:
                        crawl_state.urls_failed.append(url)
                    
                    crawl_state.urls_to_visit = [item.url for item in self.url_queue]
                    crawl_state.last_updated = datetime.now()
                    await self.memory.save_crawl_state(crawl_state)

    async def get_queue_status(self) -> Dict[str, Any]:
        """Get current status of the crawling queue.
        
        Returns:
            Dictionary with queue statistics
        """
        async with self._lock:
            return {
                "queue_size": len(self.url_queue),
                "urls_visited": len(self.urls_visited),
                "urls_in_progress": len(self.urls_in_progress),
                "concurrent_requests": self.concurrent_requests,
                "session_id": self.session_id,
                "is_running": self.is_running,
                "domains_accessed": len(self.domain_last_access),
                "robots_cache_size": len(self.robots_cache)
            }

    async def save_queue_state(self) -> None:
        """Save current queue state to persistent storage."""
        if not self.session_id:
            return
        
        async with self._lock:
            # Save queue state to memory
            queue_data = {
                "queue_items": [item.model_dump() for item in self.url_queue],
                "urls_visited": list(self.urls_visited),
                "urls_in_progress": list(self.urls_in_progress),
                "domain_last_access": self.domain_last_access,
                "robots_cache": {
                    domain: cache.model_dump() for domain, cache in self.robots_cache.items()
                }
            }
            
            # Use memory to save queue state
            from agent.memory import ExtractedData
            queue_state = ExtractedData(
                id=f"queue_state_{self.session_id}",
                url="internal://queue_state",
                session_id=self.session_id,
                extraction_type="queue_state",
                data=queue_data,
                extracted_at=datetime.now(),
                confidence_score=1.0,
                selectors_used=["internal"],
                processing_time_ms=0
            )
            
            await self.memory.save_extracted_data(queue_state)
            logger.info(f"Saved queue state for session {self.session_id}")

    async def load_queue_state(self, session_id: str) -> bool:
        """Load queue state from persistent storage.
        
        Args:
            session_id: Session ID to load state for
            
        Returns:
            True if state was loaded successfully, False otherwise
        """
        try:
            # Try to load queue state from memory
            # This would need to be implemented in memory.py to query by extraction_type
            # For now, we'll implement a basic version
            
            self.session_id = session_id
            
            # Load crawl state
            crawl_state = await self.memory.load_crawl_state(session_id)
            if crawl_state:
                # Restore basic state
                self.urls_visited = set(crawl_state.urls_visited)
                
                # Rebuild queue from urls_to_visit
                self.url_queue = []
                for url in crawl_state.urls_to_visit:
                    if url not in self.urls_visited:
                        queue_item = URLQueueItem(
                            url=url,
                            depth=1,  # Default depth
                            priority=5  # Default priority
                        )
                        self.url_queue.append(queue_item)
                
                self.is_running = crawl_state.status == "active"
                logger.info(f"Loaded queue state for session {session_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to load queue state for session {session_id}: {e}")
        
        return False

    async def prioritize_url(self, url: str, new_priority: int) -> bool:
        """Change the priority of a URL in the queue.
        
        Args:
            url: URL to prioritize
            new_priority: New priority value (higher = more important)
            
        Returns:
            True if URL was found and prioritized, False otherwise
        """
        async with self._lock:
            for item in self.url_queue:
                if item.url == url:
                    item.priority = new_priority
                    # Re-sort queue by priority
                    self.url_queue.sort(key=lambda x: x.priority, reverse=True)
                    logger.info(f"Updated priority for {url} to {new_priority}")
                    return True
            return False

    async def remove_url_from_queue(self, url: str) -> bool:
        """Remove a URL from the crawling queue.
        
        Args:
            url: URL to remove
            
        Returns:
            True if URL was found and removed, False otherwise
        """
        async with self._lock:
            initial_length = len(self.url_queue)
            self.url_queue = [item for item in self.url_queue if item.url != url]
            
            if len(self.url_queue) < initial_length:
                logger.info(f"Removed {url} from crawling queue")
                return True
            return False

    async def get_queue_by_domain(self, domain: str) -> List[URLQueueItem]:
        """Get all queued URLs for a specific domain.
        
        Args:
            domain: Domain to filter by
            
        Returns:
            List of queue items for the domain
        """
        async with self._lock:
            return [
                item for item in self.url_queue 
                if self._get_domain(item.url) == domain
            ]

    async def get_queue_by_priority(self, min_priority: int = 0) -> List[URLQueueItem]:
        """Get all queued URLs with priority >= min_priority.
        
        Args:
            min_priority: Minimum priority threshold
            
        Returns:
            List of queue items sorted by priority (highest first)
        """
        async with self._lock:
            filtered_items = [
                item for item in self.url_queue 
                if item.priority >= min_priority
            ]
            return sorted(filtered_items, key=lambda x: x.priority, reverse=True)

    async def clear_queue(self) -> int:
        """Clear all URLs from the queue.
        
        Returns:
            Number of URLs that were removed
        """
        async with self._lock:
            count = len(self.url_queue)
            self.url_queue.clear()
            logger.info(f"Cleared {count} URLs from crawling queue")
            return count

    async def get_duplicate_urls(self) -> Dict[str, int]:
        """Check for duplicate URLs in the queue.
        
        Returns:
            Dictionary mapping URLs to their occurrence count
        """
        async with self._lock:
            url_counts = {}
            for item in self.url_queue:
                url_counts[item.url] = url_counts.get(item.url, 0) + 1
            
            # Return only duplicates (count > 1)
            return {url: count for url, count in url_counts.items() if count > 1}

    async def deduplicate_queue(self) -> int:
        """Remove duplicate URLs from the queue, keeping highest priority.
        
        Returns:
            Number of duplicate URLs removed
        """
        async with self._lock:
            initial_length = len(self.url_queue)
            
            # Group by URL and keep highest priority
            url_groups = {}
            for item in self.url_queue:
                if item.url not in url_groups:
                    url_groups[item.url] = item
                else:
                    # Keep item with higher priority
                    if item.priority > url_groups[item.url].priority:
                        url_groups[item.url] = item
            
            # Replace queue with deduplicated items
            self.url_queue = list(url_groups.values())
            self.url_queue.sort(key=lambda x: x.priority, reverse=True)
            
            removed_count = initial_length - len(self.url_queue)
            if removed_count > 0:
                logger.info(f"Removed {removed_count} duplicate URLs from queue")
            
            return removed_count

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    async def _is_url_valid(self, url: str) -> bool:
        """Check if URL is valid and should be crawled."""
        try:
            parsed = urlparse(url)
            
            # Check if URL has valid scheme
            if parsed.scheme not in ['http', 'https']:
                return False
            
            # Check if domain is in allowed/blocked lists
            domain = parsed.netloc.lower()
            
            if self.config.blocked_domains and domain in self.config.blocked_domains:
                return False
            
            if self.config.allowed_domains and domain not in self.config.allowed_domains:
                return False
            
            return True
            
        except Exception:
            return False

    async def _should_crawl_url(self, url: str, depth: int) -> bool:
        """Check if URL should be added to crawling queue."""
        # Basic validation
        if not await self._is_url_valid(url):
            return False
        
        # Check if already visited or queued
        if url in self.urls_visited or url in self.urls_in_progress:
            return False
        
        # Check if already in queue
        if any(item.url == url for item in self.url_queue):
            return False
        
        # Check depth limit
        if depth >= self.config.max_depth:
            return False
        
        # Check domain URL limit
        domain = self._get_domain(url)
        domain_urls = sum(1 for item in self.url_queue if self._get_domain(item.url) == domain)
        if domain_urls >= self.config.max_urls_per_domain:
            return False
        
        # Check URL patterns to ignore
        import re
        for pattern in self.config.url_patterns_to_ignore:
            if re.match(pattern, url, re.IGNORECASE):
                return False
        
        return True

    async def _can_crawl_domain(self, domain: str) -> bool:
        """Check if we can crawl from this domain based on rate limiting."""
        if domain not in self.domain_last_access:
            return True
        
        last_access = self.domain_last_access[domain]
        time_since_last = time.time() - last_access
        
        return time_since_last >= self.config.delay_between_requests