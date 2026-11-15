"""
The study report: what the StoryMap chapters found, in plain language.

This is the email a person receives when they subscribe (and again only if
the study data is regenerated). It summarises the real results -- how much
burned according to each source, why radar was used, what kind of land
burned, where water can run, what the rain simulator gives for a few
amounts of rain, where barriers would help -- and what that means for the
subscriber's village. Nothing in it is a drill: the rain figures are the
simulator's scenarios, presented as such, and the "right now" paragraph is
the real forecast.

Every number comes from web/assets/data (the same files the page reads),
so the email and the map cannot disagree.
"""

import datetime as dt

from . import compose, config, engine
from .compose import MONTHS, fmt_date, fmt_dist, fmt_dist_plain, fmt_num, round_pools
from .geodata import haversine_m

REPORT_COLOR = "#23596A"

# ESA WorldCover classes present in the perimeter (story_stats.landcover_2021).
LANDCOVER = {
    "es": {10: "Arbolado", 20: "Matorral", 30: "Pasto y herbáceas", 50: "Zona urbana"},
    "en": {10: "Tree cover", 20: "Shrubland", 30: "Grassland", 50: "Built-up"},
}

R = {
    "es": {
        "title": "Informe del estudio",
        "subject": "Informe del estudio del incendio de {fire}: qué se quemó y por dónde puede bajar el agua",
        "lead": "Este es el resumen del estudio que hemos hecho con imágenes de satélite sobre el incendio de {fire} "
                "({period}): cuánto se quemó, por dónde puede bajar el agua cuando llueva y qué significa para tu zona.",
        "s1_h": "1. Cuánto se quemó",
        "s1_p": "La cifra depende de quién mide y de qué mide:",
        "s1_cols": ["Fuente", "Superficie", "Qué mide"],
        "s1_xunta": ["Xunta de Galicia (oficial)", "Medición sobre el terreno tras la extinción"],
        "s1_effis": ["EFFIS (Copernicus)", "Contorno exterior detectado automáticamente"],
        "s1_nisar1": ["Radar NISAR, {date}", "Vegetación muy dañada, primera pasada tras el fuego"],
        "s1_nisar2": ["Radar NISAR, {date}", "Vegetación muy dañada, con el terreno ya seco"],
        "s1_s2": ["Sentinel-2 (imagen óptica), {date}", "Quemado moderado o alto"],
        "s1_note": "Las cifras no se contradicen. El contorno de EFFIS incluye terreno poco afectado, y el radar solo "
                   "cuenta donde la vegetación quedó muy dañada. La primera pasada del radar vio menos porque había "
                   "llovido justo antes y el suelo mojado disimula la señal; la de finales de octubre, en seco, es la más fiable.",
        "s2_h": "2. Por qué se usó radar",
        "s2_p": "En los días clave, el humo y después las nubes (el 30 de septiembre cubrían el 91 % de la imagen) "
                "impedían ver el monte con satélites ópticos. El radar del satélite NISAR atraviesa humo y nubes. Cuando "
                "por fin se despejó, la imagen óptica y la del radar coincidieron en buena medida en dónde está el daño "
                "(coincidencia de {r} sobre 1).",
        "s3_h": "3. Qué tipo de terreno ardió",
        "s3_p": "Dentro del perímetro del incendio, {a} ({ap} %) y {b} ({bp} %) se reparten casi todo el terreno. "
                "El daño fuerte aparece sobre todo en {worst}.",
        "s3_cols": ["Tipo de terreno", "Superficie", "Con daño fuerte"],
        "s3_note": "Tipos de terreno según el mapa ESA WorldCover de 2021.",
        "s4_h": "4. Por dónde puede bajar el agua",
        "s4_p": "Dividimos el terreno en {n} cuencas pequeñas (cada una recoge el agua de sus laderas hacia un mismo "
                "regato) y miramos en cuáles se junta más monte quemado, más pendiente y suelo más seco. Las de mayor "
                "riesgo de arrastre son las que contienen el incendio:",
        "s4_basin": "Cuenca de {names}: {ha} ha muy dañadas ya en la primera pasada del radar y pendiente media de {slope}°.",
        "s4_basin_empty": "Cuenca sin pueblos dentro: {ha} ha muy dañadas ya en la primera pasada del radar y pendiente media de {slope}°.",
        "s4_you": "Tu zona:",
        "s5_h": "5. Qué pasaría si llueve",
        "s5_p": "Con el simulador de lluvia del estudio calculamos cuánta agua bajaría del monte quemado según lo que "
                "llueva en un día:",
        "s5_cols": ["Lluvia en un día", "Agua que bajaría del monte quemado", "Nivel de aviso"],
        "s5_row": "como unas {pools} piscinas olímpicas",
        "s5_note": "Son cálculos orientativos: suponen que el {pct} % de la lluvia corre por la superficie en lugar de "
                   "filtrarse, un valor razonable para suelo quemado pero que no se ha medido aquí.",
        "s6_h": "6. Dónde convendría frenar el agua",
        "s6_p": "El estudio localizó {n} puntos donde el terreno pasa de mucha a poca pendiente; ahí el agua pierde "
                "fuerza y es donde conviene colocar barreras de retención (fajinas). El prioritario está a unos {dist} "
                "del perímetro del incendio; el lugar más cercano es {place}, a unos {pdist}.",
        "now_h": "La lluvia prevista ahora",
        "now_calm": "Ahora mismo no hay alerta. En los próximos {n} días, el más lluvioso será el {date}, con unos {mm} "
                    "litros por metro cuadrado. Te escribiremos si la previsión alcanza el nivel de aviso que elegiste.",
        "now_alert": "Ahora mismo hay {label}: el {date} se esperan unos {mm} litros por metro cuadrado sobre el monte quemado.",
        "lim_h": "Límites del estudio",
        "lim": [
            "El radar ve el daño en la vegetación, no cómo ha quedado el suelo ni cuánta agua absorbe.",
            "Los cálculos de lluvia son escenarios, no previsiones.",
            "Los datos del satélite NISAR están todavía en fase provisional; {ok} de las {n} pasadas usadas superaron el control de calidad.",
        ],
        "todo_h": "Si llueve fuerte",
        "tech_h": "Detalle técnico",
        "tech_p": "NISAR GCOV, {track}; par pre/post {pre} / {post}. ΔHV neto en el perímetro frente a la zona de control: "
                  "{net} dB el {post}; media el 25-oct {m25} dB (control {c25} dB). Correlación con dNBR de Sentinel-2: "
                  "r = {r} (25-oct) y r = {r01} (01-oct).",
        "tech_thr_cols": ["Umbral ΔHV", "Superficie (100 m)", "Superficie (20 m)", "Falsos positivos en control (20 m)"],
        "tech_run_cols": ["Lluvia 24 h", "Escorrentía núcleo quemado", "Cauce principal (Salas/Limia)"],
        "tech_run_note": "Escorrentía = área × lluvia × C, con C = {c} (supuesto). Área quemada {burned} ha ({bdate}); "
                         "área contribuyente máxima {area} ha.",
        "foot_exp": "Informe elaborado por GeoSignal con datos abiertos de NASA/ISRO (NISAR), Copernicus y OpenStreetMap.",
    },
    "en": {
        "title": "Study report",
        "subject": "Study report on the {fire} wildfire: what burned and where water can run",
        "lead": "This is a summary of the satellite study we carried out on the {fire} wildfire ({period}): how much "
                "burned, where water can run when it rains, and what that means for your area.",
        "s1_h": "1. How much burned",
        "s1_p": "The figure depends on who measures and what they measure:",
        "s1_cols": ["Source", "Area", "What it measures"],
        "s1_xunta": ["Xunta de Galicia (official)", "Ground survey after the fire was put out"],
        "s1_effis": ["EFFIS (Copernicus)", "Outer contour detected automatically"],
        "s1_nisar1": ["NISAR radar, {date}", "Badly damaged vegetation, first pass after the fire"],
        "s1_nisar2": ["NISAR radar, {date}", "Badly damaged vegetation, once the ground was dry"],
        "s1_s2": ["Sentinel-2 (optical image), {date}", "Moderate or high burn"],
        "s1_note": "The figures do not contradict each other. The EFFIS contour includes lightly affected ground, and "
                   "the radar only counts places where vegetation was badly damaged. The first radar pass saw less "
                   "because it had just rained and wet soil hides the signal; the late-October pass, in dry conditions, "
                   "is the most reliable.",
        "s2_h": "2. Why radar was used",
        "s2_p": "On the days that mattered, smoke and then cloud (covering 91% of the image on September 30) kept "
                "optical satellites from seeing the hillside. The radar on the NISAR satellite sees through smoke and "
                "cloud. Once the sky cleared, the optical image and the radar largely agreed on where the damage is "
                "(agreement of {r} out of 1).",
        "s3_h": "3. What kind of land burned",
        "s3_p": "Inside the fire perimeter, {a} ({ap}%) and {b} ({bp}%) make up almost all the land. Severe damage "
                "shows up mostly in {worst}.",
        "s3_cols": ["Land type", "Area", "Severely damaged"],
        "s3_note": "Land types from the 2021 ESA WorldCover map.",
        "s4_h": "4. Where water can run",
        "s4_p": "We split the terrain into {n} small catchments (each one gathers water from its slopes into the same "
                "stream) and looked at which combine the most burned ground, the steepest slopes and the driest soil. "
                "The ones with the highest wash-off risk are those containing the fire:",
        "s4_basin": "Catchment of {names}: {ha} ha already badly damaged in the first radar pass, average slope {slope}°.",
        "s4_basin_empty": "Catchment with no villages inside: {ha} ha already badly damaged in the first radar pass, average slope {slope}°.",
        "s4_you": "Your area:",
        "s5_h": "5. What would happen if it rains",
        "s5_p": "With the study's rain simulator we worked out how much water would come off the burned hillside "
                "depending on how much it rains in a day:",
        "s5_cols": ["Rain in one day", "Water coming off the burned hillside", "Warning level"],
        "s5_row": "about {pools} Olympic swimming pools",
        "s5_note": "These are rough figures: they assume {pct}% of the rain runs over the surface instead of soaking "
                   "in, a reasonable value for burned soil but not one measured here.",
        "s6_h": "6. Where it would help to slow the water",
        "s6_p": "The study found {n} points where the terrain goes from steep to gentle; that is where water loses "
                "force and where retention barriers are best placed. The priority one is about {dist} from the fire "
                "perimeter; the nearest place is {place}, about {pdist} away.",
        "now_h": "Rain forecast right now",
        "now_calm": "There is no alert right now: the wettest of the next {n} days is {date}, with about {mm} mm. "
                    "We will write to you if the forecast reaches the warning level you chose.",
        "now_alert": "Right now there is a {label}: about {mm} mm is expected over the burned hillside on {date}.",
        "lim_h": "Limits of the study",
        "lim": [
            "Radar sees damage to vegetation, not the state of the soil or how much water it absorbs.",
            "The rain figures are scenarios, not forecasts.",
            "Data from the NISAR satellite is still provisional; {ok} of the {n} passes used cleared quality control.",
        ],
        "todo_h": "If it rains hard",
        "tech_h": "Technical detail",
        "tech_p": "NISAR GCOV, {track}; pre/post pair {pre} / {post}. Net ΔHV inside the perimeter versus the control "
                  "area: {net} dB on {post}; 25 Oct mean {m25} dB (control {c25} dB). Correlation with Sentinel-2 dNBR: "
                  "r = {r} (25 Oct) and r = {r01} (01 Oct).",
        "tech_thr_cols": ["ΔHV threshold", "Area (100 m)", "Area (20 m)", "False positives in control (20 m)"],
        "tech_run_cols": ["24 h rain", "Burned-core runoff", "Main channel (Salas/Limia)"],
        "tech_run_note": "Runoff = area × rain × C, with C = {c} (assumed). Burned area {burned} ha ({bdate}); "
                         "maximum contributing area {area} ha.",
        "foot_exp": "Report prepared by GeoSignal from open NASA/ISRO (NISAR), Copernicus and OpenStreetMap data.",
    },
}


