"""
stages/verify.py
Stage 2: Verify (code check + corroboration + M3.1 judge)
1. Code check: each quote must be a complete sentence, appear verbatim in the cached page,
   and (for date/number claims) contain the claim's value.
2. Corroboration (M3.1 + tools, effort 'high'): claims with < 2 independent publishers get
   up to 3 searches to add a source from a new publisher. The new source passes the same code check.
3. M3.1 judge (effort 'xhigh') decides from the quotes alone.
4. Keep rule: supported AND >= 2 independent publishers (CLAUDE.md §4A; supersedes the
   3-source rule for dates and numbers).
Writes claims.checked.json (resume point), claims.json and research-report.json.
"""

import json
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

import tldextract

from sandbase_client import SandBaseClient, strip_markdown_fences
from tools.fetch import WIKI_FAMILY, fetch_url, get_cache_path
from tools.search import available_engines, web_search


MIN_PUBLISHERS = 2
CORROBORATE_MAX_SEARCHES = 3
CORROBORATE_MAX_FETCHES = 6
CORROBORATE_MAX_TURNS = 12
CORROBORATE_WORKERS = 8
JUDGE_BATCH = 5
JUDGE_WORKERS = 4

_EXTRACT = tldextract.TLDExtract(suffix_list_urls=())  # bundled public-suffix snapshot, no network
CITE_MARKER = re.compile(r"\[\s*(?:\d+|[a-z]|citation needed|note \d+|nb \d+)\s*\]", re.I)
SENTENCE_START = re.compile(r"^[\"'“‘(\[]*[A-Z0-9]")
SENTENCE_END = re.compile(r"[.!?][\"'”’)\]]*$")
PUNCT_MAP = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-", " ": " "})


def normalize_text(text: str) -> str:
    """Normalise citation markers, quote/dash styles, whitespace and case for substring checking."""
    text = CITE_MARKER.sub(" ", text).translate(PUNCT_MAP)
    return re.sub(r"\s+", " ", text).strip().lower()


def extract_registrable_domain(url: str) -> str:
    """Registrable domain of the original publisher. Wikipedia-family sites count as one;
    web.archive.org snapshots count as the archived site."""
    m = re.match(r"https?://web\.archive\.org/web/[^/]+/(.+)", url)
    if m:
        url = m.group(1) if m.group(1).startswith("http") else "http://" + m.group(1)
    host = urlparse(url).netloc.lower()
    if any(host == d or host.endswith("." + d) for d in WIKI_FAMILY):
        return "wikipedia.org"
    ext = _EXTRACT(url)
    return getattr(ext, "top_domain_under_public_suffix", None) or ext.registered_domain or host or "unknown"


def numeric_tokens(text: Any) -> Set[str]:
    return {t.replace(",", "") for t in re.findall(r"\d[\d,]*(?:\.\d+)?", str(text or ""))}


def quote_problem(quote: str, claim: Dict[str, Any]) -> Optional[str]:
    """Why a quote is unusable as evidence, or None if it is fine."""
    q = CITE_MARKER.sub("", quote).strip()
    if len(q) < 25 or not SENTENCE_START.match(q) or not SENTENCE_END.search(q):
        return "quote is not a complete sentence (must start a sentence and end with . ! or ?)"
    if claim.get("kind") in ("date", "number"):
        have = numeric_tokens(q)
        want = numeric_tokens(claim.get("value"))
        if want and not want <= have:
            return f"quote does not contain the claim's value '{claim.get('value')}'"
        if not want and not (numeric_tokens(claim.get("claim")) & have):
            return "date/number claim but the quote contains none of its numbers"
    return None


def read_cached_body(url: str, output_dir: Path) -> Optional[str]:
    cache_file = get_cache_path(url, output_dir)
    if not cache_file.is_file():
        return None
    lines = cache_file.read_text(encoding="utf-8").splitlines(keepends=True)
    return "".join(lines[2:])  # drop URL/FETCHED header


def check_source(src: Dict[str, Any], claim: Dict[str, Any], output_dir: Path) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    """Deterministic check of one source. Returns (clean source, None) or (None, reason)."""
    url = (src.get("url") or "").strip()
    quote = (src.get("quote") or "").strip()
    if not url or not quote:
        return None, "missing url or quote"
    body = read_cached_body(url, output_dir)
    if body is None:
        return None, "page was never fetched"
    problem = quote_problem(quote, claim)
    if problem:
        return None, problem
    if normalize_text(quote) not in normalize_text(body):
        return None, "quote not found verbatim in the fetched page"
    return {
        "url": url,
        "domain": extract_registrable_domain(url),
        "quote": quote,
        "cache": str(get_cache_path(url, output_dir).relative_to(output_dir)),
    }, None


def code_check(claim: Dict[str, Any], output_dir: Path) -> Dict[str, Any]:
    surviving, failures, seen = [], [], set()
    for s in claim.get("sources", []):
        clean, reason = check_source(s, claim, output_dir)
        if clean and (clean["url"], normalize_text(clean["quote"])) not in seen:
            seen.add((clean["url"], normalize_text(clean["quote"])))
            surviving.append(clean)
        elif reason:
            failures.append({"url": s.get("url"), "reason": reason})
    out = dict(claim)
    out["sources"] = surviving
    out["independent_sources"] = len({s["domain"] for s in surviving})
    out["source_failures"] = failures
    return out


