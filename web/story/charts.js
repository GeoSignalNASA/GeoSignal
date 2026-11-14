// Gráficos SVG nativos sin dependencias externas:
// 1. Serie temporal 10 pasadas (HV perímetro vs control + SME2) con clic interactivo
// 2. Curva hectáreas quemadas vs umbral (dB) + tasa de falsos positivos en control
// 3. Histograma ΔHV dentro del perímetro vs zona de control
// 4. Barras ESA WorldCover 2021 dentro del perímetro

const NS = "http://www.w3.org/2000/svg";

function el(tag, attrs = {}, text = null) {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (text !== null) n.textContent = text;
  return n;
}

export function renderTimeseriesChart(container, series, selectedDate, onSelectDate) {
  const W = 540, H = 230;
  const pad = { l: 54, r: 50, t: 20, b: 40 };
  const pw = W - pad.l - pad.r;
  const ph = H - pad.t - pad.b;

  const hvs = series.flatMap((d) => [d.hv_fire_mean, d.hv_ctrl_mean]);
  const yMin = Math.floor(Math.min(...hvs) - 0.8);
  const yMax = Math.ceil(Math.max(...hvs) + 0.8);

  const xAt = (i) => pad.l + (i / Math.max(series.length - 1, 1)) * pw;
  const yAt = (v) => pad.t + ((yMax - v) / (yMax - yMin)) * ph;

  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Serie temporal NISAR HV y SME2" });

  // Banda vertical del incendio (entre 2026-09-19 y 2026-10-01)
  const idxPre = series.findIndex((d) => d.date === "2026-09-19");
  const idxPost = series.findIndex((d) => d.date === "2026-10-01");
  if (idxPre >= 0 && idxPost >= 0) {
    const x1 = xAt(idxPre) + (xAt(idxPost) - xAt(idxPre)) * 0.35;
    const x2 = xAt(idxPre) + (xAt(idxPost) - xAt(idxPre)) * 0.65;
    svg.appendChild(el("rect", { x: x1, y: pad.t, width: Math.max(4, x2 - x1), height: ph, fill: "rgba(142,67,33,0.12)" }));
    svg.appendChild(el("text", { x: (x1 + x2) / 2, y: pad.t + 11, "text-anchor": "middle", fill: "#A0521F", "font-size": "11", "font-family": "Inter, ui-sans-serif, sans-serif" }, "INCENDIO 24-27 SEP"));
  }

  // Rejilla horizontal dB
  for (let yv = yMin; yv <= yMax; yv += 1) {
    const y = yAt(yv);
    svg.appendChild(el("line", { x1: pad.l, y1: y, x2: W - pad.r, y2: y, stroke: "#D8CCB6", "stroke-width": "1" }));
    svg.appendChild(el("text", { x: pad.l - 6, y: y + 3, "text-anchor": "end", fill: "#57493A", "font-size": "11.5", "font-family": "Inter, ui-sans-serif, sans-serif" }, `${yv} dB`));
  }

  // Barras SME2 secundarias al fondo (humedad 0..0.35 m3/m3) + eje Y derecho
  const smeMax = 0.35;
  const smeZoneH = ph * 0.34;
  [0.0, 0.15, 0.3].forEach((sv) => {
    const sy = pad.t + ph - (sv / smeMax) * smeZoneH;
    svg.appendChild(el("line", { x1: W - pad.r, y1: sy, x2: W - pad.r + 3, y2: sy, stroke: "#23596A", "stroke-width": "1", opacity: "0.7" }));
    svg.appendChild(el("text", { x: W - pad.r + 6, y: sy + 3, "text-anchor": "start", fill: "#23596A", "font-size": "11", "font-family": "Inter, ui-sans-serif, sans-serif", opacity: "0.85" }, sv.toFixed(2)));
  });
  svg.appendChild(el("text", { x: W - pad.r + 6, y: pad.t + ph - smeZoneH - 7, "text-anchor": "start", fill: "#23596A", "font-size": "10", "font-family": "Inter, ui-sans-serif, sans-serif", opacity: "0.75" }, "m³/m³"));

  series.forEach((d, i) => {
    if (d.sme2_fire_mean == null) return;
    const bh = Math.min(smeZoneH, (d.sme2_fire_mean / smeMax) * smeZoneH);
    const x = xAt(i) - 6;
    svg.appendChild(el("rect", { x, y: pad.t + ph - bh, width: 12, height: bh, fill: "rgba(35,89,106,0.18)", rx: 2 }));
  });

  // Línea control (punteada)
  const ctrlPath = series.map((d, i) => `${i === 0 ? "M" : "L"}${xAt(i).toFixed(1)},${yAt(d.hv_ctrl_mean).toFixed(1)}`).join(" ");
  svg.appendChild(el("path", { d: ctrlPath, fill: "none", stroke: "#57493A", "stroke-width": "1.6", "stroke-dasharray": "4 3" }));

  // Línea perímetro EFFIS (naranja)
  const firePath = series.map((d, i) => `${i === 0 ? "M" : "L"}${xAt(i).toFixed(1)},${yAt(d.hv_fire_mean).toFixed(1)}`).join(" ");
  svg.appendChild(el("path", { d: firePath, fill: "none", stroke: "#8E4321", "stroke-width": "2.4" }));

  // Puntos clicables + etiquetas de fecha
  series.forEach((d, i) => {
    const x = xAt(i);
    const yf = yAt(d.hv_fire_mean);
    const yc = yAt(d.hv_ctrl_mean);
    const isSel = d.date === selectedDate;

    svg.appendChild(el("circle", { cx: x, cy: yc, r: 3, fill: "#57493A" }));
    const dot = el("circle", {
      cx: x,
      cy: yf,
      r: isSel ? 6.5 : 4.5,
      fill: d.qa_pass ? (isSel ? "#23596A" : "#8E4321") : "#A0521F",
      stroke: "#F5F0E6",
      "stroke-width": "1.5",
      style: "cursor:pointer",
    });
    dot.addEventListener("click", () => onSelectDate(d.date));
    svg.appendChild(dot);

    // Hitbox invisible más grande para accesibilidad táctil
    const hit = el("circle", { cx: x, cy: yf, r: 14, fill: "transparent", style: "cursor:pointer" });
    hit.addEventListener("click", () => onSelectDate(d.date));
    hit.appendChild(el("title", {}, `${d.date} · HV perímetro: ${d.hv_fire_mean} dB · control: ${d.hv_ctrl_mean} dB · SME2: ${d.sme2_fire_mean ?? "—"} m³/m³`));
    svg.appendChild(hit);

    svg.appendChild(
      el("text", { x, y: H - 10, "text-anchor": "middle", fill: isSel ? "#23596A" : "#57493A", "font-size": "10.5", "font-family": "Inter, ui-sans-serif, sans-serif", "font-weight": isSel ? "700" : "400" }, d.date.slice(5))
    );
  });

  container.innerHTML = "";
  container.appendChild(svg);
}

