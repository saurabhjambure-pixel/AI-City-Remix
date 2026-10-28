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

- **2026-10-29 ~01:30 IST — Handoff steps 1–4 (Claude Code)**
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
