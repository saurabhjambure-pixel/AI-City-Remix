"""
tools/osm.py
OpenStreetMap data for the map layers: a city-level boundary, named rivers and named places.
Projects each "view" (core / city / region) to its own 1920x1080 frame, simplifies in screen
space, and places labels so they do not overlap.

Source: OSM via Nominatim (https://nominatim.openstreetmap.org: /search and /lookup with
polygon_geojson). Overpass (MASTER_PLAN §3 stage 3) was unreachable from this network on
2026-10-28 (connect timeouts on overpass-api.de, kumi, private.coffee; mail.ru 504), while
Nominatim returned the same OSM objects with ids and full geometry.

Rules: no hand-typed coordinates or fallback geometry (a failed lookup raises, a missing place
is omitted and logged); never fetch national or state borders (admin_level < 6 is refused).
"""

import hashlib
import json
import math
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from shapely.geometry import LineString, MultiLineString, Point, Polygon, MultiPolygon, box, shape
from shapely.ops import linemerge, nearest_points, transform, unary_union

NOMINATIM = "https://nominatim.openstreetmap.org"
USER_AGENT = "CityRemixMap/1.0 (open-source documentary pipeline; https://github.com/sandbase-lab/awesome-minimax-m3-1-flash)"
MIN_ADMIN_LEVEL = 6  # 2 = country, 4 = state, 5 = district: never fetched
W, H = 1920, 1080
PADDING = 110
EDGE_MARGIN = 40
LABEL_FONT = 34
MAX_TOTAL_BYTES = 40_000

_last_call = [0.0]


class OSMError(RuntimeError):
    pass


def nominatim(endpoint: str, params: Dict[str, Any], cache_dir: Path) -> Any:
    """GET a Nominatim endpoint with disk cache, 1 req/s, 3 tries with backoff; raises on failure."""
    params = {**params, "format": "jsonv2"}
    key = hashlib.sha1(json.dumps([endpoint, params], sort_keys=True).encode()).hexdigest()
    cache_file = cache_dir / f"{key}.json"
    if cache_file.is_file():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    last_err = None
    for attempt, backoff in enumerate([0, 5, 20]):
        time.sleep(max(backoff, 1.1 - (time.time() - _last_call[0]), 0))
        _last_call[0] = time.time()
        try:
            resp = requests.get(f"{NOMINATIM}/{endpoint}", params=params, headers={"User-Agent": USER_AGENT}, timeout=90)
            if resp.status_code == 200:
                data = resp.json()
                cache_dir.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(json.dumps({"request": [endpoint, params], "response": data}), encoding="utf-8")
                return {"request": [endpoint, params], "response": data}
            last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
        except requests.RequestException as e:
            last_err = str(e)
    raise OSMError(f"Nominatim {endpoint} {params.get('q') or params.get('osm_ids')} failed after 3 tries: {last_err}")


def viewbox(bbox: List[float]) -> str:
    s, w, n, e = bbox
    return f"{w},{n},{e},{s}"


def find_boundary(spec: Dict[str, Any], cfg: Dict[str, Any], cache_dir: Path) -> Optional[Dict[str, Any]]:
    data = nominatim("search", {"q": spec["query"], "polygon_geojson": 1, "extratags": 1, "limit": 10,
                                "viewbox": viewbox(cfg["search_bbox"]), "bounded": 1}, cache_dir)["response"]
    for e in data:
        level = int((e.get("extratags") or {}).get("admin_level") or 0)
        if e.get("category") == "boundary" and e.get("osm_type") == "relation" and level >= MIN_ADMIN_LEVEL \
                and re.search(spec["name_regex"], e.get("name") or ""):
            return {"geom": shape(e["geojson"]), "osm": f"relation/{e['osm_id']}", "osm_name": e["name"], "admin_level": level}
    return None


def find_river(spec: Dict[str, Any], cfg: Dict[str, Any], cache_dir: Path) -> Optional[Dict[str, Any]]:
    # bounded=0: a river's centroid can lie outside the city box (the Mula-Mutha runs east to the Bhima)
    data = nominatim("search", {"q": spec["query"], "polygon_geojson": 1, "limit": 10,
                                "viewbox": viewbox(cfg["search_bbox"]), "bounded": 0}, cache_dir)["response"]
    for e in data:
        if e.get("category") == "waterway" and e.get("type") == "river" and (e.get("name") or "") == spec["osm_name"]:
            return {"geom": shape(e["geojson"]), "osm": f"{e['osm_type']}/{e['osm_id']}", "osm_name": e["name"]}
    return None


