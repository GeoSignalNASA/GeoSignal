"""
Deliver one message: through SMTP, or into alerts/outbox/ as .eml + .html
when running dry. Every subscriber gets their own message, so addresses are
never exposed to each other.
"""

import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from . import config


def build_message(settings, to_addr, subject, text, html):
    msg = EmailMessage()
    msg["From"] = settings.sender or "alerts@localhost"
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    domain = (settings.sender.split("@")[-1].strip("> ") if "@" in settings.sender else None) or "localhost"
    msg["Message-ID"] = make_msgid(domain=domain)
    msg["Auto-Submitted"] = "auto-generated"
    if settings.contact:
        msg["List-Unsubscribe"] = f"<mailto:{settings.contact}?subject=unsubscribe>"
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    return msg


def write_outbox(msg, html, stamp, outbox=None):
    outbox = outbox or config.OUTBOX_DIR
    outbox.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", msg["To"])
    eml = outbox / f"{stamp}_{safe}.eml"
    eml.write_bytes(bytes(msg))
    preview = outbox / f"{stamp}_{safe}.html"
    preview.write_text(html, encoding="utf-8")
    return eml, preview


class SmtpSession:
    """One connection reused for the whole batch."""

    def __init__(self, settings):
        self.settings = settings
        self.conn = None

    def __enter__(self):
        s = self.settings
        if s.security == "ssl":
            self.conn = smtplib.SMTP_SSL(s.host, s.port, timeout=30, context=ssl.create_default_context())
        else:
            self.conn = smtplib.SMTP(s.host, s.port, timeout=30)
            if s.security == "starttls":
                self.conn.starttls(context=ssl.create_default_context())
        if s.user:
            self.conn.login(s.user, s.password)
        return self

    def send(self, msg):
        self.conn.send_message(msg)

    def __exit__(self, *exc):
        try:
            self.conn.quit()
        except smtplib.SMTPException:
            pass
        return False
