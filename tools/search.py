"""
tools/search.py
Web search interface for research stage.
Integrates SandBase search tools or falls back to official Wikipedia Search API.
"""

import os
import urllib.parse
from typing import Any, Dict, List, Optional
import requests


USER_AGENT = "CityRemixResearch/1.0 (+https://github.com/sandbase-lab/awesome-minimax-m3-1-flash)"


def wikipedia_search(query: str, limit: int = 5) -> List[Dict[str, str]]:
    """Search Wikipedia API for articles matching query."""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "utf8": "",
        "format": "json",
        "srlimit": limit,
    }
    url = f"https://en.wikipedia.org/w/api.php?{urllib.parse.urlencode(params)}"
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        search_results = data.get("query", {}).get("search", [])

        results = []
        for r in search_results:
            title = r.get("title", "")
            snippet = r.get("snippet", "").replace('<span class="searchmatch">', "").replace("</span>", "")
            page_url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
            results.append({
                "title": title,
                "url": page_url,
                "snippet": snippet,
                "engine": "wikipedia",
            })
        return results
    except Exception as e:
        return [{"error": f"Wikipedia search failed: {str(e)}"}]


def web_search(query: str, engine: str = "auto", limit: int = 5) -> List[Dict[str, str]]:
    """
    Search web using SandBase endpoint or Wikipedia search API.
    """
    # Fallback to Wikipedia search API
    return wikipedia_search(query=query, limit=limit)
