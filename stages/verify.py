"""
stages/verify.py
Stage 2: Verify (code check + M3.1 judge, effort 'xhigh')
Verifies verbatim quotes against cached source texts, counts independent publishers,
runs MiniMax M3.1 Flash as judge, and writes claims.json and research-report.json.
"""

import json
import re
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional, Set, Tuple

from sandbase_client import SandBaseClient, strip_markdown_fences
from tools.fetch import get_cache_path


def normalize_text(text: str) -> str:
    """Normalize whitespace and lower case for substring checking."""
    return re.sub(r"\s+", " ", text).strip().lower()


def extract_registrable_domain(url: str) -> str:
    """Extract registrable domain from URL, mapping Wikipedia mirrors to one."""
    try:
        netloc = urlparse(url).netloc.lower()
        if "wikipedia.org" in netloc or "wikimedia.org" in netloc:
            return "wikipedia.org"
        parts = netloc.split(".")
        if len(parts) >= 2:
            return ".".join(parts[-2:])
        return netloc
    except Exception:
        return "unknown"


def is_official_or_academic(domain: str) -> bool:
    """Check if domain is official or academic."""
    return any(domain.endswith(sfx) for sfx in [".gov.in", ".ac.in", ".edu", ".org", "censusindia.gov.in", "pmc.gov.in", "pmrda.gov.in"])


def run_verify_stage(
    city: str,
    output_dir: Path,
    client: SandBaseClient,
    force: bool = False,
) -> Tuple[Path, Path]:
    """Execute Stage 2: Verify."""
    claims_path = output_dir / "claims.json"
    report_path = output_dir / "research-report.json"

    if claims_path.is_file() and report_path.is_file() and not force:
        print(f"[Stage 2: Verify] Reusing existing {claims_path} and {report_path}")
        return claims_path, report_path

    raw_claims_file = output_dir / "claims.raw.json"
    if not raw_claims_file.is_file():
        raise FileNotFoundError(f"Missing {raw_claims_file}. Stage 1 must be run first.")

    with open(raw_claims_file, "r", encoding="utf-8") as f:
        raw_claims = json.load(f)

    # 1. Deterministic Code Check: confirm quotes appear in cached sources
    checked_claims = []
    all_publishers: Set[str] = set()

    for item in raw_claims:
        surviving_sources = []
        for s in item.get("sources", []):
            url = s.get("url", "")
            quote = s.get("quote", "").strip()
            if not quote or not url:
                continue

            cache_file = get_cache_path(url, output_dir)
            if not cache_file.is_file():
                continue

            with open(cache_file, "r", encoding="utf-8") as cf:
                cached_text = cf.read()

            if normalize_text(quote) in normalize_text(cached_text):
                domain = extract_registrable_domain(url)
                all_publishers.add(domain)
                surviving_sources.append({
                    "url": url,
                    "domain": domain,
                    "quote": quote,
                    "cache": str(cache_file.relative_to(output_dir.parent)),
                })

        # Count independent domains
        unique_domains = {src["domain"] for src in surviving_sources}
        item_copy = dict(item)
        item_copy["sources"] = surviving_sources
        item_copy["independent_sources"] = len(unique_domains)
        checked_claims.append(item_copy)

    # 2. M3.1 Judge (effort 'xhigh')
    with open("prompts/verify.md", "r", encoding="utf-8") as pf:
        verify_prompt = pf.read()

    verified_claims = []

    # Batch claims to M3.1 judge
    batch_size = 5
    for i in range(0, len(checked_claims), batch_size):
        batch = checked_claims[i : i + batch_size]
        print(f"[Stage 2: Verify] Evaluating claims {i+1} to {min(i+batch_size, len(checked_claims))} with M3.1 Judge (effort=xhigh)...")

        batch_input = [
            {
                "id": c["id"],
                "claim": c["claim"],
                "kind": c["kind"],
                "quotes": [s["quote"] for s in c["sources"]],
                "independent_sources": c["independent_sources"],
            }
            for c in batch
        ]

        messages = [
            {"role": "system", "content": verify_prompt},
            {
                "role": "user",
                "content": (
                    f"Evaluate these claims based strictly on the provided verbatim quotes.\n"
                    f"Return a JSON list of objects: [{{\"id\": \"...\", \"supported\": true|false, \"reason\": \"...\", \"corrected_claim\": \"...\"|null}}]\n\n"
                    f"{json.dumps(batch_input, indent=2)}"
                ),
            },
        ]

        judge_msg = client.chat(
            stage="verify",
            messages=messages,
            effort="xhigh",
            max_tokens=32000,
        )

        content = strip_markdown_fences(judge_msg.get("content") or "[]")
        try:
            verdicts = json.loads(content)
            verdict_map = {v["id"]: v for v in verdicts if isinstance(v, dict) and "id" in v}
        except Exception as e:
            print(f"[Stage 2: Verify Warning] Failed to parse judge output: {e}")
            verdict_map = {}

        for c in batch:
            cid = c["id"]
            v = verdict_map.get(cid, {"supported": False, "reason": "Judge response missing"})
            c["verdict"] = v
            if v.get("corrected_claim"):
                c["claim"] = v["corrected_claim"]
            verified_claims.append(c)

    # 3. Apply Keep Rule
    kept_claims = []
    dropped_count = 0

    for c in verified_claims:
        if not c.get("verdict", {}).get("supported", False):
            dropped_count += 1
            continue

        indep = c.get("independent_sources", 0)
        kind = c.get("kind", "")
        has_official = any(is_official_or_academic(src["domain"]) for src in c.get("sources", []))

        # Rules:
        # dates and numbers: >= 3 independent sources, OR >= 2 when one is official/academic
        # everything else: >= 2 independent sources
        if kind in ("date", "number"):
            keep = (indep >= 3) or (indep >= 2 and has_official)
        else:
            keep = (indep >= 2)

        if keep:
            kept_claims.append(c)
        else:
            dropped_count += 1

    # Write output/<city>/claims.json (kept only)
    with open(claims_path, "w", encoding="utf-8") as f:
        json.dump(kept_claims, f, indent=2, ensure_ascii=False)

    # Write output/<city>/research-report.json
    report_data = {
        "city": city,
        "total_raw": len(raw_claims),
        "kept": len(kept_claims),
        "dropped": dropped_count,
        "independent_publishers": len(all_publishers),
        "single_source_claims": 0,
        "providers_used": sorted(list(all_publishers)),
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    print(f"[Stage 2: Verify] Kept {len(kept_claims)} claims (dropped {dropped_count}). Saved to {claims_path} & {report_path}")

    # Acceptance check
    if len(kept_claims) < 25:
        print(f"[Warning] Kept claims count ({len(kept_claims)}) is below target 25.")

    return claims_path, report_path