def find_place(spec: Dict[str, Any], cfg: Dict[str, Any], cache_dir: Path) -> Optional[Dict[str, Any]]:
    for name in spec["names"]:
        data = nominatim("search", {"q": name, "limit": 5, "viewbox": viewbox(cfg["search_bbox"]), "bounded": 1},
                         cache_dir)["response"]
        for e in data:
            if (e.get("name") or "").strip().lower() not in {n.lower() for n in spec["names"]}:
                continue  # exact names only: "Magarpatta" must not match "Magarpatta City School Ground"
            return {"geom": Point(float(e["lon"]), float(e["lat"])), "osm": f"{e['osm_type']}/{e['osm_id']}",
                    "osm_name": e.get("name") or e.get("display_name", "").split(",")[0], "query": name}
    return None


class Projector:
    """Equirectangular projection of a lon/lat bbox into the 1920x1080 frame (aspect-correct)."""

    def __init__(self, bounds: Tuple[float, float, float, float]):
        min_lon, min_lat, max_lon, max_lat = bounds
        self.lon0, self.lat0 = (min_lon + max_lon) / 2, (min_lat + max_lat) / 2
        self.k = math.cos(math.radians(self.lat0))
        span_x = max((max_lon - min_lon) * self.k, 1e-6)
        span_y = max(max_lat - min_lat, 1e-6)
        self.scale = min((W - 2 * PADDING) / span_x, (H - 2 * PADDING) / span_y)

    def xy(self, lon: float, lat: float, z: Any = None) -> Tuple[float, float]:
        return W / 2 + (lon - self.lon0) * self.k * self.scale, H / 2 - (lat - self.lat0) * self.scale

    def lonlat_bounds(self) -> Tuple[float, float, float, float]:
        half_w, half_h = W / 2 / (self.k * self.scale), H / 2 / self.scale
        return self.lon0 - half_w, self.lat0 - half_h, self.lon0 + half_w, self.lat0 + half_h

    def px_per_km(self) -> float:
        return self.scale / 111.32


def to_d(geom: Any) -> str:
    """SVG path d for a projected geometry (1 decimal)."""
    if geom.is_empty:
        return ""
    if isinstance(geom, (MultiLineString, MultiPolygon)) or geom.geom_type == "GeometryCollection":
        return " ".join(filter(None, (to_d(g) for g in geom.geoms)))
    if isinstance(geom, Polygon):
        return to_d(LineString(geom.exterior.coords)) + " Z"
    if isinstance(geom, LineString):
        pts = [f"{x:.1f} {y:.1f}" for x, y in geom.coords]
        return "M " + " L ".join(pts)
    return ""


def text_box(x: float, y: float, text: str, anchor: str) -> Tuple[float, float, float, float]:
    w, h = 0.56 * LABEL_FONT * len(text), LABEL_FONT * 1.2
    left = x if anchor == "start" else x - w if anchor == "end" else x - w / 2
    return left, y - h * 0.8, left + w, y + h * 0.2


def overlaps(a: Tuple[float, ...], b: Tuple[float, ...], pad: float = 6) -> bool:
    return not (a[2] + pad < b[0] or b[2] + pad < a[0] or a[3] + pad < b[1] or b[3] + pad < a[1])


def inside(bx: Tuple[float, ...]) -> bool:
    return bx[0] >= EDGE_MARGIN and bx[1] >= EDGE_MARGIN and bx[2] <= W - EDGE_MARGIN and bx[3] <= H - EDGE_MARGIN


