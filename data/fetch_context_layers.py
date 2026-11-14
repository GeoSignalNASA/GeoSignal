"""
Descarga capas de contexto reales (todas de acceso abierto, sin credenciales):
  1. OpenStreetMap (Overpass API) -> data/raw/assets.geojson
     Núcleos de población, embalses/presas aguas abajo para cruzar con cuencas.
  2. ESA WorldCover 2021 v200 (AWS COG público) -> data/out/worldcover_aoi.tif
     Cobertura del suelo a 10 m recortada al AOI (para validar árbol vs pasto/matorral).
  3. Sentinel-2 L2A COG (Earth Search AWS público) -> web/assets/data/overlays/optical_fire.png
     Imagen óptica real durante el incendio (2026-09-25, columna de humo) y bajo
     cobertura nubosa (2026-09-28) en EPSG:3857 para comparar con radar NISAR.
"""

import json
import os
import sys

import geopandas as gpd
import numpy as np
import rasterio
import requests
from PIL import Image
from rasterio.warp import Resampling, reproject, transform_bounds
from shapely.geometry import Point

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import AOI_BBOX, OUT_DIR, RAW_DIR

ASSETS_OUT = os.path.join(RAW_DIR, "assets.geojson")
WORLDCOVER_URL = (
    "/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com"
    "/v200/2021/map/ESA_WorldCover_10m_2021_v200_N39W009_Map.tif"
)
WORLDCOVER_OUT = os.path.join(OUT_DIR, "worldcover_aoi.tif")

S2_SEARCH_URL = "https://earth-search.aws.element84.com/v1/search"
S2_SCENES = [
    ("S2C_29TNG_20260925_0_L2A", "optical_fire.jpg", "Sentinel-2 L2A 2026-09-25 (incendio activo)"),
    ("S2B_29TNG_20260930_0_L2A", "optical_clouds.jpg", "Sentinel-2 L2A 2026-09-30 (91% nubes)"),
    ("S2C_29TNG_20261015_0_L2A", "optical_post.jpg", "Sentinel-2 L2A 2026-10-15 (cicatriz post-fuego)"),
]
OVERLAYS_DIR = os.path.join("web", "assets", "data", "overlays")
OPTICAL_META = os.path.join(OUT_DIR, "optical_meta.json")
DNBR_OUT = os.path.join(OUT_DIR, "s2_dnbr.tif")

# BBox ampliado para cubrir todas las microcuencas (incluye Randín, Calvos, As Meaus, Baltar, Salas)
EXTENDED_BBOX = {
    "min_lat": 41.79,
    "min_lon": -8.02,
    "max_lat": 42.02,
    "max_lon": -7.75,
}


NOMINATIM_TARGETS = [
    ("Randín, Calvos de Randín, Ourense", "Randín", "village"),
    ("Calvos, Calvos de Randín, Ourense", "Calvos", "village"),
    ("As Meaus, Baltar", "As Meaus", "hamlet"),
    ("Baltar, Ourense", "Baltar", "village"),
    ("Vila, Calvos de Randín", "Vila", "hamlet"),
    ("Rubiás, Calvos de Randín", "Rubiás", "hamlet"),
    ("Castelaus, Calvos de Randín", "Castelaus", "hamlet"),
    ("Santiago, Calvos de Randín", "Santiago de Rubiás", "hamlet"),
    ("Golpellás, Calvos de Randín", "Golpellás", "hamlet"),
    ("Lobás, Calvos de Randín", "Lobás", "hamlet"),
    ("Feás, Calvos de Randín", "Feás", "hamlet"),
    ("Guntumil, Muiños", "Guntumil", "hamlet"),
    ("Requiás, Muiños", "Requiás", "hamlet"),
    ("Maus de Salas, Muiños", "Maus de Salas", "hamlet"),
    ("Muiños, Ourense", "Muíños", "village"),
    ("Tourém, Montalegre", "Tourém (PT)", "village"),
    ("Embalse de Salas", "Embalse de Salas", "reservoir"),
    ("Encoro das Conchas", "Embalse das Conchas", "reservoir"),
]


