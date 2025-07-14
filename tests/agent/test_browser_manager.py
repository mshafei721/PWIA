"""Tests for BrowserManager class."""
import pytest
import tempfile
from datetime import datetime
from pathlib import Path
from agent.browser import BrowserManager, BrowserConfig, BrowserSession


class TestBrowserManager:
    """Test BrowserManager functionality."""
    
    @pytest.fixture
    def browser_config(self):
        """Create test browser configuration."""
        return BrowserConfig(
            browser_type="chromium",
            headless=True,
            timeout=10000,  # Shorter timeout for tests
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-web-security"
            ]
        )
    
    @pytest.fixture
    def browser_manager(self, browser_config):
        """Create BrowserManager instance for testing."""
        return BrowserManager(config=browser_config)
    
    @pytest.mark.asyncio
    async def test_browser_launch_headless(self, browser_manager):
        """Test launching browser in headless mode."""
        session_id = "test-session-headless"
        
        # Launch browser
        success = await browser_manager.launch_browser(session_id)
        assert success, "Failed to launch browser"
        assert browser_manager.is_running(), "Browser should be running"
        
        # Check session info
        session = browser_manager.get_session_info()
        assert session is not None, "Session info should be available"
        assert session.session_id == session_id
        assert session.browser_type == "chromium"
        assert session.headless is True
        assert session.is_active is True
        
        # Clean up
        await browser_manager.close_browser()
        assert not browser_manager.is_running(), "Browser should be stopped"
    
    @pytest.mark.asyncio
    async def test_browser_launch_headful(self):
        """Test launching browser in headful mode."""
        config = BrowserConfig(
            browser_type="chromium",
            headless=False,
            timeout=10000
        )
        
        browser_manager = BrowserManager(config=config)
        session_id = "test-session-headful"
        
        try:
            # Launch browser
            success = await browser_manager.launch_browser(session_id)
            assert success, "Failed to launch browser"
            
            # Check session info
            session = browser_manager.get_session_info()
            assert session.headless is False
            
        finally:
            await browser_manager.close_browser()
    
    @pytest.mark.asyncio
    async def test_context_creation(self, browser_manager):
        """Test creating browser contexts."""
        session_id = "test-context-session"
        
        # Launch browser first
        await browser_manager.launch_browser(session_id)
        
        try:
            # Create default context
            context1 = await browser_manager.create_context("context1")
            assert context1 is not None, "Failed to create context1"
            
            # Create context with custom config
            custom_config = {
                "user_agent": "TestAgent/1.0",
                "locale": "en-GB"
            }
            context2 = await browser_manager.create_context("context2", custom_config)
            assert context2 is not None, "Failed to create context2"
            
            # Check active contexts
            active_contexts = browser_manager.get_active_contexts()
            assert "context1" in active_contexts
            assert "context2" in active_contexts
            assert len(active_contexts) == 2
            
            # Check session stats
            session = browser_manager.get_session_info()
            assert session.contexts_created == 2
            
        finally:
            await browser_manager.close_browser()
    
    @pytest.mark.asyncio
    async def test_page_creation(self, browser_manager):
        """Test creating and managing pages."""
        session_id = "test-page-session"
        
        # Launch browser
        await browser_manager.launch_browser(session_id)
        
        try:
            # Create page (should auto-create default context)
            page1 = await browser_manager.get_page("page1")
            assert page1 is not None, "Failed to create page1"
            assert not page1.is_closed(), "Page1 should be open"
            
            # Create page in specific context
            await browser_manager.create_context("custom_context")
            page2 = await browser_manager.get_page("page2", "custom_context")
            assert page2 is not None, "Failed to create page2"
            
            # Check active pages
            active_pages = browser_manager.get_active_pages()
            assert "page1" in active_pages
            assert "page2" in active_pages
            assert len(active_pages) == 2
            
            # Check session stats
            session = browser_manager.get_session_info()
            assert session.pages_opened == 2
            
            # Test getting existing page
            existing_page = await browser_manager.get_page("page1")
            assert existing_page is page1, "Should return existing page"
            
        finally:
            await browser_manager.close_browser()
    
    @pytest.mark.asyncio
    async def test_page_navigation(self, browser_manager):
        """Test basic page navigation."""
        session_id = "test-navigation-session"
        
        # Launch browser
        await browser_manager.launch_browser(session_id)
        
        try:
            # Create page
            page = await browser_manager.get_page("nav_page")
            assert page is not None
            
            # Navigate to test page
            await page.goto("data:text/html,<h1>Test Page</h1><p>Content</p>")
            
            # Wait for page load
            success = await browser_manager.wait_for_load_state("nav_page", "domcontentloaded")
            assert success, "Failed to wait for page load"
            
            # Check page title and content
            title = await page.title()
            assert title == "", "Basic data URL navigation failed"
            
            content = await page.locator("h1").text_content()
            assert content == "Test Page", "Page content verification failed"
            
        finally:
            await browser_manager.close_browser()
    
    @pytest.mark.asyncio
    async def test_javascript_execution(self, browser_manager):
        """Test JavaScript execution on pages."""
        session_id = "test-js-session"
        
        # Launch browser
        await browser_manager.launch_browser(session_id)
        
        try:
            # Create page and navigate
            page = await browser_manager.get_page("js_page")
            await page.goto("data:text/html,<div id='test'>Initial</div>")
            
            # Execute script through BrowserManager
            result = await browser_manager.execute_script("js_page", 
                "(function() { document.getElementById('test').textContent = 'Modified'; return 'success'; })()")
            assert result == "success", "Script execution failed"
            
            # Verify modification
            content = await page.locator("#test").text_content()
            assert content == "Modified", "Script modification not applied"
            
            # Execute script returning data
            data = await browser_manager.execute_script("js_page",
                "(function() { return {url: window.location.href, title: document.title}; })()")
            assert isinstance(data, dict), "Script should return dictionary"
            assert "url" in data, "Script result should contain URL"
            
        finally:
            await browser_manager.close_browser()
    
    @pytest.mark.asyncio
    async def test_screenshot_functionality(self, browser_manager):
        """Test taking screenshots."""
        session_id = "test-screenshot-session"
        
        # Launch browser
        await browser_manager.launch_browser(session_id)
        
        try:
            # Create page with content
            page = await browser_manager.get_page("screenshot_page")
            await page.goto("data:text/html,<h1 style='color: blue;'>Screenshot Test</h1>")
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # Take screenshot with specified path
                screenshot_path = Path(temp_dir) / "test_screenshot.png"
                result_path = await browser_manager.take_screenshot(
                    "screenshot_page", 
                    str(screenshot_path)
                )
                
                assert result_path is not None, "Screenshot should succeed"
                assert Path(result_path).exists(), "Screenshot file should exist"
                assert Path(result_path).stat().st_size > 0, "Screenshot file should not be empty"
                
                # Take screenshot with auto-generated path
                auto_path = await browser_manager.take_screenshot("screenshot_page")
                assert auto_path is not None, "Auto screenshot should succeed"
                assert Path(auto_path).exists(), "Auto screenshot file should exist"
        
        finally:
            await browser_manager.close_browser()
    
    @pytest.mark.asyncio
    async def test_resource_cleanup(self, browser_manager):
        """Test proper resource cleanup."""
        session_id = "test-cleanup-session"
        
        # Launch browser and create resources
        await browser_manager.launch_browser(session_id)
        
        # Create multiple contexts and pages
        await browser_manager.create_context("ctx1")
        await browser_manager.create_context("ctx2")
        await browser_manager.get_page("page1", "ctx1")
        await browser_manager.get_page("page2", "ctx1")
        await browser_manager.get_page("page3", "ctx2")
        
        # Verify resources exist
        assert len(browser_manager.get_active_contexts()) == 2
        assert len(browser_manager.get_active_pages()) == 3
        
        # Test individual page cleanup
        success = await browser_manager.close_page("page1")
        assert success, "Page closure should succeed"
        assert len(browser_manager.get_active_pages()) == 2
        
        # Test context cleanup (should close remaining pages in context)
        success = await browser_manager.close_context("ctx1")
        assert success, "Context closure should succeed"
        assert len(browser_manager.get_active_pages()) == 1
        assert len(browser_manager.get_active_contexts()) == 1
        
        # Test full cleanup
        await browser_manager.close_browser()
        assert not browser_manager.is_running()
        assert len(browser_manager.get_active_pages()) == 0
        assert len(browser_manager.get_active_contexts()) == 0
    
    @pytest.mark.asyncio
    async def test_error_handling(self, browser_manager):
        """Test error handling scenarios."""
        # Test operations without launching browser
        page = await browser_manager.get_page("error_page")
        assert page is None, "Should fail when browser not launched"
        
        context = await browser_manager.create_context("error_context")
        assert context is None, "Should fail when browser not launched"
        
        # Test invalid page operations
        screenshot = await browser_manager.take_screenshot("nonexistent_page")
        assert screenshot is None, "Should fail for nonexistent page"
        
        script_result = await browser_manager.execute_script("nonexistent_page", "return 1;")
        assert script_result is None, "Should fail for nonexistent page"
    
    @pytest.mark.asyncio
    async def test_context_isolation(self, browser_manager):
        """Test that browser contexts are properly isolated."""
        session_id = "test-isolation-session"
        
        # Launch browser
        await browser_manager.launch_browser(session_id)
        
        try:
            # Create contexts with different user agents
            ctx1 = await browser_manager.create_context("isolated1", 
                                                      {"user_agent": "Agent1"})
            ctx2 = await browser_manager.create_context("isolated2", 
                                                      {"user_agent": "Agent2"})
            
            # Create pages in each context
            page1 = await browser_manager.get_page("page1", "isolated1")
            page2 = await browser_manager.get_page("page2", "isolated2")
            
            # Navigate to test pages
            await page1.goto("data:text/html,<div>Context 1</div>")
            await page2.goto("data:text/html,<div>Context 2</div>")
            
            # Check user agents are different
            ua1 = await page1.evaluate("navigator.userAgent")
            ua2 = await page2.evaluate("navigator.userAgent")
            
            assert "Agent1" in ua1, "Context 1 user agent not set"
            assert "Agent2" in ua2, "Context 2 user agent not set"
            assert ua1 != ua2, "Contexts should have different user agents"
            
        finally:
            await browser_manager.close_browser()
    
    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test BrowserManager as async context manager."""
        config = BrowserConfig(headless=True, timeout=10000)
        
        async with BrowserManager(config=config) as browser_manager:
            # Launch browser
            success = await browser_manager.launch_browser("context-manager-test")
            assert success, "Browser should launch"
            assert browser_manager.is_running(), "Browser should be running"
            
            # Create a page
            page = await browser_manager.get_page("test_page")
            assert page is not None, "Page should be created"
        
        # Browser should be automatically closed
        assert not browser_manager.is_running(), "Browser should be closed after context exit"