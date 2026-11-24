"""Optionaler Versand des Berichts per E-Mail (SMTP).

Aktiv nur, wenn diese Umgebungsvariablen gesetzt sind:
SMTP_HOST, SMTP_PORT (Standard 587), SMTP_USER, SMTP_PASSWORD, MAIL_TO.
Bei Gmail ist SMTP_PASSWORD ein App-Passwort, nicht das normale Passwort.
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path


def send_report(html_path: Path, subject: str) -> bool:
    host, user = os.environ.get("SMTP_HOST"), os.environ.get("SMTP_USER")
    password, to = os.environ.get("SMTP_PASSWORD"), os.environ.get("MAIL_TO")
    if not all((host, user, password, to)):
        return False
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.set_content("Der Bericht steht im HTML-Teil dieser E-Mail.")
    msg.add_alternative(html_path.read_text(encoding="utf-8"), subtype="html")
    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587")), timeout=60) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)
    return True
