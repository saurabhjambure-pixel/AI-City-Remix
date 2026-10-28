"""
tools/fetch.py
Fetches URLs, extracts readable clean text using BeautifulSoup, and caches to disk.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup


USER_AGENT = "CityRemixResearch/1.0 (+https://github.com/sandbase-lab/awesome-minimax-m3-1-flash)"


def get_cache_path(url: str, cache_dir: Path) -> Path:
    """Compute sha1 hash path for a given URL."""
    sha1 = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return cache_dir / "sources" / f"{sha1}.txt"


WIKI_FAMILY = ("wikipedia.org", "wikimedia.org", "wikidata.org", "wikisource.org", "wiktionary.org", "wikimediafoundation.org")
NOISE_HOSTS = ("toolforge.org", "wmflabs.org", "google.com", "worldcat.org", "openstreetmap.org")
MAX_LINKS = 100


def get_links_path(url: str, cache_dir: Path) -> Path:
    return get_cache_path(url, cache_dir).with_suffix(".links.json")


def extract_outbound_links(soup: BeautifulSoup, page_url: str) -> List[Dict[str, str]]:
    """External links on the page (e.g. a Wikipedia article's cited references), so the
    researcher can follow them to independent publishers."""
    page_host = urlparse(page_url).netloc.lower()
    seen, links = set(), []
    for a in soup.find_all("a", href=True):
        href = urljoin(page_url, a["href"]).split("#")[0]
        host = urlparse(href).netloc.lower()
        if not href.startswith(("http://", "https://")) or not host or host == page_host:
            continue
        if any(host == d or host.endswith("." + d) for d in WIKI_FAMILY + NOISE_HOSTS):
            continue
        if "search?" in href or "/search/" in href or "doBasicSearch" in href:
            continue
        if href in seen:
            continue
        seen.add(href)
        links.append({"url": href, "text": " ".join(a.get_text(" ").split())[:120]})
        if len(links) >= MAX_LINKS:
            break
    return links


BLOCK_TAGS = ["p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "div", "section", "article",
              "blockquote", "dd", "dt", "table", "caption", "figcaption", "pre", "ul", "ol", "td", "th"]


def extract_text(soup: BeautifulSoup) -> str:
    """Browser-like text: inline elements stay inside their sentence, newlines only between
    blocks, Wikipedia citation markers ([12]) and edit links removed."""
    for tag in soup.select("sup.reference, sup.noprint, span.mw-editsection, .mw-cite-backlink"):
        tag.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for tag in soup.find_all(BLOCK_TAGS):
        tag.insert_before("\n")
        tag.append("\n")
    lines = (" ".join(line.split()) for line in soup.get_text().splitlines())
    return "\n".join(line for line in lines if line)


def fetch_url(url: str, cache_dir: Path, offset: int = 0, limit: int = 30000) -> Dict[str, Any]:
    """
    Fetch URL with a descriptive User-Agent, extract readable text,
    cache to sources/<sha1>.txt with URL and timestamp header, and return 30k chars from offset.
    """
    sources_dir = cache_dir / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    cache_file = get_cache_path(url, cache_dir)

    links_file = get_links_path(url, cache_dir)

    # Check cache first (pages cached before link extraction existed are refetched)
    if cache_file.is_file() and links_file.is_file():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                content = f.read()
            # Drop the first 2 lines (URL & Timestamp header)
            lines = content.splitlines(keepends=True)
            body = "".join(lines[2:]) if len(lines) >= 2 else content
            chunk = body[offset : offset + limit]
            return {
                "url": url,
                "cached": True,
                "cache_file": str(cache_file),
                "total_length": len(body),
                "offset": offset,
                "chunk": chunk,
                "links": json.loads(links_file.read_text(encoding="utf-8")) if offset == 0 else [],
            }
        except Exception:
            pass

    # Fetch live
    try:
        headers = {"User-Agent": USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        # Parse text with BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        links = extract_outbound_links(soup, url)
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "form"]):
            tag.decompose()

        # Get text and clean excess whitespace
        body_text = extract_text(soup)

        timestamp_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        header = f"URL: {url}\nFETCHED: {timestamp_iso}\n"
        full_content = header + body_text

        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(full_content)
        links_file.write_text(json.dumps(links, ensure_ascii=False), encoding="utf-8")

        chunk = body_text[offset : offset + limit]
        return {
            "url": url,
            "cached": False,
            "cache_file": str(cache_file),
            "total_length": len(body_text),
            "offset": offset,
            "chunk": chunk,
            "links": links if offset == 0 else [],
        }

    except Exception as e:
        return {
            "url": url,
            "error": f"Failed to fetch {url}: {str(e)}",
            "chunk": "",
        }
