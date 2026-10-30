"""
Final package for the contest: checks, cover, entry.json.

    python -m stages.chronicle_final --project output/pune-chronicle

- checks: full decode, duration 120-180 s, 1920x1080, H.264 + AAC, <= 100 MiB, captions burned (Skill check.json)
- cover: a frame of the film chosen by M3.1, with the film title, 1920x1080 JPG <= 5 MiB
- entry.json: title and summary drafted by M3.1 from the finished script; director_notes and sources built
  from runs.jsonl and the claims bound in the script. City id and coordinates are the contest's, unchanged.
"""

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from sandbase_client import SandBaseClient, strip_markdown_fences

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "vendor" / "chronicle-ink-0.4.3" / "chronicle-ink"
CITY = {"city_id": "pune", "place_lat": 18.5211, "place_lng": 73.8553}
MY_CITY_LINE = "Putting down roots here, one brick at a time."
MAX_VIDEO, MAX_COVER = 100 * 1024 * 1024, 5 * 1024 * 1024


def probe(path: Path) -> Dict[str, Any]:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def check_film(film: Path) -> Dict[str, Any]:
    p = probe(film)
    v = next(s for s in p["streams"] if s["codec_type"] == "video")
    a = next((s for s in p["streams"] if s["codec_type"] == "audio"), None)
    dur = float(p["format"]["duration"])
    decode = subprocess.run(["ffmpeg", "-v", "error", "-i", str(film), "-f", "null", "-"], capture_output=True, text=True)
    res = {
        "duration_s": round(dur, 2), "duration_ok": 120 <= dur <= 180,
        "size": f"{v['width']}x{v['height']}", "size_ok": (v["width"], v["height"]) == (1920, 1080),
        "video_codec": v["codec_name"], "audio_codec": a and a["codec_name"],
        "codecs_ok": v["codec_name"] == "h264" and bool(a) and a["codec_name"] == "aac",
        "bytes": film.stat().st_size, "bytes_ok": 0 < film.stat().st_size <= MAX_VIDEO,
        "full_decode_ok": decode.returncode == 0 and not decode.stderr.strip(),
        "decode_errors": decode.stderr.strip()[-500:],
    }
    res["ok"] = all(res[k] for k in ("duration_ok", "size_ok", "codecs_ok", "bytes_ok", "full_decode_ok"))
    return res


def bound_claims(project: Path, script: Dict[str, Any]) -> List[Dict[str, Any]]:
    ids = set(script.get("title_claims", [])) | set(script.get("end_card", {}).get("claims", []))
    for sh in script["shots"]:
        ids |= set(sh.get("claims") or [])
    for kp in script.get("knowledge_points", []):
        ids |= set(kp.get("claims") or [])
    facts = json.loads((project / "work/facts/facts.json").read_text())
    return [c for c in facts["claims"] if c["id"] in ids]


def run_totals() -> Dict[str, Any]:
    calls, tok_in, tok_out, reasoning, by_stage, manual, tools = 0, 0, 0, 0, Counter(), [], Counter()
    for line in (ROOT / "runs.jsonl").read_text().splitlines():
        d = json.loads(line)
        st = str(d.get("stage", ""))
        if d.get("type") == "manual_edit":
            manual.append(d.get("reason"))
            continue
        if d.get("tool"):
            tools[d["tool"]] += 1
            continue
        u = d.get("usage") or {}
        if not u:
            continue
        calls += 1
        by_stage[st] += 1
        tok_in += u.get("prompt_tokens", 0)
        tok_out += u.get("completion_tokens", 0)
        reasoning += (u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0)
    film_stages = {k: v for k, v in by_stage.items() if k.startswith("chronicle_")}
    return {"m31_calls": calls, "prompt_tokens": tok_in, "completion_tokens": tok_out, "reasoning_tokens": reasoning,
            "film_stage_calls": film_stages, "earlier_stage_calls": {k: v for k, v in by_stage.items() if k not in film_stages},
            "tool_runs": dict(tools), "manual_edits": manual,
            "m31_cost_usd": round(tok_in * 0.15 / 1e6 + tok_out * 0.6 / 1e6, 2)}


TITLE_SYSTEM = """Write the contest entry text for a finished film. Output ONLY JSON:
{"title": <film title, at most 80 characters>, "summary": <story summary, at most 200 characters>,
 "cover_shot": <the id of the shot whose frame best represents the film>}
Stay strictly true to what is on screen (the shot list below); no facts beyond its captions."""


