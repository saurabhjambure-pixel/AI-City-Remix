"""
stages/review.py
Stage 8: Review (M3.1 Vision, effort 'medium', max 2 rounds)
Extracts 3 frames per scene (at 20%, 55%, 90% of duration), sends them to M3.1 multimodal,
evaluates quality against review.json schema, and triggers regeneration for failing scenes.
"""

import base64
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sandbase_client import SandBaseClient, strip_markdown_fences
from stages.scenes import generate_single_scene
from stages.record import record_single_scene


def extract_frame_at_time(video_path: Path, timestamp_sec: float, output_jpg: Path) -> Path:
    """Extract a single frame from video at timestamp using ffmpeg."""
    output_jpg.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-v", "error",
        "-y",
        "-ss", str(round(timestamp_sec, 2)),
        "-i", str(video_path),
        "-frames:v", "1",
        "-q:v", "2",
        str(output_jpg),
    ]
    subprocess.run(cmd, check=True)
    return output_jpg


def review_single_scene(
    scene_spec: Dict[str, Any],
    scene_timing: Dict[str, Any],
    video_path: Path,
    review_dir: Path,
    city: str,
    svg_paths_data: Dict[str, Any],
    output_dir: Path,
    client: SandBaseClient,
    max_rounds: int = 2,
) -> Dict[str, Any]:
    """Perform vision review loop (up to max_rounds) on a scene."""
    scene_id = scene_spec["id"]
    review_json_file = review_dir / f"{scene_id}.json"

    with open("prompts/review.md", "r", encoding="utf-8") as pf:
        system_prompt = pf.read()

    current_video = video_path
    last_review: Dict[str, Any] = {}

    for round_idx in range(1, max_rounds + 1):
        print(f"[Stage 8: Review] Reviewing Scene {scene_id} Round {round_idx}/{max_rounds}...")
        dur = scene_timing.get("exact_duration_seconds", 12.0)
        t20 = dur * 0.20
        t55 = dur * 0.55
        t90 = dur * 0.90

        frames = []
        for t_name, t_val in [("20%", t20), ("55%", t55), ("90%", t90)]:
            f_path = review_dir / f"{scene_id}_r{round_idx}_{t_name.replace('%', 'pct')}.jpg"
            extract_frame_at_time(current_video, t_val, f_path)
            with open(f_path, "rb") as img_f:
                b64_str = base64.b64encode(img_f.read()).decode("utf-8")
            frames.append((t_name, b64_str))

        content_list: List[Dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    f"Review these 3 frames from Scene {scene_id} of the {city} documentary film.\n"
                    f"Duration: {dur}s. Subtitle cues: {json.dumps(scene_timing.get('subtitle_cues', []))}.\n"
                    f"Timeline Beats: {json.dumps(scene_spec.get('beats', []))}.\n"
                    f"Examine text readability, label positioning, contrast, and visual movement.\n"
                    f"Return JSON matching the schema: {{\"pass\": bool, \"round\": {round_idx}, \"issues\": [...], \"prompt_additions\": \"...\"}}"
                ),
            }
        ]

        for t_name, b64 in frames:
            content_list.append({"type": "text", "text": f"Frame at {t_name}:"})
            content_list.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content_list},
        ]

        resp_msg = client.chat(
            stage="review",
            scene_id=scene_id,
            messages=messages,
            effort="medium",
            max_tokens=4000,
            schema_path=Path("schemas/review.json"),
            output_file_path=str(review_json_file),
        )

        clean_resp = strip_markdown_fences(resp_msg.get("content") or "")
        review_obj = json.loads(clean_resp)
        last_review = review_obj

        with open(review_json_file, "w", encoding="utf-8") as f:
            json.dump(review_obj, f, indent=2)

        has_high_issue = any(iss.get("severity") == "high" for iss in review_obj.get("issues", []))

        if review_obj.get("pass", False) or not has_high_issue:
            print(f"[Stage 8: Review] Scene {scene_id} PASSED visual review on Round {round_idx}.")
            break

        print(f"[Stage 8: Review] Scene {scene_id} FAILED review with high-severity issues on Round {round_idx}.")
        if round_idx < max_rounds:
            additions = review_obj.get("prompt_additions", "")
            print(f"[Stage 8: Review] Regenerating Scene {scene_id} with prompt additions: '{additions[:100]}...'")
            # Regenerate scene HTML
            new_html = generate_single_scene(
                scene_spec=scene_spec,
                scene_timing=scene_timing,
                city=city,
                svg_paths_data=svg_paths_data,
                output_scenes_dir=output_dir / "scenes",
                client=client,
                force=True,
                prompt_additions=additions,
            )
            # Re-record
            current_video = record_single_scene(new_html, current_video, dur, force=True)

    return last_review


def run_review_stage(
    city: str,
    output_dir: Path,
    client: SandBaseClient,
    force: bool = False,
) -> List[Dict[str, Any]]:
    """Execute Stage 8: Review on all recorded scenes."""
    review_dir = output_dir / "review"
    review_dir.mkdir(parents=True, exist_ok=True)

    script_path = output_dir / "script.json"
    timing_path = output_dir / "audio" / "timing.json"
    svg_paths_path = output_dir / "map" / "svg_paths.json"

    with open(script_path, "r", encoding="utf-8") as f:
        script_data = json.load(f)
    with open(timing_path, "r", encoding="utf-8") as f:
        timing_data = json.load(f)
    with open(svg_paths_path, "r", encoding="utf-8") as f:
        svg_paths_data = json.load(f)

    timings = timing_data.get("scenes", {})
    results: List[Dict[str, Any]] = []

    for scn in script_data.get("scenes", []):
        sid = scn["id"]
        v_path = output_dir / "video" / f"{sid}.mp4"
        if not v_path.is_file():
            continue
        rev = review_single_scene(
            scene_spec=scn,
            scene_timing=timings.get(sid, {}),
            video_path=v_path,
            review_dir=review_dir,
            city=city,
            svg_paths_data=svg_paths_data,
            output_dir=output_dir,
            client=client,
        )
        results.append(rev)

    return results
