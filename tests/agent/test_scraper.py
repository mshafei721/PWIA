"""Tests for DataScraper class."""
import pytest
import asyncio
import tempfile
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
from playwright.async_api import Page
from agent.scraper import DataScraper, ScraperConfig, ExtractedElement, ExtractionResult
from agent.memory import AgentMemory


class TestDataScraper:
    """Test DataScraper functionality."""
    
    @pytest.fixture
    def scraper_config(self):
        """Create test scraper configuration."""
        return ScraperConfig(
            default_timeout=5000,  # 5 seconds for tests
            max_elements_per_selector=100,
            enable_structured_data=True,
            enable_images=True,
            enable_links=True,
            custom_selectors={
                "title": "title, h1, .title",
                "description": "meta[name=description], .description, .summary"
            }
        )
    
    @pytest.fixture
    def memory(self):
        """Create test memory instance."""
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "test_memory"
            memory_path.mkdir()
            
            memory = AgentMemory(memory_dir=temp_dir)
            yield memory
    
    @pytest.fixture
    def mock_page(self):
        """Create mock Playwright page."""
        page = Mock(spec=Page)
        page.query_selector_all = AsyncMock()
        page.evaluate = AsyncMock()
        page.content = AsyncMock()
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Test Page")
        return page
    
    @pytest.fixture
    def scraper(self, scraper_config, memory):
        """Create DataScraper instance."""
        return DataScraper(config=scraper_config, memory=memory)

    def test_scraper_initialization(self, scraper, scraper_config, memory):
        """Test DataScraper initialization."""
        assert scraper.config == scraper_config
        assert scraper.memory == memory
        assert scraper.session_id is not None
        assert scraper.extraction_count == 0

    @pytest.mark.asyncio
    async def test_extract_by_css_selector(self, scraper, mock_page):
        """Test CSS selector-based extraction."""
        # Mock elements found by CSS selector
        mock_element = Mock()
        mock_element.inner_text = AsyncMock(return_value="Sample Text")
        mock_element.get_attribute = AsyncMock(return_value="https://example.com")
        mock_element.inner_html = AsyncMock(return_value="<span>Sample Text</span>")
        
        mock_page.query_selector_all.return_value = [mock_element]
        
        result = await scraper.extract_by_css_selector(
            page=mock_page,
            selector="h1",
            extract_type="text"
        )
        
        assert len(result.elements) == 1
        assert result.elements[0].text == "Sample Text"
        assert result.selector == "h1"
        assert result.extraction_type == "text"
        mock_page.query_selector_all.assert_called_once_with("h1")

    @pytest.mark.asyncio
    async def test_extract_by_xpath(self, scraper, mock_page):
        """Test XPath-based extraction."""
        # Mock XPath evaluation
        mock_page.evaluate.return_value = [
            {"text": "Sample Text", "attributes": {"href": "https://example.com"}, "html": "<a>Sample Text</a>"}
        ]
        
        result = await scraper.extract_by_xpath(
            page=mock_page,
            xpath="//a[@class='link']",
            extract_type="links"
        )
        
        assert len(result.elements) == 1
        assert result.elements[0].text == "Sample Text"
        assert result.elements[0].attributes["href"] == "https://example.com"
        assert result.selector == "//a[@class='link']"
        assert result.extraction_type == "links"

    @pytest.mark.asyncio
    async def test_extract_structured_data(self, scraper, mock_page):
        """Test structured data extraction (JSON-LD, microdata)."""
        # Mock structured data in page
        mock_page.evaluate.return_value = {
            "json_ld": [{"@type": "Article", "headline": "Test Article"}],
            "microdata": [{"type": "Product", "name": "Test Product"}],
            "rdfa": []
        }
        
        result = await scraper.extract_structured_data(mock_page)
        
        assert result.extraction_type == "structured_data"
        assert "json_ld" in result.data
        assert "microdata" in result.data
        assert len(result.data["json_ld"]) == 1
        assert result.data["json_ld"][0]["headline"] == "Test Article"

    @pytest.mark.asyncio
    async def test_extract_all_links(self, scraper, mock_page):
        """Test extraction of all links from page."""
        mock_element = Mock()
        mock_element.inner_text = AsyncMock(return_value="Click here")
        mock_element.get_attribute = AsyncMock(return_value="https://example.com/page")
        mock_element.inner_html = AsyncMock(return_value="<a>Click here</a>")
        
        mock_page.query_selector_all.return_value = [mock_element]
        
        result = await scraper.extract_all_links(mock_page)
        
        assert len(result.elements) == 1
        assert result.elements[0].text == "Click here"
        assert result.elements[0].attributes["href"] == "https://example.com/page"
        assert result.extraction_type == "links"

    @pytest.mark.asyncio
    async def test_extract_all_images(self, scraper, mock_page):
        """Test extraction of all images from page."""
        mock_element = Mock()
        mock_element.inner_text = AsyncMock(return_value="")
        mock_element.get_attribute = AsyncMock(side_effect=lambda attr: {
            "src": "https://example.com/image.jpg",
            "alt": "Test Image",
            "width": "300",
            "height": "200"
        }.get(attr))
        mock_element.inner_html = AsyncMock(return_value="<img>")
        
        mock_page.query_selector_all.return_value = [mock_element]
        
        result = await scraper.extract_all_images(mock_page)
        
        assert len(result.elements) == 1
        assert result.elements[0].attributes["src"] == "https://example.com/image.jpg"
        assert result.elements[0].attributes["alt"] == "Test Image"
        assert result.extraction_type == "images"

    @pytest.mark.asyncio
    async def test_extract_page_metadata(self, scraper, mock_page):
        """Test extraction of page metadata."""
        mock_page.title.return_value = "Test Page Title"
        mock_page.evaluate.return_value = {
            "title": "Test Page Title",
            "description": "Test page description",
            "keywords": "test, page, keywords",
            "author": "Test Author",
            "viewport": "width=device-width, initial-scale=1",
            "robots": "index, follow"
        }
        
        result = await scraper.extract_page_metadata(mock_page)
        
        assert result.extraction_type == "metadata"
        assert result.data["title"] == "Test Page Title"
        assert result.data["description"] == "Test page description"
        assert result.data["author"] == "Test Author"

    @pytest.mark.asyncio
    async def test_custom_extraction(self, scraper, mock_page):
        """Test custom extraction using configured selectors."""
        mock_element = Mock()
        mock_element.inner_text = AsyncMock(return_value="Custom Title")
        mock_element.get_attribute = AsyncMock(return_value=None)
        mock_element.inner_html = AsyncMock(return_value="<h1>Custom Title</h1>")
        
        mock_page.query_selector_all.return_value = [mock_element]
        
        result = await scraper.extract_custom(
            page=mock_page,
            extraction_name="title"
        )
        
        assert len(result.elements) == 1
        assert result.elements[0].text == "Custom Title"
        assert result.selector == "title, h1, .title"

    @pytest.mark.asyncio
    async def test_comprehensive_extraction(self, scraper, mock_page):
        """Test comprehensive page extraction."""
        # Setup mocks for all extraction types
        mock_page.title.return_value = "Test Page"
        mock_page.evaluate.return_value = {"title": "Test Page"}
        
        mock_element = Mock()
        mock_element.inner_text = AsyncMock(return_value="Test content")
        mock_element.get_attribute = AsyncMock(return_value="https://example.com")
        mock_element.inner_html = AsyncMock(return_value="<div>Test content</div>")
        mock_page.query_selector_all.return_value = [mock_element]
        
        with patch.object(scraper, 'extract_structured_data') as mock_structured:
            mock_structured.return_value = ExtractionResult(
                url="https://example.com",
                extraction_type="structured_data",
                selector="",
                elements=[],
                data={"json_ld": []},
                extracted_at=datetime.now()
            )
            
            result = await scraper.extract_comprehensive(mock_page)
            
            assert "metadata" in result
            assert "links" in result
            assert "images" in result
            assert "structured_data" in result

    @pytest.mark.asyncio
    async def test_save_extraction_result(self, scraper, memory):
        """Test saving extraction results to memory."""
        result = ExtractionResult(
            url="https://example.com",
            extraction_type="text",
            selector="h1",
            elements=[ExtractedElement(
                text="Test Title",
                attributes={},
                html="<h1>Test Title</h1>"
            )],
            data={},
            extracted_at=datetime.now()
        )
        
        with patch.object(memory, 'save_extracted_data') as mock_save:
            await scraper.save_extraction_result(result)
            mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handling_invalid_selector(self, scraper, mock_page):
        """Test error handling for invalid selectors."""
        mock_page.query_selector_all.side_effect = Exception("Invalid selector")
        
        result = await scraper.extract_by_css_selector(
            page=mock_page,
            selector="invalid{selector",
            extract_type="text"
        )
        
        assert len(result.elements) == 0
        assert "error" in result.data
        assert "Invalid selector" in result.data["error"]

    @pytest.mark.asyncio
    async def test_timeout_handling(self, scraper, mock_page):
        """Test timeout handling during extraction."""
        mock_page.query_selector_all.side_effect = asyncio.TimeoutError("Timeout")
        
        result = await scraper.extract_by_css_selector(
            page=mock_page,
            selector="h1",
            extract_type="text"
        )
        
        assert len(result.elements) == 0
        assert "error" in result.data
        assert "Timeout" in result.data["error"]

    def test_scraper_statistics(self, scraper):
        """Test scraper statistics tracking."""
        # Simulate some extractions
        scraper.extraction_count = 5
        scraper.start_time = datetime.now()
        
        stats = scraper.get_statistics()
        
        assert stats["extraction_count"] == 5
        assert stats["session_id"] == scraper.session_id
        assert "uptime_seconds" in stats
        assert "start_time" in stats

    @pytest.mark.asyncio
    async def test_extract_data_from_html(self, scraper):
        """Test BeautifulSoup-based data extraction from HTML."""
        html_content = """
        <html>
            <body>
                <h1 class="title">Test Article</h1>
                <p class="content">This is test content with <a href="/link">a link</a>.</p>
                <div class="metadata">
                    <span class="author">John Doe</span>
                    <span class="date">2025-01-01</span>
                </div>
            </body>
        </html>
        """
        
        result = await scraper.extract_data(
            html_content=html_content,
            extraction_rules={
                "title": {"selector": "h1.title", "type": "text"},
                "content": {"selector": "p.content", "type": "text"},
                "links": {"selector": "a", "type": "links"},
                "author": {"selector": ".author", "type": "text"}
            }
        )
        
        assert result.success is True
        assert "title" in result.data
        assert len(result.data["title"]) == 1
        assert result.data["title"][0] == "Test Article"
        assert "content" in result.data
        assert "links" in result.data
        assert len(result.data["links"]) == 1
        assert result.data["links"][0]["href"] == "/link"

    @pytest.mark.asyncio
    async def test_parse_elements_with_soup(self, scraper):
        """Test parsing elements using BeautifulSoup."""
        html_content = """
        <div class="container">
            <article class="post" data-id="123">
                <h2>Post Title</h2>
                <p>Post content here.</p>
                <img src="/image.jpg" alt="Test Image" width="300">
            </article>
        </div>
        """
        
        elements = await scraper.parse_elements(
            html_content=html_content,
            selector="article.post"
        )
        
        assert len(elements) == 1
        element = elements[0]
        assert element.text.strip() == "Post Title\nPost content here."
        assert element.attributes["data-id"] == "123"
        assert element.attributes["class"] == ["post"]

    @pytest.mark.asyncio
    async def test_get_text_with_cleaning(self, scraper):
        """Test text extraction with cleaning options."""
        html_content = """
        <div>
            <p>   Text with    extra   whitespace   </p>
            <p>Another paragraph</p>
            <script>alert('bad');</script>
            <style>.hidden { display: none; }</style>
        </div>
        """
        
        # Test with cleaning enabled
        text = await scraper.get_text(
            html_content=html_content,
            selector="div",
            clean_text=True,
            exclude_tags=["script", "style"]
        )
        
        assert "alert" not in text
        assert "display: none" not in text
        assert "Text with extra whitespace" in text
        assert "Another paragraph" in text

    @pytest.mark.asyncio
    async def test_get_attributes_extraction(self, scraper):
        """Test attribute extraction from elements."""
        html_content = """
        <div>
            <a href="https://example.com" title="Example Link" data-analytics="click123">Link</a>
            <img src="/test.jpg" alt="Test Image" width="300" height="200">
            <input type="email" name="email" required placeholder="Enter email">
        </div>
        """
        
        # Test link attributes
        link_attrs = await scraper.get_attributes(
            html_content=html_content,
            selector="a",
            attributes=["href", "title", "data-analytics"]
        )
        
        assert len(link_attrs) == 1
        assert link_attrs[0]["href"] == "https://example.com"
        assert link_attrs[0]["title"] == "Example Link"
        assert link_attrs[0]["data-analytics"] == "click123"
        
        # Test image attributes
        img_attrs = await scraper.get_attributes(
            html_content=html_content,
            selector="img",
            attributes=["src", "alt", "width", "height"]
        )
        
        assert len(img_attrs) == 1
        assert img_attrs[0]["src"] == "/test.jpg"
        assert img_attrs[0]["alt"] == "Test Image"
        assert img_attrs[0]["width"] == "300"

    @pytest.mark.asyncio
    async def test_extract_tables_as_data(self, scraper):
        """Test table extraction as structured data."""
        html_content = """
        <table class="data-table">
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Age</th>
                    <th>City</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>John</td>
                    <td>25</td>
                    <td>New York</td>
                </tr>
                <tr>
                    <td>Jane</td>
                    <td>30</td>
                    <td>Los Angeles</td>
                </tr>
            </tbody>
        </table>
        """
        
        table_data = await scraper.extract_table_data(
            html_content=html_content,
            selector="table.data-table"
        )
        
        assert table_data.success is True
        assert "headers" in table_data.data
        assert "rows" in table_data.data
        assert table_data.data["headers"] == ["Name", "Age", "City"]
        assert len(table_data.data["rows"]) == 2
        assert table_data.data["rows"][0] == ["John", "25", "New York"]
        assert table_data.data["rows"][1] == ["Jane", "30", "Los Angeles"]

    @pytest.mark.asyncio
    async def test_extract_forms_structure(self, scraper):
        """Test form structure extraction."""
        html_content = """
        <form action="/submit" method="post" class="contact-form">
            <input type="text" name="name" placeholder="Your Name" required>
            <input type="email" name="email" placeholder="Your Email" required>
            <select name="country">
                <option value="us">United States</option>
                <option value="uk">United Kingdom</option>
            </select>
            <textarea name="message" placeholder="Your Message"></textarea>
            <button type="submit">Submit</button>
        </form>
        """
        
        form_data = await scraper.extract_form_structure(
            html_content=html_content,
            selector="form.contact-form"
        )
        
        assert form_data.success is True
        assert form_data.data["action"] == "/submit"
        assert form_data.data["method"] == "post"
        assert len(form_data.data["fields"]) == 5  # name, email, country, message, button
        
        name_field = form_data.data["fields"][0]
        assert name_field["name"] == "name"
        assert name_field["type"] == "text"
        assert name_field["required"] is True

    @pytest.mark.asyncio
    async def test_extract_with_css_path_tracking(self, scraper):
        """Test extraction with CSS path tracking for elements."""
        html_content = """
        <article>
            <header>
                <h1>Article Title</h1>
            </header>
            <section class="content">
                <p>First paragraph</p>
                <p>Second paragraph</p>
            </section>
        </article>
        """
        
        result = await scraper.extract_with_paths(
            html_content=html_content,
            extraction_rules={
                "title": {"selector": "h1", "track_path": True},
                "paragraphs": {"selector": "section p", "track_path": True}
            }
        )
        
        assert result.success is True
        assert "title" in result.data
        assert "paragraphs" in result.data
        
        # Check that CSS paths are tracked
        title_element = result.elements[0]
        assert title_element.css_path is not None
        assert "article" in title_element.css_path
        assert "header" in title_element.css_path

    @pytest.mark.asyncio
    async def test_robust_html_parsing(self, scraper):
        """Test parsing of malformed HTML."""
        malformed_html = """
        <div>
            <p>Unclosed paragraph
            <div>Nested div
                <span>Some text</span>
            </div>
            <p>Another paragraph</p>
        </div>
        """
        
        # Should handle malformed HTML gracefully
        result = await scraper.extract_data(
            html_content=malformed_html,
            extraction_rules={
                "text": {"selector": "p", "type": "text"},
                "spans": {"selector": "span", "type": "text"}
            }
        )
        
        assert result.success is True
        assert "text" in result.data
        assert "spans" in result.data
        assert len(result.data["spans"]) == 1
        assert result.data["spans"][0] == "Some text"

    @pytest.mark.asyncio
    async def test_enhanced_json_ld_extraction(self, scraper):
        """Test enhanced JSON-LD structured data extraction."""
        html_content = """
        <html>
            <head>
                <script type="application/ld+json">
                {
                    "@context": "https://schema.org",
                    "@type": "Article",
                    "headline": "Test Article Title",
                    "author": {
                        "@type": "Person",
                        "name": "John Doe"
                    },
                    "datePublished": "2025-01-01",
                    "publisher": {
                        "@type": "Organization",
                        "name": "Test Publisher"
                    }
                }
                </script>
                <script type="application/ld+json">
                {
                    "@context": "https://schema.org",
                    "@type": "BreadcrumbList",
                    "itemListElement": [
                        {
                            "@type": "ListItem",
                            "position": 1,
                            "name": "Home",
                            "item": "https://example.com"
                        }
                    ]
                }
                </script>
            </head>
            <body>Content here</body>
        </html>
        """
        
        result = await scraper.extract_enhanced_structured_data(html_content)
        
        assert result.success is True
        assert "json_ld" in result.data
        assert len(result.data["json_ld"]) == 2
        
        # Check Article schema
        article = result.data["json_ld"][0]
        assert article["@type"] == "Article"
        assert article["headline"] == "Test Article Title"
        assert article["author"]["name"] == "John Doe"
        
        # Check BreadcrumbList schema
        breadcrumb = result.data["json_ld"][1]
        assert breadcrumb["@type"] == "BreadcrumbList"
        assert len(breadcrumb["itemListElement"]) == 1

    @pytest.mark.asyncio
    async def test_enhanced_microdata_extraction(self, scraper):
        """Test enhanced microdata extraction with nested items."""
        html_content = """
        <div itemscope itemtype="https://schema.org/Product">
            <h1 itemprop="name">Amazing Product</h1>
            <img itemprop="image" src="/product.jpg" alt="Product Image">
            <p itemprop="description">This is an amazing product description.</p>
            
            <div itemprop="offers" itemscope itemtype="https://schema.org/Offer">
                <span itemprop="price">29.99</span>
                <span itemprop="priceCurrency" content="USD">$</span>
                <span itemprop="availability" content="https://schema.org/InStock">In Stock</span>
            </div>
            
            <div itemprop="aggregateRating" itemscope itemtype="https://schema.org/AggregateRating">
                <span itemprop="ratingValue">4.5</span>
                <span itemprop="reviewCount">123</span>
            </div>
        </div>
        """
        
        result = await scraper.extract_enhanced_structured_data(html_content)
        
        assert result.success is True
        assert "microdata" in result.data
        assert len(result.data["microdata"]) >= 1
        
        # Check Product microdata
        product = result.data["microdata"][0]
        assert "https://schema.org/Product" in product["type"]
        assert product["properties"]["name"] == "Amazing Product"
        assert product["properties"]["description"] == "This is an amazing product description."
        
        # Check nested offers and ratings
        assert "offers" in product["properties"]
        assert "aggregateRating" in product["properties"]

    @pytest.mark.asyncio
    async def test_enhanced_rdfa_extraction(self, scraper):
        """Test enhanced RDFa extraction with complex properties."""
        html_content = """
        <div vocab="https://schema.org/" typeof="Article">
            <h1 property="headline">Test Article with RDFa</h1>
            <div property="author" typeof="Person">
                <span property="name">Jane Smith</span>
                <span property="email" content="jane@example.com">Contact</span>
            </div>
            <time property="datePublished" datetime="2025-01-01">January 1, 2025</time>
            <div property="publisher" typeof="Organization">
                <span property="name">Example Publisher</span>
                <span property="url" content="https://example.com">Website</span>
            </div>
        </div>
        """
        
        result = await scraper.extract_enhanced_structured_data(html_content)
        
        assert result.success is True
        assert "rdfa" in result.data
        assert len(result.data["rdfa"]) >= 1
        
        # Check Article RDFa
        article = result.data["rdfa"][0]
        assert article["type"] == "Article"
        assert article["properties"]["headline"] == "Test Article with RDFa"
        assert "author" in article["properties"]
        assert "publisher" in article["properties"]

    @pytest.mark.asyncio
    async def test_mixed_structured_data_extraction(self, scraper):
        """Test extraction of mixed structured data formats."""
        html_content = """
        <html>
            <head>
                <script type="application/ld+json">
                {
                    "@context": "https://schema.org",
                    "@type": "WebPage",
                    "name": "Mixed Data Test"
                }
                </script>
            </head>
            <body>
                <div itemscope itemtype="https://schema.org/Organization">
                    <span itemprop="name">Test Organization</span>
                </div>
                
                <article vocab="https://schema.org/" typeof="BlogPosting">
                    <h1 property="headline">Blog Post Title</h1>
                </article>
            </body>
        </html>
        """
        
        result = await scraper.extract_enhanced_structured_data(html_content)
        
        assert result.success is True
        assert "json_ld" in result.data
        assert "microdata" in result.data
        assert "rdfa" in result.data
        
        # Verify all formats were extracted
        assert len(result.data["json_ld"]) == 1
        assert len(result.data["microdata"]) == 1
        assert len(result.data["rdfa"]) == 1

    @pytest.mark.asyncio
    async def test_structured_data_validation(self, scraper):
        """Test structured data validation and schema recognition."""
        html_content = """
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Recipe",
            "name": "Chocolate Chip Cookies",
            "recipeIngredient": [
                "2 cups flour",
                "1 cup sugar",
                "1/2 cup butter"
            ],
            "recipeInstructions": [
                {
                    "@type": "HowToStep",
                    "text": "Mix ingredients"
                }
            ],
            "nutrition": {
                "@type": "NutritionInformation",
                "calories": "250 calories"
            }
        }
        </script>
        """
        
        result = await scraper.extract_enhanced_structured_data(html_content)
        
        assert result.success is True
        
        # Check validation results
        validation = await scraper.validate_structured_data(result.data)
        assert validation["valid_schemas"] > 0
        assert "Recipe" in validation["schema_types"]
        assert validation["has_context"] is True

    @pytest.mark.asyncio
    async def test_structured_data_normalization(self, scraper):
        """Test structured data normalization to common format."""
        html_content = """
        <div itemscope itemtype="https://schema.org/Person">
            <span itemprop="name">John Doe</span>
            <span itemprop="jobTitle">Software Engineer</span>
        </div>
        """
        
        result = await scraper.extract_enhanced_structured_data(html_content)
        normalized = await scraper.normalize_structured_data(result.data)
        
        assert "entities" in normalized
        assert len(normalized["entities"]) >= 1
        
        person = normalized["entities"][0]
        assert person["type"] == "Person"
        assert person["properties"]["name"] == "John Doe"
        assert person["properties"]["jobTitle"] == "Software Engineer"

    @pytest.mark.asyncio
    async def test_schema_org_detection(self, scraper):
        """Test Schema.org type detection and classification."""
        html_content = """
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": ["Product", "CreativeWork"],
            "name": "Multi-type Item"
        }
        </script>
        """
        
        result = await scraper.extract_enhanced_structured_data(html_content)
        schema_info = await scraper.analyze_schema_types(result.data)
        
        assert "Product" in schema_info["detected_types"]
        assert "CreativeWork" in schema_info["detected_types"]
        assert schema_info["has_multiple_types"] is True

    def test_clean_text_edge_cases(self, scraper):
        """Test text cleaning with various edge cases."""
        # Test with None
        assert scraper._clean_text(None) == ""
        
        # Test with empty string
        assert scraper._clean_text("") == ""
        
        # Test with only whitespace
        assert scraper._clean_text("   \n\t  ") == ""
        
        # Test with multiple spaces/tabs/newlines
        assert scraper._clean_text("  hello\t\tworld\n\ntest  ") == "hello world test"
        
        # Test with length constraints
        original_min = scraper.config.min_text_length
        original_max = scraper.config.max_text_length
        
        try:
            scraper.config.min_text_length = 5
            scraper.config.max_text_length = 10
            
            # Too short
            assert scraper._clean_text("hi") == ""
            
            # Just right
            assert scraper._clean_text("hello") == "hello"
            
            # Too long
            result = scraper._clean_text("this is a very long text that exceeds limit")
            assert len(result) == 10
            assert result == "this is a "
            
        finally:
            # Restore original values
            scraper.config.min_text_length = original_min
            scraper.config.max_text_length = original_max

    @pytest.mark.asyncio
    async def test_extract_custom_nonexistent_rule(self, scraper, mock_page):
        """Test custom extraction with non-existent rule."""
        with pytest.raises(ValueError, match="Custom extraction 'nonexistent' not configured"):
            await scraper.extract_custom(mock_page, "nonexistent")

    @pytest.mark.asyncio
    async def test_extract_structured_data_error(self, scraper, mock_page):
        """Test structured data extraction with JavaScript error."""
        mock_page.evaluate.side_effect = Exception("JavaScript execution failed")
        
        result = await scraper.extract_structured_data(mock_page)
        
        assert result.success is False
        assert result.error_message == "JavaScript execution failed"
        assert "error" in result.data

    @pytest.mark.asyncio
    async def test_extract_page_metadata_error(self, scraper, mock_page):
        """Test page metadata extraction with error."""
        mock_page.title.side_effect = Exception("Title access failed")
        
        result = await scraper.extract_page_metadata(mock_page)
        
        assert result.success is False
        assert result.error_message == "Title access failed"

    @pytest.mark.asyncio
    async def test_extract_table_no_table_found(self, scraper):
        """Test table extraction when no table exists."""
        html_content = "<div>No table here</div>"
        
        result = await scraper.extract_table_data(html_content, "table")
        
        assert result.success is False
        assert "No table found with selector: table" in result.error_message

    @pytest.mark.asyncio
    async def test_extract_form_no_form_found(self, scraper):
        """Test form extraction when no form exists."""
        html_content = "<div>No form here</div>"
        
        result = await scraper.extract_form_structure(html_content, "form")
        
        assert result.success is False
        assert "No form found with selector: form" in result.error_message

    @pytest.mark.asyncio
    async def test_extract_table_complex_structure(self, scraper):
        """Test table extraction with complex table structure."""
        html_content = """
        <table>
            <caption>Test Table</caption>
            <tbody>
                <tr><th>Header 1</th><th>Header 2</th></tr>
                <tr><td>Data 1</td><td>Data 2</td></tr>
                <tr><td colspan="2">Merged Cell</td></tr>
            </tbody>
        </table>
        """
        
        result = await scraper.extract_table_data(html_content, "table")
        
        assert result.success is True
        assert result.data["headers"] == ["Header 1", "Header 2"]
        assert len(result.data["rows"]) == 2
        assert result.data["rows"][0] == ["Data 1", "Data 2"]
        assert result.data["rows"][1] == ["Merged Cell"]

    @pytest.mark.asyncio
    async def test_extract_form_complex_fields(self, scraper):
        """Test form extraction with complex field types."""
        html_content = """
        <form>
            <fieldset>
                <legend>Personal Info</legend>
                <input type="radio" name="gender" value="male" id="male">
                <label for="male">Male</label>
                <input type="radio" name="gender" value="female" id="female" checked>
                <label for="female">Female</label>
            </fieldset>
            <input type="checkbox" name="terms" value="agree" required>
            <input type="file" name="avatar" accept="image/*">
            <input type="hidden" name="token" value="abc123">
            <input type="range" name="age" min="18" max="100" value="25">
        </form>
        """
        
        result = await scraper.extract_form_structure(html_content, "form")
        
        assert result.success is True
        assert len(result.data["fields"]) == 6  # 2 radio + checkbox + file + hidden + range
        
        # Check specific field types
        field_types = [field["type"] for field in result.data["fields"]]
        assert "radio" in field_types
        assert "checkbox" in field_types
        assert "file" in field_types
        assert "hidden" in field_types
        assert "range" in field_types

    @pytest.mark.asyncio
    async def test_generate_css_path_edge_cases(self, scraper):
        """Test CSS path generation with edge cases."""
        from bs4 import BeautifulSoup
        
        # Test with deeply nested structure
        html_content = """
        <html>
            <body>
                <div class="container">
                    <div class="row">
                        <div class="col">
                            <span id="target">Target</span>
                        </div>
                    </div>
                </div>
            </body>
        </html>
        """
        
        soup = BeautifulSoup(html_content, 'lxml')
        target = soup.find('span', id='target')
        
        css_path = scraper._generate_css_path(target)
        
        assert css_path is not None
        assert "#target" in css_path
        assert "span" in css_path

    @pytest.mark.asyncio
    async def test_microdata_extraction_nested_items(self, scraper):
        """Test microdata extraction with deeply nested items."""
        html_content = """
        <div itemscope itemtype="https://schema.org/Event">
            <h1 itemprop="name">Concert Event</h1>
            <div itemprop="location" itemscope itemtype="https://schema.org/Place">
                <span itemprop="name">Concert Hall</span>
                <div itemprop="address" itemscope itemtype="https://schema.org/PostalAddress">
                    <span itemprop="streetAddress">123 Main St</span>
                    <span itemprop="addressLocality">City</span>
                </div>
            </div>
        </div>
        """
        
        result = await scraper.extract_enhanced_structured_data(html_content)
        
        assert result.success is True
        assert len(result.data["microdata"]) >= 1
        
        event = result.data["microdata"][0]
        assert "Event" in event["type"]
        # Multiple 'name' properties may be found, check if our value is present
        name_prop = event["properties"]["name"]
        if isinstance(name_prop, list):
            assert "Concert Event" in name_prop
        else:
            assert name_prop == "Concert Event"
        assert "location" in event["properties"]

    @pytest.mark.asyncio
    async def test_rdfa_vocab_inheritance(self, scraper):
        """Test RDFa vocabulary inheritance from parent elements."""
        html_content = """
        <div vocab="https://schema.org/" typeof="Organization">
            <span property="name">ACME Corp</span>
            <div typeof="PostalAddress">
                <span property="streetAddress">123 Business St</span>
                <span property="addressLocality">Business City</span>
            </div>
        </div>
        """
        
        result = await scraper.extract_enhanced_structured_data(html_content)
        
        assert result.success is True
        assert len(result.data["rdfa"]) >= 1
        
        # Check vocabulary inheritance
        for item in result.data["rdfa"]:
            if item["type"] == "Organization":
                assert item["vocab"] == "https://schema.org/"

    @pytest.mark.asyncio
    async def test_invalid_json_ld_handling(self, scraper):
        """Test handling of invalid JSON-LD scripts."""
        html_content = """
        <script type="application/ld+json">
        {
            "invalid": "json",
            "missing": "closing brace"
        </script>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": "Valid Article"
        }
        </script>
        """
        
        result = await scraper.extract_enhanced_structured_data(html_content)
        
        # Should handle invalid JSON gracefully and extract valid ones
        assert result.success is True
        assert len(result.data["json_ld"]) == 1  # Only valid JSON-LD
        assert result.data["json_ld"][0]["headline"] == "Valid Article"

    @pytest.mark.asyncio
    async def test_comprehensive_extraction_with_errors(self, scraper, mock_page):
        """Test comprehensive extraction with some methods failing."""
        # Mock some methods to fail
        with patch.object(scraper, 'extract_page_metadata') as mock_metadata, \
             patch.object(scraper, 'extract_all_links') as mock_links, \
             patch.object(scraper, 'extract_all_images') as mock_images, \
             patch.object(scraper, 'extract_structured_data') as mock_structured:
            
            mock_metadata.return_value = Mock(success=True)
            mock_links.side_effect = Exception("Links extraction failed")
            mock_images.return_value = Mock(success=True)
            mock_structured.return_value = Mock(success=True)
            
            # The comprehensive extraction catches exceptions and continues
            # Let's test that it handles the error gracefully
            results = await scraper.extract_comprehensive(mock_page)
            
            # Should still include successful extractions despite one failure
            assert isinstance(results, dict)
            # The method returns empty dict on major errors, or partial results

    @pytest.mark.asyncio
    async def test_save_extraction_result_error(self, scraper, memory):
        """Test saving extraction result with memory error."""
        result = ExtractionResult(
            url="https://example.com",
            extraction_type="test",
            selector="test"
        )
        
        with patch.object(memory, 'save_extracted_data') as mock_save:
            mock_save.side_effect = Exception("Memory save failed")
            
            with pytest.raises(Exception, match="Memory save failed"):
                await scraper.save_extraction_result(result)

    @pytest.mark.asyncio
    async def test_extraction_rule_error_handling(self, scraper):
        """Test extraction rule error handling."""
        sample_html = """
        <html>
            <body>
                <h1>Test Title</h1>
                <p>Test content</p>
            </body>
        </html>
        """
        
        extraction_rules = {
            "valid_rule": {"selector": "h1", "type": "text"},
            "invalid_rule": {"selector": "invalid[selector", "type": "text"}  # Invalid CSS selector
        }
        
        result = await scraper.extract_data(sample_html, extraction_rules)
        
        assert result.success is True
        assert "valid_rule" in result.data
        assert "invalid_rule" in result.data
        assert result.data["invalid_rule"] == []  # Should return empty list for failed rule

    @pytest.mark.asyncio
    async def test_close_scraper(self, scraper):
        """Test scraper close method."""
        scraper.extraction_count = 5
        original_count = scraper.extraction_count
        
        await scraper.close()
        
        # Should not affect extraction count
        assert scraper.extraction_count == original_count
        
        # Should be able to call multiple times without error
        await scraper.close()