def make_entry(project: Path, client: SandBaseClient, film_check: Dict[str, Any]) -> Dict[str, Any]:
    script = json.loads((project / "script.json").read_text())
    shots = [f"{s['id']} ({s['section']}): {s['caption']['en']['text']} | {s.get('description', '')}" for s in script["shots"]]
    msg = client.chat(stage="chronicle_entry_text", effort="medium", max_tokens=8000,
                      messages=[{"role": "system", "content": TITLE_SYSTEM},
                                {"role": "user", "content": f"Film title on screen: {script['title']['en']}\nShots:\n" + "\n".join(shots)}],
                      output_file_path="final/entry.json")
    text = json.loads(strip_markdown_fences(msg.get("content") or ""))
    title, summary = text["title"][:80], text["summary"][:200]
    claims = bound_claims(project, script)
    sources = sorted({s["url"] for c in claims for s in c["sources"] if s.get("url")})
    t = run_totals()
    stages = ", ".join(f"{k.replace('chronicle_', '')} {v}" for k, v in sorted(t["film_stage_calls"].items()))
    notes = (
        f"Directed by MiniMax M3.1 flash (minimax/minimax-m3.1-flash) through the SandBase API, using the official chronicle-ink "
        f"v0.4.3 Skill (subject city, structure life, style model). M3.1 chose the Britannica pages from Britannica's own search "
        f"results, wrote every claim with a verbatim excerpt, matched Britannica facts to Wikipedia, picked the landmarks and era "
        f"areas, wrote the chronology, the 27-shot list and every caption, the music prompt, and this title and summary. "
        f"Film-stage M3.1 calls: {stages}. All logged M3.1 calls in this project: {t['m31_calls']} "
        f"({t['prompt_tokens']:,} prompt / {t['completion_tokens']:,} completion tokens, about ${t['m31_cost_usd']}). "
        f"Narration: MiniMax Speech 2.8 HD, one clip per caption; music: MiniMax Music 2.6 instrumental, both via SandBase "
        f"(tool runs: {', '.join(f'{k} {v}' for k, v in t['tool_runs'].items()) or 'none'}). Facts: the Skill's cross-check "
        f"(two agreeing publishers, one a reference institution); captions bound to claim ids. Geography: OpenStreetMap "
        f"buildings, streets and water and Wikidata landmarks via the Skill's geo.mjs; era extents are approximations. "
        f"Pictures drawn by code (WebGL), rendered with HyperFrames; no image or video model. Human involvement: the owner "
        f"chose the city, brief and closing line, approved narration and music, downloaded the Skill and chose how sources "
        f"were read; Britannica pages were read in a browser and saved verbatim (checked by hash) because the site blocks "
        f"scripts. Infrastructure code was written with Google Antigravity and Claude Code. Manual edits to film content: "
        f"{'; '.join(m for m in t['manual_edits'] if m) or 'none'}. Prompts: stages/chronicle_agent.py and stages/chronicle_audio.py."
    )
    entry = {"title": title, "summary": summary, "lang": "en",
             "fields": {**CITY, "used_m31_flash": t["m31_calls"] > 0, "director_notes": notes, "sources": sources,
                        "my_city_line": MY_CITY_LINE}}
    return {"entry": entry, "cover_shot": text.get("cover_shot"), "totals": t}


def make_cover(project: Path, film: Path, cover_shot: Optional[str], title: str, out: Path) -> None:
    timeline = json.loads((project / "work/timeline.json").read_text())
    shots = timeline.get("shots") or []
    pick = next((s for s in shots if s.get("id") == cover_shot), None) or (shots[len(shots) // 2] if shots else None)
    t = (pick["start"] + pick["end"]) / 2 if pick else 60.0
    frame = out.with_suffix(".frame.png")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(film), "-frames:v", "1", str(frame)], check=True)
    subprocess.run(["node", str(ROOT / "scripts/cover.mjs"), str(frame), title, str(out)], cwd=ROOT, check=True)
    frame.unlink()
    if out.stat().st_size > MAX_COVER:
        raise RuntimeError("cover over 5 MiB")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    args = ap.parse_args(argv)
    project = (ROOT / args.project).resolve()
    film = project / "out/film.mp4"
    final = ROOT / "final"
    final.mkdir(exist_ok=True)
    fc = check_film(film)
    print(json.dumps(fc, indent=1))
    if not fc["ok"]:
        print("[final] film fails the contest checks; nothing written")
        return 1
    res = make_entry(project, SandBaseClient(), fc)
    make_cover(project, film, res["cover_shot"], res["entry"]["title"], final / "cover.jpg")
    (final / "entry.json").write_text(json.dumps(res["entry"], ensure_ascii=False, indent=1))
    (final / "check.json").write_text(json.dumps({"film": fc, "totals": res["totals"]}, indent=1))
    (final / "fact_sources.txt").write_text("\n".join(res["entry"]["fields"]["sources"]) + "\n")
    print(f"[final] entry.json, cover.jpg ({(final / 'cover.jpg').stat().st_size // 1024} KB), check.json written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
