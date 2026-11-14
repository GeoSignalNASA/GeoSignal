import { I18N } from "./i18n.js";
import { renderPhysicsDiagrams } from "./physics.js";
import { renderHistogramChart, renderThresholdCurve, renderTimeseriesChart } from "./charts.js";

const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const RUNOFF_COEFF = 0.6;
const DEM_TILE_EDGE_LON = -8.0;

let STATS = null;
let OVERLAYS = null;
let BASINS_GJ = null;
let ASSETS_GJ = null;
let RAIN_SEGS_GJ = null;
let FIRE_GJ = null;

let map = null;
let compareInit = false;
let beforeMap = null;
let afterMap = null;
let q8Pixels = null; // { data, width, height, coordinates }
let activeLang = "es";
let activeStep = "1";
let activeSeriesDate = "2026-10-01";
let activeDbThreshold = -1.5;
let activeBasinThreshold = "risk_mean";
let activeRainMm = 60;
let activeDhbMode = "classes"; // "classes" | "threshold" | "continuous"
let assetMarkers = [];

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
      { id: "bg", type: "background", paint: { "background-color": "#12100c" } },
      {
        id: "basemap",
        type: "raster",
        source: "osm",
        paint: {
          "raster-opacity": 0.72,
          "raster-saturation": -0.82,
          "raster-brightness-max": 0.42,
          "raster-contrast": 0.18,
        },
      },
    ],
  };
}

function fmtEs(n, digits = 0) {
  return Number(n).toLocaleString("es-ES", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

function getBlockCenter() {
  const coords = OVERLAYS?.["hv_pre.png"]?.coordinates;
  if (!coords || coords.length < 4) return [-7.88, 41.91];
  const lng = (coords[0][0] + coords[1][0]) / 2;
  const lat = (coords[0][1] + coords[2][1]) / 2;
  return [lng, lat];
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
        dst[i] = 178; dst[i + 1] = 24; dst[i + 2] = 43; dst[i + 3] = 245;
      } else if (db <= -3.0) {
        dst[i] = 230; dst[i + 1] = 118; dst[i + 2] = 53; dst[i + 3] = 225;
      } else {
        dst[i] = 246; dst[i + 1] = 201; dst[i + 2] = 99; dst[i + 3] = 205;
      }
    }
  }
  ctx.putImageData(out, 0, 0);
  const bmp = await createImageBitmap(c);
  src.updateImage({ image: bmp, coordinates: info.coordinates });
  setLayerVisible("radar-overlay-layer", true);
}

function setAssetMarkersVisible(visible) {
  assetMarkers.forEach((m) => {
    m.getElement().style.display = visible ? "flex" : "none";
  });
}

function updateHud(title, sub, swatches) {
  document.getElementById("hud-title").textContent = title;
  document.getElementById("hud-sub").textContent = sub;
  const swEl = document.getElementById("legend-swatches");
  swEl.innerHTML = swatches
    .map((s) => `<span class="swatch"><i style="background:${s.color}"></i>${s.label}</span>`)
    .join("");
}

function showCompareMode(show) {
  const wrap = document.getElementById("compare-wrap");
  const labels = document.getElementById("compare-labels");
  wrap.classList.toggle("visible", show);
  labels.classList.toggle("visible", show);
  if (show && !compareInit) initCompareMaps();
  if (show && beforeMap && afterMap) {
    setTimeout(() => {
      beforeMap.resize();
      afterMap.resize();
    }, 60);
  }
}

