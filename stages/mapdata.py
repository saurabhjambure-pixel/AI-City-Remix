"""
stages/mapdata.py
Stage 3: Mapdata (code only)
Fetches and projects local city geography (rivers, municipal landmarks) to 1920x1080 SVG paths.
Enforces: Never fetch or draw national or state borders.
"""

from pathlib import Path
from tools.osm import build_pune_svg_paths


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

    print(f"[Stage 3: Mapdata] Generating SVG map paths for {city}...")
    build_pune_svg_paths(map_dir)

    if not svg_paths_file.is_file():
        raise RuntimeError(f"Stage 3 failed: {svg_paths_file} not generated.")

    print(f"[Stage 3: Mapdata] Saved SVG paths to {svg_paths_file}")
    return svg_paths_file
