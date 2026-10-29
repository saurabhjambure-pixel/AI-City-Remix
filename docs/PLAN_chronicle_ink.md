# Plan: "I Am Pune" rebuilt on chronicle-ink. Evaluation of the brief, then a better plan

## Context

The brief asks for a ~150 s Pune life-story film made with the official **chronicle-ink v0.4.3** Skill (subject=city, structure=life, style=model). The film must follow the waterways, be built around one question, and be directed by M3.1 flash through SandBase. The brief also asks for automatic upload.

Owner decisions so far: "UX/UI revamp" means the film's viewing experience; use MiniMax Speech narration; use MiniMax Music.

Facts checked on Oct 29 at about 02:30 UTC:
- **Rules page.** Uploads close Oct 31 23:59:59 UTC. Each upload or edit is reviewed within a day, and saving an edit sends the entry back to review. The uploader signs in with SandBase and ticks a declaration. Films run 60–180 s at 720p or higher with subtitles. No living people. Maps must be lawful.
- **Site city list** (`/lab/assets/cities-*.js`): `{id:"pune", lat:18.5211, lng:73.8553, wikidata:"Q1538"}`. The brief's entry.json uses placeholders, and these are the real values.
- **Skill page.** It renders WebGL in Chrome through HyperFrames. "Each fact needs two publishers that agree, one of them a reference institution such as Britannica or UNESCO." Single-source lines must be hedged ("Records say"), at most two per film. Era outlines are "approximate polygons… not surveyed maps." The Skill page also says to avoid cities "that OpenStreetMap barely maps (buildings and heights drive the picture)."
- **Repo audit:**
  - Stages 1–3 have run: 24 kept claims from 14 publishers, and **0 cite a reference institution**.
  - These topics have no kept claim: Sangam confluence (c102), Shaniwar Wada fire (c124), weekday peths, plague.
  - Panshet 1961 (c103) is kept, but only from news sources.
  - Overpass is unreachable from this network, so the map runs on Nominatim, with no buildings or streets.
  - Stages 4–11 have never run. `tts.py` uses macOS `say`.
  - runs.jsonl has 703 calls and about 20.7M tokens.

## Evaluation of the brief: what to change

