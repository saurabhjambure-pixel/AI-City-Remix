"""
stages/mapdata.py
Stage 3: Mapdata (code only)
Builds output/<city>/map/svg_paths.json (views core / city / region, each projected to 1920x1080)
and preview.html from OpenStreetMap, using cities/<city>.json for which features to look up.
Enforces: never fetch or draw national or state borders; no invented geometry.
"""

import json
from pathlib import Path

from tools.osm import build_city_map


def run_mapdata_stage(
    city: str,
    output_dir: Path,
    force: bool = False,
) -> Path:
    """Execute Stage 3: Mapdata."""
    map_dir = output_dir / "map"
    svg_paths_file = map_dir / "svg_paths.json"

    if svg_paths_file.is_file() and not force:
        print(f"[Stage 3: Mapdata] Reusing existing {svg_paths_file}")
        return svg_paths_file

    config_file = Path("cities") / f"{city.lower().replace(' ', '_')}.json"
    if not config_file.is_file():
        raise FileNotFoundError(f"Missing {config_file}: list the boundary, rivers, places and views to fetch from OSM.")
    cfg = json.loads(config_file.read_text(encoding="utf-8"))

    print(f"[Stage 3: Mapdata] Fetching OSM features for {city}...")
    data = build_city_map(cfg, map_dir)
    for line in data["log"]:
        print(f"  {line}")

    print(f"[Stage 3: Mapdata] Saved {svg_paths_file} and {map_dir / 'preview.html'}")
    return svg_paths_file
