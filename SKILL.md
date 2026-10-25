---
name: city-remix
description: AI City Remix documentary pipeline powered by MiniMax M3.1 Flash via SandBase API.
---

# City Remix Pipeline

End-to-end documentary film generation for real cities, narrated in the first person by the city and directed by **MiniMax M3.1 Flash** via the SandBase API.

## When to Use

Use this skill to research, fact-check, script, choreograph, render, and assemble a 60–180 second 1080p documentary film for any real city on Earth.

## Setup

1. Configure environment variables in `.env`:
   ```bash
   SANDBASE_API_KEY=sk-...
   ```
2. Install dependencies:
   ```bash
   npm install
   npx playwright install chromium
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

## The One Command

To run the complete pipeline for a city (e.g. Pune):

```bash
python3 run.py --city "Pune"
```

### Options

- Run a specific stage:
  ```bash
  python3 run.py --city "Pune" --stage research
  python3 run.py --city "Pune" --stage verify
  python3 run.py --city "Pune" --stage script
  python3 run.py --city "Pune" --stage scenes --workers 4
  python3 run.py --city "Pune" --stage assemble
  python3 run.py --city "Pune" --stage check
  ```
- Force rerun of an existing stage:
  ```bash
  python3 run.py --city "Pune" --stage script --force script
  ```

## Outputs

All artifacts are persisted in `output/<city>/`:
- `claims.raw.json`: Collected raw claims with verbatim source quotes.
- `claims.json`: Verified factual claims (no single-source claims).
- `research-report.json`: Fact-checking ledger with publisher counts and audit statistics.
- `map/svg_paths.json`: Local municipal boundaries, rivers, and landmark paths projected to 1920x1080.
- `script.json`: Screenplay citing verified claim IDs for every factual assertion.
- `audio/*.wav` & `audio/timing.json`: Narration audio and subtitle cue timings.
- `scenes/*.html`: Standalone, self-contained HTML scene animation files.
- `video/*.mp4`: 1080p scene video recordings.
- `review/*.json`: Multimodal vision inspection reports.
- `final/<city>.mp4`: Final assembled documentary (1080p, H.264/AAC, -16 LUFS).
- `final/<city>.srt`: Synchronized subtitles.
- `final/check.json`: Contest constraint audit report.
- `runs.jsonl`: Complete audit log of every model call and manual intervention.
