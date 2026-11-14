"""
"Rain simulator" (lightweight version): seed points along the real fire
perimeter, trace where water would flow downhill from there using the D8
flow direction already computed for basin delineation (delineate_basins.py).

Not a physical rainfall-runoff model -- no rainfall intensity, infiltration,
or debris-mobilization thresholds. This answers "which way does water go
from the burn scar," which is exactly what the D8 pointer already encodes.
"""

import os
import sys

import geopandas as gpd
import numpy as np
import rasterio
from shapely.geometry import Point

N_SEEDS = 32  # points sampled around the fire perimeter


def make_seed_points(perimeter_geojson, out_shp, n_seeds=N_SEEDS):
    perim = gpd.read_file(perimeter_geojson)
    ring = perim.geometry.iloc[0].exterior
    distances = np.linspace(0, ring.length, n_seeds, endpoint=False)
    points = [ring.interpolate(d) for d in distances]
    gdf = gpd.GeoDataFrame({"id": range(len(points))}, geometry=points, crs="EPSG:4326")
    gdf.to_file(out_shp)
    return out_shp


def trace(dem_pointer_tif, perimeter_geojson, work_dir, out_geojson):
    import whitebox

    work_dir = os.path.abspath(work_dir)
    os.makedirs(work_dir, exist_ok=True)
    seed_shp = os.path.join(work_dir, "fire_seeds.shp")
    make_seed_points(perimeter_geojson, seed_shp)

    wbt = whitebox.WhiteboxTools()
    wbt.set_working_dir(work_dir)
    wbt.set_verbose_mode(False)

    flowpaths_tif = "flowpaths.tif"
    wbt.trace_downslope_flowpaths("fire_seeds.shp", os.path.abspath(dem_pointer_tif), flowpaths_tif)

    with rasterio.open(os.path.join(work_dir, flowpaths_tif)) as src:
        data = src.read(1)
        transform = src.transform
        nodata = src.nodata

    mask = np.isfinite(data) & (data != (nodata if nodata is not None else -9999))
    rows, cols = np.where(mask)
    xs, ys = rasterio.transform.xy(transform, rows, cols)
    pts = gpd.GeoDataFrame(geometry=[Point(x, y) for x, y in zip(xs, ys)], crs="EPSG:4326")
    pts.to_file(out_geojson, driver="GeoJSON")
    print(f"wrote {out_geojson} ({len(pts)} flowpath cells from {N_SEEDS} seed points)")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("usage: python trace_flowpaths.py <d8_pointer.tif> <fire_perimeter.geojson> <work_dir> <out_flowpaths.geojson>")
        sys.exit(1)
    trace(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
