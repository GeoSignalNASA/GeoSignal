"""
Pre/post HV backscatter diff from two NISAR GCOV granules -> burn severity
GeoTIFF.

HDF5 paths below match the NISAR GCOV product spec as of the Earthdata
docs linked in the deck. VERIFY against the actual files once downloaded --
product builds have moved group paths before (e.g. frequencyA vs frequencyB,
extra polarimetric terms). Run `h5py.File(path).visit(print)` on one
granule if `HVHV` isn't where this expects it.
"""

import sys

import h5py
import numpy as np
import rasterio
from rasterio.transform import from_origin

from config import HV_BURN_THRESHOLD_DB, OUT_DIR

GRID_PATH = "/science/LSAR/GCOV/grids/frequencyA"
HV_DATASET = "HVHV"


def load_hv(h5_path):
    with h5py.File(h5_path, "r") as f:
        grid = f[GRID_PATH]
        hv = grid[HV_DATASET][:]
        x0 = grid["xCoordinates"][0]
        y0 = grid["yCoordinates"][0]
        dx = grid["xCoordinateSpacing"][()]
        dy = grid["yCoordinateSpacing"][()]
        epsg = int(grid["projection"][()])
    transform = from_origin(x0, y0, dx, abs(dy))
    return hv, transform, epsg


def to_db(power):
    power = np.where(power <= 0, np.nan, power)
    return 10 * np.log10(power)


def compute_severity(pre_path, post_path, out_path):
    pre_hv, transform, epsg = load_hv(pre_path)
    post_hv, post_transform, post_epsg = load_hv(post_path)

    if pre_hv.shape != post_hv.shape or epsg != post_epsg:
        raise ValueError(
            "Pre/post grids don't line up -- re-check that these two "
            "granules share track/frame, or reproject one onto the other "
            "before diffing."
        )

    diff_db = to_db(post_hv) - to_db(pre_hv)
    burned = diff_db <= HV_BURN_THRESHOLD_DB

    profile = {
        "driver": "GTiff",
        "height": diff_db.shape[0],
        "width": diff_db.shape[1],
        "count": 2,
        "dtype": "float32",
        "crs": f"EPSG:{epsg}",
        "transform": transform,
        "nodata": np.nan,
    }
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(diff_db.astype("float32"), 1)
        dst.write(burned.astype("float32"), 2)
        dst.set_band_description(1, "HV diff (dB, post - pre)")
        dst.set_band_description(2, f"burned mask (diff <= {HV_BURN_THRESHOLD_DB} dB)")

    print(f"wrote {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python compute_change.py <pre_gcov.h5> <post_gcov.h5>")
        sys.exit(1)

    import os

    os.makedirs(OUT_DIR, exist_ok=True)
    compute_severity(sys.argv[1], sys.argv[2], f"{OUT_DIR}/burn_severity.tif")