function initCompareMaps() {
  if (compareInit) return;
  compareInit = true;
  const center = getBlockCenter();

  beforeMap = new maplibregl.Map({ container: "before-map", style: darkBaseStyle(), center, zoom: 11.4, attributionControl: false });
  afterMap = new maplibregl.Map({ container: "after-map", style: darkBaseStyle(), center, zoom: 11.4, attributionControl: false });
  beforeMap.on("error", () => {});
  afterMap.on("error", () => {});

  beforeMap.on("load", () => {
    const opt = OVERLAYS["optical_fire.jpg"];
    if (opt) {
      beforeMap.addSource("opt-src", { type: "image", url: opt.url, coordinates: opt.coordinates });
      beforeMap.addLayer({ id: "opt-lyr", type: "raster", source: "opt-src", paint: { "raster-opacity": 0.95 } });
    }
    beforeMap.addSource("perim-b", { type: "geojson", data: FIRE_GJ });
    beforeMap.addLayer({ id: "perim-b-lyr", type: "line", source: "perim-b", paint: { "line-color": "#39e8e0", "line-width": 2 } });
  });

  afterMap.on("load", () => {
    const hv = OVERLAYS["dhv_classes.png"];
    if (hv) {
      afterMap.addSource("rad-src", { type: "image", url: hv.url, coordinates: hv.coordinates });
      afterMap.addLayer({ id: "rad-lyr", type: "raster", source: "rad-src", paint: { "raster-opacity": 0.9 } });
    }
    afterMap.addSource("perim-a", { type: "geojson", data: FIRE_GJ });
    afterMap.addLayer({ id: "perim-a-lyr", type: "line", source: "perim-a", paint: { "line-color": "#39e8e0", "line-width": 2 } });
  });

  new maplibregl.Compare(beforeMap, afterMap, "#compare-container");
}

function updateCompareLayers(optKey, radKey) {
  if (!beforeMap || !afterMap) return;
  const oSrc = beforeMap.getSource("opt-src");
  const rSrc = afterMap.getSource("rad-src");
  if (oSrc && OVERLAYS[optKey]) oSrc.updateImage({ url: OVERLAYS[optKey].url, coordinates: OVERLAYS[optKey].coordinates });
  if (rSrc && OVERLAYS[radKey]) rSrc.updateImage({ url: OVERLAYS[radKey].url, coordinates: OVERLAYS[radKey].coordinates });
  document.getElementById("cmp-left-lbl").textContent = OVERLAYS[optKey]?.label || optKey;
  document.getElementById("cmp-right-lbl").textContent = OVERLAYS[radKey]?.label || radKey;
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
      0, "#3a6ea5",
      refFlow * 0.02, "#39e8e0",
      refFlow * 0.30, "#f6c963",
      refFlow * 0.60, "#e2793c",
      refFlow * 1.25, "#c2432e",
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
    0, "#243b55",
    maxR * 0.12, "#3a6ea5",
    maxR * 0.45, "#e2a33c",
    maxR, "#c2432e",
  ]);
}

