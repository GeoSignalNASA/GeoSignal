"""
Suite de validación científica y de integridad para los datos del StoryMap.
Falla con exit code != 0 si algún invariante físico, geoespacial o de peso
se incumple.
"""

import json
import os
import sys

import geopandas as gpd

ASSETS_DIR = os.path.join("web", "assets", "data")
MANIFEST_PATH = os.path.join("data", "out", "aoi_manifest.json")
STATS_PATH = os.path.join(ASSETS_DIR, "story_stats.json")
BASINS_PATH = os.path.join(ASSETS_DIR, "basins_risk.geojson")
OVERLAYS_JSON = os.path.join(ASSETS_DIR, "overlays", "overlays.json")
MAX_ASSETS_BYTES = 3 * 1024 * 1024  # 3 MB


def dir_size_bytes(path):
    total = 0
    for root, _, files in os.walk(path):
        for fn in files:
            total += os.path.getsize(os.path.join(root, fn))
    return total


def main():
    errors = []

    for req in (MANIFEST_PATH, STATS_PATH, BASINS_PATH, OVERLAYS_JSON):
        if not os.path.exists(req):
            errors.append(f"Falta archivo requerido: {req}")
    if errors:
        raise SystemExit("\n".join(errors))

    def _reject_nan(c):
        raise ValueError(f"Constante JSON no estándar detectada: {c}")

    with open(MANIFEST_PATH, encoding="utf-8") as f:
        manifest = json.load(f, parse_constant=_reject_nan)
    with open(STATS_PATH, encoding="utf-8") as f:
        stats = json.load(f, parse_constant=_reject_nan)
    with open(OVERLAYS_JSON, encoding="utf-8") as f:
        overlays = json.load(f, parse_constant=_reject_nan)

    # 1. QA de serie temporal: EPSG idéntico y cobertura >= 99% en el perímetro
    qa = manifest["qa"]
    if len(qa) < 5:
        errors.append(f"Se esperaban >= 5 fechas NISAR, encontradas {len(qa)}")
    for row in qa:
        if row["epsg"] != 32629:
            errors.append(f"EPSG inesperado en {row['date']}: {row['epsg']}")
        if row["valid_pct_perimeter"] < 99.0:
            errors.append(f"Cobertura insuficiente en {row['date']}: {row['valid_pct_perimeter']}%")

    # 2. Conservación de área en clases dB (multitemporal principal y par 01-oct)
    sm = stats["severity_multitemporal"]
    sv = stats["severity_smooth"]
    for label_k, block in (("severity_multitemporal", sm), ("severity_smooth", sv)):
        sum_classes = sum(c["ha"] for c in block["classes"])
        if abs(sum_classes - block["total_valid_ha"]) > 1.0:
            errors.append(f"La suma de clases en {label_k} ({sum_classes}) != área válida ({block['total_valid_ha']})")

    # 2b. Auditoría del compuesto multitemporal (solo pasadas QA-pass, sesgo <= 0.5 dB, F1 >= 0.6 vs dNBR)
    qa_pass_dates = {row["date"] for row in qa if row["qa_pass"]}
    for dt in sm.get("post_dates", []):
        if dt not in qa_pass_dates:
            errors.append(f"Pasada post multitemporal sin QA-pass: {dt}")
    if not sm.get("post_dates"):
        errors.append("severity_multitemporal no tiene post_dates")
    if abs(sm.get("ctrl_offset_db", 0.0)) > 0.5:
        errors.append(f"Desplazamiento de control excesivo en multitemporal: {sm.get('ctrl_offset_db')} dB")
    val_dnbr = stats.get("validation_dnbr")
    if val_dnbr and val_dnbr.get("f1", 0.0) < 0.6:
        errors.append(f"F1 frente a Sentinel-2 dNBR demasiado bajo: {val_dnbr.get('f1')}")

    # 3. Monotonía de curva hectáreas vs umbral (threshold va de -0.5 a -8.0)
    curve = stats["threshold_curve"]
    for a, b in zip(curve, curve[1:]):
        if b["ha_smooth"] > a["ha_smooth"] + 0.01:
            errors.append(f"Curva no monótona entre {a['threshold_db']} y {b['threshold_db']}")

    # 4. Paridad de riesgo: cuencas 8 y 9 deben liderar el top-2
    basins = gpd.read_file(BASINS_PATH)
    top2 = set(basins.sort_values("risk_mean", ascending=False).head(2)["basin_id"].astype(int))
    if top2 != {8, 9}:
        errors.append(f"Se esperaba top-2 {{8, 9}}, obtenido {top2}")

    # 5. Claves obligatorias para la web y existencia de overlays
    for key in (
        "meta",
        "severity_multitemporal",
        "severity_smooth",
        "severity_raw_20m",
        "threshold_curve",
        "histogram",
        "polarizations",
        "timeseries",
        "basins_summary",
    ):
        if key not in stats:
            errors.append(f"Falta clave en story_stats.json: {key}")

    for name, info in overlays.items():
        rel = info["url"].replace("assets/data/", "")
        full = os.path.join(ASSETS_DIR, rel)
        if not os.path.exists(full):
            errors.append(f"Falta overlay {name}: {full}")

    # 6. Presupuesto de tamaño < 3 MB
    total_bytes = dir_size_bytes(ASSETS_DIR)
    if total_bytes > MAX_ASSETS_BYTES:
        errors.append(f"web/assets/data supera 3 MB: {total_bytes / 1e6:.2f} MB")

    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print(" -", e)
        sys.exit(1)

    f1_str = f", F1={val_dnbr['f1']}" if val_dnbr else ""
    print(
        f"VALIDATION OK: {len(qa)} fechas NISAR, {sm['burned_total_ha']} ha multitemporal "
        f"(FP={sm['fp_ctrl_pct']}%{f1_str}) vs {sv['burned_total_ha']} ha par 01-oct, "
        f"top-2 cuencas {sorted(top2)}, peso assets = {total_bytes / 1024:.1f} KB"
    )


if __name__ == "__main__":
    main()
