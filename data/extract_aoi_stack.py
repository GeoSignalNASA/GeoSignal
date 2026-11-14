"""
Extrae únicamente la ventana del AOI (Calvos de Randín + margen) de toda la
serie temporal NISAR GCOV (HVHV, HHHH) y SME2 (humedad del suelo), verificando
alineación de proyección/rejilla y ejecutando QA radiométrico por fecha.

Nunca carga el ráster completo de 18000x17784 en memoria (~0,5 Mpx por fecha,
< 200 MB de RAM pico).

Salida:
  data/out/aoi_stack.npz
  data/out/aoi_manifest.json
"""

import glob
import json
import os
import re
import sys

import geopandas as gpd
import h5py
import numpy as np
import rasterio
import scipy.ndimage as ndi
from rasterio.features import geometry_mask
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject, transform_bounds
from rasterio.windows import Window, from_bounds

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import AOI_BBOX, EFFIS_PERIMETER_GEOJSON, OUT_DIR, RAW_DIR

GCOV_GRID = "/science/LSAR/GCOV/grids/frequencyA"
SME2_GRID = "/science/LSAR/SME2/grids"
SMOOTH_WINDOW = 5  # boxcar 5x5 px = 100 m
SME2_FILL = -9999.0


def parse_date_from_name(path):
    m = re.search(r"_(\d{8})T\d{6}_", os.path.basename(path))
    if not m:
        raise ValueError(f"No se pudo extraer fecha de {path}")
    d = m.group(1)
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def to_db(power):
    with np.errstate(divide="ignore", invalid="ignore"):
        valid = np.isfinite(power) & (power > 0)
        out = np.full(power.shape, np.nan, dtype=np.float32)
        out[valid] = (10.0 * np.log10(power[valid])).astype(np.float32)
    return out


