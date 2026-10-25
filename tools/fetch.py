"""
tools/fetch.py
Fetches URLs, extracts readable clean text using BeautifulSoup, and caches to disk.
"""

import hashlib
import time
from pathlib import Path
from typing import Dict, Any, Tuple
import requests
from bs4 import BeautifulSoup


USER_AGENT = "CityRemixResearch/1.0 (+https://github.com/sandbase-lab/awesome-minimax-m3-1-flash)"


def get_cache_path(url: str, cache_dir: Path) -> Path:
    """Compute sha1 hash path for a given URL."""
    sha1 = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return cache_dir / "sources" / f"{sha1}.txt"


def fetch_url(url: str, cache_dir: Path, offset: int = 0, limit: int = 30000) -> Dict[str, Any]:
    """
    Fetch URL with a descriptive User-Agent, extract readable text,
    cache to sources/<sha1>.txt with URL and timestamp header, and return 30k chars from offset.
    """
    sources_dir = cache_dir / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    cache_file = get_cache_path(url, cache_dir)

    # Check cache first
    if cache_file.is_file():
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
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "form"]):
            tag.decompose()

        # Get text and clean excess whitespace
        raw_text = soup.get_text(separator="\n")
        cleaned_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        body_text = "\n".join(cleaned_lines)

        timestamp_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        header = f"URL: {url}\nFETCHED: {timestamp_iso}\n"
        full_content = header + body_text

        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(full_content)

        chunk = body_text[offset : offset + limit]
        return {
            "url": url,
            "cached": False,
            "cache_file": str(cache_file),
            "total_length": len(body_text),
            "offset": offset,
            "chunk": chunk,
        }

    except Exception as e:
        return {
            "url": url,
            "error": f"Failed to fetch {url}: {str(e)}",
            "chunk": "",
        }
