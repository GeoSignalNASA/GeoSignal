"""
Run from the repo root:  python3 -m unittest discover -s alerts/tests -t .

Uses the real web/assets/data inputs and a throwaway local SMTP sink, so
nothing here touches the network or a real mailbox.
"""

import datetime as dt
import email
import email.policy
import json
import os
import socketserver
import tempfile
import threading
import unittest
import unittest.mock
import urllib.error
import urllib.request
from pathlib import Path

from alerts import compose, config, engine, forecast, geodata, mailer, report, server, subscribers

SETTINGS = config.MailSettings(
    host="127.0.0.1", port=0, user="", password="", sender="alertas@example.org",
    security="none", contact="baja@example.org", site_url="https://example.org/mapa",
)


class SmtpSink(socketserver.StreamRequestHandler):
    """Just enough SMTP for smtplib to hand over a message."""

    def handle(self):
        self.wfile.write(b"220 sink ready\r\n")
        rcpt = []
        while True:
            line = self.rfile.readline()
            if not line:
                return
            verb = line[:4].upper()
            if verb in (b"EHLO", b"HELO"):
                self.wfile.write(b"250 sink\r\n")
            elif verb == b"RCPT":
                rcpt.append(line.decode().strip())
                self.wfile.write(b"250 ok\r\n")
            elif verb == b"DATA":
                self.wfile.write(b"354 go\r\n")
                body = b""
                while not body.endswith(b"\r\n.\r\n"):
                    body += self.rfile.readline()
                self.server.received.append((rcpt, body[:-5]))
                rcpt = []
                self.wfile.write(b"250 queued\r\n")
            elif verb == b"QUIT":
                self.wfile.write(b"221 bye\r\n")
                return
            else:
                self.wfile.write(b"250 ok\r\n")


class TerritoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.territory = geodata.load_territory()

    def test_inputs_match_the_storymap(self):
        t = self.territory
        self.assertEqual(len(t.basins), 26)
        self.assertAlmostEqual(t.burned_ha, 373.64)
        self.assertEqual([b.basin_id for b in t.basins_by_rank()[:2]], [9, 8])

    def test_place_exposure(self):
        t = self.territory
        self.assertEqual(t.find_place("as meaus").exposure, "direct")
        self.assertEqual(t.find_place("AS MEAUS").basin_id, 9)
        self.assertEqual(t.find_place("Embalse de Salas").exposure, "downstream")
        self.assertEqual(t.find_place("Baltar").exposure, "none")
        self.assertEqual(t.find_place("Muinos").name, "Muíños")  # accent-insensitive
        self.assertIsNone(t.find_place("Madrid"))

    def test_runoff_matches_web_simulator(self):
        # Chapter 07 of the StoryMap shows 269.021 m3 at 120 mm.
        a = engine.assess(self.territory, forecast.scenario(120), simulated=True)
        self.assertEqual(round(a.runoff_burned_m3), 269021)
        self.assertEqual(a.level, 3)

    def test_pool_comparison_is_rounded(self):
        self.assertEqual([compose.round_pools(v) for v in (1000, 18_000, 138_994, 269_021)], [0, 7, 55, 110])


class LevelTest(unittest.TestCase):
    def day(self, mm, peak=None):
        return forecast.DayForecast(dt.date(2026, 11, 17), mm, peak, 14 if peak else None)

    def test_daily_thresholds(self):
        self.assertEqual([engine.day_level(self.day(mm)) for mm in (0, 19.9, 20, 39.9, 40, 79.9, 80, 200)],
                         [0, 0, 1, 1, 2, 2, 3, 3])

    def test_hourly_intensity_can_raise_the_level(self):
        self.assertEqual(engine.day_level(self.day(12, peak=10)), 1)
        self.assertEqual(engine.day_level(self.day(25, peak=42)), 3)

    def test_worst_day_is_picked(self):
        territory = geodata.load_territory()
        days = [
            forecast.DayForecast(dt.date(2026, 11, 16), 5.0, 1.0, 9),
            forecast.DayForecast(dt.date(2026, 11, 17), 45.0, 9.0, 15),
            forecast.DayForecast(dt.date(2026, 11, 18), 22.0, 4.0, 3),
        ]
        a = engine.assess(territory, days)
        self.assertEqual((a.level, a.worst.date), (2, dt.date(2026, 11, 17)))
        self.assertEqual([lvl for _, lvl in a.days], [0, 2, 1])

    def test_parse_open_meteo(self):
        payload = {"hourly": {
            "time": [f"2026-11-17T{h:02d}:00" for h in range(24)] + ["2026-11-18T00:00"],
            "precipitation": [0.0] * 10 + [3.5, 12.0, 6.5] + [0.0] * 11 + [None],
        }}
        days = forecast.parse_open_meteo(payload)
        self.assertEqual(len(days), 2)
        self.assertEqual((days[0].rain_mm, days[0].peak_mm_h, days[0].peak_hour), (22.0, 12.0, 11))
        self.assertEqual((days[1].rain_mm, days[1].peak_hour), (0.0, None))


