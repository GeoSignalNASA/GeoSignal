"""
Build the email (subject, plain text, HTML) for one subscriber.

The message is written for neighbours, not for remote-sensing people:
litres per square metre instead of dB, "how exposed is my village" instead
of basin rankings, and one size comparison instead of a formula. The
"technical" profile gets the same plain email plus an appendix with the
figures behind it (burned hectares, runoff volumes, basins, check dams).

The message is assembled once as a list of blocks and rendered twice, so
the plain-text and HTML parts can never drift apart.
"""

import datetime as dt
import html as html_lib

from . import config

LEVEL_COLOR = {0: "#5E979A", 1: "#C99A1E", 2: "#C8661B", 3: "#A32D22"}
OLYMPIC_POOL_M3 = 2500.0

T = {
    "es": {
        "level": {0: "Sin alerta", 1: "Aviso amarillo", 2: "Alerta naranja", 3: "Alerta roja"},
        "rain": {0: "lluvia por debajo del nivel de aviso", 1: "lluvia moderada", 2: "lluvia fuerte", 3: "lluvia muy fuerte"},
        "drill": "SIMULACRO",
        "subject": "{label}: {rain} el {date} en el monte quemado de {fire} ({mm} l/m²)",
        "hello": "Hola{name}:",
        "headline": "El {date} se espera {rain} sobre el monte quemado de {fire}: unos {mm} litros por metro cuadrado en todo el día.",
        "peak": "Lo más intenso llegará hacia las {hour}:00.",
        "meaning": {
            0: "Con esta cantidad no esperamos problemas en la zona.",
            1: "Puede bajar agua turbia con ceniza por los regatos y cunetas cercanos al monte quemado.",
            2: "Es probable que el agua arrastre ceniza y barro hacia regatos, pistas y carreteras cercanas al monte quemado.",
            3: "Hay riesgo alto de riadas de barro y piedras en los cauces que bajan del monte quemado.",
        },
        "src_forecast": "Previsión del tiempo: Open-Meteo. Puede cambiar; si empeora te volveremos a escribir.",
        "src_scenario": "Esto es un simulacro para probar el sistema: la lluvia es inventada, no una previsión real.",
        "why_h": "Por qué avisamos",
        "why": "El incendio de {month} dejó el monte sin la vegetación que frenaba el agua. Ahora, cuando llueve "
               "con fuerza, el agua corre ladera abajo en lugar de filtrarse y se lleva ceniza y tierra suelta.",
        "why_pools": "Para hacerse una idea: ese día podría bajar del monte quemado tanta agua como la de unas {pools} "
                     "piscinas olímpicas. Es un cálculo aproximado, no una medición.",
        "place_h": "Tu zona",
        "place_direct": "{place}: exposición alta. Está en la ladera que recoge directamente el agua del monte quemado; "
                        "el regato más cercano que baja de la zona quemada pasa a unos {dist}.",
        "place_down": "{place}: exposición media. Está aguas abajo del incendio, a unos {dist} de un río o regato que "
                      "trae agua del monte quemado. Puede llegar agua turbia con ceniza y barro.",
        "place_none": "{place}: exposición baja. No está en el camino del agua que baja del monte quemado.",
        "general_direct": "Los lugares más expuestos, en las laderas que recogen el agua del monte quemado: {names}.",
        "general_down": "Aguas abajo, junto a ríos y regatos que traen agua del monte quemado: {names}.",
        "days_h": "Próximos días",
        "days_cols": ["Día", "Lluvia", "Nivel"],
        "unit": "l/m²",
        "todo_h": "Qué hacer",
        "todo": [
            "Mientras llueva, no te acerques a regatos, vaguadas ni pistas del monte quemado o aguas abajo de él.",
            "No cruces vados ni tramos de carretera por los que corra agua o barro.",
            "Antes de la lluvia, comprueba que las cunetas, sumideros y pasos de agua junto a tu casa están limpios.",
            "Si coges agua de un manantial o del río, puede bajar turbia por la ceniza: revisa la captación.",
            "Ante una emergencia llama al 112 y sigue los avisos oficiales de AEMET, MeteoGalicia y Protección Civil.",
        ],
        "tech_h": "Detalle técnico",
        "tech_rain": "Lluvia prevista: {mm} mm en 24 h; intensidad máxima {peak}.",
        "tech_burn": "Superficie quemada: {burned} ha (NISAR Banda L, {bdate}). Escorrentía estimada desde el núcleo "
                     "quemado: {vol} m³; en el cauce principal (Salas/Limia): {vmain} m³ (área contribuyente máxima "
                     "{area} ha). Supuesto: coeficiente de escorrentía C = {c}, no medido sobre el terreno.",
        "tech_thr": "Umbrales usados: 24 h ≥ {d} mm; 1 h ≥ {h} mm (amarillo / naranja / rojo). Configurables, sin calibrar in situ.",
        "tech_cols": ["Microcuenca", "Puesto", "Quemado", "Pendiente", "Humedad SME2", "Núcleos"],
        "tech_bar_h": "Candidatas a barrera de retención (rotura de pendiente)",
        "tech_bar": "{lat}, {lon}: a {dist} del perímetro, pendiente {s1}° → {s2}°, drena {area} ha{star}.",
        "tech_bar_star": " (prioritaria)",
        "foot_exp": "Aviso experimental de GeoSignal, hecho con datos de satélite. No sustituye a los avisos oficiales.",
        "foot_map": "Mapa e informe completo: {url}",
        "foot_unsub": "Si no quieres recibir más avisos, escribe a {contact}.",
        "no_peak": "sin dato horario",
    },
    "en": {
        "level": {0: "No alert", 1: "Yellow advisory", 2: "Orange alert", 3: "Red alert"},
        "rain": {0: "rain below the advisory level", 1: "moderate rain", 2: "heavy rain", 3: "very heavy rain"},
        "drill": "DRILL",
        "subject": "{label}: {rain} on {date} over the {fire} burn scar ({mm} mm)",
        "hello": "Hello{name},",
        "headline": "On {date}, {rain} is expected over the {fire} burn scar: about {mm} mm over the whole day.",
        "peak": "The heaviest rain should arrive around {hour}:00.",
        "meaning": {
            0: "We do not expect problems in the area with this amount.",
            1: "Murky water carrying ash may run down streams and roadside ditches near the burned hillside.",
            2: "Water is likely to carry ash and mud into streams, tracks and roads near the burned hillside.",
            3: "There is a high risk of mud and rock flows in the streams that run off the burned hillside.",
        },
        "src_forecast": "Weather forecast: Open-Meteo. It can change; we will write again if it gets worse.",
        "src_scenario": "This is a drill to test the system: the rainfall is made up, not a real forecast.",
        "why_h": "Why we are warning you",
        "why": "The {month} fire stripped the hillside of the vegetation that used to slow water down. Now, when it "
               "rains hard, water runs downhill instead of soaking in, taking ash and loose soil with it.",
        "why_pools": "To give an idea: that day the burned hillside could shed as much water as about {pools} Olympic "
                     "swimming pools. This is a rough estimate, not a measurement.",
        "place_h": "Your area",
        "place_direct": "{place}: high exposure. It sits on the slope that collects water straight from the burned "
                        "hillside; the nearest stream coming off the burn scar runs about {dist} away.",
        "place_down": "{place}: medium exposure. It is downstream of the fire, about {dist} from a river or stream "
                      "carrying water from the burned hillside. Murky water with ash and mud may arrive.",
        "place_none": "{place}: low exposure. It is not in the path of water running off the burned hillside.",
        "general_direct": "Most exposed places, on the slopes that collect water from the burned hillside: {names}.",
        "general_down": "Downstream, next to rivers and streams carrying water from the burned hillside: {names}.",
        "days_h": "Next days",
        "days_cols": ["Day", "Rain", "Level"],
        "unit": "mm",
        "todo_h": "What to do",
        "todo": [
            "While it rains, stay away from streams, gullies and tracks on or below the burned hillside.",
            "Do not cross fords or stretches of road with water or mud running over them.",
            "Before the rain, check that ditches, drains and culverts next to your home are clear.",
            "If you take water from a spring or the river, it may run murky with ash: check your intake.",
            "In an emergency call 112 and follow official warnings from AEMET, MeteoGalicia and Civil Protection.",
        ],
        "tech_h": "Technical detail",
        "tech_rain": "Forecast rain: {mm} mm in 24 h; peak intensity {peak}.",
        "tech_burn": "Burned area: {burned} ha (NISAR L-band, {bdate}). Estimated runoff from the burned core: "
                     "{vol} m³; in the main channel (Salas/Limia): {vmain} m³ (maximum contributing area {area} ha). "
                     "Assumption: runoff coefficient C = {c}, not measured on site.",
        "tech_thr": "Thresholds used: 24 h ≥ {d} mm; 1 h ≥ {h} mm (yellow / orange / red). Configurable, not calibrated on site.",
        "tech_cols": ["Micro-watershed", "Rank", "Burned", "Slope", "SME2 moisture", "Settlements"],
        "tech_bar_h": "Candidate retention barriers (slope break)",
        "tech_bar": "{lat}, {lon}: {dist} from the perimeter, slope {s1}° → {s2}°, drains {area} ha{star}.",
        "tech_bar_star": " (priority)",
        "foot_exp": "Experimental GeoSignal notice, built from satellite data. It does not replace official warnings.",
        "foot_map": "Map and full report: {url}",
        "foot_unsub": "If you no longer want these notices, write to {contact}.",
        "no_peak": "no hourly data",
    },
}

