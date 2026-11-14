"""
Simulación 3D de lluvia-escorrentía (PyVista) para el capítulo 08 del StoryMap.

Sustituye a las trazas 2D de `simulate_rain.py` por una simulación temporal
sobre el relieve real:

  1. Delimita la cuenca que drena el perímetro quemado hasta el borde de la
     teja GLO-30 (puntero D8 de WhiteboxTools ya calculado por
     `delineate_basins.py`).
  2. Hace llover de forma uniforme durante 24 h y enruta el agua celda a
     celda (onda cinemática explícita, Manning) siguiendo el D8.
  3. Arrastra un trazador con el agua generada DENTRO del perímetro EFFIS,
     para ver por dónde baja y cuándo llega al Embalse de Salas.
  4. Renderiza cada instante sobre el DEM en 3D con PyVista (off-screen) y
     codifica un MP4 por escenario de lluvia con ffmpeg.

Qué es real y qué es supuesto
-----------------------------
Real: relieve, direcciones de flujo, áreas contribuyentes, perímetro EFFIS,
lámina del embalse (zona plana del DEM en la cota del punto OSM).
Supuesto (igual que en la web): la lluvia (mm en 24 h, uniforme), el
coeficiente de escorrentía C = 0,6 y además los parámetros hidráulicos de
abajo (rugosidad de Manning, anchura de cauce, velocidad máxima). El embalse
se trata como sumidero: retiene todo lo que entra, sin vertido. Los tiempos
de llegada son por tanto órdenes de magnitud, no una predicción de avenida.

Uso (desde la raíz del repo):
    data/.venv/bin/python data/simulate_rain_pyvista.py
    data/.venv/bin/python data/simulate_rain_pyvista.py --rain-mm 60 --preview /tmp/prev

Salidas:
    web/assets/video/rain_sim_<mm>mm.mp4 + .jpg (póster)
    web/assets/data/rain_sim.json  (métricas e hidrogramas para la web)
"""

import argparse
import json
import math
import os
import subprocess
import sys

import geopandas as gpd
import numpy as np
import pyvista as pv
import rasterio
from rasterio import features
from rasterio.windows import Window
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import EFFIS_PERIMETER_GEOJSON, RAW_DIR  # noqa: E402

# --- Entradas -------------------------------------------------------------
POINTER_TIF = os.path.join(RAW_DIR, "hydro", "d8_pointer.tif")
ACCUM_TIF = os.path.join(RAW_DIR, "hydro", "d8_accum.tif")
FILLED_DEM_TIF = os.path.join(RAW_DIR, "hydro", "filled_dem.tif")
RAW_DEM_TIF = os.path.join(RAW_DIR, "copernicus_dem_glo30_n41_w008_wbt.tif")
ASSETS_GEOJSON = os.path.join(RAW_DIR, "assets.geojson")
RESERVOIR_NAME = "Embalse de Salas"

VIDEO_DIR = os.path.join("web", "assets", "video")
JSON_OUT = os.path.join("web", "assets", "data", "rain_sim.json")

# Puntero D8 en convención WhiteboxTools (NO la de ESRI):
#   64 128   1
#   32   0   2
#   16   8   4
WBT_DIRS = {1: (-1, 1), 2: (0, 1), 4: (1, 1), 8: (1, 0), 16: (1, -1), 32: (0, -1), 64: (-1, -1), 128: (-1, 0)}

# --- Escenario (supuestos) ------------------------------------------------
RUNOFF_COEFF = 0.6          # mismo C que el resto de la web
STORM_HOURS = 24.0          # la lluvia cae uniforme durante 24 h
SIM_HOURS = 36.0            # 24 h de lluvia + 12 h de recesión
DT_S = 10.0                 # paso de tiempo explícito
V_MAX = 2.0                 # m/s, tope de velocidad (y garantía CFL)
MIN_SLOPE = 0.002           # m/m, evita velocidad nula en llanos rellenados
CHANNEL_MIN_KM2 = 0.25      # área contribuyente a partir de la cual hay cauce
N_HILLSLOPE = 0.10          # Manning, flujo laminar sobre ladera
N_CHANNEL = 0.05            # Manning, torrente de montaña
CHANNEL_WIDTH_COEFF = 1.5   # anchura de cauce [m] = coef * sqrt(A [km2])
RECORD_EVERY_S = 300.0      # resolución del hidrograma exportado

