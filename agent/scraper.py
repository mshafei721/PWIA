"""Data scraper with CSS selector and XPath-based extraction."""
import asyncio
import json
import logging
import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, field_validator
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup, Tag, NavigableString
from agent.utils import setup_logging
from agent.memory import AgentMemory, ExtractedData

logger = logging.getLogger(__name__)


class ScraperConfig(BaseModel):
    """Configuration for data scraper behavior."""
    default_timeout: int = 10000  # milliseconds
    max_elements_per_selector: int = 1000
    enable_structured_data: bool = True
    enable_images: bool = True
    enable_links: bool = True
    enable_text_content: bool = True
    extract_attributes: List[str] = Field(default_factory=lambda: [
        "href", "src", "alt", "title", "class", "id", "data-*"
    ])
    custom_selectors: Dict[str, str] = Field(default_factory=dict)
    exclude_selectors: List[str] = Field(default_factory=lambda: [
        "script", "style", "noscript", ".hidden", "[style*='display:none']"
    ])
    text_cleanup_patterns: List[str] = Field(default_factory=lambda: [
        r'\s+',  # Multiple whitespace
        r'^\s+|\s+$',  # Leading/trailing whitespace
    ])
    min_text_length: int = 1
    max_text_length: int = 10000


class ExtractedElement(BaseModel):
    """Individual element extracted from a page."""
    text: str = ""
    attributes: Dict[str, str] = Field(default_factory=dict)
    html: str = ""
    xpath: Optional[str] = None
    css_path: Optional[str] = None


class ExtractionResult(BaseModel):
    """Result of a data extraction operation."""
    url: str
    extraction_type: str  # text, links, images, structured_data, metadata, custom
    selector: str
    elements: List[ExtractedElement] = Field(default_factory=list)
    data: Dict[str, Any] = Field(default_factory=dict)
    extracted_at: datetime = Field(default_factory=datetime.now)
    success: bool = True
    error_message: Optional[str] = None
    extraction_time_ms: float = 0


