"""
Genera todos los datos y capas ligeras del StoryMap de GeoSignal en
web/assets/data/ (< 3 MB en total) a partir de:
  - data/out/aoi_stack.npz y aoi_manifest.json (serie 10 pasadas Track 15/23)
  - data/out/burn_severity.tif, data/raw/slope.tif, data/raw/soil_moisture.tif
  - data/raw/basins.geojson, assets.geojson, effis_perimeter_calvos_de_randin.geojson, rain_channels.geojson
  - data/out/optical_meta.json (Sentinel-2 L2A real)

Todas las imágenes overlay se reproyectan a EPSG:3857 para alinear píxel a píxel
con MapLibre GL ImageSource.
"""

import json
import os
import sys

import geopandas as gpd
import numpy as np
import rasterio
from PIL import Image
from rasterio.transform import Affine, array_bounds
from rasterio.warp import Resampling, reproject, transform_bounds
from rasterio.windows import from_bounds
from rasterstats import zonal_stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import EFFIS_PERIMETER_GEOJSON, OUT_DIR, RAW_DIR

ASSETS_DATA_DIR = os.path.join("web", "assets", "data")
OVERLAYS_DIR = os.path.join(ASSETS_DATA_DIR, "overlays")
WEIGHTS = {"slope": 0.6, "dryness": 0.4}

WORLDCOVER_LABELS = {
    10: "Arbolado",
    20: "Matorral",
    30: "Pasto / herbáceo",
    40: "Cultivos",
    50: "Urbano",
    60: "Suelo desnudo / roca",
    80: "Agua",
}


def reproject_to_3857(arr, src_tf, src_crs, out_w=760, resampling=Resampling.bilinear):
    h, w = arr.shape
    src_bounds = array_bounds(h, w, src_tf)
    merc_bounds = transform_bounds(src_crs, "EPSG:3857", *src_bounds)
    out_h = round(out_w * (merc_bounds[3] - merc_bounds[1]) / (merc_bounds[2] - merc_bounds[0]))
    dst_tf = rasterio.transform.from_bounds(*merc_bounds, out_w, out_h)
    dst = np.full((out_h, out_w), np.nan, dtype=np.float32)
    reproject(
        source=arr.astype(np.float32),
        destination=dst,
        src_transform=src_tf,
        src_crs=src_crs,
        dst_transform=dst_tf,
        dst_crs="EPSG:3857",
        resampling=resampling,
        src_nodata=np.nan,
        dst_nodata=np.nan,
    )
    wgs = transform_bounds("EPSG:3857", "EPSG:4326", *merc_bounds)
    corners = [
        [round(wgs[0], 6), round(wgs[3], 6)],
        [round(wgs[2], 6), round(wgs[3], 6)],
        [round(wgs[2], 6), round(wgs[1], 6)],
        [round(wgs[0], 6), round(wgs[1], 6)],
    ]
    return dst, corners


def save_rgba(rgba, path, colors=64):
    img = Image.fromarray(rgba, mode="RGBA")
    if colors:
        img = img.quantize(colors=colors, method=Image.Quantize.FASTOCTREE)
    img.save(path, format="PNG", optimize=True)