def fetch_osm_assets():
    import time

    b = EXTENDED_BBOX
    bbox_str = f"{b['min_lat']},{b['min_lon']},{b['max_lat']},{b['max_lon']}"
    query = (
        f"[out:json][timeout:15];("
        f'node["place"="village"]({bbox_str});'
        f'node["place"="hamlet"]({bbox_str});'
        f'node["place"="town"]({bbox_str});'
        f'way["water"="reservoir"]({bbox_str});'
        f'way["waterway"="dam"]({bbox_str});'
        f");out center tags;"
    )
    rows = []
    seen = set()

    for url in ("https://overpass.kumi.systems/api/interpreter", "https://overpass-api.de/api/interpreter"):
        try:
            r = requests.post(
                url,
                data={"data": query},
                headers={"User-Agent": "GeoSignal-NASA-SpaceApps/1.0", "Accept": "application/json"},
                timeout=20,
            )
            r.raise_for_status()
            for el in r.json().get("elements", []):
                tags = el.get("tags", {})
                name = tags.get("name")
                if not name:
                    continue
                lat = el.get("lat") or el.get("center", {}).get("lat")
                lon = el.get("lon") or el.get("center", {}).get("lon")
                if lat is None or lon is None:
                    continue
                kind = (
                    tags["place"]
                    if "place" in tags
                    else ("dam" if tags.get("waterway") == "dam" else "reservoir")
                )
                key = (name.lower(), kind)
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "name": name,
                        "type": kind,
                        "population": tags.get("population"),
                        "source": "OSM Overpass",
                        "geometry": Point(float(lon), float(lat)),
                    }
                )
            if rows:
                break
        except Exception as exc:
            print(f"  warning: Overpass ({url}) no disponible: {exc}")

    if not rows:
        print("  fallback -> OSM Nominatim (1 req/s) para núcleos y embalses de la cuenca...")
        for query_str, label, kind in NOMINATIM_TARGETS:
            try:
                r = requests.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={"format": "json", "limit": 1, "q": query_str},
                    headers={"User-Agent": "GeoSignalNASA/1.0 (hackathon)"},
                    timeout=15,
                )
                r.raise_for_status()
                data = r.json()
                if data:
                    lat, lon = float(data[0]["lat"]), float(data[0]["lon"])
                    if b["min_lat"] <= lat <= b["max_lat"] and b["min_lon"] <= lon <= b["max_lon"]:
                        rows.append(
                            {
                                "name": label,
                                "type": kind,
                                "population": None,
                                "source": "OSM Nominatim",
                                "geometry": Point(lon, lat),
                            }
                        )
            except Exception as exc:
                print(f"  warning: Nominatim '{query_str}' falló ({exc})")
            time.sleep(1.05)

    if not rows:
        raise RuntimeError("No se pudieron obtener activos OSM ni por Overpass ni por Nominatim")

    gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    os.makedirs(RAW_DIR, exist_ok=True)
    gdf.to_file(ASSETS_OUT, driver="GeoJSON")
    print(f"wrote {ASSETS_OUT} ({len(gdf)} assets OSM)")