1. **"Upload and submit automatically" cannot be done as written.** The upload needs the owner's SandBase sign-in and a personal declaration tick. CLAUDE.md and my safety rules both forbid me from signing in or making that attestation. The better plan gives the owner a 5-minute upload kit. The owner signs in, uploads and ticks the declaration. With the owner's go-ahead at that moment, I can fill the text fields in the browser pane and check the live entry page afterwards.
2. **No schedule.** The brief removes CLAUDE.md §6 but adds no replacement. About 69 h remain, and each upload costs up to a day of review. A safe v1 must be live by **Oct 30 12:00 UTC**, with the final edit by **Oct 31 12:00 UTC** (see Schedule).
3. **The fact standard will wipe out the current claims.** 0 of 24 claims meet the reference-institution rule. "Re-check and upgrade" needs a concrete method. Add a reference-tier pass that searches each claim on a reference allowlist (taken from the Skill's own definition: Britannica, UNESCO, government gazetteers/census/PMC, universities). Drop the arbitrary ≥25 gate. The real gate is that **every caption is covered** and each chapter has at least one reference-backed claim.
4. **"M3.1 picks the question from verified claims" has a dependency loop.** The interesting questions (weekday peths, two rivers) have no claims yet. Flip the order to **question-first research**: M3.1 proposes 3 candidate questions, research targets the claims each one needs, and M3.1 then picks the question whose answer chain is fully verified.
5. **The geography is the biggest technical risk, and the brief does not flag it.**
   - geo.mjs needs Overpass for buildings, streets and water, and Overpass is blocked here.
   - Pune's building heights in OSM are sparse.
   - Wikidata landmark years are numbers on screen, so under the Skill's own rule they must also be in claims.
   - Era polygons drawn freehand by the model would be unanchored.
   - Fix: test geo.mjs in hour 1. Build era extents from OSM features M3.1 names, using a code-built hull. Show landmark years only when a claim covers them.
6. **The experience spec is a list of 15 equal wishes with no structure.** It needs a shot grammar that M3.1 fills and code enforces (see below). Without one, "intrigue", "clues pay off" and "return to an opening place" cannot be checked.
7. **Smaller gaps:**
   - 400 px legibility needs a numeric floor: caption text at least 64 px at 1080p and at most 32 characters per line, checked on a 400 px downscale.
   - Reach (20% of the score) is ignored. Add a public repo, a share-ready cover and a 20 s teaser cut.
   - The final line "Putting down roots…" is owner-authored content. It is allowed, but it must be logged as such.
   - Supply-chain care for the zip: verify the SHA-256, unzip into an isolated folder, read the scripts, and use `npm ci --ignore-scripts` where possible.

## Approach

### Phase 0: Setup (≈2 h)
- Re-read the rules (done). Update CLAUDE.md §6 (new schedule) and §8 (pointer to this brief) and the MASTER_PLAN §3 fact standard.
- Download the zip to `vendor/chronicle-ink-0.4.3/` (gitignored zip, committed folder), verify the SHA-256 `61dbc7b6…1af`, and review it: list every network call, `postinstall` script and binary. Then read `SKILL.md`, its input format and `references/city-film-recipe.md`.
- **Before building**, send the owner the 5-line input-to-pipeline mapping the brief asks for.
- **Smoke test the risky dependencies first:**
  - `geo.mjs` on the Sangam bbox. Try the Overpass mirrors (`overpass-api.de`, `overpass.kumi.systems`, `overpass.private.coffee`). If all are blocked, stop and ask the owner to run it on another network (for example a phone hotspot). Never invent data.
  - A HyperFrames render of the Skill's sample segment.
  - SandBase speech and music endpoint discovery: `npx -y @sandbaseai/cli@latest discover|inspect`.

### Phase 1: Facts to the Skill's standard (≈6 h, mostly model time)
Reuse `stages/research.py`, `stages/verify.py`, `sandbase_client.py` and the runs.jsonl logging. Add:
- `stages/questions.py` (M3.1, high effort). It proposes 3 central questions, each with the claims needed to pose it, plant 2–3 clues and answer it, plus 3 candidate turning points (Panshet 1961, Shaniwar Wada fire, 1890s plague).
- **Targeted research** for those needs (an extension to `run.py --extend --priority`), including the Sangam, the reservoirs, the peths and the Peshwa era (currently 0 claims).
- **Reference-tier pass** in `verify.py`. For every kept or new claim with no reference-institution publisher, M3.1 searches up to 3 times restricted to the allowlist. The result is an **upgrade** (a reference source found), a **hedge** (single source, max 2 per film), or a **drop**. The allowlist lives in code as `REFERENCE_INSTITUTIONS`, copied from the Skill's definition; M3.1 makes the agreement judgement.
- `research-report.json` gains `reference_backed`, `hedged` and `dropped_by_reason`.
- M3.1 then picks the question whose answer chain is fully reference-backed. Turning points are kept only if verified; Panshet is shown "as far as the sources describe".

### Phase 2: Geography (≈3 h, in parallel with Phase 1)
- Run `geo.mjs` for the `city` extent (PMC plus Pimpri-Chinchwad and Hinjewadi). Keep the existing `tools/osm.py` views for river and landmark validation.
- Add the **Khadakwasla and Panshet reservoirs** as named water features from OSM (they are missing today). Use Wikidata landmarks only where the Q-id is inside the bbox.
- **Era extents:** M3.1 names the OSM features that bound each era (for example peth polygons and landmarks from claims). `tools/era_hull.py` builds a buffered concave hull from those features. Every era caption carries "approx."
- Never draw national or state borders; the PMC boundary is the outermost line.

### Phase 3: Story spine and shot list. The experience revamp (M3.1, high effort)
Replace the brief's wish list with a **typed shot grammar**. M3.1 fills `film.json` in the Skill's chronology and shot-list format, and `stages/film_gate.py` enforces it:

| Beat | Time | Required elements (code-checked) |
|---|---|---|
| Hook | 0–10 s | Globe → Western Ghats edge → **rivers glow first** → today's city. Question caption at 5 s or earlier, posed over one named place (`anchor_place`). |
| Survey | 10–25 s | Slow wide pass over today's Pune. The 3–4 `return_places` are introduced, each lit briefly (the planted clues). |
| Chapters ×4–5 | ≤30 s each | Pattern **fly → linger → pull back**. Each chapter opens on one `return_place`, lights its era extent on today's buildings with a year counter, has one `hero_shot`, and ends by pulling back to the whole city. |
| Turning point | inside a chapter | Only a verified scar (for example Panshet 1961: the water layer rises, then recedes as far as the sources say). |
| Payoff | last 25 s | Return to the **exact opening camera** (same keyframe, now with all eras lit). The answer caption resolves the question, and each `clue_id` planted earlier is referenced. |
| Close | final 6 s | "Putting down roots here, one brick at a time." Final shot held at least 4 s. |

Gate checks:
- Total length 140–160 s, every chapter 30 s or less, and wide and close shots alternate.
- Every clue planted is paid off.
- Every caption has 2 lines or fewer and 32 characters or fewer per line; every number and proper noun in a caption maps to its `claim_ids`; at most 2 hedged lines.
- Every place name exists in the geo data.
- No living person is named; the generic close voice is allowed.

On failure, regenerate with the violations listed (max 2 tries), then stop.

**Narration.** M3.1 writes the voice lines, one per caption, with the same claim binding. MiniMax Speech renders them, and the measured durations drive the shot timing, so the visuals fit the voice rather than the other way round. **Music:** M3.1 writes one MiniMax Music prompt (an instrumental mood that follows the arc), and the track is ducked under the voice. Both calls are logged in runs.jsonl. `stages/tts.py` gets a SandBase backend; macOS `say` is removed for real runs.

### Phase 4: Render with test segments first (≈8 h wall time)
- Render 3 **test segments** with the Skill's renderer: the hook, one chapter including a turning point, and the payoff.
- M3.1 reviews the frames at medium effort, reusing `stages/review.py`'s frame sampling. The geo preview is the ground truth.
- Code checks on the test segments: caption legibility on a 400 px downscale, and no text outside captions and allowed labels.
- Then the full render. Mux narration and music with the existing `stages/assemble.py` (loudnorm to −16 LUFS) and burn the captions in.
- **Cover:** M3.1 picks the frame (default: the lit payoff shot) and drafts the title. Code composes a 16:9 1920×1080 JPG of at most 5 MiB.
- **Teaser:** a 20 s, 9:16 cut of the hook for sharing (reach).

### Phase 5: Final checks and the upload kit
Extend `stages/check.py`:
- A full decode (`ffmpeg -v error -i f.mp4 -f null -`).
- Duration 120–180 s, 1920×1080, H.264/AAC, 100 MiB or less, and the cover spec.
- A caption-to-claims audit and a living-people/borders scan.
- M3.1 drafts the title and summary from the final `film.json` and the frames.
- Write `final/entry.json` with `city_id:"pune"`, lat `18.5211`, lng `73.8553` (exact).
- Generate `director_notes` from runs.jsonl: prompts, call counts and tokens per stage, the Skill and tools used, and human involvement (infrastructure by Antigravity and Claude Code, owner choices, logged edits).
- Generate `sources` from the final claims.
- Also write `final/how_it_was_made.md` and `final/fact_sources.txt`.

**Upload kit** (`final/UPLOAD.md`): file paths, copy-paste fields and a 6-step checklist.
1. The owner signs in, uploads, pastes the fields, ticks the declaration and saves.
2. If the owner asks in chat, I fill the text fields in the browser pane after they have signed in.
3. I check the entry page once it is live.

**Publishing the repo** is outward-facing: I ask first and confirm that no `.env` or caches are included.

## Schedule (UTC, replaces CLAUDE.md §6)

| When | Gate |
|---|---|
| Oct 29 06:00 | Skill reviewed, mapping sent, geo.mjs and HyperFrames smoke tests pass (or blocker reported) |
| Oct 29 18:00 | Reference-tier facts done; question chosen; film.json passes the gate |
| Oct 30 06:00 | Test segments approved; narration and music done |
| **Oct 30 12:00** | **v1 passes check → owner uploads** (one review cycle of slack) |
| **Oct 31 12:00** | **Final edit uploaded** (last safe point for review before close) |

If behind, cut in this order: teaser → music (fall back to code-generated) → the 5th chapter → narration (captions only). Never cut verification, the geo truth or the final checks.

## Critical files

- **Reuse:** `run.py`, `sandbase_client.py`, `stages/research.py`, `stages/verify.py`, `stages/review.py`, `stages/assemble.py`, `stages/check.py`, `tools/osm.py`, `log_edit.py`.
- **New:** `stages/questions.py`, `stages/film_gate.py`, `tools/era_hull.py`, an adapter that writes Skill inputs (`stages/skill_inputs.py`), and the SandBase backend in `stages/tts.py`.
- **Retire for this entry:** `stages/script.py`, `stages/scenes.py` and `stages/endcard.py`. The Skill's renderer replaces the hand-built scene HTML; the existing HTML stays only as a style reference.

## Verification

- Unit tests with `fake_*` doubles for `film_gate.py` (caption-claim binding, clue payoff, timing) and `era_hull.py`.
- On real outputs:
  - `research-report.json` shows `reference_backed` ≥ the number of captions and `hedged` ≤ 2.
  - The test segments render and get screenshots, reviewed by M3.1 and by me.
  - `check.py` passes on the final MP4: full decode, duration, resolution, size, caption audit.
  - The cover meets the spec.
  - The entry.json schema validates, with the exact city_id and coordinates.
- Each step appends a dated line to PROGRESS.md and is committed.
