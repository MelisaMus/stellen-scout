"""Regelbasierte Bewertung der Passung zum eigenen Profil.

Punkte gibt es für Suchbegriffe im Titel (stark), im Beschreibungstext (schwach) und
für bevorzugte Arbeitgeberarten. Ausschlusswörter im Titel entfernen eine Stelle ganz.
Alle Wörter und Gewichte stehen in der Konfiguration, nicht im Code.
"""

from __future__ import annotations

from typing import Any

from .models import Job


def _hits(text: str, weights: dict[str, int]) -> list[tuple[str, int]]:
    low = (text or "").lower()
    return [(word, int(w)) for word, w in weights.items() if word.lower() in low]


def is_excluded(job: Job, cfg: dict[str, Any]) -> bool:
    title = job.title.lower()
    return any(word.lower() in title for word in cfg.get("exclude_title", []))


def score_job(job: Job, cfg: dict[str, Any]) -> Job:
    reasons: list[str] = []
    score = 0

    title_hits = _hits(job.title, cfg.get("title_keywords", {}))
    if title_hits:
        score += sum(w for _, w in title_hits)
        reasons.append("Titel: " + ", ".join(w for w, _ in title_hits))

    text_hits = _hits(job.description, cfg.get("text_keywords", {}))
    if text_hits:
        score += sum(w for _, w in text_hits)
        reasons.append("Text: " + ", ".join(w for w, _ in text_hits))

    employer_hits = _hits(job.employer, cfg.get("employer_keywords", {}))
    if employer_hits:
        score += sum(w for _, w in employer_hits)
        reasons.append("Arbeitgeber: " + ", ".join(w for w, _ in employer_hits))

    thresholds = cfg.get("thresholds", {"hoch": 6, "mittel": 3})
    if score >= thresholds["hoch"]:
        fit = "hoch"
    elif score >= thresholds["mittel"]:
        fit = "mittel"
    else:
        fit = "niedrig"

    job.score, job.fit, job.reasons = score, fit, reasons
    return job


def score_all(jobs: list[Job], cfg: dict[str, Any]) -> list[Job]:
    """Bewertet alle Stellen, entfernt ausgeschlossene und sortiert nach Punkten."""
    kept = [score_job(j, cfg) for j in jobs if not is_excluded(j, cfg)]
    min_fit = cfg.get("min_fit", "niedrig")
    order = {"hoch": 2, "mittel": 1, "niedrig": 0}
    kept = [j for j in kept if order[j.fit] >= order[min_fit]]
    return sorted(kept, key=lambda j: (-j.score, j.deadline or "9999", j.title))