def fmt_day(iso, lang):
    date = dt.date.fromisoformat(iso)
    month = MONTHS[lang][date.month - 1]
    return f"{date.day} de {month}" if lang == "es" else f"{month} {date.day}"


def fmt_period(start_iso, end_iso, lang):
    a, b = dt.date.fromisoformat(start_iso), dt.date.fromisoformat(end_iso)
    if (a.year, a.month) != (b.year, b.month):
        return f"{fmt_day(start_iso, lang)} – {fmt_day(end_iso, lang)}, {b.year}"
    month = MONTHS[lang][a.month - 1]
    return f"{a.day}–{b.day} de {month} de {a.year}" if lang == "es" else f"{month} {a.day}–{b.day}, {a.year}"


def join_names(names, lang):
    if len(names) < 2:
        return "".join(names)
    return ", ".join(names[:-1]) + (" y " if lang == "es" else " and ") + names[-1]


def _ha(value, lang):
    return f"{fmt_num(value, 0 if value >= 100 else 1, lang)} ha"


def nearest_place(territory, lon, lat):
    """Closest settlement (not reservoir) to a point, with its distance in metres."""
    towns = [p for p in territory.places.values() if p.kind != "reservoir"]
    best = min(towns, key=lambda p: haversine_m(lon, lat, p.lon, p.lat))
    return best, haversine_m(lon, lat, best.lon, best.lat)


