"""
Opt-in sound for the chronicle-ink film (owner selected both): MiniMax Speech narration and a MiniMax Music
instrumental, both through the SandBase CLI only (references/voice.md, references/music-track.md).

    python -m stages.chronicle_audio --project output/pune-chronicle --voice
    python -m stages.chronicle_audio --project output/pune-chronicle --music

Narration says exactly each shot's caption. The music prompt is written by M3.1 from the film's arc.
Every SandBase run is appended to runs.jsonl (stage, tool, cost basis, output path); no key is logged.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

from sandbase_client import RUNS_LOG_PATH, SandBaseClient, strip_markdown_fences

ROOT = Path(__file__).resolve().parent.parent
VOICE_TOOL, VOICE_MODEL = "sandbase_minimax_speech_2_8_hd", "minimax/speech/2.8/hd"
VOICE_ID, VOICE_SPEED = "English_CaptivatingStoryteller", 1.05
MUSIC_TOOL, MUSIC_MODEL = "sandbase_minimax_music_2_6", "minimax/music/2.6"

load_dotenv(ROOT / ".env")


def sandbase_run(tool: str, payload: Dict[str, Any], out_json: Path, stage: str) -> Dict[str, Any]:
    """Runs one SandBase tool through the official CLI and logs it; the key comes from the environment only."""
    out_json.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    proc = subprocess.run(["npx", "-y", "@sandbaseai/cli@latest", "run", tool, "-i", json.dumps(payload, ensure_ascii=False),
                           "-w", "--timeout", "600", "-o", str(out_json), "-j"],
                          cwd=ROOT, capture_output=True, text=True, timeout=900, env=os.environ.copy())
    ok = proc.returncode == 0 and out_json.exists()
    with RUNS_LOG_PATH.open("a") as f:
        f.write(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "stage": stage, "tool": tool,
                            "status": "ok" if ok else f"exit {proc.returncode}", "latency": round(time.time() - t0, 1),
                            "input_chars": len(payload.get("text") or payload.get("prompt") or ""),
                            "output_file_path": str(out_json.relative_to(ROOT))}) + "\n")
    if not ok:
        raise RuntimeError(f"{tool} failed: {(proc.stderr or proc.stdout)[-800:]}")
    return json.loads(out_json.read_text())


def find_audio_url(obj: Any) -> Optional[str]:
    if isinstance(obj, str):
        return obj if obj.startswith("http") and any(x in obj.split("?")[0].lower() for x in (".mp3", ".wav", ".flac", "audio")) else None
    if isinstance(obj, dict):
        obj = list(obj.values())
    if isinstance(obj, list):
        for v in obj:
            u = find_audio_url(v)
            if u:
                return u
    return None


def download(url: str, dest: Path) -> None:
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    dest.write_bytes(r.content)


def caption_text(shot: Dict[str, Any]) -> str:
    return " ".join(shot["caption"]["en"]["text"].split())


def make_voice(project: Path) -> None:
    script = json.loads((project / "script.json").read_text())
    vdir = project / "voice"
    vdir.mkdir(exist_ok=True)
    timeline = project / "work/timeline.json"
    room = {s["id"]: s["end"] - s["start"] - 0.25 - 0.15 for s in json.loads(timeline.read_text())["shots"]} if timeline.exists() else {}
    lines = []
    for sh in script["shots"]:
        text = caption_text(sh)
        mp3 = vdir / f"{sh['id']}.mp3"
        meta = vdir / f"{sh['id']}.run.json"
        old = json.loads(meta.read_text()) if meta.exists() else {}
        speed = old.get("speed", VOICE_SPEED) if old.get("text") == text else VOICE_SPEED
        # voice.md: shorten the caption or raise the speed; raise it only as far as the clip needs, at most 1.2
        if mp3.exists() and old.get("text") == text and sh["id"] in room:
            d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp3)],
                                     capture_output=True, text=True).stdout or 0)
            if d > room[sh["id"]] and speed < 1.2:
                speed = round(min(1.2, speed * d / room[sh["id"]] + 0.01), 2)
                old = {}
        if not (mp3.exists() and old.get("text") == text):
            res = sandbase_run(VOICE_TOOL, {"text": text, "voice_id": VOICE_ID, "speed": speed, "english_normalization": True,
                                            "format": "mp3", "sample_rate": 44100, "channel": 1},
                               vdir / f"{sh['id']}.result.json", stage="chronicle_voice")
            url = find_audio_url(res)
            if not url:
                raise RuntimeError(f"no audio URL in {VOICE_TOOL} result for {sh['id']}")
            download(url, mp3)
            meta.write_text(json.dumps({"text": text, "url": url, "speed": speed}))
            print(f"[voice] {sh['id']} (speed {speed}): {text}")
        lines.append({"shot": sh["id"], "file": f"voice/{sh['id']}.mp3", "text": text, "offset": 0.25})
    faster = {l["shot"]: json.loads((vdir / f"{l['shot']}.run.json").read_text()).get("speed", VOICE_SPEED) for l in lines}
    faster = {k: v for k, v in faster.items() if v != VOICE_SPEED}
    (vdir / "voice.json").write_text(json.dumps({
        "generated": {"model": VOICE_MODEL, "via": "SandBase", "voice_id": VOICE_ID, "speed": VOICE_SPEED,
                      **({"speed_per_line": faster} if faster else {})},
        "credit": {"en": "Narration: MiniMax Speech 2.8 HD (via SandBase)", "zh-CN": "旁白：MiniMax Speech 2.8 HD 合成（经 SandBase）"},
        "lines": lines}, ensure_ascii=False, indent=1))


MUSIC_SYSTEM = """You write the prompt for an instrumental documentary score generated by MiniMax Music for a
150-second film. Output ONLY JSON: {"prompt": <<= 600 characters: style, instrumentation, tempo feel and the arc
of the film in order (quiet opening, growth, peak, a sparse dip, a second rise, soft ending); instrumental only,
no vocals, calm and loosely pulsed so narration sits on top>, "title": <short track title>}.
Never name a real artist, film or existing song."""


def make_music(project: Path) -> None:
    script = json.loads((project / "script.json").read_text())
    beats = [f"{s['section']}: {s['description']}" for s in script["shots"]]
    client = SandBaseClient()
    mdir = project / "music"
    mdir.mkdir(exist_ok=True)
    msg = client.chat(stage="chronicle_music_prompt", effort="low", max_tokens=8000,
                      messages=[{"role": "system", "content": MUSIC_SYSTEM},
                                {"role": "user", "content": "Film: Pune, a city's life story along its rivers.\nShots:\n" + "\n".join(beats)}],
                      output_file_path="music/track.json")
    spec = json.loads(strip_markdown_fences(msg.get("content") or ""))
    res = sandbase_run(MUSIC_TOOL, {"prompt": spec["prompt"], "is_instrumental": True, "format": "mp3", "sample_rate": 44100},
                       mdir / "music.result.json", stage="chronicle_music")
    url = find_audio_url(res)
    if not url:
        raise RuntimeError(f"no audio URL in {MUSIC_TOOL} result")
    download(url, mdir / "score.mp3")
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(mdir / "score.mp3")], capture_output=True, text=True, check=True).stdout.strip())
    need = float(script["seconds"]) + 1
    print(f"[music] track length {dur:.1f} s (film {script['seconds']} s)")
    if dur < need:
        raise RuntimeError(f"generated track is {dur:.1f} s, shorter than the film ({need:.0f} s); the Skill would pad silence")
    run_id = res.get("run_id") or res.get("id") if isinstance(res, dict) else None
    (mdir / "track.json").write_text(json.dumps({
        "file": "music/score.mp3", "start": 0, "fade_in": 1.5, "fade_out": 4, "title": spec.get("title") or "Pune score",
        "by": "MiniMax Music 2.6", "licence": "generated", "source": None,
        "generated": {"model": MUSIC_MODEL, "via": "SandBase", "run_id": run_id, "prompt": spec["prompt"]},
        "credit": {"en": "Music: instrumental generated with MiniMax Music 2.6 (via SandBase)",
                   "zh-CN": "音乐：MiniMax Music 2.6 生成的器乐（经 SandBase）"}}, ensure_ascii=False, indent=1))
    print(f"[music] {spec.get('title')}: {spec['prompt']}")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--voice", action="store_true")
    ap.add_argument("--music", action="store_true")
    args = ap.parse_args(argv)
    project = (ROOT / args.project).resolve()
    if args.music:
        make_music(project)
    if args.voice:
        make_voice(project)
    return 0


if __name__ == "__main__":
    sys.exit(main())
