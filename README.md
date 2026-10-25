# AI City Remix Pipeline

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
