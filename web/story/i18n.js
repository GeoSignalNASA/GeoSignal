// Diccionario completo ES / EN para narrativa, controles, gráficos, tablas, leyenda e inspectores de GeoSignal

export const I18N = {
  es: {
    docTitle: "GeoSignal — Análisis SAR en Banda L · Calvos de Randín",
    tocAria: "Capítulos del análisis",
    mapAria: "Mapa geoespacial interactivo de Calvos de Randín",
    langBtn: "EN",
    printBtn: "Imprimir / PDF",
    tocLabels: [
      "Panorama",
      "1. Incendio",
      "2. Retrodispersión",
      "3. Serie Jul–Oct",
      "4. Óptico vs Radar",
      "5. Cobertura y HH/HV",
      "6. Microcuencas",
      "7. Drenaje D8",
      "8. Replicabilidad",
      "9. Umbrales ΔHV",
      "10. Auditoría QA",
    ],
    overlayLabels: {
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
      osmTerrain: "Territorio real (OSM)",
    },
    legends: {
      summary: [
        { color: "#8E4321", label: "Perímetro EFFIS (1.234 ha)" },
        { color: "#46603A", label: "Núcleos / embalses OSM" },
      ],
      "1": [
        { color: "#8E4321", label: "Perímetro EFFIS" },
        { color: "#46603A", label: "Núcleos / embalses OSM" },
      ],
      "2": [
        { color: "#E9DFCE", label: "HV alto (dosel 3D)" },
        { color: "#2C2824", label: "HV bajo (suelo / agua)" },
      ],
      "3": [
        { color: "#E9DFCE", label: "HV alto (dosel 3D)" },
        { color: "#2C2824", label: "HV bajo (suelo / agua)" },
      ],
      "4": [
        { color: "#8E4321", label: "Perímetro EFFIS" },
        { color: "#CC6B2C", label: "Severidad NISAR" },
      ],
      "5": [
        { color: "#CC6B2C", label: "Moderada (-1,5 a -3 dB)" },
        { color: "#9E3520", label: "Alta (-3 a -6 dB)" },
        { color: "#5A1410", label: "Extrema (≤ -6 dB)" },
      ],
      "6": [
        { color: "#4D85A8", label: "Caída HH (≤ -1,2 dB)" },
        { color: "#C9822B", label: "Aumento HH (≥ +2,2 dB)" },
      ],
      "7": [
        { color: "#86B0A9", label: "Riesgo bajo" },
        { color: "#478189", label: "Medio" },
        { color: "#13344A", label: "Alto (#8 y #9)" },
      ],
      "8": [
        { color: "#478189", label: "Escorrentía moderada" },
        { color: "#255A6E", label: "Caudal acumulado alto" },
        { color: "#D98E3A", label: "Fajina prioritaria (< 3 km)" },
      ],
      "9": [
        { color: "#13344A", label: "Cuencas críticas" },
        { color: "#8E4321", label: "Drenaje y perímetro" },
      ],
    },
    landcoverNames: {
      Arbolado: "Arbolado",
      Matorral: "Matorral",
      "Pasto / herbáceo": "Pasto / herbáceo",
      Urbano: "Urbano",
    },
    dynamic: {
      locale: "es-ES",
      xuntaSub: (forest, shrub) => `${forest} ha arbolado + ${shrub} ha pasto`,
      nisarSub: (oct01, raw, oct25) => `01-oct (100m): ${oct01} ha · 20m raw: ${raw} ha · 25-oct seco: ${oct25} ha`,
      dhvSub: (offset, oct25Mean) =>
        `Neto vs control 01-oct (+${offset} dB lluvia) · 25-oct seco: ${oct25Mean ?? "—"} dB`,
      basinsJoin: (a, b) => `#${a} y #${b}`,
      basinsSub: (total) => `Lideran las ${total} cuencas (>20× sobre la #3)`,
      polHvLabel: "HV (cruzada · copa 3D)",
      polHhLabel: "HH (paralela · suelo/tronco)",
      polNet: (v) => `(neto ${v ?? "—"})`,
      hhBounceNote: (pct, hhCtrl) =>
        `El ${pct}% de los píxeles del perímetro muestran aumento de HH ≥ +1 dB el 01-oct (combinando el salto de humedad del control +${hhCtrl} dB y doble rebote en troncos).`,
      dnbrNote: (pre, post, lowHa, highHa, oct25Ha, r) =>
        `<strong>Validación cruzada óptica (Sentinel-2 dNBR, ${pre} → ${post}):</strong> ` +
        `<strong>${lowHa} ha</strong> con dNBR ≥ 0,10 (<strong>${highHa} ha</strong> severidad alta ≥ 0,44), ` +
        `coincidiendo en orden de magnitud con las 518 ha oficiales y las <strong>${oct25Ha} ha</strong> NISAR seco del 25-oct ` +
        `(correlación píxel a píxel <code>r = ${r}</code> entre dNBR y ΔHV_oct25).`,
      octCalSuffix: "(sin sesgo)",
      octCalFp: "control ≈ 0 dB",
      oct25Suffix: "(25-oct seco)",
      oct25Fp: "25-oct seco",
      tsReadout: (dt, hvFire, hvCtrl, sme, qaPass) =>
        `${dt} · HV perímetro: ${hvFire} dB · control: ${hvCtrl} dB · SME2: ${sme ?? "—"} m³/m³ · QA: ${qaPass ? "PASS" : "FLAG"}`,
      basinTitle: (id) => `Cuenca #${id}`,
      basinRank: (rank, total) => `puesto #${rank} de ${total}`,
      basinRiskLbl: "Riesgo medio (-1,5 dB)",
      basinBurnedLbl: "Quemado real",
      basinSlopeLbl: "Pendiente media",
      basinSmeLbl: "Humedad SME2 (01-oct)",
      basinSens: (ha3, r3, ha6, r6) =>
        `Sensibilidad: -3 dB → <strong>${ha3} ha</strong> (puesto #${r3}) · -6 dB → <strong>${ha6} ha</strong> (puesto #${r6})`,
      basinAssetsHead: "Activos OSM dentro de la cuenca:",
      basinAssetsNone:
        "Sin núcleos/embalses etiquetados dentro de esta subcuenca; el drenaje continúa aguas abajo hacia la red del Limia/Salas.",
      barrierTitle: (n) => `Punto D8 #${n} · quiebre de pendiente`,
      barrierPriority: "Candidata prioritaria (&lt; 3 km)",
      barrierDistant: "Lejana (&gt; 14 km)",
      barrierDistLbl: "Distancia al perímetro",
      barrierBreakLbl: "Quiebre topográfico",
      barrierAreaLbl: "Área drenada arriba",
      barrierCoordLbl: "Coordenadas",
    },
  },

  en: {
    docTitle: "GeoSignal — L-Band SAR Severity & Runoff Analysis · Calvos de Randín",
    tocAria: "Analysis chapters",
    mapAria: "Interactive geospatial map of Calvos de Randín",
    skipLink: "Skip to content",
    brandSub: "Calvos de Randín",
    langBtn: "ES",
    printBtn: "Print / PDF",
    heroTitle: "Calvos de Randín: L-band SAR severity and post-fire hydrological susceptibility",
    heroLead:
      "NISAR L-band time series (June–October 2026), decibel-level severity (dB), smoke-free radar vs. optical comparison, and runoff susceptibility across 26 real micro-watersheds.",
    tocLabels: [
      "Overview",
      "1. Wildfire",
      "2. Backscatter",
      "3. Jul–Oct Series",
      "4. Optical vs Radar",
      "5. Cover & HH/HV",
      "6. Watersheds",
      "7. D8 Drainage",
      "8. Replicability",
      "9. ΔHV Thresholds",
      "10. QA Audit",
    ],
    kpi1K: "Official perimeter (Xunta)",
    kpi2K: "NRT Detection (EFFIS)",
    kpi2S: "Automated thermal/optical outline (fire_id 15925129)",
    kpi3K: "NISAR area (ΔHV ≤ −1.5 dB)",
    kpi4K: "Mean ΔHV change",
    kpi5K: "Critical watersheds",
    barTitle: "Estimated burned area by sensor and method",
    bar1Lbl: "Automated EFFIS (outer boundary)",
    bar2Lbl: "Xunta official (370 ha forest + 148 ha grass)",
    bar3Lbl: "NISAR L-band 20 m unsmoothed (with speckle)",
    bar4Lbl: "NISAR L-band smoothed 100 m (canopy core)",

    c1Num: "01 · Study area & timeline",
    c1Title: "The Calvos de Randín wildfire (September 24–27, 2026)",
    c1P1:
      "Between <strong>September 24 and 27, 2026</strong>, wildfire burned forest and shrubland across <strong>Calvos de Randín</strong>, Feás, and <strong>As Meaus (Baltar)</strong>, triggering a preventive Level-2 civil protection alert near villages draining toward the <strong>Salas Reservoir</strong> and the <strong>Limia River</strong>.",
    c1P2:
      "On <strong>October 27, 2026</strong>, the Spanish Government formally declared both Calvos de Randín and Quiroga as Zones Severely Affected by a Civil Protection Emergency.",

    c2Num: "02 · L-band backscatter principles",
    c2Title: "24 cm microwave penetration and polarimetric response",
    c2P1:
      "Unlike passive optical satellites, L-band SAR emits its own <strong>24 cm</strong> microwaves, penetrating dense smoke plumes and clouds day and night. Cross-polarized <strong>HV</strong> backscatter reacts to 3D tree canopy structure; when leaves and twigs burn off, volumetric scattering collapses.",
    c2CtrlLbl: "NISAR HV backscatter on map:",
    c2BtnPre: "Sep 19 · HV pre (bright canopy)",
    c2BtnPost: "Oct 1 · HV post (post-fire drop)",
    c2Tip:
      "<strong>Polarimetric interpretation:</strong><br/>· <strong>HV (cross-polarized)</strong> = sensitive to 3D canopy volume (twigs & foliage). Canopy combustion attenuates HV.<br/>· <strong>HH (co-polarized)</strong> = sensitive to bare soil, moisture, and <em>double-bounce</em> off standing trunks.<br/>· <strong>Decibels (dB)</strong>: <code>−1.5 dB</code> = <strong>29%</strong> power loss; <code>−3 dB</code> = <strong>50%</strong>; <code>−6 dB</code> = <strong>75%</strong>.",

    c3Num: "03 · Time series (June–October 2026)",
    c3Title: "Pre-fire seasonal baseline vs. the October 1 backscatter drop",
    c3P1:
      "NISAR maps this corridor (<strong>Track 15 / Frame 23 ascending</strong>) every <strong>12 days</strong>. Comparing all 10 available passes since late June against an <strong>unburned exterior control ring</strong> shows summer stability before the abrupt post-fire step.",
    c3ChartL: "Mean HV (dB) · select acquisition",
    c3ChartR: "bars: SME2 moisture",
    c3Note:
      "Amber markers flag passes highlighted during radiometric stability QA (Provisional products), retained with explicit disclosure.",

    c4Num: "04 · Multisensor observation",
    c4Title: "Optical obscuration by smoke and cloud cover vs. SAR acquisition",
    c4P1:
      "On <strong>September 25</strong> (active fire), Sentinel-2 captures the smoke plume hiding the hillside; on <strong>September 30</strong>, 91% of the scene is covered by clouds. NISAR L-band delivers a clean structural scan on <strong>October 1</strong> (and consolidated dry soil on Oct 25), verified against post-fire optical dNBR.",
    c4LeftLbl: "Left panel (real Sentinel-2 optical):",
    c4Opt1: "Sep 25 (active smoke)",
    c4Opt2: "Sep 30 (91% clouds)",
    c4Opt3: "Oct 15 (clear burn scar)",
    c4RightLbl: "Right panel (NISAR L-band / dNBR check):",
    c4Rad1: "ΔHV severity (Oct 1)",
    c4Rad2: "ΔHV severity (Oct 25 dry)",
    c4Rad3: "HV post (Oct 1)",
    c4Rad4: "Sentinel-2 dNBR (Sep 20→Oct 15)",

    c5Num: "09 · Parametric ΔHV sensitivity",
    c5Title: "Burn severity distribution across decibel thresholds (ΔHV)",
    c5P1:
      "Not everything that burns loses the same structure. Splitting <code>ΔHV = HV(post) − HV(Sep 19)</code> into physical backscatter drop thresholds separates moderate crown scorch from severe canopy loss:",
    c5ThLvl: "ΔHV level",
    c5ThHa: "Hectares",
    c5ThPct: "% perimeter",
    c5ModeLbl: "Pass / calibration applied to table and map:",
    c5Mode1: "Oct 1 raw (88.8 ha)",
    c5Mode2: "Oct 1 rain-debiased (221.0 ha)",
    c5Mode3: "Oct 25 dry consolidated (373.6 ha)",
    c5Mode4: "Continuous map threshold",
    c5Mode5: "ΔHV ramp",
    c5CalNote:
      "The <strong>October 1</strong> pass recorded a soil-moisture jump (SME2 0.18→0.23 m³/m³) lifting the exterior control ring by <strong>+1.22 dB</strong>. Removing that bias reveals 221 ha; once soils dry by <strong>October 25</strong>, <strong>373.6 ha</strong> emerge (≈ 370 ha official forest).",
    c5SliderLbl: "Applied ΔHV threshold:",
    c5Pre1: "-1.5 dB (standard)",
    c5Pre2: "-3.0 dB (-50% signal)",
    c5Pre3: "-6.0 dB (-75% signal)",
    c5M1: "Burned area (100 m)",
    c5M2: "Unsmoothed 20 m area",
    c5M3: "False positives (control)",
    c5M4: "Canopy energy lost",
    c5Ch1L: "Hectares vs. dB threshold",
    c5Ch1R: "amber = exterior false positives",
    c5Ch2: "ΔHV distribution: perimeter (terracotta) vs. control (teal)",

    c6Num: "05 · Resolution, polarization & land cover",
    c6Title: "Multilooking effects, HH/HV contrast & land-cover response",
    c6P1:
      "Earth-science rigor requires naming sensor limits: L-band SAR accurately measures 3D canopy loss and top ~5 cm soil moisture (SME2), yet it <strong>does not chemically detect</strong> hydrophobic soil crusts and responds weakly to burned short grass.",
    c6P2:
      "Crossing NISAR ΔHV with <strong>ESA WorldCover 10 m</strong> inside the perimeter confirms L-band selectivity: forest stands suffer far larger net drops than grassland/herbaceous cover, while parallel <strong>HH</strong> captures ground–trunk double-bounce.",
    c6ThCov: "Land cover (WorldCover)",
    c6ThArea: "EFFIS area",
    c6ThO1: "ΔHV Oct 1 (net)",
    c6ThO25: "ΔHV Oct 25 (dry)",
    c6ThPct: "% ≤−1.5 dB (Oct 25)",
    c6ThPol: "Polarization",
    c6ThPer: "Perimeter",
    c6ThCtrl: "Control",
    c6ThSep: "Separation",

    c7Num: "06 · Hydrological susceptibility (26 micro-watersheds)",
    c7Title: "Post-fire sediment susceptibility by micro-watershed & downstream receptors",
    c7P1:
      "Combining canopy burn severity (<strong>ΔHV</strong>), surface soil dryness (<strong>SME2</strong>), and topographic slope from the <strong>Copernicus GLO-30 DEM</strong> highlights which micro-watersheds concentrate post-fire erosion risk toward the Limia and Salas headwaters.",
    c7SensLbl: "Ranking sensitivity by minimum burn severity:",
    c7Btn1: "−1.5 dB threshold",
    c7Btn2: "Severity ≥ −3.0 dB",
    c7Btn3: "Extreme ≥ −6.0 dB",
    c7Prompt: "Click a watershed on the map…",

    c8Num: "07 · D8 drainage routing",
    c8Badge: "Simulation C = 0.6",
    c8Title: "Surface runoff routing and candidate retention points",
    c8P1:
      "Traces follow real <strong>D8 flow routing</strong> computed on the DEM from 8 perimeter points toward the Limia network and Salas Reservoir. Adjust hypothetical 24 h rainfall (assumed C = 0.6 runoff ratio) and inspect <strong>slope-break check-dam candidates</strong>.",
    c8SliderLbl: "Hypothetical 24h rainfall:",
    c8M1: "Burned-core runoff (Oct 25)",
    c8M2: "Accumulated basin flow (Salas/Limia)",
    c8BarTitle: "Retention barrier candidates (slope break)",
    c8BarPrompt: "Select a point on the map or click a candidate below to inspect terrain rationale.",
    c8Warn:
      "<strong>DEM tile edge:</strong> western streams end at the dashed −8.0° longitude line because the downloaded GLO-30 DEM tile terminates there, not because water stops flowing.",

    c9Num: "08 · Replicability & orbital synergy",
    c9Title: "Pipeline transfer to Quiroga (Ribeira Sacra) & Atlantic Constellation",
    c9P1:
      "The <strong>Ribeira Sacra wildfire (Sept 2025, 1,805 ha)</strong> proved how autumn rains on burned Galician hillslopes wash ash into the Cabe and Sil rivers. On <strong>October 27, 2026</strong>, both <strong>Calvos de Randín and Quiroga</strong> were declared disaster zones; this pipeline replicates directly by swapping the AOI.",
    c9Tip:
      "<strong>Multiscale observation:</strong><br/>Pairing <strong>NISAR</strong> (12-day high-resolution L-band structural mapping) with the upcoming <strong>Atlantic Constellation (Spain–Portugal PERTE, 16 microsatellites)</strong> would add ~3-hour revisits and GNSS-R rapid soil moisture linked to IoT rain gauges in critical basins.",

    c10Num: "10 · Radiometric QA log & limitations",
    c10Title: "NISAR acquisition audit, data sources & model constraints",
    c10P1:
      "Pass-by-pass radiometric audit across all 10 <code>GCOV</code> and <code>SME2</code> acquisitions used in this study, including Provisional calibration notices.",
    c10Th1: "Pass date",
    c10Th2: "Perimeter coverage",
    c10Th3: "Control mean HV",
    c10Th4: "Offset vs. median",
    c10Th5: "QA status",
    c10Warn:
      "<strong>Explicit limitations:</strong> Provisional NISAR products may carry minor radiometric offsets up to ±0.3 dB; D8 flow traces end at −8.0° W due to GLO-30 tile extent; m³ runoff totals assume C = 0.6 without stream-gauge calibration.",

    overlayLabels: {
      "hv_pre.png": "NISAR L-Band · HV pre (Sep 19)",
      "hv_post.png": "NISAR L-Band · HV post (Oct 1)",
      "dhv_classes.png": "NISAR L-Band · ΔHV severity (Oct 1)",
      "dhv_oct01_cal.png": "NISAR L-Band · ΔHV Oct 1 debiased",
      "dhv_oct25.png": "NISAR L-Band · ΔHV severity (Oct 25 dry)",
      "dhv_cont.png": "NISAR L-Band · Continuous ΔHV",
      "dhh.png": "NISAR L-Band · ΔHH (double-bounce)",
      "dnbr_s2.png": "Sentinel-2 dNBR (Sep 20 → Oct 15)",
      "optical_fire.jpg": "Sentinel-2 L2A 2026-09-25 (active fire)",
      "optical_clouds.jpg": "Sentinel-2 L2A 2026-09-30 (91% clouds)",
      "optical_post.jpg": "Sentinel-2 L2A 2026-10-15 (post-fire scar)",
      osmTerrain: "Real terrain (OSM)",
    },
    legends: {
      summary: [
        { color: "#8E4321", label: "EFFIS perimeter (1,234 ha)" },
        { color: "#46603A", label: "OSM villages / reservoirs" },
      ],
      "1": [
        { color: "#8E4321", label: "EFFIS perimeter" },
        { color: "#46603A", label: "OSM villages / reservoirs" },
      ],
      "2": [
        { color: "#E9DFCE", label: "High HV (3D canopy)" },
        { color: "#2C2824", label: "Low HV (bare ground / water)" },
      ],
      "3": [
        { color: "#E9DFCE", label: "High HV (3D canopy)" },
        { color: "#2C2824", label: "Low HV (bare ground / water)" },
      ],
      "4": [
        { color: "#8E4321", label: "EFFIS perimeter" },
        { color: "#CC6B2C", label: "NISAR severity" },
      ],
      "5": [
        { color: "#CC6B2C", label: "Moderate (-1.5 to -3 dB)" },
        { color: "#9E3520", label: "High (-3 to -6 dB)" },
        { color: "#5A1410", label: "Extreme (≤ -6 dB)" },
      ],
      "6": [
        { color: "#4D85A8", label: "HH drop (≤ -1.2 dB)" },
        { color: "#C9822B", label: "HH rise (≥ +2.2 dB)" },
      ],
      "7": [
        { color: "#86B0A9", label: "Low risk" },
        { color: "#478189", label: "Medium" },
        { color: "#13344A", label: "High (#8 & #9)" },
      ],
      "8": [
        { color: "#478189", label: "Moderate runoff" },
        { color: "#255A6E", label: "High accumulated flow" },
        { color: "#D98E3A", label: "Priority barrier (< 3 km)" },
      ],
      "9": [
        { color: "#13344A", label: "Critical basins" },
        { color: "#8E4321", label: "Drainage & perimeter" },
      ],
    },
    landcoverNames: {
      Arbolado: "Tree cover",
      Matorral: "Shrubland",
      "Pasto / herbáceo": "Grassland / Herbaceous",
      Urbano: "Built-up",
    },
    dynamic: {
      locale: "en-US",
      xuntaSub: (forest, shrub) => `${forest} ha forest + ${shrub} ha grassland`,
      nisarSub: (oct01, raw, oct25) => `Oct 1 (100m): ${oct01} ha · 20m raw: ${raw} ha · Oct 25 dry: ${oct25} ha`,
      dhvSub: (offset, oct25Mean) =>
        `Net vs Oct 1 control (+${offset} dB rain) · Oct 25 dry: ${oct25Mean ?? "—"} dB`,
      basinsJoin: (a, b) => `#${a} & #${b}`,
      basinsSub: (total) => `Top among ${total} basins (>20× higher than #3)`,
      polHvLabel: "HV (cross · 3D canopy)",
      polHhLabel: "HH (parallel · ground/trunk)",
      polNet: (v) => `(net ${v ?? "—"})`,
      hhBounceNote: (pct, hhCtrl) =>
        `${pct}% of perimeter pixels show an HH rise ≥ +1 dB on Oct 1 (combining the +${hhCtrl} dB control moisture jump with trunk double-bounce).`,
      dnbrNote: (pre, post, lowHa, highHa, oct25Ha, r) =>
        `<strong>Optical cross-check (Sentinel-2 dNBR, ${pre} → ${post}):</strong> ` +
        `<strong>${lowHa} ha</strong> with dNBR ≥ 0.10 (<strong>${highHa} ha</strong> high severity ≥ 0.44), ` +
        `matching the order of magnitude of the 518 ha official perimeter and <strong>${oct25Ha} ha</strong> dry Oct 25 NISAR area ` +
        `(pixel-wise correlation <code>r = ${r}</code> between dNBR and ΔHV_oct25).`,
      octCalSuffix: "(debiased)",
      octCalFp: "control ≈ 0 dB",
      oct25Suffix: "(Oct 25 dry)",
      oct25Fp: "Oct 25 dry",
      tsReadout: (dt, hvFire, hvCtrl, sme, qaPass) =>
        `${dt} · Perimeter HV: ${hvFire} dB · control: ${hvCtrl} dB · SME2: ${sme ?? "—"} m³/m³ · QA: ${qaPass ? "PASS" : "FLAG"}`,
      basinTitle: (id) => `Watershed #${id}`,
      basinRank: (rank, total) => `rank #${rank} of ${total}`,
      basinRiskLbl: "Mean risk (-1.5 dB)",
      basinBurnedLbl: "Actual burned",
      basinSlopeLbl: "Mean slope",
      basinSmeLbl: "SME2 moisture (Oct 1)",
      basinSens: (ha3, r3, ha6, r6) =>
        `Sensitivity: -3 dB → <strong>${ha3} ha</strong> (rank #${r3}) · -6 dB → <strong>${ha6} ha</strong> (rank #${r6})`,
      basinAssetsHead: "OSM assets inside watershed:",
      basinAssetsNone:
        "No settlements/reservoirs tagged inside this sub-basin; drainage continues downstream toward the Limia/Salas network.",
      barrierTitle: (n) => `D8 Point #${n} · slope break`,
      barrierPriority: "Priority candidate (&lt; 3 km)",
      barrierDistant: "Distant (&gt; 14 km)",
      barrierDistLbl: "Distance to perimeter",
      barrierBreakLbl: "Topographic break",
      barrierAreaLbl: "Upstream drained area",
      barrierCoordLbl: "Coordinates",
    },
  },
};
