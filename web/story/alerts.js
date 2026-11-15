// Sección 11 · Alertas por correo.
// Habla con la API de `python3 -m alerts serve` para gestionar suscripciones
// y envío inmediato del informe desde el equipo local.
// En un servidor estático sin esa API la sección muestra un aviso y nada más.

import { I18N } from "./i18n.js";

const API = "api/alerts/";

const $ = (id) => document.getElementById(id);
const lang = () => (document.documentElement.lang === "en" ? "en" : "es");
const t = () => I18N[lang()].alerts;

let status = null;      // respuesta de /status (can_send_report)
let places = [];        // respuesta de /places
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

function fmtDist(meters) {
  if (meters < 1000) return `${fmtNum(Math.max(50, Math.round(meters / 50) * 50))} m`;
  return `${new Intl.NumberFormat(t().locale, { maximumFractionDigits: 1 }).format(meters / 1000)} km`;
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
  $("alerts-place").addEventListener("change", renderHint);

  // story.js cambia <html lang> al pulsar EN/ES: volver a pintar lo dinámico.
  new MutationObserver(renderAll)
    .observe(document.documentElement, { attributes: true, attributeFilter: ["lang"] });
}

init();
