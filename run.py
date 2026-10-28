#!/usr/bin/env python3
"""
run.py
Main stage runner for the AI City Remix documentary pipeline.
Enforces all rules from MASTER_PLAN.md:
- M3.1 decides; you build.
- Resumable: writes artifacts to output/<city>/ and skips completed stages unless --force is passed.
- No mocks in real runs: stops and reports if SANDBASE_API_KEY is missing.
- Contest constraints code-enforced.
"""

import sys
import argparse
from pathlib import Path

from sandbase_client import SandBaseClient
from stages.research import run_research_stage
from stages.verify import run_verify_stage
from stages.mapdata import run_mapdata_stage
from stages.script import run_script_stage
from stages.tts import run_tts_stage
from stages.scenes import run_scenes_stage
from stages.record import run_record_stage
from stages.review import run_review_stage
from stages.endcard import run_endcard_stage
from stages.assemble import run_assemble_stage
from stages.check import run_check_stage


STAGES = [
    "research",
    "verify",
    "mapdata",
    "script",
    "tts",
    "scenes",
    "record",
    "review",
    "endcard",
    "assemble",
    "check",
]


def main():
    parser = argparse.ArgumentParser(description="AI City Remix Pipeline Runner")
    parser.add_argument("--city", type=str, default="Pune", help="Target city name (e.g. Pune)")
    parser.add_argument("--stage", type=str, default="all", choices=STAGES + ["all"], help="Stage to run (or 'all')")
    parser.add_argument("--force", type=str, default=None, help="Force rerun of specific stage (or 'all')")
    parser.add_argument("--workers", type=int, default=4, help="Parallel workers for scene generation")
    parser.add_argument("--extend", action="store_true", help="research: keep verified claims and add new ones")
    parser.add_argument("--priority", type=str, default="", help="research --extend: comma-separated clusters to prioritise")

    args = parser.parse_args()

    city = args.city.strip()
    city_slug = city.lower().replace(" ", "_")
    output_dir = Path("output") / city_slug
    output_dir.mkdir(parents=True, exist_ok=True)

    client = SandBaseClient()

    print(f"\n========================================================")
    print(f"🎬 AI CITY REMIX PIPELINE — {city.upper()}")
    print(f"   Target Stage: {args.stage}")
    print(f"   Output Directory: {output_dir.resolve()}")
    print(f"   Workers: {args.workers}")
    print(f"========================================================\n")

    def should_force(stage_name: str) -> bool:
        return args.force in ("all", stage_name)

    target = args.stage
    stages_to_run = STAGES if target == "all" else [target]

    for stg in stages_to_run:
        print(f"\n▶️  [Stage: {stg.upper()}] Starting...")
        force_flag = should_force(stg)

        if stg == "research":
            run_research_stage(city, output_dir, client, force=force_flag, extend=args.extend,
                               priority_clusters=[c for c in args.priority.split(",") if c])
        elif stg == "verify":
            run_verify_stage(city, output_dir, client, force=force_flag)
        elif stg == "mapdata":
            run_mapdata_stage(city, output_dir, force=force_flag)
        elif stg == "script":
            run_script_stage(city, output_dir, client, force=force_flag)
        elif stg == "tts":
            run_tts_stage(city, output_dir, force=force_flag)
        elif stg == "scenes":
            run_scenes_stage(city, output_dir, client, workers=args.workers, force=force_flag)
        elif stg == "record":
            run_record_stage(city, output_dir, force=force_flag)
        elif stg == "review":
            run_review_stage(city, output_dir, client, force=force_flag)
        elif stg == "endcard":
            run_endcard_stage(city, output_dir, client, force=force_flag)
        elif stg == "assemble":
            run_assemble_stage(city, output_dir, force=force_flag)
        elif stg == "check":
            passed, report_path = run_check_stage(city, output_dir)
            if not passed:
                print(f"[Warning] Stage 11 check reported failures. See {report_path}", file=sys.stderr)
                sys.exit(1)

    print(f"\n🎉 [PIPELINE SUCCESS] All requested stages completed for {city}.")


if __name__ == "__main__":
    main()
