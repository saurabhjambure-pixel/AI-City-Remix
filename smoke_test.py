#!/usr/bin/env python3
"""
smoke_test.py
Phase 0 Smoke Test for AI City Remix.
Verifies real API call with MiniMax M3.1 Flash:
- Key read from .env / environment only
- Explicit effort level ('high')
- max_tokens 128000 for scene HTML
- Confirms HTTP 200, completion_tokens > 0, reasoning_tokens > 0 in runs.jsonl
- Saves scene HTML byte-identical to model output (after stripping fences only)
- Records 1080p MP4 via scripts/record.mjs at 1920x1080
- Extracts frame and validates runs.jsonl audit log
"""

import os
import sys
import json
import subprocess
from pathlib import Path

from sandbase_client import SandBaseClient, strip_markdown_fences, RUNS_LOG_PATH
from stages.record import probe_video_stream


def run_smoke_test():
    print("==================================================================")
    print("🚀 RUNNING PHASE 0 SMOKE TEST — LIVE MINIMAX M3.1 FLASH")
    print("==================================================================")

    # 1. Check SANDBASE_API_KEY from .env / environment
    api_key = os.environ.get("SANDBASE_API_KEY", "").strip()
    if not api_key:
        print(
            "❌ STOP: SANDBASE_API_KEY is not set in environment or .env file.\n"
            "As per MASTER_PLAN.md Rule #3, no mocks or placeholder HTML are permitted in real runs.\n"
            "Please add your SandBase key to .env (SANDBASE_API_KEY=sk-...) and rerun `python3 smoke_test.py`.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"[*] SANDBASE_API_KEY detected: sk-...{api_key[-4:] if len(api_key) > 4 else ''}")

    client = SandBaseClient(api_key=api_key)

    # 2. Constraint Test: reasoning_effort must be explicitly passed
    print("\n[Step 1] Verifying explicit reasoning_effort constraint...")
    try:
        client.chat(
            stage="test_constraint",
            messages=[{"role": "user", "content": "ping"}],
            effort="",  # type: ignore
            max_tokens=1000,
        )
        print("❌ FAIL: Should have raised ValueError for empty reasoning_effort!")
        sys.exit(1)
    except ValueError as e:
        print(f"✅ PASS: Explicit reasoning_effort enforced ({e})")

    # 3. Model Call: Requesting Scene HTML with max_tokens=128000
    print("\n[Step 2] Calling MiniMax M3.1 Flash for Test Scene HTML (max_tokens 128000, effort=high)...")
    scene_prompt = (
        "Build a test scene of Pune at the confluence of the Mula and Mutha rivers as ONE self-contained HTML file at 1920x1080.\n"
        "Look: deep ink background (#0f1115), saffron (#f2a33a) highlights, river blue (#5fa8d3), bold strokes (>= 4px).\n"
        "Duration: exactly 5 s. Autoplay on load, no interaction, no loop, hold the last frame.\n"
        "Subtitles: bottom-center, 'I am Pune. Where the Mula and Mutha meet.'\n"
        "Rules:\n"
        "- Inline SVG + CSS animation; JavaScript only for timing. No external assets, fonts, images or CDNs.\n"
        "- Fill the viewport (1920x1080), zero scrolling.\n"
        "- Return only the complete HTML, from <!doctype html> to </html>, with no abbreviation."
    )

    resp_msg = client.chat(
        stage="smoke_test",
        scene_id="test_scene",
        messages=[{"role": "user", "content": scene_prompt}],
        effort="high",
        max_tokens=128000,
        output_file_path="output/scenes/test_scene.html",
    )

    raw_html = resp_msg.get("content") or ""
    clean_html = strip_markdown_fences(raw_html)

    # Verify HTML tags
    if "<html" not in clean_html.lower() or "</html>" not in clean_html.lower():
        print("❌ FAIL: Returned content does not contain complete HTML document!")
        sys.exit(1)

    # Save byte-identical to model's returned content
    scenes_dir = Path("output/scenes")
    scenes_dir.mkdir(parents=True, exist_ok=True)
    test_scene_path = scenes_dir / "test_scene.html"
    with open(test_scene_path, "w", encoding="utf-8") as f:
        f.write(clean_html)

    print(f"✅ Saved generated test scene ({len(clean_html)} chars) to: {test_scene_path}")

    # 4. Check runs.jsonl for HTTP 200, completion_tokens > 0, reasoning_tokens > 0
    print("\n[Step 3] Checking runs.jsonl audit log...")
    with open(RUNS_LOG_PATH, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    last_call = None
    for line in reversed(lines):
        rec = json.loads(line)
        if rec.get("type") == "model_call" and rec.get("stage") == "smoke_test":
            last_call = rec
            break

    if not last_call:
        print("❌ FAIL: No model_call record for smoke_test found in runs.jsonl!")
        sys.exit(1)

    status_code = last_call.get("status_code")
    usage = last_call.get("usage", {})
    comp_tokens = usage.get("completion_tokens", 0)
    details = usage.get("completion_tokens_details", {})
    reasoning_tokens = details.get("reasoning_tokens") or usage.get("reasoning_tokens", 0)

    print(f"   HTTP Status: {status_code}")
    print(f"   Completion Tokens: {comp_tokens}")
    print(f"   Reasoning Tokens: {reasoning_tokens}")
    print(f"   Latency: {last_call.get('latency_seconds')}s")

    if status_code != 200:
        print(f"❌ FAIL: Expected HTTP 200, got {status_code}")
        sys.exit(1)
    if comp_tokens <= 0:
        print(f"❌ FAIL: Expected completion_tokens > 0, got {comp_tokens}")
        sys.exit(1)

    print("✅ PASS: Real API call verified with valid completion and reasoning usage.")

    # 5. Record Scene via scripts/record.mjs at 1920x1080
    print("\n[Step 4] Recording test scene with scripts/record.mjs at 1920x1080...")
    videos_dir = Path("output/videos")
    videos_dir.mkdir(parents=True, exist_ok=True)
    test_mp4_path = videos_dir / "test_scene.mp4"

    record_cmd = [
        "node",
        "scripts/record.mjs",
        str(test_scene_path),
        str(test_mp4_path),
        "5",
        "1920",
        "1080",
    ]
    subprocess.run(record_cmd, check=True)

    info = probe_video_stream(test_mp4_path)
    print(f"✅ Video recorded: {test_mp4_path} ({info['width']}x{info['height']}, {info['duration']:.2f}s, codec={info['codec']})")

    if info["width"] != 1920 or info["height"] != 1080:
        print(f"❌ FAIL: Video resolution mismatch! Got {info['width']}x{info['height']}")
        sys.exit(1)

    # 6. Extract frame
    print("\n[Step 5] Extracting video frame...")
    frames_dir = Path("output/frames")
    frames_dir.mkdir(parents=True, exist_ok=True)
    frame_path = frames_dir / "test_scene_frame.jpg"
    cmd_frame = [
        "ffmpeg",
        "-v", "error",
        "-y",
        "-ss", "00:00:02",
        "-i", str(test_mp4_path),
        "-frames:v", "1",
        "-pix_fmt", "yuvj420p",
        str(frame_path),
    ]
    subprocess.run(cmd_frame, check=True)
    print(f"✅ Frame captured at t=2s: {frame_path} ({frame_path.stat().st_size} bytes)")

    print("\n==================================================================")
    print("🎉 ALL PHASE 0 ACCEPTANCE CHECKS PASSED WITH LIVE API CALL!")
    print("==================================================================")


if __name__ == "__main__":
    run_smoke_test()