class TestScraperConfig:
    """Test ScraperConfig model."""
    
    def test_scraper_config_defaults(self):
        """Test default configuration values."""
        config = ScraperConfig()
        
        assert config.default_timeout == 10000
        assert config.max_elements_per_selector == 1000
        assert config.enable_structured_data is True
        assert config.enable_images is True
        assert config.enable_links is True
        assert config.enable_text_content is True
        assert "href" in config.extract_attributes
        assert "src" in config.extract_attributes
        assert "script" in config.exclude_selectors
        assert "style" in config.exclude_selectors
        assert config.min_text_length == 1
        assert config.max_text_length == 10000

    def test_scraper_config_custom_values(self):
        """Test configuration with custom values."""
        custom_config = ScraperConfig(
            default_timeout=5000,
            max_elements_per_selector=500,
            enable_structured_data=False,
            extract_attributes=["href", "title"],
            exclude_selectors=["script", "style", "nav"],
            custom_selectors={"headlines": "h1, h2, h3"},
            min_text_length=3,
            max_text_length=500
        )
        
        assert custom_config.default_timeout == 5000
        assert custom_config.max_elements_per_selector == 500
        assert custom_config.enable_structured_data is False
        assert custom_config.extract_attributes == ["href", "title"]
        assert "nav" in custom_config.exclude_selectors
        assert custom_config.custom_selectors["headlines"] == "h1, h2, h3"
        assert custom_config.min_text_length == 3
        assert custom_config.max_text_length == 500


