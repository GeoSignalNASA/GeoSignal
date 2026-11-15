"""Command line for the alert system. Run from the repo root: python3 -m alerts <command>"""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from . import compose, config, engine, forecast, geodata, mailer, report, subscribers


def _get_days(args, territory):
    """Return (days, simulated) from the scenario flag, a saved file or the live API."""
    if args.rain_mm is not None:
        return forecast.scenario(args.rain_mm), True
    if args.forecast_file:
        payload = json.loads(Path(args.forecast_file).read_text(encoding="utf-8"))
        return forecast.parse_open_meteo(payload), False
    days = forecast.fetch_open_meteo(territory.centroid_lat, territory.centroid_lon, args.days)
    return days, False


def _print_assessment(assessment, territory):
    labels = compose.T["es"]["level"]
    origin = "escenario simulado" if assessment.simulated else "pronóstico Open-Meteo"
    print(f"Zona quemada: {territory.fire_name} · {territory.burned_ha} ha ({territory.burned_date}) · {origin}")
    for day, level in assessment.days:
        peak = f"{day.peak_mm_h} mm/h" if day.peak_mm_h else "—"
        print(f"  {day.date}  {day.rain_mm:6.1f} mm/24h  máx {peak:>10}  -> {labels[level]}")
    print(f"Nivel: {labels[assessment.level]} (día {assessment.worst.date})")
    print(f"Escorrentía estimada desde el núcleo quemado: {assessment.runoff_burned_m3:,.0f} m³ (C = {config.RUNOFF_COEFF})")


def cmd_check(args):
    territory = geodata.load_territory()
    days, simulated = _get_days(args, territory)
    _print_assessment(engine.assess(territory, days, simulated), territory)
    return 0


def _load_subs(args):
    subs = subscribers.load()
    if args.only:
        subs = [s for s in subs if s.email.lower() == args.only.lower()]
    if not subs:
        print("No hay suscriptores. Añade uno con: python3 -m alerts subscribe correo@ejemplo.org")
    return subs


def _deliver(jobs, send, settings):
    """jobs: [(kind, subscriber, (subject, text, html), on_sent)]. Dry run unless `send`."""
    if not jobs:
        print("Nada que enviar.")
        return 0
    if send and settings.missing_for_send():
        print("Falta configuración SMTP: " + ", ".join(settings.missing_for_send()), file=sys.stderr)
        return 2
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    if send:
        with mailer.SmtpSession(settings) as session:
            for kind, sub, (subject, text, html), on_sent in jobs:
                session.send(mailer.build_message(settings, sub.email, subject, text, html))
                print(f"  enviado  {sub.email}: {subject}")
                on_sent()
    else:
        for kind, sub, (subject, text, html), _ in jobs:
            eml, _ = mailer.write_outbox(mailer.build_message(settings, sub.email, subject, text, html), html, f"{stamp}-{kind}")
            print(f"  en seco  {sub.email}: {eml.relative_to(config.REPO_ROOT)}")
        print("Envío en seco: no se ha mandado ningún correo. Añade --send para enviarlos.")
    return 0


def _report_jobs(subs, territory, settings, state, assessment, force):
    """The study report, for everyone who has not received this version of it."""
    jobs = []
    for sub in subs:
        if not force and not engine.report_due(state, sub.email, territory.data_version):
            continue

        def on_sent(email=sub.email):
            engine.mark_report(state, email, territory.data_version)
            engine.save_state(state)

        jobs.append(("informe", sub, report.build_report(territory, sub, settings, assessment), on_sent))
    return jobs


def cmd_run(args):
    """What cron runs: pending study reports first, then rain alerts from the real forecast."""
    if args.rain_mm is not None and args.send:
        print("Los simulacros no se envían por correo. Quita --send para ver la vista previa en alerts/outbox/, "
              "o quita --rain-mm para usar la previsión real.", file=sys.stderr)
        return 2
    territory = geodata.load_territory()
    days, simulated = _get_days(args, territory)
    assessment = engine.assess(territory, days, simulated)
    _print_assessment(assessment, territory)

    subs = _load_subs(args)
    if not subs:
        return 1
    settings = config.MailSettings.from_env()
    state = engine.load_state()
    today = dt.date.today()

    # A drill is only a preview of the alert layout: no reports, nothing recorded.
    jobs = [] if simulated else _report_jobs(subs, territory, settings, state, assessment, force=False)
    for sub in subs:
        if not args.force and assessment.level < sub.min_level:
            print(f"  sin aviso {sub.email}: nivel por debajo de su mínimo ({sub.min_level})")
        elif not simulated and not args.force and engine.already_sent(state, sub.email, assessment.worst.date, assessment.level):
            print(f"  sin aviso {sub.email}: ya avisado de este episodio")
        else:
            def on_sent(email=sub.email):
                engine.mark_sent(state, email, assessment.worst.date, assessment.level, today)
                engine.save_state(state)

            jobs.append(("aviso", sub, compose.build_email(assessment, territory, sub, settings), on_sent))
    return _deliver(jobs, args.send, settings)


