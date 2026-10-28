# CLAUDE.md — City Remix (handoff)

You are taking over this project from a planning chat and a previous coding agent (Google Antigravity). Read this file, then `MASTER_PLAN.md` (the full spec), then `PROGRESS.md` if present. Then start at **§5 First actions**.

## 1. Goal and deadline

- Contest: SandBase "AI City Remix". Uploads close **Oct 28 23:59 UTC = Thu Oct 29, 05:29 IST**. Judging Oct 29–30, results Oct 31.
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

## 6. Schedule (IST)

| When | Gate |
|---|---|
| Sun Oct 25 | A and B done; ≥25 verified claims; real map views |
| **Mon Oct 26, 3 PM** | **v1 film passes stage 11 (all checks)** → owner uploads; repo public |
| Mon Oct 26 evening | Review loop working |
| **Tue Oct 27, 9 PM** | **Final Pune film uploaded** (edits re-enter review for up to a day) |
| Wed Oct 28, 9 PM | Entry 2 uploaded |

If behind, cut in this order: music → review round 2 → scene 6 → entry 2. Never cut verification or the final checks.

## 7. Contest constraints (enforce in stage 11)

60–180 s · MP4 · ≥720p (target 1920×1080) · English with subtitles in the video · original work · no copyrighted film or music · **no real living people** (no faces, none named; the personal close is voice only) · maps lawful: city level, **no national or state borders** · directed with M3.1 flash through SandBase.

## 8. Film outline (script stage input; M3.1 may adjust)

1. Cold open at the river confluence: "I am Pune." · 2. Maratha seat: Lal Mahal, Shaniwar Wada (Bahirjee Naik line only if verified) · 3. Peshwa capital to British rule, cantonments · 4. "Oxford of the East", colleges · 5. Industry then IT: Pimpri-Chinchwad, Hinjewadi · 6. One warm thing: monsoon or food · 7. Personal close, voice only: "Someone new is putting down roots here…" · 8. End card with research stats, "Directed by MiniMax M3.1 flash via SandBase", repo URL.

## 9. Upload-form copy (owner pastes; fill [brackets] from real runs)

- Title: `I Am Pune`
- Summary (190 chars): `Pune tells its own story, from the river confluence to Maratha palaces, colleges and the IT boom, drawn on its real map. Every fact double-sourced. Directed end to end by MiniMax M3.1 flash.`
- Me and this city: `Putting down roots here, one brick at a time.`
- When the film is final, generate `final/how_it_was_made.md` from real numbers in `runs.jsonl` and `research-report.json` (stages, tools, human interventions, cost), and `final/fact_sources.txt` (one unique URL per line from `claims.json`).
