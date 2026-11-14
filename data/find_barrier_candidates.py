"""
Candidate sites for check-dams/retention basins along the real drainage
channels traced from the fire perimeter (simulate_rain.py): points where
slope drops sharply (steep -> flatter), the classic geomorphological
signature of where sediment naturally starts depositing.

This is a terrain-analysis HINT, not an engineering design. Flagging a
point here means "worth a geotechnical look," not "build here."
"""

import sys

import geopandas as gpd
import numpy as np
import rasterio
from shapely.geometry import Point

from simulate_rain import DIRS, cell_size_m, seed_rowcols

LOOKAHEAD_CELLS = 10  # ~300m at 30m resolution
SMOOTH_WINDOW = 5  # ~150m
MIN_UPSTREAM_SLOPE_DEG = 12.0
MIN_CONTRIB_AREA_M2 = 50_000  # 5 ha -- must be along real flow, not a random hillside
DEDUPE_RADIUS_M = 200


def slope_degrees_native(dem, transform):
    lat_mid = rasterio.transform.xy(transform, dem.shape[0] // 2, dem.shape[1] // 2)[1]
    dx_m, dy_m = cell_size_m(transform, lat_mid)
    dzdy, dzdx = np.gradient(dem, dy_m, dx_m)
    return np.degrees(np.arctan(np.sqrt(dzdx**2 + dzdy**2)))


def moving_average(arr, window):
    if len(arr) < window:
        return arr
    kernel = np.ones(window) / window
    return np.convolve(arr, kernel, mode="same")


def trace_with_slope(pntr, accum, slope, transform, start_row, start_col, max_steps=4000):
    height, width = pntr.shape
    row, col = start_row, start_col
    path = []
    dist_m = 0.0
    for _ in range(max_steps):
        if row < 0 or row >= height or col < 0 or col >= width:
            break
        v = pntr[row, col]
        lon, lat = rasterio.transform.xy(transform, row, col)
        path.append(
            {
                "lon": lon,
                "lat": lat,
                "dist_m": dist_m,
                "contrib_area_m2": float(accum[row, col]) * np.prod(cell_size_m(transform, lat)),
                "slope_deg": float(slope[row, col]),
            }
        )
        if v not in DIRS:
            break
        dr, dc = DIRS[v]
        dx_m, dy_m = cell_size_m(transform, lat)
        step_m = dy_m if dc == 0 else (dx_m if dr == 0 else np.hypot(dx_m, dy_m))
        dist_m += step_m
        row, col = row + dr, col + dc
    return path


def find_candidates(filled_dem_tif, pointer_tif, accum_tif, perimeter_geojson, n_seeds=8):
    with rasterio.open(filled_dem_tif) as src:
        dem = src.read(1)
        transform = src.transform
    with rasterio.open(pointer_tif) as src:
        pntr = src.read(1)
    with rasterio.open(accum_tif) as src:
        accum = src.read(1)

    slope = slope_degrees_native(dem, transform)
    seeds = seed_rowcols(perimeter_geojson, transform, n_seeds)

    candidates = []
    for seed_id, (row, col) in enumerate(seeds):
        path = trace_with_slope(pntr, accum, slope, transform, row, col)
        if len(path) < LOOKAHEAD_CELLS + SMOOTH_WINDOW:
            continue
        slopes = np.array([p["slope_deg"] for p in path])
        smoothed = moving_average(slopes, SMOOTH_WINDOW)

        for i in range(len(path) - LOOKAHEAD_CELLS):
            before = smoothed[i]
            after = smoothed[i + LOOKAHEAD_CELLS]
            drop = before - after
            p = path[i]
            if (
                drop > 6.0
                and before > MIN_UPSTREAM_SLOPE_DEG
                and p["contrib_area_m2"] > MIN_CONTRIB_AREA_M2
            ):
                candidates.append(
                    {
                        "seed_id": seed_id,
                        "lon": p["lon"],
                        "lat": p["lat"],
                        "dist_from_fire_m": round(p["dist_m"], 0),
                        "slope_before_deg": round(float(before), 1),
                        "slope_after_deg": round(float(after), 1),
                        "slope_drop_deg": round(float(drop), 1),
                        "contrib_area_ha": round(p["contrib_area_m2"] / 1e4, 1),
                    }
                )

    if not candidates:
        return gpd.GeoDataFrame(columns=["geometry"])

    cand_gdf = gpd.GeoDataFrame(
        candidates, geometry=[Point(c["lon"], c["lat"]) for c in candidates], crs="EPSG:4326"
    )
    cand_gdf = cand_gdf.sort_values("slope_drop_deg", ascending=False).reset_index(drop=True)

    # de-dupe: keep the strongest candidate in each DEDUPE_RADIUS_M cluster
    proj = cand_gdf.to_crs(32629)
    kept = []
    kept_geoms = []
    for idx, row in proj.iterrows():
        if any(row.geometry.distance(g) < DEDUPE_RADIUS_M for g in kept_geoms):
            continue
        kept.append(idx)
        kept_geoms.append(row.geometry)

    return cand_gdf.loc[kept].reset_index(drop=True)


if __name__ == "__main__":
    if len(sys.argv) != 6:
        print(
            "usage: python find_barrier_candidates.py <filled_dem.tif> <d8_pointer.tif> "
            "<d8_accum.tif> <fire_perimeter.geojson> <out.geojson>"
        )
        sys.exit(1)
    out = find_candidates(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    out.to_file(sys.argv[5], driver="GeoJSON")
    print(f"wrote {sys.argv[5]} ({len(out)} candidate sites after dedupe)")
    print(out[["dist_from_fire_m", "slope_before_deg", "slope_after_deg", "slope_drop_deg", "contrib_area_ha"]].to_string(index=False))
