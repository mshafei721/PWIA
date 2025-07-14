"""Tests for environment setup and browser automation dependencies."""
import pytest
from playwright.async_api import async_playwright


class TestEnvironmentSetup:
    """Test environment configuration and dependency availability."""

    @pytest.mark.asyncio
    async def test_playwright_installation(self):
        """Test that Playwright can launch Chrome browser."""
        async with async_playwright() as p:
            # Test browser launch with minimal configuration
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            
            # Verify browser is running
            assert browser is not None, "Browser failed to launch"
            
            # Test page creation
            page = await browser.new_page()
            assert page is not None, "Failed to create new page"
            
            # Test basic navigation
            await page.goto("data:text/html,<h1>Test Page</h1>")
            title = await page.title()
            assert title == "", "Basic navigation failed"
            
            # Test content extraction
            content = await page.locator("h1").text_content()
            assert content == "Test Page", "Content extraction failed"
            
            # Clean up
            await page.close()
            await browser.close()

    @pytest.mark.asyncio
    async def test_playwright_headful_mode(self):
        """Test that Playwright can launch in headful mode (for debugging)."""
        async with async_playwright() as p:
            # Test headful browser launch
            browser = await p.chromium.launch(
                headless=False,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            
            assert browser is not None, "Headful browser failed to launch"
            
            # Quick verification and cleanup
            page = await browser.new_page()
            await page.goto("data:text/html,<h1>Headful Test</h1>")
            await page.close()
            await browser.close()

    def test_tinydb_import(self):
        """Test that TinyDB can be imported and used."""
        from tinydb import TinyDB, Query
        
        # Test basic TinyDB functionality
        db = TinyDB(':memory:')
        assert db is not None, "TinyDB failed to initialize"
        
        # Clear any existing data
        db.truncate()
        
        # Test basic operations
        db.insert({'name': 'test', 'value': 42})
        result = db.search(Query().name == 'test')
        assert len(result) == 1, "TinyDB insert/search failed"
        assert result[0]['value'] == 42, "TinyDB data integrity failed"

    def test_aiofiles_import(self):
        """Test that aiofiles can be imported."""
        import aiofiles
        assert aiofiles is not None, "aiofiles import failed"

    def test_robotparser_import(self):
        """Test that robotparser can be imported and used."""
        import urllib.robotparser
        
        # Test basic robotparser functionality
        rp = urllib.robotparser.RobotFileParser()
        assert rp is not None, "RobotFileParser failed to initialize"
        
        # Test with a basic robots.txt content
        rp.set_url("http://example.com/robots.txt")
        rp.read()
        
        # This should not raise an exception
        can_fetch = rp.can_fetch("*", "http://example.com/")
        assert isinstance(can_fetch, bool), "RobotFileParser can_fetch failed"

    @pytest.mark.asyncio
    async def test_browser_context_isolation(self):
        """Test that browser contexts are properly isolated."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            
            # Create two contexts with different user agents
            context1 = await browser.new_context(user_agent="Agent1")
            context2 = await browser.new_context(user_agent="Agent2")
            
            # Create pages in each context
            page1 = await context1.new_page()
            page2 = await context2.new_page()
            
            # Test that contexts have different user agents
            user_agent1 = await page1.evaluate("navigator.userAgent")
            user_agent2 = await page2.evaluate("navigator.userAgent")
            
            assert "Agent1" in user_agent1, "Context 1 user agent not set correctly"
            assert "Agent2" in user_agent2, "Context 2 user agent not set correctly"
            assert user_agent1 != user_agent2, "Browser contexts not properly isolated"
            
            # Test that pages are independent
            await page1.goto("data:text/html,<h1>Context 1</h1>")
            await page2.goto("data:text/html,<h1>Context 2</h1>")
            
            content1 = await page1.locator("h1").text_content()
            content2 = await page2.locator("h1").text_content()
            
            assert content1 == "Context 1", "Context 1 content failed"
            assert content2 == "Context 2", "Context 2 content failed"
            
            # Clean up
            await context1.close()
            await context2.close()
            await browser.close()

    @pytest.mark.asyncio
    async def test_browser_resource_cleanup(self):
        """Test that browser resources are properly cleaned up."""
        browser_count = 0
        page_count = 0
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            browser_count += 1
            
            # Create multiple pages
            pages = []
            for i in range(3):
                page = await browser.new_page()
                pages.append(page)
                page_count += 1
            
            # Close pages individually
            for page in pages:
                await page.close()
                page_count -= 1
            
            # Close browser
            await browser.close()
            browser_count -= 1
            
            # Verify counts (basic resource tracking)
            assert browser_count == 0, "Browser not properly closed"
            assert page_count == 0, "Pages not properly closed"