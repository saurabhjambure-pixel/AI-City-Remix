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
from tools.search import ENGINES, web_search


MAX_SEARCH_CALLS = 60
MAX_FETCH_CALLS = 80
MAX_SAVE_REVISIONS = 1  # after the first save_claims, code-check failures are returned once for fixing


RESEARCH_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for historical, geographic, or cultural pages about the city. SandBase engines that are unavailable fall back to Wikipedia search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Specific search query"},
                    "engine": {"type": "string", "enum": ENGINES, "default": "tavily"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Fetch a webpage, extract clean text, cache to disk, and return 30k characters of text from offset plus the page's outbound links (e.g. a Wikipedia article's references).",
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


def save_feedback(claims: List[Dict[str, Any]], output_dir: Path) -> List[Dict[str, Any]]:
    """Run the verify stage's deterministic code check and list what would be discarded."""
    from stages.verify import MIN_PUBLISHERS, code_check
    problems = []
    for c in claims:
        checked = code_check(c, output_dir)
        if checked["source_failures"] or checked["independent_sources"] < MIN_PUBLISHERS:
            problems.append({
                "id": c.get("id"),
                "independent_publishers": checked["independent_sources"],
                "rejected_sources": checked["source_failures"],
            })
    return problems


def run_research_stage(
    city: str,
    output_dir: Path,
    client: SandBaseClient,
    force: bool = False,
    max_turns: int = 60,
    extend: bool = False,
    priority_clusters: Optional[List[str]] = None,
) -> Path:
    """Execute Stage 1: Research.

    extend=True keeps the raw claims that verify already kept (claims.json) and asks M3.1 for
    NEW claims only, prioritising priority_clusters; the saved file is kept + new.
    """
    claims_raw_path = output_dir / "claims.raw.json"
    if claims_raw_path.is_file() and not force:
        print(f"[Stage 1: Research] Reusing existing {claims_raw_path}")
        return claims_raw_path

    output_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = Path("prompts/research.md")
    with open(prompt_file, "r", encoding="utf-8") as f:
        system_prompt = f.read().format(city=city)

    prior: List[Dict[str, Any]] = []
    kept_path = output_dir / "claims.json"
    if extend and claims_raw_path.is_file() and kept_path.is_file():
        kept_ids = {c["id"] for c in json.loads(kept_path.read_text(encoding="utf-8"))}
        prior = [c for c in json.loads(claims_raw_path.read_text(encoding="utf-8")) if c["id"] in kept_ids]
        print(f"[Stage 1: Research] Extending: keeping {len(prior)} previously verified raw claims")

    task = (
        f"Begin thorough factual research on {city}.\n"
        f"Use web_search and fetch_url to find authoritative information.\n"
        f"Target 35-50 claims across the 9 clusters.\n"
        f"CRITICAL: Every claim needs at least 2 independent publishers, and EACH quote must ON ITS OWN state the "
        f"whole claim (every name, date and number in it). A quote that is only on the same topic, or that states "
        f"half the claim, does not count. Keep claims short and single-fact so two publishers can both state them.\n"
        f"When you have collected claims across all clusters, call save_claims."
    )
    if prior:
        from collections import Counter
        counts = Counter(c["cluster"] for c in prior)
        task = (
            f"Continue factual research on {city}. These claims are ALREADY VERIFIED; do not repeat them:\n"
            + "\n".join(f"- [{c['cluster']}] {c['claim']}" for c in prior)
            + f"\n\nVerified claims per cluster: {dict(counts)}.\n"
            f"Find 35-45 NEW claims. Priority: {', '.join(priority_clusters or [])} (at least 10 new claims each, "
            f"they currently have none or few); then clusters with fewer than 4 verified claims.\n"
            f"CRITICAL: Every claim needs at least 2 independent publishers, and EACH quote must ON ITS OWN state the "
            f"whole claim (every name, date and number in it). A quote that is only on the same topic, or that states "
            f"half the claim, does not count; earlier claims were dropped for exactly this. Keep claims short and "
            f"single-fact so two publishers can both state them. Use ids c101, c102, ...\n"
            f"Call save_claims with the NEW claims only."
        )
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task},
    ]

    search_count = 0
    fetch_count = 0
    claims_saved = False
    save_revisions = 0

    turn = 0
    while turn < max_turns and not claims_saved:
        turn += 1
        if turn == max_turns - 1 and not claims_raw_path.is_file():
            messages.append({"role": "user", "content": "Turn limit reached. Call save_claims now with every claim you have."})
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
                    res = web_search(query, engine=args.get("engine", "tavily"))
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
                prior_ids = {c["id"] for c in prior}
                for n, c in enumerate(claims):
                    if c.get("id") in prior_ids:
                        c["id"] = f"c{901 + n}"
                with open(claims_raw_path, "w", encoding="utf-8") as f:
                    json.dump(prior + claims, f, indent=2, ensure_ascii=False)
                print(f"[Stage 1: Research] Saved {len(prior)} kept + {len(claims)} new raw claims to {claims_raw_path}")
                feedback = save_feedback(claims, output_dir)
                if feedback and save_revisions < MAX_SAVE_REVISIONS:
                    save_revisions += 1
                    result_str = json.dumps({
                        "status": "saved_with_problems", "count": len(claims),
                        "problems": feedback,
                        "instruction": "Fix these (re-copy complete sentences, add a source from another publisher, "
                                       "or drop the claim), then call save_claims again with the FULL corrected list.",
                    }, ensure_ascii=False)
                else:
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
