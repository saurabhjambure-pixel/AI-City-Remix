# AI City Remix Pipeline

## The film: "Pune: Mula River and Mutha River" (AI City Remix entry)

A 150-second 3D life-story film of Pune, directed end to end by **MiniMax M3.1 flash** through SandBase,
made with the official **chronicle-ink v0.4.3** Skill (subject city, structure life, style model). The globe
flies into ~17,000 real OpenStreetMap buildings; history is projected on today's city as light, from the
Mula–Mutha junction to the 1961 Panshet Dam flood and the present. Every fact on screen passed the Skill's
cross-check: two agreeing publishers, one a reference institution (Britannica).

**How it was made** (`stages/chronicle_agent.py` drives the Skill; every model call is in `runs.jsonl`):

| Step | Who decides | Code |
|---|---|---|
| Choose Britannica pages from Britannica's own search results | M3.1 | `--plan-sources` |
| Atomic claims with verbatim excerpts; Britannica↔Wikipedia pairing | M3.1 | Skill `facts` + harness |
| Landmarks (Wikidata QIDs resolved by code) and era extents | M3.1 | `--write-places`, `tools/geo_cached.mjs` |
| Chronology, 27-shot list, every caption | M3.1 | `--write-film` (Skill gate + independent M3.1 entailment check) |
| Segment review from code measurements (no vision model) | M3.1 | `stages/chronicle_review.py` |
| Narration (MiniMax Speech 2.8 HD) and instrumental (MiniMax Music 2.6) | M3.1 prompts, SandBase tools | `stages/chronicle_audio.py` |
| Title, summary, cover frame; checks; upload | M3.1 / code | `stages/chronicle_final.py`, `tools/submit_entry.py` |

Final result: all 10 Skill checks pass (format, loudness, downbeats, sound sync, captions, AIGC labels,
re-hooks, facts, scene scan, visual review). Plan and decisions: `docs/PLAN_chronicle_ink.md`; day-by-day log:
`PROGRESS.md`; package: `final/` (the MP4 itself is not committed).

**Not included:** the chronicle-ink Skill (download it from SandBase Lab into `vendor/chronicle-ink-0.4.3/`),
the official `contest-submit.py`, the full source texts the facts were extracted from, and generated audio/video
masters. Credentials come only from `.env` (see `.env.example`).

### Data, sources and licences

- Code in this repository: MIT (see `LICENSE`).
- Map data: © OpenStreetMap contributors, ODbL (`output/pune-chronicle/geo/basemap.json`); landmark coordinates
  and years from Wikidata (CC0).
- Fact excerpts: short quotations (≤30 words) from Encyclopaedia Britannica and Wikipedia (CC BY-SA), each with
  its source URL in the claim files; sources for the film are listed in `final/fact_sources.txt`.
- Narration and music: generated with MiniMax Speech 2.8 HD and MiniMax Music 2.6 via SandBase.
- Historic extents in the film are approximations and are labelled "AI illustration" on screen.

## Earlier pipeline (Oct 25–28)

Infrastructure pipeline for the **AI City Remix** documentary generation challenge. All runtime creative and factual decisions—historical research, factual claims, multi-scene screenplay, scene HTML code generation, and visual frame reviews—originate exclusively from **MiniMax M3.1 Flash** via the SandBase API.

## Core Architecture & Rules

1. **Infrastructure Only**:
   - The Python and JavaScript code provides the execution harness, browser recording, video assembly, and audit logging.
   - **Zero Hand-Editing**: Generated content (HTML, scripts, claims, reviews) is never hand-edited. If an issue is discovered, prompts or harness code are tuned and rerun.
2. **Model & Endpoint**:
   - Provider: [SandBase](https://www.sandbase.ai)
   - Endpoint: `https://api.sandbase.ai/v1/chat/completions`
   - Model ID: `minimax/minimax-m3.1-flash`
   - Authentication: Read from `SANDBASE_API_KEY` (env or `.env` file).
3. **Reasoning & Token Budgets**:
   - `reasoning_effort`: Set **explicitly** on every call (`low`, `medium`, `high`, `xhigh`, `max`).
   - `max_tokens`: Configured to `128000` for scene HTML generation to accommodate thinking tokens and full-fidelity Three.js code.
4. **Tool Turns & Reasoning Trace**:
   - The full assistant message (including `reasoning_content` and `tool_calls`) is preserved verbatim across tool turns in conversation history.
5. **Audit Logging**:
   - Every model call (tokens, reasoning length, duration, status, usage) and every manual intervention is logged as a JSON line to `runs.jsonl`.
6. **Headless 1080p Recording**:
   - Powered by `scripts/record.mjs` (from `sandbase-lab/awesome-minimax-m3-1-flash`), driving headless Chromium with SwiftShader WebGL and ffmpeg to export 1920x1080 H.264 MP4 videos.

## Project Structure

```
AI City Remix/
├── director.py           # Director agent orchestrating the tool loop with MiniMax M3.1 Flash
├── sandbase_client.py    # SandBase API client, reasoning preservation, and runs.jsonl logging
├── tools.py              # Tool schemas and execution logic (claims, script, HTML, recording, review)
├── smoke_test.py         # End-to-end smoke test verifying client constraints, recording, and logging
├── scripts/
│   └── record.mjs        # Playwright headless browser recorder exporting 1080p MP4
├── output/
│   ├── scenes/           # Generated HTML scenes (Three.js/Canvas/WebGPU)
│   ├── videos/           # Recorded 1080p MP4 scene videos
│   └── frames/           # Extracted review frames (JPEGs)
├── package.json          # Playwright dependency definition
├── runs.jsonl            # Audit log tracking all model calls and interventions
└── .env.example          # Environment variable template
```

## Quick Start

### 1. Set your API Key

```bash
export SANDBASE_API_KEY="sk-your-sandbase-api-key"
# Or create a .env file:
# echo "SANDBASE_API_KEY=sk-your-sandbase-api-key" > .env
```

### 2. Run the Smoke Test

Verifies the constraints, calls MiniMax M3.1 Flash for scene HTML (`max_tokens: 128000`), records a 1920x1080 test scene, extracts a frame, and logs all events to `runs.jsonl`:

```bash
python3 smoke_test.py
```

### 3. Run the Director Agent

Orchestrates the complete city documentary pipeline:

```bash
# Live run with MiniMax M3.1 Flash:
python3 director.py --city "Mumbai" --reasoning-effort high

# With custom visual style:
python3 director.py --city "Tokyo" --style "Neon cyberpunk with historical Edo transitions" --reasoning-effort high

# Offline simulation mode (when API key is not yet exported):
python3 director.py --city "Mumbai" --mock
```

### 4. Direct Scene Recording

Record any generated HTML file directly using `scripts/record.mjs`:

```bash
node scripts/record.mjs output/scenes/test_scene.html output/videos/test_scene.mp4 10 1920 1080
```
