"""Quelle: Stellenliste auf einer gewöhnlichen Webseite (z. B. Stellenportal einer Hochschule).

Zwei Betriebsarten:
- Mit CSS-Selektoren (item_selector, title_selector, link_selector): präzise, aber
  seitenspezifisch. Die Selektoren findet man mit den Entwicklerwerkzeugen des Browsers.
- Ohne Selektoren: Es werden alle Links der Seite genommen, deren Text nach einer
  Stellenanzeige aussieht (enthält z. B. "(m/w/d)" oder einen der Suchbegriffe).
  Das funktioniert auf vielen Portalen ohne Anpassung.
"""

from __future__ import annotations

import re
from typing import Any, Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .. import http
from ..models import Job

JOB_MARKERS = re.compile(r"\(\s*[mwfd]\s*/\s*[mwfd]\s*(/\s*[mwfdx])?\s*\)|\bm/w/d\b|\bw/m/d\b|\bd/m/w\b", re.I)


def _looks_like_job(text: str, terms: list[str]) -> bool:
    if JOB_MARKERS.search(text):
        return True
    low = text.lower()
    return any(t.lower() in low for t in terms)


def parse_page(html: str, cfg: dict[str, Any], search_terms: Iterable[str] = ()) -> list[Job]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = cfg["url"]
    name = cfg["name"]
    jobs: list[Job] = []
    seen: set[str] = set()

    def add(title: str, href: str) -> None:
        title = " ".join(title.split())
        if not title or not href or href.startswith(("mailto:", "javascript:", "#")):
            return
        url = urljoin(base_url, href)
        if url in seen:
            return
        seen.add(url)
        jobs.append(Job(source=name, source_id=url, title=title, url=url,
                        employer=cfg.get("employer", ""), location=cfg.get("location", "")))

    if cfg.get("item_selector"):
        for item in soup.select(cfg["item_selector"]):
            title_el = item.select_one(cfg["title_selector"]) if cfg.get("title_selector") else item
            link_el = item.select_one(cfg["link_selector"]) if cfg.get("link_selector") else item.find("a")
            if title_el is None or link_el is None:
                continue
            add(title_el.get_text(" "), link_el.get("href", ""))
    else:
        terms = [t for t in search_terms if t]
        for a in soup.find_all("a", href=True):
            text = a.get_text(" ")
            if len(text.strip()) >= 12 and _looks_like_job(text, terms):
                add(text, a["href"])
    return jobs


def fetch(cfg: dict[str, Any], search_terms: Iterable[str] = ()) -> list[Job]:
    resp = http.get(cfg["url"])
    return parse_page(resp.text, cfg, search_terms)
