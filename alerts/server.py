"""
Serve the StoryMap (web/) plus a small JSON API so the "Alertas" section of
the page can show the current level, preview an email and subscribe people.

    python3 -m alerts serve            # http://127.0.0.1:8765/

Endpoints (all under /api/alerts/):
    GET  status      current forecast and alert level
    GET  places      settlements and how exposed each one is
    POST preview     the study report a given person would receive (nothing is sent)
    POST subscribe   add or update a subscriber
    POST report      send the study report to an already-subscribed address;
                     only accepted from this machine

Limits worth knowing before putting this on a public host: subscribing has
no confirmation email (anyone can sign up any address) and there is no rate
limiting. That is fine for a demo on localhost, not for production.
"""

import datetime as dt
import ipaddress
import json
import smtplib
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from . import config, engine, forecast, geodata, mailer, report, subscribers

API_PREFIX = "/api/alerts/"
MAX_BODY_BYTES = 10_000
FORECAST_TTL_S = 15 * 60


class ApiError(Exception):
    def __init__(self, status, code, message=""):
        super().__init__(message or code)
        self.status, self.code, self.message = status, code, message or code


class AlertService:
    """Everything the handlers need, shared across request threads."""

    def __init__(self, fetch=forecast.fetch_open_meteo, subscribers_file=None, state_file=None):
        self.territory = geodata.load_territory()
        self.fetch = fetch
        self.subscribers_file = subscribers_file
        self.state_file = state_file
        self.lock = threading.Lock()
        self._cache = None  # (monotonic time, days)

    def forecast_days(self):
        with self.lock:
            if self._cache and time.monotonic() - self._cache[0] < FORECAST_TTL_S:
                return self._cache[1]
        try:
            days = self.fetch(self.territory.centroid_lat, self.territory.centroid_lon, config.FORECAST_DAYS)
        except Exception as err:  # network, DNS, bad payload: all mean "no forecast"
            raise ApiError(502, "forecast_unavailable", str(err))
        with self.lock:
            self._cache = (time.monotonic(), days)
        return days

    def assessment(self):
        return engine.assess(self.territory, self.forecast_days())

    def assessment_or_none(self):
        """The report is complete without the forecast paragraph, so a failed lookup is not fatal."""
        try:
            return self.assessment()
        except ApiError:
            return None

    # --- endpoints ----------------------------------------------------------

    def status(self, local):
        a = self.assessment()
        settings = config.MailSettings.from_env()
        return {
            "level": a.level,
            "worst_date": a.worst.date.isoformat(),
            "days": [
                {"date": d.date.isoformat(), "rain_mm": d.rain_mm, "peak_mm_h": d.peak_mm_h,
                 "peak_hour": d.peak_hour, "level": lvl}
                for d, lvl in a.days
            ],
            "thresholds": {"rain_24h_mm": config.RAIN_24H_THRESHOLDS_MM, "rain_1h_mm": config.RAIN_1H_THRESHOLDS_MM},
            "can_send_report": local and not settings.missing_for_send(),
        }

    def places(self):
        order = {"direct": 0, "downstream": 1, "none": 2}
        ranked = sorted(self.territory.places.values(), key=lambda p: (order[p.exposure], p.name))
        return {"places": [
            {"name": p.name, "kind": p.kind, "exposure": p.exposure, "trace_dist_m": round(p.trace_dist_m)}
            for p in ranked
        ]}

    def _subscriber(self, body, email):
        places = body.get("places") or []
        if not isinstance(places, list) or len(places) > 5 or not all(isinstance(p, str) for p in places):
            raise ApiError(400, "invalid", "places must be a short list of names")
        try:
            return subscribers.Subscriber(
                email=email,
                name=str(body.get("name") or "").strip()[:80],
                lang=body.get("lang", "es"),
                places=places,
                profile=body.get("profile", "resident"),
                min_level=body.get("min_level", 1),
            ).validate(self.territory)
        except (ValueError, TypeError) as err:
            raise ApiError(400, "invalid", str(err))

    @staticmethod
    def _email(body):
        email = str(body.get("email") or "").strip()
        if not subscribers.EMAIL_RE.match(email) or len(email) > 254:
            raise ApiError(400, "invalid_email")
        return email

    def preview(self, body):
        sub = self._subscriber(body, "preview@example.org")
        subject, _text, html = report.build_report(self.territory, sub, config.MailSettings.from_env(), self.assessment_or_none())
        return {"subject": subject, "html": html}

    def subscribe(self, body):
        sub = self._subscriber(body, self._email(body))
        with self.lock:
            subs, replaced = subscribers.upsert(subscribers.load(self.subscribers_file), sub)
            subscribers.save(subs, self.subscribers_file)
        return {"ok": True, "replaced": replaced}

    def send_report(self, body, local):
        if not local:
            raise ApiError(403, "forbidden", "sending is only accepted from this machine")
        email = self._email(body)
        with self.lock:
            match = [s for s in subscribers.load(self.subscribers_file) if s.email.lower() == email.lower()]
        if not match:
            raise ApiError(404, "not_subscribed")
        settings = config.MailSettings.from_env()
        if settings.missing_for_send():
            raise ApiError(409, "smtp_not_configured", ", ".join(settings.missing_for_send()))
        subject, text, html = report.build_report(self.territory, match[0], settings, self.assessment_or_none())
        try:
            with mailer.SmtpSession(settings) as session:
                session.send(mailer.build_message(settings, match[0].email, subject, text, html))
        except (smtplib.SMTPException, OSError) as err:
            raise ApiError(502, "smtp_failed", str(err))
        with self.lock:  # so the scheduled run does not send the same report again
            state = engine.load_state(self.state_file)
            engine.mark_report(state, match[0].email, self.territory.data_version)
            engine.save_state(state, self.state_file)
        return {"ok": True, "subject": subject}


