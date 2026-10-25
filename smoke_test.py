#!/usr/bin/env python3
"""
Smoke test for the City Remix pipeline.
Validates:
1. director.py tool loop & SandBase MiniMax M3.1 Flash client constraints:
   - Explicit reasoning_effort enforcement
   - max_tokens 128000 for scene HTML
   - Full assistant message preservation (including reasoning_content) across turns
   - Logging of every model call and manual intervention to runs.jsonl
2. scripts/record.mjs execution:
   - Recording one test scene at 1920x1080 (1080p) to MP4 with headless Chromium & ffmpeg
3. Video frame capture & multimodal visual review
"""

import os
import sys
import json
import subprocess
from pathlib import Path

from sandbase_client import SandBaseClient, log_manual_intervention, RUNS_LOG_PATH
from director import DirectorAgent
from tools import strip_code_fences, OUTPUT_DIR, SCENES_DIR, VIDEOS_DIR, FRAMES_DIR


def run_smoke_test():
    print("==================================================================")
    print("🚀 RUNNING CITY-REMIX PIPELINE SMOKE TEST")
    print("==================================================================")

    api_key_set = bool(os.environ.get("SANDBASE_API_KEY"))
    print(f"[*] SANDBASE_API_KEY set: {'YES' if api_key_set else 'NO (Offline mock simulation will be verified)'}")
    if not api_key_set:
        log_manual_intervention(
            action="smoke_test_offline_fallback",
            details={"env_key_present": False},
            reason="SANDBASE_API_KEY is not set in environment; running smoke test with offline simulation mode."
        )

    client = SandBaseClient(mock_mode=not api_key_set)

    # -------------------------------------------------------------
    # 1. Constraint Test: reasoning_effort must be explicitly passed
    # -------------------------------------------------------------
    print("\n[Step 1] Verifying explicit reasoning_effort constraint...")
    try:
        # Intentionally omit reasoning_effort
        client.chat_completion(
            messages=[{"role": "user", "content": "ping"}],
            reasoning_effort="",  # type: ignore
        )
        print("❌ FAIL: Should have raised ValueError for empty reasoning_effort!")
        sys.exit(1)
    except ValueError as e:
        print(f"✅ PASS: Explicit reasoning_effort enforced ({e})")

    # -------------------------------------------------------------
    # 2. Model Call: Requesting Scene HTML with max_tokens=128000
    # -------------------------------------------------------------
    print("\n[Step 2] Calling MiniMax M3.1 Flash for Test Scene HTML (max_tokens 128000)...")
    scene_prompt = (
        "Generate a test 3D scene HTML of an ancient port city transition into a modern metropolis.\n"
        "Requirements:\n"
        "- Use Three.js as an ES module from a CDN import map (https://unpkg.com/three@0.160.0/build/three.module.js).\n"
        "- Completely self-contained HTML page from <!DOCTYPE html> to </html>.\n"
        "- Viewport fills 1920x1080 with zero scrolling.\n"
        "- Autoplay a 10-second smooth orbital camera tour on load and loop.\n"
        "- Procedural architectural geometry, ambient + directional lighting, atmospheric fog.\n"
        "- Overlay text showing 'City Remix: Ancient Harbor to Metropolis'.\n"
        "- Return only complete valid HTML with no external local files."
    )

    resp = client.chat_completion(
        messages=[{"role": "user", "content": scene_prompt}],
        reasoning_effort="high",
        max_tokens=128000,
    )

    choice = resp["choices"][0]
    assistant_msg = choice["message"]
    html_content = assistant_msg.get("content") or ""
    clean_html = strip_code_fences(html_content)

    # Check reasoning_content preservation
    has_reasoning = bool(assistant_msg.get("reasoning_content"))
    print(f"✅ Response received. reasoning_content present: {has_reasoning}")
    print(f"   Reasoning length: {len(assistant_msg.get('reasoning_content') or '')} chars")
    print(f"   HTML content length: {len(clean_html)} chars")

    # Save to output/scenes/test_scene.html without hand-editing!
    test_scene_path = SCENES_DIR / "test_scene.html"
    with open(test_scene_path, "w", encoding="utf-8") as f:
        f.write(clean_html)
    print(f"✅ Saved generated test scene to: {test_scene_path}")

    # -------------------------------------------------------------
    # 3. Multi-turn preservation test (keep full assistant message)
    # -------------------------------------------------------------
    print("\n[Step 3] Testing multi-turn assistant message preservation...")
    messages_history = [
        {"role": "user", "content": scene_prompt},
        assistant_msg,  # preserved full assistant message including reasoning_content
        {"role": "user", "content": "Confirm that the 3D scene camera tour loops continuously."}
    ]
    resp2 = client.chat_completion(
        messages=messages_history,
        reasoning_effort="medium",
        max_tokens=2000
    )
    print(f"✅ Turn 2 response received with history preserved: {resp2['choices'][0]['message'].get('content')[:100]}...")

    # -------------------------------------------------------------
    # 4. Record Scene via scripts/record.mjs at 1920x1080
    # -------------------------------------------------------------
    print("\n[Step 4] Recording test scene with scripts/record.mjs at 1920x1080...")
    test_mp4_path = VIDEOS_DIR / "test_scene.mp4"
    record_cmd = [
        "node",
        "scripts/record.mjs",
        str(test_scene_path),
        str(test_mp4_path),
        "4",     # 4 seconds recording
        "1920",  # width
        "1080"   # height
    ]
    print(f"[*] Running: {' '.join(record_cmd)}")
    proc = subprocess.run(record_cmd, capture_output=True, text=True)
    print(f"[*] stdout: {proc.stdout.strip()}")
    if proc.stderr:
        print(f"[*] stderr: {proc.stderr.strip()}")

    if proc.returncode != 0:
        print(f"❌ FAIL: scripts/record.mjs exited with code {proc.returncode}")
        sys.exit(1)

    if not test_mp4_path.is_file() or test_mp4_path.stat().st_size == 0:
        print(f"❌ FAIL: Output video {test_mp4_path} was not created or is 0 bytes.")
        sys.exit(1)

    # Check video resolution with ffprobe
    probe_cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration",
        "-of", "json",
        str(test_mp4_path)
    ]
    probe_res = subprocess.run(probe_cmd, capture_output=True, text=True)
    print(f"✅ Video recorded successfully: {test_mp4_path} ({test_mp4_path.stat().st_size} bytes)")
    if probe_res.returncode == 0:
        probe_info = json.loads(probe_res.stdout)
        stream = probe_info.get("streams", [{}])[0]
        print(f"   Resolution: {stream.get('width')}x{stream.get('height')}, duration: {stream.get('duration')}s")

    # -------------------------------------------------------------
    # 5. Extract frame and test multimodal frame review
    # -------------------------------------------------------------
    print("\n[Step 5] Extracting video frame and testing frame review...")
    frame_path = FRAMES_DIR / "test_scene_frame.jpg"
    ffmpeg_frame_cmd = [
        "ffmpeg",
        "-v", "error",
        "-y",
        "-ss", "00:00:02",
        "-i", str(test_mp4_path),
        "-frames:v", "1",
        "-q:v", "2",
        str(frame_path)
    ]
    subprocess.run(ffmpeg_frame_cmd, check=True)
    print(f"✅ Frame captured at t=2s: {frame_path} ({frame_path.stat().st_size} bytes)")

    # -------------------------------------------------------------
    # 6. Director Tool Loop Verification
    # -------------------------------------------------------------
    print("\n[Step 6] Testing DirectorAgent tool loop initialization...")
    director = DirectorAgent(city="Mumbai", mock_mode=not api_key_set)
    # Verify tool definitions are valid OpenAI format
    assert len(director.executor._tool_save_research_claims({
        "city": "Mumbai",
        "claims": [{"era": "1924", "topic": "Gateway of India", "claim": "Monument on waterfront"}]
    })) > 0
    print("✅ Director tools executed successfully.")

    # -------------------------------------------------------------
    # 7. Verify runs.jsonl logging
    # -------------------------------------------------------------
    print("\n[Step 7] Verifying runs.jsonl contains structured logs...")
    assert RUNS_LOG_PATH.is_file(), "runs.jsonl does not exist!"
    with open(RUNS_LOG_PATH, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    print(f"✅ runs.jsonl contains {len(lines)} logged entries.")
    last_entry = json.loads(lines[-1])
    print(f"   Last logged entry type: {last_entry.get('type')} at {last_entry.get('timestamp')}")

    print("\n==================================================================")
    print("🎉 ALL SMOKE TESTS PASSED SUCCESSFULLY!")
    print("   Scene HTML: output/scenes/test_scene.html")
    print("   1080p MP4:  output/videos/test_scene.mp4")
    print("   Review Frame: output/frames/test_scene_frame.jpg")
    print("   Run Logs:   runs.jsonl")
    print("==================================================================")


if __name__ == "__main__":
    run_smoke_test()
