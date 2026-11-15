"""
Email alerts for the Calvos de Randin burn scar.

Two emails per subscriber: the study report once (what the StoryMap found,
in plain language) and a rain alert whenever the real forecast over the
burned area reaches their level. Standard library only, so it runs without
data/.venv:

    python3 -m alerts check            # what the forecast says right now
    python3 -m alerts report           # the study report, dry run -> alerts/outbox/
    python3 -m alerts run              # pending reports + alerts, dry run
    python3 -m alerts run --send       # really deliver through SMTP (what cron runs)
    python3 -m alerts serve            # the StoryMap with its "Alertas" section live

Run from the repo root (same convention as the data/ pipeline).
"""
