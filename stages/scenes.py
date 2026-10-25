"""
stages/scenes.py
Stage 6: Scenes (M3.1, effort 'medium', concurrent execution)
Generates self-contained 1920x1080 HTML scene files (Inline SVG + CSS animation)
using the exact prompt template and code constraints from MASTER_PLAN.md §3.
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

from sandbase_client import SandBaseClient, strip_markdown_fences


SCENE_PROMPT_TEMPLATE = """Build scene {scene_id} of a documentary about {city} as ONE self-contained HTML file at 1920x1080.
Look: deep ink background (#0f1115), saffron (#f2a33a) for the city and growth, cream (#f3ead8) labels, river blue (#5fa8d3). Bold strokes (>= 4px), large type (labels >= 34px, subtitles 44px).
Duration: exactly {seconds} s. Autoplay on load, no interaction, no loop, hold the last frame.
Timeline: {beats}
Subtitles: bottom-center, max 2 lines, semi-opaque backing, at exactly these times: {cues}
Map: use ONLY these SVG paths and positions (already projected to 1920x1080):
{svg_paths_subset}
Label only these places: {labels}. Do not draw any country or state borders.
Rules:
- Inline SVG + CSS animation; JavaScript only for timing. No external assets, fonts, images or CDNs.
- Fill the viewport (1920x1080), no scrolling.
- Before finishing, check the page has zero console errors.
- Return only the complete HTML, from <!doctype html> to </html>, with no abbreviation.
"""


def generate_single_scene(
    scene_spec: Dict[str, Any],
    scene_timing: Dict[str, Any],
    city: str,
    svg_paths_data: Dict[str, Any],
    output_scenes_dir: Path,
    client: SandBaseClient,
    force: bool = False,
    prompt_additions: str = "",
) -> Path:
    """Generate HTML for a single scene using MiniMax M3.1 Flash."""
    scene_id = scene_spec["id"]
    html_file = output_scenes_dir / f"{scene_id}.html"

    if html_file.is_file() and not force and not prompt_additions:
        print(f"[Stage 6: Scenes] Reusing existing {html_file}")
        return html_file

    exact_seconds = scene_timing.get("exact_duration_seconds", 12.0)
    beats = json.dumps(scene_spec.get("beats", []), indent=2)
    cues = json.dumps(scene_timing.get("subtitle_cues", []), indent=2)

    # Filter SVG paths for this scene
    needed_layers = scene_spec.get("map_layers", [])
    needed_labels = scene_spec.get("labels", [])

    svg_subset = {}
    for lyr in needed_layers:
        if lyr in svg_paths_data:
            svg_subset[lyr] = svg_paths_data[lyr]

    # Include landmark points
    all_landmarks = svg_paths_data.get("landmarks", {})
    subset_landmarks = {}
    for k, v in all_landmarks.items():
        if any(lbl.lower() in v["name"].lower() for lbl in needed_labels):
            subset_landmarks[k] = v
    if subset_landmarks:
        svg_subset["landmarks"] = subset_landmarks

    prompt = SCENE_PROMPT_TEMPLATE.format(
        scene_id=scene_id,
        city=city,
        seconds=exact_seconds,
        beats=beats,
        cues=cues,
        svg_paths_subset=json.dumps(svg_subset, indent=2),
        labels=json.dumps(needed_labels),
    )

    if prompt_additions:
        prompt += f"\n\nCRITICAL FIX INSTRUCTIONS FROM REVIEW:\n{prompt_additions}"

    messages = [
        {"role": "user", "content": prompt}
    ]

    print(f"[Stage 6: Scenes] Generating Scene {scene_id} HTML with MiniMax M3.1 Flash (effort=medium, max_tokens=128000)...")
    resp_msg = client.chat(
        stage="scenes",
        scene_id=scene_id,
        messages=messages,
        effort="medium",
        max_tokens=128000,
        output_file_path=str(html_file),
    )

    raw_html = resp_msg.get("content") or ""
    clean_html = strip_markdown_fences(raw_html)

    # Deterministic Code Checks
    if "<html" not in clean_html.lower() or "</html>" not in clean_html.lower():
        raise ValueError(f"Generated scene {scene_id} HTML is missing <html> tags!")

    # Check for external URLs
    if "http://" in clean_html or "https://" in clean_html:
        # Check if they are just XML namespaces or external resource loads
        lines_with_http = [line.strip() for line in clean_html.splitlines() if ("http://" in line or "https://" in line) and "w3.org" not in line]
        if lines_with_http:
            raise ValueError(f"Scene {scene_id} contains forbidden external network resources: {lines_with_http[:3]}")

    if len(clean_html.encode("utf-8")) > 2 * 1024 * 1024:
        raise ValueError(f"Scene {scene_id} exceeds 2 MB file size limit!")

    with open(html_file, "w", encoding="utf-8") as f:
        f.write(clean_html)

    print(f"[Stage 6: Scenes] Successfully wrote {html_file} ({len(clean_html)} chars)")
    return html_file


def run_scenes_stage(
    city: str,
    output_dir: Path,
    client: SandBaseClient,
    workers: int = 4,
    force: bool = False,
) -> List[Path]:
    """Execute Stage 6: Scenes concurrently up to workers."""
    scenes_dir = output_dir / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)

    script_path = output_dir / "script.json"
    timing_path = output_dir / "audio" / "timing.json"
    svg_paths_path = output_dir / "map" / "svg_paths.json"

    with open(script_path, "r", encoding="utf-8") as f:
        script_data = json.load(f)
    with open(timing_path, "r", encoding="utf-8") as f:
        timing_data = json.load(f)
    with open(svg_paths_path, "r", encoding="utf-8") as f:
        svg_paths_data = json.load(f)

    scene_specs = script_data.get("scenes", [])
    timings = timing_data.get("scenes", {})

    print(f"[Stage 6: Scenes] Generating {len(scene_specs)} scenes concurrently (workers={workers})...")
    output_files: List[Path] = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {
            pool.submit(
                generate_single_scene,
                scn,
                timings.get(scn["id"], {}),
                city,
                svg_paths_data,
                scenes_dir,
                client,
                force,
            ): scn["id"]
            for scn in scene_specs
        }

        for fut in as_completed(future_map):
            sid = future_map[fut]
            try:
                res_path = fut.result()
                output_files.append(res_path)
            except Exception as e:
                print(f"[Stage 6: Scenes Error] Scene {sid} generation failed: {e}")
                raise

    return sorted(output_files)
