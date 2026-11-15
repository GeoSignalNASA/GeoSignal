import { I18N } from "./i18n.js";
import { renderPhysicsDiagrams } from "./physics.js";
import { renderHistogramChart, renderThresholdCurve, renderTimeseriesChart } from "./charts.js";

const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const RUNOFF_COEFF = 0.6;
const DEM_TILE_EDGE_LON = -8.0;
const REGION_BOUNDS = [
  [-8.42, 41.65],
  [-7.40, 42.18],
];
const MIN_ZOOM = 10.2;
const MAX_ZOOM = 15.0;

const OVERLAY_LABELS = {
  "hv_pre.png": "NISAR Banda L · HV pre (19-sep)",
  "hv_post.png": "NISAR Banda L · HV post (01-oct)",
  "dhv_classes.png": "NISAR Banda L · Severidad ΔHV (01-oct)",
  "dhv_oct01_cal.png": "NISAR Banda L · ΔHV 01-oct sin sesgo",
  "dhv_oct25.png": "NISAR Banda L · Severidad ΔHV (25-oct seco)",
  "dhv_cont.png": "NISAR Banda L · ΔHV continuo",
  "dhh.png": "NISAR Banda L · ΔHH (doble rebote)",
  "dnbr_s2.png": "Sentinel-2 dNBR (20-sep → 15-oct)",
  "optical_fire.jpg": "Sentinel-2 L2A 2026-09-25 (incendio activo)",
  "optical_clouds.jpg": "Sentinel-2 L2A 2026-09-30 (91% nubes)",
  "optical_post.jpg": "Sentinel-2 L2A 2026-10-15 (cicatriz post-fuego)",
};

let STATS = null;
let OVERLAYS = null;
let BASINS_GJ = null;
let ASSETS_GJ = null;
let RAIN_SEGS_GJ = null;
let FIRE_GJ = null;
let BARRIERS_GJ = null;

let map = null;
let compareInit = false;
let compareControl = null;
let lastCompareWidth = 0;
let beforeMap = null;
let afterMap = null;
let q8Pixels = null; // { data, width, height, coordinates }
let activeLang = "es";
let activeStep = "summary";
let activeSeriesDate = "2026-10-01";
let activeDbThreshold = -1.5;
let activeBasinThreshold = "risk_mean";
let activeRainMm = 60;
let activeDhbMode = "classes"; // "classes" | "oct01_cal" | "oct25" | "threshold" | "continuous"
let activeCap2HvKey = "hv_pre.png";
let activeOptKey = "optical_fire.jpg";
let activeRadKey = "dhv_classes.png";
let assetMarkers = [];
let assetMarkersVisible = true;
let selectedBarrierIdx = -1;

function darkBaseStyle() {
  return {
    version: 8,
    sources: {
      osm: {
        type: "raster",
        tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
        tileSize: 256,
        maxzoom: 19,
        attribution: "© OpenStreetMap contributors",
      },
    },
    layers: [
      { id: "bg", type: "background", paint: { "background-color": "#ECE4D4" } },
      {
        id: "basemap",
        type: "raster",
        source: "osm",
        paint: {
          "raster-opacity": 0.9,
          "raster-saturation": -0.78,
          "raster-brightness-min": 0.06,
          "raster-contrast": -0.08,
        },
      },
    ],
  };
}

function fmtEs(n, digits = 0) {
  const locale = I18N[activeLang]?.dynamic?.locale || "es-ES";
  return Number(n).toLocaleString(locale, { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

function getBlockCenter() {
  const coords = OVERLAYS?.["hv_pre.png"]?.coordinates;
  if (!coords || coords.length < 4) return [-7.88, 41.91];
  const lng = (coords[0][0] + coords[1][0]) / 2;
  const lat = (coords[0][1] + coords[2][1]) / 2;
  return [lng, lat];
}

function getOverlayLabel(key) {
  const dict = I18N[activeLang];
  if (activeLang === "en" && dict?.overlayLabels?.[key]) return dict.overlayLabels[key];
  return OVERLAYS?.[key]?.label || dict?.overlayLabels?.[key] || OVERLAY_LABELS[key] || key;
}

function getAoiFrameGeoJson() {
  const coords = OVERLAYS?.["hv_pre.png"]?.coordinates;
  if (!coords || coords.length < 4) return { type: "FeatureCollection", features: [] };
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        geometry: {
          type: "Polygon",
          coordinates: [[coords[0], coords[1], coords[2], coords[3], coords[0]]],
        },
        properties: {},
      },
    ],
  };
}

function setRasterOpacityForKey(key) {
  return key.startsWith("hv_") || key.startsWith("ts/") ? 0.97 : 0.92;
}

function centerCompareSlider(force = false) {
  if (!compareControl) return;
  const wrap = document.getElementById("compare-wrap");
  const container = document.getElementById("compare-container");
  if (!wrap?.classList.contains("visible") || !container) return;
  const w = container.clientWidth;
  if (!w) return;
  if (force || Math.abs(w - lastCompareWidth) > 8) {
    lastCompareWidth = w;
    window.dispatchEvent(new Event("resize"));
    compareControl.setSlider(Math.round(w * 0.5));
  }
}

function resizeAllMaps() {
  if (map) map.resize();
  if (beforeMap) beforeMap.resize();
  if (afterMap) afterMap.resize();
  centerCompareSlider(false);
  layoutAssetMarkers();
}

function flyToCamera(center, zoom) {
  if (!map) return;
  const opts = { center, zoom, essential: true };
  if (REDUCED_MOTION) map.jumpTo(opts);
  else map.flyTo({ ...opts, speed: 1.15 });
}

function setLayerVisible(id, visible) {
  if (!map || !map.getLayer(id)) return;
  map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
}

function updateRasterOverlay(key) {
  if (!map || !OVERLAYS || !OVERLAYS[key]) return;
  const src = map.getSource("radar-overlay");
  if (!src) return;
  src.updateImage({ url: OVERLAYS[key].url, coordinates: OVERLAYS[key].coordinates });
  if (map.getLayer("radar-overlay-layer")) {
    map.setPaintProperty("radar-overlay-layer", "raster-opacity", setRasterOpacityForKey(key));
  }
  setLayerVisible("radar-overlay-layer", true);
}

async function decodeQ8Image() {
  const info = OVERLAYS["dhv_q8.png"];
  if (!info) return;
  const img = new Image();
  img.src = info.url;
  await img.decode();
  const c = document.createElement("canvas");
  c.width = img.width;
  c.height = img.height;
  const ctx = c.getContext("2d");
  ctx.drawImage(img, 0, 0);
  const raw = ctx.getImageData(0, 0, c.width, c.height).data;
  q8Pixels = { raw, width: c.width, height: c.height, info };
}

