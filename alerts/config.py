"""
Settings for the alert system.

Thresholds and the runoff coefficient are operating assumptions, not
calibrated values: nobody has measured infiltration on this burn scar.
RUNOFF_COEFF matches the web simulator (web/story/story.js) on purpose so
the email and the map never disagree. Tune the thresholds with Proteccion
Civil / AEMET before using this for anything beyond a demo.
"""

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "web" / "assets" / "data"
ALERTS_DIR = Path(__file__).resolve().parent

SUBSCRIBERS_FILE = ALERTS_DIR / "subscribers.json"
STATE_FILE = ALERTS_DIR / "state.json"
OUTBOX_DIR = ALERTS_DIR / "outbox"

# Same value as RUNOFF_COEFF in web/story/story.js.
RUNOFF_COEFF = 0.6

# Alert level per forecast day = the highest level reached by either the
# 24 h total or the peak hourly intensity. Index 0 -> level 1 (yellow),
# 1 -> level 2 (orange), 2 -> level 3 (red).
RAIN_24H_THRESHOLDS_MM = (20.0, 40.0, 80.0)
RAIN_1H_THRESHOLDS_MM = (10.0, 20.0, 40.0)

FORECAST_DAYS = 3

# A place counts as "downstream" when it sits this close to one of the D8
# runoff traces that start on the fire perimeter (rain_channels.geojson).
DOWNSTREAM_MAX_DIST_M = 1000.0

LEVEL_KEYS = {0: "none", 1: "yellow", 2: "orange", 3: "red"}
LANGS = ("es", "en")
PROFILES = ("resident", "technical")


def load_dotenv(path=REPO_ROOT / ".env"):
    """Read KEY=VALUE lines from .env (already git-ignored) without overriding
    variables that are set in the real environment."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


@dataclass
class MailSettings:
    host: str
    port: int
    user: str
    password: str
    sender: str
    security: str  # "starttls" | "ssl" | "none"
    contact: str   # address people write to in order to unsubscribe
    site_url: str  # public URL of the StoryMap, linked from the email

    @classmethod
    def from_env(cls):
        load_dotenv()
        env = os.environ.get
        user = env("ALERTS_SMTP_USER", "")
        sender = env("ALERTS_FROM", user)
        return cls(
            host=env("ALERTS_SMTP_HOST", "smtp.gmail.com"),
            port=int(env("ALERTS_SMTP_PORT", "587")),
            user=user,
            password=env("ALERTS_SMTP_PASSWORD", "").replace(" ", ""),
            sender=sender,
            security=env("ALERTS_SMTP_SECURITY", "starttls").lower(),
            contact=env("ALERTS_CONTACT", sender),
            site_url=env("ALERTS_SITE_URL", ""),
        )

    def missing_for_send(self):
        missing = []
        if not self.host:
            missing.append("ALERTS_SMTP_HOST")
        # Gmail refuses anonymous sends: it needs the account and an app password.
        needs_login = self.host.endswith("gmail.com")
        if needs_login and not self.user:
            missing.append("ALERTS_SMTP_USER")
        if (needs_login or self.user) and not self.password:
            missing.append("ALERTS_SMTP_PASSWORD")
        if not self.sender and "ALERTS_SMTP_USER" not in missing:
            missing.append("ALERTS_FROM")
        return missing
