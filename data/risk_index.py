"""
Combine burn severity + slope + soil moisture into a per-microbasin risk
score, then attach whatever sits downstream (towns, reservoirs, intakes)
so each basin says who it threatens.

Inputs this expects on disk (none of these are fetched by this script --
see README for where to get each one):
  data/out/burn_severity.tif   <- compute_change.py (band 1 = HV diff dB)
  data/raw/slope.tif           <- derived from IGN MDT / Copernicus DEM
  data/raw/soil_moisture.tif   <- NISAR SME2, resampled to the same grid
  data/raw/basins.geojson      <- microbasin polygons (WhiteboxTools / pysheds)
  data/raw/assets.geojson      <- OSM towns + reservoirs/intakes, point layer

All three rasters must share the same grid (same CRS, transform, shape).
If they don't, reproject/resample with rasterio.warp.reproject before
running this -- it does not do that for you.
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

# severity x slope x dryness -- tune these once you see real numbers.
WEIGHTS = {"severity": 0.5, "slope": 0.3, "dryness": 0.2}


def normalize(arr):
    valid = arr[np.isfinite(arr)]
    if valid.size == 0:
        return np.zeros_like(arr)
    lo, hi = np.nanpercentile(valid, [2, 98])
    return np.clip((arr - lo) / (hi - lo + 1e-9), 0, 1)


def build_risk_raster():
    with rasterio.open(SEVERITY_TIF) as src:
        severity_db = src.read(1)
        profile = src.profile
    with rasterio.open(SLOPE_TIF) as src:
        slope = src.read(1)
    with rasterio.open(SOIL_MOISTURE_TIF) as src:
        soil_moisture = src.read(1)

    if not (severity_db.shape == slope.shape == soil_moisture.shape):
        raise ValueError(
            "severity/slope/soil_moisture rasters are not on the same "
            "grid -- resample them to match before computing risk."
        )

    # bigger HV drop = more severe burn, so flip sign before normalizing
    severity_norm = normalize(-severity_db)
    slope_norm = normalize(slope)
    dryness_norm = normalize(-soil_moisture)

    risk = (
        WEIGHTS["severity"] * severity_norm
        + WEIGHTS["slope"] * slope_norm
        + WEIGHTS["dryness"] * dryness_norm
    )

    profile.update(count=1, dtype="float32")
    with rasterio.open("data/out/risk_index.tif", "w", **profile) as dst:
        dst.write(risk.astype("float32"), 1)

    return "data/out/risk_index.tif"


def summarize_by_basin(risk_tif):
    basins = gpd.read_file(BASINS_GEOJSON)
    assets = gpd.read_file(ASSETS_GEOJSON)

    stats = zonal_stats(basins, risk_tif, stats=["mean", "max"], nodata=np.nan)
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