async function renderLiveThresholdOverlay(thresholdDb) {
  if (!q8Pixels || !map) return;
  const src = map.getSource("radar-overlay");
  if (!src) return;
  const { raw, width, height, info } = q8Pixels;
  const c = document.createElement("canvas");
  c.width = width;
  c.height = height;
  const ctx = c.getContext("2d");
  const out = ctx.createImageData(width, height);
  const dst = out.data;

  const minDb = info.min_db;
  const span = info.max_db - minDb;
  for (let i = 0; i < raw.length; i += 4) {
    const q = raw[i];
    if (q >= 255) continue;
    const db = minDb + (q / 254.0) * span;
    if (db <= thresholdDb) {
      if (db <= -6.0) {
        dst[i] = 90; dst[i + 1] = 20; dst[i + 2] = 16; dst[i + 3] = 245;
      } else if (db <= -3.0) {
        dst[i] = 158; dst[i + 1] = 53; dst[i + 2] = 32; dst[i + 3] = 225;
      } else {
        dst[i] = 204; dst[i + 1] = 107; dst[i + 2] = 44; dst[i + 3] = 205;
      }
    }
  }
  ctx.putImageData(out, 0, 0);
  const bmp = await createImageBitmap(c);
  src.updateImage({ image: bmp, coordinates: info.coordinates });
  if (map.getLayer("radar-overlay-layer")) {
    map.setPaintProperty("radar-overlay-layer", "raster-opacity", 0.94);
  }
  setLayerVisible("radar-overlay-layer", true);
}

function layoutAssetMarkers() {
  if (!map || !assetMarkers.length) return;
  if (!assetMarkersVisible) {
    assetMarkers.forEach(({ el }) => {
      el.style.display = "none";
    });
    return;
  }
  const canvas = map.getCanvas();
  const w = canvas?.clientWidth || window.innerWidth;
  const h = canvas?.clientHeight || window.innerHeight;
  const placed = [];
  const padX = 8;
  const padY = 6;
  const ordered = [...assetMarkers].sort((a, b) => b.priority - a.priority);

  for (const item of ordered) {
    const pt = map.project(item.coords);
    if (pt.x < 14 || pt.x > w - 14 || pt.y < 28 || pt.y > h - 14) {
      item.el.style.display = "none";
      continue;
    }
    item.el.style.visibility = "hidden";
    item.el.style.display = "inline-flex";
    const mw = item.el.offsetWidth || 96;
    const mh = item.el.offsetHeight || 22;
    const box = {
      left: pt.x - mw / 2 - padX,
      right: pt.x + mw / 2 + padX,
      top: pt.y - mh - 4 - padY,
      bottom: pt.y - 4 + padY,
    };
    const collides = placed.some(
      (b) => !(box.right < b.left || box.left > b.right || box.bottom < b.top || box.top > b.bottom)
    );
    if (collides) {
      item.el.style.display = "none";
    } else {
      item.el.style.visibility = "visible";
      item.el.style.display = "inline-flex";
      placed.push(box);
    }
  }
}

function setAssetMarkersVisible(visible) {
  assetMarkersVisible = visible;
  layoutAssetMarkers();
}

function updateLegend(swatches) {
  const box = document.querySelector(".map-legend");
  const swEl = document.getElementById("legend-swatches");
  if (!swEl) return;
  if (!swatches || !swatches.length) {
    if (box) box.style.display = "none";
    swEl.innerHTML = "";
    return;
  }
  if (box) box.style.display = "";
  swEl.innerHTML = swatches
    .map((s) => `<span class="swatch"><i style="background:${s.color}"></i>${s.label}</span>`)
    .join("");
}

function syncCompareCamera(sourceMap) {
  if (!sourceMap || !beforeMap || !afterMap) return;
  const center = sourceMap.getCenter();
  const zoom = sourceMap.getZoom();
  const opts = { center, zoom, bearing: sourceMap.getBearing(), pitch: sourceMap.getPitch() };
  beforeMap.jumpTo(opts);
  afterMap.jumpTo(opts);
}

function configureCompareForStep(stepId) {
  if (!beforeMap || !afterMap) return;
  if (stepId === "2") {
    if (beforeMap.getLayer("opt-lyr")) {
      beforeMap.setLayoutProperty("opt-lyr", "visibility", "none");
    }
    const rSrc = afterMap.getSource("rad-src");
    const info = OVERLAYS?.[activeCap2HvKey];
    if (rSrc && info) rSrc.updateImage({ url: info.url, coordinates: info.coordinates });
    if (afterMap.getLayer("rad-lyr")) {
      afterMap.setLayoutProperty("rad-lyr", "visibility", "visible");
      afterMap.setPaintProperty("rad-lyr", "raster-opacity", 0.98);
    }
    if (afterMap.getLayer("aoi-frame-a-lyr")) {
      afterMap.setLayoutProperty("aoi-frame-a-lyr", "visibility", "visible");
    }
    document.getElementById("cmp-left-lbl").textContent = I18N[activeLang].overlayLabels.osmTerrain;
    document.getElementById("cmp-right-lbl").textContent = getOverlayLabel(activeCap2HvKey);
  } else {
    if (beforeMap.getLayer("opt-lyr")) {
      beforeMap.setLayoutProperty("opt-lyr", "visibility", "visible");
    }
    if (afterMap.getLayer("rad-lyr")) {
      afterMap.setLayoutProperty("rad-lyr", "visibility", "visible");
      afterMap.setPaintProperty("rad-lyr", "raster-opacity", 0.94);
    }
    if (afterMap.getLayer("aoi-frame-a-lyr")) {
      afterMap.setLayoutProperty("aoi-frame-a-lyr", "visibility", "none");
    }
    updateCompareLayers(activeOptKey, activeRadKey);
  }
}

function showCompareMode(show) {
  const wrap = document.getElementById("compare-wrap");
  const labels = document.getElementById("compare-labels");
  wrap.classList.toggle("visible", show);
  labels.classList.toggle("visible", show);
  if (show && !compareInit) initCompareMaps();
  if (show && beforeMap && afterMap) {
    if (activeStep === "2") {
      const target = { center: getBlockCenter(), zoom: 11.4, bearing: 0, pitch: 0 };
      beforeMap.jumpTo(target);
      afterMap.jumpTo(target);
    } else {
      syncCompareCamera(map);
    }
    configureCompareForStep(activeStep);
    requestAnimationFrame(() => {
      beforeMap.resize();
      afterMap.resize();
      centerCompareSlider(true);
    });
    setTimeout(() => {
      beforeMap.resize();
      afterMap.resize();
      centerCompareSlider(true);
    }, 620);
  }
}

