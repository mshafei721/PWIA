"""Browser management using Playwright for web automation."""
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from agent.utils import setup_logging

logger = logging.getLogger(__name__)


class BrowserConfig(BaseModel):
    """Configuration for browser management."""
    browser_type: str = "chromium"  # chromium, firefox, webkit
    headless: bool = True
    user_agent: Optional[str] = None
    viewport: Dict[str, int] = Field(default_factory=lambda: {"width": 1920, "height": 1080})
    timeout: int = 30000  # milliseconds
    slow_mo: int = 0  # milliseconds to slow down operations
    args: List[str] = Field(default_factory=lambda: [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled"
    ])
    locale: str = "en-US"
    timezone_id: str = "America/New_York"
    geolocation: Optional[Dict[str, float]] = None
    permissions: List[str] = Field(default_factory=list)
    ignore_https_errors: bool = True
    java_script_enabled: bool = True
    extra_http_headers: Dict[str, str] = Field(default_factory=dict)


class BrowserSession(BaseModel):
    """Information about an active browser session."""
    session_id: str
    browser_type: str
    headless: bool
    start_time: datetime
    pages_opened: int = 0
    contexts_created: int = 0
    is_active: bool = True
    last_activity: datetime = Field(default_factory=datetime.now)


class BrowserManager:
    """Manages Playwright browser instances with context isolation."""
    
    def __init__(self, config: Optional[BrowserConfig] = None):
        """Initialize browser manager with configuration."""
        self.config = config or BrowserConfig()
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.contexts: Dict[str, BrowserContext] = {}
        self.pages: Dict[str, Page] = {}
        self.session: Optional[BrowserSession] = None
        self._is_running = False
        
        logger.info(f"BrowserManager initialized with {self.config.browser_type} browser")
    
    async def launch_browser(self, session_id: str) -> bool:
        """Launch browser with configured settings."""
        try:
            if self._is_running:
                logger.warning("Browser already running, closing previous instance")
                await self.close_browser()
            
            # Start Playwright
            self.playwright = await async_playwright().start()
            
            # Select browser type
            if self.config.browser_type == "chromium":
                browser_type = self.playwright.chromium
            elif self.config.browser_type == "firefox":
                browser_type = self.playwright.firefox
            elif self.config.browser_type == "webkit":
                browser_type = self.playwright.webkit
            else:
                raise ValueError(f"Unsupported browser type: {self.config.browser_type}")
            
            # Launch browser
            self.browser = await browser_type.launch(
                headless=self.config.headless,
                slow_mo=self.config.slow_mo,
                args=self.config.args,
                timeout=self.config.timeout
            )
            
            # Create session tracking
            self.session = BrowserSession(
                session_id=session_id,
                browser_type=self.config.browser_type,
                headless=self.config.headless,
                start_time=datetime.now()
            )
            
            self._is_running = True
            logger.info(f"Browser launched successfully for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to launch browser: {e}")
            await self._cleanup_on_error()
            return False
    
    async def create_context(self, context_id: str, 
                           custom_config: Optional[Dict[str, Any]] = None) -> Optional[BrowserContext]:
        """Create a new browser context with isolation."""
        try:
            if not self.browser:
                logger.error("Browser not launched, cannot create context")
                return None
            
            # Prepare context options
            context_options = {
                "viewport": self.config.viewport,
                "user_agent": self.config.user_agent,
                "locale": self.config.locale,
                "timezone_id": self.config.timezone_id,
                "permissions": self.config.permissions,
                "ignore_https_errors": self.config.ignore_https_errors,
                "java_script_enabled": self.config.java_script_enabled,
                "extra_http_headers": self.config.extra_http_headers
            }
            
            # Apply custom configuration
            if custom_config:
                context_options.update(custom_config)
            
            # Add geolocation if specified
            if self.config.geolocation:
                context_options["geolocation"] = self.config.geolocation
            
            # Remove None values
            context_options = {k: v for k, v in context_options.items() if v is not None}
            
            # Create context
            context = await self.browser.new_context(**context_options)
            
            # Set default timeout
            context.set_default_timeout(self.config.timeout)
            
            # Store context
            self.contexts[context_id] = context
            
            # Update session stats
            if self.session:
                self.session.contexts_created += 1
                self.session.last_activity = datetime.now()
            
            logger.info(f"Browser context created: {context_id}")
            return context
            
        except Exception as e:
            logger.error(f"Failed to create browser context {context_id}: {e}")
            return None
    
    async def get_page(self, page_id: str, context_id: str = "default") -> Optional[Page]:
        """Get or create a page in the specified context."""
        try:
            # Check if page already exists
            if page_id in self.pages:
                page = self.pages[page_id]
                if not page.is_closed():
                    logger.debug(f"Returning existing page: {page_id}")
                    return page
                else:
                    # Remove closed page
                    del self.pages[page_id]
            
            # Get or create context
            context = self.contexts.get(context_id)
            if not context:
                context = await self.create_context(context_id)
                if not context:
                    logger.error(f"Failed to create context for page {page_id}")
                    return None
            
            # Create new page
            page = await context.new_page()
            
            # Set page timeout
            page.set_default_timeout(self.config.timeout)
            
            # Store page
            self.pages[page_id] = page
            
            # Update session stats
            if self.session:
                self.session.pages_opened += 1
                self.session.last_activity = datetime.now()
            
            logger.info(f"New page created: {page_id} in context {context_id}")
            return page
            
        except Exception as e:
            logger.error(f"Failed to create page {page_id}: {e}")
            return None
    
    async def close_page(self, page_id: str) -> bool:
        """Close a specific page."""
        try:
            page = self.pages.get(page_id)
            if not page:
                logger.warning(f"Page {page_id} not found")
                return False
            
            if not page.is_closed():
                await page.close()
            
            del self.pages[page_id]
            
            # Update session activity
            if self.session:
                self.session.last_activity = datetime.now()
            
            logger.info(f"Page closed: {page_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to close page {page_id}: {e}")
            return False
    
    async def close_context(self, context_id: str) -> bool:
        """Close a browser context and all its pages."""
        try:
            context = self.contexts.get(context_id)
            if not context:
                logger.warning(f"Context {context_id} not found")
                return False
            
            # Close all pages in this context first
            pages_to_close = [
                page_id for page_id, page in self.pages.items()
                if page.context == context
            ]
            
            for page_id in pages_to_close:
                await self.close_page(page_id)
            
            # Close context
            await context.close()
            del self.contexts[context_id]
            
            # Update session activity
            if self.session:
                self.session.last_activity = datetime.now()
            
            logger.info(f"Context closed: {context_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to close context {context_id}: {e}")
            return False
    
    async def close_browser(self) -> bool:
        """Close browser and clean up resources."""
        try:
            success = True
            
            # Close all pages
            for page_id in list(self.pages.keys()):
                if not await self.close_page(page_id):
                    success = False
            
            # Close all contexts
            for context_id in list(self.contexts.keys()):
                if not await self.close_context(context_id):
                    success = False
            
            # Close browser
            if self.browser:
                await self.browser.close()
                self.browser = None
            
            # Stop Playwright
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
            
            # Update session
            if self.session:
                self.session.is_active = False
                self.session.last_activity = datetime.now()
            
            self._is_running = False
            logger.info("Browser closed successfully")
            return success
            
        except Exception as e:
            logger.error(f"Error closing browser: {e}")
            await self._cleanup_on_error()
            return False
    
    async def _cleanup_on_error(self):
        """Force cleanup on error conditions."""
        try:
            self.pages.clear()
            self.contexts.clear()
            
            if self.browser:
                try:
                    await self.browser.close()
                except:
                    pass
                self.browser = None
            
            if self.playwright:
                try:
                    await self.playwright.stop()
                except:
                    pass
                self.playwright = None
            
            if self.session:
                self.session.is_active = False
            
            self._is_running = False
            logger.info("Emergency cleanup completed")
            
        except Exception as cleanup_error:
            logger.error(f"Error during cleanup: {cleanup_error}")
    
    def is_running(self) -> bool:
        """Check if browser is currently running."""
        return self._is_running and self.browser is not None
    
    def get_session_info(self) -> Optional[BrowserSession]:
        """Get current browser session information."""
        return self.session
    
    def get_active_pages(self) -> List[str]:
        """Get list of active page IDs."""
        active_pages = []
        for page_id, page in self.pages.items():
            if not page.is_closed():
                active_pages.append(page_id)
        return active_pages
    
    def get_active_contexts(self) -> List[str]:
        """Get list of active context IDs."""
        return list(self.contexts.keys())
    
    async def take_screenshot(self, page_id: str, 
                            screenshot_path: Optional[str] = None) -> Optional[str]:
        """Take a screenshot of the specified page."""
        try:
            page = self.pages.get(page_id)
            if not page or page.is_closed():
                logger.error(f"Page {page_id} not available for screenshot")
                return None
            
            # Generate screenshot path if not provided
            if not screenshot_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = f"screenshot_{page_id}_{timestamp}.png"
            
            # Ensure directory exists
            screenshot_file = Path(screenshot_path)
            screenshot_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Take screenshot
            await page.screenshot(path=str(screenshot_file))
            
            logger.info(f"Screenshot saved: {screenshot_path}")
            return str(screenshot_file)
            
        except Exception as e:
            logger.error(f"Failed to take screenshot of page {page_id}: {e}")
            return None
    
    async def execute_script(self, page_id: str, script: str) -> Any:
        """Execute JavaScript on the specified page."""
        try:
            page = self.pages.get(page_id)
            if not page or page.is_closed():
                logger.error(f"Page {page_id} not available for script execution")
                return None
            
            result = await page.evaluate(script)
            logger.debug(f"Script executed on page {page_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to execute script on page {page_id}: {e}")
            return None
    
    async def wait_for_load_state(self, page_id: str, 
                                state: str = "networkidle") -> bool:
        """Wait for page load state."""
        try:
            page = self.pages.get(page_id)
            if not page or page.is_closed():
                logger.error(f"Page {page_id} not available")
                return False
            
            await page.wait_for_load_state(state)
            logger.debug(f"Page {page_id} reached load state: {state}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to wait for load state on page {page_id}: {e}")
            return False
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close_browser()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit (sync wrapper)."""
        if self.is_running():
            asyncio.create_task(self.close_browser())