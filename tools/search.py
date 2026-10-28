"""
tools/search.py
Web search interface for research stage.

SandBase search endpoints (called over the SandBase MCP endpoint, same as `sandbase run`):
  tavily  -> sandbase_tavily_search       $0.012/call
  exa     -> sandbase_exa_search          $0.0105/call
  scholar -> sandbase_scholar_search_web  $0.0036/call
Discovered 2026-10-28 with `npx -y @sandbaseai/cli@latest discover/inspect`.
At that time every one returned status "completed" with output null, so an engine
that returns no output is disabled for the rest of the process and the official
Wikipedia Search API is used instead (MASTER_PLAN §3 stage 1 fallback).
"""

import json
import os
import threading
import urllib.parse
from typing import Any, Dict, List, Optional
import requests


USER_AGENT = "CityRemixResearch/1.0 (+https://github.com/sandbase-lab/awesome-minimax-m3-1-flash)"

SANDBASE_MCP_URL = "https://api.sandbase.ai/v1/mcp"
SANDBASE_ENGINES = {
    "tavily": ("sandbase_tavily_search", lambda q, n: {"query": q, "max_results": n}),
    "exa": ("sandbase_exa_search", lambda q, n: {"query": q, "numResults": n}),
    "scholar": ("sandbase_scholar_search_web", lambda q, n: {"query": q, "max_num_results": n}),
}
ENGINES = list(SANDBASE_ENGINES) + ["wikipedia"]

_dead_engines: set = set()
_dead_lock = threading.Lock()


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


def _normalise_results(output: Any, engine: str) -> List[Dict[str, str]]:
    """Map a provider's output to [{title, url, snippet, engine}]."""
    items = output
    if isinstance(output, dict):
        items = output.get("results") or output.get("data") or output.get("organic_results") or []
    results = []
    for r in items if isinstance(items, list) else []:
        if not isinstance(r, dict) or not r.get("url"):
            continue
        results.append({
            "title": r.get("title", ""),
            "url": r["url"],
            "snippet": (r.get("content") or r.get("snippet") or r.get("description") or r.get("text") or "")[:500],
            "engine": engine,
        })
    return results


def sandbase_search(query: str, engine: str, limit: int = 5) -> Optional[List[Dict[str, str]]]:
    """Run one SandBase search tool. Returns None when the engine gives no usable output."""
    api_key = os.environ.get("SANDBASE_API_KEY")
    if not api_key or engine in _dead_engines:
        return None
    tool_name, build_args = SANDBASE_ENGINES[engine]
    body = {
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "sandbase_run", "arguments": {"name": tool_name, "arguments": build_args(query, limit)}},
    }
    headers = {
        "authorization": f"Bearer {api_key}",
        "content-type": "application/json",
        "accept": "application/json, text/event-stream",
    }
    try:
        resp = requests.post(SANDBASE_MCP_URL, headers=headers, json=body, timeout=120)
        text = resp.text
        if "text/event-stream" in resp.headers.get("content-type", ""):
            text = [l[5:].strip() for l in text.splitlines() if l.startswith("data:")][-1]
        result = json.loads(text).get("result", {})
        output = (result.get("structuredContent") or {}).get("output")
        results = _normalise_results(output, engine)
    except Exception:
        results = []
    if not results:
        with _dead_lock:
            _dead_engines.add(engine)
        print(f"[search] SandBase engine '{engine}' returned no output; disabled for this run, using Wikipedia.")
        return None
    return results


def web_search(query: str, engine: str = "tavily", limit: int = 5) -> List[Dict[str, str]]:
    """
    Search with the requested SandBase engine; fall back to the Wikipedia Search API
    if that engine is unavailable.
    """
    if engine in SANDBASE_ENGINES:
        results = sandbase_search(query, engine, limit)
        if results is not None:
            return results
    return wikipedia_search(query=query, limit=limit)


def available_engines() -> List[str]:
    """Engines not yet found to be broken in this process."""
    return [e for e in ENGINES if e not in _dead_engines]
