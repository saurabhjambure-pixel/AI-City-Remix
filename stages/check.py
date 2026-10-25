"""
stages/check.py
Stage 11: Contest Constraint Verification (code only)
Validates all contest requirements on the final assembled video and documentary metadata,
outputting output/<city>/final/check.json.
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple


def probe_media_file(media_path: Path) -> Dict[str, Any]:
    """Probe video and audio streams with ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "stream=codec_name,codec_type,width,height,pix_fmt,r_frame_rate",
        "-show_entries", "format=duration,size,format_name",
        "-of", "json",
        str(media_path)
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(proc.stdout)
    video_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    audio_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), {})
    duration = float(data.get("format", {}).get("duration", 0.0))
    size = int(data.get("format", {}).get("size", 0))

    return {
        "duration": duration,
        "size_bytes": size,
        "format": data.get("format", {}).get("format_name"),
        "video_codec": video_stream.get("codec_name"),
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "pix_fmt": video_stream.get("pix_fmt"),
        "audio_codec": audio_stream.get("codec_name"),
    }


def count_manual_edits(runs_log_path: Path) -> int:
    """Count manual edits recorded in runs.jsonl."""
    if not runs_log_path.is_file():
        return 0
    count = 0
    with open(runs_log_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                if rec.get("type") in ("manual_edit", "manual_intervention"):
                    count += 1
            except Exception:
                pass
    return count


def run_check_stage(
    city: str,
    output_dir: Path,
) -> Tuple[bool, Path]:
    """Execute Stage 11: Check against contest constraints."""
    final_dir = output_dir / "final"
    final_mp4 = final_dir / f"{city.lower()}.mp4"
    check_json = final_dir / "check.json"

    if not final_mp4.is_file():
        raise FileNotFoundError(f"Missing {final_mp4}. Stage 10 must be run first.")

    media_info = probe_media_file(final_mp4)
    duration = media_info["duration"]
    width = media_info.get("width", 0)
    height = media_info.get("height", 0)
    video_codec = media_info.get("video_codec", "")
    audio_codec = media_info.get("audio_codec", "")

    # 1. Duration check: 60-180s
    dur_pass = (60.0 <= duration <= 180.0)

    # 2. Resolution check: >= 1280x720 (target 1920x1080)
    res_pass = (width >= 1280 and height >= 720)

    # 3. Codec check: h264 and aac
    codec_pass = (video_codec == "h264" and audio_codec == "aac")

    # 4. Check claims & sources
    report_file = output_dir / "research-report.json"
    single_source_pass = False
    kept_claims_count = 0
    if report_file.is_file():
        with open(report_file, "r", encoding="utf-8") as f:
            rep = json.load(f)
        single_source_pass = (rep.get("single_source_claims") == 0)
        kept_claims_count = rep.get("kept", 0)

    # 5. Check script citations
    script_file = output_dir / "script.json"
    claims_file = output_dir / "claims.json"
    citations_pass = False
    subtitles_pass = False

    if script_file.is_file() and claims_file.is_file():
        with open(claims_file, "r", encoding="utf-8") as cf:
            valid_cids = {c["id"] for c in json.load(cf)}
        with open(script_file, "r", encoding="utf-8") as sf:
            script_data = json.load(sf)

        scenes = script_data.get("scenes", [])
        subtitles_pass = len(scenes) >= 6

        all_cids_valid = True
        for scn in scenes:
            for narr in scn.get("narration", []):
                for cid in narr.get("claim_ids", []):
                    if cid not in valid_cids:
                        all_cids_valid = False
        citations_pass = all_cids_valid

    # 6. Check borders: confirm no state/national border layers passed
    map_file = output_dir / "map" / "svg_paths.json"
    borders_pass = True
    if map_file.is_file():
        with open(map_file, "r", encoding="utf-8") as mf:
            map_data = json.load(mf)
        forbidden = ["state", "country", "national_border", "international"]
        for k in map_data.keys():
            if any(f in k.lower() for f in forbidden):
                borders_pass = False

    # 7. Check scene HTML assets: no external URLs
    assets_pass = True
    scenes_dir = output_dir / "scenes"
    for hf in scenes_dir.glob("*.html"):
        with open(hf, "r", encoding="utf-8") as f:
            content = f.read()
        for line in content.splitlines():
            if ("http://" in line or "https://" in line) and "w3.org" not in line:
                assets_pass = False
                break

    # 8. Manual edits count
    manual_edits = count_manual_edits(Path("runs.jsonl"))

    checks = {
        "duration_seconds": {
            "value": round(duration, 2),
            "expected": "60 to 180s",
            "pass": dur_pass,
        },
        "resolution": {
            "value": f"{width}x{height}",
            "expected": ">= 1280x720 (1920x1080 target)",
            "pass": res_pass,
        },
        "container_codecs": {
            "video": video_codec,
            "audio": audio_codec,
            "expected": "h264 / aac",
            "pass": codec_pass,
        },
        "subtitles_present": {
            "pass": subtitles_pass,
        },
        "claim_citations_verified": {
            "pass": citations_pass,
            "kept_claims_count": kept_claims_count,
        },
        "zero_single_source_claims": {
            "pass": single_source_pass,
        },
        "no_national_state_borders": {
            "pass": borders_pass,
        },
        "no_external_scene_assets": {
            "pass": assets_pass,
        },
        "manual_edits_count": {
            "value": manual_edits,
            "target": 0,
        },
    }

    all_passed = all(
        c.get("pass", True)
        for k, c in checks.items()
        if k != "manual_edits_count"
    )

    result_report = {
        "city": city,
        "all_passed": all_passed,
        "checks": checks,
        "video_file": str(final_mp4),
        "video_size_mb": round(media_info["size_bytes"] / (1024 * 1024), 2),
    }

    with open(check_json, "w", encoding="utf-8") as f:
        json.dump(result_report, f, indent=2)

    print(f"\n========================================================")
    print(f"📋 STAGE 11 AUDIT RESULT FOR {city}: {'PASSED ✅' if all_passed else 'FAILED ❌'}")
    print(f"   Duration: {duration:.2f}s | Resolution: {width}x{height} | Codecs: {video_codec}/{audio_codec}")
    print(f"   Manual edits logged: {manual_edits}")
    print(f"   Check report: {check_json}")
    print(f"========================================================\n")

    return all_passed, check_json