def build_blocks(territory, sub, settings, assessment=None):
    lang = sub.lang
    r, t = R[lang], compose.T[lang]
    stats, meta = territory.stats, territory.stats["meta"]
    fire = territory.fire_name.split(" (")[0]
    unit = t["unit"]
    blocks = []

    blocks.append(("p", t["hello"].format(name=f" {sub.name}" if sub.name else "")))
    blocks.append(("lead", r["lead"].format(fire=fire, period=fmt_period(meta["ignition_date"], meta["controlled_date"], lang))))

    # 1. How much burned ------------------------------------------------------
    dnbr = stats["optical_dnbr"]
    def source(key, area, date=None):
        name, what = r[key]
        return [name.format(date=fmt_day(date, lang)) if date else name, _ha(area, lang), what]
    blocks.append(("h", r["s1_h"]))
    blocks.append(("p", r["s1_p"]))
    blocks.append(("table", r["s1_cols"], [
        source("s1_xunta", meta["official_xunta_ha"]),
        source("s1_effis", meta["effis_ha"]),
        source("s1_nisar1", stats["severity_smooth"]["burned_total_ha"], meta["post_date"]),
        source("s1_nisar2", territory.burned_ha, territory.burned_date),
        source("s1_s2", dnbr["burned_mod_high_ha"], dnbr["post_scene"]),
    ]))
    blocks.append(("p", r["s1_note"]))

    # 2. Why radar ------------------------------------------------------------
    blocks.append(("h", r["s2_h"]))
    blocks.append(("p", r["s2_p"].format(r=fmt_num(abs(dnbr["pearson_r_vs_dhv_oct25"]), 2, lang))))

    # 3. Land cover -----------------------------------------------------------
    cover = sorted(stats["landcover_2021"], key=lambda c: -c["area_ha"])
    names = LANDCOVER[lang]
    label = lambda c: names.get(c["code"], c["name"])
    worst = max(cover, key=lambda c: c["burned_pct_oct25_15db"])
    blocks.append(("h", r["s3_h"]))
    blocks.append(("p", r["s3_p"].format(
        a=label(cover[0]).lower(), ap=fmt_num(cover[0]["pct_of_perimeter"], 0, lang),
        b=label(cover[1]).lower(), bp=fmt_num(cover[1]["pct_of_perimeter"], 0, lang),
        worst=label(worst).lower(),
    )))
    blocks.append(("table", r["s3_cols"], [
        [label(c), _ha(c["area_ha"], lang), f"{fmt_num(c['burned_pct_oct25_15db'], 0, lang)} %"] for c in cover
    ]))
    blocks.append(("note", r["s3_note"]))

    # 4. Where water runs -----------------------------------------------------
    burned_basins = [b for b in territory.basins_by_rank() if b.overlaps_fire]
    blocks.append(("h", r["s4_h"]))
    blocks.append(("p", r["s4_p"].format(n=len(territory.basins))))
    blocks.append(("ul", [
        r["s4_basin" if b.assets else "s4_basin_empty"].format(
            names=join_names(b.assets, lang), ha=fmt_num(b.burned_ha, 1, lang), slope=fmt_num(b.slope_mean_deg, 1, lang))
        for b in burned_basins
    ]))
    places = [p for p in (territory.find_place(name) for name in sub.places) if p is not None]
    if places:
        blocks.append(("p", r["s4_you"]))
        blocks.append(("ul", [compose._place_line(p, t, lang) for p in places]))
    else:
        everyone = sorted(territory.places.values(), key=lambda p: p.name)
        down = [p.name for p in everyone if p.exposure == "downstream"]
        if down:
            blocks.append(("p", t["general_down"].format(names=", ".join(down))))

    # 5. Rain simulator -------------------------------------------------------
    burned_m2 = territory.burned_ha * 10_000
    blocks.append(("h", r["s5_h"]))
    blocks.append(("p", r["s5_p"]))
    blocks.append(("table", r["s5_cols"], [
        [f"{fmt_num(mm, 0, lang)} {unit}",
         r["s5_row"].format(pools=fmt_num(round_pools(engine.runoff_m3(burned_m2, mm)), 0, lang)),
         t["level"][level]]
        for level, mm in enumerate(config.RAIN_24H_THRESHOLDS_MM, start=1)
    ]))
    blocks.append(("note", r["s5_note"].format(pct=fmt_num(config.RUNOFF_COEFF * 100, 0, lang))))

    # 6. Barriers -------------------------------------------------------------
    priority = sorted((b for b in territory.barriers if b.relevant), key=lambda b: b.dist_from_fire_m)
    if priority:
        top = priority[0]
        place, pdist = nearest_place(territory, top.lon, top.lat)
        blocks.append(("h", r["s6_h"]))
        blocks.append(("p", r["s6_p"].format(
            n=len(territory.barriers), dist=fmt_dist_plain(top.dist_from_fire_m, lang),
            place=place.name, pdist=fmt_dist_plain(pdist, lang),
        )))

    # Real forecast, when there is one ---------------------------------------
    if assessment is not None and not assessment.simulated:
        worst_day = assessment.worst
        mm = fmt_num(worst_day.rain_mm, 0 if worst_day.rain_mm >= 10 else 1, lang)
        blocks.append(("h", r["now_h"]))
        if assessment.level:
            blocks.append(("p", r["now_alert"].format(label=t["level"][assessment.level].lower(), date=fmt_date(worst_day.date, lang), mm=mm)))
        else:
            blocks.append(("p", r["now_calm"].format(n=len(assessment.days), date=fmt_date(worst_day.date, lang), mm=mm)))

    # Limits and advice -------------------------------------------------------
    qa = stats["qa"]
    blocks.append(("h", r["lim_h"]))
    blocks.append(("ul", [line.format(ok=sum(1 for q in qa if q["qa_pass"]), n=len(qa)) for line in r["lim"]]))
    blocks.append(("h", r["todo_h"]))
    blocks.append(("ul", t["todo"]))

    if sub.profile == "technical":
        pol = stats["polarizations"]
        db = lambda v: fmt_num(v, 2, lang)
        blocks.append(("h", r["tech_h"]))
        blocks.append(("p", r["tech_p"].format(
            track=meta["track_frame"], pre=meta["pre_date"], post=meta["post_date"],
            net=db(pol["hv_fire_net_db"]), m25=db(pol["hv_oct25_fire_mean_db"]), c25=db(pol["hv_oct25_ctrl_mean_db"]),
            r=db(dnbr["pearson_r_vs_dhv_oct25"]), r01=db(dnbr["pearson_r_vs_dhv_oct01"]),
        )))
        curve = {row["threshold_db"]: row for row in stats["threshold_curve"]}
        blocks.append(("table", r["tech_thr_cols"], [
            [f"{fmt_num(thr, 1, lang)} dB", _ha(curve[thr]["ha_smooth"], lang), _ha(curve[thr]["ha_raw"], lang),
             f"{fmt_num(curve[thr]['fp_ctrl_pct_raw'], 2, lang)} %"]
            for thr in (-1.5, -3.0, -6.0) if thr in curve
        ]))
        blocks.append(("table", r["tech_run_cols"], [
            [f"{fmt_num(mm, 0, lang)} mm", f"{fmt_num(engine.runoff_m3(burned_m2, mm), 0, lang)} m³",
             f"{fmt_num(engine.runoff_m3(territory.max_contrib_area_m2, mm), 0, lang)} m³"]
            for mm in config.RAIN_24H_THRESHOLDS_MM
        ]))
        blocks.append(("note", r["tech_run_note"].format(
            c=fmt_num(config.RUNOFF_COEFF, 1, lang), burned=fmt_num(territory.burned_ha, 1, lang),
            bdate=territory.burned_date, area=fmt_num(territory.max_contrib_area_m2 / 10_000, 0, lang),
        )))
        blocks.append(("table", t["tech_cols"], [
            [f"#{b.basin_id}", f"#{b.rank}", f"{fmt_num(b.burned_ha, 1, lang)} ha ({fmt_num(b.burned_pct, 2, lang)} %)",
             f"{fmt_num(b.slope_mean_deg, 1, lang)}°", f"{fmt_num(b.moisture_mean, 3, lang)} m³/m³",
             ", ".join(b.assets) or "—"]
            for b in territory.basins_by_rank()[:5]
        ]))
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

    footer = [r["foot_exp"]]
    if settings.site_url:
        footer.append(t["foot_map"].format(url=settings.site_url))
    if settings.contact:
        footer.append(t["foot_unsub"].format(contact=settings.contact))
    blocks.append(("footer", footer))
    return blocks


def build_report(territory, sub, settings, assessment=None):
    """Return (subject, plain text, html). `assessment` adds the real forecast paragraph."""
    lang = sub.lang
    r = R[lang]
    fire = territory.fire_name.split(" (")[0]
    title = f"{r['title']} · {fire}"
    subject = "[GeoSignal] " + r["subject"].format(fire=fire)
    blocks = build_blocks(territory, sub, settings, assessment)
    return subject, compose.render_text(title, blocks), compose.render_html(title, REPORT_COLOR, lang, blocks)
