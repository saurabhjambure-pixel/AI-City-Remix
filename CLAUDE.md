# CLAUDE.md — City Remix (handoff)

You are taking over this project from a planning chat and a previous coding agent (Google Antigravity). Read this file, then `docs/PLAN_chronicle_ink.md` (the current plan), then `PROGRESS.md`. `MASTER_PLAN.md` is the original pipeline spec; §4–§5 below are the Oct 25 audit and are history. Continue from the plan phase that PROGRESS.md says is next.

## 1. Goal and deadline

- Contest: SandBase "AI City Remix". Uploads close **Oct 31 23:59:59 UTC = Sun Nov 1, 05:29 IST** (rules re-read Oct 29). Judging Nov 1–2, results Nov 3. Each upload or edit is reviewed within a day.
- **Current brief (Oct 29, rev 2):** a 120–180 s (target ~150 s) Pune life-story film on the official chronicle-ink Skill (subject=city, structure=life, style=model), directed end to end by **MiniMax M3.1 flash via SandBase**. Narration (MiniMax Speech) and MiniMax Music are **explicitly selected by the owner**. Plan: `docs/PLAN_chronicle_ink.md`.
- Contest ids (preserve exactly): `city_id "pune"`, `place_lat 18.5211`, `place_lng 73.8553` (Wikidata Q1538). Entry id `a43da048-c1e7-429f-9306-005dabcd638b`. **One entry only:** never create another; later versions are edits to this entry.
- Judging weights: AI workflow 30% (less human intervention, new tools, open source scores extra) · Accuracy 25% · Story and craft 25% · Reach 20%.
- Owner: Saurabh. You never sign in to SandBase. The owner has delegated **this entry's upload and submission** to the official client `contest-submit.py` with a one-entry token (rules in §2.9). If the client asks for the contest declaration, show the owner its exact wording first.

## 2. Non-negotiable rules

