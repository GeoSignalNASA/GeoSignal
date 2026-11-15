"""
Subscriber list. Lives in alerts/subscribers.json, which is git-ignored
because it holds personal data (see subscribers.example.json for the shape).
"""

import json
import re
from dataclasses import asdict, dataclass, field

from . import config

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class Subscriber:
    email: str
    name: str = ""
    lang: str = "es"
    places: list = field(default_factory=list)
    profile: str = "resident"
    min_level: int = 1

    def validate(self, territory=None):
        if not EMAIL_RE.match(self.email):
            raise ValueError(f"not a valid email address: {self.email!r}")
        if self.lang not in config.LANGS:
            raise ValueError(f"lang must be one of {config.LANGS}, got {self.lang!r}")
        if self.profile not in config.PROFILES:
            raise ValueError(f"profile must be one of {config.PROFILES}, got {self.profile!r}")
        if self.min_level not in (1, 2, 3):
            raise ValueError("min_level must be 1 (yellow), 2 (orange) or 3 (red)")
        if territory is not None:
            unknown = [p for p in self.places if territory.find_place(p) is None]
            if unknown:
                known = ", ".join(sorted(p.name for p in territory.places.values()))
                raise ValueError(f"unknown place(s) {unknown}. Known places: {known}")
            self.places = [territory.find_place(p).name for p in self.places]
        return self


def load(path=None):
    path = path or config.SUBSCRIBERS_FILE
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Subscriber(**item).validate() for item in raw]


def save(subs, path=None):
    path = path or config.SUBSCRIBERS_FILE
    payload = [asdict(s) for s in sorted(subs, key=lambda s: s.email)]
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def upsert(subs, new):
    """Add a subscriber, or replace the entry with the same address."""
    kept = [s for s in subs if s.email.lower() != new.email.lower()]
    return kept + [new], len(kept) != len(subs)


def remove(subs, email):
    kept = [s for s in subs if s.email.lower() != email.lower()]
    return kept, len(kept) != len(subs)
