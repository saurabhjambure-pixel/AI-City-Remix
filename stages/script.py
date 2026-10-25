"""
stages/script.py
Stage 4: Script (M3.1, effort 'high')
Generates the ~150-second documentary screenplay where the city speaks in the first person.
Enforces that every factual statement cites verified claim_ids.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from sandbase_client import SandBaseClient, strip_markdown_fences


def run_script_stage(
    city: str,
    output_dir: Path,
    client: SandBaseClient,
    force: bool = False,
) -> Path:
    """Execute Stage 4: Script."""
    script_path = output_dir / "script.json"
    if script_path.is_file() and not force:
        print(f"[Stage 4: Script] Reusing existing {script_path}")
        return script_path

    claims_path = output_dir / "claims.json"
    if not claims_path.is_file():
        raise FileNotFoundError(f"Missing {claims_path}. Stage 2 must be run first.")

    svg_paths_file = output_dir / "map" / "svg_paths.json"
    if not svg_paths_file.is_file():
        raise FileNotFoundError(f"Missing {svg_paths_file}. Stage 3 must be run first.")

    with open(claims_path, "r", encoding="utf-8") as f:
        claims_data = json.load(f)

    with open(svg_paths_file, "r", encoding="utf-8") as f:
        svg_paths_data = json.load(f)

    valid_claim_ids: Set[str] = {c["id"] for c in claims_data}
    map_layers_list = [k for k in svg_paths_data.keys() if k != "viewBox"]
    landmarks_list = list(svg_paths_data.get("landmarks", {}).keys())

    with open("prompts/script.md", "r", encoding="utf-8") as pf:
        system_prompt = pf.read().format(city=city)

    user_prompt = (
        f"Write the official AI City Remix documentary script for {city}.\n\n"
        f"Available Map Layers: {map_layers_list}\n"
        f"Available Landmark Points: {landmarks_list}\n\n"
        f"Verified Factual Claims Base ({len(claims_data)} claims):\n"
        f"{json.dumps([{'id': c['id'], 'cluster': c['cluster'], 'claim': c['claim']} for c in claims_data], indent=2)}\n\n"
        f"Remember: Return valid JSON matching the script schema. Every factual assertion must cite claim_ids."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    print(f"[Stage 4: Script] Calling MiniMax M3.1 Flash for Screenplay (effort=high)...")
    resp_msg = client.chat(
        stage="script",
        messages=messages,
        effort="high",
        max_tokens=32000,
        schema_path=Path("schemas/script.json"),
        output_file_path=str(script_path),
    )

    clean_content = strip_markdown_fences(resp_msg.get("content") or "")
    script_obj = json.loads(clean_content)

    # Deterministic Code Check: verify all cited claim_ids exist in claims.json
    invalid_citations = []
    total_sentences = 0
    cited_sentences = 0

    for scn in script_obj.get("scenes", []):
        for narr in scn.get("narration", []):
            total_sentences += 1
            cids = narr.get("claim_ids", [])
            if cids:
                cited_sentences += 1
                for cid in cids:
                    if cid not in valid_claim_ids:
                        invalid_citations.append((narr.get("text"), cid))

    if invalid_citations:
        raise ValueError(f"Script citations failed check! Invalid claim IDs cited: {invalid_citations}")

    print(f"[Stage 4: Script] Script validated ({len(script_obj.get('scenes', []))} scenes, {cited_sentences}/{total_sentences} factual sentences cited).")

    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(script_obj, f, indent=2, ensure_ascii=False)

    return script_path