function selectBasinById(basinId) {
  const feat = BASINS_GJ.features.find((f) => Number(f.properties.basin_id) === Number(basinId));
  if (!feat) return;
  const p = feat.properties;
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
    : `<p style="font-size:0.8rem;color:var(--text-muted);margin:0.35rem 0 0">Sin núcleos/embalses etiquetados dentro de esta subcuenca; el drenaje continúa aguas abajo hacia la red del Limia/Salas.</p>`;

  document.getElementById("basin-inspector").innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;gap:0.5rem">
      <strong style="font-size:1.05rem">Cuenca #${p.basin_id}</strong>
      <span class="step-badge">puesto #${p.rank} de ${BASINS_GJ.features.length}</span>
    </div>
    <div class="mini-metrics">
      <div class="mini-metric"><div class="k">Riesgo medio (-1,5 dB)</div><div class="v">${Number(p.risk_mean).toFixed(5)}</div></div>
      <div class="mini-metric"><div class="k">Quemado real</div><div class="v">${p.burned_pct}% (${p.burned_ha} ha)</div></div>
      <div class="mini-metric"><div class="k">Pendiente media</div><div class="v">${p.slope_mean_deg}°</div></div>
      <div class="mini-metric"><div class="k">Humedad SME2 (01-oct)</div><div class="v">${p.moisture_mean ?? "—"} m³/m³</div></div>
    </div>
    <div style="margin-top:0.55rem;font-size:0.78rem;color:var(--text-muted)">
      Sensibilidad: -3 dB → <strong>${p.burned_ha_3db} ha</strong> (puesto #${p.rank_3db}) · -6 dB → <strong>${p.burned_ha_6db} ha</strong> (puesto #${p.rank_6db})
    </div>
    <div style="margin-top:0.55rem;font-size:0.8rem"><strong>Activos OSM dentro de la cuenca:</strong>${assetsHtml}</div>
  `;

  if (map && map.getLayer("basins-selected")) {
    map.setFilter("basins-selected", ["==", ["get", "basin_id"], Number(basinId)]);
  }
}

function activateStep(stepId) {
  activeStep = String(stepId);
  document.querySelectorAll(".step-card").forEach((c) => {
    c.classList.toggle("is-active", c.dataset.step === activeStep);
  });
  showCompareMode(activeStep === "4");

  if (!map) return;

  // Reset de visibilidad base antes de activar la combinación del capítulo
  setLayerVisible("radar-overlay-layer", false);
  setLayerVisible("basins-fill", false);
  setLayerVisible("basins-outline", false);
  setLayerVisible("basins-selected", false);
  setLayerVisible("rain-lines", false);
  setLayerVisible("dem-edge-line", false);
  setLayerVisible("fire-fill", false);
  setAssetMarkersVisible(false);

  switch (activeStep) {
    case "1":
      flyToCamera([-7.84, 41.925], 11.4);
      setLayerVisible("fire-fill", true);
      setAssetMarkersVisible(true);
      updateHud("Capítulo 1 · El incendio", "Perímetro EFFIS (1.234 ha) y núcleos cercanos (As Meaus, Randín, Embalse de Salas).", [
        { color: "#39e8e0", label: "Perímetro EFFIS" },
        { color: "#f6c963", label: "Núcleos / embalses OSM" },
      ]);
      break;
    case "2":
      flyToCamera(getBlockCenter(), 11.5);
      updateRasterOverlay("hv_pre.png");
      updateHud("Capítulo 2 · Cómo ve el radar", "NISAR Banda L HV pre-incendio (19-sep): el bosque denso devuelve señal brillante (dispersión volumétrica).", [
        { color: "#d4d4d4", label: "HV alto (dosel 3D)" },
        { color: "#303030", label: "HV bajo (suelo / agua)" },
      ]);
      break;
    case "3":
      flyToCamera(getBlockCenter(), 11.5);
      updateRasterOverlay(`ts/${activeSeriesDate}`);
      updateHud(`Capítulo 3 · Serie Jul–Oct (${activeSeriesDate})`, "Haz clic en cualquier fecha del gráfico para inspeccionar esa pasada NISAR.", [
        { color: "#e2793c", label: "Media HV perímetro" },
        { color: "#9c9284", label: "Control no quemado" },
      ]);
      break;
    case "4":
      updateHud("Capítulo 4 · Óptico ciego vs Radar nítido", "Desliza la cortina: Sentinel-2 real con humo/nubes frente a NISAR Banda L.", [
        { color: "#39e8e0", label: "Perímetro EFFIS" },
        { color: "#e67635", label: "Severidad NISAR" },
      ]);
      break;
    case "5":
      flyToCamera(getBlockCenter(), 11.6);
      applyDhbMode(activeDhbMode);
      updateHud("Capítulo 5 · Niveles de dB (ΔHV)", "Mueve el umbral de dB o alterna entre 01-oct bruto, calibrado y 25-oct seco.", [
        { color: "#f6c963", label: "Moderada (-1,5 a -3 dB)" },
        { color: "#e67635", label: "Alta (-3 a -6 dB)" },
        { color: "#b2182b", label: "Extrema (≤ -6 dB)" },
      ]);
      break;
    case "6":
      flyToCamera(getBlockCenter(), 11.6);
      updateRasterOverlay("dhh.png");
      updateHud("Capítulo 6 · Polarizaciones HH vs HV", "Mapa ΔHH (azul = caída, dorado = aumento por doble rebote en troncos/humedad).", [
        { color: "#38bdf8", label: "Caída HH" },
        { color: "#f5b932", label: "Aumento HH (doble rebote)" },
      ]);
      break;
    case "7":
      flyToCamera([-7.88, 41.92], 10.7);
      setLayerVisible("basins-fill", true);
      setLayerVisible("basins-outline", true);
      setLayerVisible("basins-selected", true);
      setAssetMarkersVisible(true);
      updateHud("Capítulo 7 · Riesgo por microcuenca", "26 microcuencas reales (DEM Copernicus). Haz clic en una cuenca para ver métricas y activos.", [
        { color: "#3a6ea5", label: "Riesgo bajo" },
        { color: "#e2a33c", label: "Medio" },
        { color: "#c2432e", label: "Alto (#8 y #9)" },
      ]);
      break;
    case "8":
      flyToCamera([-7.91, 41.915], 10.9);
      setLayerVisible("basins-outline", true);
      setLayerVisible("rain-lines", true);
      setLayerVisible("dem-edge-line", true);
      setAssetMarkersVisible(true);
      updateRainMapLayer(activeRainMm);
      updateHud("Capítulo 8 · Escenario de lluvia", "Trazas D8 reales desde el perímetro × lluvia hipotética (C = 0,6 asumido).", [
        { color: "#39e8e0", label: "Escorrentía moderada" },
        { color: "#e2793c", label: "Caudal acumulado alto" },
      ]);
      break;
    case "9":
      flyToCamera([-7.86, 41.92], 10.3);
      setLayerVisible("basins-fill", true);
      setLayerVisible("basins-outline", true);
      setLayerVisible("rain-lines", true);
      setAssetMarkersVisible(true);
      updateHud("Capítulo 9 · Escalabilidad Ibérica", "Pipeline replicable a Quiroga/Ribeira Sacra y sinergia NISAR (12d) + Constelación Atlántica (3h).", [
        { color: "#c2432e", label: "Cuencas críticas" },
        { color: "#39e8e0", label: "Drenaje y perímetro" },
      ]);
      break;
  }
}

function renderSeverityTable(sevObj) {
  const tbody = document.getElementById("db-classes-tbody");
  tbody.innerHTML = sevObj.classes
    .map(
      (c) => `
      <tr>
        <td>${c.label}</td>
        <td class="num">${fmtEs(c.ha, 1)} ha</td>
        <td class="num">${c.pct}%</td>
      </tr>`
    )
    .join("");
}

function applyDhbMode(mode) {
  activeDhbMode = mode;
  if (mode === "classes") {
    updateRasterOverlay("dhv_classes.png");
    renderSeverityTable(STATS.severity_smooth);
  } else if (mode === "oct01_cal") {
    updateRasterOverlay("dhv_oct01_cal.png");
    renderSeverityTable(STATS.severity_oct01_calibrated || STATS.severity_smooth);
  } else if (mode === "oct25") {
    updateRasterOverlay("dhv_oct25.png");
    renderSeverityTable(STATS.severity_oct25 || STATS.severity_smooth);
  } else if (mode === "continuous") {
    updateRasterOverlay("dhv_cont.png");
    renderSeverityTable(STATS.severity_smooth);
  } else {
    renderLiveThresholdOverlay(activeDbThreshold);
    renderSeverityTable(STATS.severity_smooth);
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

  document.getElementById("kpi-xunta").textContent = `${fmtEs(m.official_xunta_ha)} ha`;
  document.getElementById("kpi-xunta-sub").textContent = `${m.official_forest_ha} ha arbolado + ${m.official_grass_ha} ha pasto`;
  document.getElementById("kpi-effis").textContent = `${fmtEs(m.effis_ha)} ha`;
  document.getElementById("kpi-nisar-smooth").textContent = `${fmtEs(sm.burned_total_ha, 1)} → ${fmtEs(oct25 ? oct25.burned_total_ha : sm.burned_total_ha, 1)} ha`;
  document.getElementById("kpi-nisar-sub").textContent = `01-oct (100m): ${fmtEs(sm.burned_total_ha, 1)} ha · 20m raw: ${fmtEs(raw.burned_total_ha, 0)} ha · 25-oct seco: ${fmtEs(oct25 ? oct25.burned_total_ha : sm.burned_total_ha, 1)} ha`;
  document.getElementById("kpi-dhv").textContent = `${pol.hv_fire_net_db ?? pol.hv_fire_mean_db} dB`;
  document.getElementById("kpi-dhv-sub").textContent = `Neto vs control 01-oct (+${pol.ctrl_offset_oct01_db ?? 0} dB lluvia) · 25-oct seco: ${pol.hv_oct25_fire_mean_db ?? "—"} dB`;
  document.getElementById("kpi-basins").textContent = `#${top1.basin_id} y #${top2.basin_id}`;
  document.getElementById("kpi-basins-sub").textContent = `Lideran las ${STATS.basins_summary.length} cuencas (>20× sobre la #3)`;

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
    <tr><td>HV (cruzada · copa 3D)</td><td class="num">${pol.hv_fire_mean_db} dB (neto ${pol.hv_fire_net_db ?? "—"})</td><td class="num">${pol.hv_ctrl_mean_db} dB</td><td class="num"><strong>${pol.hv_separation_db} dB</strong></td></tr>
    <tr><td>HH (paralela · suelo/tronco)</td><td class="num">${pol.hh_fire_mean_db} dB (neto ${pol.hh_fire_net_db ?? "—"})</td><td class="num">${pol.hh_ctrl_mean_db} dB</td><td class="num">${pol.hh_separation_db} dB</td></tr>
  `;
  document.getElementById("hh-double-bounce-note").textContent =
    `El ${pol.hh_double_bounce_pct_fire}% de los píxeles del perímetro muestran aumento de HH ≥ +1 dB el 01-oct (combinando el salto de humedad del control +${pol.hh_ctrl_mean_db} dB y doble rebote en troncos).`;

  const wcBody = document.getElementById("worldcover-tbody");
  wcBody.innerHTML = (STATS.landcover_2021 || [])
    .map(
      (w) => `
      <tr>
        <td>${w.name}</td>
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
    dnbrEl.innerHTML =
      `<strong>Validación cruzada óptica (Sentinel-2 dNBR, ${dnbr.pre_scene} → ${dnbr.post_scene}):</strong> ` +
      `<strong>${fmtEs(dnbr.burned_low_plus_ha, 1)} ha</strong> con dNBR ≥ 0,10 (<strong>${fmtEs(dnbr.burned_high_ha, 1)} ha</strong> severidad alta ≥ 0,44), ` +
      `coincidiendo en orden de magnitud con las 518 ha oficiales y las <strong>${fmtEs(oct25?.burned_total_ha || 0, 1)} ha</strong> NISAR seco del 25-oct ` +
      `(correlación píxel a píxel <code>r = ${dnbr.pearson_r_vs_dhv_oct25}</code> entre dNBR y ΔHV_oct25).`;
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

  renderThresholdCurve(document.getElementById("chart-threshold"), STATS.threshold_curve, db, STATS.meta);
  if (activeStep === "5" && activeDhbMode === "threshold") {
    renderLiveThresholdOverlay(db);
  }
}

// --- Header scroll-spy (independent from the map step observer) ---
// Watches EVERY section linked from the chapter menu (including Resumen and
// Límites, which are not step-cards) through a horizontal line at 45% of the
// viewport, so sections taller than the screen are handled too.
let activeChapter = -1;

// "3. Serie Jul–Oct" -> { num: "3", name: "Serie Jul–Oct" }; unnumbered -> num null
function parseChapterLabel(text) {
  const m = text.trim().match(/^(\d+)\.\s*(.*)$/);
  return m ? { num: m[1], name: m[2] } : { num: null, name: text.trim() };
}

function renderChapterIndicator(idx, direction = 0) {
  const links = [...document.querySelectorAll(".toc-pill")];
  if (!links[idx]) return;
  const total = links.filter((a) => parseChapterLabel(a.textContent).num !== null).length;
  const { num, name } = parseChapterLabel(links[idx].textContent);

  const count = document.getElementById("chapter-count");
  const pad = (n) => String(n).padStart(2, "0");
  count.textContent = num ? `${pad(num)} / ${pad(total)}` : "";
  count.hidden = !num;

  const viewport = document.getElementById("chapter-label-viewport");
  const current = viewport.querySelector(".chapter-label:not(.is-leaving)");
  if (current && current.textContent === name) return;

  const next = document.createElement("span");
  next.className = "chapter-label";
  next.textContent = name;

  if (!current || direction === 0) {
    viewport.replaceChildren(next);
    return;
  }

  // Slide the old label out and the new one in, following the scroll direction.
  const dir = direction > 0 ? "up" : "down";
  viewport.querySelectorAll(".is-leaving").forEach((el) => el.remove());
  current.classList.add("is-leaving", `leave-${dir}`);
  current.setAttribute("aria-hidden", "true");
  current.addEventListener("animationend", () => current.remove(), { once: true });
  next.classList.add(`enter-${dir}`);
  next.addEventListener("animationend", () => next.classList.remove(`enter-${dir}`), { once: true });
  viewport.appendChild(next);
}

function setActiveChapter(idx) {
  if (idx === activeChapter || idx < 0) return;
  const direction = activeChapter < 0 ? 0 : Math.sign(idx - activeChapter);
  activeChapter = idx;
  document.querySelectorAll(".toc-pill").forEach((link, i) => {
    const isActive = i === idx;
    link.classList.toggle("active", isActive);
    if (isActive) link.setAttribute("aria-current", "location");
    else link.removeAttribute("aria-current");
  });
  renderChapterIndicator(idx, direction);
}

function isChapterMenuOpen() {
  return document.getElementById("chapter-trigger").getAttribute("aria-expanded") === "true";
}

// Anchor the strip to the trigger's right edge (CSS ignores it on phones).
function positionChapterMenu() {
  const topbar = document.querySelector(".topbar");
  const trigger = document.getElementById("chapter-trigger");
  const left = trigger.getBoundingClientRect().right - topbar.getBoundingClientRect().left;
  topbar.style.setProperty("--chapter-menu-left", `${Math.round(left)}px`);
}

function scrollActiveChapterIntoStrip() {
  const menu = document.getElementById("chapter-menu");
  const active = menu.querySelector(".toc-pill.active");
  if (!active) return;
  menu.scrollLeft = active.offsetLeft - (menu.clientWidth - active.offsetWidth) / 2;
}

function setChapterMenuOpen(open) {
  const trigger = document.getElementById("chapter-trigger");
  const menu = document.getElementById("chapter-menu");
  if (open) positionChapterMenu();
  trigger.setAttribute("aria-expanded", String(open));
  menu.hidden = !open;
  if (open) scrollActiveChapterIntoStrip();
}

function initChapterMenu() {
  const nav = document.querySelector(".chapter-nav");
  const trigger = document.getElementById("chapter-trigger");
  const menu = document.getElementById("chapter-menu");
  const links = () => [...menu.querySelectorAll(".toc-pill")];

  trigger.addEventListener("click", (e) => {
    const open = !isChapterMenuOpen();
    setChapterMenuOpen(open);
    // Keyboard activation (detail === 0): move focus straight into the strip.
    if (open && e.detail === 0) (menu.querySelector(".toc-pill.active") || links()[0]).focus();
  });

  trigger.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      e.preventDefault();
      setChapterMenuOpen(true);
      (menu.querySelector(".toc-pill.active") || links()[0]).focus();
    }
  });

  // Arrow keys / Home / End move between chapters, Escape closes.
  menu.addEventListener("keydown", (e) => {
    const all = links();
    const i = all.indexOf(document.activeElement);
    let target = null;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") target = all[Math.min(i + 1, all.length - 1)];
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") target = all[Math.max(i - 1, 0)];
    else if (e.key === "Home") target = all[0];
    else if (e.key === "End") target = all[all.length - 1];
    if (!target) return;
    e.preventDefault();
    target.focus();
    target.scrollIntoView({ inline: "nearest", block: "nearest" });
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && isChapterMenuOpen()) {
      setChapterMenuOpen(false);
      trigger.focus();
    }
  });

  // Jumping to a chapter: close the strip and hand focus to the section so
  // screen readers and Tab continue from there.
  menu.addEventListener("click", (e) => {
    const link = e.target.closest(".toc-pill");
    if (!link) return;
    setChapterMenuOpen(false);
    const section = document.querySelector(link.getAttribute("href"));
    if (section) {
      if (!section.hasAttribute("tabindex")) section.setAttribute("tabindex", "-1");
      section.focus({ preventScroll: true });
    }
  });

  // Close on outside click, when focus leaves the nav, or when the page scrolls.
  document.addEventListener("pointerdown", (e) => {
    if (isChapterMenuOpen() && !nav.contains(e.target)) setChapterMenuOpen(false);
  });
  nav.addEventListener("focusout", (e) => {
    if (isChapterMenuOpen() && e.relatedTarget && !nav.contains(e.relatedTarget)) setChapterMenuOpen(false);
  });
  window.addEventListener("scroll", () => {
    if (isChapterMenuOpen()) setChapterMenuOpen(false);
  }, { passive: true });

  // Vertical mouse wheel scrolls the strip sideways.
  menu.addEventListener("wheel", (e) => {
    if (Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return;
    e.preventDefault();
    menu.scrollLeft += e.deltaY;
  }, { passive: false });

  window.addEventListener("resize", () => {
    if (isChapterMenuOpen()) positionChapterMenu();
  });
}

