// AOI must match data/config.py AOI_BBOX -- keep these in sync.
const AOI_BBOX = { minLon: -4.95, minLat: 40.20, maxLon: -4.35, maxLat: 40.65 };
const CENTER = [-4.65, 40.42];

const OSM_STYLE = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

// --- comparison slider: optical (with smoke) vs. radar severity ---

const beforeMap = new maplibregl.Map({
  container: "before-map",
  style: OSM_STYLE,
  center: CENTER,
  zoom: 10,
});

const afterMap = new maplibregl.Map({
  container: "after-map",
  style: OSM_STYLE,
  center: CENTER,
  zoom: 10,
});

// TODO (imagery owner): swap this tile source for true-color Sentinel-2
// around the fire date so the smoke/cloud cover is visible in the "before" pane.
// e.g. a Sentinel Hub WMS/XYZ endpoint with your API key.

afterMap.on("load", () => {
  // TODO (data pipeline owner): export data/out/risk_index.tif (or
  // burn_severity.tif) to a PNG with gdal_translate -of PNG -scale,
  // drop it at web/data/severity.png, and this will show it.
  afterMap.addSource("severity-overlay", {
    type: "image",
    url: "data/severity.png",
    coordinates: [
      [AOI_BBOX.minLon, AOI_BBOX.maxLat],
      [AOI_BBOX.maxLon, AOI_BBOX.maxLat],
      [AOI_BBOX.maxLon, AOI_BBOX.minLat],
      [AOI_BBOX.minLon, AOI_BBOX.minLat],
    ],
  });
  afterMap.addLayer({
    id: "severity-layer",
    type: "raster",
    source: "severity-overlay",
    paint: { "raster-opacity": 0.75 },
  });
});

new maplibregl.Compare(beforeMap, afterMap, "#compare-container");

// --- risk-by-basin map ---

const riskMap = new maplibregl.Map({
  container: "risk-map",
  style: OSM_STYLE,
  center: CENTER,
  zoom: 10,
});

const basinPanel = document.getElementById("basin-panel");

riskMap.on("load", () => {
  // TODO (data pipeline owner): produced by data/risk_index.py
  riskMap.addSource("basins", {
    type: "geojson",
    data: "data/basins_risk.geojson",
  });

  riskMap.addLayer({
    id: "basins-fill",
    type: "fill",
    source: "basins",
    paint: {
      "fill-color": [
        "interpolate",
        ["linear"],
        ["coalesce", ["get", "risk_mean"], 0],
        0, "#2b6cb0",
        0.5, "#ecc94b",
        1, "#c53030",
      ],
      "fill-opacity": 0.65,
    },
  });

  riskMap.addLayer({
    id: "basins-outline",
    type: "line",
    source: "basins",
    paint: { "line-color": "#ffffff", "line-width": 0.5, "line-opacity": 0.4 },
  });

  riskMap.on("click", "basins-fill", (e) => {
    const props = e.features[0].properties;
    renderBasinPanel(props);
  });

  riskMap.on("mouseenter", "basins-fill", () => {
    riskMap.getCanvas().style.cursor = "pointer";
  });
  riskMap.on("mouseleave", "basins-fill", () => {
    riskMap.getCanvas().style.cursor = "";
  });
});

function renderBasinPanel(props) {
  let assets = [];
  try {
    assets = JSON.parse(props.downstream_assets || "[]");
  } catch (e) {
    assets = [];
  }

  const riskMean = typeof props.risk_mean === "number" ? props.risk_mean.toFixed(2) : "—";
  const assetsHtml = assets.length
    ? `<ul>${assets.map((a) => `<li>${a.name} (${a.type})</li>`).join("")}</ul>`
    : "<p class='placeholder'>Sin activos registrados aguas abajo.</p>";

  basinPanel.innerHTML = `
    <h3>Cuenca ${props.name || props.id || ""}</h3>
    <div class="risk-score">${riskMean}</div>
    <p>riesgo medio (0–1)</p>
    <strong>Aguas abajo:</strong>
    ${assetsHtml}
  `;
}