def build_view(name: str, spec: Dict[str, Any], features: Dict[str, Dict[str, Any]], tolerance: float) -> Tuple[Dict[str, Any], List[str]]:
    """Project, clip, simplify and label one view."""
    log: List[str] = []
    if "center" in spec:
        c = features[spec["center"]]["geom"]
        dlat = spec["radius_km"] / 111.32
        dlon = dlat / math.cos(math.radians(c.y))
        fit = (c.x - dlon, c.y - dlat, c.x + dlon, c.y + dlat)
    else:
        fit = unary_union([features[f]["geom"] for f in spec["fit"] if f in features]).bounds
    proj = Projector(fit)
    frame = box(*proj.lonlat_bounds())
    screen = box(0, 0, W, H)

    layers: Dict[str, Any] = {}
    taken: List[Tuple[float, ...]] = []
    show = [fid for fid in spec["show"] if fid in features]
    for fid in spec["show"]:
        if fid not in features:
            log.append(f"{name}: {fid} not available (not found in OSM)")
    # markers first, so labels avoid them
    for fid in show:
        f = features[fid]
        if f["kind"] == "point" and frame.contains(f["geom"]):
            x, y = proj.xy(f["geom"].x, f["geom"].y)
            taken.append((x - 12, y - 12, x + 12, y + 12))

    def screen_geom(f: Dict[str, Any]) -> Any:
        g = f["geom"]
        if f["kind"] == "boundary" and not frame.contains(g):
            g = g.boundary  # partly off-frame: draw the outline only, never the frame edge
        return transform(proj.xy, g.intersection(frame)).simplify(tolerance).intersection(screen)

    # lines that labels should avoid where possible
    strokes = unary_union([screen_geom(features[fid]).boundary if features[fid]["kind"] == "boundary"
                           and screen_geom(features[fid]).geom_type in ("Polygon", "MultiPolygon")
                           else screen_geom(features[fid])
                           for fid in show if features[fid]["kind"] != "point"] or [Point(-1e6, -1e6)])

    def fits(bx: Tuple[float, ...], avoid_lines: bool) -> bool:
        return inside(bx) and not any(overlaps(bx, t) for t in taken) and \
            not (avoid_lines and strokes.intersects(box(bx[0] - 4, bx[1] - 4, bx[2] + 4, bx[3] + 4)))

    # labels in priority order: places (in show order), then rivers, then the boundary
    for kind in ("point", "river", "boundary"):
        for fid in show:
            f = features[fid]
            if f["kind"] != kind:
                continue
            g = f["geom"]
            if not g.intersects(frame):
                continue
            sg = screen_geom(f)
            if sg.is_empty:
                continue
            entry: Dict[str, Any] = {"type": "point" if kind == "point" else "path", "label": f["label"], "osm": f["osm"]}
            if kind == "point":
                entry["x"], entry["y"] = round(sg.x, 1), round(sg.y, 1)
                candidates = [(sg.x + dx, sg.y + dy, a) for dx, dy, a in
                              ((20, 12, "start"), (-20, 12, "end"), (0, -24, "middle"), (0, 50, "middle"),
                               (18, -18, "start"), (-18, -18, "end"), (18, 44, "start"), (-18, 44, "end"),
                               (18, -52, "start"), (-18, -52, "end"), (18, 80, "start"), (-18, 80, "end"))]
            else:
                entry["d"] = to_d(sg)
                line = sg.boundary if sg.geom_type in ("Polygon", "MultiPolygon") else sg
                line = linemerge(line) if line.geom_type == "MultiLineString" else line
                longest = max(getattr(line, "geoms", [line]), key=lambda l: l.length)
                pts = [longest.interpolate(t, normalized=True) for t in (0.5, 0.35, 0.65, 0.2, 0.8, 0.1, 0.9)]
                candidates = [(p.x + dx, p.y + dy, a) for p in pts for dx, dy, a in
                              ((0, -22, "middle"), (0, 46, "middle"), (16, 12, "start"), (-16, 12, "end"))]
            # near spots before far ones; within each, clear of lines first, then clear of labels only
            near, far = candidates[:4], candidates[4:]
            choice = next(((lx, ly, a) for group in (near, far) for avoid in (True, False)
                           for lx, ly, a in group if fits(text_box(lx, ly, f["label"], a), avoid)), None)
            if choice:
                lx, ly, anchor = choice
                taken.append(text_box(lx, ly, f["label"], anchor))
                entry.update({"label_x": round(lx, 1), "label_y": round(ly, 1), "label_anchor": anchor})
            else:
                if kind == "point":
                    log.append(f"{name}: omitted {fid} (no room for its label)")
                    continue
                entry["label_x"] = None
                log.append(f"{name}: {fid} drawn without a label (no room)")
            layers[fid] = entry
    layers = {k: layers[k] for k in sorted(layers, key=lambda k: layers[k]["type"] != "path")}
    view = {
        "viewBox": f"0 0 {W} {H}",
        "lonlat_bounds": [round(v, 5) for v in proj.lonlat_bounds()],
        "px_per_km": round(proj.px_per_km(), 2),
        "label_font_px": LABEL_FONT,
        "layers": layers,
    }
    return view, log