function initCompareMaps() {
  if (compareInit) return;
  compareInit = true;
  const center = getBlockCenter();

  beforeMap = new maplibregl.Map({
    container: "before-map",
    style: darkBaseStyle(),
    center,
    zoom: 11.4,
    minZoom: MIN_ZOOM,
    maxZoom: MAX_ZOOM,
    maxBounds: REGION_BOUNDS,
    attributionControl: false,
  });
  afterMap = new maplibregl.Map({
    container: "after-map",
    style: darkBaseStyle(),
    center,
    zoom: 11.4,
    minZoom: MIN_ZOOM,
    maxZoom: MAX_ZOOM,
    maxBounds: REGION_BOUNDS,
    attributionControl: false,
  });
  beforeMap.on("error", () => {});
  afterMap.on("error", () => {});

  beforeMap.on("load", () => {
    const opt = OVERLAYS[activeOptKey] || OVERLAYS["optical_fire.jpg"];
    if (opt) {
      beforeMap.addSource("opt-src", { type: "image", url: opt.url, coordinates: opt.coordinates });
      beforeMap.addLayer({ id: "opt-lyr", type: "raster", source: "opt-src", paint: { "raster-opacity": 0.96 } });
    }
    beforeMap.addSource("perim-b", { type: "geojson", data: FIRE_GJ });
    beforeMap.addLayer({ id: "perim-b-lyr", type: "line", source: "perim-b", paint: { "line-color": "#8E4321", "line-width": 2.2 } });
    if (activeStep === "2" || activeStep === "4") configureCompareForStep(activeStep);
    beforeMap.resize();
    centerCompareSlider(true);
  });

  afterMap.on("load", () => {
    const hv = OVERLAYS[activeRadKey] || OVERLAYS["dhv_classes.png"];
    if (hv) {
      afterMap.addSource("rad-src", { type: "image", url: hv.url, coordinates: hv.coordinates });
      afterMap.addLayer({ id: "rad-lyr", type: "raster", source: "rad-src", paint: { "raster-opacity": 0.94 } });
    }
    afterMap.addSource("aoi-frame-a", { type: "geojson", data: getAoiFrameGeoJson() });
    afterMap.addLayer({
      id: "aoi-frame-a-lyr",
      type: "line",
      source: "aoi-frame-a",
      layout: { visibility: "none" },
      paint: { "line-color": "rgba(36, 28, 20, 0.36)", "line-width": 1.1 },
    });
    afterMap.addSource("perim-a", { type: "geojson", data: FIRE_GJ });
    afterMap.addLayer({ id: "perim-a-lyr", type: "line", source: "perim-a", paint: { "line-color": "#8E4321", "line-width": 2.2 } });
    if (activeStep === "2" || activeStep === "4") configureCompareForStep(activeStep);
    afterMap.resize();
    centerCompareSlider(true);
  });

  compareControl = new maplibregl.Compare(beforeMap, afterMap, "#compare-container");
}

function updateCompareLayers(optKey, radKey) {
  if (!beforeMap || !afterMap) return;
  const oSrc = beforeMap.getSource("opt-src");
  const rSrc = afterMap.getSource("rad-src");
  if (oSrc && OVERLAYS[optKey]) oSrc.updateImage({ url: OVERLAYS[optKey].url, coordinates: OVERLAYS[optKey].coordinates });
  if (rSrc && OVERLAYS[radKey]) rSrc.updateImage({ url: OVERLAYS[radKey].url, coordinates: OVERLAYS[radKey].coordinates });
  document.getElementById("cmp-left-lbl").textContent = getOverlayLabel(optKey);
  document.getElementById("cmp-right-lbl").textContent = getOverlayLabel(radKey);
}

function parseNumberArray(raw) {
  if (Array.isArray(raw)) return raw.map(Number);
  if (typeof raw !== "string") return [];
  const trimmed = raw.trim().replace(/^\[|\]$/g, "").trim();
  if (!trimmed) return [];
  return trimmed.split(/[\s,]+/).map(Number).filter(Number.isFinite);
}

function buildRainSegmentsGeoJson(rainGeoJson) {
  const features = [];
  const stride = 4;
  for (const feat of rainGeoJson.features) {
    const coords = feat.geometry.coordinates;
    const areas = parseNumberArray(feat.properties.contrib_area_m2);
    for (let i = 0; i < coords.length - 1; i += stride) {
      const next = Math.min(i + stride, coords.length - 1);
      const segArea = Math.max(areas[i] || 0, areas[next] || 0);
      features.push({
        type: "Feature",
        geometry: { type: "LineString", coordinates: [coords[i], coords[next]] },
        properties: { seed_id: feat.properties.seed_id, area_m2: segArea },
      });
    }
  }
  return { type: "FeatureCollection", features };
}

function updateRainMapLayer(rainMm) {
  activeRainMm = rainMm;
  document.getElementById("rain-val-label").textContent = `${rainMm} mm`;

  const maxArea = Math.max(...RAIN_SEGS_GJ.features.map((f) => f.properties.area_m2), 1);
  if (map && map.getLayer("rain-lines")) {
    const k = (rainMm / 1000) * RUNOFF_COEFF;
    // Referencia a 100 mm con C=0.6 (0.06 m efectivos) para resaltar troncos principales ya a 60 mm
    const refFlow = maxArea * 0.06;

    map.setPaintProperty("rain-lines", "line-width", [
      "interpolate",
      ["linear"],
      ["*", ["get", "area_m2"], k],
      0, 1.1,
      refFlow * 0.05, 2.0,
      refFlow * 0.60, 4.2,
      refFlow * 1.40, 5.6,
    ]);
    map.setPaintProperty("rain-lines", "line-color", [
      "interpolate",
      ["linear"],
      ["*", ["get", "area_m2"], k],
      0, "#86B0A9",
      refFlow * 0.15, "#5E979A",
      refFlow * 0.40, "#478189",
      refFlow * 0.75, "#255A6E",
      refFlow * 1.25, "#13344A",
    ]);
  }

  const burnedHa = STATS?.severity_oct25?.burned_total_ha || STATS?.severity_smooth?.burned_total_ha || 0;
  const vBurned = burnedHa * 10000 * (rainMm / 1000) * RUNOFF_COEFF;
  const vMain = maxArea * (rainMm / 1000) * RUNOFF_COEFF;
  document.getElementById("rain-v-near").textContent = `${fmtEs(vBurned)} m³`;
  document.getElementById("rain-v-main").textContent = `${fmtEs(vMain)} m³`;
}

function updateBasinSensitivity(field) {
  activeBasinThreshold = field;
  if (!map || !map.getLayer("basins-fill")) return;
  const maxR = Math.max(...BASINS_GJ.features.map((f) => f.properties[field] || 0), 0.0001);
  map.setPaintProperty("basins-fill", "fill-color", [
    "interpolate",
    ["linear"],
    ["coalesce", ["get", field], 0],
    0, "#C8DCD6",
    maxR * 0.12, "#86B0A9",
    maxR * 0.35, "#478189",
    maxR * 0.65, "#255A6E",
    maxR, "#13344A",
  ]);
}

let selectedBasinId = null;
let currentSeverityObj = null;
let selectDateFn = null;

