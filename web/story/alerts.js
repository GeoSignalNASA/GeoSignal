// Sección 11 · Alertas por correo.
// Habla con la API de `python3 -m alerts serve`: estado de la previsión, vista previa
// del informe del estudio que recibe cada persona y suscripción.
// En un servidor estático sin esa API la sección muestra un aviso y nada más.

import { I18N } from "./i18n.js";

const API = "api/alerts/";
const LEVEL_CLASS = ["lvl-0", "lvl-1", "lvl-2", "lvl-3"];

const $ = (id) => document.getElementById(id);
const lang = () => (document.documentElement.lang === "en" ? "en" : "es");
const t = () => I18N[lang()].alerts;

let status = null;      // respuesta de /status, o null si no hay previsión
let places = [];        // respuesta de /places
let previewTimer = null;
let previewSeq = 0;
let lastMessage = null; // () => texto, para poder traducirlo al cambiar de idioma

class ApiError extends Error {
  constructor(code) {
    super(code);
    this.code = code;
  }
}

async function api(path, body) {
  let resp;
  try {
    resp = await fetch(API + path, body === undefined ? {} : {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError("network");
  }
  const isJson = (resp.headers.get("Content-Type") || "").includes("application/json");
  if (!isJson) throw new ApiError("no_api");
  const data = await resp.json();
  if (!resp.ok) throw new ApiError(data.error || "invalid");
  return data;
}

function fmtNum(value) {
  return new Intl.NumberFormat(t().locale, { maximumFractionDigits: value >= 10 ? 0 : 1 }).format(value);
}

function fmtDay(iso) {
  return new Date(`${iso}T12:00:00`).toLocaleDateString(t().locale, { weekday: "long", day: "numeric", month: "long" });
}

function fmtDist(meters) {
  if (meters < 1000) return `${fmtNum(Math.max(50, Math.round(meters / 50) * 50))} m`;
  return `${new Intl.NumberFormat(t().locale, { maximumFractionDigits: 1 }).format(meters / 1000)} km`;
}

function setLevel(el, level) {
  el.textContent = t().levels[level];
  el.classList.remove(...LEVEL_CLASS);
  el.classList.add(LEVEL_CLASS[level]);
}

function renderStatus() {
  const d = t();
  const tbody = $("alerts-days");
  tbody.replaceChildren();
  if (!status) {
    $("alerts-level").textContent = "—";
    $("alerts-level").classList.remove(...LEVEL_CLASS);
    $("alerts-rain").textContent = "—";
    $("alerts-rain-k").textContent = d.rainK("—");
    $("alerts-now-note").textContent = d.nowUnavailable;
    return;
  }
  const worst = status.days.find((day) => day.date === status.worst_date) || status.days[0];
  setLevel($("alerts-level"), status.level);
  $("alerts-rain").textContent = `${fmtNum(worst.rain_mm)} ${d.unit}`;
  $("alerts-rain-k").textContent = d.rainK(fmtDay(worst.date));
  for (const day of status.days) {
    const tr = document.createElement("tr");
    const cells = [fmtDay(day.date), `${fmtNum(day.rain_mm)} ${d.unit}`, ""];
    cells.forEach((text, i) => {
      const td = document.createElement("td");
      td.textContent = text;
      if (i === 1) td.className = "num";
      if (i === 2) setLevel(td, day.level);
      tr.append(td);
    });
    tbody.append(tr);
  }
  const th = status.thresholds;
  $("alerts-now-note").textContent = d.nowNote(th.rain_24h_mm.join(" / "), th.rain_1h_mm.join(" / "));
}

function renderPlaces() {
  const d = t();
  const select = $("alerts-place");
  const chosen = select.value;
  select.replaceChildren(new Option(d.noPlace, ""));
  for (const place of places) select.append(new Option(`${place.name} · ${d.exposure[place.exposure]}`, place.name));
  select.value = places.some((p) => p.name === chosen) ? chosen : "";
  renderHint();
}

function renderHint() {
  const d = t();
  const place = places.find((p) => p.name === $("alerts-place").value);
  $("alerts-place-hint").textContent = place ? d.hint[place.exposure](fmtDist(place.trace_dist_m)) : d.hint.general();
}

function renderSendNote() {
  const canSend = Boolean(status && status.can_send_report);
  $("alerts-test").hidden = !canSend;
  $("alerts-send-note").textContent = canSend ? "" : t().sendNote;
}

function showMessage(makeText, isError = false) {
  lastMessage = makeText ? { makeText, isError } : null;
  const el = $("alerts-msg");
  el.textContent = makeText ? makeText() : "";
  el.classList.toggle("is-error", Boolean(makeText) && isError);
}

function showError(err) {
  showMessage(() => t().errors[err.code] || t().errors.invalid, true);
}

function formData() {
  const place = $("alerts-place").value;
  return {
    name: $("alerts-name").value.trim(),
    places: place ? [place] : [],
    lang: lang(),
    profile: $("alerts-tech").checked ? "technical" : "resident",
    min_level: Number($("alerts-min").value),
  };
}

async function updatePreview() {
  const seq = ++previewSeq;
  const subject = $("alerts-subject");
  if (!subject.textContent) subject.textContent = t().loading;
  try {
    const data = await api("preview", formData());
    if (seq !== previewSeq) return; // llegó tarde: ya hay otra petición más reciente
    subject.textContent = data.subject;
    $("alerts-frame").srcdoc = data.html;
  } catch {
    if (seq === previewSeq) subject.textContent = t().previewFailed;
  }
}

function schedulePreview() {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(updatePreview, 250);
}

function readEmail() {
  const input = $("alerts-email");
  const email = input.value.trim();
  if (!email || !input.checkValidity()) {
    showMessage(() => t().badEmail, true);
    input.focus();
    return null;
  }
  return email;
}

async function subscribe() {
  const email = readEmail();
  if (!email) return null;
  const data = await api("subscribe", { ...formData(), email });
  showMessage(() => (data.replaced ? t().updated(email) : t().subscribed(email)));
  return email;
}

async function withBusy(button, task) {
  button.disabled = true;
  try {
    await task();
  } catch (err) {
    showError(err);
  } finally {
    button.disabled = false;
  }
}

function renderAll() {
  renderStatus();
  renderPlaces();
  renderSendNote();
  if (lastMessage) showMessage(lastMessage.makeText, lastMessage.isError);
}

async function init() {
  if (!$("cap-11")) return;
  try {
    places = (await api("places")).places;
  } catch {
    $("alerts-offline").hidden = false; // servidor estático: no hay API
    return;
  }
  try {
    status = await api("status");
  } catch {
    status = null; // sin previsión; el resto de la sección funciona igual
  }
  $("alerts-live").hidden = false;
  renderAll();
  updatePreview();

  const form = $("alerts-form");
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    withBusy(form.querySelector('button[type="submit"]'), subscribe);
  });
  $("alerts-test").addEventListener("click", () => {
    withBusy($("alerts-test"), async () => {
      const email = await subscribe(); // el informe solo se envía a direcciones suscritas
      if (!email) return;
      showMessage(() => t().sending);
      await api("report", { email });
      showMessage(() => t().sent(email));
    });
  });
  $("alerts-place").addEventListener("change", () => { renderHint(); schedulePreview(); });
  $("alerts-tech").addEventListener("change", schedulePreview);
  $("alerts-name").addEventListener("input", schedulePreview);

  // story.js cambia <html lang> al pulsar EN/ES: volver a pintar lo dinámico.
  new MutationObserver(() => { renderAll(); updatePreview(); })
    .observe(document.documentElement, { attributes: true, attributeFilter: ["lang"] });
}

init();
