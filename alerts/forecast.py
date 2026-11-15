"""
Rain forecast over the burn scar.

Source: Open-Meteo (free, no API key, no login). The only thing sent is
the fire centroid rounded to 2 decimals. `scenario()` builds a made-up day
instead, for demos and tests -- emails built from it are labelled as a
simulation.
"""

import datetime as dt
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


@dataclass
class DayForecast:
    date: dt.date
    rain_mm: float
    peak_mm_h: float | None = None
    peak_hour: int | None = None


def fetch_open_meteo(lat, lon, days, timeout=20):
    query = urllib.parse.urlencode({
        "latitude": round(lat, 2),
        "longitude": round(lon, 2),
        "hourly": "precipitation",
        "forecast_days": days,
        "timezone": "Europe/Madrid",
    })
    req = urllib.request.Request(f"{OPEN_METEO_URL}?{query}", headers={"User-Agent": "rain-alerts/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return parse_open_meteo(json.load(resp))


def parse_open_meteo(payload):
    """Collapse the hourly precipitation series into one entry per local day."""
    hourly = payload["hourly"]
    by_day = {}
    for stamp, mm in zip(hourly["time"], hourly["precipitation"]):
        when = dt.datetime.fromisoformat(stamp)
        by_day.setdefault(when.date(), []).append((when.hour, float(mm or 0.0)))
    days = []
    for date in sorted(by_day):
        hours = by_day[date]
        peak_hour, peak = max(hours, key=lambda item: item[1])
        days.append(DayForecast(
            date=date,
            rain_mm=round(sum(mm for _, mm in hours), 1),
            peak_mm_h=round(peak, 1),
            peak_hour=peak_hour if peak > 0 else None,
        ))
    return days


def scenario(rain_mm, date=None):
    return [DayForecast(date=date or dt.date.today(), rain_mm=float(rain_mm))]