function selectBasinById(basinId) {
  const feat = BASINS_GJ.features.find((f) => Number(f.properties.basin_id) === Number(basinId));
  if (!feat) return;
  selectedBasinId = Number(basinId);
  const p = feat.properties;
  const d = I18N[activeLang].dynamic;
  const rawAssets = p.downstream_assets;
  let assets = [];
  if (Array.isArray(rawAssets)) {
    assets = rawAssets;
  } else if (typeof rawAssets === "string") {
    try {
      assets = JSON.parse(rawAssets || "[]");
    } catch {
      assets = [];
    }
  }

  const assetsHtml = assets.length
    ? `<ul class="asset-list">${assets.map((a) => `<li class="asset-chip">${a.name} (${a.type})</li>`).join("")}</ul>`
    : `<p style="font-size:0.8rem;color:var(--text-muted);margin:0.35rem 0 0">${d.basinAssetsNone}</p>`;

  document.getElementById("basin-inspector").innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;gap:0.5rem">
      <strong style="font-size:1.05rem">${d.basinTitle(p.basin_id)}</strong>
      <span class="step-badge">${d.basinRank(p.rank, BASINS_GJ.features.length)}</span>
    </div>
    <div class="mini-metrics">
      <div class="mini-metric"><div class="k">${d.basinRiskLbl}</div><div class="v">${Number(p.risk_mean).toFixed(5)}</div></div>
      <div class="mini-metric"><div class="k">${d.basinBurnedLbl}</div><div class="v">${p.burned_pct}% (${p.burned_ha} ha)</div></div>
      <div class="mini-metric"><div class="k">${d.basinSlopeLbl}</div><div class="v">${p.slope_mean_deg}°</div></div>
      <div class="mini-metric"><div class="k">${d.basinSmeLbl}</div><div class="v">${p.moisture_mean ?? "—"} m³/m³</div></div>
    </div>
    <div style="margin-top:0.55rem;font-size:0.78rem;color:var(--text-muted)">
      ${d.basinSens(p.burned_ha_3db, p.rank_3db, p.burned_ha_6db, p.rank_6db)}
    </div>
    <div style="margin-top:0.55rem;font-size:0.8rem"><strong>${d.basinAssetsHead}</strong>${assetsHtml}</div>
  `;

  if (map && map.getLayer("basins-selected")) {
    map.setFilter("basins-selected", ["==", ["get", "basin_id"], Number(basinId)]);
  }
}

function selectBarrierByIdx(idx) {
  const host = document.getElementById("barrier-inspector");
  if (!host || !BARRIERS_GJ?.features?.length) return;
  const feat = BARRIERS_GJ.features.find((f) => Number(f.properties.idx) === Number(idx)) || BARRIERS_GJ.features[0];
  if (!feat) return;
  const p = feat.properties;
  const d = I18N[activeLang].dynamic;
  selectedBarrierIdx = Number(p.idx);

  const relLabel = p.relevant
    ? `<span class="step-badge" style="color:var(--orange);border-color:rgba(142,67,33,0.45)">${d.barrierPriority}</span>`
    : `<span class="step-badge">${d.barrierDistant}</span>`;
  const distStr = p.dist_from_fire_m < 1000 ? `${Math.round(p.dist_from_fire_m)} m` : `${fmtEs(p.dist_from_fire_m / 1000, 1)} km`;

  const btns = BARRIERS_GJ.features
    .map((f) => {
      const fp = f.properties;
      const isAct = Number(fp.idx) === selectedBarrierIdx ? " active" : "";
      const tag = fp.relevant ? "★ " : "";
      const dLbl = fp.dist_from_fire_m < 1000 ? `${Math.round(fp.dist_from_fire_m)} m` : `${fmtEs(fp.dist_from_fire_m / 1000, 1)} km`;
      return `<button class="pill-btn${isAct}" type="button" data-barrier-idx="${fp.idx}">${tag}${dLbl} (−${fp.slope_drop_deg}°)</button>`;
    })
    .join("");

  host.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;gap:0.5rem;flex-wrap:wrap">
      <strong style="font-size:0.96rem">${d.barrierTitle(Number(p.idx) + 1)}</strong>
      ${relLabel}
    </div>
    <div class="pill-group" style="margin-top:0.55rem">${btns}</div>
    <div class="mini-metrics">
      <div class="mini-metric"><div class="k">${d.barrierDistLbl}</div><div class="v">${distStr}</div></div>
      <div class="mini-metric"><div class="k">${d.barrierBreakLbl}</div><div class="v">−${p.slope_drop_deg}° (${p.slope_before_deg}° → ${p.slope_after_deg}°)</div></div>
      <div class="mini-metric"><div class="k">${d.barrierAreaLbl}</div><div class="v">${fmtEs(p.contrib_area_ha, 1)} ha</div></div>
      <div class="mini-metric"><div class="k">${d.barrierCoordLbl}</div><div class="v">${Number(p.lat).toFixed(4)}, ${Number(p.lon).toFixed(4)}</div></div>
    </div>
  `;

  if (map && map.getLayer("barriers-selected")) {
    map.setFilter("barriers-selected", ["==", ["get", "idx"], selectedBarrierIdx]);
  }
}

function updateLegendForStep(stepId) {
  const swatches = I18N[activeLang]?.legends?.[String(stepId)];
  if (swatches) updateLegend(swatches);
}

function translateSeverityLabel(label, lang) {
  if (lang !== "en") return label;
  return String(label)
    .replace(/Sin cambio/g, "Unchanged")
    .replace(/Moderada/g, "Moderate")
    .replace(/Severa/g, "Severe")
    .replace(/Alta/g, "High")
    .replace(/Extrema/g, "Extreme")
    .replace(/ a /g, " to ");
}