def nan_aware_boxcar(arr, size=SMOOTH_WINDOW):
    valid = np.isfinite(arr).astype(np.float32)
    filled = np.where(np.isfinite(arr), arr, np.float32(0.0))
    sum_valid = ndi.uniform_filter(filled, size=size, mode="constant", cval=0.0)
    frac_valid = ndi.uniform_filter(valid, size=size, mode="constant", cval=0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(frac_valid > 0, sum_valid / frac_valid, np.nan).astype(np.float32)


def gcov_meta(h5_path):
    with h5py.File(h5_path, "r") as f:
        g = f[GCOV_GRID]
        shape = g["HVHV"].shape
        x0 = float(g["xCoordinates"][0])
        y0 = float(g["yCoordinates"][0])
        dx = float(g["xCoordinateSpacing"][()])
        dy = float(g["yCoordinateSpacing"][()])
        epsg = int(g["projection"][()])
    transform = from_origin(x0, y0, dx, abs(dy))
    return shape, transform, epsg


def compute_aoi_window(ref_shape, ref_transform, ref_crs):
    # Margen de 1,5 km para cubrir la zona de control alrededor del perímetro
    bounds_utm = transform_bounds(
        "EPSG:4326",
        ref_crs,
        AOI_BBOX["min_lon"] - 0.015,
        AOI_BBOX["min_lat"] - 0.015,
        AOI_BBOX["max_lon"] + 0.015,
        AOI_BBOX["max_lat"] + 0.015,
    )
    win = from_bounds(*bounds_utm, transform=ref_transform).round_offsets().round_lengths()
    r0 = max(0, int(win.row_off))
    c0 = max(0, int(win.col_off))
    r1 = min(ref_shape[0], r0 + int(win.height))
    c1 = min(ref_shape[1], c0 + int(win.width))
    win = Window(c0, r0, c1 - c0, r1 - r0)
    aoi_tf = rasterio.windows.transform(win, ref_transform)
    return win, aoi_tf


def read_sme2_aligned(h5_path, dst_shape, dst_tf, dst_crs):
    with h5py.File(h5_path, "r") as f:
        g = f[SME2_GRID]
        x_coords = g["xCoordinates"][:]
        y_coords = g["yCoordinates"][:]
        dx = float(g["xCoordinateSpacing"][()])
        dy = float(g["yCoordinateSpacing"][()])
        epsg = int(g["projection"][()])

        # Calcular bounds del AOI en EPSG:6933 para leer solo un recorte pequeño
        aoi_bounds_4326 = transform_bounds(
            dst_crs,
            "EPSG:4326",
            *rasterio.transform.array_bounds(dst_shape[0], dst_shape[1], dst_tf),
        )
        b6933 = transform_bounds(
            "EPSG:4326",
            f"EPSG:{epsg}",
            aoi_bounds_4326[0] - 0.05,
            aoi_bounds_4326[1] - 0.05,
            aoi_bounds_4326[2] + 0.05,
            aoi_bounds_4326[3] + 0.05,
        )
        c_mask = (x_coords >= b6933[0]) & (x_coords <= b6933[2])
        r_mask = (y_coords >= b6933[1]) & (y_coords <= b6933[3])
        cols = np.where(c_mask)[0]
        rows = np.where(r_mask)[0]
        r0, r1 = int(rows[0]), int(rows[-1]) + 1
        c0, c1 = int(cols[0]), int(cols[-1]) + 1
        sub = g["soilMoisture"][r0:r1, c0:c1].astype(np.float32)

    sub = np.where(sub <= SME2_FILL + 1, np.nan, sub)
    src_tf = from_origin(float(x_coords[c0]) - abs(dx) / 2, float(y_coords[r0]) + abs(dy) / 2, abs(dx), abs(dy))

    dst = np.full(dst_shape, np.nan, dtype=np.float32)
    reproject(
        source=sub,
        destination=dst,
        src_transform=src_tf,
        src_crs=f"EPSG:{epsg}",
        dst_transform=dst_tf,
        dst_crs=dst_crs,
        resampling=Resampling.bilinear,
        src_nodata=np.nan,
        dst_nodata=np.nan,
    )
    return dst


def reproject_raster_to_aoi(src_path, dst_shape, dst_tf, dst_crs, resampling):
    with rasterio.open(src_path) as src:
        dst = np.full(dst_shape, np.nan if resampling != Resampling.nearest else 0, dtype=np.float32)
        if src.crs == dst_crs and src.shape[0] >= dst_shape[0] and resampling != Resampling.nearest:
            # Lectura rápida por ventana cuando el ráster ya está en la rejilla GCOV (slope, soil_moisture)
            b = rasterio.transform.array_bounds(dst_shape[0], dst_shape[1], dst_tf)
            win = from_bounds(*b, transform=src.transform).round_offsets().round_lengths()
            if int(win.height) == dst_shape[0] and int(win.width) == dst_shape[1]:
                return src.read(1, window=win).astype(np.float32)
        reproject(
            source=rasterio.band(src, 1),
            destination=dst,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=dst_tf,
            dst_crs=dst_crs,
            resampling=resampling,
        )
    return dst


def main():
    gcov_files = sorted(glob.glob(os.path.join(RAW_DIR, "NISAR_L2_PR_GCOV_*_015_A_023_*.h5")))
    sme2_files = sorted(glob.glob(os.path.join(RAW_DIR, "NISAR_L3_PR_SME2_*_015_A_023_*.h5")))
    if not gcov_files:
        raise FileNotFoundError("No hay archivos NISAR GCOV Track 15/Frame 23 en data/raw/")

    gcov_by_date = {parse_date_from_name(p): p for p in gcov_files}
    sme2_by_date = {parse_date_from_name(p): p for p in sme2_files}
    dates = sorted(gcov_by_date.keys())

    ref_shape, ref_tf, ref_epsg = gcov_meta(gcov_by_date[dates[0]])
    ref_crs = f"EPSG:{ref_epsg}"
    win, aoi_tf = compute_aoi_window(ref_shape, ref_tf, ref_crs)
    h, w = int(win.height), int(win.width)
    r0, r1 = int(win.row_off), int(win.row_off + win.height)
    c0, c1 = int(win.col_off), int(win.col_off + win.width)
    print(f"Ventana AOI: {w}x{h} px ({ref_crs}) en {len(dates)} fechas GCOV")

    # Máscaras vectoriales reales: perímetro EFFIS y zona de control (fuera del perímetro - 1 km buffer)
    perim_gdf = gpd.read_file(EFFIS_PERIMETER_GEOJSON).to_crs(ref_crs)
    fire_mask = ~geometry_mask(perim_gdf.geometry, out_shape=(h, w), transform=aoi_tf, invert=False)
    buf_geom = perim_gdf.geometry.buffer(1000.0)
    ctrl_mask = geometry_mask(buf_geom, out_shape=(h, w), transform=aoi_tf, invert=False)

    hv_smooth_stack = np.full((len(dates), h, w), np.nan, dtype=np.float32)
    hh_smooth_stack = np.full((len(dates), h, w), np.nan, dtype=np.float32)
    hv_raw_stack = np.full((len(dates), h, w), np.nan, dtype=np.float32)
    sme2_stack = np.full((len(dates), h, w), np.nan, dtype=np.float32)

    qa_rows = []
    for idx, dt in enumerate(dates):
        path = gcov_by_date[dt]
        shape, tf, epsg = gcov_meta(path)
        if epsg != ref_epsg:
            raise ValueError(f"EPSG distinto en {dt}: {epsg} != {ref_epsg}")

        # Calcular ventana específica por si hubiera desplazamiento entero entre pasadas
        if shape == ref_shape and tf == ref_tf:
            lr0, lr1, lc0, lc1 = r0, r1, c0, c1
        else:
            b = rasterio.transform.array_bounds(h, w, aoi_tf)
            lwin = from_bounds(*b, transform=tf).round_offsets().round_lengths()
            lr0, lc0 = int(lwin.row_off), int(lwin.col_off)
            lr1, lc1 = lr0 + h, lc0 + w

        with h5py.File(path, "r") as f:
            g = f[GCOV_GRID]
            hv_pow = g["HVHV"][lr0:lr1, lc0:lc1]
            hh_pow = g["HHHH"][lr0:lr1, lc0:lc1]

        hv_db_raw = to_db(hv_pow)
        hh_db_raw = to_db(hh_pow)
        hv_db = nan_aware_boxcar(hv_db_raw, SMOOTH_WINDOW)
        hh_db = nan_aware_boxcar(hh_db_raw, SMOOTH_WINDOW)

        hv_raw_stack[idx] = hv_db_raw
        hv_smooth_stack[idx] = hv_db
        hh_smooth_stack[idx] = hh_db

        if dt in sme2_by_date:
            sme2_stack[idx] = read_sme2_aligned(sme2_by_date[dt], (h, w), aoi_tf, ref_crs)

        valid_perim = float(np.isfinite(hv_db[fire_mask]).mean() * 100.0)
        ctrl_hv_vals = hv_db[ctrl_mask]
        ctrl_hh_vals = hh_db[ctrl_mask]
        qa_rows.append(
            {
                "date": dt,
                "gcov_file": os.path.basename(path),
                "sme2_file": os.path.basename(sme2_by_date[dt]) if dt in sme2_by_date else None,
                "epsg": epsg,
                "grid_aligned": bool(shape == ref_shape and tf == ref_tf),
                "valid_pct_perimeter": round(valid_perim, 2),
                "ctrl_hv_mean_db": round(float(np.nanmean(ctrl_hv_vals)), 3),
                "ctrl_hv_std_db": round(float(np.nanstd(ctrl_hv_vals)), 3),
                "ctrl_hh_mean_db": round(float(np.nanmean(ctrl_hh_vals)), 3),
            }
        )
        print(
            f"  {dt}: valid_perim={valid_perim:.1f}% | "
            f"ctrl_HV={qa_rows[-1]['ctrl_hv_mean_db']} dB | "
            f"SME2={'ok' if dt in sme2_by_date else 'no'}"
        )

    # Detección automática de anomalías radiométricas (> 1.0 dB respecto a la mediana de control)
    ctrl_means = np.array([q["ctrl_hv_mean_db"] for q in qa_rows])
    med_ctrl = float(np.median(ctrl_means))
    for q in qa_rows:
        delta = abs(q["ctrl_hv_mean_db"] - med_ctrl)
        q["ctrl_deviation_db"] = round(delta, 3)
        q["qa_pass"] = bool(q["valid_pct_perimeter"] >= 99.0 and delta <= 1.0)
        if not q["qa_pass"]:
            print(f"  [QA FLAG] {q['date']}: valid={q['valid_pct_perimeter']}%, dev={delta:.2f} dB")

    # Capas estáticas alineadas al mismo AOI
    slope_aoi = reproject_raster_to_aoi(
        os.path.join(RAW_DIR, "slope.tif"), (h, w), aoi_tf, ref_crs, Resampling.bilinear
    )
    wc_path = os.path.join(OUT_DIR, "worldcover_aoi.tif")
    worldcover_aoi = (
        reproject_raster_to_aoi(wc_path, (h, w), aoi_tf, ref_crs, Resampling.nearest).astype(np.uint8)
        if os.path.exists(wc_path)
        else np.zeros((h, w), dtype=np.uint8)
    )

    os.makedirs(OUT_DIR, exist_ok=True)
    npz_path = os.path.join(OUT_DIR, "aoi_stack.npz")
    np.savez_compressed(
        npz_path,
        dates=np.array(dates),
        hv_smooth=hv_smooth_stack,
        hh_smooth=hh_smooth_stack,
        hv_raw=hv_raw_stack,
        sme2=sme2_stack,
        slope=slope_aoi,
        worldcover=worldcover_aoi,
        fire_mask=fire_mask,
        ctrl_mask=ctrl_mask,
    )

    manifest = {
        "crs": ref_crs,
        "epsg": ref_epsg,
        "shape": [h, w],
        "transform": list(aoi_tf)[:6],
        "bounds_utm": list(rasterio.transform.array_bounds(h, w, aoi_tf)),
        "bounds_wgs84": list(transform_bounds(ref_crs, "EPSG:4326", *rasterio.transform.array_bounds(h, w, aoi_tf))),
        "dates": dates,
        "ctrl_hv_median_db": round(med_ctrl, 3),
        "qa": qa_rows,
    }
    manifest_path = os.path.join(OUT_DIR, "aoi_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"wrote {npz_path} y {manifest_path}")


if __name__ == "__main__":
    main()
