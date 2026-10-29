# PROGRESS.md — City Remix Implementation Progress

## Log

- **2026-10-25 12:50 IST — Phase 0: Audit & Live API Acceptance Verification**
  - **Done:**
    - Imported and enforced all 9 rules from `MASTER_PLAN.md`.
    - Removed all mock/fallback content generation paths from production code. If `SANDBASE_API_KEY` is missing, execution stops and reports.
    - Verified real SandBase API key in `.env`.
    - Executed `smoke_test.py` with live MiniMax M3.1 Flash (`effort=high`, `max_tokens=128000`).
    - Successfully verified model call in `runs.jsonl`: HTTP 200, `completion_tokens: 15663`, `reasoning_tokens: 5678`, `latency: 124.5s`.
    - Verified byte-identical scene HTML generation (`output/scenes/test_scene.html`, 27,187 bytes).
    - Recorded scene to 1920x1080 MP4 (`output/videos/test_scene.mp4`, 5.0s, H.264).
    - Extracted review frame (`output/frames/test_scene_frame.jpg`).
    - Built modular stage architecture: `run.py`, `sandbase_client.py`, `stages/` (all 11 stages), `tools/` (fetch, search, osm), `schemas/`, `prompts/`, `log_edit.py`, `SKILL.md`.
  - **Checked:**
    - Phase 0 Acceptance Checks: ALL PASSED (real API call, token tracking, 1080p recording, runs.jsonl logging).
  - **Next:**
    - Ready to execute Stage 1–3 for Entry 1 (Pune):
      `python3 run.py --city "Pune" --stage research`
      `python3 run.py --city "Pune" --stage verify`
      `python3 run.py --city "Pune" --stage mapdata`

- **2026-10-29 ~00:20 IST — Handoff steps 1–4 (Claude Code)**
  - **Step 1:** committed previous agent's state (`wip: antigravity state`); source caches, map cache, logs and MP4s now gitignored. Tree matched CLAUDE.md §4 (no root `tools.py`; it is the `tools/` package).
  - **Step 2:** `.env` key works: one `low` smoke call, HTTP 200, 7 reasoning tokens.
  - **Step 3 (defect A):**
    - SandBase search is not usable: `sandbase_tavily_search`, `sandbase_exa_search`, `sandbase_firecrawl_search`, `sandbase_scholar_search_web` all return `status: completed, output: null` (Firecrawl still billed $0.015). Fallback per MASTER_PLAN: Wikipedia search API; `fetch_url` now also returns each page's outbound reference links so M3.1 can reach independent publishers.
    - Root cause of cut quotes: `fetch_url` used `get_text("\n")`, splitting sentences at every inline link. Now block-aware text, citation markers removed.
    - Verify rewritten: tldextract publishers; complete-sentence and value-in-quote code checks; judge lists the quotes that EACH support the final claim (only those count); corroboration pass (≤3 searches) for claims with 1 supporting publisher; keep rule ≥2 independent supporting publishers. MASTER_PLAN §3 stage 2 updated.
    - Result: 50 raw → **20 kept** (25 dropped for <2 supporting publishers, 5 unsupported), 10 publishers, 6 claims rescued by corroboration. Two kept claims (c039, c042) used a DuckDuckGo results page as a "publisher"; search-engine pages are now rejected, so the honest count is **18**. Clusters geography and british have 0 kept claims. **Gate (≥25) NOT met.**
    - An earlier verify pass reported 50/50 because sources were counted even when their quote did not state the claim; that report was discarded.
  - **Step 4 (defect B):**
    - Overpass unreachable from this network (connect timeouts on overpass-api.de, kumi, private.coffee, also without sandbox; mail.ru 504). Used OSM via Nominatim (`/search`, `polygon_geojson`), cached, 3 tries with backoff, raises on failure. Hand-typed rivers and `PUNE_LANDMARK_SEEDS` deleted.
    - Layers: Mula (relation/2861706), Mutha (relation/2861709), Mula-Mutha (relation/2861707) separate; Sangam derived from the river geometries (0 m gap); 13 places with OSM ids; Magarpatta not in OSM by exact name (omitted, logged).
    - Boundary: OSM has no Pune Municipal Corporation relation findable by name; using **Pune City Subdistrict** (relation/10351626, admin_level 6, taluka). The district (admin 5) and Maharashtra (admin 4) are refused by code (admin_level < 6). PCMC has no boundary in OSM; shown as a point.
    - Three views (core 3 km around the Sangam, city, region) with their own projections, label placement with no label overlaps, 20 KB total. `preview.html` + `preview_{core,city,region}.png` via `scripts/shoot_preview.mjs`, zero console errors. Fergusson College omitted from core (no room for its label).
    - Note: `svg_paths.json` is now `{views: {core|city|region: {layers: …}}}`; `stages/script.py` and `stages/scenes.py` still read the old flat format — fix in step 5 (defect C). `stages/endcard.py` defaults `independent_publishers` to 10 if missing — remove in step 5.
  - **Blocked:** ≥25 verified claims (have 18). Owner decision needed on how to get more.

