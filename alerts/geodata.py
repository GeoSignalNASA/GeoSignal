"""
Read the light web inputs (web/assets/data) the StoryMap already uses and
turn them into what an alert needs: burned area, basins, and for every
settlement how exposed it is to runoff coming off the burn scar.

Everything here is real pipeline output. The only hypothetical quantity in
an alert is the rain itself (and the runoff coefficient applied to it).
"""

import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass, field

from . import config


@dataclass
class Basin:
    basin_id: int
    rank: int
    risk_mean: float
    burned_ha: float
    burned_pct: float
    area_ha: float
    slope_mean_deg: float
    moisture_mean: float
    overlaps_fire: bool
    assets: list = field(default_factory=list)


@dataclass
class Place:
    name: str
    kind: str            # village | hamlet | reservoir
    lon: float
    lat: float
    basin_id: int | None
    exposure: str        # "direct" | "downstream" | "none"
    trace_dist_m: float  # distance to the nearest runoff trace


@dataclass
class Barrier:
    lon: float
    lat: float
    dist_from_fire_m: float
    slope_before_deg: float
    slope_after_deg: float
    contrib_area_ha: float
    relevant: bool


@dataclass
class Territory:
    fire_name: str
    burned_ha: float
    burned_date: str
    ignition_date: str
    centroid_lat: float
    centroid_lon: float
    max_contrib_area_m2: float
    basins: dict
    places: dict
    barriers: list
    stats: dict           # story_stats.json as the StoryMap reads it
    data_version: str     # changes when the study data is regenerated

    def find_place(self, name):
        return self.places.get(normalize(name))

    def basins_by_rank(self):
        return sorted(self.basins.values(), key=lambda b: b.rank)


def normalize(name):
    """Case- and accent-insensitive key, so "as meaus" matches "As Meaus"."""
    text = unicodedata.normalize("NFKD", name)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip().casefold()


def haversine_m(lon1, lat1, lon2, lat2):
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def parse_number_array(text):
    """rain_channels.geojson stores per-vertex arrays as numpy-printed strings."""
    return [float(tok) for tok in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", str(text))]


def _read(name, data_dir):
    with open(data_dir / name, encoding="utf-8") as fh:
        return json.load(fh)


def load_territory(data_dir=None):
    data_dir = data_dir or config.DATA_DIR
    stats = _read("story_stats.json", data_dir)
    basins_gj = _read("basins_risk.geojson", data_dir)
    assets_gj = _read("assets.geojson", data_dir)
    fire_gj = _read("fire_perimeter.geojson", data_dir)
    rain_gj = _read("rain_channels.geojson", data_dir)
    barriers_gj = _read("barrier_candidates.geojson", data_dir)

    # Same choice as the web simulator: the dry 25-Oct scene when present.
    if stats.get("severity_oct25", {}).get("burned_total_ha"):
        burned_ha, burned_date = stats["severity_oct25"]["burned_total_ha"], "2026-10-25"
    else:
        burned_ha, burned_date = stats["severity_smooth"]["burned_total_ha"], stats["meta"]["post_date"]

    basins = {}
    place_basin = {}
    for feat in basins_gj["features"]:
        p = feat["properties"]
        assets = [a["name"] for a in p.get("downstream_assets", [])]
        basins[p["basin_id"]] = Basin(
            basin_id=p["basin_id"], rank=p["rank"], risk_mean=p["risk_mean"],
            burned_ha=p["burned_ha"], burned_pct=p["burned_pct"], area_ha=p["area_ha"],
            slope_mean_deg=p["slope_mean_deg"], moisture_mean=p["moisture_mean"],
            overlaps_fire=bool(p["overlaps_fire"]), assets=assets,
        )
        for name in assets:
            place_basin[normalize(name)] = p["basin_id"]

    trace_points = []
    max_area = 0.0
    for feat in rain_gj["features"]:
        trace_points.extend(feat["geometry"]["coordinates"])
        areas = parse_number_array(feat["properties"].get("contrib_area_m2", ""))
        if areas:
            max_area = max(max_area, max(areas))

    places = {}
    for feat in assets_gj["features"]:
        p = feat["properties"]
        lon, lat = feat["geometry"]["coordinates"][:2]
        basin_id = place_basin.get(normalize(p["name"]))
        dist = min(haversine_m(lon, lat, x, y) for x, y in trace_points) if trace_points else math.inf
        if basin_id is not None and basins[basin_id].overlaps_fire:
            exposure = "direct"
        elif dist <= config.DOWNSTREAM_MAX_DIST_M:
            exposure = "downstream"
        else:
            exposure = "none"
        places[normalize(p["name"])] = Place(
            name=p["name"], kind=p.get("type", ""), lon=lon, lat=lat,
            basin_id=basin_id, exposure=exposure, trace_dist_m=dist,
        )

    ring = fire_gj["features"][0]["geometry"]["coordinates"][0]
    barriers = [
        Barrier(
            lon=f["properties"]["lon"], lat=f["properties"]["lat"],
            dist_from_fire_m=f["properties"]["dist_from_fire_m"],
            slope_before_deg=f["properties"]["slope_before_deg"],
            slope_after_deg=f["properties"]["slope_after_deg"],
            contrib_area_ha=f["properties"]["contrib_area_ha"],
            relevant=bool(f["properties"].get("relevant")),
        )
        for f in barriers_gj["features"]
    ]

    return Territory(
        fire_name=stats["meta"]["fire_name"],
        burned_ha=burned_ha,
        burned_date=burned_date,
        ignition_date=stats["meta"]["ignition_date"],
        centroid_lat=sum(pt[1] for pt in ring) / len(ring),
        centroid_lon=sum(pt[0] for pt in ring) / len(ring),
        max_contrib_area_m2=max_area,
        basins=basins,
        places=places,
        barriers=barriers,
        stats=stats,
        data_version=hashlib.sha1((data_dir / "story_stats.json").read_bytes()).hexdigest()[:12],
    )