def render_hv_grayscale(arr, vmin=-20.0, vmax=-5.0):
    h, w = arr.shape
    norm = np.nan_to_num(np.clip((arr - vmin) / (vmax - vmin), 0.0, 1.0), nan=0.0)
    gray = np.round(norm * 255.0).astype(np.uint8)
    # Suavizado de bordes (24 px) para fundir suavemente con el mapa base
    pad = max(8, min(h, w) // 16)
    wy = np.minimum(np.arange(h), h - 1 - np.arange(h)) / float(pad)
    wx = np.minimum(np.arange(w), w - 1 - np.arange(w)) / float(pad)
    feather = np.clip(np.minimum(wy[:, None], wx[None, :]), 0.0, 1.0)
    alpha = np.where(np.isfinite(arr), np.round(220.0 * feather), 0).astype(np.uint8)
    rgba = np.stack([gray, gray, gray, alpha], axis=-1)
    return rgba


def render_dnbr_classes(dnbr):
    # Clases USGS dNBR: >=0.10 baja, >=0.27 mod-alta, >=0.44 alta
    h, w = dnbr.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    valid = np.isfinite(dnbr)
    c1 = valid & (dnbr >= 0.10) & (dnbr < 0.27)
    c2 = valid & (dnbr >= 0.27) & (dnbr < 0.44)
    c3 = valid & (dnbr >= 0.44)
    rgba[c1] = [57, 232, 224, 175]
    rgba[c2] = [246, 201, 99, 210]
    rgba[c3] = [226, 121, 60, 235]
    return rgba


def render_dhv_classes(dhv):
    # Clases dB daltonismo-safe: > -1.5 transparente, -1.5..-3 ámbar, -3..-6 naranja, <= -6 carmesí
    h, w = dhv.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    valid = np.isfinite(dhv)
    c1 = valid & (dhv <= -1.5) & (dhv > -3.0)
    c2 = valid & (dhv <= -3.0) & (dhv > -6.0)
    c3 = valid & (dhv <= -6.0)
    rgba[c1] = [246, 201, 99, 205]
    rgba[c2] = [230, 118, 53, 225]
    rgba[c3] = [178, 24, 43, 245]
    return rgba


def render_dhv_continuous(dhv):
    # Transición suave de 0 -> -8 dB; > -0.5 transparente para no ensuciar suelo intacto
    h, w = dhv.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    valid = np.isfinite(dhv) & (dhv <= -0.5)
    t = np.clip((-dhv - 0.5) / 7.5, 0.0, 1.0)
    # Ramp: #fef08a (254,240,138) -> #e67635 (230,118,53) -> #991b1b (153,27,27)
    r = np.where(t < 0.5, 254 - (254 - 230) * (t * 2), 230 - (230 - 153) * ((t - 0.5) * 2))
    g = np.where(t < 0.5, 240 - (240 - 118) * (t * 2), 118 - (118 - 27) * ((t - 0.5) * 2))
    b = np.where(t < 0.5, 138 - (138 - 53) * (t * 2), 53 - (53 - 27) * ((t - 0.5) * 2))
    a = 120 + t * 125
    rgba[valid, 0] = np.clip(r[valid], 0, 255).astype(np.uint8)
    rgba[valid, 1] = np.clip(g[valid], 0, 255).astype(np.uint8)
    rgba[valid, 2] = np.clip(b[valid], 0, 255).astype(np.uint8)
    rgba[valid, 3] = np.clip(a[valid], 0, 255).astype(np.uint8)
    return rgba


def render_dhh_diverging(dhh):
    # Divergente azul (caída <= -1 dB) vs dorado/naranja (subida / doble rebote >= +1 dB)
    h, w = dhh.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    neg = np.isfinite(dhh) & (dhh <= -1.0)
    pos = np.isfinite(dhh) & (dhh >= 1.0)
    tn = np.clip((-dhh - 1.0) / 5.0, 0.0, 1.0)
    tp = np.clip((dhh - 1.0) / 5.0, 0.0, 1.0)
    rgba[neg, 0] = 56
    rgba[neg, 1] = (189 - 85 * tn[neg]).astype(np.uint8)
    rgba[neg, 2] = 248
    rgba[neg, 3] = (140 + 100 * tn[neg]).astype(np.uint8)
    rgba[pos, 0] = 245
    rgba[pos, 1] = (185 - 85 * tp[pos]).astype(np.uint8)
    rgba[pos, 2] = 50
    rgba[pos, 3] = (140 + 100 * tp[pos]).astype(np.uint8)
    return rgba


def encode_dhv_q8(dhv):
    """Codifica ΔHV en [-10.0, +4.0] dB -> uint8 0..254 (255 = NaN) para slider en tiempo real."""
    q = np.full(dhv.shape, 255, dtype=np.uint8)
    valid = np.isfinite(dhv)
    scaled = np.clip(np.round((dhv[valid] + 10.0) / 14.0 * 254.0), 0, 254).astype(np.uint8)
    q[valid] = scaled
    return q


def fullframe_percentile_bounds(tif_path, negate=False):
    with rasterio.open(tif_path) as src:
        step_h = max(1, src.height // 4000)
        step_w = max(1, src.width // 4000)
        out_h = (src.height + step_h - 1) // step_h
        out_w = (src.width + step_w - 1) // step_w
        sample = src.read(1, out_shape=(out_h, out_w))
    if negate:
        sample = -sample
    valid = sample[np.isfinite(sample)]
    lo, hi = np.nanpercentile(valid, [2, 98])
    return float(lo), float(hi)


def build_basins_and_sensitivity(assets_gdf, perim_gdf):
    basins = gpd.read_file(os.path.join(RAW_DIR, "basins.geojson"))
    sev_path = os.path.join(OUT_DIR, "burn_severity.tif")
    slope_path = os.path.join(RAW_DIR, "slope.tif")
    sm_path = os.path.join(RAW_DIR, "soil_moisture.tif")

    slope_lo, slope_hi = fullframe_percentile_bounds(slope_path, negate=False)
    dry_lo, dry_hi = fullframe_percentile_bounds(sm_path, negate=True)

    with rasterio.open(sev_path) as src:
        raster_crs = src.crs
        basins_proj = basins.to_crs(raster_crs)
        win = from_bounds(*basins_proj.total_bounds, transform=src.transform).round_offsets().round_lengths()
        win_tf = src.window_transform(win)
        dhv_win = src.read(1, window=win)
        mask_15 = src.read(2, window=win)

    with rasterio.open(slope_path) as src:
        slope_win = src.read(1, window=win)
    with rasterio.open(sm_path) as src:
        sm_win = src.read(1, window=win)

    slope_norm = np.clip((slope_win - slope_lo) / (slope_hi - slope_lo + 1e-9), 0, 1).astype(np.float32)
    dry_norm = np.clip((-sm_win - dry_lo) / (dry_hi - dry_lo + 1e-9), 0, 1).astype(np.float32)
    terrain_term = WEIGHTS["slope"] * slope_norm + WEIGHTS["dryness"] * dry_norm

    def stats_for_mask(burned_bin, prefix):
        risk_arr = (burned_bin * terrain_term).astype(np.float32)
        st_risk = zonal_stats(basins_proj, risk_arr, affine=win_tf, stats=["mean", "max"], nodata=np.nan)
        st_burn = zonal_stats(basins_proj, burned_bin.astype(np.float32), affine=win_tf, stats=["mean", "sum"], nodata=np.nan)
        basins[f"risk_mean{prefix}"] = [round(float(s["mean"] or 0.0), 6) for s in st_risk]
        basins[f"risk_max{prefix}"] = [round(float(s["max"] or 0.0), 4) for s in st_risk]
        basins[f"burned_pct{prefix}"] = [round(float((s["mean"] or 0.0) * 100.0), 2) for s in st_burn]
        basins[f"burned_ha{prefix}"] = [round(float((s["sum"] or 0.0) * 0.04), 2) for s in st_burn]

    stats_for_mask(mask_15, "")
    stats_for_mask((dhv_win <= -3.0).astype(np.float32), "_3db")
    stats_for_mask((dhv_win <= -6.0).astype(np.float32), "_6db")

    st_slope = zonal_stats(basins_proj, slope_win, affine=win_tf, stats=["mean"], nodata=np.nan)
    st_sm = zonal_stats(basins_proj, sm_win, affine=win_tf, stats=["mean"], nodata=np.nan)
    basins["slope_mean_deg"] = [round(float(s["mean"] or 0.0), 1) for s in st_slope]
    basins["moisture_mean"] = [round(float(s["mean"]), 3) if s["mean"] is not None else None for s in st_sm]
    basins["area_ha"] = (basins_proj.geometry.area / 10_000.0).round(1)

    fire_union = perim_gdf.to_crs(basins.crs).geometry.union_all()
    basins["overlaps_fire"] = basins.geometry.intersects(fire_union)

    # Ranking por riesgo estándar (-1.5 dB) y por niveles
    for suffix in ("", "_3db", "_6db"):
        order = basins[f"risk_mean{suffix}"].rank(ascending=False, method="min").astype(int)
        basins[f"rank{suffix}"] = order

    # Cruce con activos aguas abajo (OSM)
    assets_proj = assets_gdf.to_crs(basins.crs)
    joined = gpd.sjoin(assets_proj, basins[["basin_id", "geometry"]], how="inner", predicate="within")
    by_basin = {}
    for _, row in joined.iterrows():
        bid = int(row["basin_id"])
        by_basin.setdefault(bid, []).append({"name": row["name"], "type": row["type"]})
    basins["downstream_assets"] = [json.dumps(by_basin.get(int(bid), []), ensure_ascii=False) for bid in basins["basin_id"]]

    # Simplificar geometría (~10 m) para mantener < 250 KB en GeoJSON web
    basins_out = basins.copy()
    basins_out["geometry"] = basins_out.geometry.simplify(0.0001, preserve_topology=True)
    out_path = os.path.join(ASSETS_DATA_DIR, "basins_risk.geojson")
    basins_out.to_file(out_path, driver="GeoJSON")
    print(f"wrote {out_path} ({os.path.getsize(out_path) // 1024} KB, {len(basins_out)} basins)")

    top = basins.sort_values("risk_mean", ascending=False)[
        ["basin_id", "rank", "risk_mean", "risk_mean_3db", "risk_mean_6db", "burned_pct", "burned_ha", "area_ha", "slope_mean_deg", "moisture_mean", "overlaps_fire"]
    ]
    return top.to_dict(orient="records"), by_basin


def main():
    os.makedirs(OVERLAYS_DIR, exist_ok=True)
    npz = np.load(os.path.join(OUT_DIR, "aoi_stack.npz"))
    with open(os.path.join(OUT_DIR, "aoi_manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)

    dates = list(manifest["dates"])
    hv_smooth = npz["hv_smooth"]
    hh_smooth = npz["hh_smooth"]
    hv_raw = npz["hv_raw"]
    sme2 = npz["sme2"]
    wc = npz["worldcover"]
    fire_mask = npz["fire_mask"].astype(bool)
    ctrl_mask = npz["ctrl_mask"].astype(bool)

    aoi_tf = Affine(*manifest["transform"])
    src_crs = manifest["crs"]
    px_ha = (20.0 * 20.0) / 10_000.0  # 0.04 ha por píxel de 20 m

    idx_pre = dates.index("2026-09-19")
    idx_post = dates.index("2026-10-01")
    idx_oct25 = dates.index("2026-10-25") if "2026-10-25" in dates else idx_post
    dhv = hv_smooth[idx_post] - hv_smooth[idx_pre]
    dhv_raw = hv_raw[idx_post] - hv_raw[idx_pre]
    dhh = hh_smooth[idx_post] - hh_smooth[idx_pre]
    ctrl_offset_oct01 = float(np.nanmean(dhv[ctrl_mask]))
    dhv_oct01_cal = dhv - ctrl_offset_oct01
    dhv_oct25 = hv_smooth[idx_oct25] - hv_smooth[idx_pre]
    ctrl_offset_oct25 = float(np.nanmean(dhv_oct25[ctrl_mask]))

    # Línea base robusta: mediana de pasadas pre-incendio QA-pass (ago-sep)
    qa_pass_dates = {q["date"] for q in manifest["qa"] if q["qa_pass"]}
    pre_indices = [i for i, d in enumerate(dates) if "2026-08-01" <= d <= "2026-09-20" and d in qa_pass_dates]
    hv_pre_med = np.nanmedian(hv_smooth[pre_indices], axis=0)
    dhv_robust = hv_smooth[idx_post] - hv_pre_med

    # 1. Clases de dB dentro del perímetro EFFIS (y versión 20m cruda para explicar 239 vs 89 ha)
    valid_fire = fire_mask & np.isfinite(dhv)
    valid_ctrl = ctrl_mask & np.isfinite(dhv)
    expected_fire_px = int(fire_mask.sum())
    valid_fire_px = int(valid_fire.sum())

    def class_counts(arr, mask):
        vals = arr[mask & np.isfinite(arr)]
        c0 = int((vals > -1.5).sum())
        c1 = int(((vals <= -1.5) & (vals > -3.0)).sum())
        c2 = int(((vals <= -3.0) & (vals > -6.0)).sum())
        c3 = int((vals <= -6.0).sum())
        return {
            "total_valid_ha": round(len(vals) * px_ha, 2),
            "classes": [
                {"id": 0, "label": "Sin cambio (> -1.5 dB)", "px": c0, "ha": round(c0 * px_ha, 2), "pct": round(c0 / len(vals) * 100, 1)},
                {"id": 1, "label": "Moderada (-1.5 a -3 dB)", "px": c1, "ha": round(c1 * px_ha, 2), "pct": round(c1 / len(vals) * 100, 1)},
                {"id": 2, "label": "Alta (-3 a -6 dB)", "px": c2, "ha": round(c2 * px_ha, 2), "pct": round(c2 / len(vals) * 100, 1)},
                {"id": 3, "label": "Extrema (<= -6 dB)", "px": c3, "ha": round(c3 * px_ha, 2), "pct": round(c3 / len(vals) * 100, 1)},
            ],
            "burned_total_ha": round((c1 + c2 + c3) * px_ha, 2),
        }

    classes_smooth = class_counts(dhv, fire_mask)
    classes_raw = class_counts(dhv_raw, fire_mask)
    classes_robust = class_counts(dhv_robust, fire_mask)
    classes_oct01_cal = class_counts(dhv_oct01_cal, fire_mask)
    classes_oct25 = class_counts(dhv_oct25, fire_mask)

    # 2. Curva hectáreas vs umbral (-0.5 a -8.0 dB, paso 0.25) + tasa de falsos positivos en control
    thresholds = [round(-0.5 - 0.25 * k, 2) for k in range(31)]
    curve = []
    fire_vals_smooth = dhv[valid_fire]
    ctrl_vals_smooth = dhv[valid_ctrl]
    fire_vals_raw = dhv_raw[fire_mask & np.isfinite(dhv_raw)]
    ctrl_vals_raw = dhv_raw[ctrl_mask & np.isfinite(dhv_raw)]
    for th in thresholds:
        ha_s = round(float((fire_vals_smooth <= th).sum()) * px_ha, 2)
        fp_s = round(float((ctrl_vals_smooth <= th).mean()) * 100.0, 2)
        ha_r = round(float((fire_vals_raw <= th).sum()) * px_ha, 2)
        fp_r = round(float((ctrl_vals_raw <= th).mean()) * 100.0, 2)
        curve.append({"threshold_db": th, "ha_smooth": ha_s, "fp_ctrl_pct_smooth": fp_s, "ha_raw": ha_r, "fp_ctrl_pct_raw": fp_r})

    # 3. Histograma ΔHV dentro del perímetro vs control
    bins = np.linspace(-10.0, 4.0, 29)  # paso 0.5 dB
    hist_fire, _ = np.histogram(fire_vals_smooth, bins=bins, density=True)
    hist_ctrl, _ = np.histogram(ctrl_vals_smooth, bins=bins, density=True)
    histogram = [
        {"bin_center": round(float((bins[i] + bins[i + 1]) / 2), 2), "fire_density": round(float(hist_fire[i]), 4), "ctrl_density": round(float(hist_ctrl[i]), 4)}
        for i in range(len(bins) - 1)
    ]

    # 4. Comparativa HH vs HV (pregunta obligatoria 2)
    dhh_fire = dhh[fire_mask & np.isfinite(dhh)]
    dhh_ctrl = dhh[ctrl_mask & np.isfinite(dhh)]
    dhv25_fire = dhv_oct25[fire_mask & np.isfinite(dhv_oct25)]
    dhv25_ctrl = dhv_oct25[ctrl_mask & np.isfinite(dhv_oct25)]
    pol_stats = {
        "hv_fire_mean_db": round(float(np.mean(fire_vals_smooth)), 3),
        "hv_fire_net_db": round(float(np.mean(fire_vals_smooth) - ctrl_offset_oct01), 3),
        "hv_fire_p10_db": round(float(np.percentile(fire_vals_smooth, 10)), 3),
        "hv_ctrl_mean_db": round(float(np.mean(ctrl_vals_smooth)), 3),
        "hh_fire_mean_db": round(float(np.mean(dhh_fire)), 3),
        "hh_fire_net_db": round(float(np.mean(dhh_fire) - np.mean(dhh_ctrl)), 3),
        "hh_fire_p90_db": round(float(np.percentile(dhh_fire, 90)), 3),
        "hh_ctrl_mean_db": round(float(np.mean(dhh_ctrl)), 3),
        "hv_separation_db": round(float(np.mean(ctrl_vals_smooth) - np.mean(fire_vals_smooth)), 3),
        "hh_separation_db": round(float(np.mean(dhh_ctrl) - np.mean(dhh_fire)), 3),
        "hh_double_bounce_pct_fire": round(float((dhh_fire >= 1.0).mean()) * 100.0, 2),
        "ctrl_offset_oct01_db": round(ctrl_offset_oct01, 3),
        "ctrl_offset_oct25_db": round(ctrl_offset_oct25, 3),
        "hv_oct25_fire_mean_db": round(float(np.mean(dhv25_fire)), 3),
        "hv_oct25_ctrl_mean_db": round(float(np.mean(dhv25_ctrl)), 3),
    }

    # 5. Serie temporal de 10 pasadas (perímetro EFFIS vs control + SME2)
    timeseries = []
    for i, dt in enumerate(dates):
        qa = manifest["qa"][i]
        hv_f = hv_smooth[i][fire_mask]
        hv_c = hv_smooth[i][ctrl_mask]
        hh_f = hh_smooth[i][fire_mask]
        hh_c = hh_smooth[i][ctrl_mask]
        sm_f = sme2[i][fire_mask]
        sm_c = sme2[i][ctrl_mask]
        timeseries.append(
            {
                "date": dt,
                "qa_pass": qa["qa_pass"],
                "valid_pct_perimeter": qa["valid_pct_perimeter"],
                "ctrl_deviation_db": qa["ctrl_deviation_db"],
                "hv_fire_mean": round(float(np.nanmean(hv_f)), 3),
                "hv_ctrl_mean": round(float(np.nanmean(hv_c)), 3),
                "hh_fire_mean": round(float(np.nanmean(hh_f)), 3),
                "hh_ctrl_mean": round(float(np.nanmean(hh_c)), 3),
                "sme2_fire_mean": round(float(np.nanmean(sm_f)), 3) if np.isfinite(sm_f).any() else None,
                "sme2_ctrl_mean": round(float(np.nanmean(sm_c)), 3) if np.isfinite(sm_c).any() else None,
            }
        )

    # 6. Desglose por cobertura del suelo (ESA WorldCover 2021 dentro del perímetro EFFIS)
    landcover = []
    for code, name in WORLDCOVER_LABELS.items():
        m = valid_fire & (wc == code)
        cnt = int(m.sum())
        if cnt < 25:  # < 1 ha
            continue
        vals = dhv[m]
        vals25 = dhv_oct25[m]
        landcover.append(
            {
                "code": code,
                "name": name,
                "area_ha": round(cnt * px_ha, 2),
                "pct_of_perimeter": round(cnt / valid_fire_px * 100.0, 1),
                "dhv_mean_db": round(float(np.mean(vals)), 3),
                "dhv_net_oct01_db": round(float(np.mean(vals) - ctrl_offset_oct01), 3),
                "dhv_oct25_mean_db": round(float(np.nanmean(vals25)), 3),
                "burned_ha_15db": round(float((vals <= -1.5).sum()) * px_ha, 2),
                "burned_pct_15db": round(float((vals <= -1.5).mean()) * 100.0, 1),
                "burned_pct_oct25_15db": round(float((vals25 <= -1.5).mean()) * 100.0, 1),
            }
        )

    # 7. Overlays en EPSG:3857 para MapLibre
    overlays_meta = {}
    layers_to_export = [
        ("hv_pre.png", hv_smooth[idx_pre], render_hv_grayscale, 540),
        ("hv_post.png", hv_smooth[idx_post], render_hv_grayscale, 540),
        ("dhv_classes.png", dhv, render_dhv_classes, 680),
        ("dhv_oct01_cal.png", dhv_oct01_cal, render_dhv_classes, 680),
        ("dhv_oct25.png", dhv_oct25, render_dhv_classes, 680),
        ("dhv_cont.png", dhv, render_dhv_continuous, 680),
        ("dhh.png", dhh, render_dhh_diverging, 540),
    ]
    dnbr_stats = None
    dnbr_path = os.path.join(OUT_DIR, "s2_dnbr.tif")
    if os.path.exists(dnbr_path):
        with rasterio.open(dnbr_path) as dsrc:
            dnbr_arr = dsrc.read(1)
        val_dnbr = fire_mask & np.isfinite(dnbr_arr) & np.isfinite(dhv_oct25)
        dnbr_vals = dnbr_arr[val_dnbr]
        dnbr_stats = {
            "pre_scene": "2026-09-20",
            "post_scene": "2026-10-15",
            "valid_pct": round(float(val_dnbr.sum() / fire_mask.sum()) * 100.0, 1),
            "burned_low_plus_ha": round(float((dnbr_vals >= 0.10).sum()) * px_ha, 2),
            "burned_mod_high_ha": round(float((dnbr_vals >= 0.27).sum()) * px_ha, 2),
            "burned_high_ha": round(float((dnbr_vals >= 0.44).sum()) * px_ha, 2),
            "pearson_r_vs_dhv_oct25": round(float(np.corrcoef(dnbr_vals, dhv_oct25[val_dnbr])[0, 1]), 3),
            "pearson_r_vs_dhv_oct01": round(float(np.corrcoef(dnbr_vals, dhv[val_dnbr])[0, 1]), 3),
        }
        layers_to_export.append(("dnbr_s2.png", dnbr_arr, render_dnbr_classes, 680))

    for fname, arr, renderer, out_w in layers_to_export:
        merc_arr, corners = reproject_to_3857(arr, aoi_tf, src_crs, out_w=out_w)
        rgba = renderer(merc_arr)
        out_p = os.path.join(OVERLAYS_DIR, fname)
        save_rgba(rgba, out_p)
        overlays_meta[fname] = {"url": f"assets/data/overlays/{fname}", "coordinates": corners}

    # Cuantización 8-bit de ΔHV para filtrado instantáneo por umbral en canvas del navegador
    dhv_merc, dhv_corners = reproject_to_3857(dhv, aoi_tf, src_crs, out_w=520)
    q8 = encode_dhv_q8(dhv_merc)
    q8_path = os.path.join(OVERLAYS_DIR, "dhv_q8.png")
    Image.fromarray(q8, mode="L").save(q8_path, format="PNG", optimize=True)
    overlays_meta["dhv_q8.png"] = {
        "url": "assets/data/overlays/dhv_q8.png",
        "coordinates": dhv_corners,
        "min_db": -10.0,
        "max_db": 4.0,
    }

    # Miniaturas de HV por cada fecha de la serie temporal (para clic en gráfico)
    ts_dir = os.path.join(OVERLAYS_DIR, "ts")
    os.makedirs(ts_dir, exist_ok=True)
    for i, dt in enumerate(dates):
        m_arr, corners = reproject_to_3857(hv_smooth[i], aoi_tf, src_crs, out_w=320)
        rgba = render_hv_grayscale(m_arr)
        p = os.path.join(ts_dir, f"hv_{dt}.png")
        save_rgba(rgba, p)
        overlays_meta[f"ts/{dt}"] = {"url": f"assets/data/overlays/ts/{dt}.png".replace(f"/{dt}.png", f"/hv_{dt}.png"), "coordinates": corners}

    opt_path = os.path.join(OUT_DIR, "optical_meta.json")
    if os.path.exists(opt_path):
        with open(opt_path, encoding="utf-8") as f:
            overlays_meta.update(json.load(f))

    with open(os.path.join(OVERLAYS_DIR, "overlays.json"), "w", encoding="utf-8") as f:
        json.dump(overlays_meta, f, indent=2, ensure_ascii=False)

    # 8. GeoJSON de contexto y cuencas con sensibilidad
    perim_gdf = gpd.read_file(EFFIS_PERIMETER_GEOJSON).to_crs("EPSG:4326")
    perim_gdf.to_file(os.path.join(ASSETS_DATA_DIR, "fire_perimeter.geojson"), driver="GeoJSON")

    assets_gdf = gpd.read_file(os.path.join(RAW_DIR, "assets.geojson")).to_crs("EPSG:4326")
    assets_gdf.to_file(os.path.join(ASSETS_DATA_DIR, "assets.geojson"), driver="GeoJSON")

    rain_src = os.path.join(RAW_DIR, "rain_channels.geojson")
    if os.path.exists(rain_src):
        rain_gdf = gpd.read_file(rain_src).to_crs("EPSG:4326")
        rain_gdf.to_file(os.path.join(ASSETS_DATA_DIR, "rain_channels.geojson"), driver="GeoJSON")

    basins_summary, assets_by_basin = build_basins_and_sensitivity(assets_gdf, perim_gdf)

    stats = {
        "meta": {
            "fire_name": "Calvos de Randín (Ourense, Galicia)",
            "ignition_date": "2026-09-24",
            "controlled_date": "2026-09-27",
            "declaration_date": "2026-10-27",
            "track_frame": "Track 15 / Frame 23 (ascendente)",
            "pre_date": "2026-09-19",
            "post_date": "2026-10-01",
            "official_xunta_ha": 518,
            "official_forest_ha": 370,
            "official_grass_ha": 148,
            "effis_ha": 1234,
            "effis_fire_id": 15925129,
            "valid_coverage_pct": round(valid_fire_px / expected_fire_px * 100.0, 2),
        },
        "severity_smooth": classes_smooth,
        "severity_raw_20m": classes_raw,
        "severity_robust_baseline": classes_robust,
        "severity_oct01_calibrated": classes_oct01_cal,
        "severity_oct25": classes_oct25,
        "threshold_curve": curve,
        "histogram": histogram,
        "polarizations": pol_stats,
        "timeseries": timeseries,
        "landcover_2021": landcover,
        "optical_dnbr": dnbr_stats,
        "basins_summary": basins_summary,
        "assets_by_basin": {str(k): v for k, v in assets_by_basin.items()},
        "qa": manifest["qa"],
        "ctrl_hv_median_db": manifest["ctrl_hv_median_db"],
    }
    stats_path = os.path.join(ASSETS_DATA_DIR, "story_stats.json")
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    print(f"wrote {stats_path} ({os.path.getsize(stats_path) // 1024} KB)")


if __name__ == "__main__":
    main()