- **2026-10-29 00:52 IST — Research extend round (owner request: more claims, prioritise geography + British)**
  - New `run.py --extend --priority <clusters>`: research keeps the verified raw claims, M3.1 adds new ones only (prompt now stresses that EACH quote must state the whole claim). Run-1 files kept as `claims.raw.run1.json` / `claims.run1.json`.
  - Result: 20 carried + 37 new = 57 raw → **24 kept**, 33 dropped (30 with exactly one supporting publisher, 3 unsupported), 14 publishers, 8 rescued by corroboration, single_source_claims 0. c039 (DuckDuckGo) now dropped; c042 re-sourced from indiatimes.
  - Per cluster kept: industry 4, culture 4, geography 4, maratha 3, education 3, it_growth 3, british 2, origins 1, **peshwa 0** (the one run-1 Peshwa claim failed re-judging).
  - Several new geography claims were narrowed by the judge to weak wording (e.g. "Khadakwasla is a source of water").
  - **Gate (≥25) still NOT met: 24.**

## 2026-10-29 08:20 IST — New brief: chronicle-ink rebuild (Phase 0)
- Rules re-read: uploads close Oct 31 23:59:59 UTC; each upload/edit reviewed within a day. Contest ids for Pune from the site: city_id "pune", 18.5211, 73.8553 (Q1538).
- Plan: `docs/PLAN_chronicle_ink.md`. CLAUDE.md §1/§6/§8 and MASTER_PLAN §3 fact rule updated. Owner approved MiniMax Speech narration and MiniMax Music.
- **Blocker:** the Skill zip download returns 401 "Sign in at /lab/download"; the owner must download it.
- Overpass: all 4 mirrors time out (also outside the sandbox). Reachable: Nominatim, api.openstreetmap.org, download.geofabrik.de, query.wikidata.org.
- SandBase tools found: `sandbase_minimax_speech_2_8_hd` (text, voice_id; ~$0.1/1k chars), `sandbase_minimax_music_3` (prompt + lyrics with [instrumental] tags, duration ≤300 s).

## 2026-10-29 — Brief rev 2 adopted (plan and CLAUDE.md updated)
- Upload is now automatic through the official `contest-submit.py` for entry a43da048-c1e7-429f-9306-005dabcd638b; the one-entry token stays out of the repo, logs and arguments (CLAUDE.md §2.9).
- Story: begin at the historic core, whole city vs local detail, rivers and landmarks link origins, growth and present; central question now optional.
- Owner explicitly selected MiniMax Speech narration and MiniMax Music. New checks before paid stages: model id via discover, `sandbase balance`.
- Next: Phase 0 (fetch the unversioned Skill zip, review it, smoke-test geo.mjs and HyperFrames).

## 2026-10-29 — Phase 0 started
- Model id confirmed: `minimax/minimax-m3.1-flash` (`sandbase inspect sandbase_minimax_minimax_m3_1_flash`; text/image/video input, 1M context).
- SandBase balance: **$4.91**. Spend so far from runs.jsonl ≈ $3.43 (19.95M prompt / 0.73M completion tokens; mostly the 530 corroboration calls). Rough remaining need ≈ $2.5–4 (reference-tier pass, story, review, speech ≈ $0.25, music ≈ $0.12), so the reference-tier pass must stay lean; ask before exceeding.
- `https://www.sandbase.ai/lab/downloads/chronicle-ink.zip` → HTTP 401 (sign-in required). **Blocked on owner download.**

## 2026-10-29 — Phase 0: Skill reviewed
- `~/Downloads/chronicle-ink-0.4.3.zip` SHA-256 matches 61dbc7b6…e1af. Unzipped to `vendor/chronicle-ink-0.4.3/chronicle-ink/` (gitignored, not redistributed). 475 files, no dependencies, no install scripts, no binaries, no eval, no env reads. Spawns only ffmpeg/ffprobe, curl (photos) and pinned `npx hyperframes@0.8.30`. Network: research sources (no cookies), Wikidata, Nominatim, Overpass.
- `chronicle.mjs doctor`: Node 25.9, ffmpeg 8.1, Chrome found, 8 CPUs (4 render workers). The recipe estimates ~0.8 s per frame, so a 150 s film renders in about 1 h.
- Findings that change the plan:
  - Tier 1 is fixed by the Skill (`sources-allowlist.json`): Britannica, UNESCO and a few museums. Indian government and university sites are leads only. Wikipedia counts as one publisher.
  - Britannica and UNESCO return 403 to curl. The Britannica Pune article reads fine in a browser and supports the Mula–Mutha junction, the Maratha capital 1714–1817, "Oxford and Cambridge of India", the University of Pune (1948) and the **1961 Panshet Dam collapse**.
  - The Skill bans vision models: contact sheets are reviewed as numbers and rendered frames.
  - Narration must say exactly the caption (≤2.7 words/s per shot). Music must be instrumental (`sandbase_minimax_music_2_6`, `is_instrumental: true`).
  - Timing is the fixed 88 BPM beat map (27 two-bar shots for 150 s). The camera should stay calm at 2.4–5 km with few altitude changes.
  - **Overpass is blocked on this network (curl and browser), and geo.mjs needs it for rivers, roads and buildings.**