def cmd_report(args):
    """Send (or preview) the study report on its own."""
    territory = geodata.load_territory()
    subs = _load_subs(args)
    if not subs:
        return 1
    try:
        days = forecast.fetch_open_meteo(territory.centroid_lat, territory.centroid_lon, config.FORECAST_DAYS)
        assessment = engine.assess(territory, days)
    except Exception as err:  # the report is still complete without the forecast paragraph
        print(f"Sin previsión de lluvia ({err}); el informe sale sin ese apartado.")
        assessment = None
    settings = config.MailSettings.from_env()
    state = engine.load_state()
    jobs = _report_jobs(subs, territory, settings, state, assessment, force=args.force)
    for sub in subs:
        if all(job[1] is not sub for job in jobs):
            print(f"  omitido  {sub.email}: ya recibió esta versión del informe (usa --force para reenviarlo)")
    return _deliver(jobs, args.send, settings)


def cmd_subscribe(args):
    territory = geodata.load_territory()
    try:
        new = subscribers.Subscriber(
            email=args.email, name=args.name, lang=args.lang, places=args.place or [],
            profile=args.profile, min_level=args.min_level,
        ).validate(territory)
    except ValueError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 2
    subs, replaced = subscribers.upsert(subscribers.load(), new)
    subscribers.save(subs)
    print(f"{'Actualizado' if replaced else 'Añadido'}: {new.email} ({new.profile}, {new.lang}, "
          f"nivel mínimo {new.min_level}, lugares: {', '.join(new.places) or 'ninguno'})")
    return 0


def cmd_unsubscribe(args):
    subs, removed = subscribers.remove(subscribers.load(), args.email)
    if not removed:
        print(f"{args.email} no estaba suscrito.")
        return 1
    subscribers.save(subs)
    print(f"Eliminado: {args.email}")
    return 0


def cmd_list(_args):
    subs = subscribers.load()
    for s in subs:
        print(f"{s.email}  {s.profile}  {s.lang}  nivel≥{s.min_level}  {', '.join(s.places) or '-'}")
    print(f"{len(subs)} suscriptor(es)")
    return 0


def cmd_places(_args):
    territory = geodata.load_territory()
    names = {"direct": "microcuenca con zona quemada", "downstream": "junto a cauce aguas abajo", "none": "sin conexión"}
    for p in sorted(territory.places.values(), key=lambda p: (p.exposure, p.trace_dist_m)):
        basin = f"#{p.basin_id}" if p.basin_id is not None else "-"
        print(f"{p.name:22} {p.kind:10} cuenca {basin:4} cauce a {p.trace_dist_m:7.0f} m  {names[p.exposure]}")
    return 0


def cmd_serve(args):
    from . import server  # imported here so the other commands do not load http.server
    return server.serve(args.host, args.port)


def _add_forecast_args(parser):
    parser.add_argument("--rain-mm", type=float, help="vista previa de un aviso con esta lluvia en 24 h (nunca se envía por correo)")
    parser.add_argument("--forecast-file", help="JSON de Open-Meteo guardado, en vez de consultar la API")
    parser.add_argument("--days", type=int, default=config.FORECAST_DAYS, help="días de pronóstico (por defecto %(default)s)")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python3 -m alerts", description="Alertas por correo de lluvia sobre la zona quemada.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check", help="evalúa el pronóstico y muestra el nivel de alerta")
    _add_forecast_args(p)
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("report", help="informe del estudio para quien aún no lo ha recibido")
    p.add_argument("--send", action="store_true", help="envía de verdad por SMTP (sin esto solo escribe en alerts/outbox/)")
    p.add_argument("--force", action="store_true", help="reenvía aunque ya lo hubieran recibido")
    p.add_argument("--only", metavar="EMAIL", help="limita el envío a un suscriptor")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("run", help="informes pendientes + avisos de lluvia (lo que ejecuta cron)")
    _add_forecast_args(p)
    p.add_argument("--send", action="store_true", help="envía de verdad por SMTP (sin esto solo escribe en alerts/outbox/)")
    p.add_argument("--force", action="store_true", help="prepara el aviso aunque no haya alerta o ya se hubiera avisado")
    p.add_argument("--only", metavar="EMAIL", help="limita el envío a un suscriptor")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("subscribe", help="añade o actualiza un suscriptor")
    p.add_argument("email")
    p.add_argument("--name", default="")
    p.add_argument("--lang", default="es", choices=config.LANGS)
    p.add_argument("--place", action="append", help="núcleo de interés (repetible); ver 'places'")
    p.add_argument("--profile", default="resident", choices=config.PROFILES)
    p.add_argument("--min-level", type=int, default=1, choices=(1, 2, 3), help="1 amarillo, 2 naranja, 3 rojo")
    p.set_defaults(func=cmd_subscribe)

    p = sub.add_parser("unsubscribe", help="elimina un suscriptor")
    p.add_argument("email")
    p.set_defaults(func=cmd_unsubscribe)

    sub.add_parser("list", help="lista los suscriptores").set_defaults(func=cmd_list)
    sub.add_parser("places", help="lista los núcleos y su exposición").set_defaults(func=cmd_places)

    p = sub.add_parser("serve", help="sirve la web con la sección de alertas activa")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
