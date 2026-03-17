"""Debug: find which REMOVE_PATTERN kills all text."""
import re
import requests
from bs4 import BeautifulSoup

REMOVE_TAGS = ['script', 'style', 'aside', 'form', 'iframe', 'noscript']
REMOVE_PATTERNS = ['nav', 'navbar', 'menu', 'sidebar', 'footer', 'header',
                   'advertisement', 'ad-', 'ads-', 'cookie', 'popup', 'modal',
                   'social', 'share', 'comment', 'breadcrumb', 'pagination']

s = requests.Session()
s.headers.update({"User-Agent": "AriaBot/1.0"})
r = s.get("https://www.nevastech.com/", timeout=15)
soup = BeautifulSoup(str(BeautifulSoup(r.text, "lxml")), "lxml")

for tag_name in REMOVE_TAGS:
    for tag in soup.find_all(tag_name):
        tag.decompose()

body = soup.find("body")
prev_len = len(body.get_text(strip=True))
print(f"Before patterns: {prev_len} chars")

for pattern in REMOVE_PATTERNS:
    # Make a copy for this test
    test_soup = BeautifulSoup(str(soup), "lxml")
    boundary_re = re.compile(r"(?:^|[\s_-])" + re.escape(pattern) + r"(?:$|[\s_-])", re.I)
    
    removed_items = []
    for element in test_soup.find_all(class_=boundary_re):
        removed_items.append(f"class={element.get('class',[])} tag={element.name}")
        element.decompose()
    for element in test_soup.find_all(id=boundary_re):
        removed_items.append(f"id={element.get('id','')} tag={element.name}")
        element.decompose()
    
    test_body = test_soup.find("body")
    new_len = len(test_body.get_text(strip=True)) if test_body else 0
    if removed_items:
        print(f"  Pattern [{pattern}]: {prev_len} -> {new_len} chars ({len(removed_items)} elements)")
        for item in removed_items:
            print(f"    removed: {item}")
