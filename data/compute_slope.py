"""
Copernicus DEM GLO-30 -> slope (degrees), reprojected and resampled onto
burn_severity.tif's grid so risk_index.py can use it directly.

DEM tiles come from the public AWS Open Data bucket (no auth needed):
https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_<N/S><lat>_00_<E/W><lon>_00_DEM/...tif
one 1x1 degree tile per cell, named by its SW corner.
"""

import sys

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling


def reproject_to_reference(src_path, reference_tif):
    with rasterio.open(src_path) as src:
        elev_src = src.read(1).astype("float64")
        src_transform = src.transform
        src_crs = src.crs

    with rasterio.open(reference_tif) as ref:
        elev = np.full((ref.height, ref.width), np.nan, dtype="float64")
        reproject(
            source=elev_src,
            destination=elev,
            src_transform=src_transform,
            src_crs=src_crs,
            dst_transform=ref.transform,
            dst_crs=ref.crs,
            resampling=Resampling.bilinear,
            src_nodata=None,
            dst_nodata=np.nan,
        )
        profile = ref.profile.copy()
        dx = abs(ref.transform.a)
        dy = abs(ref.transform.e)
    return elev, profile, dx, dy


def slope_degrees(elev, dx, dy):
    dzdy, dzdx = np.gradient(elev, dy, dx)
    slope_rad = np.arctan(np.sqrt(dzdx**2 + dzdy**2))
    return np.degrees(slope_rad)


def compute_slope(dem_path, reference_tif, out_path):
    elev, profile, dx, dy = reproject_to_reference(dem_path, reference_tif)
    slope = slope_degrees(elev, dx, dy)

    profile.update(count=1, dtype="float32")
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(slope.astype("float32"), 1)
        dst.set_band_description(1, "slope (degrees), from Copernicus DEM GLO-30")

    valid = np.isfinite(slope)
    print(
        f"wrote {out_path}  ({valid.sum()} valid px, "
        f"mean={np.nanmean(slope):.1f} deg, max={np.nanmax(slope):.1f} deg)"
    )


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("usage: python compute_slope.py <dem.tif> <reference.tif> <out_slope.tif>")
        sys.exit(1)
    compute_slope(sys.argv[1], sys.argv[2], sys.argv[3])
