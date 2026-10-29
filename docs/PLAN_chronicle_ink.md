# Plan: Pune life-story film on chronicle-ink (brief of Oct 29, rev 2)

## Context

The owner's brief (rev 2, from the contest site) asks for a 120–180 s Pune film (target ~150 s) made with the official **chronicle-ink** Skill (subject=city, structure=life, style=model), directed by MiniMax M3.1 flash through SandBase. It also asks that the film be **uploaded and submitted automatically** with the official client.

Owner decisions:
- The "UX/UI revamp" means the film's viewing experience.
- **Narration (MiniMax Speech) and MiniMax Music are explicitly selected.**

Facts checked on Oct 29:
- **Rules page.** Uploads close Oct 31 23:59:59 UTC. Each upload or edit is reviewed within a day, and saving an edit sends the entry back to review.
- **Contest ids.** The owner's `entry.json` and the site's city list agree: `city_id "pune"`, `place_lat 18.5211`, `place_lng 73.8553` (Wikidata Q1538).
- **Skill page.** Each fact needs two publishers that agree, one of them a reference institution such as Britannica or UNESCO. At most two hedged single-source lines ("Records say"). Era outlines are "approximate polygons… not surveyed maps". Rendering is WebGL in Chrome through HyperFrames.
- **Repo:**
  - Stages 1–3 have run: 24 kept claims, and **0 cite a reference institution**.
  - Overpass is unreachable from this network (all 4 mirrors). The OSM API, Geofabrik and Wikidata are reachable.
  - Stages 4–11 have never run.
- **SandBase tools:** `sandbase_minimax_speech_2_8_hd` and `sandbase_minimax_music_3` (instrumental via `[instrumental]` tags).

## Rev 3: what reading the Skill changed (Oct 29; overrides the phases below)

The Skill was verified (SHA-256 matches) and reviewed in `vendor/chronicle-ink-0.4.3/chronicle-ink/`. Owner decisions: the map comes from a **hotspot run**, and segment review **follows the Skill** (no vision model).

- **Harness, not a parallel pipeline.** The Skill's `chronicle.mjs all` stops at each `awaiting_…` step and writes `AGENT_TASK.md`. The new `stages/chronicle_agent.py` forwards each task and its request files to M3.1, writes M3.1's answer to the requested path, logs to runs.jsonl, and reruns `all`. This replaces the planned `questions.py`, `film_gate.py` and `era_hull.py`. The Skill's own script gate does the caption checks.
- **Facts:**
  - Tier 1 is fixed by the Skill (`src/engine/data/sources-allowlist.json`). For Pune that is effectively **Britannica**, UNESCO and a few museums. Wikipedia counts as one publisher. Indian government and university sites, and our 24 news-sourced claims, are **leads only**.
  - No `REFERENCE_INSTITUTIONS` list of our own.
  - M3.1 chooses the source pages. The harness saves them verbatim as `sources/<n>-<name>.txt` (`source: <url>` on the first line), using Playwright for Britannica, which returns 403 to curl.
  - M3.1 writes `work/facts/claims.agent.json`, with two claims per fact (one per publisher). The Skill's `facts` stage cross-checks them. `verify.py` is retired for this film.
  - The Britannica Pune article already supports: the Mula–Mutha junction, the Bhonsle and Maratha capital (1714–1817), "Oxford and Cambridge of India", University of Pune (1948), BORI (1917), the industrial suburbs, and **the 1961 Panshet Dam collapse washing away much of the old town** (a verifiable scar).
- **Map:** `tools/geo_cached.mjs` runs the unchanged `geo.mjs` and records every map read to `geo/cache/`. There is one hotspot session once M3.1 has written `geo/places.json`; reruns are then `--offline`. Era extents are M3.1's `areas` (polygon or `around` + `radius_km`), tagged "AI illustration" by the Skill.
- **Shots:**
  - 150 s = 27 two-bar shots on the fixed 88 BPM sections: intro 2 · verse 6 · build 2 · drop 4 · breakdown 4 · build2 2 · drop2 4 · outro 3.
  - Section roles follow `references/narrative-city.md`. "Begin at the historic core" maps to intro then verse: the globe, then the old core at the Sangam.
  - The camera stays calm at 2.4–5 km with few altitude changes. This **replaces** "alternate wide and close" and "fly, linger, pull back each chapter". Local detail comes from `focus` callouts on landmarks.
  - Captions: ≤2 lines, ≤9 words / 42 characters per line. We keep the 400 px legibility check.