def fetch_worldcover_aoi():
    os.makedirs(OUT_DIR, exist_ok=True)
    # Usamos extensión ligeramente mayor que AOI_BBOX para cubrir el perímetro entero
    min_lon, min_lat = AOI_BBOX["min_lon"] - 0.02, AOI_BBOX["min_lat"] - 0.02
    max_lon, max_lat = AOI_BBOX["max_lon"] + 0.02, AOI_BBOX["max_lat"] + 0.02

    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", AWS_NO_SIGN_REQUEST="YES"):
        with rasterio.open(WORLDCOVER_URL) as src:
            win = rasterio.windows.from_bounds(min_lon, min_lat, max_lon, max_lat, transform=src.transform)
            win = win.round_offsets().round_lengths()
            data = src.read(1, window=win)
            win_transform = src.window_transform(win)
            profile = src.profile.copy()
            profile.update(
                driver="GTiff",
                height=data.shape[0],
                width=data.shape[1],
                transform=win_transform,
                compress="lzw",
            )
    with rasterio.open(WORLDCOVER_OUT, "w", **profile) as dst:
        dst.write(data, 1)
    print(f"wrote {WORLDCOVER_OUT} ({data.shape[1]}x{data.shape[0]} px)")


def get_target_wgs_bounds():
    """Usa exactamente los límites del cubo NISAR (aoi_manifest.json) si existe."""
    manifest_path = os.path.join(OUT_DIR, "aoi_manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as f:
            m = json.load(f)
        tf = rasterio.Affine(*m["transform"])
        h, w = m["shape"]
        b_utm = (tf.c, tf.f + tf.e * h, tf.c + tf.a * w, tf.f)
        return transform_bounds(m["crs"], "EPSG:4326", *b_utm)
    return (
        AOI_BBOX["min_lon"] - 0.015,
        AOI_BBOX["min_lat"] - 0.015,
        AOI_BBOX["max_lon"] + 0.015,
        AOI_BBOX["max_lat"] + 0.015,
    )


def fetch_sentinel2_overlays():
    os.makedirs(OVERLAYS_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    ids = [s[0] for s in S2_SCENES]
    resp = requests.post(
        S2_SEARCH_URL,
        json={"collections": ["sentinel-2-l2a"], "ids": ids},
        timeout=30,
    )
    resp.raise_for_status()
    features = {f["id"]: f for f in resp.json().get("features", [])}

    min_lon, min_lat, max_lon, max_lat = get_target_wgs_bounds()
    merc_bounds = transform_bounds("EPSG:4326", "EPSG:3857", min_lon, min_lat, max_lon, max_lat)

    meta = {}
    for scene_id, out_name, label in S2_SCENES:
        feat = features.get(scene_id)
        if not feat:
            print(f"warning: {scene_id} no encontrado en Earth Search")
            continue
        href = feat.get("assets", {}).get("visual", {}).get("href")
        if not href:
            continue
        vsi_url = f"/vsicurl/{href}"
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", AWS_NO_SIGN_REQUEST="YES"):
            with rasterio.open(vsi_url) as src:
                utm_bounds = transform_bounds("EPSG:4326", src.crs, min_lon - 0.01, min_lat - 0.01, max_lon + 0.01, max_lat + 0.01)
                win = rasterio.windows.from_bounds(*utm_bounds, transform=src.transform)
                win = win.round_offsets().round_lengths()
                src_rgb = src.read([1, 2, 3], window=win)
                src_tf = src.window_transform(win)

                out_w = 800
                out_h = round(out_w * (merc_bounds[3] - merc_bounds[1]) / (merc_bounds[2] - merc_bounds[0]))
                dst_tf = rasterio.transform.from_bounds(*merc_bounds, out_w, out_h)
                dst_rgb = np.zeros((3, out_h, out_w), dtype=np.uint8)
                for b in range(3):
                    reproject(
                        source=src_rgb[b],
                        destination=dst_rgb[b],
                        src_transform=src_tf,
                        src_crs=src.crs,
                        dst_transform=dst_tf,
                        dst_crs="EPSG:3857",
                        resampling=Resampling.bilinear,
                    )

        img = Image.fromarray(np.transpose(dst_rgb, (1, 2, 0)), mode="RGB")
        out_path = os.path.join(OVERLAYS_DIR, out_name)
        img.save(out_path, format="JPEG", quality=82, optimize=True)
        wgs_bounds = transform_bounds("EPSG:3857", "EPSG:4326", *merc_bounds)
        corners = [
            [wgs_bounds[0], wgs_bounds[3]],
            [wgs_bounds[2], wgs_bounds[3]],
            [wgs_bounds[2], wgs_bounds[1]],
            [wgs_bounds[0], wgs_bounds[1]],
        ]
        meta[out_name] = {
            "url": f"assets/data/overlays/{out_name}",
            "scene_id": scene_id,
            "datetime": feat["properties"].get("datetime"),
            "cloud_cover": feat["properties"].get("eo:cloud_cover"),
            "label": label,
            "coordinates": corners,
        }
        print(f"wrote {out_path} ({out_w}x{out_h}, {os.path.getsize(out_path) // 1024} KB)")

    with open(OPTICAL_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"wrote {OPTICAL_META}")


def compute_sentinel2_dnbr():
    """Calcula dNBR real (20-sep -> 15-oct) alineado a la rejilla exacta de aoi_manifest.json."""
    manifest_path = os.path.join(OUT_DIR, "aoi_manifest.json")
    if not os.path.exists(manifest_path):
        print("skip dNBR: falta data/out/aoi_manifest.json")
        return
    with open(manifest_path, encoding="utf-8") as f:
        m = json.load(f)
    aoi_tf = rasterio.Affine(*m["transform"])
    h, w = m["shape"]
    min_lon, min_lat, max_lon, max_lat = get_target_wgs_bounds()

    resp = requests.post(
        S2_SEARCH_URL,
        json={"collections": ["sentinel-2-l2a"], "ids": ["S2B_29TNG_20260920_0_L2A", "S2C_29TNG_20261015_0_L2A"]},
        timeout=30,
    )
    resp.raise_for_status()
    feats = {f["id"]: f for f in resp.json().get("features", [])}

    def read_nbr(feat):
        bands = {}
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", AWS_NO_SIGN_REQUEST="YES"):
            for key, asset in (("b8", "nir08"), ("b12", "swir22"), ("scl", "scl")):
                href = feat["assets"][asset]["href"]
                with rasterio.open(f"/vsicurl/{href}") as src:
                    ub = transform_bounds("EPSG:4326", src.crs, min_lon - 0.01, min_lat - 0.01, max_lon + 0.01, max_lat + 0.01)
                    win = rasterio.windows.from_bounds(*ub, transform=src.transform).round_offsets().round_lengths()
                    src_arr = src.read(1, window=win)
                    dst = np.zeros((h, w), dtype=np.float32)
                    reproject(
                        src_arr,
                        dst,
                        src_transform=src.window_transform(win),
                        src_crs=src.crs,
                        dst_transform=aoi_tf,
                        dst_crs=m["crs"],
                        resampling=Resampling.nearest if key == "scl" else Resampling.bilinear,
                    )
                    bands[key] = dst
        scl = np.round(bands["scl"]).astype(int)
        valid = (bands["b8"] > 0) & (bands["b12"] > 0) & (~np.isin(scl, [0, 1, 3, 8, 9, 10]))
        return np.where(valid, (bands["b8"] - bands["b12"]) / (bands["b8"] + bands["b12"] + 1e-6), np.nan).astype(np.float32)

    dnbr = (read_nbr(feats["S2B_29TNG_20260920_0_L2A"]) - read_nbr(feats["S2C_29TNG_20261015_0_L2A"])).astype(np.float32)
    with rasterio.open(
        DNBR_OUT,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=1,
        dtype="float32",
        crs=m["crs"],
        transform=aoi_tf,
        nodata=np.nan,
        compress="lzw",
    ) as dst:
        dst.write(dnbr, 1)
    print(f"wrote {DNBR_OUT} ({w}x{h} px)")


if __name__ == "__main__":
    fetch_osm_assets()
    fetch_worldcover_aoi()
    fetch_sentinel2_overlays()
    compute_sentinel2_dnbr()