# --- Render ---------------------------------------------------------------
FPS = 24
N_FRAMES = 288              # 12 s
SIZE = (1120, 840)
VERT_EXAG = 2.2
MARGIN_CELLS = 16
BG = "#12100c"              # mismo fondo que el mapa de la web
C_WATER = np.array([61, 155, 255], np.float32)       # escorrentía de la cuenca
C_MIX = np.array([240, 172, 72], np.float32)         # ámbar (mezcla)
C_BURN = np.array([226, 121, 60], np.float32)        # --accent (agua del perímetro)
C_PERIM = "#39e8e0"                                  # perímetro EFFIS (--cyan)
C_LABEL = "#ede6da"
LABEL_WHITELIST = (
    "Embalse de Salas", "Calvos de Randín", "Randín", "As Meaus", "Tourém (PT)",
    "Maus de Salas", "Requiás", "Muíños",
)


def m_per_deg(lat):
    return 111_320.0 * math.cos(math.radians(lat)), 111_320.0


def frame_schedule(n_frames):
    """Horas simuladas de cada fotograma: más fotogramas para la crecida y la recesión."""
    u = np.linspace(0.0, 1.0, n_frames)
    return np.interp(u, [0.0, 0.42, 0.62, 1.0], [0.0, 8.0, STORM_HOURS, SIM_HOURS])