- **Sound:**
  - **Narration:** one `minimax/speech/2.8/hd` clip per shot, saying **exactly the caption** (≤2.7 words/s), in `voice/voice.json`.
  - **Music:** `minimax/music/2.6` with `is_instrumental: true`, in `music/track.json`.
  - The Skill masters to −14 LUFS; its own mix replaces our `assemble.py`.
- **Review:** the Skill's render segments, contact sheets and numeric checks (frame-difference flicker scan, timing, captions). M3.1 reviews the numbers and text in `work/review.json` (max 3 rounds per segment). No frames are sent to a vision model.
- **Render:** about 0.8 s per frame, so roughly 1 h for 150 s with 4 workers. `npx hyperframes@0.8.30` is installed and runs. Keep `buildings_km` small enough for fewer than 60,000 footprints.
- **Still ours:** the cover, `entry.json`, `director_notes`, the submit wrapper, and `how_it_was_made.md`.

## What the rev-2 brief changes (vs rev 1)

| Area | Rev 1 / old plan | Rev 2 / this plan |
|---|---|---|
| Upload | Owner signs in and uploads; I prepare a kit | **I upload and submit with the official `contest-submit.py`**, entry `a43da048-c1e7-429f-9306-005dabcd638b`, using the owner's one-entry token (see Phase 5) |
| Opening | Today's Pune: globe → Ghats → rivers | **Begin at the historic core** (the old city by the Sangam) and explain how the city took its present shape |
| Story device | Waterways plus ONE central question, clues and payoff (required) | **Whole city vs local detail**, with origins → growth → present connected **through rivers and landmarks on the real map**. The question-and-payoff device is kept as our craft choice, not a requirement |
| Turning points | Test Panshet 1961, the Shaniwar Wada fire, the 1890s plague | No suggestions. Use only sourced turning points; never invent disasters, wars or rebirth |
| Narration / music | Owner asked | Rev 2 makes them opt-in. **The owner opted in for both** |
| Model id | Taken from CLAUDE.md | **Look it up** with `sandbase discover` before use; never assume |
| Skill zip | Versioned 0.4.3 + SHA-256 (download needs sign-in) | Unversioned `chronicle-ink.zip`, no checksum. Check whether it needs sign-in; review the contents and record the version |
| `my_city_line` | Free text | **≤50 characters, "one sentence about the place"** |
| Budget | Not mentioned | **Check `sandbase balance` and ask before exceeding it** |
| Conflicts | Stop and report | **Explain and ask** when the brief conflicts with the Skill (e.g. Overpass blocked, sparse building heights); never switch Skills silently |
| Entries | Entry 2 planned | **Only this one entry.** Never create another entry; later versions are edits to the same entry |

## Approach

### Phase 0: Setup
- Look up the M3.1 flash model id with `sandbase discover -t llm` and record it in CLAUDE.md §3.
- Run `sandbase balance`, then estimate the cost of the remaining work (M3.1 calls, speech, music). Ask before going over the balance.
- Fetch `https://www.sandbase.ai/lab/downloads/chronicle-ink.zip`.
  - If it returns 401, ask the owner to download it.
  - Unzip into `vendor/chronicle-ink/` and record its version and SHA-256.
  - Review it: network calls, `postinstall` scripts, binaries. Use `npm ci --ignore-scripts` where possible.
  - Read `SKILL.md`, its input format and `references/city-film-recipe.md`.
- Send the owner a 5-line note on how the Skill's inputs map onto our pipeline.
- **Smoke tests:**
  - `geo.mjs` on the old-city bbox. Overpass is blocked here, so if geo.mjs cannot use another real OSM source (OSM API, a Geofabrik extract), explain and ask (for example, run it on another network). Never invent data.
  - A HyperFrames render of the Skill's sample segment.