function initChapterSpy() {
  const links = [...document.querySelectorAll(".toc-pill")];
  const sections = links.map((a) => document.querySelector(a.getAttribute("href")));

  const spy = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) setActiveChapter(sections.indexOf(entry.target));
      }
    },
    { threshold: 0, rootMargin: "-45% 0px -54% 0px" }
  );
  sections.forEach((s) => s && spy.observe(s));

  // The last section may be too short to ever cross the 45% line,
  // so mark it explicitly once the page bottom is reached.
  window.addEventListener("scroll", () => {
    const doc = document.documentElement;
    if (doc.scrollTop + doc.clientHeight >= doc.scrollHeight - 4) {
      setActiveChapter(sections.length - 1);
    }
  }, { passive: true });

  setActiveChapter(0);
}

function applyLanguage(lang) {
  activeLang = lang;
  const dict = I18N[lang];
  document.documentElement.lang = lang;
  document.getElementById("brand-sub").textContent = dict.brandSub;
  document.getElementById("btn-print").textContent = dict.printBtn;
  document.getElementById("btn-lang").textContent = dict.langBtn;
  document.getElementById("hero-eyebrow").textContent = dict.heroEyebrow;
  document.getElementById("hero-title").textContent = dict.heroTitle;
  document.getElementById("hero-lead").textContent = dict.heroLead;
  document.querySelectorAll(".toc-pill").forEach((el, idx) => {
    if (dict.tocLabels[idx]) el.textContent = dict.tocLabels[idx];
  });
  document.getElementById("chapter-nav").setAttribute("aria-label", dict.chapterNavLabel);
  document.getElementById("chapter-current-prefix").textContent = dict.currentChapterPrefix;
  if (activeChapter >= 0) renderChapterIndicator(activeChapter);
  renderPhysicsDiagrams(document.getElementById("physics-diagrams"), lang);
}