export function renderThresholdCurve(container, curve, currentDb, meta) {
  const W = 540, H = 220;
  const pad = { l: 58, r: 58, t: 18, b: 38 };
  const pw = W - pad.l - pad.r;
  const ph = H - pad.t - pad.b;

  const yMax = Math.max(meta.effis_ha, ...curve.map((c) => c.ha_raw)) * 1.05;
  const xMin = -8.0, xMax = -0.5;
  const xAt = (db) => pad.l + ((db - xMin) / (xMax - xMin)) * pw;
  const yHa = (ha) => pad.t + (1 - ha / yMax) * ph;
  const yFp = (fp) => pad.t + (1 - Math.min(fp, 40) / 40) * ph;

  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Hectáreas quemadas según umbral de dB" });

  // Referencias oficiales Xunta y EFFIS
  [
    { ha: meta.official_xunta_ha, label: `Xunta ${meta.official_xunta_ha} ha`, col: "#46603A" },
    { ha: meta.effis_ha, label: `EFFIS ${meta.effis_ha} ha`, col: "#23596A" },
  ].forEach((ref) => {
    const y = yHa(ref.ha);
    svg.appendChild(el("line", { x1: pad.l, y1: y, x2: W - pad.r, y2: y, stroke: ref.col, "stroke-width": "1", "stroke-dasharray": "4 3", opacity: "0.7" }));
    svg.appendChild(el("text", { x: pad.l + 4, y: y - 3, fill: ref.col, "font-size": "11", "font-family": "Inter, ui-sans-serif, sans-serif" }, ref.label));
  });

  // Curva 20m raw (punteada)
  const rawPath = curve.map((c, i) => `${i === 0 ? "M" : "L"}${xAt(c.threshold_db).toFixed(1)},${yHa(c.ha_raw).toFixed(1)}`).join(" ");
  svg.appendChild(el("path", { d: rawPath, fill: "none", stroke: "#57493A", "stroke-width": "1.6", "stroke-dasharray": "3 3" }));

  // Curva 100m suavizada (naranja)
  const smPath = curve.map((c, i) => `${i === 0 ? "M" : "L"}${xAt(c.threshold_db).toFixed(1)},${yHa(c.ha_smooth).toFixed(1)}`).join(" ");
  svg.appendChild(el("path", { d: smPath, fill: "none", stroke: "#8E4321", "stroke-width": "2.4" }));

  // Curva falsos positivos en control (eje derecho, amarillo)
  const fpPath = curve.map((c, i) => `${i === 0 ? "M" : "L"}${xAt(c.threshold_db).toFixed(1)},${yFp(c.fp_ctrl_pct_smooth).toFixed(1)}`).join(" ");
  svg.appendChild(el("path", { d: fpPath, fill: "none", stroke: "#A0521F", "stroke-width": "1.8" }));

  // Marcador del umbral activo
  const cx = xAt(currentDb);
  svg.appendChild(el("line", { x1: cx, y1: pad.t, x2: cx, y2: pad.t + ph, stroke: "#241C14", "stroke-width": "1.6" }));

  [-8, -6, -3, -1.5, -0.5].forEach((db) => {
    svg.appendChild(el("text", { x: xAt(db), y: H - 10, "text-anchor": "middle", fill: "#57493A", "font-size": "11", "font-family": "Inter, ui-sans-serif, sans-serif" }, `${db}`));
  });
  svg.appendChild(el("text", { x: pad.l - 6, y: pad.t + 8, "text-anchor": "end", fill: "#8E4321", "font-size": "11", "font-family": "Inter, ui-sans-serif, sans-serif" }, `${Math.round(yMax)} ha`));
  svg.appendChild(el("text", { x: W - pad.r + 4, y: pad.t + 8, fill: "#A0521F", "font-size": "11", "font-family": "Inter, ui-sans-serif, sans-serif" }, "40% FP"));

  container.innerHTML = "";
  container.appendChild(svg);
}

