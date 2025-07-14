"""Integration layer orchestrating browser, crawler, and scraper components."""
import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from pydantic import BaseModel, Field

from agent.browser import BrowserManager, BrowserConfig, BrowserSession
from agent.crawler import WebCrawler, CrawlerConfig, URLQueueItem
from agent.scraper import DataScraper, ScraperConfig, ExtractionResult
from agent.memory import AgentMemory, CrawlState, VisitedURL, ExtractedData, AgentSession
from agent.utils import setup_logging

logger = logging.getLogger(__name__)


class IntegrationConfig(BaseModel):
    """Configuration for the integration layer."""
    session_timeout: int = 3600  # seconds
    max_concurrent_pages: int = 3
    page_load_timeout: int = 30000  # milliseconds
    extraction_timeout: int = 15000  # milliseconds
    retry_failed_urls: bool = True
    max_retry_attempts: int = 3
    save_intermediate_results: bool = True
    enable_screenshots: bool = False
    screenshot_on_error: bool = True
    batch_size: int = 10  # URLs to process in one batch
    progress_report_interval: int = 5  # seconds
    # Enhanced error recovery settings
    circuit_breaker_threshold: int = 5  # Failed attempts before circuit opens
    circuit_breaker_timeout: int = 60  # seconds before retrying
    health_check_interval: int = 30  # seconds between health checks
    max_memory_usage_mb: int = 512  # Maximum memory usage before throttling
    enable_adaptive_delays: bool = True  # Adaptive delays based on server response
    max_adaptive_delay: int = 10  # Maximum adaptive delay in seconds
    # Long-running session management settings
    enable_session_persistence: bool = True  # Save session state to disk
    session_checkpoint_interval: int = 300  # seconds between checkpoints
    session_recovery_enabled: bool = True  # Enable automatic session recovery
    max_session_duration: int = 86400  # Maximum session duration (24 hours)
    session_heartbeat_interval: int = 60  # seconds between heartbeat updates
    auto_session_cleanup_age: int = 604800  # Auto-cleanup sessions older than 7 days
    enable_session_migration: bool = True  # Allow session migration between restarts


class TaskProgress(BaseModel):
    """Progress information for crawling tasks."""
    task_id: str
    session_id: str
    start_time: datetime
    urls_queued: int = 0
    urls_processed: int = 0
    urls_successful: int = 0
    urls_failed: int = 0
    data_extracted: int = 0
    current_url: Optional[str] = None
    status: str = "initializing"  # initializing, running, paused, completed, failed
    completion_percentage: float = 0.0
    estimated_time_remaining: Optional[int] = None  # seconds
    last_updated: datetime = Field(default_factory=datetime.now)


class TaskResult(BaseModel):
    """Final result of a crawling task."""
    task_id: str
    session_id: str
    success: bool
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    urls_processed: int
    urls_successful: int
    urls_failed: int
    data_extracted: int
    extraction_results: List[str] = Field(default_factory=list)  # IDs of extracted data
    failed_urls: List[Dict[str, Any]] = Field(default_factory=list)
    error_message: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)


class SessionCheckpoint(BaseModel):
    """Checkpoint data for session recovery."""
    session_id: str
    task_id: str
    checkpoint_time: datetime
    progress_snapshot: Dict[str, Any]
    crawler_state: Dict[str, Any]
    circuit_breaker_state: Dict[str, Any]
    adaptive_delays_state: Dict[str, Any]
    active_urls: List[str] = Field(default_factory=list)
    completed_urls: List[str] = Field(default_factory=list)
    failed_urls: List[str] = Field(default_factory=list)
    extraction_results: List[str] = Field(default_factory=list)
    browser_session_info: Optional[Dict[str, Any]] = None
    recovery_metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionRecoveryInfo(BaseModel):
    """Information about recoverable sessions."""
    session_id: str
    task_id: str
    last_checkpoint: datetime
    last_heartbeat: datetime
    status: str  # active, paused, crashed, recoverable
    recovery_possible: bool
    estimated_progress: float
    urls_remaining: int
    crash_reason: Optional[str] = None
    recovery_strategy: str = "resume"  # resume, restart, skip


class SessionHeartbeat(BaseModel):
    """Heartbeat data for session monitoring."""
    session_id: str
    timestamp: datetime
    status: str
    urls_processed: int
    urls_remaining: int
    current_url: Optional[str] = None
    memory_usage_mb: float
    browser_pages_active: int
    health_score: float = Field(ge=0.0, le=1.0)  # 0.0 = unhealthy, 1.0 = healthy