def corroboration_tools() -> List[Dict[str, Any]]:
    return [
        {"type": "function", "function": {
            "name": "web_search",
            "description": "Search the web. Unavailable engines silently fall back to Wikipedia search.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"},
                "engine": {"type": "string", "enum": available_engines()},
            }, "required": ["query"]}}},
        {"type": "function", "function": {
            "name": "fetch_url",
            "description": "Fetch a page; returns 30k chars of text from offset plus the page's outbound links (e.g. a Wikipedia article's references).",
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string"}, "offset": {"type": "integer", "default": 0},
            }, "required": ["url"]}}},
        {"type": "function", "function": {
            "name": "add_source",
            "description": "Attach a corroborating source: a fetched URL and a verbatim quote of one or more complete sentences from it.",
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string"}, "quote": {"type": "string"},
            }, "required": ["url", "quote"]}}},
        {"type": "function", "function": {
            "name": "give_up",
            "description": "Stop: no independent publisher supporting this claim was found.",
            "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}}},
    ]


def corroborate(claim: Dict[str, Any], output_dir: Path, client: SandBaseClient) -> Dict[str, Any]:
    """Tool loop in which M3.1 adds sources from new publishers until the claim has MIN_PUBLISHERS."""
    claim = dict(claim)
    publishers = {s["domain"] for s in claim["sources"]}
    system = Path("prompts/corroborate.md").read_text(encoding="utf-8")
    task = {
        "claim": claim["claim"],
        "kind": claim["kind"],
        "value": claim.get("value"),
        "existing_sources": [{"url": s["url"], "publisher": s["domain"], "quote": s["quote"]} for s in claim["sources"]],
        "publishers_needed": MIN_PUBLISHERS - len(publishers),
        "rejected_earlier": claim.get("source_failures", []),
    }
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(task, ensure_ascii=False, indent=2)},
    ]
    searches = fetches = 0
    log: List[str] = []
    for _ in range(CORROBORATE_MAX_TURNS):
        msg = client.chat(stage="verify_corroborate", messages=messages, effort="high", max_tokens=32000,
                          tools=corroboration_tools(), scene_id=claim["id"])
        messages.append(msg)
        calls = msg.get("tool_calls") or []
        if not calls:
            break
        stop = False
        for tc in calls:
            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except Exception:
                args = {}
            if name == "web_search":
                if searches >= CORROBORATE_MAX_SEARCHES:
                    result = {"error": "search budget (3) spent; fetch links you already have or give_up"}
                else:
                    searches += 1
                    result = web_search(args.get("query", claim["claim"]), engine=args.get("engine", "tavily"))
            elif name == "fetch_url":
                if fetches >= CORROBORATE_MAX_FETCHES:
                    result = {"error": "fetch budget (6) spent; add_source or give_up"}
                else:
                    fetches += 1
                    result = fetch_url(args.get("url", ""), cache_dir=output_dir, offset=int(args.get("offset", 0) or 0))
            elif name == "add_source":
                clean, reason = check_source(args, claim, output_dir)
                if not clean:
                    result = {"ok": False, "error": reason}
                elif clean["domain"] in publishers:
                    result = {"ok": False, "error": f"publisher {clean['domain']} is already counted; need a different publisher"}
                else:
                    claim["sources"] = claim["sources"] + [clean]
                    publishers.add(clean["domain"])
                    log.append(f"added {clean['domain']}")
                    result = {"ok": True, "publishers": sorted(publishers)}
                    stop = len(publishers) >= MIN_PUBLISHERS
            elif name == "give_up":
                log.append(f"gave up: {args.get('reason', '')}")
                result = {"ok": True}
                stop = True
            else:
                result = {"error": f"unknown tool {name}"}
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(result, ensure_ascii=False)})
        if stop:
            break
    claim["independent_sources"] = len(publishers)
    claim["corroboration"] = {"searches": searches, "fetches": fetches, "log": log}
    return claim


def judge_batch(batch: List[Dict[str, Any]], client: SandBaseClient, verify_prompt: str) -> Dict[str, Dict[str, Any]]:
    batch_input = [{"id": c["id"], "claim": c["claim"], "kind": c["kind"], "value": c.get("value"),
                    "quotes": [s["quote"] for s in c["sources"]]} for c in batch]
    messages = [
        {"role": "system", "content": verify_prompt},
        {"role": "user", "content": (
            "Evaluate these claims based strictly on the provided verbatim quotes.\n"
            "Return a JSON list of objects: [{\"id\": \"...\", \"supported\": true|false, \"reason\": \"...\", \"corrected_claim\": \"...\"|null}]\n\n"
            f"{json.dumps(batch_input, indent=2, ensure_ascii=False)}")},
    ]
    msg = client.chat(stage="verify", messages=messages, effort="xhigh", max_tokens=32000,
                      schema_path="schemas/verdicts.json", scene_id=",".join(c["id"] for c in batch))
    verdicts = json.loads(strip_markdown_fences(msg.get("content") or "[]"))
    return {v["id"]: v for v in verdicts}