function activateStep(stepId) {
  activeStep = String(stepId);
  document.querySelectorAll(".narrative-col [data-step]").forEach((c) => {
    c.classList.toggle("is-active", c.dataset.step === activeStep);
  });
  document.querySelectorAll(".toc-pill").forEach((p) => {
    p.classList.toggle("active", p.dataset.step === activeStep);
  });
  updateTocLabel();

  const isCompareStep = activeStep === "2" || activeStep === "4";
  showCompareMode(isCompareStep);

  if (!map) return;

  // Reset de visibilidad base antes de activar la combinación del capítulo
  setLayerVisible("radar-overlay-layer", false);
  setLayerVisible("aoi-frame-line", false);
  setLayerVisible("basins-fill", false);
  setLayerVisible("basins-outline", false);
  setLayerVisible("basins-selected", false);
  setLayerVisible("rain-lines", false);
  setLayerVisible("dem-edge-line", false);
  setLayerVisible("barriers-circle", false);
  setLayerVisible("barriers-selected", false);
  setLayerVisible("fire-fill", false);
  setAssetMarkersVisible(false);

  switch (activeStep) {
    case "summary":
      flyToCamera([-7.85, 41.923], 11.3);
      setLayerVisible("fire-fill", true);
      setAssetMarkersVisible(true);
      break;
    case "1":
      flyToCamera([-7.84, 41.925], 11.4);
      setLayerVisible("fire-fill", true);
      setAssetMarkersVisible(true);
      break;
    case "2":
      break;
    case "3":
      flyToCamera(getBlockCenter(), 11.5);
      updateRasterOverlay(`ts/${activeSeriesDate}`);
      setLayerVisible("aoi-frame-line", true);
      break;
    case "4":
      break;
    case "5":
      flyToCamera(getBlockCenter(), 11.6);
      applyDhbMode(activeDhbMode);
      break;
    case "6":
      flyToCamera(getBlockCenter(), 11.6);
      updateRasterOverlay("dhh.png");
      setLayerVisible("aoi-frame-line", true);
      break;
    case "7":
      flyToCamera([-7.88, 41.92], 10.7);
      setLayerVisible("basins-fill", true);
      setLayerVisible("basins-outline", true);
      setLayerVisible("basins-selected", true);
      setAssetMarkersVisible(true);
      break;
    case "8":
      flyToCamera([-7.91, 41.915], 10.9);
      setLayerVisible("basins-outline", true);
      setLayerVisible("rain-lines", true);
      setLayerVisible("dem-edge-line", true);
      setLayerVisible("barriers-circle", true);
      setLayerVisible("barriers-selected", true);
      setAssetMarkersVisible(true);
      updateRainMapLayer(activeRainMm);
      break;
    case "9":
      flyToCamera([-7.86, 41.92], 10.3);
      setLayerVisible("basins-fill", true);
      setLayerVisible("basins-outline", true);
      setLayerVisible("rain-lines", true);
      setAssetMarkersVisible(true);
      break;
  }
  updateLegendForStep(activeStep);
}

function renderSeverityTable(sevObj) {
  currentSeverityObj = sevObj;
  const tbody = document.getElementById("db-classes-tbody");
  tbody.innerHTML = sevObj.classes
    .map(
      (c) => `
      <tr>
        <td>${translateSeverityLabel(c.label, activeLang)}</td>
        <td class="num">${fmtEs(c.ha, 1)} ha</td>
        <td class="num">${c.pct}%</td>
      </tr>`
    )
    .join("");
}

function updateTocLabel() {
  const pills = [...document.querySelectorAll(".toc-pill")];
  const footer = document.getElementById("cap-10");
  const alerts = document.getElementById("cap-11");
  const atFooter = footer && footer.getBoundingClientRect().top < window.innerHeight * 0.5;
  const atAlerts = alerts && alerts.getBoundingClientRect().top < window.innerHeight * 0.5;
  const current = atAlerts
    ? pills.find((p) => p.dataset.step === "11")
    : atFooter
    ? pills.find((p) => p.dataset.step === "10")
    : pills.find((p) => p.dataset.step === activeStep) || pills[0];
  pills.forEach((p) => (p === current ? p.setAttribute("aria-current", "true") : p.removeAttribute("aria-current")));
  const lbl = document.getElementById("toc-current");
  if (lbl && current) lbl.textContent = current.textContent;
}

function syncPressed() {
  document.querySelectorAll(".pill-btn").forEach((b) => b.setAttribute("aria-pressed", b.classList.contains("active")));
}

function initToc() {
  const btn = document.getElementById("toc-toggle");
  const list = document.getElementById("toc-pills");
  if (!btn || !list) return;
  const setOpen = (open) => {
    list.hidden = !open;
    btn.setAttribute("aria-expanded", String(open));
  };
  btn.addEventListener("click", () => setOpen(list.hidden));
  list.addEventListener("click", (e) => { if (e.target.closest("a")) setOpen(false); });
  document.addEventListener("click", (e) => { if (!list.hidden && !e.target.closest(".toc")) setOpen(false); });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !list.hidden) { setOpen(false); btn.focus(); }
  });
}

function applyDhbMode(mode, updateMap = true) {
  activeDhbMode = mode;
  if (mode === "classes") {
    if (updateMap) updateRasterOverlay("dhv_classes.png");
    renderSeverityTable(STATS.severity_smooth);
    updateThresholdReadout(activeDbThreshold);
  } else if (mode === "oct01_cal") {
    const cal = STATS.severity_oct01_calibrated || STATS.severity_smooth;
    const d = I18N[activeLang].dynamic;
    if (updateMap) updateRasterOverlay("dhv_oct01_cal.png");
    renderSeverityTable(cal);
    document.getElementById("db-ha-smooth").textContent = `${fmtEs(cal.burned_total_ha, 1)} ha`;
    document.getElementById("db-ha-raw").textContent = `${fmtEs(cal.burned_total_ha, 1)} ha ${d.octCalSuffix}`;
    document.getElementById("db-fp-rate").textContent = d.octCalFp;
    document.getElementById("db-energy-loss").textContent = "29% (−1,5 dB)";
  } else if (mode === "oct25") {
    const oct25 = STATS.severity_oct25 || STATS.severity_smooth;
    const d = I18N[activeLang].dynamic;
    if (updateMap) updateRasterOverlay("dhv_oct25.png");
    renderSeverityTable(oct25);
    document.getElementById("db-ha-smooth").textContent = `${fmtEs(oct25.burned_total_ha, 1)} ha`;
    document.getElementById("db-ha-raw").textContent = `${fmtEs(oct25.burned_total_ha, 1)} ha ${d.oct25Suffix}`;
    document.getElementById("db-fp-rate").textContent = d.oct25Fp;
    document.getElementById("db-energy-loss").textContent = "29% (−1,5 dB)";
  } else if (mode === "continuous") {
    if (updateMap) updateRasterOverlay("dhv_cont.png");
    renderSeverityTable(STATS.severity_smooth);
    updateThresholdReadout(activeDbThreshold);
  } else {
    if (updateMap) renderLiveThresholdOverlay(activeDbThreshold);
    renderSeverityTable(STATS.severity_smooth);
    updateThresholdReadout(activeDbThreshold);
  }
}