1. **M3.1 decides; you build.** Research, claims, verification judgements, script, scene HTML, frame review and end card come from `minimax/minimax-m3.1-flash` via `https://api.sandbase.ai/v1/chat/completions`. You write and fix infrastructure code only. Never call `api.minimax.io`.
2. **Never hand-write or hand-edit generated content.** Bad output → change the prompt or code and rerun. Owner-approved exceptions are logged with `python log_edit.py "<reason>"`.
3. **No mocks or fallbacks in real runs.** No hand-typed coordinates, placeholder HTML or default content. If a dependency fails, stop and report. Test doubles are named `fake_*` and live in tests only.
4. **Credentials:** `SANDBASE_API_KEY` from `.env` or the environment only. Never search the home directory, shell history or other apps for keys. Never print or commit it.
5. Every model call is logged to `runs.jsonl` (stage, effort, max_tokens, status, latency, usage incl. reasoning tokens, output path).
6. Always set `reasoning_effort` explicitly (API default is `max`). Keep the full assistant message (incl. `reasoning_content`, `tool_calls`) across tool turns.
7. Stages are resumable; `--force <stage>` reruns one.
8. Commits: small, descriptive; never commit `.env`, source caches or large videos.
9. **Submission token:** passed only as `LAB_SUBMISSION_TOKEN` in the subprocess environment (from a mode-600 file outside the repo, or the client's hidden prompt). Never in arguments, URLs, logs, `runs.jsonl`, commits, `entry.json` or chat output; never sent to any other service. Report success only when Lab returns `pending` or `approved` (pending is not approval). On failure keep the files and report; on HTTP 401 or expiry ask the owner for resume instructions at `https://www.sandbase.ai/lab/event/aicityremix/mine?upload=a43da048-c1e7-429f-9306-005dabcd638b`. Never re-render or create a new entry because of it.
10. **Budget:** check `sandbase balance` before paid stages; ask the owner before exceeding it.
11. **Brief vs Skill conflicts** (e.g. Overpass blocked, sparse building heights): explain and ask; never switch Skills or invent data silently.

## 3. Model and tool facts (verified)

| Item | Value |
|---|---|
| Endpoint | `https://api.sandbase.ai/v1/chat/completions` (OpenAI-compatible) |
| Model | `minimax/minimax-m3.1-flash` (confirmed Oct 29 via `sandbase inspect sandbase_minimax_minimax_m3_1_flash`; accepts text, image and video input; 1M context) |
| Effort levels | `low` `medium` `high` `xhigh` `max`; thinking cannot be disabled |
| Per stage | research high · verify xhigh · script high · scenes medium · review medium · end card low |
| max_tokens | 128000 for scene HTML (reasoning counts against it); 32000 elsewhere; API max 512K |
| Timeouts | 900 s per call; scene pages can take minutes to an hour → run in parallel |
| Images | `{"type":"image_url","image_url":{"url":"data:image/jpeg;base64,..."}}`; video input unconfirmed, send frames |
| Price | $0.15 / $0.60 per 1M input/output tokens |
| SandBase CLI | `npx -y @sandbaseai/cli@latest discover|inspect|run|balance` (inspect is free) |
| Speech / music | `sandbase_minimax_speech_2_8_hd` (text, voice_id; ~$0.1/1k chars) · `sandbase_minimax_music_3` (prompt + lyrics; `[instrumental]` tags; duration ≤300 s; ~$0.12) |
| Skill | chronicle-ink from `https://www.sandbase.ai/lab/downloads/chronicle-ink.zip` (unversioned; record version and SHA-256 on download; may need owner sign-in) |
| Submit | `python3 tools/contest-submit.py --contest city-life --entry a43da048-c1e7-429f-9306-005dabcd638b --metadata final/entry.json --video final/film.mp4 --cover final/cover.jpg` (read the client fully before first run) |
| Recorder | `scripts/record.mjs` (from sandbase-lab/awesome-minimax-m3-1-flash): `node scripts/record.mjs in.html out.mp4 <sec> 1920 1080`; output has no audio |

Scene HTML rules (official prompt guide): one self-contained file, no external assets or CDNs (Three.js import map is the only exception), autoplay a timeline of exact length, fill the viewport, bold strokes and large type, "check zero console errors", "return only the complete HTML".

## 4. Current state (audited Oct 25 from the local preview portal at http://localhost:8080)

Built: `sandbase_client.py`, `tools.py`, `director.py`, `stages/` (incl. `mapdata.py`), `tools/osm.py`, `scripts/record.mjs`, `smoke_test.py`, preview portal, git repo. Real M3.1 calls are logged in `runs.jsonl` (HTTP 200, reasoning tokens present).

Defects to fix (in this order):

**A. Research/verify kept 1 of 60 claims** (`research-report.json`).
- All 60 raw claims have a single publisher (30 with one source; the rest quote the same site twice, often Wikipedia).
- Domain parsing bug: `coeptech.ac.in` becomes `ac.in`; all `.gov.in`/`.ac.in` sites merge into one publisher. Use `tldextract`.
- Quotes are cut mid-sentence. Require complete sentences; for date/number claims the quote must contain the claim's value (code check).
- Add a corroboration pass: for each claim with <2 independent publishers, M3.1 searches with a different engine (3 searches max per claim) and adds a source from a new publisher.
- Keep rule: **≥2 independent publishers for every claim** (supersedes the 3-source rule in MASTER_PLAN.md §3 stage 2; update that section).
- Target: ≥25 kept claims, `single_source_claims == 0`.

**B. Map data is invented.**
- Overpass failed silently (empty `output/pune/map/cache/`) and `tools/osm.py` fell back to hand-typed river lines and the hardcoded `PUNE_LANDMARK_SEEDS`. Delete both. Retry Overpass (timeout 90 s, both endpoints, 3 tries, backoff), else stop with an error.
- Separate layers for Mula, Mutha and Mula-Mutha (the regex currently files Mula-Mutha under Mutha).
- Add the Pune Municipal Corporation boundary (city level). Never national or state borders.
- Landmark coordinates only from OSM by name within the city bbox; store OSM ids; omit and log any not found.
- Emit three views with their own projections: `core` (~3 km around the Sangam), `city` (PMC + Pimpri-Chinchwad, Hinjewadi, cantonments), `region` (adds Sinhagad). Labels must not overlap in `preview.html`.

**C. Scenes ignore the map data and draw their own Pune.**
- `output/scenes/test_scene.html` invents streets and rivers, shows Kothrud twice, puts Pimpri south-east (it is north-west), puts Shaniwar Wada on the wrong bank of the Mutha, and shows unsourced side-panel facts ("Mula · North to south", "MH 12"). Labels collide. The visual style (ink, saffron, river blue, framed map, subtitle bar) is good; keep it.
- Prompt: geography only from the provided path strings; no streets, blocks or grids; on-screen text limited to subtitles, allowed labels and the scene title; no fact panels.
- Code check after generation: every provided path `d` string appears verbatim; extracted visible text contains no proper noun outside allowed labels + subtitles + title. On failure, regenerate with violations listed (max 2 tries).
- Review stage also gets the view's preview image as ground truth.
- Discard `test_scene.html`.

## 5. First actions

1. Run `git status` and `git log --oneline | head`, read `PROGRESS.md`, and confirm the tree matches §4. Commit any uncommitted work from the previous agent as "wip: antigravity state".
2. Confirm `.env` has the key with one `low`-effort smoke call (cost is negligible).
3. Fix A, rerun stages 1–2 for Pune, and report kept/dropped/publishers.
4. Fix B, rerun stage 3, and screenshot `preview.html` (all three views) for the owner.
5. Fix C, then run stages 4–11 to a first full film.
6. After each step, append a dated line to `PROGRESS.md` and commit.

## 6. Schedule (UTC; replaces the Oct 25–28 schedule)

| When | Gate |
|---|---|
| Oct 29 12:00 | Skill reviewed, model id and balance checked, geo.mjs and HyperFrames smoke tests pass (or blocker raised) |
| Oct 29 22:00 | Reference-tier facts done; spine chosen; film.json passes the gate |
| Oct 30 06:00 | Test segments approved; narration and music done |
| **Oct 30 12:00** | **v1 passes check → submitted via the official client (pending)** |
| **Oct 31 12:00** | **Last edit submitted** (one review cycle before close) |

The submission token expires within 24 h of issue (about Oct 30 morning); if it lapses, use the resume link rather than rushing quality.

If behind, cut in this order: teaser → music (code-generated instead) → 5th chapter → narration (captions only). Never cut verification, geo truth or the final checks. Entry 2 is dropped.

## 7. Contest constraints (enforce in stage 11)

60–180 s · MP4 · ≥720p (target 1920×1080) · English with subtitles in the video · original work · no copyrighted film or music · **no real living people** (no faces, none named; the personal close is voice only) · maps lawful: city level, **no national or state borders** · directed with M3.1 flash through SandBase.

## 8. Film outline (rev 2, Oct 29)

**Begin at the historic core** (the old city by the Sangam) and explain how Pune took its present shape. Contrast the whole city with local details: each chapter flies to one exact place, lingers on its detail, then pulls back to show its era lit on today's buildings. Origins, growth and the present are connected **through the rivers and landmarks on the real map**. Close by returning to the opening core view. M3.1 chooses the spine from verified claims; an optional central question is allowed as a craft choice. Turning points only from sourced claims; never invent disasters, wars or rebirth, and no fictional people or events as history. Vary viewpoint, scenes and shot order; do not copy the Skill's "rings of a city" examples. Shot grammar: `docs/PLAN_chronicle_ink.md` Phase 3, enforced by `stages/film_gate.py`. `my_city_line` (≤50 chars, owner-authored): "Putting down roots here, one brick at a time." — also the last caption.

**Fact standard (chronicle-ink):** each fact needs two agreeing publishers, one of them a reference institution (e.g. Britannica, UNESCO); at most two hedged single-source lines ("Records say…"); every number and name in a caption must be in its claims. This supersedes the ≥25-claim gate.

## 9. Entry metadata (`final/entry.json`)

`{"title" (≤80), "summary" (≤200), "lang":"en", "fields":{"city_id":"pune","place_lat":18.5211,"place_lng":73.8553,"used_m31_flash":true,"director_notes","sources":[...],"my_city_line"}}`

- Title and summary: M3.1 drafts them from the finished film; true to what is on screen.
- `used_m31_flash: true` only with runs.jsonl evidence.
- `director_notes`: actual prompts, M3.1 call counts and token totals from runs.jsonl, the Skill and tools, human involvement (infrastructure by Google Antigravity and Claude Code; owner chose the city and brief; any logged manual edits).
- `sources`: one per unique URL in the final verified claims. No credentials anywhere.
- Also generate `final/how_it_was_made.md` and `final/fact_sources.txt` from real numbers.
