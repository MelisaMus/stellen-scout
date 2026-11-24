"""Quelle: Jobbörse der Bundesagentur für Arbeit.

Nutzt die öffentliche Jobsuche-Schnittstelle, wie sie die Community unter
https://github.com/bundesAPI/jobsuche-api dokumentiert. Die Bundesagentur bietet
dafür keine offizielle, garantierte API an: Pfad, Version und Feldnamen können sich
ändern. Stand November 2026 antwortet Version 6 (Version 4 liefert 403). Pfad und
Version sind konfigurierbar, und das Auslesen probiert die Feldnamen beider Versionen.
"""

from __future__ import annotations

from typing import Any, Iterable

from .. import http
from ..models import Job

SOURCE_NAME = "Bundesagentur für Arbeit"
DEFAULT_ENDPOINT = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
API_KEY_HEADER = {"X-API-Key": "jobboerse-jobsuche"}
DETAIL_URL = "https://www.arbeitsagentur.de/jobsuche/jobdetail/{refnr}"

CONTRACT = {"UNBEFRISTET": "unbefristet", "BEFRISTET": "befristet",
            "BEFRISTET_MIT_OPTION": "befristet mit Option"}
PERIOD = {"JAHRESGEHALT": "Jahr", "MONATSGEHALT": "Monat", "STUNDENLOHN": "Stunde"}


def _first(d: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        value = d.get(key)
        if value not in (None, ""):
            return value
    return default


def _euro(value: Any) -> str:
    return f"{float(value):,.0f}".replace(",", ".")


def _salary(offer: dict[str, Any]) -> str:
    low, high = offer.get("gehaltsspanneVon"), offer.get("gehaltsspanneBis")
    if not low and not high:
        return ""
    period = PERIOD.get(str(offer.get("verguetungsangabe", "")), "")
    if low and high and low != high:
        amount = f"{_euro(low)}–{_euro(high)} €"
    else:
        amount = f"{_euro(low or high)} €"
    return f"{amount} / {period}" if period else amount


def _location(offer: dict[str, Any]) -> str:
    # v6: stellenlokationen[].adresse, v4: arbeitsort
    places = offer.get("stellenlokationen")
    if isinstance(places, list) and places:
        address = places[0].get("adresse") or places[0]
    else:
        address = offer.get("arbeitsort") or {}
        if isinstance(address, list):
            address = address[0] if address else {}
    return " ".join(str(p) for p in (address.get("plz", ""), address.get("ort", "")) if p).strip()


def parse_offer(offer: dict[str, Any]) -> Job | None:
    """Wandelt einen Eintrag der API-Antwort in ein Job-Objekt um."""
    refnr = _first(offer, "referenznummer", "refnr")
    title = _first(offer, "stellenangebotsTitel", "titel", "hauptberuf", "beruf")
    if not refnr or not title:
        return None

    employer = _first(offer, "firma", "arbeitgeber", "arbeitgeberName")
    if isinstance(employer, dict):
        employer = _first(employer, "name", "arbeitgeberName")

    period = offer.get("veroeffentlichungszeitraum") or {}
    published = str(_first(period, "von") if isinstance(period, dict) else "") or str(
        _first(offer, "aktuelleVeroeffentlichungsdatum", "datumErsteVeroeffentlichung", "modifikationsTimestamp"))

    professions = offer.get("alleBerufe") or []
    description = ", ".join(dict.fromkeys([str(_first(offer, "hauptberuf", "beruf")), *map(str, professions)]))

    return Job(
        source=SOURCE_NAME,
        source_id=str(refnr),
        title=str(title).strip(),
        url=_first(offer, "externeUrl") or DETAIL_URL.format(refnr=refnr),
        employer=str(employer).strip(),
        location=_location(offer),
        published=published[:10],
        description=description.strip(", "),
        salary=_salary(offer),
        contract=CONTRACT.get(str(offer.get("vertragsdauer", "")), ""),
    )


def parse_response(data: dict[str, Any]) -> list[Job]:
    offers = data.get("ergebnisliste") or data.get("stellenangebote") or []
    jobs = [parse_offer(o) for o in offers if isinstance(o, dict)]
    return [j for j in jobs if j is not None]


def fetch(cfg: dict[str, Any], search_terms: Iterable[str]) -> list[Job]:
    """Fragt jeden Suchbegriff einzeln ab und gibt alle Treffer zurück."""
    endpoint = cfg.get("endpoint", DEFAULT_ENDPOINT)
    size = int(cfg.get("page_size", 50))
    max_pages = int(cfg.get("max_pages", 2))
    base_params = {
        "wo": cfg.get("location", "Freiburg im Breisgau"),
        "umkreis": cfg.get("radius_km", 50),
        "veroeffentlichtseit": cfg.get("published_within_days", 7),
        "angebotsart": 1,          # 1 = Arbeit (keine Ausbildung, kein Praktikum)
        "zeitarbeit": str(cfg.get("include_temp_agencies", False)).lower(),
        "size": size,
    }
    jobs: list[Job] = []
    for term in search_terms:
        for page in range(1, max_pages + 1):
            params = {**base_params, "was": term, "page": page}
            resp = http.get(endpoint, params=params, headers=API_KEY_HEADER, check_robots=False)
            data = resp.json()
            batch = parse_response(data)
            jobs.extend(batch)
            total = int(data.get("maxErgebnisse") or 0)
            if len(batch) < size or page * size >= total:
                break
    return jobs