class MailSettingsTest(unittest.TestCase):
    def make(self, **over):
        base = dict(host="smtp.gmail.com", port=587, user="", password="", sender="", security="starttls", contact="", site_url="")
        return config.MailSettings(**{**base, **over})

    def test_gmail_needs_account_and_app_password(self):
        self.assertEqual(self.make().missing_for_send(), ["ALERTS_SMTP_USER", "ALERTS_SMTP_PASSWORD"])
        self.assertEqual(self.make(user="a@gmail.com", sender="a@gmail.com").missing_for_send(), ["ALERTS_SMTP_PASSWORD"])
        self.assertEqual(self.make(user="a@gmail.com", sender="a@gmail.com", password="x").missing_for_send(), [])

    def test_other_servers_may_be_open_relays(self):
        self.assertEqual(self.make(host="127.0.0.1", sender="a@example.org").missing_for_send(), [])


class StateTest(unittest.TestCase):
    def test_dedup_and_escalation(self):
        state, date, today = {}, dt.date(2026, 11, 17), dt.date(2026, 11, 16)
        self.assertFalse(engine.already_sent(state, "a@b.org", date, 1))
        engine.mark_sent(state, "a@b.org", date, 1, today)
        self.assertTrue(engine.already_sent(state, "a@b.org", date, 1))
        self.assertFalse(engine.already_sent(state, "a@b.org", date, 2))  # escalation goes out
        self.assertFalse(engine.already_sent(state, "c@d.org", date, 1))
        engine.mark_sent(state, "a@b.org", dt.date(2026, 11, 20), 1, dt.date(2026, 11, 19))
        self.assertNotIn("2026-11-17", state["a@b.org"])  # past events are pruned

    def test_report_goes_out_once_per_data_version(self):
        state = {}
        self.assertTrue(engine.report_due(state, "a@b.org", "v1"))
        engine.mark_report(state, "a@b.org", "v1")
        self.assertFalse(engine.report_due(state, "a@b.org", "v1"))
        self.assertTrue(engine.report_due(state, "a@b.org", "v2"))   # study data regenerated
        self.assertTrue(engine.report_due(state, "c@d.org", "v1"))   # new subscriber


class ReportTest(unittest.TestCase):
    """The study report: real results in plain language, never a drill."""

    @classmethod
    def setUpClass(cls):
        cls.territory = geodata.load_territory()

    def test_resident_report_es(self):
        sub = subscribers.Subscriber("a@b.org", name="Uxía", places=["As Meaus"])
        subject, text, html = report.build_report(self.territory, sub, SETTINGS)
        self.assertEqual(subject, "[GeoSignal] Informe del estudio del incendio de Calvos de Randín: qué se quemó y por dónde puede bajar el agua")
        for expected in (
            "24–27 de septiembre de 2026",
            "518 ha", "1.234 ha", "88,8 ha", "374 ha", "483 ha",       # every source of burned area
            "coincidencia de 0,77 sobre 1",
            "pasto y herbáceas (49 %) y arbolado (47 %)",
            "Cuenca de As Meaus, Rubiás y Santiago de Rubiás",
            "As Meaus: exposición alta",
            "como unas 35 piscinas olímpicas",                           # 40 l/m2 in the rain simulator
            "el lugar más cercano es As Meaus",
            "8 de las 10 pasadas",
            "112",
        ):
            self.assertIn(expected, text)
        for unwanted in ("SIMULACRO", "simulacro", "dB", "ΔHV", "m³", "Detalle técnico", "La lluvia prevista ahora"):
            self.assertNotIn(unwanted, text)
        self.assertIn("Informe del estudio · Calvos de Randín", html)

    def test_forecast_paragraph_uses_the_real_forecast(self):
        sub = subscribers.Subscriber("a@b.org")
        calm = engine.assess(self.territory, [forecast.DayForecast(dt.date(2026, 11, 15), 18.9, 2.8, 13),
                                               forecast.DayForecast(dt.date(2026, 11, 16), 3.1, 0.5, 4)])
        text = report.build_report(self.territory, sub, SETTINGS, calm)[1]
        self.assertIn("Ahora mismo no hay alerta. En los próximos 2 días, el más lluvioso será el domingo 15 de noviembre, con unos 19 litros", text)
        wet = engine.assess(self.territory, [forecast.DayForecast(dt.date(2026, 11, 17), 62.0, 14.5, 16)])
        self.assertIn("Ahora mismo hay alerta naranja: el martes 17 de noviembre", report.build_report(self.territory, sub, SETTINGS, wet)[1])
        # A made-up scenario never shows up as "the forecast".
        drill = engine.assess(self.territory, forecast.scenario(90), simulated=True)
        self.assertNotIn("La lluvia prevista ahora", report.build_report(self.territory, sub, SETTINGS, drill)[1])

    def test_technical_report_en(self):
        sub = subscribers.Subscriber("t@b.org", lang="en", profile="technical", places=["Randín"])
        subject, text, _ = report.build_report(self.territory, sub, SETTINGS)
        self.assertEqual(subject, "[GeoSignal] Study report on the Calvos de Randín wildfire: what burned and where water can run")
        for expected in ("September 24–27, 2026", "1,234 ha", "Randín: medium exposure", "about 35 Olympic swimming pools",
                         "Technical detail", "-1.5 dB", "r = -0.77", "89,674 m³", "(priority)"):
            self.assertIn(expected, text)


