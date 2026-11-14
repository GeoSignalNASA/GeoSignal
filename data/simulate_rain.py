"""
"Rain simulator," lightweight version: trace real D8 flow paths downhill
from the fire perimeter (same pointer raster delineate_basins.py already
computed), recording real contributing area at every step. Rainfall
amount itself is NOT real data -- it's a slider in the web UI the user
sets to ask "if this much rain fell, how much water would be at this
point in the channel." That scenario math (area x rainfall x runoff
coefficient) happens client-side in JS; this script only exports the
real geometry + real contributing area per point.
"""

import os
import sys
import math

import geopandas as gpd
import numpy as np
import rasterio
from shapely.geometry import LineString

N_SEEDS = 8
MAX_STEPS = 4000

# (d_row, d_col) per pointer code. delineate_basins.py writes the pointer with
# WhiteboxTools' default convention (1 = NE, clockwise), NOT ESRI's (1 = E):
#   64 128   1
#   32   0   2
#   16   8   4
# Decoding it as ESRI rotates every step 45 deg and the "channel" climbs uphill.
DIRS = {1: (-1, 1), 2: (0, 1), 4: (1, 1), 8: (1, 0), 16: (1, -1), 32: (0, -1), 64: (-1, -1), 128: (-1, 0)}


def seed_rowcols(perimeter_geojson, transform, n_seeds):
    perim = gpd.read_file(perimeter_geojson)
    ring = perim.geometry.iloc[0].exterior
    distances = np.linspace(0, ring.length, n_seeds, endpoint=False)
    rowcols = []
    for d in distances:
        pt = ring.interpolate(d)
        row, col = rasterio.transform.rowcol(transform, pt.x, pt.y)
        rowcols.append((row, col))
    return rowcols


def cell_size_m(transform, lat):
    dx_deg = abs(transform.a)
    dy_deg = abs(transform.e)
    m_per_deg = 111_320.0
    dx_m = dx_deg * m_per_deg * math.cos(math.radians(lat))
    dy_m = dy_deg * m_per_deg
    return dx_m, dy_m


def trace_one(pntr, accum, transform, start_row, start_col, max_steps=MAX_STEPS):
    height, width = pntr.shape
    row, col = start_row, start_col
    path = []
    dist_m = 0.0
    for _ in range(max_steps):
        if row < 0 or row >= height or col < 0 or col >= width:
            break
        v = pntr[row, col]
        lon, lat = rasterio.transform.xy(transform, row, col)
        dx_m, dy_m = cell_size_m(transform, lat)
        acc = accum[row, col]
        contributing_area_m2 = float(acc) * dx_m * dy_m
        path.append((lon, lat, dist_m, contributing_area_m2))
        if v not in DIRS:
            break  # sink, nodata, or edge of the D8 pointer's valid region
        dr, dc = DIRS[v]
        step_m = dy_m if dc == 0 else (dx_m if dr == 0 else math.hypot(dx_m, dy_m))
        dist_m += step_m
        row, col = row + dr, col + dc
    return path


def simulate(pointer_tif, accum_tif, perimeter_geojson, out_geojson, n_seeds=N_SEEDS):
    with rasterio.open(pointer_tif) as src:
        pntr = src.read(1)
        transform = src.transform
    with rasterio.open(accum_tif) as src:
        accum = src.read(1)

    seeds = seed_rowcols(perimeter_geojson, transform, n_seeds)

    lines = []
    for seed_id, (row, col) in enumerate(seeds):
        path = trace_one(pntr, accum, transform, row, col)
        if len(path) < 2:
            continue
        coords = [(lon, lat) for lon, lat, _, _ in path]
        lines.append(
            {
                "seed_id": seed_id,
                "geometry": LineString(coords),
                "dist_m": [round(d, 1) for _, _, d, _ in path],
                "contrib_area_m2": [round(a, 1) for *_, a in path],
                "ran_off_edge": len(path) == MAX_STEPS,
            }
        )

    gdf = gpd.GeoDataFrame(lines, crs="EPSG:4326")
    # list columns aren't valid GeoJSON properties directly -- stash as JSON strings
    import json

    gdf["dist_m"] = gdf["dist_m"].apply(json.dumps)
    gdf["contrib_area_m2"] = gdf["contrib_area_m2"].apply(json.dumps)
    gdf.to_file(out_geojson, driver="GeoJSON")
    print(f"wrote {out_geojson} ({len(gdf)} traced channels from {n_seeds} seed points)")
    for _, row in gdf.iterrows():
        edge_note = " (hit DEM tile edge, not a real endpoint)" if row["ran_off_edge"] else ""
        print(f"  seed {row['seed_id']}: {len(json.loads(row['dist_m']))} steps{edge_note}")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("usage: python simulate_rain.py <d8_pointer.tif> <d8_accum.tif> <fire_perimeter.geojson> <out.geojson>")
        sys.exit(1)
    simulate(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
