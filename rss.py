"""Quelle: RSS- oder Atom-Feed (viele Stellenportale bieten einen an)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from typing import Any

from .. import http
from ..models import Job

ATOM = "{http://www.w3.org/2005/Atom}"


def _date(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    try:
        return parsedate_to_datetime(text).date().isoformat()   # RSS: RFC 822
    except (TypeError, ValueError):
        return text[:10]                                          # Atom: ISO 8601


def parse_feed(xml_text: str, cfg: dict[str, Any]) -> list[Job]:
    root = ET.fromstring(xml_text)
    name = cfg["name"]
    jobs: list[Job] = []
    items = root.findall(".//item") or root.findall(f".//{ATOM}entry")
    for item in items:
        title = (item.findtext("title") or item.findtext(f"{ATOM}title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not link:
            atom_link = item.find(f"{ATOM}link")
            link = atom_link.get("href", "") if atom_link is not None else ""
        if not title or not link:
            continue
        published = _date(item.findtext("pubDate") or item.findtext(f"{ATOM}updated") or "")
        summary = item.findtext("description") or item.findtext(f"{ATOM}summary") or ""
        jobs.append(Job(
            source=name,
            source_id=(item.findtext("guid") or item.findtext(f"{ATOM}id") or link).strip(),
            title=title,
            url=link,
            employer=cfg.get("employer", ""),
            location=cfg.get("location", ""),
            published=published,
            description=summary.strip()[:500],
        ))
    return jobs


def fetch(cfg: dict[str, Any]) -> list[Job]:
    resp = http.get(cfg["url"])
    return parse_feed(resp.text, cfg)