function populateExecutiveSummary() {
  const m = STATS.meta;
  const sm = STATS.severity_smooth;
  const raw = STATS.severity_raw_20m;
  const oct25 = STATS.severity_oct25;
  const pol = STATS.polarizations;
  const top1 = STATS.basins_summary[0];
  const top2 = STATS.basins_summary[1];
  const d = I18N[activeLang].dynamic;
  const lc = I18N[activeLang].landcoverNames || {};

  document.getElementById("kpi-xunta").textContent = `${fmtEs(m.official_xunta_ha)} ha`;
  document.getElementById("kpi-xunta-sub").textContent = d.xuntaSub(m.official_forest_ha, m.official_grass_ha);
  document.getElementById("kpi-effis").textContent = `${fmtEs(m.effis_ha)} ha`;
  document.getElementById("kpi-nisar-smooth").textContent = `${fmtEs(sm.burned_total_ha, 1)} → ${fmtEs(oct25 ? oct25.burned_total_ha : sm.burned_total_ha, 1)} ha`;
  document.getElementById("kpi-nisar-sub").textContent = d.nisarSub(
    fmtEs(sm.burned_total_ha, 1),
    fmtEs(raw.burned_total_ha, 0),
    fmtEs(oct25 ? oct25.burned_total_ha : sm.burned_total_ha, 1)
  );
  document.getElementById("kpi-dhv").textContent = `${pol.hv_fire_net_db ?? pol.hv_fire_mean_db} dB`;
  document.getElementById("kpi-dhv-sub").textContent = d.dhvSub(pol.ctrl_offset_oct01_db ?? 0, pol.hv_oct25_fire_mean_db);
  document.getElementById("kpi-basins").textContent = d.basinsJoin(top1.basin_id, top2.basin_id);
  document.getElementById("kpi-basins-sub").textContent = d.basinsSub(STATS.basins_summary.length);

  const maxBar = m.effis_ha;
  document.getElementById("bar-effis").style.width = "100%";
  document.getElementById("val-effis").textContent = `${fmtEs(m.effis_ha)} ha`;
  document.getElementById("bar-xunta").style.width = `${(m.official_xunta_ha / maxBar) * 100}%`;
  document.getElementById("val-xunta").textContent = `${fmtEs(m.official_xunta_ha)} ha`;
  document.getElementById("bar-raw").style.width = `${(raw.burned_total_ha / maxBar) * 100}%`;
  document.getElementById("val-raw").textContent = `${fmtEs(raw.burned_total_ha, 0)} ha`;
  document.getElementById("bar-smooth").style.width = `${(sm.burned_total_ha / maxBar) * 100}%`;
  document.getElementById("val-smooth").textContent = `${fmtEs(sm.burned_total_ha, 1)} ha`;

  renderSeverityTable(sm);

  // Tabla HH vs HV y WorldCover 2021
  document.getElementById("pol-compare-body").innerHTML = `
    <tr><td>${d.polHvLabel}</td><td class="num">${pol.hv_fire_mean_db} dB ${d.polNet(pol.hv_fire_net_db)}</td><td class="num">${pol.hv_ctrl_mean_db} dB</td><td class="num"><strong>${pol.hv_separation_db} dB</strong></td></tr>
    <tr><td>${d.polHhLabel}</td><td class="num">${pol.hh_fire_mean_db} dB ${d.polNet(pol.hh_fire_net_db)}</td><td class="num">${pol.hh_ctrl_mean_db} dB</td><td class="num">${pol.hh_separation_db} dB</td></tr>
  `;
  document.getElementById("hh-double-bounce-note").textContent = d.hhBounceNote(
    pol.hh_double_bounce_pct_fire,
    pol.hh_ctrl_mean_db
  );

  const wcBody = document.getElementById("worldcover-tbody");
  wcBody.innerHTML = (STATS.landcover_2021 || [])
    .map(
      (w) => `
      <tr>
        <td>${lc[w.name] || w.name}</td>
        <td class="num">${fmtEs(w.area_ha, 1)} ha (${w.pct_of_perimeter}%)</td>
        <td class="num">${w.dhv_net_oct01_db ?? w.dhv_mean_db} dB</td>
        <td class="num">${w.dhv_oct25_mean_db ?? "—"} dB</td>
        <td class="num">${w.burned_pct_oct25_15db ?? w.burned_pct_15db}%</td>
      </tr>`
    )
    .join("");

  const dnbr = STATS.optical_dnbr;
  const dnbrEl = document.getElementById("dnbr-validation-note");
  if (dnbr && dnbrEl) {
    dnbrEl.innerHTML = d.dnbrNote(
      dnbr.pre_scene,
      dnbr.post_scene,
      fmtEs(dnbr.burned_low_plus_ha, 1),
      fmtEs(dnbr.burned_high_ha, 1),
      fmtEs(oct25?.burned_total_ha || 0, 1),
      dnbr.pearson_r_vs_dhv_oct25
    );
  }

  // Tabla QA en metodología
  document.getElementById("qa-tbody").innerHTML = STATS.qa
    .map(
      (q) => `
      <tr>
        <td>${q.date}</td>
        <td class="num">${q.valid_pct_perimeter}%</td>
        <td class="num">${q.ctrl_hv_mean_db} dB</td>
        <td class="num">${q.ctrl_deviation_db} dB</td>
        <td><span class="${q.qa_pass ? "qa-pass" : "qa-flag"}">${q.qa_pass ? "PASS" : "FLAG"}</span></td>
      </tr>`
    )
    .join("");
}

function updateThresholdReadout(db) {
  activeDbThreshold = db;
  document.getElementById("db-slider-val").textContent = `${db.toFixed(2)} dB`;
  const row = STATS.threshold_curve.reduce((best, cur) =>
    Math.abs(cur.threshold_db - db) < Math.abs(best.threshold_db - db) ? cur : best
  );
  const pctLoss = Math.round((1 - Math.pow(10, db / 10)) * 100);
  document.getElementById("db-ha-smooth").textContent = `${fmtEs(row.ha_smooth, 1)} ha`;
  document.getElementById("db-ha-raw").textContent = `${fmtEs(row.ha_raw, 1)} ha`;
  document.getElementById("db-fp-rate").textContent = `${row.fp_ctrl_pct_smooth}%`;
  document.getElementById("db-energy-loss").textContent = `${pctLoss}%`;

  renderThresholdCurve(document.getElementById("chart-threshold"), STATS.threshold_curve, db, STATS.meta, activeLang);
  if (activeStep === "5" && activeDhbMode === "threshold") {
    renderLiveThresholdOverlay(db);
  }
}

