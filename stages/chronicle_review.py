"""
Segment review for the chronicle-ink film, following the Skill's director's loop without a vision model.

    python -m stages.chronicle_review --project output/pune-chronicle [--note "<render-bug finding>"]...

Code measures each timeline segment of out/film.mp4 (per-frame luma and frame-to-frame difference from ffmpeg
signalstats: dark or empty frames, flicker spikes, caption timing). M3.1 reads those numbers, the shot list and
any render-bug notes and writes the round for each segment (findings, fixes, open_blocking) into
work/review.json. At most 3 rounds per segment (the Skill's limit).
"""

import argparse
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from sandbase_client import SandBaseClient, strip_markdown_fences
from stages.chronicle_agent import parse_json_lines

ROOT = Path(__file__).resolve().parent.parent


def frame_stats(film: Path) -> List[Dict[str, float]]:
    """Per-frame mean luma (YAVG) and difference to the previous frame (YDIF), on a 480 px proxy."""
    proc = subprocess.run(["ffmpeg", "-v", "error", "-i", str(film), "-vf", "scale=480:-2,signalstats,metadata=print:file=-",
                           "-an", "-f", "null", "-"], capture_output=True, text=True, check=True)
    out, cur = [], {}
    for line in proc.stdout.splitlines():
        m = re.match(r"frame:\s*(\d+)\s+pts:\s*\S+\s+pts_time:([\d.]+)", line)
        if m:
            if cur:
                out.append(cur)
            cur = {"t": float(m.group(2))}
            continue
        m = re.match(r"lavfi\.signalstats\.(YAVG|YDIF)=([\d.]+)", line)
        if m:
            cur[m.group(1)] = float(m.group(2))
    if cur:
        out.append(cur)
    return out


EMPTY_EDGE = 5.0  # calibrated on the first render: city frames 7-17, empty views 2-4.5


def edge_density(film: Path) -> List[Dict[str, float]]:
    """Edge density per half second (edgedetect + mean): empty views with no buildings score low."""
    proc = subprocess.run(["ffmpeg", "-v", "error", "-i", str(film), "-vf",
                           "fps=2,scale=480:-2,edgedetect=low=0.08:high=0.2,signalstats,metadata=print:file=-",
                           "-an", "-f", "null", "-"], capture_output=True, text=True, check=True)
    out, t = [], None
    for line in proc.stdout.splitlines():
        m = re.search(r"pts_time:([\d.]+)", line)
        if m:
            t = float(m.group(1))
        m = re.search(r"signalstats\.YAVG=([\d.]+)", line)
        if m and t is not None:
            out.append({"t": t, "edge": float(m.group(1))})
    return out


def segment_metrics(project: Path, film: Path) -> List[Dict[str, Any]]:
    tl = json.loads((project / "work/timeline.json").read_text())
    stats = frame_stats(film)
    edges = edge_density(film)
    cuts = {round(s["start"], 2) for s in tl["shots"]}
    res = []
    for seg in tl["segments"]:
        a, b = seg["start"], seg["end"]
        fr = [f for f in stats if a <= f["t"] < b]
        y = [f.get("YAVG", 0) for f in fr]
        d = [f.get("YDIF", 0) for f in fr if not any(abs(f["t"] - c) < 0.05 for c in cuts)]
        med = statistics.median(d) if d else 0
        spikes = [round(f["t"], 2) for f in fr if f.get("YDIF", 0) > max(12, med * 6) and not any(abs(f["t"] - c) < 0.05 for c in cuts)]
        shots = [s for s in tl["shots"] if s["start"] < b and s["end"] > a]
        ed = [e for e in edges if a <= e["t"] < b and e["t"] >= 4.0]  # the globe opening is meant to be sparse
        empty = [round(e["t"], 1) for e in ed if e["edge"] < EMPTY_EDGE]
        res.append({"id": seg["id"], "from_s": round(a, 2), "to_s": round(b, 2), "frames": len(fr),
                    "mean_luma": round(statistics.mean(y), 1) if y else None,
                    "dark_frames_pct": round(100 * sum(1 for v in y if v < 22) / len(y), 1) if y else None,
                    "median_frame_diff": round(med, 2), "flicker_spikes_s": spikes[:12],
                    "empty_view_pct": round(100 * len(empty) / len(ed), 1) if ed else 0.0, "empty_view_at_s": empty[:20],
                    "shots": [s["id"] for s in shots],
                    "captions": [" ".join(c.get("lines") or []) for c in tl["captions"] if c["start"] < b and c["end"] > a][:12]})
    return res


REVIEW_SYSTEM = """You are the director reviewing render segments of a chronicle-ink city film, as the Skill's
director's loop requires. You cannot see the frames; you judge from measurements made by code on the rendered
film (per-second luma, the share of near-black frames, frame-to-frame difference spikes outside cuts) and from
render-bug notes a person wrote after looking at the contact sheet. Thresholds: empty views (edge density
below 5, i.e. no buildings or streets in frame) above 10% of a segment, or near-black frames above 15%, mean
the camera shows a void; flicker spikes outside cuts mean an effect pops; captions must exist for
every shot. Output JSON Lines, one line per segment, nothing else:
{"id": <segment id>, "findings": [<short findings>], "fixes": [<what was or must be changed>], "open_blocking": [<findings that must be fixed before the final render>]}
Be strict but factual: a finding needs a measurement or a note behind it."""


def review(project: Path, client: SandBaseClient, notes: List[str], prior: Optional[Dict[str, List[str]]] = None,
           film: Optional[Path] = None) -> Path:
    film = film or project / "out/film.mp4"
    metrics = segment_metrics(project, film)
    user = (f"Segment measurements:\n{json.dumps(metrics, ensure_ascii=False, indent=1)}\n\n"
            f"Render-bug notes from the contact sheet: {json.dumps(notes, ensure_ascii=False)}\n"
            f"Fixes already applied since the previous round: {json.dumps(prior or {}, ensure_ascii=False)}")
    msg = client.chat(stage="chronicle_review", effort="medium", max_tokens=16000,
                      messages=[{"role": "system", "content": REVIEW_SYSTEM}, {"role": "user", "content": user}],
                      output_file_path="work/review.json")
    answers, _ = parse_json_lines(msg.get("content") or "", require="id")
    path = project / "work/review.json"
    doc = json.loads(path.read_text()) if path.exists() else {"schema": "chronicle-review/1", "segments": []}
    by_id = {s["id"]: s for s in doc["segments"]}
    for a in answers:
        seg = by_id.setdefault(a["id"], {"id": a["id"], "rounds": []})
        if len(seg["rounds"]) >= 3:
            continue
        seg["rounds"].append({"sheet": "out/sheet.jpg", "measurements": next((m for m in metrics if m["id"] == a["id"]), None),
                              "findings": a.get("findings", []), "fixes": a.get("fixes", []), "open_blocking": a.get("open_blocking", [])})
    doc["segments"] = list(by_id.values())
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    for s in doc["segments"]:
        last = s["rounds"][-1]
        print(f"[review] {s['id']}: round {len(s['rounds'])}, findings {len(last['findings'])}, open {last['open_blocking']}")
    return path


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--note", action="append", default=[])
    ap.add_argument("--fixed", action="append", default=[], help="a fix applied since the last round")
    ap.add_argument("--film", help="film to measure (default out/film.mp4)")
    args = ap.parse_args(argv)
    project = (ROOT / args.project).resolve()
    review(project, SandBaseClient(), args.note, {"applied": args.fixed} if args.fixed else None,
           Path(args.film) if args.film else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
