"""
stages/tts.py
Stage 5: TTS & Timing Cues
Generates narration audio per scene, calculates exact durations using ffprobe,
and constructs subtitle timing cues and SRT files.
"""

import os
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple


def get_audio_duration_seconds(audio_file: Path) -> float:
    """Measure exact audio duration in seconds using ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_file)
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(proc.stdout.strip())


def generate_speech_wav(text: str, output_wav: Path) -> None:
    """Generate spoken speech WAV using macOS say and ffmpeg."""
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    temp_aiff = output_wav.with_suffix(".aiff")

    # Use macOS say with a calm voice
    cmd_say = ["say", "-v", "Samantha", "-o", str(temp_aiff), text]
    subprocess.run(cmd_say, check=True)

    # Convert to 48kHz WAV
    cmd_ffmpeg = [
        "ffmpeg",
        "-v", "error",
        "-y",
        "-i", str(temp_aiff),
        "-ar", "48000",
        "-ac", "2",
        str(output_wav)
    ]
    subprocess.run(cmd_ffmpeg, check=True)
    if temp_aiff.is_file():
        temp_aiff.unlink()


def format_srt_timestamp(seconds: float) -> str:
    """Format seconds into SRT timestamp 00:00:00,000."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def run_tts_stage(
    city: str,
    output_dir: Path,
    force: bool = False,
) -> Tuple[Path, Path]:
    """Execute Stage 5: TTS and Timing."""
    audio_dir = output_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    timing_file = audio_dir / "timing.json"
    final_dir = output_dir / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    srt_file = final_dir / f"{city.lower()}.srt"

    if timing_file.is_file() and srt_file.is_file() and not force:
        print(f"[Stage 5: TTS] Reusing existing {timing_file} and {srt_file}")
        return timing_file, srt_file

    script_path = output_dir / "script.json"
    if not script_path.is_file():
        raise FileNotFoundError(f"Missing {script_path}. Stage 4 must be run first.")

    with open(script_path, "r", encoding="utf-8") as f:
        script_obj = json.load(f)

    scenes = script_obj.get("scenes", [])
    timing_data: Dict[str, Any] = {"scenes": {}}
    global_time = 0.0
    srt_entries: List[str] = []
    srt_index = 1

    for scn in scenes:
        scene_id = scn["id"]
        narration_items = scn.get("narration", [])
        full_narration = " ".join([n["text"].strip() for n in narration_items if n.get("text")])

        wav_file = audio_dir / f"{scene_id}.wav"

        if full_narration:
            print(f"[Stage 5: TTS] Synthesizing audio for {scene_id} ('{full_narration[:40]}...')...")
            generate_speech_wav(full_narration, wav_file)
            measured_dur = get_audio_duration_seconds(wav_file)
        else:
            measured_dur = float(scn.get("seconds_target", 10))

        # Scene duration = narration + 0.8 s tail (end card fixed 10s)
        tail = 0.8 if full_narration else 0.0
        scene_duration = round(measured_dur + tail, 2)

        # Build proportional subtitle cues
        cues = []
        if narration_items:
            total_chars = sum(len(n["text"]) for n in narration_items)
            current_local = 0.0
            for n in narration_items:
                t_str = n["text"].strip()
                if not t_str:
                    continue
                fraction = len(t_str) / max(total_chars, 1)
                cue_dur = fraction * measured_dur
                start_local = round(current_local, 2)
                end_local = round(current_local + cue_dur, 2)
                current_local = end_local

                cues.append({
                    "text": t_str,
                    "start": start_local,
                    "end": end_local,
                })

                # Global SRT timestamp
                global_start = global_time + start_local
                global_end = global_time + end_local
                srt_entries.append(
                    f"{srt_index}\n{format_srt_timestamp(global_start)} --> {format_srt_timestamp(global_end)}\n{t_str}\n"
                )
                srt_index += 1

        timing_data["scenes"][scene_id] = {
            "scene_id": scene_id,
            "audio_file": str(wav_file) if full_narration else None,
            "measured_audio_seconds": round(measured_dur, 2),
            "exact_duration_seconds": scene_duration,
            "subtitle_cues": cues,
        }

        global_time += scene_duration

    with open(timing_file, "w", encoding="utf-8") as f:
        json.dump(timing_data, f, indent=2)

    with open(srt_file, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_entries) + "\n")

    print(f"[Stage 5: TTS] Audio & timing generated. Total timeline: {round(global_time, 1)}s. Saved {timing_file} and {srt_file}")
    return timing_file, srt_file