function applyLanguage(lang) {
  activeLang = lang;
  const dict = I18N[lang];
  if (!dict) return;

  document.documentElement.lang = lang;
  if (dict.docTitle) document.title = dict.docTitle;
  const tocNav = document.querySelector("nav.toc");
  if (tocNav && dict.tocAria) tocNav.setAttribute("aria-label", dict.tocAria);
  const mapFrameEl = document.getElementById("map-frame");
  if (mapFrameEl && dict.mapAria) mapFrameEl.setAttribute("aria-label", dict.mapAria);

  document.querySelectorAll("[data-i18n]").forEach((el) => {
    if (el.id === "basin-inspector" && selectedBasinId !== null) return;
    if (el.id === "barrier-inspector" && selectedBarrierIdx !== null) return;
    const key = el.dataset.i18n;
    if (el.dataset.i18nEs === undefined) el.dataset.i18nEs = el.textContent;
    const val = dict[key];
    el.textContent = val !== undefined ? val : el.dataset.i18nEs;
  });

  document.querySelectorAll("[data-i18n-html]").forEach((el) => {
    const key = el.dataset.i18nHtml;
    if (el.dataset.i18nHtmlEs === undefined) el.dataset.i18nHtmlEs = el.innerHTML;
    const val = dict[key];
    el.innerHTML = val !== undefined ? val : el.dataset.i18nHtmlEs;
  });

  document.querySelectorAll(".toc-pill").forEach((el, idx) => {
    if (dict.tocLabels[idx]) el.textContent = dict.tocLabels[idx];
  });

  if (STATS) {
    populateExecutiveSummary();
    if (activeDhbMode === "oct01_cal" || activeDhbMode === "oct25") {
      applyDhbMode(activeDhbMode, activeStep === "5");
    } else {
      updateThresholdReadout(activeDbThreshold);
    }
    renderHistogramChart(document.getElementById("chart-histogram"), STATS.histogram, lang);
  }
  renderPhysicsDiagrams(document.getElementById("physics-diagrams"), lang);
  if (selectDateFn) selectDateFn(activeSeriesDate);
  if (selectedBasinId !== null) selectBasinById(selectedBasinId);
  if (selectedBarrierIdx !== null) selectBarrierByIdx(selectedBarrierIdx);
  if (RAIN_SEGS_GJ) updateRainMapLayer(activeRainMm);
  if (activeStep === "2" || activeStep === "4") configureCompareForStep(activeStep);
  updateLegendForStep(activeStep);
  updateTocLabel();
}