WEEKDAYS = {
    "es": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
}
MONTHS = {
    "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
           "septiembre", "octubre", "noviembre", "diciembre"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"],
}


def fmt_num(value, decimals, lang):
    text = f"{value:,.{decimals}f}"
    if lang == "es":
        text = text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return text


def fmt_date(date, lang):
    wd, month = WEEKDAYS[lang][date.weekday()], MONTHS[lang][date.month - 1]
    return f"{wd} {date.day} de {month}" if lang == "es" else f"{wd}, {month} {date.day}"


def fmt_short_date(date, lang):
    wd = WEEKDAYS[lang][date.weekday()]
    return f"{wd} {date.day}"


def fmt_dist(meters, lang):
    """Exact-ish distance for the technical appendix."""
    if meters < 1000:
        return f"{fmt_num(round(meters, -1), 0, lang)} m"
    return f"{fmt_num(meters / 1000, 1, lang)} km"


def fmt_dist_plain(meters, lang):
    """Rounded distance for neighbours: "unos 300 m" reads better than "314 m"."""
    if meters < 1000:
        return f"{fmt_num(max(50, round(meters / 50) * 50), 0, lang)} m"
    return f"{fmt_num(meters / 1000, 0 if meters >= 10_000 else 1, lang)} km"


def round_pools(volume_m3):
    """Olympic pools, rounded so the comparison does not look more exact than it is."""
    pools = volume_m3 / OLYMPIC_POOL_M3
    if pools < 1:
        return 0
    if pools < 10:
        return round(pools)
    if pools < 100:
        return round(pools / 5) * 5
    return round(pools / 10) * 10