def run_verify_stage(
    city: str,
    output_dir: Path,
    client: SandBaseClient,
    force: bool = False,
) -> Tuple[Path, Path]:
    """Execute Stage 2: Verify."""
    claims_path = output_dir / "claims.json"
    report_path = output_dir / "research-report.json"
    checked_path = output_dir / "claims.checked.json"

    if claims_path.is_file() and report_path.is_file() and not force:
        print(f"[Stage 2: Verify] Reusing existing {claims_path} and {report_path}")
        return claims_path, report_path

    raw_claims_file = output_dir / "claims.raw.json"
    if not raw_claims_file.is_file():
        raise FileNotFoundError(f"Missing {raw_claims_file}. Stage 1 must be run first.")
    raw_claims = json.loads(raw_claims_file.read_text(encoding="utf-8"))

    # 1 + 2. Code check, then corroborate claims short of publishers (resumable via claims.checked.json)
    if checked_path.is_file() and not force and checked_path.stat().st_mtime >= raw_claims_file.stat().st_mtime:
        print(f"[Stage 2: Verify] Reusing corroborated claims from {checked_path}")
        checked = json.loads(checked_path.read_text(encoding="utf-8"))
    else:
        checked = [code_check(c, output_dir) for c in raw_claims]
        need = [i for i, c in enumerate(checked) if c["independent_sources"] < MIN_PUBLISHERS]
        print(f"[Stage 2: Verify] Code check: {len(checked) - len(need)}/{len(checked)} claims already have "
              f">= {MIN_PUBLISHERS} publishers; corroborating {len(need)} with {CORROBORATE_WORKERS} workers...")
        with ThreadPoolExecutor(max_workers=CORROBORATE_WORKERS) as pool:
            for i, result in zip(need, pool.map(lambda i: corroborate(checked[i], output_dir, client), need)):
                checked[i] = result
                print(f"  {result['id']}: {result['independent_sources']} publishers {result['corroboration']['log']}")
        checked_path.write_text(json.dumps(checked, indent=2, ensure_ascii=False), encoding="utf-8")

    # 3. M3.1 judge on claims that can still meet the keep rule
    verify_prompt = Path("prompts/verify.md").read_text(encoding="utf-8")
    eligible = [c for c in checked if c["independent_sources"] >= MIN_PUBLISHERS]
    batches = [eligible[i:i + JUDGE_BATCH] for i in range(0, len(eligible), JUDGE_BATCH)]
    print(f"[Stage 2: Verify] Judging {len(eligible)} claims in {len(batches)} batches (effort=xhigh)...")
    verdict_map: Dict[str, Dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=JUDGE_WORKERS) as pool:
        for vm in pool.map(lambda b: judge_batch(b, client, verify_prompt), batches):
            verdict_map.update(vm)

    # 4. Keep rule
    kept, drop_reasons = [], Counter()
    for c in checked:
        if c["independent_sources"] < MIN_PUBLISHERS:
            drop_reasons["fewer than 2 independent publishers"] += 1
            continue
        v = verdict_map.get(c["id"])
        if not v:
            drop_reasons["judge returned no verdict"] += 1
            continue
        if not v.get("supported"):
            drop_reasons["judge: quotes do not support claim"] += 1
            continue
        c = {k: val for k, val in c.items() if k not in ("source_failures", "corroboration")}
        c["verdict"] = {"supported": True, "reason": v.get("reason", ""), "corrected_claim": v.get("corrected_claim")}
        if v.get("corrected_claim"):
            c["claim"] = v["corrected_claim"]
        kept.append(c)

    claims_path.write_text(json.dumps(kept, indent=2, ensure_ascii=False), encoding="utf-8")

    publishers = sorted({s["domain"] for c in kept for s in c["sources"]})
    report_data = {
        "city": city,
        "total_raw": len(raw_claims),
        "kept": len(kept),
        "dropped": len(raw_claims) - len(kept),
        "independent_publishers": len(publishers),
        "single_source_claims": sum(1 for c in kept if c["independent_sources"] < MIN_PUBLISHERS),
        "providers_used": publishers,
        "corroborated": sum(1 for c in checked if c.get("corroboration", {}).get("log", []) and
                            any(l.startswith("added") for l in c["corroboration"]["log"])),
        "drop_reasons": dict(drop_reasons),
        "keep_rule": f">= {MIN_PUBLISHERS} independent publishers (registrable domains; Wikipedia family = 1) and judge-supported",
    }
    report_path.write_text(json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[Stage 2: Verify] Kept {len(kept)} claims (dropped {report_data['dropped']}: {dict(drop_reasons)}). "
          f"Publishers: {len(publishers)}. Saved to {claims_path} & {report_path}")
    if len(kept) < 25:
        print(f"[Warning] Kept claims count ({len(kept)}) is below target 25.")

    return claims_path, report_path
