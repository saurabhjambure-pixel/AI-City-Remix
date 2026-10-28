"""
stages/research.py
Stage 1: Research (M3.1 + tools, effort 'high')
Discovers facts and verbatim quotes across 9 clusters using web_search and fetch_url.
Saves output/<city>/claims.raw.json and caches sources to output/<city>/sources/<sha1>.txt.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from sandbase_client import SandBaseClient
from tools.fetch import fetch_url
from tools.search import web_search


MAX_SEARCH_CALLS = 60
MAX_FETCH_CALLS = 80


RESEARCH_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web/Wikipedia for historical, geographic, or cultural articles about the city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Specific search query"},
                    "engine": {"type": "string", "enum": ["auto", "wikipedia"], "default": "auto"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Fetch a webpage, extract clean text, cache to disk, and return 30k characters of text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL to fetch"},
                    "offset": {"type": "integer", "description": "Character offset to read from", "default": 0}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_claims",
            "description": "Save collected factual claims with verbatim quotes to claims.raw.json.",
            "parameters": {
                "type": "object",
                "properties": {
                    "claims": {
                        "type": "array",
                        "description": "List of 40-60 claims with sources and verbatim quotes",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string", "description": "e.g. c001, c002"},
                                "cluster": {
                                    "type": "string",
                                    "enum": ["geography", "origins", "maratha", "peshwa", "british", "education", "industry", "it_growth", "culture"]
                                },
                                "claim": {"type": "string"},
                                "kind": {
                                    "type": "string",
                                    "enum": ["event", "date", "number", "place", "name", "culture"]
                                },
                                "value": {"type": ["string", "number", "null"]},
                                "sources": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "url": {"type": "string"},
                                            "quote": {"type": "string", "description": "Exact verbatim quote copied from fetched text"}
                                        },
                                        "required": ["url", "quote"]
                                    }
                                }
                            },
                            "required": ["id", "cluster", "claim", "kind", "sources"]
                        }
                    }
                },
                "required": ["claims"]
            }
        }
    }
]


def run_research_stage(
    city: str,
    output_dir: Path,
    client: SandBaseClient,
    force: bool = False,
    max_turns: int = 35,
) -> Path:
    """Execute Stage 1: Research."""
    claims_raw_path = output_dir / "claims.raw.json"
    if claims_raw_path.is_file() and not force:
        print(f"[Stage 1: Research] Reusing existing {claims_raw_path}")
        return claims_raw_path

    output_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = Path("prompts/research.md")
    with open(prompt_file, "r", encoding="utf-8") as f:
        system_prompt = f.read().format(city=city)

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Begin thorough factual research on {city}.\n"
                f"Use web_search and fetch_url to find authoritative information.\n"
                f"Target 35-50 claims across the 9 clusters.\n"
                f"CRITICAL: Every single claim MUST include at least 2 independent sources from DIFFERENT domains "
                f"(e.g. .gov.in, .ac.in, .edu, reputable archives, Wikipedia) with verbatim quotes copied directly from fetched text.\n"
                f"Single-source claims will be dropped by the verifier.\n"
                f"When you have collected claims across all clusters, call save_claims."
            ),
        },
    ]

    search_count = 0
    fetch_count = 0
    claims_saved = False

    turn = 0
    while turn < max_turns and not claims_saved:
        turn += 1
        print(f"[Stage 1: Research] Turn {turn}/{max_turns} (Searches: {search_count}/{MAX_SEARCH_CALLS}, Fetches: {fetch_count}/{MAX_FETCH_CALLS})...")

        assistant_msg = client.chat(
            stage="research",
            messages=messages,
            effort="high",
            max_tokens=32000,
            tools=RESEARCH_TOOLS,
            output_file_path=str(claims_raw_path),
        )

        messages.append(assistant_msg)
        tool_calls = assistant_msg.get("tool_calls", [])

        if not tool_calls:
            # If the model didn't call tools, prompt it to proceed
            content = assistant_msg.get("content", "")
            if "save_claims" not in content:
                messages.append({
                    "role": "user",
                    "content": "Please continue researching via web_search / fetch_url, or call save_claims if you have compiled 40-60 verified claims."
                })
            continue

        for tc in tool_calls:
            call_id = tc["id"]
            fn_name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"])
            except Exception:
                args = {}

            result_str = ""

            if fn_name == "web_search":
                if search_count >= MAX_SEARCH_CALLS:
                    result_str = json.dumps({"warning": "Search budget exhausted. Proceed to fetch or save claims."})
                else:
                    search_count += 1
                    query = args.get("query", city)
                    res = web_search(query)
                    result_str = json.dumps(res, ensure_ascii=False)

            elif fn_name == "fetch_url":
                if fetch_count >= MAX_FETCH_CALLS:
                    result_str = json.dumps({"warning": "Fetch budget exhausted. Proceed to save claims."})
                else:
                    fetch_count += 1
                    url = args.get("url", "")
                    offset = args.get("offset", 0)
                    res = fetch_url(url=url, cache_dir=output_dir, offset=offset)
                    result_str = json.dumps(res, ensure_ascii=False)

            elif fn_name == "save_claims":
                claims = args.get("claims", [])
                with open(claims_raw_path, "w", encoding="utf-8") as f:
                    json.dump(claims, f, indent=2, ensure_ascii=False)
                print(f"[Stage 1: Research] Saved {len(claims)} raw claims to {claims_raw_path}")
                result_str = json.dumps({"status": "saved", "count": len(claims), "file": str(claims_raw_path)})
                claims_saved = True

            else:
                result_str = json.dumps({"error": f"Unknown tool: {fn_name}"})

            # Append tool result preserving conversation history
            messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "content": result_str,
            })

    if not claims_raw_path.is_file():
        raise RuntimeError(f"Stage 1 failed: claims.raw.json was not generated.")

    return claims_raw_path
