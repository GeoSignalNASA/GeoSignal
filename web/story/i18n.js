// Diccionario completo ES / EN para narrativa, controles, gráficos, tablas, leyenda e inspectores de GeoSignal

export const I18N = {
  es: {
    docTitle: "GeoSignal - Análisis SAR en Banda L · Calvos de Randín",
    tocAria: "Capítulos del análisis",
    mapAria: "Mapa geoespacial interactivo de Calvos de Randín",
    langBtn: "EN",
    printBtn: "PDF",
    glossIntro: "Qué significan las siglas de esta introducción",
    glossSection: "Qué significan las siglas de este apartado",
    c10Toggle: "Ver fuentes y equipo",
    assetTypes: {
      hamlet: "aldea",
      village: "pueblo",
      reservoir: "embalse",
    },
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
      "10. Fuentes y equipo",
      "11. Alertas",
    ],
    overlayLabels: {
      "hv_pre.png": "NISAR Banda L · HV pre (19-sep)",
      "hv_post.png": "NISAR Banda L · HV post (01-oct)",
      "dhv_mt.png": "NISAR Banda L · Severidad multitemporal ΔHV (jul–oct)",
      "dhv_classes.png": "NISAR Banda L · Severidad ΔHV (01-oct)",
      "dhv_oct01_cal.png": "NISAR Banda L · ΔHV 01-oct sin sesgo",
      "dhv_oct25.png": "NISAR Banda L · Severidad ΔHV (25-oct seco)",
      "dhv_cont.png": "NISAR Banda L · ΔHV multitemporal continuo",
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
        { color: "#E9DFCE", label: "HV alto (ramas / hojas)" },
        { color: "#2C2824", label: "HV bajo (suelo / agua)" },
      ],
      "3": [
        { color: "#E9DFCE", label: "HV alto (ramas / hojas)" },
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
        { color: "#13344A", label: "Alto (cuencas de As Meaus y Calvos)" },
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
    a11Num: "11 · Alertas por correo",
    a11Title: "Avisos de lluvia sobre el monte quemado",
    a11P1:
      "Al suscribirte recibes por correo el informe de este estudio, escrito sin tecnicismos: cuánto se quemó, por dónde puede bajar el agua, qué dan los simuladores de arriba y qué significa para tu pueblo. Después solo te escribiremos cuando la previsión real anuncie lluvia fuerte sobre el monte quemado.",
    a11Offline:
      "<strong>Sección inactiva en este servidor:</strong> los avisos necesitan el servidor de alertas. Arranca la web con <code>python3 -m alerts serve</code> desde la raíz del repositorio y vuelve a cargar esta página.",
    a11FormH: "Recibir el informe y los avisos",
    a11Name: "Nombre (opcional)",
    a11Email: "Correo electrónico",
    a11Place: "Tu pueblo",
    a11Min: "Avisarme de lluvia a partir de",
    a11Min1: "Aviso amarillo (lluvia moderada)",
    a11Min2: "Alerta naranja (lluvia fuerte)",
    a11Min3: "Solo alerta roja (lluvia muy fuerte)",
    a11Tech: "Añadir el detalle técnico (hectáreas, volúmenes, microcuencas)",
    a11Subscribe: "Suscribirme",
    a11Test: "Enviarme el informe ahora",
    alerts: {
      locale: "es-ES",
      noPlace: "Sin pueblo concreto (aviso general)",
      exposure: { direct: "exposición alta", downstream: "exposición media", none: "exposición baja" },
      hint: {
        direct: (d) => `Exposición alta: está en la ladera que recoge directamente el agua del monte quemado (regato a unos ${d}).`,
        downstream: (d) => `Exposición media: está aguas abajo del incendio, a unos ${d} de un río o regato que trae agua del monte quemado.`,
        none: () => "Exposición baja: no está en el camino del agua que baja del monte quemado.",
        general: () => "El informe nombrará los pueblos más expuestos en lugar de uno concreto.",
      },
      badEmail: "Escribe una dirección de correo válida.",
      subscribed: (email) => `Suscripción guardada. ${email} recibirá el informe del estudio y, después, un aviso cuando la previsión alcance el nivel elegido.`,
      updated: (email) => `Suscripción actualizada para ${email}.`,
      sending: "Enviando el informe…",
      sent: (email) => `Informe enviado a ${email}. Revisa la bandeja de entrada (y la carpeta de spam).`,
      sendNote: "Este servidor todavía no tiene configurado el envío con Gmail: la suscripción se guarda, pero no saldrá ningún correo hasta configurarlo.",
      errors: {
        invalid_email: "Escribe una dirección de correo válida.",
        invalid: "Revisa los datos del formulario.",
        smtp_not_configured: "El envío con Gmail no está configurado en este servidor.",
        smtp_failed: "Gmail rechazó el envío. Revisa la cuenta y la contraseña de aplicación.",
        forbidden: "El informe solo se puede enviar al momento desde el equipo que ejecuta el servidor.",
        forecast_unavailable: "No se pudo consultar la previsión.",
        network: "No hay conexión con el servidor de alertas.",
      },
    },
    dynamic: {
      locale: "es-ES",
      xuntaSub: (forest, shrub) => `${forest} ha arbolado + ${shrub} ha pasto`,
      nisarSub: (oct01, rawMt, f1) => `5 pre + 2 post secas (F1=${f1} vs dNBR) · 01-oct mojado: ${oct01} ha`,
      dhvSub: (offset, oct25Mean) =>
        `Compuesto jul–oct · 01-oct (+${offset} dB lluvia) · 25-oct: ${oct25Mean ?? "—"} dB`,
      basinsJoin: (a, b) => `${a} y ${b}`,
      basinsSub: (total, third) => `Lideran las ${total} cuencas (>4,7× sobre la cuenca de ${third})`,
      polHvLabel: "HV (cruzada · ramas/hojas)",
      polHhLabel: "HH (paralela · suelo/tronco)",
      polNet: (v) => `(neto ${v ?? "—"})`,
      hhBounceNote: (pct, hhCtrl) =>
        `El ${pct}% de los píxeles del perímetro muestran aumento de HH ≥ +1 dB el 01-oct (combinando el salto de humedad del control +${hhCtrl} dB y doble rebote en troncos).`,
      dnbrNote: (pre, post, refHa, tpHa, sarHa, f1, omHa, omDhv, r) =>
        `<strong>Validación cruzada óptica (Sentinel-2 dNBR, ${pre} → ${post}):</strong> ` +
        `De las <strong>${sarHa} ha</strong> detectadas por NISAR multitemporal, <strong>${tpHa} ha</strong> coinciden ` +
        `con cicatriz dNBR ≥ 0,27 (<strong>${refHa} ha</strong> en óptico; <code>F1 = ${f1}</code>, <code>r = ${r}</code>). ` +
        `Las <strong>${omHa} ha</strong> restantes son fuego bajo copa o quema leve invisible a 24 cm (<code>ΔHV medio = ${omDhv} dB</code>).`,
      oct01WetSuffix: "(20m 01-oct mojado)",
      oct01WetFp: "0,0% (enmascarado)",
      octCalSuffix: "(sin sesgo)",
      octCalFp: "control ≈ 0 dB",
      oct25Suffix: "(25-oct seco)",
      oct25Fp: "25-oct seco",
      tsReadout: (dt, hvFire, hvCtrl, sme, qaPass) =>
        `${dt} · HV perímetro: ${hvFire} dB · control: ${hvCtrl} dB · SME2: ${sme ?? "—"} m³/m³ · QA: ${qaPass ? "PASS" : "FLAG"}`,
      basinTitle: (id, place) => (place ? `Cuenca de ${place}` : `Cuenca #${id}`),
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
      barrierTitle: (dist) => `Candidato a barrera · ${dist} del perímetro`,
      barrierPriority: "Candidata prioritaria (&lt; 3 km)",
      barrierDistant: "Lejana (&gt; 14 km)",
      barrierDistLbl: "Distancia al perímetro",
      barrierBreakLbl: "Quiebre topográfico",
      barrierAreaLbl: "Área drenada arriba",
      barrierCoordLbl: "Coordenadas",
    },
  },

  en: {
    docTitle: "GeoSignal - L-Band SAR Severity & Runoff Analysis · Calvos de Randín",
    tocAria: "Analysis chapters",
    mapAria: "Interactive geospatial map of Calvos de Randín",
    skipLink: "Skip to content",
    brandSub: "Calvos de Randín",
    langBtn: "ES",
    printBtn: "PDF",
    glossIntro: "What the acronyms in this overview mean",
    glossSection: "What the acronyms in this section mean",
    c10Toggle: "View sources & team",
    assetTypes: {
      hamlet: "hamlet",
      village: "village",
      reservoir: "reservoir",
    },
    heroTitle: "Calvos de Randín: the fire seen by radar, and the water risk that follows",
    heroLead:
      "NISAR L-band time series (June–October 2026), decibel-level severity (dB), smoke-free radar vs. optical comparison, and runoff susceptibility across 26 real micro-watersheds.",
    heroGloss:
      "<dt>ha (hectare)</dt><dd>Unit of area. 1 ha = 100 × 100 m, about one and a half football pitches.</dd><dt>dB (decibel)</dt><dd>Measures how much radar signal comes back to the satellite. The lower (more negative), the less vegetation is left.</dd><dt>NRT (near real time)</dt><dd>Automatic satellite detection within days of the fire - before anyone measures it on the ground.</dd><dt>EFFIS</dt><dd>European (Copernicus) service that detects wildfires by satellite across the EU.</dd>",
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
      "11. Alerts",
    ],
    kpi1K: "Official perimeter (Xunta)",
    kpi2K: "NRT Detection (EFFIS)",
    kpi2S: "Automated thermal/optical outline (EFFIS fire ID: 15925129)",
    kpi3K: "NISAR area (ΔHV ≤ −1.5 dB)",
    kpi4K: "Mean ΔHV change",
    kpi5K: "Critical watersheds",
    barTitle: "Estimated burned area by sensor and method",
    bar1Lbl: "Automated EFFIS (outer boundary)",
    bar2Lbl: "Xunta official (370 ha forest + 148 ha grass)",
    bar3Lbl: "Sentinel-2 dNBR ≥ 0.27 (optical reference)",
    bar4Lbl: "NISAR linear multitemporal (−1.5 dB, dry passes)",
    bar5Lbl: "NISAR single Oct 1 pair (wet-soil bias)",

    c1Num: "01 · Study area & timeline",
    c1Title: "The Calvos de Randín wildfire (September 24–27, 2026)",
    c1P1:
      "Between <strong>September 24 and 27, 2026</strong>, wildfire burned forest and shrubland across <strong>Calvos de Randín</strong>, Feás, and <strong>As Meaus (Baltar)</strong>, triggering a preventive Level-2 civil protection alert near villages draining toward the <strong>Salas Reservoir</strong> and the <strong>Limia River</strong>.",
    c1P2:
      "To avoid inflating the numbers, we didn't measure inside a square drawn by eye on the map (that would multiply the burned area by ~4.5). We used the real fire outline detected by <strong>Copernicus EFFIS</strong> (the European wildfire detection service), and the real villages and reservoirs downstream from <strong>OpenStreetMap</strong> (the free, collaborative map).",
    c1Gloss:
      "<dt>ha (hectare)</dt><dd>Unit of area. 1 ha = 100 × 100 m.</dd><dt>EFFIS</dt><dd>European automatic wildfire-detection service.</dd><dt>OpenStreetMap</dt><dd>A free, volunteer-made map of the world - our source for the real villages and reservoirs.</dd>",

    c2Num: "02 · L-band backscatter principles",
    c2Title: "24 cm microwave penetration and polarimetric response",
    c2P1:
      "Unlike passive optical satellites, L-band SAR emits its own <strong>24 cm</strong> microwaves, penetrating dense smoke plumes and clouds day and night. Cross-polarized <strong>HV</strong> backscatter reacts to 3D tree canopy structure; when leaves and twigs burn off, volumetric scattering collapses.",
    c2CtrlLbl: "NISAR HV backscatter on map:",
    c2BtnPre: "Sep 19 · HV pre (bright canopy)",
    c2BtnPost: "Oct 1 · HV post (post-fire drop)",
    c2Tip:
      "<strong>Polarimetric interpretation:</strong><br/>· <strong>HV</strong> (one of the two signals the radar measures) is sensitive to a tree's branches and leaves. When fire burns the canopy (the leafy top of the tree), this signal <strong>drops sharply</strong>.<br/>· <strong>HH</strong> (the other signal) is sensitive to bare soil, moisture, and tree trunks still standing after the fire.<br/>· <strong>Decibels (dB)</strong>: this is how we measure how much signal the radar gets back. The lower (more negative), the more vegetation was lost: <code>−1.5 dB</code> is a <strong>29%</strong> signal loss; <code>−3 dB</code>, <strong>50%</strong>; <code>−6 dB</code>, <strong>75%</strong>.",
    c2Gloss:
      "<dt>L-band</dt><dd>A radar wavelength of about 24 cm. The longer the wave, the better it passes through smoke, clouds, and leaves.</dd><dt>HV / HH</dt><dd>The two ways the radar sends and receives its signal. Each reacts differently to what's below: HV to branches and leaves, HH to soil and tree trunks.</dd><dt>dB (decibel)</dt><dd>Measures how much radar signal comes back to the satellite. The lower (more negative), the more vegetation has been lost.</dd>",

    c3Num: "03 · Time series (June–October 2026)",
    c3Title: "Pre-fire seasonal baseline vs. the October 1 backscatter drop",
    c3P1:
      "NISAR passes over this same area, from the exact same spot in the sky, every <strong>12 days</strong> - so dates can be fairly compared. Comparing just two dates alone could be confused with normal seasonal moisture changes. That's why we use the whole series available since June–July 2026, compared against a <strong>control area that didn't burn</strong>: it looks stable before the fire, and drops sharply right after.",
    c3Gloss:
      "<dt>dB (decibel)</dt><dd>Measures how much radar signal comes back to the satellite. The lower, the more vegetation has been lost.</dd><dt>SME2</dt><dd>NISAR's soil-moisture product.</dd><dt>Provisional</dt><dd>NISAR is a very new mission; its data isn't finally calibrated yet and may shift slightly later on.</dd>",
    c3ChartL: "Mean HV (dB) · select acquisition",
    c3ChartR: "bars: SME2 moisture",
    c3Note:
      "Passes marked separately on the chart flag radiometric stability QA notices (Provisional products), retained with explicit disclosure.",

    c4Num: "04 · Multisensor observation",
    c4Title: "Optical obscuration by smoke and cloud cover vs. SAR acquisition",
    c4P1:
      "On <strong>September 25</strong> (active fire), Sentinel-2 captures the smoke plume hiding the hillside; on <strong>September 30</strong>, 91% of the scene is covered by clouds. NISAR L-band delivers a clean structural scan on <strong>October 1</strong> (and consolidated dry soil on Oct 25), verified against post-fire optical dNBR.",
    c4LeftLbl: "Left panel (real Sentinel-2 optical):",
    c4Opt1: "Sep 25 (active smoke)",
    c4Opt2: "Sep 30 (91% clouds)",
    c4Opt3: "Oct 15 (clear burn scar)",
    c4RightLbl: "Right panel (NISAR L-band / dNBR check):",
    c4Rad1: "Multitemporal ΔHV severity (Jul–Oct)",
    c4Rad2: "ΔHV severity (Oct 25 dry)",
    c4Rad3: "Oct 1 pair (wet bias)",
    c4Rad4: "Sentinel-2 dNBR (Sep 20→Oct 15)",
    c4Gloss:
      "<dt>dNBR</dt><dd>An index computed from ordinary satellite photos (not radar) that measures how much greener-to-browner the vegetation turned. We use it to check that the radar is getting it right.</dd>",

    c5Num: "09 · Parametric ΔHV sensitivity",
    c5Title: "Burn severity distribution across decibel thresholds (ΔHV)",
    c5P1:
      "Splitting the multitemporal <code>ΔHV</code> composite (5 dry pre passes → Oct 13/25) into physical backscatter drop thresholds separates moderate impact from severe structural loss, and contrasts with the wet Oct 1 pass:",
    c5ThLvl: "ΔHV level",
    c5ThHa: "Hectares",
    c5ThPct: "% perimeter",
    c5ModeLbl: "Pass / calibration applied to table and map:",
    c5Mode1: "Dry multitemporal (324.9 ha)",
    c5Mode6: "Oct 1 wet pair (87.5 ha)",
    c5Mode2: "Oct 1 rain-debiased (219 ha)",
    c5Mode3: "Oct 25 dry only (360.5 ha)",
    c5Mode4: "Continuous map threshold",
    c5Mode5: "ΔHV ramp",
    c5CalNote:
      "The <strong>October 1</strong> pass recorded a soil-moisture jump (SME2 0.18→0.23 m³/m³) lifting the exterior control ring by <strong>+1.16 dB</strong> and masking part of the scar. Linear-power averaging of QA-passing dry scenes stabilizes the burned estimate at <strong>324.9 ha</strong> (0.16% control FP; F1 = 0.80 vs dNBR).",
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
    c5Ch2: "ΔHV distribution: perimeter (orange) vs. control (blue)",
    c5Gloss:
      "<dt>dB (decibel)</dt><dd>Measures the radar signal drop. The lower (more negative), the more damage.</dd><dt>ΔHV (delta HV)</dt><dd>The difference between the HV signal before and after the fire.</dd><dt>ha (hectare)</dt><dd>Unit of area. 1 ha = 100 × 100 m.</dd>",

    c6Num: "05 · Resolution, polarization & land cover",
    c6Title: "Multilooking effects, HH/HV contrast & land-cover response",
    c6P1:
      "Comparing just two dates (<code>Sep 19 → Oct 1</code>) initially yielded only <strong>87.5 ha</strong>: Oct 1 coincided with wet soil (<code>SME2 0.18→0.23 m³/m³</code>), lifting scene backscatter by <strong>+1.16 dB</strong> and masking part of the scar on top of single-pair radar grain (<em>speckle</em>). Averaging in linear power (avoiding log bias) across the <strong>5 dry pre-fire passes</strong> and <strong>2 dry post-fire passes</strong> (<code>Oct 13</code> & <code>Oct 25</code>) over 100 m windows recovers a stable <strong>324.9 ha</strong> (only 0.16% exterior false positives).",
    c6P2:
      "So why does it still sit below the official 518 ha or the 483.1 ha seen optically (<code>dNBR ≥ 0.27</code>)? Cross-referencing <strong>ΔHV</strong> with <strong>ESA WorldCover 2021</strong> (a European land-cover map that groups Galician gorse/heath scrub under \"grassland/herbaceous\") reveals the physical limit of a 24 cm wave: NISAR detects open-scrub removal well (<code>247.5 ha</code>), whereas surface fire creeping underneath intact tree crowns leaves trunks and heavy branches standing (<code>ΔHV ≈ −0.07 dB</code> in missed forest patches).",
    c6Gloss:
      "<dt>speckle</dt><dd>Random grain found in any radar image, not a fault of the satellite or the terrain.</dd><dt>ha (hectare)</dt><dd>Unit of area. 1 ha = 100 × 100 m.</dd><dt>ΔHV (delta HV)</dt><dd>How much the HV signal changed between before and after the fire.</dd><dt>WorldCover</dt><dd>European (ESA) map classifying every point of land: forest, grassland, shrubland, etc.</dd>",
    c6ThCov: "Land cover (WorldCover)",
    c6ThArea: "EFFIS area",
    c6ThO1: "ΔHV multitemp.",
    c6ThO25: "NISAR (−1.5 dB)",
    c6ThPct: "dNBR ≥ 0.27",
    c6ThPol: "Polarization",
    c6ThPer: "Perimeter",
    c6ThCtrl: "Control",
    c6ThSep: "Separation",

    c7Num: "06 · Hydrological susceptibility (26 micro-watersheds)",
    c7Title: "Post-fire sediment susceptibility by micro-watershed & downstream receptors",
    c7P1:
      "Radar <strong>cannot</strong> tell whether the soil repels water after the fire - that can only be checked chemically, on the ground. But by combining where it burned, the <strong>slope</strong> of the terrain (from a Copernicus elevation model), and how <strong>dry</strong> the soil is (from NISAR's moisture data), we get a reasonable estimate of which areas are more likely to have rain wash away soil and ash: <code>risk = (burned) × (0.6 · slope + 0.4 · dryness)</code>.",
    c7SensLbl: "Ranking sensitivity by minimum burn severity:",
    c7Btn1: "−1.5 dB threshold",
    c7Btn2: "Severity ≥ −3.0 dB",
    c7Btn3: "Extreme ≥ −6.0 dB",
    c7Prompt: "Click a watershed on the map…",
    c7Gloss:
      "<dt>dB (decibel)</dt><dd>Measures the radar signal drop; the lower, the more severe the damage required for an area to count as \"burned\" in this calculation.</dd><dt>Micro-watershed</dt><dd>A small patch of land that drains rain from its slopes into the same stream.</dd>",

    c8Num: "07 · D8 drainage routing",
    c8Badge: "Simulation C = 0.6",
    c8Title: "Surface runoff routing and candidate retention points",
    c8P1:
      "The lines follow where water would actually flow (calculated from the terrain's elevation model) from 8 points on the fire's edge toward the Limia River and the Salas Reservoir. The only <strong>hypothetical</strong> part is the amount of rain: move the slider to see how much water would come down, assuming <strong>60%</strong> of the rain runs off the surface instead of soaking into the ground (typical for burned hillsides, but not measured on this specific terrain).",
    c8SliderLbl: "Hypothetical 24h rainfall:",
    c8M1: "Burned-core runoff (NISAR)",
    c8M2: "Accumulated basin flow (Salas/Limia)",
    c8BarTitle: "Retention barrier candidates (slope break)",
    c8BarPrompt: "Click an amber or grey marker on the map to see that spot on the terrain where it would make sense to slow the water down…",
    c8Warn:
      "<strong>Limit of the downloaded elevation map:</strong> The channels heading west stop at the dashed line at <code>−8.0°</code> longitude because that's the edge of the terrain tile we downloaded, not because the water really stops there.",
    c8Gloss:
      "<dt>mm (of rain)</dt><dd>Litres of water per square metre. 20 mm = 20 litres per m².</dd><dt>m³ (cubic metre)</dt><dd>Unit of water volume. 1 m³ = 1,000 litres.</dd><dt>DEM</dt><dd>A map where every point has its elevation; used to calculate where water would flow.</dd>",

    c9Num: "08 · Replicability & orbital synergy",
    c9Title: "Pipeline transfer to Quiroga (Ribeira Sacra) & Atlantic Constellation",
    c9P1:
      "The <strong>Ribeira Sacra wildfire (Sept 2025, 1,805 ha)</strong> proved how autumn rains on burned Galician hillslopes wash ash into the Cabe and Sil rivers. On <strong>October 27, 2026</strong>, both <strong>Calvos de Randín and Quiroga</strong> were declared disaster zones; this pipeline replicates directly by swapping the AOI.",
    c9Tip:
      "<strong>Multiscale observation:</strong><br/>Pairing <strong>NISAR</strong> (12-day high-resolution L-band structural mapping) with the upcoming <strong>Atlantic Constellation (Spain–Portugal PERTE, 16 microsatellites)</strong> would add ~3-hour revisits and GNSS-R rapid soil moisture linked to IoT rain gauges in critical basins.",

    c10Num: "10 · Sources & team",
    c10Title: "Project sources",
    c10NasaH: "NASA Data",
    c10OtherH: "Space Agency Partner & Other Data",
    c10TeamH: "Team",
    c10P1:
      "All calculations are done with our own code, on open data: from the NASA/ISRO <strong>NISAR</strong> mission (<code>GCOV</code> and <code>SME2</code> products, still in test phase - \"<em>Provisional</em>\", always taken from the satellite's exact same orbit, identified as <strong>Track 15 / Frame 23</strong>, so every date can be fairly compared); from <strong>Copernicus</strong> (the terrain elevation model and EFFIS fire detection); from the <strong>ESA</strong> (the WorldCover 2021 land-cover map); and from <strong>OpenStreetMap</strong>.",
    c10Gloss:
      "<dt>GCOV / SME2</dt><dd>The two NISAR data products we use: GCOV measures vegetation, SME2 measures soil moisture.</dd><dt>Track / Frame</dt><dd>The exact orbit and segment identifier of the satellite, so anyone can check the same original data.</dd><dt>Provisional</dt><dd>NISAR is a very new mission; this data isn't finally calibrated yet.</dd><dt>QA (quality assurance)</dt><dd>A check that each satellite pass is reliable before using it.</dd>",
    c10Th1: "Pass date",
    c10Th2: "Perimeter coverage",
    c10Th3: "Control mean HV",
    c10Th4: "Offset vs. median",
    c10Th5: "QA status",
    c10Warn:
      "<strong>Explicit limitations:</strong> (1) radar cannot tell whether soil repels water or measure its grain size - that can only be checked on the ground; (2) rain right before a satellite pass can boost the signal and mask mild canopy damage; (3) the land-cover map (WorldCover) is from 2021, not current; (4) the rain simulation assumes 60% surface runoff (not measured on this terrain), and is cut off at the edge of the downloaded elevation tile; (5) the NISAR data used here is still in test phase (\"Provisional\"), not the final version.",

    overlayLabels: {
      "hv_pre.png": "NISAR L-Band · HV pre (Sep 19)",
      "hv_post.png": "NISAR L-Band · HV post (Oct 1)",
      "dhv_mt.png": "NISAR L-Band · Multitemporal ΔHV severity (Jul–Oct)",
      "dhv_classes.png": "NISAR L-Band · ΔHV severity (Oct 1)",
      "dhv_oct01_cal.png": "NISAR L-Band · ΔHV Oct 1 debiased",
      "dhv_oct25.png": "NISAR L-Band · ΔHV severity (Oct 25 dry)",
      "dhv_cont.png": "NISAR L-Band · Continuous multitemporal ΔHV",
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
        { color: "#E9DFCE", label: "High HV (branches / leaves)" },
        { color: "#2C2824", label: "Low HV (bare ground / water)" },
      ],
      "3": [
        { color: "#E9DFCE", label: "High HV (branches / leaves)" },
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
        { color: "#13344A", label: "High (As Meaus and Calvos watersheds)" },
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
    a11Num: "11 · Email alerts",
    a11Title: "Rain warnings for the burned hillside",
    a11P1:
      "When you subscribe you receive this study's report by email, written without jargon: how much burned, where water can run, what the simulators above show and what it means for your village. After that we only write when the real forecast announces heavy rain over the burned hillside.",
    a11Offline:
      "<strong>Section inactive on this server:</strong> warnings need the alert server. Start the site with <code>python3 -m alerts serve</code> from the repository root and reload this page.",
    a11FormH: "Get the report and the warnings",
    a11Name: "Name (optional)",
    a11Email: "Email address",
    a11Place: "Your village",
    a11Min: "Warn me about rain from",
    a11Min1: "Yellow advisory (moderate rain)",
    a11Min2: "Orange alert (heavy rain)",
    a11Min3: "Red alert only (very heavy rain)",
    a11Tech: "Add the technical detail (hectares, volumes, micro-watersheds)",
    a11Subscribe: "Subscribe",
    a11Test: "Send me the report now",
    alerts: {
      locale: "en-US",
      noPlace: "No specific village (general warning)",
      exposure: { direct: "high exposure", downstream: "medium exposure", none: "low exposure" },
      hint: {
        direct: (d) => `High exposure: it sits on the slope that collects water straight from the burned hillside (stream about ${d} away).`,
        downstream: (d) => `Medium exposure: it is downstream of the fire, about ${d} from a river or stream carrying water from the burned hillside.`,
        none: () => "Low exposure: it is not in the path of water running off the burned hillside.",
        general: () => "The report will name the most exposed villages instead of a specific one.",
      },
      badEmail: "Enter a valid email address.",
      subscribed: (email) => `Subscription saved. ${email} will receive the study report and, after that, a warning when the forecast reaches the level you chose.`,
      updated: (email) => `Subscription updated for ${email}.`,
      sending: "Sending the report…",
      sent: (email) => `Report sent to ${email}. Check the inbox (and the spam folder).`,
      sendNote: "This server does not have Gmail sending configured yet: the subscription is saved, but no email will go out until it is.",
      errors: {
        invalid_email: "Enter a valid email address.",
        invalid: "Check the form details.",
        smtp_not_configured: "Gmail sending is not configured on this server.",
        smtp_failed: "Gmail rejected the message. Check the account and its app password.",
        forbidden: "The report can only be sent on the spot from the machine running the server.",
        forecast_unavailable: "The forecast could not be checked.",
        network: "Cannot reach the alert server.",
      },
    },
    dynamic: {
      locale: "en-US",
      xuntaSub: (forest, shrub) => `${forest} ha forest + ${shrub} ha grassland`,
      nisarSub: (oct01, rawMt, f1) => `5 pre + 2 dry post (F1=${f1} vs dNBR) · wet Oct 1: ${oct01} ha`,
      dhvSub: (offset, oct25Mean) =>
        `Jul–Oct composite · Oct 1 (+${offset} dB rain) · Oct 25: ${oct25Mean ?? "—"} dB`,
      basinsJoin: (a, b) => `${a} and ${b}`,
      basinsSub: (total, third) => `Top among ${total} basins (>4.7× higher than the ${third} watershed)`,
      polHvLabel: "HV (cross · branches/leaves)",
      polHhLabel: "HH (parallel · ground/trunk)",
      polNet: (v) => `(net ${v ?? "—"})`,
      hhBounceNote: (pct, hhCtrl) =>
        `${pct}% of perimeter pixels show an HH rise ≥ +1 dB on Oct 1 (combining the +${hhCtrl} dB control moisture jump with trunk double-bounce).`,
      dnbrNote: (pre, post, refHa, tpHa, sarHa, f1, omHa, omDhv, r) =>
        `<strong>Optical cross-check (Sentinel-2 dNBR, ${pre} → ${post}):</strong> ` +
        `Of the <strong>${sarHa} ha</strong> detected by multitemporal NISAR, <strong>${tpHa} ha</strong> fall inside ` +
        `the dNBR ≥ 0.27 scar (<strong>${refHa} ha</strong> optical; <code>F1 = ${f1}</code>, <code>r = ${r}</code>). ` +
        `The remaining <strong>${omHa} ha</strong> are low-severity or under-canopy surface burn invisible at 24 cm (<code>mean ΔHV = ${omDhv} dB</code>).`,
      oct01WetSuffix: "(20m Oct 1 wet)",
      oct01WetFp: "0.0% (masked)",
      octCalSuffix: "(debiased)",
      octCalFp: "control ≈ 0 dB",
      oct25Suffix: "(Oct 25 dry)",
      oct25Fp: "Oct 25 dry",
      tsReadout: (dt, hvFire, hvCtrl, sme, qaPass) =>
        `${dt} · Perimeter HV: ${hvFire} dB · control: ${hvCtrl} dB · SME2: ${sme ?? "—"} m³/m³ · QA: ${qaPass ? "PASS" : "FLAG"}`,
      basinTitle: (id, place) => (place ? `${place} watershed` : `Watershed #${id}`),
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
      barrierTitle: (dist) => `Barrier candidate · ${dist} from the perimeter`,
      barrierPriority: "Priority candidate (&lt; 3 km)",
      barrierDistant: "Distant (&gt; 14 km)",
      barrierDistLbl: "Distance to perimeter",
      barrierBreakLbl: "Topographic break",
      barrierAreaLbl: "Upstream drained area",
      barrierCoordLbl: "Coordinates",
    },
  },
};