class DataScraper:
    """Data scraper implementing CSS selector and XPath-based extraction."""
    
    def __init__(self, config: ScraperConfig, memory: AgentMemory):
        """Initialize DataScraper."""
        self.config = config
        self.memory = memory
        self.session_id = str(uuid.uuid4())
        self.extraction_count = 0
        self.start_time = datetime.now()
        
        setup_logging()
        logger.info(f"DataScraper initialized with session_id: {self.session_id}")

    async def extract_by_css_selector(
        self,
        page: Page,
        selector: str,
        extract_type: str = "text",
        max_elements: Optional[int] = None
    ) -> ExtractionResult:
        """Extract data using CSS selectors."""
        start_time = datetime.now()
        result = ExtractionResult(
            url=page.url,
            extraction_type=extract_type,
            selector=selector
        )
        
        try:
            # Set timeout and max elements
            timeout = self.config.default_timeout
            max_elem = max_elements or self.config.max_elements_per_selector
            
            # Query elements
            elements = await page.query_selector_all(selector)
            if len(elements) > max_elem:
                elements = elements[:max_elem]
                logger.warning(f"Limited results to {max_elem} elements for selector: {selector}")
            
            # Extract data from elements
            extracted_elements = []
            for element in elements:
                try:
                    extracted_elem = ExtractedElement()
                    
                    # Get text content
                    if self.config.enable_text_content:
                        text = await element.inner_text()
                        extracted_elem.text = self._clean_text(text)
                    
                    # Get attributes
                    for attr in self.config.extract_attributes:
                        if attr.endswith('*'):
                            # Handle data-* attributes
                            base_attr = attr.rstrip('*')
                            # Would need JS evaluation for data attributes
                            continue
                        else:
                            attr_value = await element.get_attribute(attr)
                            if attr_value:
                                extracted_elem.attributes[attr] = attr_value
                    
                    # Get HTML if needed
                    if extract_type in ["html", "full"]:
                        extracted_elem.html = await element.inner_html()
                    
                    extracted_elements.append(extracted_elem)
                    
                except Exception as e:
                    logger.warning(f"Error extracting element: {e}")
                    continue
            
            result.elements = extracted_elements
            result.success = True
            
        except Exception as e:
            logger.error(f"CSS selector extraction failed: {e}")
            result.success = False
            result.error_message = str(e)
            result.data["error"] = str(e)
        
        # Calculate extraction time
        end_time = datetime.now()
        result.extraction_time_ms = (end_time - start_time).total_seconds() * 1000
        
        self.extraction_count += 1
        return result

    async def extract_by_xpath(
        self,
        page: Page,
        xpath: str,
        extract_type: str = "text",
        max_elements: Optional[int] = None
    ) -> ExtractionResult:
        """Extract data using XPath expressions."""
        start_time = datetime.now()
        result = ExtractionResult(
            url=page.url,
            extraction_type=extract_type,
            selector=xpath
        )
        
        try:
            max_elem = max_elements or self.config.max_elements_per_selector
            
            # Execute XPath using page.evaluate
            xpath_script = f"""
            () => {{
                const elements = document.evaluate(
                    '{xpath}',
                    document,
                    null,
                    XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,
                    null
                );
                
                const results = [];
                const maxElements = {max_elem};
                const count = Math.min(elements.snapshotLength, maxElements);
                
                for (let i = 0; i < count; i++) {{
                    const element = elements.snapshotItem(i);
                    const result = {{
                        text: element.textContent || '',
                        html: element.innerHTML || '',
                        attributes: {{}}
                    }};
                    
                    // Extract common attributes
                    const attrs = ['href', 'src', 'alt', 'title', 'class', 'id'];
                    attrs.forEach(attr => {{
                        if (element.hasAttribute && element.hasAttribute(attr)) {{
                            result.attributes[attr] = element.getAttribute(attr);
                        }}
                    }});
                    
                    results.push(result);
                }}
                
                return results;
            }}
            """
            
            elements_data = await page.evaluate(xpath_script)
            
            # Convert to ExtractedElement objects
            extracted_elements = []
            for elem_data in elements_data:
                extracted_elem = ExtractedElement(
                    text=self._clean_text(elem_data.get("text", "")),
                    attributes=elem_data.get("attributes", {}),
                    html=elem_data.get("html", ""),
                    xpath=xpath
                )
                extracted_elements.append(extracted_elem)
            
            result.elements = extracted_elements
            result.success = True
            
        except Exception as e:
            logger.error(f"XPath extraction failed: {e}")
            result.success = False
            result.error_message = str(e)
            result.data["error"] = str(e)
        
        # Calculate extraction time
        end_time = datetime.now()
        result.extraction_time_ms = (end_time - start_time).total_seconds() * 1000
        
        self.extraction_count += 1
        return result

    async def extract_structured_data(self, page: Page) -> ExtractionResult:
        """Extract structured data (JSON-LD, microdata, RDFa)."""
        start_time = datetime.now()
        result = ExtractionResult(
            url=page.url,
            extraction_type="structured_data",
            selector="structured_data_extraction"
        )
        
        try:
            # JavaScript to extract structured data
            structured_data_script = """
            () => {
                const result = {
                    json_ld: [],
                    microdata: [],
                    rdfa: []
                };
                
                // Extract JSON-LD
                const jsonLdElements = document.querySelectorAll('script[type="application/ld+json"]');
                jsonLdElements.forEach(element => {
                    try {
                        const data = JSON.parse(element.textContent);
                        result.json_ld.push(data);
                    } catch (e) {
                        console.warn('Invalid JSON-LD:', e);
                    }
                });
                
                // Extract Microdata
                const microdataElements = document.querySelectorAll('[itemtype]');
                microdataElements.forEach(element => {
                    const item = {
                        type: element.getAttribute('itemtype'),
                        properties: {}
                    };
                    
                    const props = element.querySelectorAll('[itemprop]');
                    props.forEach(prop => {
                        const name = prop.getAttribute('itemprop');
                        const value = prop.getAttribute('content') || 
                                     prop.getAttribute('href') || 
                                     prop.textContent;
                        item.properties[name] = value;
                    });
                    
                    result.microdata.push(item);
                });
                
                // Extract RDFa (basic implementation)
                const rdfaElements = document.querySelectorAll('[typeof]');
                rdfaElements.forEach(element => {
                    const item = {
                        type: element.getAttribute('typeof'),
                        properties: {}
                    };
                    
                    const props = element.querySelectorAll('[property]');
                    props.forEach(prop => {
                        const name = prop.getAttribute('property');
                        const value = prop.getAttribute('content') || prop.textContent;
                        item.properties[name] = value;
                    });
                    
                    result.rdfa.push(item);
                });
                
                return result;
            }
            """
            
            structured_data = await page.evaluate(structured_data_script)
            result.data = structured_data
            result.success = True
            
        except Exception as e:
            logger.error(f"Structured data extraction failed: {e}")
            result.success = False
            result.error_message = str(e)
            result.data["error"] = str(e)
        
        # Calculate extraction time
        end_time = datetime.now()
        result.extraction_time_ms = (end_time - start_time).total_seconds() * 1000
        
        self.extraction_count += 1
        return result

    async def extract_all_links(self, page: Page) -> ExtractionResult:
        """Extract all links from the page."""
        return await self.extract_by_css_selector(
            page=page,
            selector="a[href]",
            extract_type="links"
        )

    async def extract_all_images(self, page: Page) -> ExtractionResult:
        """Extract all images from the page."""
        return await self.extract_by_css_selector(
            page=page,
            selector="img",
            extract_type="images"
        )

    async def extract_page_metadata(self, page: Page) -> ExtractionResult:
        """Extract page metadata (title, meta tags, etc.)."""
        start_time = datetime.now()
        result = ExtractionResult(
            url=page.url,
            extraction_type="metadata",
            selector="metadata_extraction"
        )
        
        try:
            # Get page title
            title = await page.title()
            
            # Extract meta tags
            metadata_script = """
            () => {
                const metadata = {
                    title: document.title,
                    description: '',
                    keywords: '',
                    author: '',
                    viewport: '',
                    robots: '',
                    canonical: '',
                    og: {},
                    twitter: {}
                };
                
                // Extract meta tags
                const metaTags = document.querySelectorAll('meta');
                metaTags.forEach(meta => {
                    const name = meta.getAttribute('name') || meta.getAttribute('property');
                    const content = meta.getAttribute('content');
                    
                    if (name && content) {
                        if (name === 'description') metadata.description = content;
                        else if (name === 'keywords') metadata.keywords = content;
                        else if (name === 'author') metadata.author = content;
                        else if (name === 'viewport') metadata.viewport = content;
                        else if (name === 'robots') metadata.robots = content;
                        else if (name.startsWith('og:')) {
                            metadata.og[name.substring(3)] = content;
                        } else if (name.startsWith('twitter:')) {
                            metadata.twitter[name.substring(8)] = content;
                        }
                    }
                });
                
                // Extract canonical URL
                const canonical = document.querySelector('link[rel="canonical"]');
                if (canonical) {
                    metadata.canonical = canonical.getAttribute('href');
                }
                
                return metadata;
            }
            """
            
            metadata = await page.evaluate(metadata_script)
            result.data = metadata
            result.success = True
            
        except Exception as e:
            logger.error(f"Metadata extraction failed: {e}")
            result.success = False
            result.error_message = str(e)
            result.data["error"] = str(e)
        
        # Calculate extraction time
        end_time = datetime.now()
        result.extraction_time_ms = (end_time - start_time).total_seconds() * 1000
        
        self.extraction_count += 1
        return result

    async def extract_custom(
        self,
        page: Page,
        extraction_name: str,
        extract_type: str = "text"
    ) -> ExtractionResult:
        """Extract data using custom configured selectors."""
        if extraction_name not in self.config.custom_selectors:
            raise ValueError(f"Custom extraction '{extraction_name}' not configured")
        
        selector = self.config.custom_selectors[extraction_name]
        return await self.extract_by_css_selector(
            page=page,
            selector=selector,
            extract_type=extract_type
        )

    async def extract_comprehensive(self, page: Page) -> Dict[str, ExtractionResult]:
        """Perform comprehensive extraction of all data types."""
        results = {}
        
        try:
            # Extract metadata
            results["metadata"] = await self.extract_page_metadata(page)
            
            # Extract links if enabled
            if self.config.enable_links:
                results["links"] = await self.extract_all_links(page)
            
            # Extract images if enabled
            if self.config.enable_images:
                results["images"] = await self.extract_all_images(page)
            
            # Extract structured data if enabled
            if self.config.enable_structured_data:
                results["structured_data"] = await self.extract_structured_data(page)
            
            # Extract custom selectors
            for name in self.config.custom_selectors:
                try:
                    results[f"custom_{name}"] = await self.extract_custom(page, name)
                except Exception as e:
                    logger.warning(f"Custom extraction '{name}' failed: {e}")
            
        except Exception as e:
            logger.error(f"Comprehensive extraction failed: {e}")
        
        return results

    async def save_extraction_result(self, result: ExtractionResult) -> str:
        """Save extraction result to memory."""
        try:
            # Convert to ExtractedData format
            extracted_data = ExtractedData(
                id=str(uuid.uuid4()),
                url=result.url,
                session_id=self.session_id,
                extraction_type=result.extraction_type,
                data={
                    "selector": result.selector,
                    "elements": [elem.model_dump() for elem in result.elements],
                    "metadata": result.data,
                    "success": result.success,
                    "error_message": result.error_message,
                    "extraction_time_ms": result.extraction_time_ms
                },
                extracted_at=result.extracted_at,
                confidence_score=1.0 if result.success else 0.0
            )
            
            return await self.memory.save_extracted_data(extracted_data)
            
        except Exception as e:
            logger.error(f"Failed to save extraction result: {e}")
            raise

    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text."""
        if not text:
            return ""
        
        # Basic text cleanup
        import re
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # Check length constraints
        if len(text) < self.config.min_text_length:
            return ""
        
        if len(text) > self.config.max_text_length:
            text = text[:self.config.max_text_length]
        
        return text

    def get_statistics(self) -> Dict[str, Any]:
        """Get scraper statistics."""
        uptime = datetime.now() - self.start_time
        
        return {
            "session_id": self.session_id,
            "extraction_count": self.extraction_count,
            "start_time": self.start_time.isoformat(),
            "uptime_seconds": uptime.total_seconds(),
            "config": self.config.model_dump()
        }

    async def extract_data(
        self, 
        html_content: str, 
        extraction_rules: Dict[str, Dict[str, Any]]
    ) -> ExtractionResult:
        """Extract data from HTML using BeautifulSoup with flexible extraction rules."""
        start_time = datetime.now()
        result = ExtractionResult(
            url="html_content",
            extraction_type="html_extraction",
            selector="multiple_rules"
        )
        
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            extracted_data = {}
            
            for rule_name, rule_config in extraction_rules.items():
                selector = rule_config.get("selector", "")
                extract_type = rule_config.get("type", "text")
                
                try:
                    elements = soup.select(selector)
                    
                    if extract_type == "text":
                        text_list = [
                            self._clean_text(elem.get_text()) for elem in elements
                        ]
                        extracted_data[rule_name] = text_list
                    
                    elif extract_type == "links":
                        links = []
                        for elem in elements:
                            if elem.name == 'a' and elem.get('href'):
                                links.append({
                                    "text": self._clean_text(elem.get_text()),
                                    "href": elem.get('href'),
                                    "title": elem.get('title', '')
                                })
                        extracted_data[rule_name] = links
                    
                    elif extract_type == "images":
                        images = []
                        for elem in elements:
                            if elem.name == 'img' and elem.get('src'):
                                images.append({
                                    "src": elem.get('src'),
                                    "alt": elem.get('alt', ''),
                                    "width": elem.get('width', ''),
                                    "height": elem.get('height', '')
                                })
                        extracted_data[rule_name] = images
                    
                    elif extract_type == "attributes":
                        attributes = rule_config.get("attributes", [])
                        attr_data = []
                        for elem in elements:
                            elem_attrs = {}
                            for attr in attributes:
                                elem_attrs[attr] = elem.get(attr, '')
                            attr_data.append(elem_attrs)
                        extracted_data[rule_name] = attr_data
                    
                except Exception as e:
                        logger.warning(f"Rule '{rule_name}' failed: {e}")
                        extracted_data[rule_name] = []
            
            result.data = extracted_data
            result.success = True
            
        except Exception as e:
            logger.error(f"HTML extraction failed: {e}")
            result.success = False
            result.error_message = str(e)
            result.data["error"] = str(e)
        
        # Calculate extraction time
        end_time = datetime.now()
        result.extraction_time_ms = (end_time - start_time).total_seconds() * 1000
        self.extraction_count += 1
        
        return result

    async def parse_elements(
        self, 
        html_content: str, 
        selector: str
    ) -> List[ExtractedElement]:
        """Parse elements from HTML using BeautifulSoup."""
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            elements = soup.select(selector)
            
            extracted_elements = []
            for elem in elements:
                extracted_elem = ExtractedElement()
                
                # Get text content
                extracted_elem.text = elem.get_text()
                
                # Get all attributes
                extracted_elem.attributes = dict(elem.attrs) if elem.attrs else {}
                
                # Get HTML content
                extracted_elem.html = str(elem)
                
                # Generate CSS path
                extracted_elem.css_path = self._generate_css_path(elem)
                
                extracted_elements.append(extracted_elem)
            
            return extracted_elements
            
        except Exception as e:
            logger.error(f"Element parsing failed: {e}")
            return []

    async def get_text(
        self, 
        html_content: str, 
        selector: str,
        clean_text: bool = True,
        exclude_tags: Optional[List[str]] = None
    ) -> str:
        """Extract clean text from HTML elements."""
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Remove excluded tags
            if exclude_tags:
                for tag_name in exclude_tags:
                    for tag in soup.find_all(tag_name):
                        tag.decompose()
            
            # Find target elements
            elements = soup.select(selector)
            
            if not elements:
                return ""
            
            # Combine text from all matching elements
            text_parts = []
            for elem in elements:
                text = elem.get_text()
                if clean_text:
                    text = self._clean_text(text)
                if text:
                    text_parts.append(text)
            
            return "\n".join(text_parts)
            
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            return ""

    async def get_attributes(
        self, 
        html_content: str, 
        selector: str,
        attributes: List[str]
    ) -> List[Dict[str, str]]:
        """Extract specific attributes from elements."""
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            elements = soup.select(selector)
            
            result = []
            for elem in elements:
                elem_attrs = {}
                for attr in attributes:
                    elem_attrs[attr] = elem.get(attr, '')
                result.append(elem_attrs)
            
            return result
            
        except Exception as e:
            logger.error(f"Attribute extraction failed: {e}")
            return []

    async def extract_table_data(
        self, 
        html_content: str, 
        selector: str
    ) -> ExtractionResult:
        """Extract structured data from HTML tables."""
        start_time = datetime.now()
        result = ExtractionResult(
            url="html_content",
            extraction_type="table_data",
            selector=selector
        )
        
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            table = soup.select_one(selector)
            
            if not table:
                result.success = False
                result.error_message = f"No table found with selector: {selector}"
                return result
            
            # Extract headers
            headers = []
            header_row = table.find('thead')
            if header_row:
                th_elements = header_row.find_all(['th', 'td'])
                headers = [self._clean_text(th.get_text()) for th in th_elements]
            
            # Extract rows
            rows = []
            tbody = table.find('tbody') or table
            tr_elements = tbody.find_all('tr')
            
            for tr in tr_elements:
                # Skip header row if no thead
                if not header_row and tr == tr_elements[0] and tr.find('th'):
                    headers = [self._clean_text(th.get_text()) for th in tr.find_all(['th', 'td'])]
                    continue
                
                td_elements = tr.find_all(['td', 'th'])
                row_data = [self._clean_text(td.get_text()) for td in td_elements]
                if row_data:  # Only add non-empty rows
                    rows.append(row_data)
            
            result.data = {
                "headers": headers,
                "rows": rows,
                "row_count": len(rows),
                "column_count": len(headers) if headers else (len(rows[0]) if rows else 0)
            }
            result.success = True
            
        except Exception as e:
            logger.error(f"Table extraction failed: {e}")
            result.success = False
            result.error_message = str(e)
            result.data["error"] = str(e)
        
        # Calculate extraction time
        end_time = datetime.now()
        result.extraction_time_ms = (end_time - start_time).total_seconds() * 1000
        self.extraction_count += 1
        
        return result

    async def extract_form_structure(
        self, 
        html_content: str, 
        selector: str
    ) -> ExtractionResult:
        """Extract form structure and field information."""
        start_time = datetime.now()
        result = ExtractionResult(
            url="html_content",
            extraction_type="form_structure",
            selector=selector
        )
        
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            form = soup.select_one(selector)
            
            if not form:
                result.success = False
                result.error_message = f"No form found with selector: {selector}"
                return result
            
            # Extract form attributes
            form_data = {
                "action": form.get('action', ''),
                "method": form.get('method', 'get').lower(),
                "enctype": form.get('enctype', 'application/x-www-form-urlencoded'),
                "fields": []
            }
            
            # Extract form fields
            field_elements = form.find_all(['input', 'select', 'textarea', 'button'])
            
            for field in field_elements:
                field_info = {
                    "tag": field.name,
                    "type": field.get('type', ''),
                    "name": field.get('name', ''),
                    "id": field.get('id', ''),
                    "placeholder": field.get('placeholder', ''),
                    "required": field.has_attr('required'),
                    "disabled": field.has_attr('disabled'),
                    "value": field.get('value', '')
                }
                
                # Handle select options
                if field.name == 'select':
                    options = []
                    for option in field.find_all('option'):
                        options.append({
                            "value": option.get('value', ''),
                            "text": self._clean_text(option.get_text()),
                            "selected": option.has_attr('selected')
                        })
                    field_info["options"] = options
                
                form_data["fields"].append(field_info)
            
            result.data = form_data
            result.success = True
            
        except Exception as e:
            logger.error(f"Form extraction failed: {e}")
            result.success = False
            result.error_message = str(e)
            result.data["error"] = str(e)
        
        # Calculate extraction time
        end_time = datetime.now()
        result.extraction_time_ms = (end_time - start_time).total_seconds() * 1000
        self.extraction_count += 1
        
        return result

    async def extract_with_paths(
        self, 
        html_content: str, 
        extraction_rules: Dict[str, Dict[str, Any]]
    ) -> ExtractionResult:
        """Extract data with CSS path tracking for each element."""
        start_time = datetime.now()
        result = ExtractionResult(
            url="html_content",
            extraction_type="path_extraction",
            selector="multiple_rules_with_paths"
        )
        
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            extracted_data = {}
            all_elements = []
            
            for rule_name, rule_config in extraction_rules.items():
                selector = rule_config.get("selector", "")
                track_path = rule_config.get("track_path", False)
                
                try:
                    elements = soup.select(selector)
                    rule_data = []
                    
                    for elem in elements:
                        elem_data = {
                            "text": self._clean_text(elem.get_text()),
                            "attributes": dict(elem.attrs) if elem.attrs else {}
                        }
                        
                        if track_path:
                            elem_data["css_path"] = self._generate_css_path(elem)
                        
                        rule_data.append(elem_data)
                        
                        # Create ExtractedElement for result
                        extracted_elem = ExtractedElement(
                            text=elem_data["text"],
                            attributes=elem_data["attributes"],
                            html=str(elem),
                            css_path=elem_data.get("css_path")
                        )
                        all_elements.append(extracted_elem)
                    
                    extracted_data[rule_name] = rule_data
                    
                except Exception as e:
                    logger.warning(f"Rule '{rule_name}' failed: {e}")
                    extracted_data[rule_name] = []
            
            result.data = extracted_data
            result.elements = all_elements
            result.success = True
            
        except Exception as e:
            logger.error(f"Path extraction failed: {e}")
            result.success = False
            result.error_message = str(e)
            result.data["error"] = str(e)
        
        # Calculate extraction time
        end_time = datetime.now()
        result.extraction_time_ms = (end_time - start_time).total_seconds() * 1000
        self.extraction_count += 1
        
        return result

    def _generate_css_path(self, element: Tag) -> str:
        """Generate CSS path for an element."""
        try:
            path_parts = []
            current = element
            
            while current and current.name != '[document]':
                if current.name:
                    # Build selector for current element
                    selector = current.name
                    
                    # Add ID if present
                    if current.get('id'):
                        selector += f"#{current.get('id')}"
                    
                    # Add classes if present
                    classes = current.get('class')
                    if classes:
                        selector += '.' + '.'.join(classes)
                    
                    # Add nth-child if needed for uniqueness
                    if current.parent:
                        siblings = [s for s in current.parent.children 
                                  if hasattr(s, 'name') and s.name == current.name]
                        if len(siblings) > 1:
                            index = siblings.index(current) + 1
                            selector += f":nth-child({index})"
                    
                    path_parts.append(selector)
                
                current = current.parent
            
            return ' > '.join(reversed(path_parts))
            
        except Exception as e:
            logger.warning(f"CSS path generation failed: {e}")
            return ""

    async def extract_enhanced_structured_data(self, html_content: str) -> ExtractionResult:
        """Enhanced structured data extraction from HTML using BeautifulSoup."""
        start_time = datetime.now()
        result = ExtractionResult(
            url="html_content",
            extraction_type="enhanced_structured_data",
            selector="structured_data_enhanced"
        )
        
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            structured_data = {
                "json_ld": [],
                "microdata": [],
                "rdfa": [],
                "opengraph": [],
                "twitter_cards": []
            }
            
            # Extract JSON-LD
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string or script.get_text())
                    structured_data["json_ld"].append(data)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON-LD: {e}")
            
            # Extract enhanced Microdata with nested support
            microdata_items = soup.find_all(attrs={"itemscope": True})
            for item in microdata_items:
                microdata_obj = self._extract_microdata_item(item, soup)
                if microdata_obj:
                    structured_data["microdata"].append(microdata_obj)
            
            # Extract enhanced RDFa
            rdfa_items = soup.find_all(attrs={"typeof": True})
            for item in rdfa_items:
                rdfa_obj = self._extract_rdfa_item(item, soup)
                if rdfa_obj:
                    structured_data["rdfa"].append(rdfa_obj)
            
            # Extract OpenGraph metadata
            og_tags = soup.find_all('meta', attrs={'property': re.compile(r'^og:')})
            og_data = {}
            for tag in og_tags:
                property_name = tag.get('property', '').replace('og:', '')
                content = tag.get('content', '')
                if property_name and content:
                    og_data[property_name] = content
            if og_data:
                structured_data["opengraph"].append(og_data)
            
            # Extract Twitter Card metadata
            twitter_tags = soup.find_all('meta', attrs={'name': re.compile(r'^twitter:')})
            twitter_data = {}
            for tag in twitter_tags:
                name = tag.get('name', '').replace('twitter:', '')
                content = tag.get('content', '')
                if name and content:
                    twitter_data[name] = content
            if twitter_data:
                structured_data["twitter_cards"].append(twitter_data)
            
            result.data = structured_data
            result.success = True
            
        except Exception as e:
            logger.error(f"Enhanced structured data extraction failed: {e}")
            result.success = False
            result.error_message = str(e)
            result.data["error"] = str(e)
        
        # Calculate extraction time
        end_time = datetime.now()
        result.extraction_time_ms = (end_time - start_time).total_seconds() * 1000
        self.extraction_count += 1
        
        return result

    def _extract_microdata_item(self, item_element, soup) -> Optional[Dict[str, Any]]:
        """Extract microdata item with nested support."""
        try:
            item_type = item_element.get('itemtype', '')
            item_data = {
                "type": item_type,
                "properties": {}
            }
            
            # Find all properties within this item scope
            props = item_element.find_all(attrs={"itemprop": True})
            
            for prop in props:
                prop_name = prop.get('itemprop')
                if not prop_name:
                    continue
                
                # Check if this property has nested itemscope
                if prop.get('itemscope'):
                    nested_item = self._extract_microdata_item(prop, soup)
                    if nested_item:
                        item_data["properties"][prop_name] = nested_item
                else:
                    # Extract property value
                    value = self._extract_microdata_value(prop)
                    if value:
                        if prop_name in item_data["properties"]:
                            # Handle multiple values for same property
                            if not isinstance(item_data["properties"][prop_name], list):
                                item_data["properties"][prop_name] = [item_data["properties"][prop_name]]
                            item_data["properties"][prop_name].append(value)
                        else:
                            item_data["properties"][prop_name] = value
            
            return item_data if item_data["properties"] else None
            
        except Exception as e:
            logger.warning(f"Microdata item extraction failed: {e}")
            return None

    def _extract_microdata_value(self, element) -> str:
        """Extract value from microdata property element."""
        # Check for content attribute first
        if element.get('content'):
            return element.get('content')
        
        # Check for href attribute (links)
        if element.get('href'):
            return element.get('href')
        
        # Check for src attribute (images)
        if element.get('src'):
            return element.get('src')
        
        # Check for datetime attribute (time elements)
        if element.get('datetime'):
            return element.get('datetime')
        
        # Check for value attribute (inputs)
        if element.get('value'):
            return element.get('value')
        
        # Fall back to text content
        return self._clean_text(element.get_text())

    def _extract_rdfa_item(self, item_element, soup) -> Optional[Dict[str, Any]]:
        """Extract RDFa item with enhanced property support."""
        try:
            item_type = item_element.get('typeof', '')
            vocab = item_element.get('vocab', '') or self._find_rdfa_vocab(item_element)
            
            item_data = {
                "type": item_type,
                "vocab": vocab,
                "properties": {}
            }
            
            # Find all properties within this item
            props = item_element.find_all(attrs={"property": True})
            
            for prop in props:
                prop_name = prop.get('property')
                if not prop_name:
                    continue
                
                # Check if this property has nested typeof
                if prop.get('typeof'):
                    nested_item = self._extract_rdfa_item(prop, soup)
                    if nested_item:
                        item_data["properties"][prop_name] = nested_item
                else:
                    # Extract property value
                    value = self._extract_rdfa_value(prop)
                    if value:
                        if prop_name in item_data["properties"]:
                            # Handle multiple values
                            if not isinstance(item_data["properties"][prop_name], list):
                                item_data["properties"][prop_name] = [item_data["properties"][prop_name]]
                            item_data["properties"][prop_name].append(value)
                        else:
                            item_data["properties"][prop_name] = value
            
            return item_data if item_data["properties"] else None
            
        except Exception as e:
            logger.warning(f"RDFa item extraction failed: {e}")
            return None

    def _extract_rdfa_value(self, element) -> str:
        """Extract value from RDFa property element."""
        # Check for content attribute first
        if element.get('content'):
            return element.get('content')
        
        # Check for resource attribute
        if element.get('resource'):
            return element.get('resource')
        
        # Check for href attribute
        if element.get('href'):
            return element.get('href')
        
        # Check for src attribute
        if element.get('src'):
            return element.get('src')
        
        # Check for datetime attribute
        if element.get('datetime'):
            return element.get('datetime')
        
        # Fall back to text content
        return self._clean_text(element.get_text())

    def _find_rdfa_vocab(self, element) -> str:
        """Find RDFa vocabulary by traversing up the DOM."""
        current = element
        while current and current.name:
            if current.get('vocab'):
                return current.get('vocab')
            current = current.parent
        return ""

    async def validate_structured_data(self, structured_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate structured data and provide quality metrics."""
        try:
            validation_result = {
                "valid_schemas": 0,
                "invalid_schemas": 0,
                "schema_types": [],
                "has_context": False,
                "warnings": [],
                "errors": []
            }
            
            # Validate JSON-LD
            for item in structured_data.get("json_ld", []):
                if isinstance(item, dict):
                    if "@type" in item:
                        validation_result["valid_schemas"] += 1
                        schema_type = item["@type"]
                        if isinstance(schema_type, list):
                            validation_result["schema_types"].extend(schema_type)
                        else:
                            validation_result["schema_types"].append(schema_type)
                    
                    if "@context" in item:
                        validation_result["has_context"] = True
                    else:
                        validation_result["warnings"].append("JSON-LD missing @context")
                else:
                    validation_result["invalid_schemas"] += 1
                    validation_result["errors"].append("Invalid JSON-LD structure")
            
            # Validate Microdata
            for item in structured_data.get("microdata", []):
                if item.get("type") and item.get("properties"):
                    validation_result["valid_schemas"] += 1
                    schema_type = item["type"].split("/")[-1] if "/" in item["type"] else item["type"]
                    validation_result["schema_types"].append(schema_type)
                else:
                    validation_result["invalid_schemas"] += 1
            
            # Validate RDFa
            for item in structured_data.get("rdfa", []):
                if item.get("type") and item.get("properties"):
                    validation_result["valid_schemas"] += 1
                    validation_result["schema_types"].append(item["type"])
                else:
                    validation_result["invalid_schemas"] += 1
            
            # Remove duplicates from schema types
            validation_result["schema_types"] = list(set(validation_result["schema_types"]))
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Structured data validation failed: {e}")
            return {"error": str(e)}

    async def normalize_structured_data(self, structured_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize structured data to a common format."""
        try:
            normalized = {
                "entities": [],
                "metadata": {
                    "extraction_count": 0,
                    "formats_found": [],
                    "schema_types": []
                }
            }
            
            # Normalize JSON-LD
            for item in structured_data.get("json_ld", []):
                if isinstance(item, dict) and "@type" in item:
                    entity = self._normalize_json_ld_entity(item)
                    if entity:
                        normalized["entities"].append(entity)
                        normalized["metadata"]["formats_found"].append("JSON-LD")
            
            # Normalize Microdata
            for item in structured_data.get("microdata", []):
                entity = self._normalize_microdata_entity(item)
                if entity:
                    normalized["entities"].append(entity)
                    normalized["metadata"]["formats_found"].append("Microdata")
            
            # Normalize RDFa
            for item in structured_data.get("rdfa", []):
                entity = self._normalize_rdfa_entity(item)
                if entity:
                    normalized["entities"].append(entity)
                    normalized["metadata"]["formats_found"].append("RDFa")
            
            # Update metadata
            normalized["metadata"]["extraction_count"] = len(normalized["entities"])
            normalized["metadata"]["formats_found"] = list(set(normalized["metadata"]["formats_found"]))
            normalized["metadata"]["schema_types"] = list(set([
                entity["type"] for entity in normalized["entities"] if "type" in entity
            ]))
            
            return normalized
            
        except Exception as e:
            logger.error(f"Structured data normalization failed: {e}")
            return {"error": str(e)}

    def _normalize_json_ld_entity(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize JSON-LD entity to common format."""
        try:
            entity_type = item.get("@type", "Unknown")
            if isinstance(entity_type, list):
                entity_type = entity_type[0]  # Use first type
            
            entity = {
                "type": entity_type,
                "format": "JSON-LD",
                "properties": {}
            }
            
            # Copy all properties except @context and @type
            for key, value in item.items():
                if key not in ["@context", "@type"]:
                    entity["properties"][key] = value
            
            return entity
            
        except Exception as e:
            logger.warning(f"JSON-LD normalization failed: {e}")
            return None

    def _normalize_microdata_entity(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize Microdata entity to common format."""
        try:
            entity_type = item.get("type", "Unknown")
            if "/" in entity_type:
                entity_type = entity_type.split("/")[-1]
            
            entity = {
                "type": entity_type,
                "format": "Microdata",
                "properties": item.get("properties", {})
            }
            
            return entity
            
        except Exception as e:
            logger.warning(f"Microdata normalization failed: {e}")
            return None

    def _normalize_rdfa_entity(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize RDFa entity to common format."""
        try:
            entity = {
                "type": item.get("type", "Unknown"),
                "format": "RDFa",
                "vocab": item.get("vocab", ""),
                "properties": item.get("properties", {})
            }
            
            return entity
            
        except Exception as e:
            logger.warning(f"RDFa normalization failed: {e}")
            return None

    async def analyze_schema_types(self, structured_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze and classify Schema.org types found in structured data."""
        try:
            analysis = {
                "detected_types": [],
                "has_multiple_types": False,
                "schema_categories": {},
                "type_counts": {}
            }
            
            # Common Schema.org categories
            schema_categories = {
                "CreativeWork": ["Article", "BlogPosting", "NewsArticle", "Recipe", "Review"],
                "Organization": ["Corporation", "EducationalOrganization", "GovernmentOrganization"],
                "Person": ["Person"],
                "Product": ["Product", "SoftwareApplication"],
                "Event": ["Event", "BusinessEvent", "SocialEvent"],
                "Place": ["Place", "LocalBusiness", "Restaurant"],
                "Thing": ["Thing"]
            }
            
            # Collect all types
            all_types = []
            
            # From JSON-LD
            for item in structured_data.get("json_ld", []):
                if isinstance(item, dict) and "@type" in item:
                    item_type = item["@type"]
                    if isinstance(item_type, list):
                        all_types.extend(item_type)
                        analysis["has_multiple_types"] = True
                    else:
                        all_types.append(item_type)
            
            # From Microdata
            for item in structured_data.get("microdata", []):
                if item.get("type"):
                    type_name = item["type"].split("/")[-1] if "/" in item["type"] else item["type"]
                    all_types.append(type_name)
            
            # From RDFa
            for item in structured_data.get("rdfa", []):
                if item.get("type"):
                    all_types.append(item["type"])
            
            # Categorize types
            analysis["detected_types"] = list(set(all_types))
            
            for detected_type in analysis["detected_types"]:
                analysis["type_counts"][detected_type] = all_types.count(detected_type)
                
                # Find category
                for category, types in schema_categories.items():
                    if detected_type in types:
                        if category not in analysis["schema_categories"]:
                            analysis["schema_categories"][category] = []
                        analysis["schema_categories"][category].append(detected_type)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Schema type analysis failed: {e}")
            return {"error": str(e)}

    async def close(self):
        """Clean up scraper resources."""
        logger.info(f"DataScraper session {self.session_id} closed after {self.extraction_count} extractions")