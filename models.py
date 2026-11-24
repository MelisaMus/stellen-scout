"""Gemeinsames Datenmodell für Stellenangebote aus allen Quellen."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Job:
    """Ein Stellenangebot, unabhängig von der Quelle."""

    source: str                 # Name der Quelle, z. B. "Bundesagentur für Arbeit"
    source_id: str              # ID innerhalb der Quelle (oder die URL)
    title: str
    url: str
    employer: str = ""
    location: str = ""
    published: str = ""         # ISO-Datum JJJJ-MM-TT, falls bekannt
    deadline: str = ""          # Bewerbungsfrist JJJJ-MM-TT, falls bekannt
    description: str = ""       # Kurztext, falls die Quelle einen liefert
    salary: str = ""            # z. B. "55.000–75.000 € / Jahr", falls angegeben
    contract: str = ""          # z. B. "unbefristet", "befristet"
    # Wird von der Bewertung befüllt:
    score: int = 0
    fit: str = ""               # "hoch", "mittel" oder "niedrig"
    reasons: list[str] = field(default_factory=list)
    ai_comment: str = ""
    # Wird vom Speicher befüllt:
    dedupe_key: str = ""
    first_seen: str = ""
    is_new: bool = False