class Handler(SimpleHTTPRequestHandler):
    service = None  # set by make_server

    def _is_local(self):
        try:
            return ipaddress.ip_address(self.client_address[0]).is_loopback
        except ValueError:
            return False

    def _json(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        # Requiring JSON keeps other websites from posting here with a plain form.
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            raise ApiError(415, "invalid", "Content-Type must be application/json")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ApiError(400, "invalid", "bad Content-Length")
        if not 0 < length <= MAX_BODY_BYTES:
            raise ApiError(413, "invalid", "body missing or too large")
        try:
            body = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            raise ApiError(400, "invalid", "body is not valid JSON")
        if not isinstance(body, dict):
            raise ApiError(400, "invalid", "body must be a JSON object")
        return body

    def _api(self, method):
        route = self.path.split("?", 1)[0][len(API_PREFIX):]
        try:
            if method == "GET" and route == "status":
                result = self.service.status(self._is_local())
            elif method == "GET" and route == "places":
                result = self.service.places()
            elif method == "POST" and route == "preview":
                result = self.service.preview(self._body())
            elif method == "POST" and route == "subscribe":
                result = self.service.subscribe(self._body())
            elif method == "POST" and route == "report":
                result = self.service.send_report(self._body(), self._is_local())
            else:
                raise ApiError(404, "not_found")
        except ApiError as err:
            return self._json(err.status, {"error": err.code, "message": err.message})
        self._json(200, result)

    def do_GET(self):
        if self.path.startswith(API_PREFIX):
            return self._api("GET")
        super().do_GET()

    def do_POST(self):
        if self.path.startswith(API_PREFIX):
            return self._api("POST")
        self.send_error(405)


def make_server(host="127.0.0.1", port=8765, service=None):
    handler = partial(Handler, directory=str(config.REPO_ROOT / "web"))
    Handler.service = service or AlertService()
    return ThreadingHTTPServer((host, port), handler)


def serve(host, port):
    server = make_server(host, port)
    print(f"GeoSignal + alertas en http://{host}:{server.server_address[1]}/  (Ctrl+C para parar)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