def build_city_map(cfg: Dict[str, Any], output_map_dir: Path) -> Dict[str, Any]:
    """Fetch OSM features for a city config and write svg_paths.json + preview.html."""
    cache_dir = output_map_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    features: Dict[str, Dict[str, Any]] = {}
    log: List[str] = []

    for spec in cfg["boundaries"]:
        b = find_boundary(spec, cfg, cache_dir)
        if b:
            features[spec["id"]] = {"kind": "boundary", "label": spec["label"], **b}
            log.append(f"boundary {spec['id']}: {b['osm']} '{b['osm_name']}' admin_level={b['admin_level']}")
        else:
            log.append(f"boundary {spec['id']}: not found in OSM (query '{spec['query']}'); omitted")
    for spec in cfg["rivers"]:
        r = find_river(spec, cfg, cache_dir)
        if not r:
            raise OSMError(f"River '{spec['osm_name']}' not found in OSM; refusing to invent it.")
        features[spec["id"]] = {"kind": "river", "label": spec["label"], **r}
        log.append(f"river {spec['id']}: {r['osm']} '{r['osm_name']}'")

    if cfg.get("confluence"):
        a, b = (features[i]["geom"] for i in cfg["confluence"]["between"])
        pa, pb = nearest_points(a, b)
        gap_m = pa.distance(pb) * 111_320
        if gap_m > 300:
            raise OSMError(f"Rivers {cfg['confluence']['between']} do not meet in OSM (gap {gap_m:.0f} m).")
        features[cfg["confluence"]["id"]] = {"kind": "point", "label": cfg["confluence"]["label"],
                                             "geom": Point((pa.x + pb.x) / 2, (pa.y + pb.y) / 2),
                                             "osm": f"derived: nearest point of {features[cfg['confluence']['between'][0]]['osm']} and {features[cfg['confluence']['between'][1]]['osm']}"}
        log.append(f"confluence: derived from river geometries (gap {gap_m:.0f} m)")

    for spec in cfg["places"]:
        p = find_place(spec, cfg, cache_dir)
        if p:
            features[spec["id"]] = {"kind": "point", "label": spec["label"], **p}
            log.append(f"place {spec['id']}: {p['osm']} '{p['osm_name']}'")
        else:
            log.append(f"place {spec['id']}: NOT FOUND in OSM ({spec['names']}); omitted")

    tolerance, views = 1.0, {}
    for _ in range(6):
        views, view_logs = {}, []
        for vname, vspec in cfg["views"].items():
            views[vname], vl = build_view(vname, vspec, features, tolerance)
            view_logs += vl
        size = len(json.dumps(views))
        if size <= MAX_TOTAL_BYTES:
            break
        tolerance *= 1.6
    else:
        raise OSMError(f"svg_paths.json still {size} bytes after simplification")
    log += view_logs + [f"simplify tolerance {tolerance:.2f}px, total {size} bytes"]

    out = {"city": cfg["city"], "source": "OpenStreetMap contributors (ODbL), via Nominatim",
           "views": views, "log": log}
    (output_map_dir / "svg_paths.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    (output_map_dir / "preview.html").write_text(render_preview(out), encoding="utf-8")
    return out


def render_preview(data: Dict[str, Any]) -> str:
    """Static preview of every view, drawn only from svg_paths.json."""
    sections = []
    for vname, v in data["views"].items():
        els = []
        for lid, l in v["layers"].items():
            if l["type"] == "path":
                cls = "boundary" if lid.startswith("boundary") else "river"
                els.append(f'<path class="{cls}" d="{l["d"]}"/>')
        for lid, l in v["layers"].items():
            if l["type"] == "point":
                els.append(f'<circle class="dot" cx="{l["x"]}" cy="{l["y"]}" r="9"/>')
        for lid, l in v["layers"].items():
            if l.get("label_x") is not None:
                cls = "rlabel" if lid.startswith("river") else "label"
                els.append(f'<text class="{cls}" x="{l["label_x"]}" y="{l["label_y"]}" text-anchor="{l["label_anchor"]}">{l["label"]}</text>')
        sections.append(f'''<section id="{vname}"><h2>{vname} &middot; {v["px_per_km"]} px/km</h2>
<svg viewBox="{v["viewBox"]}" xmlns="http://www.w3.org/2000/svg"><rect width="1920" height="1080" fill="#0f1115"/>{"".join(els)}</svg></section>''')
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{data["city"]} map views</title>
<style>
body{{margin:0;background:#0f1115;color:#f3ead8;font-family:-apple-system,Segoe UI,Roboto,sans-serif}}
section{{padding:16px 24px}} h2{{margin:0 0 8px;color:#f2a33a;font-size:20px;letter-spacing:1px;text-transform:uppercase}}
svg{{width:100%;height:auto;display:block;border:1px solid #2a2f3a}}
.river{{fill:none;stroke:#5fa8d3;stroke-width:6;stroke-linecap:round;stroke-linejoin:round}}
.boundary{{fill:rgba(242,163,58,.08);stroke:#f2a33a;stroke-width:4;stroke-dasharray:14 10}}
.dot{{fill:#f2a33a;stroke:#0f1115;stroke-width:3}}
.label{{fill:#f3ead8;font-size:{LABEL_FONT}px;font-weight:600;paint-order:stroke;stroke:#0f1115;stroke-width:6}}
.rlabel{{fill:#5fa8d3;font-size:{LABEL_FONT}px;font-style:italic;font-weight:600;paint-order:stroke;stroke:#0f1115;stroke-width:6}}
footer{{padding:8px 24px 24px;color:#8a8f99;font-size:14px}}
</style></head><body>
{"".join(sections)}
<footer>Map data &copy; OpenStreetMap contributors (ODbL)</footer>
</body></html>
'''