# ---------------------------------------------------------------------------
# 1. Dominio: cuenca que drena el perímetro, recortada del DEM
# ---------------------------------------------------------------------------
def build_domain():
    with rasterio.open(POINTER_TIF) as src:
        pntr = src.read(1)
        transform = src.transform
    H, W = pntr.shape

    dr = np.zeros((H, W), np.int32)
    dc = np.zeros((H, W), np.int32)
    for code, (a, b) in WBT_DIRS.items():
        m = pntr == code
        dr[m], dc[m] = a, b
    rr, cc = np.mgrid[0:H, 0:W]
    r2, c2 = rr + dr, cc + dc
    flows = (pntr > 0) & (r2 >= 0) & (r2 < H) & (c2 >= 0) & (c2 < W)
    idx = np.arange(H * W).reshape(H, W)
    down = np.where(flows, np.clip(r2, 0, H - 1) * W + np.clip(c2, 0, W - 1), idx).ravel()
    del rr, cc, r2, c2

    # Celda terminal de cada celda por "pointer jumping" (log2 iteraciones)
    root = down.copy()
    while True:
        nxt = root[root]
        if np.array_equal(nxt, root):
            break
        root = nxt

    perim = gpd.read_file(EFFIS_PERIMETER_GEOJSON).to_crs("EPSG:4326")
    geom = perim.geometry.iloc[0]
    burned_full = features.geometry_mask([geom], out_shape=(H, W), transform=transform, invert=True)
    roots, counts = np.unique(root[burned_full.ravel()], return_counts=True)
    outlet = int(roots[counts.argmax()])
    burned_in_basin_pct = 100.0 * counts.max() / counts.sum()
    basin_full = (root == outlet).reshape(H, W)

    rows = np.where(basin_full.any(axis=1))[0]
    cols = np.where(basin_full.any(axis=0))[0]
    r0, r1 = max(rows[0] - MARGIN_CELLS, 0), min(rows[-1] + MARGIN_CELLS + 1, H)
    c0, c1 = max(cols[0] - MARGIN_CELLS, 0), min(cols[-1] + MARGIN_CELLS + 1, W)
    win = Window(c0, r0, c1 - c0, r1 - r0)
    sl = (slice(r0, r1), slice(c0, c1))

    with rasterio.open(ACCUM_TIF) as src:
        accum = src.read(1, window=win).astype(np.float64)
    with rasterio.open(FILLED_DEM_TIF) as src:
        z_fill = src.read(1, window=win).astype(np.float64)
    with rasterio.open(RAW_DEM_TIF) as src:
        z_raw = src.read(1, window=win).astype(np.float64)

    h, w = z_raw.shape
    lon0 = transform.c + (c0 + 0.5) * transform.a
    lat0 = transform.f + (r0 + 0.5) * transform.e
    lons = lon0 + np.arange(w) * transform.a
    lats = lat0 + np.arange(h) * transform.e
    dx, dy = m_per_deg(float(lats.mean()))
    dx *= abs(transform.a)
    dy *= abs(transform.e)

    dom = {
        "transform": transform, "r0": r0, "c0": c0, "h": h, "w": w,
        "lons": lons, "lats": lats, "dx": dx, "dy": dy, "cell_area": dx * dy,
        "pntr": pntr[sl], "dr": dr[sl], "dc": dc[sl], "accum": accum,
        "z_fill": z_fill, "z_raw": z_raw, "basin": basin_full[sl], "burned": burned_full[sl],
        "geom": geom, "burned_in_basin_pct": burned_in_basin_pct,
        "outlet_lonlat": rasterio.transform.xy(transform, outlet // W, outlet % W),
    }

    # Lámina del embalse: zona plana conectada del DEM a la cota del punto OSM
    dom["reservoir"] = np.zeros((h, w), bool)
    dom["assets"] = []
    if os.path.exists(ASSETS_GEOJSON):
        assets = gpd.read_file(ASSETS_GEOJSON).to_crs("EPSG:4326")
        for _, a in assets.iterrows():
            col = int(round((a.geometry.x - lons[0]) / transform.a))
            row = int(round((a.geometry.y - lats[0]) / transform.e))
            if 0 <= row < h and 0 <= col < w:
                dom["assets"].append({"name": a["name"], "type": a["type"], "row": row, "col": col})
        res = next((a for a in dom["assets"] if a["name"] == RESERVOIR_NAME), None)
        if res is not None:
            level = z_raw[res["row"], res["col"]]
            labels, _ = ndimage.label(np.abs(z_raw - level) < 0.05)
            lab = labels[res["row"], res["col"]]
            if lab:
                dom["reservoir"] = (labels == lab) & dom["basin"]
    return dom


# ---------------------------------------------------------------------------
# 2. Modelo de escorrentía (onda cinemática explícita sobre D8)
# ---------------------------------------------------------------------------
class RunoffModel:
    def __init__(self, dom, rain_mm):
        self.dom = dom
        self.rain_mm = rain_mm
        act = dom["basin"]
        n = int(act.sum())
        self.n = n
        self.active = act
        id_map = np.full(act.shape, n, np.int64)  # n = sumidero (fuera del dominio)
        id_map[act] = np.arange(n)

        rows, cols = np.nonzero(act)
        dr, dc = dom["dr"][act], dom["dc"][act]
        r2, c2 = rows + dr, cols + dc
        ok = (dom["pntr"][act] > 0) & (r2 >= 0) & (r2 < dom["h"]) & (c2 >= 0) & (c2 < dom["w"])
        r2c, c2c = np.clip(r2, 0, dom["h"] - 1), np.clip(c2, 0, dom["w"] - 1)
        self.down = np.where(ok, id_map[r2c, c2c], n)

        dx, dy, area = dom["dx"], dom["dy"], dom["cell_area"]
        length = np.hypot(dr * dy, dc * dx)
        length[length == 0] = dy
        dz = dom["z_fill"][act] - np.where(ok, dom["z_fill"][r2c, c2c], dom["z_fill"][act])
        slope = np.maximum(dz / length, MIN_SLOPE)

        a_km2 = dom["accum"][act] * area / 1e6
        channel = a_km2 >= CHANNEL_MIN_KM2
        width = np.where(channel, np.maximum(CHANNEL_WIDTH_COEFF * np.sqrt(a_km2), 1.0), math.sqrt(area))
        n_man = np.where(channel, N_CHANNEL, N_HILLSLOPE)

        self.reservoir = dom["reservoir"][act]
        self.inv_wl = 1.0 / (width * length)                 # calado h = S / (w·L)
        self.kf = np.sqrt(slope) / n_man * DT_S / length     # f = kf · h^(2/3)
        self.kf[self.reservoir] = 0.0                        # el embalse retiene
        self.fcap = np.minimum(V_MAX * DT_S / length, 1.0)
        down_res = np.append(self.reservoir, False)[self.down]
        self.into_res = down_res & ~self.reservoir

        src = (rain_mm / 1000.0) * RUNOFF_COEFF * area / (STORM_HOURS * 3600.0) * DT_S
        self.src = np.full(n, src)
        self.src_burn = np.where(dom["burned"][act], src, 0.0)

        self.S = np.zeros(n)   # agua almacenada por celda [m3]
        self.B = np.zeros(n)   # ...de la cual procede del perímetro quemado
        self.out = np.zeros(n)
        self.out_b = np.zeros(n)
        self.left_domain = 0.0
        self.rained = 0.0
        self.rec_t, self.rec_q, self.rec_qb = [], [], []
        self._acc_q = self._acc_qb = 0.0
        self._acc_n = 0
        self.step_i = 0

    def step(self):
        t = self.step_i * DT_S
        if t < STORM_HOURS * 3600.0:
            self.S += self.src
            self.B += self.src_burn
            self.rained += self.src.sum()
        h = self.S * self.inv_wl
        f = np.minimum(self.kf * np.cbrt(h) ** 2, self.fcap)
        out = self.S * f
        out_b = self.B * f
        self.S -= out
        self.B -= out_b
        moved = np.bincount(self.down, weights=out, minlength=self.n + 1)
        self.S += moved[: self.n]
        self.left_domain += moved[self.n]
        self.B += np.bincount(self.down, weights=out_b, minlength=self.n + 1)[: self.n]
        self.out, self.out_b = out, out_b

        self._acc_q += out[self.into_res].sum()
        self._acc_qb += out_b[self.into_res].sum()
        self._acc_n += 1
        self.step_i += 1
        if self._acc_n * DT_S >= RECORD_EVERY_S:
            span = self._acc_n * DT_S
            self.rec_t.append(self.step_i * DT_S / 3600.0)
            self.rec_q.append(self._acc_q / span)
            self.rec_qb.append(self._acc_qb / span)
            self._acc_q = self._acc_qb = 0.0
            self._acc_n = 0

    def advance_to(self, hours):
        target = int(round(hours * 3600.0 / DT_S))
        while self.step_i < target:
            self.step()

    def fields(self):
        """Caudal total y caudal procedente del perímetro [m3/s] en la rejilla 2D."""
        q = np.zeros(self.active.shape)
        qb = np.zeros(self.active.shape)
        q[self.active] = self.out / DT_S
        qb[self.active] = self.out_b / DT_S
        return q, qb

    def reservoir_state(self):
        s = self.S[self.reservoir].sum()
        b = self.B[self.reservoir].sum()
        return s, b

    def summary(self):
        t = np.array(self.rec_t)
        q = np.array(self.rec_q)
        qb = np.array(self.rec_qb)
        res_s, res_b = self.reservoir_state()
        balance = self.S.sum() + self.left_domain
        out = {
            "rain_mm": self.rain_mm,
            "mass_balance_error": float(abs(balance - self.rained) / max(self.rained, 1e-9)),
            "runoff_total_hm3": round(self.rained / 1e6, 3),
        }
        if self.reservoir.any() and qb.max() > 0:
            arrival = float(t[np.argmax(qb >= 0.1 * qb.max())])
            out.update({
                "reservoir_peak_inflow_m3s": round(float(q.max()), 1),
                "burned_peak_inflow_m3s": round(float(qb.max()), 2),
                "burned_arrival_hour": round(arrival, 1),
                "reservoir_inflow_hm3": round(res_s / 1e6, 3),
                "reservoir_burned_hm3": round(res_b / 1e6, 3),
                "reservoir_burned_pct": round(100.0 * res_b / max(res_s, 1e-9), 1),
            })
        return out, t, q, qb


# ---------------------------------------------------------------------------
# 3. Escena PyVista
# ---------------------------------------------------------------------------
def hillshade(z, dx, dy, az_deg=235.0, alt_deg=42.0):
    gy, gx = np.gradient(z, dy, dx)          # gy: hacia el sur (filas crecen al sur)
    nx, ny, nz = -gx, gy, np.ones_like(z)    # normal en ejes este / norte / arriba
    norm = np.sqrt(nx**2 + ny**2 + nz**2)
    az, alt = math.radians(az_deg), math.radians(alt_deg)
    lx, ly, lz = math.sin(az) * math.cos(alt), math.cos(az) * math.cos(alt), math.sin(alt)
    return np.clip((nx * lx + ny * ly + nz * lz) / norm, 0.0, 1.0)


class Scene:
    def __init__(self, dom, size=SIZE):
        self.dom = dom
        h, w = dom["h"], dom["w"]
        dx, dy = dom["dx"], dom["dy"]
        self.x = np.arange(w) * dx
        self.y = (h - 1 - np.arange(h)) * dy             # norte arriba
        self.z0 = float(np.percentile(dom["z_raw"], 1))
        self.zs = (dom["z_raw"] - self.z0) * VERT_EXAG
        self.lx, self.ly = float(self.x[-1]), float(self.y[0])
        self.ztop = float(self.zs.max())

        X, Y = np.meshgrid(self.x, self.y)
        self.grid = pv.StructuredGrid(X, Y, self.zs)
        self.base = self._base_colors()
        self.grid.point_data["rgb"] = self._to_points(self.base)

        pv.global_theme.allow_empty_mesh = True
        self.pl = pv.Plotter(off_screen=True, window_size=list(size))
        self.pl.set_background(BG)
        self.pl.add_mesh(self.grid, scalars="rgb", rgb=True, lighting=False, show_scalar_bar=False)
        self._add_perimeter()
        self._add_labels()
        self._init_rain()
        try:
            self.pl.enable_anti_aliasing("ssaa")
        except Exception:
            pass

    def _to_points(self, rgb):
        """(h, w, 3) float -> uint8 en el orden de puntos de StructuredGrid (Fortran)."""
        arr = np.clip(rgb, 0, 255).astype(np.uint8)
        return np.ascontiguousarray(arr.transpose(1, 0, 2)).reshape(-1, 3)

    def _base_colors(self):
        dom = self.dom
        z = dom["z_raw"]
        t = np.clip((z - np.percentile(z, 2)) / (np.percentile(z, 98) - np.percentile(z, 2)), 0, 1)
        lo = np.array([58, 60, 50], np.float32)
        hi = np.array([150, 138, 116], np.float32)
        albedo = lo + (hi - lo) * t[..., None]
        shade = 0.32 + 0.95 * hillshade(z * VERT_EXAG, dom["dx"], dom["dy"])
        rgb = albedo * shade[..., None]
        # fuera de la cuenca simulada: contexto atenuado
        out = ~dom["basin"]
        gray = rgb.mean(axis=-1, keepdims=True)
        rgb = np.where(out[..., None], (0.6 * gray + 0.4 * rgb) * 0.52, rgb)
        # perímetro quemado: tinte de brasa
        ember = np.array([150, 62, 34], np.float32) * shade[..., None]
        rgb = np.where(dom["burned"][..., None], 0.5 * rgb + 0.5 * ember, rgb)
        return rgb.astype(np.float32)

    def _xyz(self, lon, lat, lift=0.0):
        dom = self.dom
        t = dom["transform"]
        col = (np.asarray(lon) - dom["lons"][0]) / t.a
        row = (np.asarray(lat) - dom["lats"][0]) / t.e
        z = ndimage.map_coordinates(self.zs, [np.atleast_1d(row), np.atleast_1d(col)], order=1, mode="nearest")
        return np.c_[np.atleast_1d(col) * dom["dx"], (dom["h"] - 1 - np.atleast_1d(row)) * dom["dy"], z + lift]

    def _add_perimeter(self):
        ring = self.dom["geom"].exterior
        d = np.linspace(0, ring.length, 600)
        pts = [ring.interpolate(v) for v in d]
        xyz = self._xyz([p.x for p in pts], [p.y for p in pts], lift=45.0)
        self.pl.add_mesh(pv.lines_from_points(xyz, close=True), color=C_PERIM, line_width=2.6, lighting=False)

    def _add_labels(self):
        dom = self.dom
        items = [a for a in dom["assets"] if a["name"] in LABEL_WHITELIST]
        if not items:
            return
        lon = [dom["lons"][a["col"]] for a in items]
        lat = [dom["lats"][a["row"]] for a in items]
        xyz = self._xyz(lon, lat, lift=120.0)
        res = np.array([a["type"] == "reservoir" for a in items])
        for mask, color in ((res, "#39b8ff"), (~res, "#f6c963")):
            if mask.any():
                self.pl.add_points(xyz[mask], color=color, point_size=9, render_points_as_spheres=True, lighting=False)
        self.pl.add_point_labels(
            xyz, [a["name"] for a in items], font_size=15, text_color=C_LABEL, shape=None,
            show_points=False, always_visible=True, shadow=True, bold=False, margin=6,
        )

    # --- lluvia: trazos que caen ---
    def _init_rain(self):
        self.rng = np.random.default_rng(7)
        self.rain_n = 0
        self.rain_mesh = pv.PolyData()
        self.rain_actor = None
        self.rain_top = self.ztop + 3800.0

    def set_rain_intensity(self, rain_mm):
        if self.rain_actor is not None:
            self.pl.remove_actor(self.rain_actor)
        n = int(np.clip(rain_mm * 22, 400, 3400))
        self.rain_n = n
        pad = 1500.0
        self.rain_xy = np.c_[self.rng.uniform(-pad, self.lx + pad, n), self.rng.uniform(-pad, self.ly + pad, n)]
        self.rain_phase = self.rng.uniform(0, 1, n)
        self.rain_speed = self.rng.uniform(0.85, 1.25, n)
        self.rain_len = self.rng.uniform(260.0, 520.0, n) * (0.8 + rain_mm / 150.0)
        lines = np.c_[np.full(n, 2), np.arange(n) * 2, np.arange(n) * 2 + 1].ravel()
        self.rain_mesh = pv.PolyData(np.zeros((2 * n, 3)), lines=lines)
        opacity = float(np.clip(0.26 + rain_mm / 700.0, 0.26, 0.44))
        self.rain_actor = self.pl.add_mesh(self.rain_mesh, color="#b9d3f2", line_width=1.3, opacity=opacity, lighting=False)

    def update_rain(self, frame, raining):
        self.rain_actor.SetVisibility(bool(raining))
        if not raining:
            return
        fall = self.rain_top + 600.0
        ph = (self.rain_phase + frame * self.rain_speed / 20.0) % 1.0
        z_head = self.rain_top - ph * fall
        slant = 0.22  # viento del oeste
        pts = np.empty((2 * self.rain_n, 3))
        pts[0::2, 0] = self.rain_xy[:, 0] + (self.rain_top - z_head) * slant
        pts[0::2, 1] = self.rain_xy[:, 1]
        pts[0::2, 2] = z_head
        pts[1::2, 0] = pts[0::2, 0] - self.rain_len * slant
        pts[1::2, 1] = self.rain_xy[:, 1]
        pts[1::2, 2] = z_head + self.rain_len
        self.rain_mesh.points = pts

    # --- agua sobre el relieve ---
    def paint_water(self, q, qb, lake_frac):
        qd, bd = q.copy(), qb.copy()
        # ensancha los cauces según su caudal para que se lean en el vídeo
        for thr, size in ((0.05, 3), (1.0, 5), (8.0, 7)):
            m = q >= thr
            if not m.any():
                continue
            qd = np.maximum(qd, ndimage.maximum_filter(np.where(m, q, 0.0), size=size))
            bd = np.maximum(bd, ndimage.maximum_filter(np.where(m, qb, 0.0), size=size))
        alpha = np.clip((np.log10(qd + 1e-12) + 3.0) / 3.7, 0.0, 1.0) ** 1.25 * 0.94
        frac = bd / np.maximum(qd, 1e-12)

        lake = self.dom["reservoir"]
        alpha[lake] = 0.93
        frac[lake] = lake_frac

        g = np.clip(frac / 0.35, 0.0, 1.0) ** 0.6
        g = g[..., None]
        water = np.where(g < 0.5, C_WATER + (C_MIX - C_WATER) * (g / 0.5), C_MIX + (C_BURN - C_MIX) * ((g - 0.5) / 0.5))
        a = alpha[..., None]
        rgb = self.base * (1.0 - a) + water * a
        self.grid.point_data["rgb"] = self._to_points(rgb)

    def set_camera(self, u):
        """Vista oblicua desde el sur con una órbita lenta (u en 0..1)."""
        focal = np.array([self.lx * 0.5, self.ly * 0.5, self.ztop * 0.18])
        az = math.radians(-5.0 + 10.0 * u)
        el = math.radians(41.0)
        dist = self.lx * 1.34
        pos = focal + dist * np.array([math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)])
        self.pl.camera.position = tuple(pos)
        self.pl.camera.focal_point = tuple(focal)
        self.pl.camera.up = (0, 0, 1)
        self.pl.camera.view_angle = 30.0
        self.pl.camera.clipping_range = (dist * 0.05, dist * 4.0)

    def frame(self):
        self.pl.render()
        return np.ascontiguousarray(self.pl.screenshot(return_img=True)[..., :3])


