"""
scraper.py - Advanced Web Scraper for Neva Chatbot
====================================================
Crawls websites to extract clean text content for the RAG knowledge base.

Advanced features:
- Hybrid crawling: Sitemap + BFS combined for maximum coverage
- Robots.txt sitemap discovery
- WordPress/CMS-specific URL detection
- Retry logic with exponential backoff
- Broad link extraction (a, link, canonical, meta)
- Smart content extraction with structured data support
"""

import re
import time
import logging
from typing import List, Set, Optional, Tuple
from urllib.parse import urljoin, urlparse, urlunparse
from collections import deque

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
    Advanced web scraper that leaves no page behind.

    Strategy:
    1. Parse robots.txt for sitemap locations
    2. Try multiple known sitemap paths (standard, WordPress, Yoast, etc.)
    3. Parse all sitemaps (including sitemap indexes recursively)
    4. Run BFS crawl from the root URL in parallel to discover unlisted pages
    5. Merge both URL sources and scrape everything
    """

    # Elements to remove during text extraction
    REMOVE_TAGS = [
        'script', 'style', 'aside', 'form', 'iframe', 'noscript',
        'svg', 'canvas', 'video', 'audio',
    ]

    # CSS classes/IDs commonly associated with non-content elements
    REMOVE_PATTERNS = [
        'nav', 'navbar', 'menu', 'sidebar', 'footer',
        'header', 'advertisement', 'ad-', 'ads-', 'cookie',
        'popup', 'modal', 'social', 'share', 'comment',
        'breadcrumb', 'pagination', 'widget', 'related-posts',
        'newsletter', 'subscribe', 'cta-banner',
    ]

    # File extensions to skip
    SKIP_EXTENSIONS = {
        '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.svg', '.ico',
        '.mp4', '.mp3', '.avi', '.mov', '.zip', '.tar', '.gz',
        '.css', '.js', '.xml', '.json', '.woff', '.woff2', '.ttf',
        '.eot', '.map', '.webp', '.bmp', '.tiff', '.doc', '.docx',
        '.xls', '.xlsx', '.ppt', '.pptx', '.rar', '.7z',
    }

    # URL path patterns to skip (login pages, admin, feeds, etc.)
    SKIP_PATH_PATTERNS = [
        r'/wp-admin', r'/wp-login', r'/feed', r'/rss',
        r'/cart', r'/checkout', r'/my-account', r'/login',
        r'/register', r'/tag/', r'/author/',
        r'/page/\d+', r'/\?replytocom=',
        r'/wp-json/', r'/xmlrpc', r'/#',
    ]

    # Known sitemap paths to try
    SITEMAP_PATHS = [
        '/sitemap.xml',
        '/sitemap_index.xml',
        '/sitemap/sitemap.xml',
        '/wp-sitemap.xml',                 # WordPress core sitemaps (5.5+)
        '/sitemap_index.xml',
        '/post-sitemap.xml',               # Yoast SEO
        '/page-sitemap.xml',               # Yoast SEO
        '/category-sitemap.xml',           # Yoast SEO
        '/product-sitemap.xml',            # WooCommerce
        '/sitemap.xml.gz',                 # Compressed sitemaps
        '/sitemaps/sitemap.xml',
    ]

    def __init__(self, max_pages: int = 500, delay: float = 0.5):
        """
        Initialize the advanced web scraper.

        Args:
            max_pages: Maximum number of pages to crawl (default: 500)
            delay: Delay in seconds between requests (default: 0.5)
        """
        self.max_pages = max_pages
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; NevaBot/2.0; +https://nevastech.com/bot)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
        })
        # Compiled skip patterns
        self._skip_patterns = [re.compile(p, re.I) for p in self.SKIP_PATH_PATTERNS]

    def scrape_website(self, url: str) -> List[ScrapedDocument]:
        """
        Main entry point - scrape an entire website comprehensively.

        Strategy: Collect URLs from sitemap AND BFS crawl, then scrape all.

        Args:
            url: The root URL of the website to scrape

        Returns:
            List of ScrapedDocument objects with extracted content
        """
        logger.info(f"🚀 Starting advanced website scrape: {url}")
        base_domain = urlparse(url).netloc
        documents = []
        visited: Set[str] = set()
        queue = deque()

        # Resolve actual domain after redirects
        resolved_base, base_domain = self._resolve_domain(url, base_domain)
        logger.info(f"Base domain: {base_domain}")

        # ── Phase 1: Discover URLs from all sitemap sources ──
        logger.info("📋 Phase 1: Discovering pages from sitemaps & robots.txt...")
        sitemap_urls = self._discover_all_sitemaps(resolved_base)
        logger.info(f"Found {len(sitemap_urls)} URLs from sitemaps")

        # ── Phase 2: Seed the BFS queue ──
        # Add sitemap URLs + root URL to the queue
        for su in sitemap_urls:
            normalized = self._normalize_url(su)
            if normalized not in visited and self._is_valid_url(normalized, base_domain):
                queue.append(normalized)

        # Always add root URL to ensure BFS starts from homepage
        root_normalized = self._normalize_url(url)
        if root_normalized not in visited:
            queue.appendleft(root_normalized)

        # ── Phase 3: Probe common CMS endpoints for extra pages ──
        logger.info("🔍 Phase 2: Probing CMS-specific URLs...")
        cms_urls = self._probe_cms_urls(resolved_base)
        for cu in cms_urls:
            normalized = self._normalize_url(cu)
            if normalized not in visited and self._is_valid_url(normalized, base_domain):
                queue.append(normalized)
        logger.info(f"Found {len(cms_urls)} additional CMS URLs")

        # ── Phase 4: BFS Crawl + Scrape ──
        logger.info(f"🕸️ Phase 3: BFS crawling (max {self.max_pages} pages)...")
        pages_scraped = 0

        while queue and pages_scraped < self.max_pages:
            current_url = queue.popleft()

            # Normalize and validate
            current_url = self._normalize_url(current_url)
            if current_url in visited:
                continue
            if not self._is_valid_url(current_url, base_domain):
                continue
            if self._should_skip_path(current_url):
                continue

            visited.add(current_url)

            try:
                # Fetch the page (with retry)
                response = self._fetch_page_with_retry(current_url)
                if response is None:
                    continue

                soup = BeautifulSoup(response.text, 'lxml')

                # Extract clean text content
                text = self._extract_text(soup)
                if text and len(text.strip()) > 50:
                    title = self._extract_title(soup)
                    meta_desc = self._extract_meta_description(soup)

                    # Build rich page content
                    page_content = text
                    if meta_desc and meta_desc not in text:
                        page_content = f"{meta_desc}\n\n{text}"

                    documents.append(ScrapedDocument(
                        page_content=page_content,
                        metadata={
                            'url': current_url,
                            'title': title,
                            'source': 'web_scrape',
                        }
                    ))
                    pages_scraped += 1
                    logger.info(f"✅ Scraped ({pages_scraped}/{self.max_pages}): {current_url} [{len(text)} chars]")

                # ALWAYS extract links for BFS — even when sitemap was found
                new_links = self._extract_all_links(soup, current_url, base_domain)
                for link in new_links:
                    if link not in visited:
                        queue.append(link)

                # Polite delay
                time.sleep(self.delay)

            except Exception as e:
                logger.warning(f"⚠️ Error scraping {current_url}: {str(e)}")
                continue

        logger.info(f"🎉 Scraping complete. Extracted {len(documents)} documents from {len(visited)} visited URLs.")
        return documents

    # ─────────────────────────────────────────────
    # Domain Resolution
    # ─────────────────────────────────────────────

    def _resolve_domain(self, url: str, base_domain: str) -> Tuple[str, str]:
        """Resolve actual domain after following redirects."""
        try:
            head_resp = self.session.head(url, timeout=10, allow_redirects=True)
            resolved_domain = urlparse(head_resp.url).netloc
            if resolved_domain:
                base_domain = resolved_domain
                logger.info(f"Resolved domain: {base_domain}")
        except Exception:
            pass
        resolved_base = f"{urlparse(url).scheme}://{base_domain}"
        return resolved_base, base_domain

    # ─────────────────────────────────────────────
    # Sitemap Discovery (comprehensive)
    # ─────────────────────────────────────────────

    def _discover_all_sitemaps(self, base_url: str) -> List[str]:
        """
        Discover ALL sitemap URLs using multiple strategies:
        1. Parse robots.txt for sitemap declarations
        2. Try known sitemap paths
        3. Recursively parse sitemap indexes
        """
        all_urls: Set[str] = set()
        sitemaps_to_parse: Set[str] = set()

        # Strategy 1: Check robots.txt for sitemap URLs
        robots_sitemaps = self._parse_robots_txt(base_url)
        sitemaps_to_parse.update(robots_sitemaps)
        if robots_sitemaps:
            logger.info(f"Found {len(robots_sitemaps)} sitemaps from robots.txt")

        # Strategy 2: Try all known sitemap paths
        for path in self.SITEMAP_PATHS:
            sitemap_url = urljoin(base_url, path)
            sitemaps_to_parse.add(sitemap_url)

        # Strategy 3: Parse all discovered sitemaps
        parsed_sitemaps: Set[str] = set()
        while sitemaps_to_parse:
            sitemap_url = sitemaps_to_parse.pop()
            if sitemap_url in parsed_sitemaps:
                continue
            parsed_sitemaps.add(sitemap_url)

            urls, sub_sitemaps = self._parse_sitemap(sitemap_url)
            all_urls.update(urls)

            # Add any discovered sub-sitemaps for parsing
            for sub in sub_sitemaps:
                if sub not in parsed_sitemaps:
                    sitemaps_to_parse.add(sub)

        return list(all_urls)[:self.max_pages * 2]  # Allow generous discovery

    def _parse_robots_txt(self, base_url: str) -> List[str]:
        """Extract sitemap URLs from robots.txt."""
        sitemaps = []
        try:
            robots_url = urljoin(base_url, '/robots.txt')
            response = self.session.get(robots_url, timeout=10)
            if response.status_code == 200:
                for line in response.text.splitlines():
                    line = line.strip()
                    if line.lower().startswith('sitemap:'):
                        sitemap_url = line.split(':', 1)[1].strip()
                        sitemaps.append(sitemap_url)
                        logger.debug(f"Found sitemap in robots.txt: {sitemap_url}")
        except Exception as e:
            logger.debug(f"Could not fetch robots.txt: {e}")
        return sitemaps

    def _parse_sitemap(self, sitemap_url: str) -> Tuple[List[str], List[str]]:
        """
        Parse a single sitemap XML file.

        Returns:
            Tuple of (page_urls, sub_sitemap_urls)
        """
        page_urls = []
        sub_sitemaps = []

        try:
            response = self.session.get(sitemap_url, timeout=15)
            if response.status_code != 200:
                return page_urls, sub_sitemaps

            content_start = response.text[:500].lower()
            is_xml = any(marker in content_start for marker in [
                '<?xml', '<urlset', '<sitemapindex',
            ])
            if not is_xml:
                return page_urls, sub_sitemaps

            soup = BeautifulSoup(response.text, 'lxml')

            # Handle sitemap index (contains links to other sitemaps)
            sitemap_tags = soup.find_all('sitemap')
            if sitemap_tags:
                for tag in sitemap_tags:
                    loc = tag.find('loc')
                    if loc and loc.text.strip():
                        sub_sitemaps.append(loc.text.strip())
                logger.debug(f"Sitemap index {sitemap_url}: {len(sub_sitemaps)} sub-sitemaps")
            else:
                # Regular sitemap with <url> tags
                for url_tag in soup.find_all('url'):
                    loc = url_tag.find('loc')
                    if loc and loc.text.strip():
                        page_urls.append(loc.text.strip())
                logger.debug(f"Sitemap {sitemap_url}: {len(page_urls)} URLs")

        except Exception as e:
            logger.debug(f"Error parsing sitemap {sitemap_url}: {e}")

        return page_urls, sub_sitemaps

    # ─────────────────────────────────────────────
    # CMS-Specific URL Discovery
    # ─────────────────────────────────────────────

    def _probe_cms_urls(self, base_url: str) -> List[str]:
        """
        Probe CMS-specific endpoints to discover additional pages.
        Supports WordPress, common blog patterns, and standard web patterns.
        """
        discovered = []

        # WordPress REST API — get all pages and posts
        wp_endpoints = [
            '/wp-json/wp/v2/pages?per_page=100&status=publish',
            '/wp-json/wp/v2/posts?per_page=100&status=publish',
            '/wp-json/wp/v2/categories?per_page=100',
        ]

        for endpoint in wp_endpoints:
            try:
                resp = self.session.get(urljoin(base_url, endpoint), timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        for item in data:
                            link = item.get('link') or item.get('url')
                            if link:
                                discovered.append(link)
                    logger.debug(f"WP API {endpoint}: found {len(data)} items")
            except Exception:
                pass

        # Common pages that might not be linked
        common_pages = [
            '/about', '/about-us', '/contact', '/contact-us',
            '/services', '/products', '/solutions', '/pricing',
            '/faq', '/faqs', '/help', '/support',
            '/blog', '/news', '/resources', '/case-studies',
            '/portfolio', '/testimonials', '/careers', '/jobs',
            '/privacy-policy', '/terms-of-service', '/terms',
            '/team', '/our-team', '/leadership',
            '/features', '/integrations', '/partners',
            '/demo', '/request-demo', '/schedule-demo',
            '/industries', '/clients', '/customers',
        ]

        for page in common_pages:
            page_url = urljoin(base_url, page)
            try:
                resp = self.session.head(page_url, timeout=5, allow_redirects=True)
                if resp.status_code == 200:
                    # Use the final URL after redirects
                    discovered.append(resp.url)
            except Exception:
                pass

        return discovered

    # ─────────────────────────────────────────────
    # Page Fetching (with retry)
    # ─────────────────────────────────────────────

    def _fetch_page_with_retry(self, url: str, max_retries: int = 2) -> Optional[requests.Response]:
        """Fetch a web page with retry logic."""
        for attempt in range(max_retries + 1):
            try:
                response = self.session.get(url, timeout=15, allow_redirects=True)
                content_type = response.headers.get('Content-Type', '')

                # Only process HTML content
                if 'text/html' not in content_type.lower():
                    return None

                if response.status_code == 200:
                    return response
                elif response.status_code == 429:
                    # Rate limited — wait and retry
                    wait = (attempt + 1) * 3
                    logger.debug(f"Rate limited on {url}, waiting {wait}s...")
                    time.sleep(wait)
                    continue
                elif response.status_code >= 500 and attempt < max_retries:
                    # Server error — retry
                    time.sleep(1)
                    continue
                else:
                    logger.debug(f"HTTP {response.status_code} for {url}")
                    return None
            except requests.exceptions.RequestException as e:
                if attempt < max_retries:
                    time.sleep(1)
                    continue
                logger.debug(f"Request failed for {url}: {str(e)}")
                return None
        return None

    # ─────────────────────────────────────────────
    # Content Extraction
    # ─────────────────────────────────────────────

    def _extract_text(self, soup: BeautifulSoup) -> str:
        """
        Extract clean text content from a parsed HTML page.
        Removes non-content elements while preserving important text.
        """
        # Create a copy to avoid modifying the original
        soup_copy = BeautifulSoup(str(soup), 'lxml')

        # Remove unwanted HTML tags
        for tag_name in self.REMOVE_TAGS:
            for tag in soup_copy.find_all(tag_name):
                tag.decompose()

        # Remove elements with non-content class names/IDs
        for pattern in self.REMOVE_PATTERNS:
            boundary_re = re.compile(
                r'(?:^|[\s_-])' + re.escape(pattern) + r'(?:$|[\s_-])', re.I
            )
            for element in soup_copy.find_all(class_=boundary_re):
                if len(element.get_text(strip=True)) < 500:
                    element.decompose()
            for element in soup_copy.find_all(id=boundary_re):
                if len(element.get_text(strip=True)) < 500:
                    element.decompose()

        # Remove hidden elements
        for element in soup_copy.find_all(style=re.compile(r'display\s*:\s*none', re.I)):
            element.decompose()

        # Try to find main content area
        main_content = (
            soup_copy.find('main') or
            soup_copy.find('article') or
            soup_copy.find(id=re.compile(r'content|main', re.I)) or
            soup_copy.find(class_=re.compile(r'content|main|post|article|entry', re.I)) or
            soup_copy.find('body')
        )

        if main_content:
            text = main_content.get_text(separator='\n', strip=True)
            if not text.strip() and main_content.name != 'body':
                body = soup_copy.find('body')
                if body:
                    text = body.get_text(separator='\n', strip=True)
        else:
            text = soup_copy.get_text(separator='\n', strip=True)

        # Also extract FAQ schema data
        faq_text = self._extract_faq_schema(soup)
        if faq_text:
            text += "\n\n" + faq_text

        # Also extract table data
        table_text = self._extract_tables(soup_copy)
        if table_text:
            text += "\n\n" + table_text

        return self._clean_text(text)

    def _extract_faq_schema(self, soup: BeautifulSoup) -> str:
        """Extract FAQ structured data (JSON-LD FAQPage schema)."""
        import json
        faq_items = []

        for script_tag in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script_tag.string or '')
                items = []

                # Handle single schema or array
                schemas = data if isinstance(data, list) else [data]
                for schema in schemas:
                    if schema.get('@type') == 'FAQPage':
                        items = schema.get('mainEntity', [])
                    elif schema.get('@type') == 'Question':
                        items = [schema]

                for item in items:
                    q = item.get('name', '')
                    a = item.get('acceptedAnswer', {})
                    answer_text = a.get('text', '') if isinstance(a, dict) else ''
                    if q and answer_text:
                        faq_items.append(f"Q: {q}\nA: {answer_text}")
            except (json.JSONDecodeError, AttributeError):
                pass

        if faq_items:
            return "Frequently Asked Questions:\n" + "\n\n".join(faq_items)
        return ""

    def _extract_tables(self, soup: BeautifulSoup) -> str:
        """Extract content from HTML tables (pricing, feature comparisons, etc.)."""
        table_texts = []

        for table in soup.find_all('table'):
            rows = []
            for tr in table.find_all('tr'):
                cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                if any(cells):
                    rows.append(' | '.join(cells))
            if len(rows) > 1:  # Only include tables with actual data
                table_texts.append('\n'.join(rows))

        return '\n\n'.join(table_texts) if table_texts else ""

    def _extract_meta_description(self, soup: BeautifulSoup) -> str:
        """Extract meta description from the page."""
        meta = soup.find('meta', attrs={'name': 'description'})
        if meta and meta.get('content', '').strip():
            return meta['content'].strip()

        og_desc = soup.find('meta', property='og:description')
        if og_desc and og_desc.get('content', '').strip():
            return og_desc['content'].strip()

        return ""

    def _clean_text(self, text: str) -> str:
        """Clean extracted text by removing extra whitespace and duplicates."""
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line:
                line = re.sub(r'\s+', ' ', line)
                cleaned_lines.append(line)

        # Remove consecutive duplicate lines
        final_lines = []
        for line in cleaned_lines:
            if not final_lines or line != final_lines[-1]:
                final_lines.append(line)

        return '\n'.join(final_lines)

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract the page title."""
        title_tag = soup.find('title')
        if title_tag and title_tag.text.strip():
            return title_tag.text.strip()

        h1_tag = soup.find('h1')
        if h1_tag and h1_tag.text.strip():
            return h1_tag.text.strip()

        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content', '').strip():
            return og_title['content'].strip()

        return 'Untitled Page'

    # ─────────────────────────────────────────────
    # Link Extraction (comprehensive)
    # ─────────────────────────────────────────────

    def _extract_all_links(self, soup: BeautifulSoup, current_url: str, base_domain: str) -> List[str]:
        """
        Extract ALL internal links from the page using multiple strategies:
        - <a href> tags
        - <link rel="canonical"> tags
        - <link rel="alternate"> tags
        - data-href attributes
        """
        links: Set[str] = set()

        # Strategy 1: Standard <a> tags
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].strip()
            if href.startswith(('#', 'javascript:', 'mailto:', 'tel:', 'data:')):
                continue
            absolute_url = self._normalize_url(urljoin(current_url, href))
            if self._is_valid_url(absolute_url, base_domain):
                links.add(absolute_url)

        # Strategy 2: Canonical and alternate links
        for link_tag in soup.find_all('link', href=True):
            rel = link_tag.get('rel', [])
            if isinstance(rel, list):
                rel = ' '.join(rel).lower()
            else:
                rel = str(rel).lower()
            if any(r in rel for r in ['canonical', 'alternate', 'next', 'prev']):
                href = link_tag['href'].strip()
                absolute_url = self._normalize_url(urljoin(current_url, href))
                if self._is_valid_url(absolute_url, base_domain):
                    links.add(absolute_url)

        # Strategy 3: Data attributes (some frameworks use data-href, data-url)
        for element in soup.find_all(attrs={'data-href': True}):
            href = element['data-href'].strip()
            absolute_url = self._normalize_url(urljoin(current_url, href))
            if self._is_valid_url(absolute_url, base_domain):
                links.add(absolute_url)

        return list(links)

    # ─────────────────────────────────────────────
    # URL Validation & Normalization
    # ─────────────────────────────────────────────

    def _normalize_url(self, url: str) -> str:
        """Normalize a URL by removing fragments, query params for duplicates, and trailing slashes."""
        parsed = urlparse(url)
        # Remove fragment
        normalized = parsed._replace(fragment='')
        url = normalized.geturl()
        # Remove trailing slash (except for root)
        if url.endswith('/') and url.count('/') > 3:
            url = url.rstrip('/')
        return url

    def _is_valid_url(self, url: str, base_domain: str) -> bool:
        """Check if a URL is valid for crawling."""
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

            # Skip URLs with unwanted file extensions
            path = parsed.path.lower()
            for ext in self.SKIP_EXTENSIONS:
                if path.endswith(ext):
                    return False

            return True
        except Exception:
            return False

    def _should_skip_path(self, url: str) -> bool:
        """Check if the URL path matches any skip patterns."""
        parsed = urlparse(url)
        path = parsed.path + ('?' + parsed.query if parsed.query else '')
        for pattern in self._skip_patterns:
            if pattern.search(path):
                return True
        return False
