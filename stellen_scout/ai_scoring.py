"""Optionale KI-Bewertung über die Anthropic-API.

Wird nur verwendet, wenn die Umgebungsvariable ANTHROPIC_API_KEY gesetzt ist und
"ai.enabled" in der Konfiguration true ist. Bewertet werden nur die neuen Stellen mit
regelbasierter Passung "hoch" oder "mittel", damit die Kosten klein bleiben.
Die KI ändert die Punkte nicht, sie ergänzt einen kurzen Kommentar.
"""

from __future__ import annotations

import json
import os
from typing import Any

import requests

from .models import Job

API_URL = "https://api.anthropic.com/v1/messages"


def _prompt(job: Job, profile: str) -> str:
    return (
        "Bewerte in höchstens zwei Sätzen auf Deutsch, wie gut diese Stelle zum Profil passt, "
        "und nenne die größte Lücke. Antworte nur mit dem Kommentar.\n\n"
        f"PROFIL:\n{profile}\n\n"
        f"STELLE:\nTitel: {job.title}\nArbeitgeber: {job.employer}\nOrt: {job.location}\n"
        f"Beschreibung: {job.description[:1500]}"
    )


def comment_jobs(jobs: list[Job], cfg: dict[str, Any]) -> int:
    """Ergänzt ai_comment für geeignete Stellen. Gibt die Zahl der Aufrufe zurück."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not cfg.get("enabled") or not key:
        return 0
    model = cfg.get("model", "claude-haiku-5-5")
    limit = int(cfg.get("max_jobs_per_run", 15))
    profile = cfg.get("profile", "")
    calls = 0
    for job in jobs:
        if calls >= limit:
            break
        if not job.is_new or job.fit not in ("hoch", "mittel"):
            continue
        try:
            resp = requests.post(
                API_URL,
                headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                data=json.dumps({"model": model, "max_tokens": 200,
                                 "messages": [{"role": "user", "content": _prompt(job, profile)}]}),
                timeout=60,
            )
            resp.raise_for_status()
            parts = resp.json().get("content", [])
            job.ai_comment = " ".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()
        except requests.RequestException as exc:
            job.ai_comment = f"(KI-Bewertung fehlgeschlagen: {exc.__class__.__name__})"
        calls += 1
    return calls