async function init() {

  const [stats, overlays, basins, assets, fire, rain, barriers] = await Promise.all([
    fetch("assets/data/story_stats.json").then((r) => r.json()),
    fetch("assets/data/overlays/overlays.json").then((r) => r.json()),
    fetch("assets/data/basins_risk.geojson").then((r) => r.json()),
    fetch("assets/data/assets.geojson").then((r) => r.json()),
    fetch("assets/data/fire_perimeter.geojson").then((r) => r.json()),
    fetch("assets/data/rain_channels.geojson").then((r) => r.json()),
    fetch("assets/data/barrier_candidates.geojson").then((r) => r.json()),
  ]);

  STATS = stats;
  OVERLAYS = overlays;
  BASINS_GJ = basins;
  ASSETS_GJ = assets;
  FIRE_GJ = fire;
  RAIN_SEGS_GJ = buildRainSegmentsGeoJson(rain);
  BARRIERS_GJ = {
    ...barriers,
    features: (barriers?.features || []).map((f, idx) => ({
      ...f,
      properties: { ...f.properties, idx },
    })),
  };

  initToc();
  syncPressed();
  // Tras cualquier clic en un botón de opción, reflejar su estado para lectores de pantalla
  document.addEventListener("click", (e) => { if (e.target.closest(".pill-btn")) syncPressed(); });
  populateExecutiveSummary();
  renderPhysicsDiagrams(document.getElementById("physics-diagrams"), activeLang);
  renderHistogramChart(document.getElementById("chart-histogram"), STATS.histogram, activeLang);

  const selectDate = (dt) => {
    activeSeriesDate = dt;
    const row = STATS.timeseries.find((t) => t.date === dt);
    if (row) {
      document.getElementById("ts-selected-readout").textContent = I18N[activeLang].dynamic.tsReadout(
        dt,
        row.hv_fire_mean,
        row.hv_ctrl_mean,
        row.sme2_fire_mean,
        row.qa_pass
      );
    }
    renderTimeseriesChart(document.getElementById("chart-timeseries"), STATS.timeseries, dt, selectDate, activeLang);
    if (activeStep === "3") updateRasterOverlay(`ts/${dt}`);
  };
  selectDateFn = selectDate;
  selectDate("2026-10-01");
  updateThresholdReadout(-1.5);

  await decodeQ8Image();

  map = new maplibregl.Map({
    container: "story-map",
    style: darkBaseStyle(),
    center: [-7.855, 41.922],
    zoom: 11.4,
    minZoom: MIN_ZOOM,
    maxZoom: MAX_ZOOM,
    maxBounds: REGION_BOUNDS,
  });
  map.on("error", () => {});

  const mapFrame = document.getElementById("map-frame");
  if (mapFrame && typeof ResizeObserver !== "undefined") {
    const ro = new ResizeObserver(() => resizeAllMaps());
    ro.observe(mapFrame);
  }

  map.on("load", () => {
    const first = OVERLAYS["dhv_classes.png"];
    map.addSource("radar-overlay", { type: "image", url: first.url, coordinates: first.coordinates });
    map.addLayer({ id: "radar-overlay-layer", type: "raster", source: "radar-overlay", layout: { visibility: "none" }, paint: { "raster-opacity": 0.92 } });

    map.addSource("aoi-frame", { type: "geojson", data: getAoiFrameGeoJson() });
    map.addLayer({ id: "aoi-frame-line", type: "line", source: "aoi-frame", layout: { visibility: "none" }, paint: { "line-color": "rgba(36, 28, 20, 0.36)", "line-width": 1.1 } });

    map.addSource("basins", { type: "geojson", data: BASINS_GJ });
    map.addLayer({ id: "basins-fill", type: "fill", source: "basins", layout: { visibility: "none" }, paint: { "fill-color": "#478189", "fill-opacity": 0.62 } });
    map.addLayer({ id: "basins-outline", type: "line", source: "basins", layout: { visibility: "none" }, paint: { "line-color": "#241C14", "line-width": 0.8, "line-opacity": 0.35 } });
    map.addLayer({ id: "basins-selected", type: "line", source: "basins", filter: ["==", ["get", "basin_id"], -1], layout: { visibility: "none" }, paint: { "line-color": "#241C14", "line-width": 2.6 } });
    updateBasinSensitivity("risk_mean");

    map.addSource("rain-segs", { type: "geojson", data: RAIN_SEGS_GJ });
    map.addLayer({ id: "rain-lines", type: "line", source: "rain-segs", layout: { visibility: "none", "line-cap": "round" }, paint: { "line-color": "#86B0A9", "line-width": 2, "line-opacity": 0.88 } });

    map.addSource("dem-edge", {
      type: "geojson",
      data: { type: "Feature", geometry: { type: "LineString", coordinates: [[DEM_TILE_EDGE_LON, 41.80], [DEM_TILE_EDGE_LON, 42.02]] } },
    });
    map.addLayer({ id: "dem-edge-line", type: "line", source: "dem-edge", layout: { visibility: "none" }, paint: { "line-color": "#57493A", "line-width": 1.4, "line-dasharray": [4, 4] } });

    map.addSource("fire-perim", { type: "geojson", data: FIRE_GJ });
    map.addLayer({ id: "fire-fill", type: "fill", source: "fire-perim", layout: { visibility: "none" }, paint: { "fill-color": "#8E4321", "fill-opacity": 0.22 } });
    map.addLayer({ id: "fire-line", type: "line", source: "fire-perim", paint: { "line-color": "#8E4321", "line-width": 2.2 } });

    map.addSource("barriers", { type: "geojson", data: BARRIERS_GJ });
    map.addLayer({
      id: "barriers-circle",
      type: "circle",
      source: "barriers",
      layout: { visibility: "none" },
      paint: {
        "circle-radius": ["case", ["get", "relevant"], 8, 6],
        "circle-color": ["case", ["get", "relevant"], "#D98E3A", "#57493A"],
        "circle-stroke-color": "#F5F0E6",
        "circle-stroke-width": 1.8,
      },
    });
    map.addLayer({
      id: "barriers-selected",
      type: "circle",
      source: "barriers",
      filter: ["==", ["get", "idx"], -1],
      layout: { visibility: "none" },
      paint: {
        "circle-radius": 12.5,
        "circle-color": "transparent",
        "circle-stroke-color": "#241C14",
        "circle-stroke-width": 2.5,
      },
    });

    // Marcadores HTML en píldoras compactas para núcleos/embalses OSM con prioridad antisolape
    const topNames = new Set(["As Meaus", "Calvos de Randín", "Feás", "Randín", "Rubiás"]);
    const midNames = new Set(["Maus de Salas", "Santiago de Rubiás", "Baltar", "Muíños"]);
    assetMarkers = ASSETS_GJ.features.map((f) => {
      const el = document.createElement("div");
      el.style.cssText =
        "display:inline-flex;align-items:center;gap:5px;padding:2px 8px;border-radius:4px;background:rgba(245,240,230,0.94);font:600 12px Inter,ui-sans-serif,sans-serif;color:#241C14;white-space:nowrap;pointer-events:none;box-shadow:0 1px 6px rgba(36,28,20,0.25);";
      const dotCol = f.properties.type === "reservoir" ? "#23596A" : "#8E4321";
      el.innerHTML = `<span style="width:6px;height:6px;border-radius:50%;background:${dotCol};flex-shrink:0"></span><span>${f.properties.name}</span>`;
      const marker = new maplibregl.Marker({ element: el, anchor: "bottom", offset: [0, -4] }).setLngLat(f.geometry.coordinates).addTo(map);
      const priority =
        f.properties.type === "reservoir" ? 100 : topNames.has(f.properties.name) ? 85 : midNames.has(f.properties.name) ? 60 : 35;
      return { marker, el, coords: f.geometry.coordinates, priority };
    });

    map.on("move", layoutAssetMarkers);
    map.on("zoom", layoutAssetMarkers);
    map.on("resize", layoutAssetMarkers);

    map.on("click", "basins-fill", (e) => {
      if (e.features?.length) selectBasinById(e.features[0].properties.basin_id);
    });
    map.on("mouseenter", "basins-fill", () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "basins-fill", () => { map.getCanvas().style.cursor = ""; });

    map.on("click", "barriers-circle", (e) => {
      if (e.features?.length) selectBarrierByIdx(e.features[0].properties.idx);
    });
    map.on("mouseenter", "barriers-circle", () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "barriers-circle", () => { map.getCanvas().style.cursor = ""; });

    selectBasinById(STATS.basins_summary[0].basin_id);
    const relBarrier = BARRIERS_GJ.features.find((f) => f.properties.relevant) || BARRIERS_GJ.features[0];
    if (relBarrier) selectBarrierByIdx(relBarrier.properties.idx);

    // Si el mapa termina de cargar con el lector ya a mitad del informe, activar el paso visible
    const mid = window.innerHeight * 0.45;
    const visible = [...document.querySelectorAll(".narrative-col [data-step]")].find((c) => {
      const r = c.getBoundingClientRect();
      return r.top <= mid && r.bottom >= mid;
    });
    activateStep(visible ? visible.dataset.step : "summary");
  });

  // Controles interactivos
  document.getElementById("db-slider").addEventListener("input", (e) => {
    activeDhbMode = "threshold";
    document.querySelectorAll("[data-dhb-mode]").forEach((b) => b.classList.toggle("active", b.dataset.dhbMode === "threshold"));
    updateThresholdReadout(Number(e.target.value));
  });

  document.querySelectorAll("[data-db-preset]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const v = Number(btn.dataset.dbPreset);
      document.getElementById("db-slider").value = v;
      activeDhbMode = "threshold";
      document.querySelectorAll("[data-dhb-mode]").forEach((b) => b.classList.toggle("active", b.dataset.dhbMode === "threshold"));
      updateThresholdReadout(v);
    });
  });

  document.querySelectorAll("[data-dhb-mode]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-dhb-mode]").forEach((b) => b.classList.toggle("active", b === btn));
      applyDhbMode(btn.dataset.dhbMode);
    });
  });

  document.querySelectorAll("[data-cap2-hv]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-cap2-hv]").forEach((b) => b.classList.toggle("active", b === btn));
      activeCap2HvKey = btn.dataset.cap2Hv;
      if (activeStep === "2") configureCompareForStep("2");
    });
  });

  document.querySelectorAll("[data-opt-key]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-opt-key]").forEach((b) => b.classList.toggle("active", b === btn));
      activeOptKey = btn.dataset.optKey;
      if (activeStep === "4") configureCompareForStep("4");
    });
  });
  document.querySelectorAll("[data-rad-key]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-rad-key]").forEach((b) => b.classList.toggle("active", b === btn));
      activeRadKey = btn.dataset.radKey;
      if (activeStep === "4") configureCompareForStep("4");
    });
  });

  document.querySelectorAll("[data-basin-field]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-basin-field]").forEach((b) => b.classList.toggle("active", b === btn));
      updateBasinSensitivity(btn.dataset.basinField);
    });
  });

  document.getElementById("barrier-inspector")?.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-barrier-idx]");
    if (btn) selectBarrierByIdx(Number(btn.dataset.barrierIdx));
  });

  document.getElementById("rain-slider").addEventListener("input", (e) => {
    updateRainMapLayer(Number(e.target.value));
  });

  document.getElementById("btn-print").addEventListener("click", () => window.print());
  document.getElementById("btn-lang").addEventListener("click", () => {
    applyLanguage(activeLang === "es" ? "en" : "es");
  });

  // Scrollytelling observer + progress bar
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          activateStep(entry.target.dataset.step);
        }
      }
    },
    { threshold: 0, rootMargin: "-35% 0px -45% 0px" }
  );
  document.querySelectorAll(".narrative-col [data-step]").forEach((el) => observer.observe(el));

  window.addEventListener("scroll", () => {
    const doc = document.documentElement;
    const pct = (doc.scrollTop / Math.max(doc.scrollHeight - doc.clientHeight, 1)) * 100;
    document.getElementById("progress-fill").style.width = `${Math.min(100, Math.max(0, pct))}%`;
    if (window.scrollY < 40 && activeStep !== "summary") {
      activateStep("summary");
    } else {
      updateTocLabel();
    }
  }, { passive: true });
}

init().catch((err) => {
  console.error("GeoSignal StoryMap init error:", err);
});
