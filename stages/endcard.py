"""
stages/endcard.py
Stage 9: End Card (M3.1, effort 'low')
Generates the audited documentary end-card HTML displaying fact base statistics and credits,
then records it to video/endcard.mp4.
"""

import json
from pathlib import Path
from typing import Any, Dict

from sandbase_client import SandBaseClient, strip_markdown_fences
from stages.record import record_single_scene


def run_endcard_stage(
    city: str,
    output_dir: Path,
    client: SandBaseClient,
    repo_url: str = "https://github.com/sandbase-lab/awesome-minimax-m3-1-flash",
    force: bool = False,
) -> Path:
    """Execute Stage 9: End Card."""
    scenes_dir = output_dir / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    html_file = scenes_dir / "endcard.html"
    mp4_file = output_dir / "video" / "endcard.mp4"

    if html_file.is_file() and mp4_file.is_file() and not force:
        print(f"[Stage 9: End Card] Reusing existing {mp4_file}")
        return mp4_file

    report_path = output_dir / "research-report.json"
    if not report_path.is_file():
        raise FileNotFoundError(f"Missing {report_path}. Stage 2 must be run first.")

    with open(report_path, "r", encoding="utf-8") as f:
        report_data = json.load(f)

    with open("prompts/endcard.md", "r", encoding="utf-8") as pf:
        template = pf.read()

    prompt = template.format(
        city=city,
        kept=report_data.get("kept", 25),
        independent_publishers=report_data.get("independent_publishers", 10),
        repo_url=repo_url,
    )

    messages = [{"role": "user", "content": prompt}]

    print(f"[Stage 9: End Card] Generating End Card HTML with MiniMax M3.1 Flash (effort=low, max_tokens=128000)...")
    resp_msg = client.chat(
        stage="endcard",
        scene_id="endcard",
        messages=messages,
        effort="low",
        max_tokens=128000,
        output_file_path=str(html_file),
    )

    clean_html = strip_markdown_fences(resp_msg.get("content") or "")
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(clean_html)

    # Record 10s video
    record_single_scene(html_file, mp4_file, target_seconds=10.0, force=force)
    return mp4_file
