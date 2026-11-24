"""Dubletten erkennen: dieselbe Stelle erscheint oft auf mehreren Portalen,
mit leicht anderem Titel ("(m/w/d)", "Referent*in" vs. "Referentin" usw.)."""

from __future__ import annotations

import re
import unicodedata

from .models import Job

_GENDER = re.compile(r"\(\s*[a-z]{1,3}(\s*/\s*[a-z]{1,3}){1,3}\s*\)|\b[mwfd]/[mwfd](/[mwfdx])?\b", re.I)
_GENDER_SUFFIX = re.compile(r"(\*|:|_|/)?(in|innen)\b", re.I)
_LEGAL_FORMS = re.compile(r"\b(gmbh|ag|kg|e\.?\s?v|ggmbh|mbh|co|se|kgaa|adör|aör)\b\.?", re.I)
_NON_WORD = re.compile(r"[^a-z0-9äöüß ]+")
_SPACES = re.compile(r"\s+")


def _base(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    return text


def normalize_title(title: str) -> str:
    t = _base(title)
    t = _GENDER.sub(" ", t)
    t = _GENDER_SUFFIX.sub("", t)          # "referent*in" -> "referent"
    t = _NON_WORD.sub(" ", t)
    return _SPACES.sub(" ", t).strip()


def normalize_employer(employer: str) -> str:
    e = _LEGAL_FORMS.sub(" ", _base(employer))
    e = _NON_WORD.sub(" ", e)
    return _SPACES.sub(" ", e).strip()


def normalize_city(location: str) -> str:
    # PLZ und Zusätze weglassen, nur den ersten Ortsnamen behalten.
    loc = re.sub(r"\d{5}", " ", _base(location))
    loc = _NON_WORD.sub(" ", loc)
    words = loc.split()
    return words[0] if words else ""


def dedupe_key(job: Job) -> str:
    return "|".join((normalize_title(job.title), normalize_employer(job.employer), normalize_city(job.location)))


def merge_duplicates(jobs: list[Job]) -> list[Job]:
    """Fasst Stellen mit gleichem Schlüssel innerhalb eines Laufs zusammen.
    Behalten wird der Eintrag mit den meisten Angaben."""
    best: dict[str, Job] = {}
    for job in jobs:
        job.dedupe_key = dedupe_key(job)
        current = best.get(job.dedupe_key)
        if current is None or _richness(job) > _richness(current):
            best[job.dedupe_key] = job
    return list(best.values())


def _richness(job: Job) -> int:
    return sum(bool(v) for v in (job.employer, job.location, job.published, job.deadline, job.description))