class IntegrationLayer:
    """Orchestrates browser, crawler, and scraper components for web automation tasks."""
    
    def __init__(
        self,
        browser_config: Optional[BrowserConfig] = None,
        crawler_config: Optional[CrawlerConfig] = None,
        scraper_config: Optional[ScraperConfig] = None,
        integration_config: Optional[IntegrationConfig] = None,
        memory: Optional[AgentMemory] = None
    ):
        """Initialize the integration layer with component configurations."""
        self.config = integration_config or IntegrationConfig()
        self.memory = memory or AgentMemory()
        
        # Initialize components
        self.browser_manager = BrowserManager(browser_config)
        self.crawler = WebCrawler(crawler_config or CrawlerConfig(), self.memory)
        self.scraper = DataScraper(scraper_config or ScraperConfig(), self.memory)
        
        # State management
        self.active_sessions: Dict[str, AgentSession] = {}
        self.task_progress: Dict[str, TaskProgress] = {}
        self.session_browsers: Dict[str, str] = {}  # session_id -> browser_session_id
        
        # Coordination state
        self._shutdown_event = asyncio.Event()
        self._progress_task: Optional[asyncio.Task] = None
        
        # Enhanced error recovery state
        self._circuit_breaker_failures: Dict[str, int] = {}  # domain -> failure count
        self._circuit_breaker_opened: Dict[str, datetime] = {}  # domain -> open time
        self._adaptive_delays: Dict[str, float] = {}  # domain -> current delay
        self._health_check_task: Optional[asyncio.Task] = None
        self._processing_semaphore = asyncio.Semaphore(self.config.max_concurrent_pages)
        
        # Session persistence and recovery state
        self._session_checkpoints: Dict[str, SessionCheckpoint] = {}
        self._session_heartbeats: Dict[str, SessionHeartbeat] = {}
        self._checkpoint_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._session_persistence_dir = Path("app-memory/sessions")
        self._session_persistence_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("IntegrationLayer initialized with all components")
    
    async def execute_task(
        self,
        task_id: str,
        initial_urls: List[str],
        extraction_rules: Optional[Dict[str, Any]] = None,
        task_config: Optional[Dict[str, Any]] = None
    ) -> TaskResult:
        """Execute a complete web crawling and data extraction task."""
        session_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        logger.info(f"Starting task {task_id} with session {session_id}")
        
        try:
            # Initialize task progress tracking
            progress = TaskProgress(
                task_id=task_id,
                session_id=session_id,
                start_time=start_time,
                urls_queued=len(initial_urls),
                status="initializing"
            )
            self.task_progress[task_id] = progress
            
            # Create agent session
            agent_session = AgentSession(
                session_id=session_id,
                task_id=task_id,
                start_time=start_time,
                config=task_config or {}
            )
            self.active_sessions[session_id] = agent_session
            await self.memory.save_session(agent_session)
            
            # Launch browser and start crawling session
            browser_session_id = f"browser_{session_id}"
            await self.browser_manager.launch_browser(browser_session_id)
            self.session_browsers[session_id] = browser_session_id
            
            # Start crawler session
            await self.crawler.start_crawling_session(session_id, initial_urls)
            
            # Update progress
            progress.status = "running"
            progress.last_updated = datetime.now()
            
            # Start background monitoring tasks
            self._progress_task = asyncio.create_task(
                self._progress_reporter(task_id)
            )
            self._health_check_task = asyncio.create_task(
                self._health_monitor(session_id)
            )
            
            # Start session persistence tasks if enabled
            if self.config.enable_session_persistence:
                self._checkpoint_task = asyncio.create_task(
                    self._session_checkpoint_manager(session_id, task_id)
                )
                self._heartbeat_task = asyncio.create_task(
                    self._session_heartbeat_manager(session_id)
                )
            
            # Execute crawling workflow with enhanced error recovery
            extraction_results = await self._execute_crawling_workflow_enhanced(
                task_id, session_id, extraction_rules
            )
            
            # Calculate final metrics
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Create task result
            result = TaskResult(
                task_id=task_id,
                session_id=session_id,
                success=True,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                urls_processed=progress.urls_processed,
                urls_successful=progress.urls_successful,
                urls_failed=progress.urls_failed,
                data_extracted=progress.data_extracted,
                extraction_results=extraction_results,
                metrics=await self._collect_metrics(session_id)
            )
            
            # Update progress to completed
            progress.status = "completed"
            progress.completion_percentage = 100.0
            progress.last_updated = datetime.now()
            
            logger.info(f"Task {task_id} completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Task {task_id} failed: {str(e)}")
            
            # Update progress to failed
            if task_id in self.task_progress:
                self.task_progress[task_id].status = "failed"
                self.task_progress[task_id].last_updated = datetime.now()
            
            # Create failure result
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            return TaskResult(
                task_id=task_id,
                session_id=session_id,
                success=False,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                urls_processed=self.task_progress.get(task_id, progress).urls_processed,
                urls_successful=self.task_progress.get(task_id, progress).urls_successful,
                urls_failed=self.task_progress.get(task_id, progress).urls_failed,
                data_extracted=self.task_progress.get(task_id, progress).data_extracted,
                error_message=str(e)
            )
        
        finally:
            # Cleanup
            await self._cleanup_session(session_id)
    
    async def coordinate_components(
        self,
        session_id: str,
        url: str,
        extraction_rules: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Coordinate browser, crawler, and scraper for a single URL with enhanced error recovery."""
        # Check circuit breaker
        domain = self._get_domain_from_url(url)
        if not await self._check_circuit_breaker(domain):
            return False, f"Circuit breaker open for domain {domain}", None
        
        browser_session_id = self.session_browsers.get(session_id)
        if not browser_session_id:
            return False, "No browser session found", None
        
        # Acquire semaphore for concurrent processing control
        async with self._processing_semaphore:
            try:
                # Apply adaptive delay
                delay = self._adaptive_delays.get(domain, 0)
                if delay > 0:
                    logger.debug(f"Applying adaptive delay of {delay}s for {domain}")
                    await asyncio.sleep(delay)
                
                # Create browser page
                page_id = f"page_{uuid.uuid4()}"
                page = await self.browser_manager.get_page(page_id)
                if not page:
                    await self._record_failure(domain)
                    return False, "Failed to create browser page", None
                
                # Navigate to URL with timeout
                logger.debug(f"Navigating to {url}")
                start_time = datetime.now()
                await asyncio.wait_for(
                    page.goto(url, timeout=self.config.page_load_timeout),
                    timeout=self.config.page_load_timeout / 1000
                )
            
                # Wait for page to load
                await self.browser_manager.wait_for_load_state(page_id, "networkidle")
                
                # Record successful navigation timing
                navigation_time = (datetime.now() - start_time).total_seconds()
                await self._update_adaptive_delay(domain, navigation_time)
                
                # Extract data using scraper with timeout
                extraction_data = {}
                extraction_start = datetime.now()
                
                if extraction_rules:
                    # Custom extraction based on rules
                    for rule_name, rule_config in extraction_rules.items():
                        try:
                            if rule_config.get("type") == "css":
                                result = await asyncio.wait_for(
                                    self.scraper.extract_by_css_selector(
                                        page, rule_config["selector"], rule_config.get("attributes", [])
                                    ),
                                    timeout=self.config.extraction_timeout / 1000
                                )
                            elif rule_config.get("type") == "xpath":
                                result = await asyncio.wait_for(
                                    self.scraper.extract_by_xpath(
                                        page, rule_config["selector"], rule_config.get("attributes", [])
                                    ),
                                    timeout=self.config.extraction_timeout / 1000
                                )
                            else:
                                continue
                            
                            extraction_data[rule_name] = result.model_dump()
                            
                        except Exception as e:
                            logger.warning(f"Extraction rule {rule_name} failed: {str(e)}")
                else:
                    # Comprehensive extraction
                    comprehensive_results = await asyncio.wait_for(
                        self.scraper.extract_comprehensive(page),
                        timeout=self.config.extraction_timeout / 1000
                    )
                    extraction_data = {
                        name: result.model_dump() 
                        for name, result in comprehensive_results.items()
                    }
                
                # Record successful extraction timing
                extraction_time = (datetime.now() - extraction_start).total_seconds()
                logger.debug(f"Extraction completed in {extraction_time:.2f}s for {url}")
                
                # Save extraction results
                if extraction_data:
                    for result_name, result_data in extraction_data.items():
                        extraction_result = ExtractionResult(**result_data)
                        await self.scraper.save_extraction_result(extraction_result)
                
                # Mark URL as completed in crawler
                await self.crawler.mark_url_completed(url, True)
                
                # Record success for circuit breaker
                await self._record_success(domain)
                
                # Close page
                await self.browser_manager.close_page(page_id)
                
                return True, None, extraction_data
            
            except Exception as e:
                error_msg = f"Failed to process {url}: {str(e)}"
                logger.error(error_msg)
                
                # Record failure for circuit breaker
                await self._record_failure(domain)
                
                # Take screenshot on error if enabled
                if self.config.screenshot_on_error and browser_session_id:
                    try:
                        screenshot_path = f"error_{session_id}_{url.replace('/', '_')}.png"
                        await self.browser_manager.take_screenshot(page_id, file_path=screenshot_path)
                    except:
                        pass
                
                # Mark URL as failed
                await self.crawler.mark_url_completed(url, False, error_msg)
                
                return False, error_msg, None
    
    async def handle_failures(
        self,
        session_id: str,
        failed_urls: List[str],
        max_retries: Optional[int] = None
    ) -> Dict[str, bool]:
        """Handle and retry failed URLs with enhanced exponential backoff and circuit breaker awareness."""
        if not self.config.retry_failed_urls:
            return {url: False for url in failed_urls}
        
        max_retries = max_retries or self.config.max_retry_attempts
        results = {}
        
        # Group URLs by domain for efficient circuit breaker handling
        domain_groups = {}
        for url in failed_urls:
            domain = self._get_domain_from_url(url)
            if domain not in domain_groups:
                domain_groups[domain] = []
            domain_groups[domain].append(url)
        
        for domain, urls in domain_groups.items():
            # Check if circuit breaker is open for this domain
            if not await self._check_circuit_breaker(domain):
                logger.info(f"Circuit breaker open for {domain}, skipping {len(urls)} URLs")
                for url in urls:
                    results[url] = False
                continue
            
            # Process URLs for this domain with progressive delays
            for url in urls:
                retry_count = 0
                success = False
                base_delay = self._adaptive_delays.get(domain, 1.0)
                
                while retry_count < max_retries and not success:
                    retry_count += 1
                    # Enhanced exponential backoff with jitter
                    wait_time = min(
                        base_delay * (2 ** retry_count) + (await self._get_jitter()),
                        self.config.max_adaptive_delay
                    )
                    
                    logger.info(f"Retrying {url} (attempt {retry_count}/{max_retries}) after {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    
                    try:
                        # Check circuit breaker again before retry
                        if not await self._check_circuit_breaker(domain):
                            logger.info(f"Circuit breaker opened during retry for {domain}")
                            break
                        
                        success, error_msg, _ = await self.coordinate_components(session_id, url)
                        if success:
                            logger.info(f"Retry successful for {url}")
                            await self._record_success(domain)
                            break
                        else:
                            await self._record_failure(domain)
                            
                    except Exception as e:
                        logger.warning(f"Retry {retry_count} failed for {url}: {str(e)}")
                        await self._record_failure(domain)
                
                results[url] = success
                
                # Brief delay between URLs in same domain
                if not success and len(urls) > 1:
                    await asyncio.sleep(0.5)
        
        return results
    
    async def get_task_progress(self, task_id: str) -> Optional[TaskProgress]:
        """Get current progress for a task."""
        return self.task_progress.get(task_id)
    
    async def pause_task(self, task_id: str) -> bool:
        """Pause an active task."""
        if task_id not in self.task_progress:
            return False
        
        progress = self.task_progress[task_id]
        if progress.status != "running":
            return False
        
        progress.status = "paused"
        progress.last_updated = datetime.now()
        
        # Stop crawler session
        await self.crawler.stop_crawling_session()
        
        logger.info(f"Task {task_id} paused")
        return True
    
    async def resume_task(self, task_id: str) -> bool:
        """Resume a paused task."""
        if task_id not in self.task_progress:
            return False
        
        progress = self.task_progress[task_id]
        if progress.status != "paused":
            return False
        
        progress.status = "running"
        progress.last_updated = datetime.now()
        
        logger.info(f"Task {task_id} resumed")
        return True
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel an active or paused task."""
        if task_id not in self.task_progress:
            return False
        
        progress = self.task_progress[task_id]
        progress.status = "cancelled"
        progress.last_updated = datetime.now()
        
        # Cleanup session
        session_id = progress.session_id
        await self._cleanup_session(session_id)
        
        logger.info(f"Task {task_id} cancelled")
        return True
    
    async def _execute_crawling_workflow(
        self,
        task_id: str,
        session_id: str,
        extraction_rules: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Execute the main crawling and extraction workflow."""
        extraction_results = []
        progress = self.task_progress[task_id]
        
        while True:
            # Get next URL from crawler queue
            url_item = await self.crawler.get_next_url()
            if not url_item:
                logger.info("No more URLs to process")
                break
            
            # Update progress
            progress.current_url = url_item.url
            progress.last_updated = datetime.now()
            
            # Process the URL
            success, error_msg, extraction_data = await self.coordinate_components(
                session_id, url_item.url, extraction_rules
            )
            
            # Update counters
            progress.urls_processed += 1
            if success:
                progress.urls_successful += 1
                if extraction_data:
                    progress.data_extracted += len(extraction_data)
                    extraction_results.extend([
                        result.get("id", "") for result in extraction_data.values()
                    ])
            else:
                progress.urls_failed += 1
            
            # Update completion percentage
            total_urls = progress.urls_queued
            if total_urls > 0:
                progress.completion_percentage = (progress.urls_processed / total_urls) * 100
            
            # Check if should pause
            if progress.status == "paused":
                logger.info("Workflow paused")
                break
            
            # Batch processing delay
            if progress.urls_processed % self.config.batch_size == 0:
                await asyncio.sleep(1)  # Brief pause between batches
        
        return extraction_results
    
    async def _progress_reporter(self, task_id: str):
        """Background task to report progress periodically."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self.config.progress_report_interval)
                
                if task_id in self.task_progress:
                    progress = self.task_progress[task_id]
                    
                    # Calculate estimated time remaining
                    if progress.urls_processed > 0 and progress.urls_queued > 0:
                        elapsed = (datetime.now() - progress.start_time).total_seconds()
                        rate = progress.urls_processed / elapsed
                        remaining_urls = progress.urls_queued - progress.urls_processed
                        progress.estimated_time_remaining = int(remaining_urls / rate) if rate > 0 else None
                    
                    logger.info(
                        f"Task {task_id} progress: {progress.urls_processed}/{progress.urls_queued} "
                        f"({progress.completion_percentage:.1f}%) - "
                        f"Success: {progress.urls_successful}, Failed: {progress.urls_failed}"
                    )
                
            except Exception as e:
                logger.error(f"Progress reporter error: {str(e)}")
    
    async def _collect_metrics(self, session_id: str) -> Dict[str, Any]:
        """Collect performance and operational metrics."""
        metrics = {}
        
        try:
            # Browser metrics
            browser_session = self.browser_manager.get_session_info()
            if browser_session:
                metrics["browser"] = {
                    "pages_opened": browser_session.pages_opened,
                    "contexts_created": browser_session.contexts_created,
                    "session_duration": (datetime.now() - browser_session.start_time).total_seconds()
                }
            
            # Crawler metrics
            queue_status = await self.crawler.get_queue_status()
            metrics["crawler"] = queue_status
            
            # Scraper metrics
            scraper_stats = self.scraper.get_statistics()
            metrics["scraper"] = scraper_stats
            
        except Exception as e:
            logger.error(f"Failed to collect metrics: {str(e)}")
        
        return metrics
    
    async def _cleanup_session(self, session_id: str):
        """Clean up resources for a session."""
        try:
            # Stop background tasks
            if self._progress_task and not self._progress_task.done():
                self._progress_task.cancel()
            if self._health_check_task and not self._health_check_task.done():
                self._health_check_task.cancel()
            if self._checkpoint_task and not self._checkpoint_task.done():
                self._checkpoint_task.cancel()
            if self._heartbeat_task and not self._heartbeat_task.done():
                self._heartbeat_task.cancel()
            
            # Stop crawler session
            await self.crawler.stop_crawling_session()
            
            # Close browser session
            browser_session_id = self.session_browsers.get(session_id)
            if browser_session_id:
                await self.browser_manager.close_browser()
                del self.session_browsers[session_id]
            
            # Update session as ended
            if session_id in self.active_sessions:
                session = self.active_sessions[session_id]
                session.end_time = datetime.now()
                session.status = "completed"
                await self.memory.save_session(session)
                del self.active_sessions[session_id]
            
            logger.info(f"Session {session_id} cleaned up")
            
        except Exception as e:
            logger.error(f"Cleanup error for session {session_id}: {str(e)}")
    
    async def close(self):
        """Close the integration layer and all components."""
        try:
            # Signal shutdown
            self._shutdown_event.set()
            
            # Cancel progress reporting
            if self._progress_task and not self._progress_task.done():
                self._progress_task.cancel()
            
            # Cleanup all active sessions
            for session_id in list(self.active_sessions.keys()):
                await self._cleanup_session(session_id)
            
            # Close components
            await self.browser_manager.close_browser()
            await self.scraper.close()
            
            # Close memory
            self.memory.close()
            
            logger.info("IntegrationLayer closed successfully")
            
        except Exception as e:
            logger.error(f"Error closing IntegrationLayer: {str(e)}")
    
    async def _execute_crawling_workflow_enhanced(
        self,
        task_id: str,
        session_id: str,
        extraction_rules: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Enhanced crawling workflow with circuit breaker and adaptive processing."""
        extraction_results = []
        progress = self.task_progress[task_id]
        concurrent_tasks = []
        
        while True:
            # Process URLs concurrently up to semaphore limit
            while len(concurrent_tasks) < self.config.max_concurrent_pages:
                url_item = await self.crawler.get_next_url()
                if not url_item:
                    break
                
                # Create concurrent task for URL processing
                task = asyncio.create_task(
                    self._process_url_with_recovery(
                        session_id, url_item.url, extraction_rules, progress
                    )
                )
                concurrent_tasks.append(task)
            
            if not concurrent_tasks:
                break
            
            # Wait for at least one task to complete
            done, pending = await asyncio.wait(
                concurrent_tasks, return_when=asyncio.FIRST_COMPLETED
            )
            
            # Process completed tasks
            for task in done:
                try:
                    result = await task
                    if result:
                        extraction_results.extend(result)
                except Exception as e:
                    logger.error(f"Task processing error: {str(e)}")
                
                concurrent_tasks.remove(task)
            
            # Update completion percentage
            total_urls = progress.urls_queued
            if total_urls > 0:
                progress.completion_percentage = (progress.urls_processed / total_urls) * 100
            
            # Check if should pause
            if progress.status == "paused":
                logger.info("Workflow paused")
                # Wait for remaining tasks to complete
                if concurrent_tasks:
                    await asyncio.gather(*concurrent_tasks, return_exceptions=True)
                break
        
        # Wait for any remaining tasks
        if concurrent_tasks:
            await asyncio.gather(*concurrent_tasks, return_exceptions=True)
        
        return extraction_results
    
    async def _process_url_with_recovery(
        self,
        session_id: str,
        url: str,
        extraction_rules: Optional[Dict[str, Any]],
        progress: TaskProgress
    ) -> List[str]:
        """Process a single URL with enhanced recovery and tracking."""
        progress.current_url = url
        progress.last_updated = datetime.now()
        
        # Process the URL
        success, error_msg, extraction_data = await self.coordinate_components(
            session_id, url, extraction_rules
        )
        
        # Update counters
        progress.urls_processed += 1
        if success:
            progress.urls_successful += 1
            if extraction_data:
                progress.data_extracted += len(extraction_data)
                return [result.get("id", "") for result in extraction_data.values()]
        else:
            progress.urls_failed += 1
        
        return []
    
    async def _health_monitor(self, session_id: str):
        """Monitor system health and adjust processing accordingly."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self.config.health_check_interval)
                
                # Check memory usage (simplified)
                import psutil
                memory_mb = psutil.Process().memory_info().rss / 1024 / 1024
                
                if memory_mb > self.config.max_memory_usage_mb:
                    logger.warning(f"High memory usage: {memory_mb:.1f}MB")
                    # Reduce concurrent processing
                    if self._processing_semaphore._value > 1:
                        await self._processing_semaphore.acquire()
                
                # Check browser health
                if self.browser_manager.is_running():
                    browser_info = self.browser_manager.get_session_info()
                    if browser_info and browser_info.pages_opened > 20:
                        logger.info("High page count, considering cleanup")
                
            except Exception as e:
                logger.error(f"Health monitor error: {str(e)}")
    
    def _get_domain_from_url(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc.lower()
        except:
            return "unknown"
    
    async def _check_circuit_breaker(self, domain: str) -> bool:
        """Check if circuit breaker is open for domain."""
        if domain in self._circuit_breaker_opened:
            open_time = self._circuit_breaker_opened[domain]
            if (datetime.now() - open_time).total_seconds() < self.config.circuit_breaker_timeout:
                return False
            else:
                # Circuit breaker timeout expired, reset
                del self._circuit_breaker_opened[domain]
                self._circuit_breaker_failures[domain] = 0
        
        return True
    
    async def _record_failure(self, domain: str):
        """Record a failure for circuit breaker tracking."""
        self._circuit_breaker_failures[domain] = self._circuit_breaker_failures.get(domain, 0) + 1
        
        if self._circuit_breaker_failures[domain] >= self.config.circuit_breaker_threshold:
            self._circuit_breaker_opened[domain] = datetime.now()
            logger.warning(f"Circuit breaker opened for {domain}")
    
    async def _record_success(self, domain: str):
        """Record a success for circuit breaker tracking."""
        if domain in self._circuit_breaker_failures:
            # Reduce failure count on success
            self._circuit_breaker_failures[domain] = max(0, self._circuit_breaker_failures[domain] - 1)
    
    async def _update_adaptive_delay(self, domain: str, response_time: float):
        """Update adaptive delay based on response time."""
        if not self.config.enable_adaptive_delays:
            return
        
        current_delay = self._adaptive_delays.get(domain, 0.5)
        
        # Adjust delay based on response time
        if response_time > 5.0:  # Slow response
            new_delay = min(current_delay * 1.5, self.config.max_adaptive_delay)
        elif response_time < 1.0:  # Fast response
            new_delay = max(current_delay * 0.8, 0.1)
        else:
            new_delay = current_delay
        
        self._adaptive_delays[domain] = new_delay
    
    async def _get_jitter(self) -> float:
        """Get random jitter for backoff timing."""
        import random
        return random.uniform(0, 0.5)
    
    # =============================================================================
    # SESSION PERSISTENCE AND RECOVERY METHODS
    # =============================================================================
    
    async def create_session_checkpoint(self, session_id: str, task_id: str) -> bool:
        """Create a checkpoint for session recovery."""
        try:
            if task_id not in self.task_progress:
                logger.warning(f"No progress found for task {task_id}")
                return False
            
            progress = self.task_progress[task_id]
            
            # Get crawler state
            crawler_state = await self.crawler.get_queue_status()
            
            # Create checkpoint
            checkpoint = SessionCheckpoint(
                session_id=session_id,
                task_id=task_id,
                checkpoint_time=datetime.now(),
                progress_snapshot=progress.model_dump(),
                crawler_state=crawler_state,
                circuit_breaker_state={
                    "failures": self._circuit_breaker_failures.copy(),
                    "opened": {k: v.isoformat() for k, v in self._circuit_breaker_opened.items()}
                },
                adaptive_delays_state=self._adaptive_delays.copy(),
                browser_session_info=self.browser_manager.get_session_info().model_dump() if self.browser_manager.get_session_info() else None
            )
            
            # Save checkpoint to memory and disk
            self._session_checkpoints[session_id] = checkpoint
            if self.config.enable_session_persistence:
                await self._save_checkpoint_to_disk(checkpoint)
            
            logger.debug(f"Created checkpoint for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create checkpoint for session {session_id}: {str(e)}")
            return False
    
    async def recover_session(self, session_id: str) -> Optional[SessionRecoveryInfo]:
        """Attempt to recover a crashed or interrupted session."""
        try:
            # Check for existing checkpoint
            checkpoint = await self._load_checkpoint_from_disk(session_id)
            if not checkpoint:
                logger.info(f"No checkpoint found for session {session_id}")
                return None
            
            # Analyze recovery feasibility
            recovery_info = await self._analyze_session_recovery(checkpoint)
            
            if recovery_info.recovery_possible:
                logger.info(f"Session {session_id} is recoverable: {recovery_info.recovery_strategy}")
                
                # Restore session state
                await self._restore_session_state(checkpoint)
                
                return recovery_info
            else:
                logger.warning(f"Session {session_id} is not recoverable: {recovery_info.crash_reason}")
                return recovery_info
                
        except Exception as e:
            logger.error(f"Failed to recover session {session_id}: {str(e)}")
            return None
    
    async def list_recoverable_sessions(self) -> List[SessionRecoveryInfo]:
        """List all sessions that can be recovered."""
        recoverable_sessions = []
        
        try:
            # Scan session directory for checkpoints
            if not self._session_persistence_dir.exists():
                return recoverable_sessions
            
            for checkpoint_file in self._session_persistence_dir.glob("checkpoint_*.json"):
                try:
                    session_id = checkpoint_file.stem.replace("checkpoint_", "")
                    checkpoint = await self._load_checkpoint_from_disk(session_id)
                    
                    if checkpoint:
                        recovery_info = await self._analyze_session_recovery(checkpoint)
                        recoverable_sessions.append(recovery_info)
                        
                except Exception as e:
                    logger.warning(f"Failed to analyze checkpoint {checkpoint_file}: {str(e)}")
            
            return recoverable_sessions
            
        except Exception as e:
            logger.error(f"Failed to list recoverable sessions: {str(e)}")
            return recoverable_sessions
    
    async def cleanup_old_sessions(self, max_age_days: int = 7) -> int:
        """Clean up old session data and checkpoints."""
        cleaned_count = 0
        cutoff_time = datetime.now().timestamp() - (max_age_days * 86400)
        
        try:
            if not self._session_persistence_dir.exists():
                return 0
            
            for session_file in self._session_persistence_dir.iterdir():
                if session_file.stat().st_mtime < cutoff_time:
                    session_file.unlink()
                    cleaned_count += 1
                    logger.debug(f"Cleaned up old session file: {session_file.name}")
            
            logger.info(f"Cleaned up {cleaned_count} old session files")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old sessions: {str(e)}")
            return cleaned_count
    
    async def _session_checkpoint_manager(self, session_id: str, task_id: str):
        """Background task to create periodic checkpoints."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self.config.session_checkpoint_interval)
                await self.create_session_checkpoint(session_id, task_id)
                
            except Exception as e:
                logger.error(f"Checkpoint manager error for session {session_id}: {str(e)}")
    
    async def _session_heartbeat_manager(self, session_id: str):
        """Background task to maintain session heartbeat."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self.config.session_heartbeat_interval)
                await self._update_session_heartbeat(session_id)
                
            except Exception as e:
                logger.error(f"Heartbeat manager error for session {session_id}: {str(e)}")
    
    async def _update_session_heartbeat(self, session_id: str):
        """Update session heartbeat with current status."""
        try:
            # Find progress by session_id
            progress = None
            for task_id, task_progress in self.task_progress.items():
                if task_progress.session_id == session_id:
                    progress = task_progress
                    break
            
            if not progress:
                return
            
            # Calculate health score
            health_score = await self._calculate_session_health(session_id)
            
            # Get memory usage
            import psutil
            memory_mb = psutil.Process().memory_info().rss / 1024 / 1024
            
            # Create heartbeat
            heartbeat = SessionHeartbeat(
                session_id=session_id,
                timestamp=datetime.now(),
                status=progress.status,
                urls_processed=progress.urls_processed,
                urls_remaining=progress.urls_queued - progress.urls_processed,
                current_url=progress.current_url,
                memory_usage_mb=memory_mb,
                browser_pages_active=len(self.browser_manager.get_active_pages()),
                health_score=health_score
            )
            
            # Save heartbeat
            self._session_heartbeats[session_id] = heartbeat
            if self.config.enable_session_persistence:
                await self._save_heartbeat_to_disk(heartbeat)
            
        except Exception as e:
            logger.error(f"Failed to update heartbeat for session {session_id}: {str(e)}")
    
    async def _calculate_session_health(self, session_id: str) -> float:
        """Calculate a health score for the session (0.0 to 1.0)."""
        health_factors = []
        
        try:
            # Memory usage factor (lower is better)
            import psutil
            memory_mb = psutil.Process().memory_info().rss / 1024 / 1024
            memory_factor = max(0.0, 1.0 - (memory_mb / self.config.max_memory_usage_mb))
            health_factors.append(memory_factor)
            
            # Browser health factor
            browser_info = self.browser_manager.get_session_info()
            if browser_info:
                page_factor = max(0.0, 1.0 - (browser_info.pages_opened / 50.0))  # Assume 50 pages is unhealthy
                health_factors.append(page_factor)
            
            # Circuit breaker factor (fewer failures is better)
            total_failures = sum(self._circuit_breaker_failures.values())
            failure_factor = max(0.0, 1.0 - (total_failures / 20.0))  # Assume 20 total failures is unhealthy
            health_factors.append(failure_factor)
            
            # Processing rate factor
            for task_id, task_progress in self.task_progress.items():
                if task_progress.session_id == session_id:
                    if task_progress.urls_processed > 0:
                        success_rate = task_progress.urls_successful / task_progress.urls_processed
                        health_factors.append(success_rate)
                    break
            
            # Return average health score
            return sum(health_factors) / len(health_factors) if health_factors else 0.5
            
        except Exception as e:
            logger.error(f"Failed to calculate health for session {session_id}: {str(e)}")
            return 0.5
    
    async def _save_checkpoint_to_disk(self, checkpoint: SessionCheckpoint):
        """Save checkpoint to disk for persistence."""
        try:
            checkpoint_file = self._session_persistence_dir / f"checkpoint_{checkpoint.session_id}.json"
            checkpoint_data = checkpoint.model_dump_json(indent=2)
            
            with open(checkpoint_file, 'w') as f:
                f.write(checkpoint_data)
                
        except Exception as e:
            logger.error(f"Failed to save checkpoint to disk: {str(e)}")
    
    async def _save_heartbeat_to_disk(self, heartbeat: SessionHeartbeat):
        """Save heartbeat to disk for monitoring."""
        try:
            heartbeat_file = self._session_persistence_dir / f"heartbeat_{heartbeat.session_id}.json"
            heartbeat_data = heartbeat.model_dump_json(indent=2)
            
            with open(heartbeat_file, 'w') as f:
                f.write(heartbeat_data)
                
        except Exception as e:
            logger.error(f"Failed to save heartbeat to disk: {str(e)}")
    
    async def _load_checkpoint_from_disk(self, session_id: str) -> Optional[SessionCheckpoint]:
        """Load checkpoint from disk."""
        try:
            checkpoint_file = self._session_persistence_dir / f"checkpoint_{session_id}.json"
            if not checkpoint_file.exists():
                return None
            
            with open(checkpoint_file, 'r') as f:
                checkpoint_data = json.load(f)
            
            return SessionCheckpoint(**checkpoint_data)
            
        except Exception as e:
            logger.error(f"Failed to load checkpoint from disk: {str(e)}")
            return None
    
    async def _analyze_session_recovery(self, checkpoint: SessionCheckpoint) -> SessionRecoveryInfo:
        """Analyze if a session can be recovered and how."""
        try:
            now = datetime.now()
            checkpoint_age = (now - checkpoint.checkpoint_time).total_seconds()
            
            # Check if checkpoint is too old
            if checkpoint_age > self.config.max_session_duration:
                return SessionRecoveryInfo(
                    session_id=checkpoint.session_id,
                    task_id=checkpoint.task_id,
                    last_checkpoint=checkpoint.checkpoint_time,
                    last_heartbeat=checkpoint.checkpoint_time,
                    status="expired",
                    recovery_possible=False,
                    estimated_progress=0.0,
                    urls_remaining=0,
                    crash_reason="Session too old to recover",
                    recovery_strategy="restart"
                )
            
            # Calculate progress and remaining work
            progress_data = checkpoint.progress_snapshot
            urls_processed = progress_data.get("urls_processed", 0)
            urls_queued = progress_data.get("urls_queued", 0)
            estimated_progress = (urls_processed / urls_queued * 100) if urls_queued > 0 else 0
            urls_remaining = urls_queued - urls_processed
            
            # Determine recovery strategy
            recovery_strategy = "resume"
            if estimated_progress > 90:
                recovery_strategy = "skip"  # Nearly complete, not worth recovering
            elif checkpoint_age > 3600:  # More than 1 hour old
                recovery_strategy = "restart"
            
            return SessionRecoveryInfo(
                session_id=checkpoint.session_id,
                task_id=checkpoint.task_id,
                last_checkpoint=checkpoint.checkpoint_time,
                last_heartbeat=checkpoint.checkpoint_time,
                status="recoverable",
                recovery_possible=True,
                estimated_progress=estimated_progress,
                urls_remaining=urls_remaining,
                recovery_strategy=recovery_strategy
            )
            
        except Exception as e:
            logger.error(f"Failed to analyze session recovery: {str(e)}")
            return SessionRecoveryInfo(
                session_id=checkpoint.session_id,
                task_id=checkpoint.task_id,
                last_checkpoint=checkpoint.checkpoint_time,
                last_heartbeat=checkpoint.checkpoint_time,
                status="unknown",
                recovery_possible=False,
                estimated_progress=0.0,
                urls_remaining=0,
                crash_reason=str(e),
                recovery_strategy="restart"
            )
    
    async def _restore_session_state(self, checkpoint: SessionCheckpoint):
        """Restore session state from checkpoint."""
        try:
            # Restore circuit breaker state
            self._circuit_breaker_failures = checkpoint.circuit_breaker_state.get("failures", {})
            
            # Restore adaptive delays
            self._adaptive_delays = checkpoint.adaptive_delays_state
            
            # Restore crawler state if possible
            await self.crawler.load_queue_state(checkpoint.session_id)
            
            logger.info(f"Restored session state for {checkpoint.session_id}")
            
        except Exception as e:
            logger.error(f"Failed to restore session state: {str(e)}")