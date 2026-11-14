"""
Delineate microbasins from the Copernicus DEM using WhiteboxTools:
fill depressions -> flow direction -> flow accumulation -> stream
network -> subbasins (one polygon per stream segment's contributing
area). Filters the result down to whatever intersects the AOI so the
output geojson only has the handful of basins that matter here, not
every subbasin in the whole 1x1 degree DEM tile.
"""

import os
import sys

import geopandas as gpd
import whitebox

# cells; tested 1000/5000/10000/20000/40000 against the real EFFIS perimeter --
# 10000 (~9 km^2 contributing area) is the sweet spot: basins come out ~1,260 ha
# on average (close to the fire's own 1,234 ha), and only 2 basins touch the
# fire instead of 23 (at 1000) or 1 giant one swallowing everything (at 40000).
STREAM_THRESHOLD_CELLS = 10000


def delineate(dem_path, work_dir, aoi_bbox):
    work_dir = os.path.abspath(work_dir)
    os.makedirs(work_dir, exist_ok=True)
    wbt = whitebox.WhiteboxTools()
    wbt.set_working_dir(work_dir)
    wbt.set_verbose_mode(False)

    dem_abs = os.path.abspath(dem_path)
    filled = "filled_dem.tif"
    pointer = "d8_pointer.tif"
    accum = "d8_accum.tif"
    streams = "streams.tif"
    subbasins_tif = "subbasins.tif"
    subbasins_shp = "subbasins.shp"

    wbt.fill_depressions(dem_abs, filled)
    wbt.d8_pointer(filled, pointer)
    wbt.d8_flow_accumulation(filled, accum, out_type="cells")
    wbt.extract_streams(accum, streams, threshold=STREAM_THRESHOLD_CELLS)
    wbt.subbasins(pointer, streams, subbasins_tif)
    wbt.raster_to_vector_polygons(subbasins_tif, subbasins_shp)

    basins = gpd.read_file(os.path.join(work_dir, subbasins_shp))
    basins = basins.set_crs("EPSG:4326", allow_override=True)

    min_lon, min_lat, max_lon, max_lat = (
        aoi_bbox["min_lon"],
        aoi_bbox["min_lat"],
        aoi_bbox["max_lon"],
        aoi_bbox["max_lat"],
    )
    clipped = basins.cx[min_lon:max_lon, min_lat:max_lat]
    return clipped


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("usage: python delineate_basins.py <dem.tif> <work_dir> <out_basins.geojson>")
        sys.exit(1)

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from config import AOI_BBOX

    dem_path, work_dir, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    basins = delineate(dem_path, work_dir, AOI_BBOX)
    basins["basin_id"] = range(1, len(basins) + 1)
    basins.to_file(out_path, driver="GeoJSON")
    print(f"wrote {out_path}  ({len(basins)} basins intersecting the AOI)")