def _fmt_thresholds(values, lang):
    return " / ".join(fmt_num(v, 0, lang) for v in values)


def _fmt_mm(value, lang):
    return fmt_num(value, 0 if value >= 10 else 1, lang)


def _place_line(place, t, lang):
    key = {"direct": "place_direct", "downstream": "place_down", "none": "place_none"}[place.exposure]
    return t[key].format(place=place.name, dist=fmt_dist_plain(place.trace_dist_m, lang))


def build_blocks(assessment, territory, sub, settings):
    lang = sub.lang
    t = T[lang]
    worst = assessment.worst
    fire = territory.fire_name.split(" (")[0]
    mm = _fmt_mm(worst.rain_mm, lang)
    blocks = []

    blocks.append(("p", t["hello"].format(name=f" {sub.name}" if sub.name else "")))
    headline = t["headline"].format(date=fmt_date(worst.date, lang), rain=t["rain"][assessment.level], fire=fire, mm=mm)
    if worst.peak_mm_h and worst.peak_hour is not None:
        headline += " " + t["peak"].format(hour=f"{worst.peak_hour:02d}")
    blocks.append(("lead", headline))
    blocks.append(("p", t["meaning"][assessment.level]))
    blocks.append(("note", t["src_scenario"] if assessment.simulated else t["src_forecast"]))

    month = MONTHS[lang][dt.date.fromisoformat(territory.ignition_date).month - 1]
    why = t["why"].format(month=month)
    pools = round_pools(assessment.runoff_burned_m3)
    if pools:
        why += " " + t["why_pools"].format(pools=fmt_num(pools, 0, lang))
    blocks.append(("h", t["why_h"]))
    blocks.append(("p", why))

    blocks.append(("h", t["place_h"]))
    places = [territory.find_place(name) for name in sub.places]
    places = [p for p in places if p is not None]
    if places:
        blocks.append(("ul", [_place_line(p, t, lang) for p in places]))
    else:
        everyone = sorted(territory.places.values(), key=lambda p: p.name)
        direct = [p.name for p in everyone if p.exposure == "direct"]
        down = [p.name for p in everyone if p.exposure == "downstream"]
        lines = []
        if direct:
            lines.append(t["general_direct"].format(names=", ".join(direct)))
        if down:
            lines.append(t["general_down"].format(names=", ".join(down)))
        blocks.append(("ul", lines))

    if len(assessment.days) > 1:
        rows = [
            [fmt_date(day.date, lang), f"{_fmt_mm(day.rain_mm, lang)} {t['unit']}", t["level"][level]]
            for day, level in assessment.days
        ]
        blocks.append(("h", t["days_h"]))
        blocks.append(("table", t["days_cols"], rows))

    blocks.append(("h", t["todo_h"]))
    blocks.append(("ul", t["todo"]))

    if sub.profile == "technical":
        c = fmt_num(config.RUNOFF_COEFF, 1, lang)
        peak = t["no_peak"]
        if worst.peak_mm_h and worst.peak_hour is not None:
            peak = f"{fmt_num(worst.peak_mm_h, 1, lang)} mm/h ({worst.peak_hour:02d}:00)"
        blocks.append(("h", t["tech_h"]))
        blocks.append(("p", t["tech_rain"].format(mm=fmt_num(worst.rain_mm, 1, lang), peak=peak)))
        blocks.append(("p", t["tech_burn"].format(
            burned=fmt_num(territory.burned_ha, 1, lang), bdate=territory.burned_date,
            vol=fmt_num(assessment.runoff_burned_m3, 0, lang),
            vmain=fmt_num(assessment.runoff_main_m3, 0, lang),
            area=fmt_num(territory.max_contrib_area_m2 / 10_000, 0, lang), c=c,
        )))
        rows = [
            [f"#{b.basin_id}", f"#{b.rank}", f"{fmt_num(b.burned_ha, 1, lang)} ha ({fmt_num(b.burned_pct, 2, lang)} %)",
             f"{fmt_num(b.slope_mean_deg, 1, lang)}°", f"{fmt_num(b.moisture_mean, 3, lang)} m³/m³",
             ", ".join(b.assets) or "—"]
            for b in territory.basins_by_rank()[:5]
        ]
        blocks.append(("table", t["tech_cols"], rows))
        if territory.barriers:
            blocks.append(("h", t["tech_bar_h"]))
            ordered = sorted(territory.barriers, key=lambda b: (not b.relevant, b.dist_from_fire_m))
            blocks.append(("ul", [
                t["tech_bar"].format(
                    lat=f"{b.lat:.5f}", lon=f"{b.lon:.5f}", dist=fmt_dist(b.dist_from_fire_m, lang),
                    s1=fmt_num(b.slope_before_deg, 1, lang), s2=fmt_num(b.slope_after_deg, 1, lang),
                    area=fmt_num(b.contrib_area_ha, 1, lang), star=t["tech_bar_star"] if b.relevant else "",
                )
                for b in ordered
            ]))
        blocks.append(("note", t["tech_thr"].format(
            d=_fmt_thresholds(config.RAIN_24H_THRESHOLDS_MM, lang),
            h=_fmt_thresholds(config.RAIN_1H_THRESHOLDS_MM, lang),
        )))

    footer = [t["foot_exp"]]
    if settings.site_url:
        footer.append(t["foot_map"].format(url=settings.site_url))
    if settings.contact:
        footer.append(t["foot_unsub"].format(contact=settings.contact))
    blocks.append(("footer", footer))
    return blocks