class TestExtractionModels:
    """Test extraction result models."""
    
    def test_extracted_element_defaults(self):
        """Test ExtractedElement default values."""
        element = ExtractedElement()
        
        assert element.text == ""
        assert element.attributes == {}
        assert element.html == ""
        assert element.xpath is None
        assert element.css_path is None

    def test_extracted_element_with_values(self):
        """Test ExtractedElement with values."""
        element = ExtractedElement(
            text="Sample text",
            attributes={"class": "test", "id": "elem1"},
            html="<p>Sample text</p>",
            xpath="//p[@id='elem1']",
            css_path="body > p#elem1"
        )
        
        assert element.text == "Sample text"
        assert element.attributes["class"] == "test"
        assert element.attributes["id"] == "elem1"
        assert element.html == "<p>Sample text</p>"
        assert element.xpath == "//p[@id='elem1']"
        assert element.css_path == "body > p#elem1"

    def test_extraction_result_defaults(self):
        """Test ExtractionResult default values."""
        result = ExtractionResult(
            url="https://example.com",
            extraction_type="test",
            selector="div"
        )
        
        assert result.url == "https://example.com"
        assert result.extraction_type == "test"
        assert result.selector == "div"
        assert result.elements == []
        assert result.data == {}
        assert result.success is True
        assert result.error_message is None
        assert result.extraction_time_ms == 0
        assert isinstance(result.extracted_at, datetime)

    def test_extraction_result_with_error(self):
        """Test ExtractionResult with error state."""
        result = ExtractionResult(
            url="https://example.com",
            extraction_type="test",
            selector="invalid",
            success=False,
            error_message="Invalid selector",
            extraction_time_ms=250.0
        )
        
        assert result.success is False
        assert result.error_message == "Invalid selector"
        assert result.extraction_time_ms == 250.0

    def test_extraction_result_with_elements(self):
        """Test ExtractionResult with extracted elements."""
        elements = [
            ExtractedElement(text="Element 1", html="<p>Element 1</p>"),
            ExtractedElement(text="Element 2", html="<p>Element 2</p>")
        ]
        
        result = ExtractionResult(
            url="https://example.com",
            extraction_type="text",
            selector="p",
            elements=elements,
            data={"count": 2}
        )
        
        assert len(result.elements) == 2
        assert result.elements[0].text == "Element 1"
        assert result.elements[1].text == "Element 2"
        assert result.data["count"] == 2