# ---------------------------------------------------------------------------
# 4. Bucle por escenario
# ---------------------------------------------------------------------------
def open_ffmpeg(path, size, crf):
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{size[0]}x{size[1]}", "-r", str(FPS), "-i", "-", "-an",
        "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", path,
    ]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def run_scenario(dom, scene, rain_mm, hours, args):
    from PIL import Image

    model = RunoffModel(dom, rain_mm)
    scene.set_rain_intensity(rain_mm)
    name = f"rain_sim_{int(rain_mm):03d}mm"
    video_path = os.path.join(VIDEO_DIR, name + ".mp4")
    poster_path = os.path.join(VIDEO_DIR, name + ".jpg")
    preview_frames = set(np.linspace(0, len(hours) - 1, 7).astype(int)) if args.preview else set()
    proc = None if args.preview else open_ffmpeg(video_path, scene.pl.window_size, args.crf)
    poster_i = int(np.argmin(np.abs(hours - 10.0)))

    for i, th in enumerate(hours):
        model.advance_to(th)
        if args.preview and i not in preview_frames:
            continue
        q, qb = model.fields()
        res_s, res_b = model.reservoir_state()
        scene.paint_water(q, qb, res_b / res_s if res_s > 0 else 0.0)
        scene.update_rain(i, th < STORM_HOURS)
        scene.set_camera(i / (len(hours) - 1))
        img = scene.frame()
        if args.preview:
            Image.fromarray(img).save(os.path.join(args.preview, f"{name}_f{i:03d}_{th:04.1f}h.png"))
        else:
            proc.stdin.write(img.tobytes())
            if i == poster_i:
                Image.fromarray(img).save(poster_path, quality=82)

    if proc is not None:
        proc.stdin.close()
        if proc.wait() != 0:
            raise SystemExit(f"ffmpeg falló al escribir {video_path}")

    summary, t, q, qb = model.summary()
    if summary["mass_balance_error"] > 1e-6:
        raise SystemExit(f"Balance de masa roto en {rain_mm} mm: {summary['mass_balance_error']:.2e}")
    summary["hydrograph_q_m3s"] = [round(float(v), 2) for v in np.interp(hours, t, q, left=0.0)]
    summary["hydrograph_burned_m3s"] = [round(float(v), 3) for v in np.interp(hours, t, qb, left=0.0)]
    if not args.preview:
        summary["video"] = f"assets/video/{name}.mp4"
        summary["poster"] = f"assets/video/{name}.jpg"
        summary["video_kb"] = round(os.path.getsize(video_path) / 1024)
    print(
        f"  {rain_mm:>5.0f} mm: punta embalse {summary.get('reservoir_peak_inflow_m3s')} m3/s, "
        f"llegada agua del perímetro h {summary.get('burned_arrival_hour')}, "
        f"entra {summary.get('reservoir_inflow_hm3')} hm3 ({summary.get('reservoir_burned_pct')}% del perímetro), "
        f"error de masa {summary['mass_balance_error']:.1e}"
    )
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rain-mm", type=float, nargs="+", default=[30, 60, 90, 120, 150])
    ap.add_argument("--frames", type=int, default=N_FRAMES)
    ap.add_argument("--crf", type=int, default=27)
    ap.add_argument("--preview", metavar="DIR", help="guarda 7 PNG por escenario en DIR y no escribe vídeo ni JSON")
    args = ap.parse_args()

    dom = build_domain()
    area = dom["cell_area"]
    info = {
        "basin_km2": round(float(dom["basin"].sum() * area / 1e6), 1),
        "burned_km2_in_basin": round(float((dom["burned"] & dom["basin"]).sum() * area / 1e6), 2),
        "burned_in_basin_pct": round(dom["burned_in_basin_pct"], 1),
        "reservoir_km2": round(float(dom["reservoir"].sum() * area / 1e6), 2),
        "outlet_lonlat": [round(float(v), 4) for v in dom["outlet_lonlat"]],
        "grid": [dom["h"], dom["w"]],
        "cell_m": [round(dom["dx"], 1), round(dom["dy"], 1)],
    }
    print("dominio:", json.dumps(info))

    os.makedirs(VIDEO_DIR, exist_ok=True)
    if args.preview:
        os.makedirs(args.preview, exist_ok=True)
    hours = frame_schedule(args.frames)
    scene = Scene(dom)
    scenarios = [run_scenario(dom, scene, mm, hours, args) for mm in args.rain_mm]
    scene.pl.close()
    if args.preview:
        print(f"previsualización en {args.preview}")
        return

    payload = {
        "generated_by": "data/simulate_rain_pyvista.py",
        "fps": FPS,
        "storm_hours": STORM_HOURS,
        "sim_hours": SIM_HOURS,
        "frame_hours": [round(float(v), 3) for v in hours],
        "domain": info,
        "assumptions": {
            "runoff_coeff": RUNOFF_COEFF, "manning_hillslope": N_HILLSLOPE, "manning_channel": N_CHANNEL,
            "channel_min_km2": CHANNEL_MIN_KM2, "channel_width_m": f"{CHANNEL_WIDTH_COEFF}*sqrt(A_km2)",
            "v_max_ms": V_MAX, "dt_s": DT_S, "reservoir": "sumidero sin vertido",
        },
        "scenarios": scenarios,
    }
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print(f"wrote {JSON_OUT} y {len(scenarios)} vídeos en {VIDEO_DIR}")


if __name__ == "__main__":
    main()
