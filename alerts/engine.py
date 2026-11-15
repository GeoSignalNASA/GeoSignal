"""
Turn a rain forecast into an alert level and the numbers the email quotes.

Runoff volumes use the same formula as the web simulator
(area x rain x RUNOFF_COEFF), so 120 mm gives the same 269.021 m3 from the
burned core that chapter 07 of the StoryMap shows.
"""

import json
from dataclasses import dataclass

from . import config


@dataclass
class Assessment:
    days: list            # [(DayForecast, level)] for every forecast day
    worst: object         # the DayForecast that sets the alert level
    level: int            # 0 none, 1 yellow, 2 orange, 3 red
    runoff_burned_m3: float
    runoff_main_m3: float
    simulated: bool       # True when the rain is a made-up scenario


def _level(value, thresholds):
    if value is None:
        return 0
    return sum(1 for limit in thresholds if value >= limit)


def day_level(day):
    return max(
        _level(day.rain_mm, config.RAIN_24H_THRESHOLDS_MM),
        _level(day.peak_mm_h, config.RAIN_1H_THRESHOLDS_MM),
    )


def runoff_m3(area_m2, rain_mm):
    return area_m2 * (rain_mm / 1000.0) * config.RUNOFF_COEFF


def assess(territory, days, simulated=False):
    if not days:
        raise ValueError("forecast has no days")
    scored = [(day, day_level(day)) for day in days]
    # Highest level wins; ties go to the wetter day, then to the earlier one.
    worst, level = max(scored, key=lambda item: (item[1], item[0].rain_mm, -item[0].date.toordinal()))
    return Assessment(
        days=scored,
        worst=worst,
        level=level,
        runoff_burned_m3=runoff_m3(territory.burned_ha * 10_000, worst.rain_mm),
        runoff_main_m3=runoff_m3(territory.max_contrib_area_m2, worst.rain_mm),
        simulated=simulated,
    )


# --- de-duplication ---------------------------------------------------------
# state.json remembers the highest level already emailed to each address for
# each event date, so a cron job every few hours does not repeat itself. An
# escalation (yellow -> orange) for the same date is sent again. Under
# REPORTS_KEY it keeps the version of the study report each address received,
# so the report goes out once and again only when the data is regenerated.

REPORTS_KEY = "_reports"  # not an email address, so it cannot collide with one


def load_state(path=None):
    path = path or config.STATE_FILE
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(state, path=None):
    path = path or config.STATE_FILE
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def already_sent(state, email, date, level):
    return state.get(email, {}).get(date.isoformat(), 0) >= level


def report_due(state, email, data_version):
    return state.get(REPORTS_KEY, {}).get(email) != data_version


def mark_report(state, email, data_version):
    state.setdefault(REPORTS_KEY, {})[email] = data_version


def mark_sent(state, email, date, level, today):
    sent = state.setdefault(email, {})
    sent[date.isoformat()] = level
    for key in [k for k in sent if k < today.isoformat()]:
        del sent[key]