export function renderHistogramChart(container, hist) {
  const W = 540, H = 180;
  const pad = { l: 24, r: 16, t: 18, b: 34 };
  const pw = W - pad.l - pad.r;
  const ph = H - pad.t - pad.b;

  const maxD = Math.max(...hist.flatMap((h) => [h.fire_density, h.ctrl_density]), 0.1);
  const xMin = -10, xMax = 4;
  const xAt = (v) => pad.l + ((v - xMin) / (xMax - xMin)) * pw;
  const yAt = (d) => pad.t + (1 - d / maxD) * ph;

  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Distribución de ΔHV dentro y fuera del perímetro" });

  // Línea umbral -1.5 dB
  const tx = xAt(-1.5);
  svg.appendChild(el("line", { x1: tx, y1: pad.t, x2: tx, y2: pad.t + ph, stroke: "#A0521F", "stroke-dasharray": "4 2", "stroke-width": "1.2" }));
  svg.appendChild(el("text", { x: tx - 4, y: pad.t + 10, "text-anchor": "end", fill: "#A0521F", "font-size": "11", "font-family": "Inter, ui-sans-serif, sans-serif" }, "-1.5 dB"));

  const bw = pw / hist.length - 1;
  hist.forEach((b) => {
    const x = xAt(b.bin_center) - bw / 2;
    const hf = (b.fire_density / maxD) * ph;
    svg.appendChild(el("rect", { x, y: pad.t + ph - hf, width: bw, height: hf, fill: "rgba(142,67,33,0.55)" }));
  });

  const ctrlLine = hist.map((b, i) => `${i === 0 ? "M" : "L"}${xAt(b.bin_center).toFixed(1)},${yAt(b.ctrl_density).toFixed(1)}`).join(" ");
  svg.appendChild(el("path", { d: ctrlLine, fill: "none", stroke: "#23596A", "stroke-width": "2" }));

  [-9, -6, -3, -1.5, 0, 3].forEach((v) => {
    svg.appendChild(el("text", { x: xAt(v), y: H - 10, "text-anchor": "middle", fill: "#57493A", "font-size": "11", "font-family": "Inter, ui-sans-serif, sans-serif" }, `${v}`));
  });

  container.innerHTML = "";
  container.appendChild(svg);
}
