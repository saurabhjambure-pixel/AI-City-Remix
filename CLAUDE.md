# CLAUDE.md — City Remix (handoff)

You are taking over this project from a planning chat and a previous coding agent (Google Antigravity). Read this file, then `MASTER_PLAN.md` (the full spec), then `PROGRESS.md` if present. Then start at **§5 First actions**.

## 1. Goal and deadline

- Contest: SandBase "AI City Remix". Uploads close **Oct 31 23:59:59 UTC = Sun Nov 1, 05:29 IST** (rules re-read Oct 29). Judging Nov 1–2, results Nov 3. Each upload or edit is reviewed within a day.
- **Current brief (Oct 29):** rebuild the Pune film on the official chronicle-ink v0.4.3 Skill (subject=city, structure=life, style=model), with MiniMax Speech narration and MiniMax Music (owner approved both). Plan: `docs/PLAN_chronicle_ink.md`. Contest ids: `city_id "pune"`, lat 18.5211, lng 73.8553 (Wikidata Q1538).
- Entry 1: "I Am Pune", a ~150 s film in which Pune narrates itself in the first person, directed end to end by **MiniMax M3.1 flash via SandBase**.
- Entry 2 (Oct 28): 60–90 s demo of the same tool on a contrasting place.
- Judging weights: AI workflow 30% (less human intervention, new tools, open source scores extra) · Accuracy 25% · Story and craft 25% · Reach 20%.
- Owner: Saurabh. Owner signs in, uploads, adds the cover and ticks the declaration. You never sign in or upload.

## 2. Non-negotiable rules

1. **M3.1 decides; you build.** Research, claims, verification judgements, script, scene HTML, frame review and end card come from `minimax/minimax-m3.1-flash` via `https://api.sandbase.ai/v1/chat/completions`. You write and fix infrastructure code only. Never call `api.minimax.io`.
2. **Never hand-write or hand-edit generated content.** Bad output → change the prompt or code and rerun. Owner-approved exceptions are logged with `python log_edit.py "<reason>"`.
3. **No mocks or fallbacks in real runs.** No hand-typed coordinates, placeholder HTML or default content. If a dependency fails, stop and report. Test doubles are named `fake_*` and live in tests only.
4. **Credentials:** `SANDBASE_API_KEY` from `.env` or the environment only. Never search the home directory, shell history or other apps for keys. Never print or commit it.
5. Every model call is logged to `runs.jsonl` (stage, effort, max_tokens, status, latency, usage incl. reasoning tokens, output path).
6. Always set `reasoning_effort` explicitly (API default is `max`). Keep the full assistant message (incl. `reasoning_content`, `tool_calls`) across tool turns.
7. Stages are resumable; `--force <stage>` reruns one.
8. Commits: small, descriptive; never commit `.env`, source caches or large videos.

## 3. Model and tool facts (verified)

| Item | Value |
|---|---|
| Endpoint | `https://api.sandbase.ai/v1/chat/completions` (OpenAI-compatible) |
| Model | `minimax/minimax-m3.1-flash` |
| Effort levels | `low` `medium` `high` `xhigh` `max`; thinking cannot be disabled |
| Per stage | research high · verify xhigh · script high · scenes medium · review medium · end card low |
| max_tokens | 128000 for scene HTML (reasoning counts against it); 32000 elsewhere; API max 512K |
| Timeouts | 900 s per call; scene pages can take minutes to an hour → run in parallel |
| Images | `{"type":"image_url","image_url":{"url":"data:image/jpeg;base64,..."}}`; video input unconfirmed, send frames |
| Price | $0.15 / $0.60 per 1M input/output tokens |
| SandBase CLI | `npx -y @sandbaseai/cli@latest discover|inspect|run` (inspect is free) — use to find search and TTS endpoint names |
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
| Oct 29 06:00 | Skill reviewed, mapping sent, geo.mjs and HyperFrames smoke tests pass (or blocker reported) |
| Oct 29 18:00 | Reference-tier facts done; question chosen; film.json passes the gate |
| Oct 30 06:00 | Test segments approved; narration and music done |
| **Oct 30 12:00** | **v1 passes check → owner uploads** |
| **Oct 31 12:00** | **Final edit uploaded** (last safe point for review before close) |

If behind, cut in this order: teaser → music (code-generated instead) → 5th chapter → narration (captions only). Never cut verification, geo truth or the final checks. Entry 2 is dropped.

## 7. Contest constraints (enforce in stage 11)

60–180 s · MP4 · ≥720p (target 1920×1080) · English with subtitles in the video · original work · no copyrighted film or music · **no real living people** (no faces, none named; the personal close is voice only) · maps lawful: city level, **no national or state borders** · directed with M3.1 flash through SandBase.

## 8. Film outline (superseded Oct 29)

The old 8-scene outline is retired. The film follows the waterways (Mula, Mutha, the Sangam, the reservoirs upstream) and is built around ONE question that M3.1 picks from verified claims, posed in the first 10 s and answered in the final chapter. The shot grammar (hook, survey, chapters ≤30 s, payoff at the opening camera, close) is in `docs/PLAN_chronicle_ink.md` Phase 3 and is enforced by `stages/film_gate.py`. Last caption: "Putting down roots here, one brick at a time." (owner-authored).

**Fact standard (chronicle-ink):** each fact needs two agreeing publishers, one of them a reference institution (e.g. Britannica, UNESCO); at most two hedged single-source lines ("Records say…"); every number and name in a caption must be in its claims. This supersedes the ≥25-claim gate.

## 9. Upload-form copy (owner pastes; fill [brackets] from real runs)

- Title: `I Am Pune`
- Summary (190 chars): `Pune tells its own story, from the river confluence to Maratha palaces, colleges and the IT boom, drawn on its real map. Every fact double-sourced. Directed end to end by MiniMax M3.1 flash.`
- Me and this city: `Putting down roots here, one brick at a time.`
- When the film is final, generate `final/how_it_was_made.md` from real numbers in `runs.jsonl` and `research-report.json` (stages, tools, human interventions, cost), and `final/fact_sources.txt` (one unique URL per line from `claims.json`).