async function init() {
  const [stats, overlays, basins, assets, fire, rain] = await Promise.all([
    fetch("assets/data/story_stats.json").then((r) => r.json()),
    fetch("assets/data/overlays/overlays.json").then((r) => r.json()),
    fetch("assets/data/basins_risk.geojson").then((r) => r.json()),
    fetch("assets/data/assets.geojson").then((r) => r.json()),
    fetch("assets/data/fire_perimeter.geojson").then((r) => r.json()),
    fetch("assets/data/rain_channels.geojson").then((r) => r.json()),
  ]);

  STATS = stats;
  OVERLAYS = overlays;
  BASINS_GJ = basins;
  ASSETS_GJ = assets;
  FIRE_GJ = fire;
  RAIN_SEGS_GJ = buildRainSegmentsGeoJson(rain);

  populateExecutiveSummary();
  renderPhysicsDiagrams(document.getElementById("physics-diagrams"), activeLang);
  renderHistogramChart(document.getElementById("chart-histogram"), STATS.histogram);

  const selectDate = (dt) => {
    activeSeriesDate = dt;
    const row = STATS.timeseries.find((t) => t.date === dt);
    if (row) {
      document.getElementById("ts-selected-readout").textContent =
        `${dt} · HV perímetro: ${row.hv_fire_mean} dB · control: ${row.hv_ctrl_mean} dB · SME2: ${row.sme2_fire_mean ?? "—"} m³/m³ · QA: ${row.qa_pass ? "PASS" : "FLAG"}`;
    }
    renderTimeseriesChart(document.getElementById("chart-timeseries"), STATS.timeseries, dt, selectDate);
    if (activeStep === "3") updateRasterOverlay(`ts/${dt}`);
  };
  selectDate("2026-10-01");
  updateThresholdReadout(-1.5);

  await decodeQ8Image();

  map = new maplibregl.Map({
    container: "story-map",
    style: darkBaseStyle(),
    center: [-7.84, 41.925],
    zoom: 11.4,
  });
  map.on("error", () => {});

  map.on("load", () => {
    const first = OVERLAYS["dhv_classes.png"];
    map.addSource("radar-overlay", { type: "image", url: first.url, coordinates: first.coordinates });
    map.addLayer({ id: "radar-overlay-layer", type: "raster", source: "radar-overlay", layout: { visibility: "none" }, paint: { "raster-opacity": 0.9 } });

    map.addSource("basins", { type: "geojson", data: BASINS_GJ });
    map.addLayer({ id: "basins-fill", type: "fill", source: "basins", layout: { visibility: "none" }, paint: { "fill-color": "#3a6ea5", "fill-opacity": 0.62 } });
    map.addLayer({ id: "basins-outline", type: "line", source: "basins", layout: { visibility: "none" }, paint: { "line-color": "#ede6da", "line-width": 0.8, "line-opacity": 0.4 } });
    map.addLayer({ id: "basins-selected", type: "line", source: "basins", filter: ["==", ["get", "basin_id"], -1], layout: { visibility: "none" }, paint: { "line-color": "#ffffff", "line-width": 2.4 } });
    updateBasinSensitivity("risk_mean");

    map.addSource("rain-segs", { type: "geojson", data: RAIN_SEGS_GJ });
    map.addLayer({ id: "rain-lines", type: "line", source: "rain-segs", layout: { visibility: "none", "line-cap": "round" }, paint: { "line-color": "#39e8e0", "line-width": 2, "line-opacity": 0.88 } });

    map.addSource("dem-edge", {
      type: "geojson",
      data: { type: "Feature", geometry: { type: "LineString", coordinates: [[DEM_TILE_EDGE_LON, 41.80], [DEM_TILE_EDGE_LON, 42.02]] } },
    });
    map.addLayer({ id: "dem-edge-line", type: "line", source: "dem-edge", layout: { visibility: "none" }, paint: { "line-color": "#9c9284", "line-width": 1.2, "line-dasharray": [4, 4] } });

    map.addSource("fire-perim", { type: "geojson", data: FIRE_GJ });
    map.addLayer({ id: "fire-fill", type: "fill", source: "fire-perim", layout: { visibility: "none" }, paint: { "fill-color": "#e2793c", "fill-opacity": 0.16 } });
    map.addLayer({ id: "fire-line", type: "line", source: "fire-perim", paint: { "line-color": "#39e8e0", "line-width": 2.2 } });

    // Marcadores HTML en píldoras compactas para núcleos/embalses OSM
    assetMarkers = ASSETS_GJ.features.map((f) => {
      const el = document.createElement("div");
      el.style.cssText =
        "display:inline-flex;align-items:center;gap:4px;padding:1px 6px;border-radius:999px;background:rgba(21,19,15,0.86);border:1px solid rgba(255,255,255,0.14);font:600 10px ui-monospace,monospace;color:#f3ede2;white-space:nowrap;pointer-events:none;box-shadow:0 1px 4px rgba(0,0,0,0.65);";
      const dotCol = f.properties.type === "reservoir" ? "#39e8e0" : "#f6c963";
      el.innerHTML = `<span style="width:6px;height:6px;border-radius:50%;background:${dotCol};flex-shrink:0"></span><span>${f.properties.name}</span>`;
      return new maplibregl.Marker({ element: el, anchor: "bottom", offset: [0, -4] }).setLngLat(f.geometry.coordinates).addTo(map);
    });

    map.on("click", "basins-fill", (e) => {
      if (e.features?.length) selectBasinById(e.features[0].properties.basin_id);
    });
    map.on("mouseenter", "basins-fill", () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "basins-fill", () => { map.getCanvas().style.cursor = ""; });

    selectBasinById(STATS.basins_summary[0].basin_id);
    activateStep("1");
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

  document.querySelectorAll("[data-opt-key]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-opt-key]").forEach((b) => b.classList.toggle("active", b === btn));
      const radKey = document.querySelector("[data-rad-key].active")?.dataset.radKey || "dhv_classes.png";
      updateCompareLayers(btn.dataset.optKey, radKey);
    });
  });
  document.querySelectorAll("[data-rad-key]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-rad-key]").forEach((b) => b.classList.toggle("active", b === btn));
      const optKey = document.querySelector("[data-opt-key].active")?.dataset.optKey || "optical_fire.jpg";
      updateCompareLayers(optKey, btn.dataset.radKey);
    });
  });

  document.querySelectorAll("[data-basin-field]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-basin-field]").forEach((b) => b.classList.toggle("active", b === btn));
      updateBasinSensitivity(btn.dataset.basinField);
    });
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
    { threshold: 0.45, rootMargin: "-15% 0px -35% 0px" }
  );
  document.querySelectorAll(".step-card[data-step]").forEach((el) => observer.observe(el));

  window.addEventListener("scroll", () => {
    const doc = document.documentElement;
    const pct = (doc.scrollTop / Math.max(doc.scrollHeight - doc.clientHeight, 1)) * 100;
    document.getElementById("progress-fill").style.width = `${Math.min(100, Math.max(0, pct))}%`;
  }, { passive: true });
}

// Header navigation does not depend on the data fetch, so it works even if init() fails.
initChapterSpy();
initChapterMenu();

init().catch((err) => {
  console.error("GeoSignal StoryMap init error:", err);
});