### Phase 1: Facts to the Skill's standard
Reuse `stages/research.py`, `stages/verify.py`, `sandbase_client.py` and the runs.jsonl logging.
- **`stages/questions.py`** (M3.1, high effort). It proposes 3 candidate story spines for "historic core → present shape". Each spine lists the claims it needs: the founding place, how each era extended the city, the river and landmark anchors, and 1–2 local details per chapter. It may add an optional central question.
- **Targeted research** for those needs, via `run.py --extend --priority`. Covers the old core and Sangam, the peths, the Peshwa era (0 claims today), the cantonments, the reservoirs, industry and IT.
- **Reference-tier pass** in `verify.py`. For each claim with no reference-institution publisher, M3.1 searches up to 3 times restricted to `REFERENCE_INSTITUTIONS` (copied from the Skill's definition). Each claim ends as an **upgrade**, a **hedge** (at most 2 per film) or a **drop**. `research-report.json` gains `reference_backed`, `hedged` and `dropped_by_reason`.
- M3.1 picks the spine whose chain is fully reference-backed. Turning points come only from verified claims.

### Phase 2: Geography
- Run `geo.mjs` for the city extent (PMC + Pimpri-Chinchwad + Hinjewadi): buildings with heights, streets and water. Wikidata landmarks only inside the bbox. Keep `tools/osm.py` views for river and landmark validation.
- Add the named reservoirs (Khadakwasla, Panshet) from OSM.
- **Era extents:** M3.1 names the OSM features that bound each era. `tools/era_hull.py` builds a buffered hull from them, and every era caption says "approx."
- Show a landmark's year only when a claim covers it.
- Never draw national or state borders; the PMC boundary is the outermost line.

### Phase 3: Story spine and shot list (the experience revamp)
M3.1 fills `film.json` in the Skill's chronology and shot-list format. `stages/film_gate.py` enforces this grammar:

| Beat | Time | Required elements (code-checked) |
|---|---|---|
| Hook | 0–10 s | **Close on the historic core** (one named place by the Sangam), the rivers glowing, then the first pull-back hinting at the whole city. Optional question caption at 5 s or earlier |
| Chapters ×4–5 | ≤30 s each | **Local detail → whole city**: fly to one exact place, linger on its detail, then pull back to show its era's extent lit on today's buildings, with a year counter. The rivers and landmarks link each chapter to the last. One hero shot per chapter |
| Turning point | inside a chapter | Only a verified one, shown only as far as its sources describe |
| Present | last chapter | Today's full extent, with every era lit outward from the core |
| Close | final 6 s | Return to the opening core view, now understood. Last caption is `my_city_line` if the owner keeps it. Final shot held ≥4 s |

Gate checks:
- Total 140–160 s; every chapter ≤30 s; wide and close shots alternate.
- Every caption is ≤2 lines and ≤32 characters per line.
- Every number and proper noun in a caption maps to its `claim_ids`.
- At most 2 hedged lines.
- Every place exists in the geo data.
- No living people, and no fictional people or events presented as history.
- If the optional question is used, it must be answered in the present chapter.

On failure, regenerate with the violations listed (max 2 tries), then stop.

**Narration:** M3.1 writes one voice line per caption with the same claim binding. `sandbase_minimax_speech_2_8_hd` renders them, and the measured durations drive shot timing. `stages/tts.py` gets a SandBase backend; macOS `say` is removed for real runs.

**Music:** M3.1 writes one `sandbase_minimax_music_3` prompt (instrumental, following the arc). The track is ducked under the voice.

Both calls are logged in runs.jsonl.

### Phase 4: Render (test segments first)
- Render 3 test segments: the hook, one chapter, and the close.
- M3.1 reviews the frames (reusing `stages/review.py`), with the geo preview as ground truth.
- Code checks: caption legibility on a 400 px downscale, and no text outside captions and allowed labels.
- Then the full render. Mux with `stages/assemble.py` (loudnorm −16 LUFS) and burn the captions in.
- **Cover:** M3.1 picks the frame and drafts the title. Code composes a 16:9 1920×1080 JPG of at most 5 MiB.
- **Teaser:** a 20 s, 9:16 cut for sharing (reach).

### Phase 5: Final checks, entry.json, upload and submit
**Checks** (extend `stages/check.py`):
- A full decode (`ffmpeg -v error -i film.mp4 -f null -`).
- Duration 120–180 s, 1920×1080, H.264/AAC, ≤100 MiB.
- The cover spec.
- A caption-to-claims audit and a scan for living people and borders.

**entry.json:**
- M3.1 drafts the title (≤80 chars) and summary (≤200) from the final film.
- `city_id "pune"`, 18.5211, 73.8553, exactly as given.
- `used_m31_flash: true` only with runs.jsonl evidence.
- `director_notes` from runs.jsonl: prompts, calls and tokens per stage, the Skill and tools, and human involvement (infrastructure by Antigravity and Claude Code, owner choices, logged edits).
- `sources`: one per unique URL in the final claims.
- `my_city_line`: ≤50 chars, owner-authored.

**Upload and submit** (approved in the owner's brief):
1. `curl -fL https://www.sandbase.ai/lab/contest-submit.py -o tools/contest-submit.py`, then **read the whole file** before running it. If it asks for the contest declaration, show the owner its exact wording before submitting.
2. Token handling: the token goes in a mode-600 file in the session scratchpad (never the repo). It is passed only as `LAB_SUBMISSION_TOKEN` in the subprocess environment, never in arguments, URLs, logs, runs.jsonl, commits or `entry.json`. It is never sent to any other service, and never echoed.
3. Run `python3 tools/contest-submit.py --contest city-life --entry a43da048-c1e7-429f-9306-005dabcd638b --metadata final/entry.json --video final/film.mp4 --cover final/cover.jpg`.
4. Report success **only** when Lab returns `pending` or `approved`, then point the owner to https://www.sandbase.ai/lab/event/aicityremix to track review. Pending is not approval.
5. On failure, keep the files and report the error. On **HTTP 401 or expiry**, ask the owner to fetch resume instructions at `https://www.sandbase.ai/lab/event/aicityremix/mine?upload=a43da048-c1e7-429f-9306-005dabcd638b`. Never re-render for that reason and never create another entry.
6. Later versions are edits to this same entry, and each one restarts review.

Also write `final/how_it_was_made.md` and `final/fact_sources.txt`.

Publishing the repo is outward-facing, so ask first and confirm that no `.env`, token or caches are included.

## Schedule (UTC)

The token expires within 24 h of issue (about Oct 30 morning). Don't rush quality to beat it; use the resume link if it lapses.

| When | Gate |
|---|---|
| Oct 29 12:00 | Skill reviewed, model id and balance checked, geo.mjs and HyperFrames smoke tests pass (or blocker raised) |
| Oct 29 22:00 | Reference-tier facts done; spine chosen; film.json passes the gate |
| Oct 30 06:00 | Test segments approved; narration and music done |
| **Oct 30 12:00** | **v1 passes check → submitted (pending)** |
| **Oct 31 12:00** | **Last edit submitted** (one review cycle before close) |

If behind, cut in this order: teaser → music (code-generated instead) → 5th chapter → narration (captions only). Never cut verification, geo truth or the final checks.

## Critical files

- **Reuse:** `run.py`, `sandbase_client.py`, `stages/research.py`, `stages/verify.py`, `stages/review.py`, `stages/assemble.py`, `stages/check.py`, `tools/osm.py`, `log_edit.py`.
- **New:** `stages/questions.py`, `stages/film_gate.py`, `tools/era_hull.py`, `stages/skill_inputs.py` (adapter to the Skill's input format), a SandBase backend in `stages/tts.py`, and `stages/submit.py` (a wrapper that runs the official client with the token from the environment and parses the Lab status).
- **Retire for this entry:** `stages/script.py`, `stages/scenes.py`, `stages/endcard.py`.

## Verification

- Unit tests with `fake_*` doubles for `film_gate.py`, `era_hull.py`, and `submit.py` (the token never appears in argv or logs).
- `research-report.json` shows `reference_backed` ≥ the number of captions and `hedged` ≤ 2.
- Test segments are rendered, screenshotted and reviewed.
- `check.py` passes on the final MP4 and cover.
- The `entry.json` schema validates, with the exact ids.
- The submit result shows `pending` or `approved`.
- Each step appends a dated line to PROGRESS.md and is committed.