class SubscriberTest(unittest.TestCase):
    def test_validation(self):
        territory = geodata.load_territory()
        ok = subscribers.Subscriber("a@b.org", places=["rubias"]).validate(territory)
        self.assertEqual(ok.places, ["Rubiás"])
        for bad in (
            subscribers.Subscriber("not-an-email"),
            subscribers.Subscriber("a@b.org", lang="fr"),
            subscribers.Subscriber("a@b.org", min_level=5),
            subscribers.Subscriber("a@b.org", places=["Madrid"]),
        ):
            with self.assertRaises(ValueError):
                bad.validate(territory)

    def test_roundtrip_upsert_remove(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "subs.json"
            subs, replaced = subscribers.upsert([], subscribers.Subscriber("a@b.org", name="Ana"))
            self.assertFalse(replaced)
            subs, replaced = subscribers.upsert(subs, subscribers.Subscriber("A@B.org", name="Ana María"))
            self.assertTrue(replaced)
            subscribers.save(subs, path)
            loaded = subscribers.load(path)
            self.assertEqual([(s.email, s.name) for s in loaded], [("A@B.org", "Ana María")])
            self.assertEqual(subscribers.remove(loaded, "a@b.org"), ([], True))


class ServerTest(unittest.TestCase):
    """The API behind section 11 of the StoryMap, on a throwaway port."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.subs_file = Path(cls.tmp.name) / "subs.json"
        cls.calls = 0

        def fake_fetch(lat, lon, days):
            cls.calls += 1
            return [forecast.DayForecast(dt.date(2026, 11, 17), 45.0, 9.0, 15),
                    forecast.DayForecast(dt.date(2026, 11, 18), 3.0, 1.0, 2)]

        cls.state_file = Path(cls.tmp.name) / "state.json"
        service = server.AlertService(fetch=fake_fetch, subscribers_file=cls.subs_file, state_file=cls.state_file)
        cls.httpd = server.make_server("127.0.0.1", 0, service)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.tmp.cleanup()

    def call(self, path, body=None, content_type="application/json"):
        data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        req = urllib.request.Request(self.base + path, data=data, headers={"Content-Type": content_type} if data else {})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.load(resp)
        except urllib.error.HTTPError as err:
            return err.code, json.load(err)

    def test_serves_the_storymap(self):
        with urllib.request.urlopen(self.base + "/", timeout=10) as resp:
            self.assertIn(b'id="cap-11"', resp.read())

    def test_status_is_cached(self):
        first = self.call("/api/alerts/status")
        second = self.call("/api/alerts/status")
        self.assertEqual(first, second)
        self.assertEqual((first[0], first[1]["level"], first[1]["worst_date"]), (200, 2, "2026-11-17"))
        self.assertEqual([d["level"] for d in first[1]["days"]], [2, 0])
        self.assertEqual(self.calls, 1)  # one upstream request for both

    def test_places_most_exposed_first(self):
        status, data = self.call("/api/alerts/places")
        self.assertEqual(status, 200)
        self.assertEqual(len(data["places"]), 18)
        self.assertEqual(data["places"][0], {"name": "As Meaus", "kind": "hamlet", "exposure": "direct", "trace_dist_m": 314})

    def test_preview_sends_nothing_and_escapes_input(self):
        status, data = self.call("/api/alerts/preview", {"name": "<script>x</script>", "places": ["Randín"], "lang": "es"})
        self.assertEqual(status, 200)
        self.assertIn("Informe del estudio", data["subject"])
        self.assertIn("Randín: exposición media", data["html"])
        self.assertIn("Ahora mismo hay alerta naranja", data["html"])  # the (fake) real forecast: 45 mm
        self.assertNotIn("SIMULACRO", data["subject"] + data["html"])
        self.assertNotIn("<script>", data["html"])

    def test_subscribe_then_update(self):
        body = {"email": "ana@example.org", "name": "Ana", "places": ["rubias"], "lang": "es", "min_level": 2}
        self.assertEqual(self.call("/api/alerts/subscribe", body), (200, {"ok": True, "replaced": False}))
        self.assertEqual(self.call("/api/alerts/subscribe", {**body, "profile": "technical"}), (200, {"ok": True, "replaced": True}))
        saved = [s for s in subscribers.load(self.subs_file) if s.email == "ana@example.org"]  # other tests share the file
        self.assertEqual([(s.email, s.places, s.profile, s.min_level) for s in saved],
                         [("ana@example.org", ["Rubiás"], "technical", 2)])

    def test_bad_requests_are_rejected(self):
        post = lambda body, **kw: self.call("/api/alerts/subscribe", body, **kw)
        self.assertEqual(post({"email": "nope"})[1]["error"], "invalid_email")
        self.assertEqual(post({"email": "a@b.org", "places": ["Madrid"]})[0], 400)
        self.assertEqual(post({"email": "a@b.org", "min_level": 9})[0], 400)
        self.assertEqual(post(b"not json")[0], 400)
        self.assertEqual(post({"email": "a@b.org"}, content_type="text/plain")[0], 415)  # blocks cross-site form posts
        self.assertEqual(post(json.dumps({"email": "a@b.org", "name": "x" * 20000}).encode())[0], 413)
        self.assertEqual(self.call("/api/alerts/preview", {"places": ["Madrid"]})[0], 400)
        self.assertEqual(self.call("/api/alerts/nope")[0], 404)

    def test_report_is_sent_only_to_subscribers(self):
        self.assertEqual(self.call("/api/alerts/report", {"email": "nadie@example.org"})[1]["error"], "not_subscribed")
        self.assertEqual(self.call("/api/alerts/report", {"email": "nope"})[1]["error"], "invalid_email")

    def test_report_delivery_and_bookkeeping(self):
        sink = socketserver.ThreadingTCPServer(("127.0.0.1", 0), SmtpSink)
        sink.received = []
        threading.Thread(target=sink.serve_forever, daemon=True).start()
        env = {"ALERTS_SMTP_HOST": "127.0.0.1", "ALERTS_SMTP_PORT": str(sink.server_address[1]),
               "ALERTS_SMTP_SECURITY": "none", "ALERTS_FROM": "alertas@example.org"}
        try:
            self.call("/api/alerts/subscribe", {"email": "eva@example.org", "places": ["Feás"]})
            with unittest.mock.patch.dict(os.environ, env):
                self.assertTrue(self.call("/api/alerts/status")[1]["can_send_report"])
                status, data = self.call("/api/alerts/report", {"email": "eva@example.org"})
        finally:
            sink.shutdown()
            sink.server_close()
        self.assertEqual(status, 200)
        self.assertIn("Informe del estudio", data["subject"])
        (rcpt, raw), = sink.received
        self.assertIn("eva@example.org", rcpt[0])
        body = email.message_from_bytes(raw, policy=email.policy.default).get_body(("plain",)).get_content()
        self.assertIn("Feás: exposición alta", body)
        # Recorded, so the scheduled run will not send the same report again.
        state = engine.load_state(self.state_file)
        self.assertFalse(engine.report_due(state, "eva@example.org", geodata.load_territory().data_version))


class ComposeAndSendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.territory = geodata.load_territory()
        cls.assessment = engine.assess(cls.territory, [
            forecast.DayForecast(dt.date(2026, 11, 17), 62.0, 14.5, 16),
            forecast.DayForecast(dt.date(2026, 11, 18), 8.0, 2.0, 4),
        ])

    def test_resident_email_es(self):
        sub = subscribers.Subscriber("a@b.org", name="Ana <b>", places=["As Meaus", "Baltar"])
        subject, text, html = compose.build_email(self.assessment, self.territory, sub, SETTINGS)
        self.assertEqual(subject, "[GeoSignal] Alerta naranja: lluvia fuerte el martes 17 en el monte quemado de Calvos de Randín (62 l/m²)")
        self.assertIn("El martes 17 de noviembre se espera lluvia fuerte", text)
        self.assertIn("unos 62 litros por metro cuadrado", text)
        self.assertIn("Lo más intenso llegará hacia las 16:00", text)
        self.assertIn("El incendio de septiembre", text)
        self.assertIn("unas 55 piscinas olímpicas", text)  # 138.994 m3 / 2.500 m3, rounded
        self.assertIn("As Meaus: exposición alta", text)
        self.assertIn("pasa a unos 300 m", text)
        self.assertIn("Baltar: exposición baja", text)
        self.assertIn("112", text)
        self.assertIn("baja@example.org", text)
        # Residents get plain language: no jargon, no formulas.
        for jargon in ("Detalle técnico", "m³", "NISAR", "microcuenca", "mm/h", "C = "):
            self.assertNotIn(jargon, text)
        self.assertIn("Ana &lt;b&gt;", html)  # subscriber input is escaped
        self.assertNotIn("<b>", html)

    def test_technical_email_en(self):
        sub = subscribers.Subscriber("t@b.org", lang="en", profile="technical")
        subject, text, _ = compose.build_email(self.assessment, self.territory, sub, SETTINGS)
        self.assertIn("Orange alert: heavy rain on Tuesday 17", subject)
        self.assertIn("Tuesday, November 17", text)
        self.assertIn("138,994 m³", text)
        self.assertIn("Technical detail", text)
        self.assertIn("#9", text)
        self.assertIn("(priority)", text)
        self.assertIn("Most exposed places, on the slopes that collect water from the burned hillside: As Meaus", text)
        self.assertIn("peak intensity 14.5 mm/h (16:00)", text)

    def test_drill_is_labelled(self):
        a = engine.assess(self.territory, forecast.scenario(90, dt.date(2026, 11, 17)), simulated=True)
        subject, text, _ = compose.build_email(a, self.territory, subscribers.Subscriber("a@b.org"), SETTINGS)
        self.assertIn("SIMULACRO", subject)
        self.assertIn("no una previsión real", text)

    def test_delivery_through_smtp(self):
        server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), SmtpSink)
        server.received = []
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            settings = config.MailSettings(**{**SETTINGS.__dict__, "port": server.server_address[1]})
            recipients = [subscribers.Subscriber("ana@example.org", places=["Rubiás"]),
                          subscribers.Subscriber("tom@example.org", lang="en", profile="technical")]
            with mailer.SmtpSession(settings) as session:
                for sub in recipients:
                    subject, text, html = compose.build_email(self.assessment, self.territory, sub, settings)
                    session.send(mailer.build_message(settings, sub.email, subject, text, html))
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(len(server.received), 2)
        for (rcpt, raw), sub in zip(server.received, recipients):
            self.assertEqual(len(rcpt), 1)  # one recipient per message: no address leaks
            self.assertIn(sub.email, rcpt[0])
            msg = email.message_from_bytes(raw, policy=email.policy.default)
            self.assertEqual(msg["To"], sub.email)
            self.assertEqual(msg["From"], "alertas@example.org")
            self.assertIn("baja@example.org", msg["List-Unsubscribe"])
            self.assertEqual([p.get_content_type() for p in msg.iter_parts()], ["text/plain", "text/html"])
            self.assertIn("62", msg.get_body(("plain",)).get_content())

    def test_outbox_dry_run(self):
        sub = subscribers.Subscriber("ana@example.org")
        subject, text, html = compose.build_email(self.assessment, self.territory, sub, SETTINGS)
        with tempfile.TemporaryDirectory() as tmp:
            eml, preview = mailer.write_outbox(mailer.build_message(SETTINGS, sub.email, subject, text, html), html, "x", Path(tmp))
            self.assertIn("Alerta naranja", email.message_from_bytes(eml.read_bytes(), policy=email.policy.default)["Subject"])
            self.assertTrue(preview.read_text(encoding="utf-8").startswith("<!doctype html>"))


if __name__ == "__main__":
    unittest.main()
