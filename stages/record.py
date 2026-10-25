"""
stages/record.py
Stage 7: Record (code only)
Records scene HTML files to 1920x1080 MP4 using scripts/record.mjs and validates with ffprobe.
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


def probe_video_stream(video_path: Path) -> Dict[str, Any]:
    """Probe video file stream properties using ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,duration",
        "-show_entries", "format=duration",
        "-of", "json",
        str(video_path)
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(proc.stdout)
    stream = data.get("streams", [{}])[0]
    fmt = data.get("format", {})
    dur = float(stream.get("duration") or fmt.get("duration") or 0.0)
    return {
        "codec": stream.get("codec_name"),
        "width": stream.get("width"),
        "height": stream.get("height"),
        "duration": dur,
    }


def record_single_scene(
    html_file: Path,
    output_mp4: Path,
    target_seconds: float,
    force: bool = False,
) -> Path:
    """Record an HTML file into 1920x1080 MP4 with retry on duration mismatch."""
    output_mp4.parent.mkdir(parents=True, exist_ok=True)

    if output_mp4.is_file() and not force:
        try:
            info = probe_video_stream(output_mp4)
            if info["width"] == 1920 and info["height"] == 1080 and abs(info["duration"] - target_seconds) <= 0.6:
                print(f"[Stage 7: Record] Reusing valid {output_mp4}")
                return output_mp4
        except Exception:
            pass

    record_cmd = [
        "node",
        "scripts/record.mjs",
        str(html_file),
        str(output_mp4),
        str(round(target_seconds, 1)),
        "1920",
        "1080",
    ]

    for attempt in range(2):
        print(f"[Stage 7: Record] Recording {html_file.name} -> {output_mp4.name} ({target_seconds}s, 1920x1080) attempt {attempt+1}...")
        proc = subprocess.run(record_cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"[Record Warning] scripts/record.mjs stderr: {proc.stderr}")
            if attempt == 1:
                raise RuntimeError(f"Recording failed for {html_file}: {proc.stderr}")
            continue

        if not output_mp4.is_file() or output_mp4.stat().st_size == 0:
            if attempt == 1:
                raise RuntimeError(f"Recorded video {output_mp4} missing or empty.")
            continue

        # Check resolution and duration
        info = probe_video_stream(output_mp4)
        if info["width"] != 1920 or info["height"] != 1080:
            if attempt == 1:
                raise RuntimeError(f"Resolution mismatch: expected 1920x1080, got {info['width']}x{info['height']}")
            continue

        diff = abs(info["duration"] - target_seconds)
        if diff > 0.6 and attempt == 0:
            print(f"[Record Notice] Duration diff {diff:.2f}s > 0.6s. Re-recording once...")
            continue

        print(f"[Stage 7: Record] Successfully verified {output_mp4} ({info['duration']:.2f}s, {info['width']}x{info['height']})")
        return output_mp4

    return output_mp4


def run_record_stage(
    city: str,
    output_dir: Path,
    force: bool = False,
) -> List[Path]:
    """Execute Stage 7: Record for all scenes."""
    scenes_dir = output_dir / "scenes"
    videos_dir = output_dir / "video"
    videos_dir.mkdir(parents=True, exist_ok=True)

    timing_file = output_dir / "audio" / "timing.json"
    with open(timing_file, "r", encoding="utf-8") as f:
        timing_data = json.load(f)
    timings = timing_data.get("scenes", {})

    recorded_files: List[Path] = []
    html_files = sorted(list(scenes_dir.glob("*.html")))

    for hf in html_files:
        sid = hf.stem
        target_sec = timings.get(sid, {}).get("exact_duration_seconds", 12.0)
        mp4_path = videos_dir / f"{sid}.mp4"
        rec = record_single_scene(hf, mp4_path, target_sec, force=force)
        recorded_files.append(rec)

    return recorded_files