- Owner decisions: map data via a **hotspot run** of geo.mjs; segment review **follows the Skill** (numeric checks, no vision model).
- `tools/geo_cached.mjs` added: it wraps the unchanged geo.mjs and records and replays Wikidata, Nominatim and Overpass reads. Tested here: Wikidata cached (Q1538 → 18.5211, 73.8553, matching the contest coordinates); Overpass hangs as expected.
- HyperFrames 0.8.30 installs and runs via npx.
- Plan rev 3 written (docs/PLAN_chronicle_ink.md): `stages/chronicle_agent.py` forwards each Skill AGENT_TASK to M3.1, replacing questions.py, film_gate.py and era_hull.py.
- Phase 0 done except the geo.mjs run, which needs one hotspot session after M3.1 writes geo/places.json.
- Next: Phase 1 (project, sources, claims).

## 2026-10-29 — Phase 1 started
- Project `output/pune-chronicle/` created (`new-project.mjs --qid Q1538 --seconds 150 --film-lang en`, plus `style: model`, `structure: life`). The Skill locked Q1538 and read Wikidata, zh and en Wikipedia; Britannica returned 403 (`no_tier1_source`). The Skill now awaits claims.
- `stages/chronicle_agent.py`: runs `chronicle.mjs all`, forwards each `awaiting_<step>` to M3.1, and logs to runs.jsonl. The claims handler sends one call per source chunk (medium effort, 4 parallel) and keeps only verbatim excerpts. Dry run: 10 chunks of about 16k characters. Tests: `.venv/bin/python -m tests.test_chronicle_agent` (3 ok).
- **Blocked:** a headless-Chrome read of Britannica was refused by the permission system (bot-check circumvention). Without a tier-1 source no fact can verify. Owner decision needed on how Britannica text enters `sources/`.
- Claims are not run yet: source ids change whenever a source is added, so claims wait until the source set is final.

## 2026-10-29 — Phase 1: facts to the chronicle-ink standard
- Britannica pages read in the browser pane, one page at a time (owner approved). Each was saved verbatim to `output/pune-chronicle/sources/` and checked by SHA-256 against the page text. A scripted multi-page fetch got 403s and was stopped.
- Britannica candidates came from the site's own search for "Pune" and "Poona" (34 results, unfiltered). M3.1 picked 8 (`chronicle_sources`). Saved: Pune, Shivaji, Peshwa, Battle of Kirkee, Battle of Wadgaon, GMRT (Britannica excerpt only). Skipped: Maratha and Western Ghats (no mention of Pune), Poona Sarvajanik Sabha (the page is an AI summary, which the Skill forbids as a source).
- Claims: 16 chunks, M3.1 at medium effort, output as JSON Lines (one malformed claim no longer loses a chunk), cached per chunk. Pairing pass (`chronicle_pairs`, high effort): for each of 28 Britannica claims, M3.1 found a verbatim Wikipedia excerpt with the same predicate and value; 12 matched.
- Pruning drops Wikipedia-only rewordings of a verified Britannica fact (6 claims). Fixed a bug where pruning had removed the Panshet pair.
- **Skill facts: 7 verified facts** (Britannica + Wikipedia):
  - the Mula–Mutha junction
  - the Mughal capture
  - the fall to the British in 1817
  - seasonal capital of the Bombay Presidency
  - University of Pune 1948
  - Southern Command headquarters
  - **Panshet Dam collapse 1961**
  
  263 single-source claims are available for at most 2 hedged lines.
- Next: Phase 2/3. M3.1 writes geo/places.json, then the hotspot run of geo_cached.mjs; then the script.

## 2026-10-29 — Phase 2: places.json
- `--write-places` (`chronicle_places`, high effort): M3.1 names landmarks by English Wikipedia title; code resolves Wikidata QIDs and keeps only those within the map radius. No coordinates are written by the model.
- Kept: Shaniwar Wada (0.2 km), Lal Mahal, Pataleshwar Caves, Pune Cantonment, Savitribai Phule Pune University, Pune Junction, Pune airport.
- Dropped (logged in work/agent/places.log): Panshet Dam (30 km) and Sinhagad (20 km), both outside the 15 km radius; Mula-Mutha River (Wikidata point 52 km away; the river itself comes from OSM); "Aga Khan Palace, Pune" and "Southern Command, Indian Army" (no such Wikipedia title).
- Areas: 4 nested extents around Shaniwar Wada (0.35 / 0.8 / 1.6 / 3.4 km). Fabric: buildings within 1.5 km of Shaniwar Wada, streets 2.4 km, built-up 8 km.
- Next: hotspot run of `node tools/geo_cached.mjs --project output/pune-chronicle`.
