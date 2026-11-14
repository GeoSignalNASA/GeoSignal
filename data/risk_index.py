"""
Combine burn severity + slope + soil moisture into a per-microbasin risk
score, then attach whatever sits downstream (towns, reservoirs, intakes)
so each basin says who it threatens.

Inputs this expects on disk:
  data/out/burn_severity.tif   <- compute_change.py (band 1 = HV diff dB, band 2 = burned mask)
  data/raw/slope.tif           <- compute_slope.py, from Copernicus DEM
  data/raw/soil_moisture.tif   <- convert_sme2.py, from NISAR SME2
  data/raw/basins.geojson      <- delineate_basins.py, from the same DEM
  data/raw/assets.geojson      <- OSM towns + reservoirs/intakes, point layer (still missing)

All three rasters must share the same grid (same CRS, transform, shape).
If they don't, reproject/resample with rasterio.warp.reproject before
running this -- it does not do that for you.

Severity uses the burned MASK (band 2), not the raw dB diff (band 1).
Tested both on the real Calvos de Randin data: using mean dB diff per
basin buries the fire's signal under the ~80% of any basin that didn't
burn, so the basin containing the real fire ranked 18th of 26 by risk.
Burned-area-fraction is also what the actual post-fire debris-flow
literature uses, not a raw backscatter average, so this isn't just a
hack to make the number look right.
"""

import json

import geopandas as gpd
import numpy as np
import rasterio
from rasterstats import zonal_stats

SEVERITY_TIF = "data/out/burn_severity.tif"
SLOPE_TIF = "data/raw/slope.tif"
SOIL_MOISTURE_TIF = "data/raw/soil_moisture.tif"
BASINS_GEOJSON = "data/raw/basins.geojson"
ASSETS_GEOJSON = "data/raw/assets.geojson"
OUT_GEOJSON = "web/data/basins_risk.geojson"

# Tested additive (severity + slope + dryness) on real data: burned-area
# fraction tops out around 1-2% even for the basin with the actual fire in
# it, so it's numerically swamped by slope/dryness (0-1 range) in a sum.
# Multiplicative instead: risk only exists where something burned, so
# burned_frac GATES the terrain term rather than competing with it.
WEIGHTS = {"slope": 0.6, "dryness": 0.4}


def normalize(arr):
    valid = arr[np.isfinite(arr)]
    if valid.size == 0:
        return np.zeros_like(arr)
    lo, hi = np.nanpercentile(valid, [2, 98])
    return np.clip((arr - lo) / (hi - lo + 1e-9), 0, 1)


def build_risk_raster():
    with rasterio.open(SEVERITY_TIF) as src:
        burned_mask = src.read(2)
        profile = src.profile
    with rasterio.open(SLOPE_TIF) as src:
        slope = src.read(1)
    with rasterio.open(SOIL_MOISTURE_TIF) as src:
        soil_moisture = src.read(1)

    if not (burned_mask.shape == slope.shape == soil_moisture.shape):
        raise ValueError(
            "severity/slope/soil_moisture rasters are not on the same "
            "grid -- resample them to match before computing risk."
        )

    slope_norm = normalize(slope)
    dryness_norm = normalize(-soil_moisture)
    terrain_term = WEIGHTS["slope"] * slope_norm + WEIGHTS["dryness"] * dryness_norm

    # burned_mask (0/1) gates the terrain term: no burn, no elevated
    # post-fire risk, regardless of how steep or dry the ground is.
    risk = burned_mask * terrain_term

    profile.update(count=1, dtype="float32")
    with rasterio.open("data/out/risk_index.tif", "w", **profile) as dst:
        dst.write(risk.astype("float32"), 1)

    return "data/out/risk_index.tif"


def summarize_by_basin(risk_tif):
    basins = gpd.read_file(BASINS_GEOJSON)
    assets = gpd.read_file(ASSETS_GEOJSON)

    with rasterio.open(risk_tif) as src:
        raster_crs = src.crs
    basins_proj = basins.to_crs(raster_crs) if basins.crs != raster_crs else basins

    stats = zonal_stats(basins_proj, risk_tif, stats=["mean", "max"], nodata=np.nan)
    basins["risk_mean"] = [s["mean"] for s in stats]
    basins["risk_max"] = [s["max"] for s in stats]

    if assets.crs != basins.crs:
        assets = assets.to_crs(basins.crs)

    joined = gpd.sjoin(assets, basins[["geometry"]], how="inner", predicate="within")
    downstream = {}
    for basin_idx, group in joined.groupby("index_right"):
        downstream[basin_idx] = [
            {"name": row.get("name", "unnamed"), "type": row.get("type", "unknown")}
            for _, row in group.iterrows()
        ]

    basins["downstream_assets"] = [
        json.dumps(downstream.get(i, [])) for i in basins.index
    ]
    return basins


if __name__ == "__main__":
    risk_tif = build_risk_raster()
    basins = summarize_by_basin(risk_tif)
    basins.to_file(OUT_GEOJSON, driver="GeoJSON")
    print(f"wrote {OUT_GEOJSON} ({len(basins)} basins)")
