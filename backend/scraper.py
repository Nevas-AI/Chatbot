"""
scraper.py - Web Scraper Module for Aria Chatbot
=================================================
Crawls websites to extract clean text content for the RAG knowledge base.
Supports sitemap.xml parsing, BFS crawling, and intelligent text extraction.
"""

import re
import time
import logging
from typing import List, Set, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Configure logging
logger = logging.getLogger(__name__)


class ScrapedDocument:
    """Represents a scraped document with content and metadata."""

    def __init__(self, page_content: str, metadata: dict):
        self.page_content = page_content
        self.metadata = metadata

    def __repr__(self):
        return f"ScrapedDocument(url={self.metadata.get('url', 'unknown')}, length={len(self.page_content)})"


class WebScraper:
    """
    Web scraper that crawls a website and extracts clean text content.
    
    Features:
    - Sitemap.xml detection and parsing
    - BFS crawl within the same domain
    - Clean text extraction (removes nav, footer, scripts, ads)
    - Configurable max pages limit
    - Polite crawling with delays between requests
    """

    # Elements to remove during text extraction
    # NOTE: We intentionally exclude 'nav', 'header', 'footer' here because
    # many websites wrap ALL content inside these tags. Navigation/header
    # content is instead handled by class/ID matching in REMOVE_PATTERNS.
    REMOVE_TAGS = [
        'script', 'style', 'aside', 'form', 'iframe', 'noscript',
    ]

    # CSS classes/IDs commonly associated with non-content elements
    REMOVE_PATTERNS = [
        'nav', 'navbar', 'menu', 'sidebar', 'footer',
        'header', 'advertisement', 'ad-', 'ads-', 'cookie',
        'popup', 'modal', 'social', 'share', 'comment',
        'breadcrumb', 'pagination',
    ]

    # File extensions to skip
    SKIP_EXTENSIONS = {
        '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.svg', '.ico',
        '.mp4', '.mp3', '.avi', '.mov', '.zip', '.tar', '.gz',
        '.css', '.js', '.xml', '.json', '.woff', '.woff2', '.ttf',
        '.eot', '.map',
    }

    def __init__(self, max_pages: int = 100, delay: float = 1.0):
        """
        Initialize the web scraper.
        
        Args:
            max_pages: Maximum number of pages to crawl (default: 100)
            delay: Delay in seconds between requests (default: 1.0)
        """
        self.max_pages = max_pages
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'AriaBot/1.0 (Customer Support Knowledge Crawler)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })

    def scrape_website(self, url: str) -> List[ScrapedDocument]:
        """
        Main entry point - scrape an entire website starting from the given URL.
        
        Args:
            url: The root URL of the website to scrape
            
        Returns:
            List of ScrapedDocument objects with extracted content
        """
        logger.info(f"Starting website scrape: {url}")
        base_domain = urlparse(url).netloc
        documents = []
        visited: Set[str] = set()
        to_visit: List[str] = []

        # Resolve the actual domain after following redirects
        # (e.g. nevastech.com -> www.nevastech.com)
        try:
            head_resp = self.session.head(url, timeout=10, allow_redirects=True)
            resolved_domain = urlparse(head_resp.url).netloc
            if resolved_domain:
                base_domain = resolved_domain
                logger.info(f"Resolved domain after redirect: {base_domain}")
        except Exception:
            pass  # Keep original base_domain

        # Step 1: Try to get URLs from sitemap.xml
        # Build the resolved base URL from the (possibly redirected) domain
        resolved_base = f"{urlparse(url).scheme}://{base_domain}"
        sitemap_urls = self._parse_sitemap(resolved_base)
        if sitemap_urls:
            logger.info(f"Found {len(sitemap_urls)} URLs from sitemap.xml")
            to_visit.extend(sitemap_urls)
        else:
            logger.info("No sitemap found, starting BFS crawl from root URL")
            to_visit.append(url)

        # Step 2: Crawl pages using BFS
        while to_visit and len(documents) < self.max_pages:
            current_url = to_visit.pop(0)

            # Normalize and validate URL
            current_url = self._normalize_url(current_url)
            if current_url in visited:
                continue
            if not self._is_valid_url(current_url, base_domain):
                continue

            visited.add(current_url)

            try:
                # Fetch the page
                response = self._fetch_page(current_url)
                if response is None:
                    continue

                soup = BeautifulSoup(response.text, 'lxml')

                # Extract clean text content
                text = self._extract_text(soup)
                if text and len(text.strip()) > 50:  # Skip near-empty pages
                    title = self._extract_title(soup)
                    documents.append(ScrapedDocument(
                        page_content=text,
                        metadata={
                            'url': current_url,
                            'title': title,
                            'source': 'web_scrape',
                        }
                    ))
                    logger.info(f"Scraped ({len(documents)}/{self.max_pages}): {current_url}")

                # Extract links for further crawling (only if not from sitemap)
                if not sitemap_urls:
                    new_links = self._extract_links(soup, current_url, base_domain)
                    for link in new_links:
                        if link not in visited:
                            to_visit.append(link)

                # Polite delay between requests
                time.sleep(self.delay)

            except Exception as e:
                logger.warning(f"Error scraping {current_url}: {str(e)}")
                continue

        logger.info(f"Scraping complete. Extracted {len(documents)} documents.")
        return documents

    def _parse_sitemap(self, base_url: str) -> List[str]:
        """
        Try to find and parse sitemap.xml for the website.
        
        Args:
            base_url: The root URL of the website
            
        Returns:
            List of URLs found in the sitemap, or empty list if not found
        """
        sitemap_urls_to_try = [
            urljoin(base_url, '/sitemap.xml'),
            urljoin(base_url, '/sitemap_index.xml'),
            urljoin(base_url, '/sitemap/sitemap.xml'),
        ]

        urls = []
        for sitemap_url in sitemap_urls_to_try:
            try:
                response = self.session.get(sitemap_url, timeout=10)
                content_start = response.text[:500].lower()
                is_xml = any(marker in content_start for marker in [
                    '<?xml', '<urlset', '<sitemapindex',
                ])
                if response.status_code == 200 and is_xml:
                    soup = BeautifulSoup(response.text, 'lxml')

                    # Handle sitemap index (contains links to other sitemaps)
                    sitemap_tags = soup.find_all('sitemap')
                    if sitemap_tags:
                        for sitemap_tag in sitemap_tags[:10]:  # Limit sub-sitemaps
                            loc = sitemap_tag.find('loc')
                            if loc:
                                sub_urls = self._parse_single_sitemap(loc.text.strip())
                                urls.extend(sub_urls)
                    else:
                        # Regular sitemap with <url> tags
                        urls = self._parse_single_sitemap(sitemap_url)

                    if urls:
                        return urls[:self.max_pages]  # Cap at max_pages
            except Exception as e:
                logger.debug(f"Could not fetch sitemap at {sitemap_url}: {str(e)}")
                continue

        return urls

    def _parse_single_sitemap(self, sitemap_url: str) -> List[str]:
        """Parse a single sitemap XML and extract URLs."""
        urls = []
        try:
            response = self.session.get(sitemap_url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'lxml')
                for url_tag in soup.find_all('url'):
                    loc = url_tag.find('loc')
                    if loc:
                        urls.append(loc.text.strip())
        except Exception as e:
            logger.debug(f"Error parsing sitemap {sitemap_url}: {str(e)}")
        return urls

    def _fetch_page(self, url: str) -> Optional[requests.Response]:
        """
        Fetch a single web page with error handling.
        
        Args:
            url: URL to fetch
            
        Returns:
            Response object or None if the request failed
        """
        try:
            response = self.session.get(url, timeout=15, allow_redirects=True)
            content_type = response.headers.get('Content-Type', '')

            # Only process HTML content
            if 'text/html' not in content_type.lower():
                return None

            if response.status_code == 200:
                return response
            else:
                logger.debug(f"HTTP {response.status_code} for {url}")
                return None
        except requests.exceptions.RequestException as e:
            logger.debug(f"Request failed for {url}: {str(e)}")
            return None

    def _extract_text(self, soup: BeautifulSoup) -> str:
        """
        Extract clean text content from a BeautifulSoup parsed page.
        Removes navigation, footers, scripts, ads, and other non-content elements.
        
        Args:
            soup: Parsed BeautifulSoup object
            
        Returns:
            Clean text content as a string
        """
        # Create a copy to avoid modifying the original
        soup_copy = BeautifulSoup(str(soup), 'lxml')

        # Remove unwanted HTML tags
        for tag_name in self.REMOVE_TAGS:
            for tag in soup_copy.find_all(tag_name):
                tag.decompose()

        # Remove elements with common non-content class names and IDs
        # Use word-boundary matching so 'nav' matches 'main-nav' but not 'sharepoint-navigation'
        # Skip elements with substantial text (>500 chars) — they're likely content wrappers
        for pattern in self.REMOVE_PATTERNS:
            boundary_re = re.compile(
                r'(?:^|[\s_-])' + re.escape(pattern) + r'(?:$|[\s_-])', re.I
            )
            # Remove by class
            for element in soup_copy.find_all(class_=boundary_re):
                if len(element.get_text(strip=True)) < 500:
                    element.decompose()
            # Remove by ID
            for element in soup_copy.find_all(id=boundary_re):
                if len(element.get_text(strip=True)) < 500:
                    element.decompose()

        # Remove hidden elements
        for element in soup_copy.find_all(style=re.compile(r'display\s*:\s*none', re.I)):
            element.decompose()

        # Try to find the main content area first
        main_content = (
            soup_copy.find('main') or
            soup_copy.find('article') or
            soup_copy.find(id=re.compile(r'content|main', re.I)) or
            soup_copy.find(class_=re.compile(r'content|main|post|article', re.I)) or
            soup_copy.find('body')
        )

        if main_content:
            text = main_content.get_text(separator='\n', strip=True)
            # Fallback to body if main content was emptied by filtering
            if not text.strip() and main_content.name != 'body':
                body = soup_copy.find('body')
                if body:
                    text = body.get_text(separator='\n', strip=True)
        else:
            text = soup_copy.get_text(separator='\n', strip=True)

        # Clean up the extracted text
        text = self._clean_text(text)
        return text

    def _clean_text(self, text: str) -> str:
        """
        Clean extracted text by removing extra whitespace and empty lines.
        
        Args:
            text: Raw extracted text
            
        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line:  # Skip empty lines
                # Collapse multiple spaces
                line = re.sub(r'\s+', ' ', line)
                cleaned_lines.append(line)

        # Remove consecutive duplicate lines
        final_lines = []
        for line in cleaned_lines:
            if not final_lines or line != final_lines[-1]:
                final_lines.append(line)

        return '\n'.join(final_lines)

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract the page title from the soup."""
        # Try <title> tag first
        title_tag = soup.find('title')
        if title_tag and title_tag.text.strip():
            return title_tag.text.strip()

        # Try <h1> as fallback
        h1_tag = soup.find('h1')
        if h1_tag and h1_tag.text.strip():
            return h1_tag.text.strip()

        # Try og:title meta tag
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content', '').strip():
            return og_title['content'].strip()

        return 'Untitled Page'

    def _extract_links(self, soup: BeautifulSoup, current_url: str, base_domain: str) -> List[str]:
        """
        Extract internal links from the page for further crawling.
        
        Args:
            soup: Parsed BeautifulSoup object
            current_url: The URL of the current page
            base_domain: The base domain to stay within
            
        Returns:
            List of absolute URLs to crawl next
        """
        links = []
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].strip()

            # Skip anchors, javascript, mailto, tel links
            if href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                continue

            # Convert to absolute URL
            absolute_url = urljoin(current_url, href)
            absolute_url = self._normalize_url(absolute_url)

            # Only keep links within the same domain
            if self._is_valid_url(absolute_url, base_domain):
                links.append(absolute_url)

        return links

    def _normalize_url(self, url: str) -> str:
        """Normalize a URL by removing fragments and trailing slashes."""
        parsed = urlparse(url)
        # Remove fragment
        normalized = parsed._replace(fragment='')
        url = normalized.geturl()
        # Remove trailing slash (except for root)
        if url.endswith('/') and url.count('/') > 3:
            url = url.rstrip('/')
        return url

    def _is_valid_url(self, url: str, base_domain: str) -> bool:
        """
        Check if a URL is valid for crawling.
        
        Args:
            url: URL to validate
            base_domain: Expected domain
            
        Returns:
            True if the URL should be crawled
        """
        try:
            parsed = urlparse(url)

            # Must be HTTP/HTTPS
            if parsed.scheme not in ('http', 'https'):
                return False

            # Must be same domain (normalize www. prefix)
            url_domain = parsed.netloc.lower().removeprefix('www.')
            base = base_domain.lower().removeprefix('www.')
            if url_domain != base:
                return False

            # Skip URLs with file extensions we don't want
            path = parsed.path.lower()
            for ext in self.SKIP_EXTENSIONS:
                if path.endswith(ext):
                    return False

            return True
        except Exception:
            return False