def render_text(title, blocks):
    out = [title.upper(), "=" * len(title), ""]
    for block in blocks:
        kind = block[0]
        if kind in ("p", "lead", "note"):
            out += [block[1], ""]
        elif kind == "h":
            out += [block[1], "-" * len(block[1])]
        elif kind == "ul":
            out += [f"- {item}" for item in block[1]] + [""]
        elif kind == "table":
            _, cols, rows = block
            widths = [max(len(str(r[i])) for r in [cols] + rows) for i in range(len(cols))]
            for row in [cols] + rows:
                out.append("  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)).rstrip())
            out.append("")
        elif kind == "footer":
            out += ["--"] + block[1]
    return "\n".join(out).rstrip() + "\n"


def render_html(title, color, lang, blocks):
    esc = html_lib.escape
    font = "font-family:Helvetica,Arial,sans-serif;"
    parts = []
    for block in blocks:
        kind = block[0]
        if kind == "p":
            parts.append(f'<p style="margin:0 0 14px;line-height:1.55;">{esc(block[1])}</p>')
        elif kind == "lead":
            parts.append(f'<p style="margin:0 0 10px;font-size:18px;line-height:1.45;font-weight:bold;color:#1F1A14;">{esc(block[1])}</p>')
        elif kind == "note":
            parts.append(f'<p style="margin:0 0 18px;font-size:13px;line-height:1.5;color:#6B6156;">{esc(block[1])}</p>')
        elif kind == "h":
            parts.append(f'<h2 style="margin:22px 0 8px;font-size:15px;color:{color};text-transform:uppercase;letter-spacing:0.04em;">{esc(block[1])}</h2>')
        elif kind == "ul":
            items = "".join(f'<li style="margin:0 0 7px;line-height:1.5;">{esc(item)}</li>' for item in block[1])
            parts.append(f'<ul style="margin:0 0 14px;padding-left:20px;">{items}</ul>')
        elif kind == "table":
            _, cols, rows = block
            cell = "padding:7px 10px;border-bottom:1px solid #DDD3C2;text-align:left;font-size:13px;vertical-align:top;"
            head = "".join(f'<th style="{cell}color:#6B6156;font-weight:bold;">{esc(c)}</th>' for c in cols)
            body = "".join(
                "<tr>" + "".join(f'<td style="{cell}">{esc(str(c))}</td>' for c in row) + "</tr>" for row in rows
            )
            parts.append(f'<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse;margin:0 0 14px;"><tr>{head}</tr>{body}</table>')
        elif kind == "footer":
            lines = "<br>".join(esc(line) for line in block[1])
            parts.append(f'<p style="margin:26px 0 0;padding-top:14px;border-top:1px solid #DDD3C2;font-size:12px;line-height:1.6;color:#6B6156;">{lines}</p>')
    return (
        f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title></head>'
        f'<body style="margin:0;padding:0;background:#F5F0E6;{font}color:#2B241C;font-size:15px;">'
        f'<div style="max-width:620px;margin:0 auto;padding:16px;">'
        f'<div style="background:{color};color:#FFFFFF;padding:14px 20px;border-radius:8px 8px 0 0;font-size:17px;font-weight:bold;">{esc(title)}</div>'
        f'<div style="background:#FFFFFF;padding:22px 20px;border:1px solid #DDD3C2;border-top:0;border-radius:0 0 8px 8px;">'
        + "".join(parts) +
        "</div></div></body></html>"
    )


def build_email(assessment, territory, sub, settings):
    """Return (subject, plain text, html) for one subscriber."""
    lang = sub.lang
    t = T[lang]
    worst = assessment.worst
    label = t["level"][assessment.level]
    if assessment.simulated:
        label = f"{t['drill']} · {label}"
    subject = "[GeoSignal] " + t["subject"].format(
        label=label, rain=t["rain"][assessment.level], date=fmt_short_date(worst.date, lang),
        fire=territory.fire_name.split(" (")[0], mm=_fmt_mm(worst.rain_mm, lang),
    )
    blocks = build_blocks(assessment, territory, sub, settings)
    return subject, render_text(label, blocks), render_html(label, LEVEL_COLOR[assessment.level], lang, blocks)
