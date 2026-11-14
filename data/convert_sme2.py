"""
Convert a NISAR SME2 soil-moisture granule to a GeoTIFF aligned to
burn_severity.tif's grid, so risk_index.py can use it directly.

SME2's soilMoisture grid is natively on EASE-Grid 2.0 (EPSG:6933) at
~200m, not the UTM grid GCOV uses -- this reprojects + resamples onto
whatever reference raster you pass (normally burn_severity.tif).
"""

import sys

import h5py
import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import reproject, Resampling

GRID_PATH = "science/LSAR/SME2/grids"
FILL_VALUE = -9999.0


def load_soil_moisture(h5_path):
    with h5py.File(h5_path, "r") as f:
        grid = f[GRID_PATH]
        sm = grid["soilMoisture"][:]
        x0 = grid["xCoordinates"][0]
        y0 = grid["yCoordinates"][0]
        dx = grid["xCoordinateSpacing"][()]
        dy = grid["yCoordinateSpacing"][()]
        epsg = int(grid["projection"][()])
    sm = np.where(sm <= FILL_VALUE + 1, np.nan, sm)
    transform = from_origin(x0, y0, dx, abs(dy))
    return sm, transform, epsg


def convert(sme2_path, reference_tif, out_path):
    sm, src_transform, src_epsg = load_soil_moisture(sme2_path)

    with rasterio.open(reference_tif) as ref:
        dst_profile = ref.profile.copy()
        dst_profile.update(count=1, dtype="float32")
        dst_array = np.full((ref.height, ref.width), np.nan, dtype="float32")

        reproject(
            source=sm,
            destination=dst_array,
            src_transform=src_transform,
            src_crs=f"EPSG:{src_epsg}",
            dst_transform=ref.transform,
            dst_crs=ref.crs,
            resampling=Resampling.bilinear,
            src_nodata=np.nan,
            dst_nodata=np.nan,
        )

    with rasterio.open(out_path, "w", **dst_profile) as dst:
        dst.write(dst_array, 1)
        dst.set_band_description(1, "SME2 soil moisture (m3/m3), reprojected to severity grid")

    valid = np.isfinite(dst_array)
    print(f"wrote {out_path}  ({valid.sum()} valid px, mean={np.nanmean(dst_array):.3f} m3/m3)")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("usage: python convert_sme2.py <sme2.h5> <reference.tif> <out.tif>")
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2], sys.argv[3])
