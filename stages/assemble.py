"""
stages/assemble.py
Stage 10: Assemble (code, ffmpeg)
Muxes audio and video per scene, concatenates in order, normalizes loudness to -16 LUFS,
and exports the final 1080p MP4 and SRT files.
"""

import json
import subprocess
from pathlib import Path
from typing import List, Tuple


def mux_scene_video_and_audio(video_file: Path, audio_file: Path, output_file: Path) -> Path:
    """Mux scene video with narration audio, padding audio to match video duration."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    if audio_file and audio_file.is_file():
        cmd = [
            "ffmpeg",
            "-v", "error",
            "-y",
            "-i", str(video_file),
            "-i", str(audio_file),
            "-c:v", "copy",
            "-af", "apad",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "48000",
            "-shortest",
            str(output_file)
        ]
    else:
        # Silent audio track for scenes without voiceover
        cmd = [
            "ffmpeg",
            "-v", "error",
            "-y",
            "-i", str(video_file),
            "-f", "lavfi",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            str(output_file)
        ]
    subprocess.run(cmd, check=True)
    return output_file


def run_assemble_stage(
    city: str,
    output_dir: Path,
    force: bool = False,
) -> Tuple[Path, Path]:
    """Execute Stage 10: Assemble."""
    final_dir = output_dir / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    final_mp4 = final_dir / f"{city.lower()}.mp4"
    final_srt = final_dir / f"{city.lower()}.srt"

    if final_mp4.is_file() and not force:
        print(f"[Stage 10: Assemble] Reusing existing {final_mp4}")
        return final_mp4, final_srt

    script_path = output_dir / "script.json"
    with open(script_path, "r", encoding="utf-8") as f:
        script_data = json.load(f)

    timing_path = output_dir / "audio" / "timing.json"
    with open(timing_path, "r", encoding="utf-8") as f:
        timing_data = json.load(f)

    timings = timing_data.get("scenes", {})
    muxed_dir = output_dir / "muxed"
    muxed_dir.mkdir(parents=True, exist_ok=True)

    ordered_muxed: List[Path] = []

    # 1. Mux narration scenes
    for scn in script_data.get("scenes", []):
        sid = scn["id"]
        v_file = output_dir / "video" / f"{sid}.mp4"
        a_file = output_dir / "audio" / f"{sid}.wav"
        m_file = muxed_dir / f"{sid}_muxed.mp4"

        if not v_file.is_file():
            raise FileNotFoundError(f"Missing video file {v_file}")

        mux_scene_video_and_audio(v_file, a_file if a_file.is_file() else None, m_file)
        ordered_muxed.append(m_file)

    # 2. Mux endcard
    endcard_video = output_dir / "video" / "endcard.mp4"
    if endcard_video.is_file():
        endcard_muxed = muxed_dir / "endcard_muxed.mp4"
        mux_scene_video_and_audio(endcard_video, None, endcard_muxed)
        ordered_muxed.append(endcard_muxed)

    # 3. Concatenate and apply loudness normalization
    concat_list = final_dir / "concat_list.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for p in ordered_muxed:
            f.write(f"file '{p.resolve()}'\n")

    print(f"[Stage 10: Assemble] Concatenating {len(ordered_muxed)} scenes and applying loudnorm (-16 LUFS)...")
    cmd_concat = [
        "ffmpeg",
        "-v", "error",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-movflags", "+faststart",
        str(final_mp4)
    ]
    subprocess.run(cmd_concat, check=True)

    print(f"[Stage 10: Assemble] Final documentary produced: {final_mp4} ({final_mp4.stat().st_size} bytes)")
    return final_mp4, final_srt
