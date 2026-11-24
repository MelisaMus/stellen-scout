"""Höflicher HTTP-Zugriff: fester User-Agent, Timeout, Pause zwischen Abrufen,
robots.txt-Prüfung für Webseiten."""

from __future__ import annotations

import time
import urllib.robotparser
from urllib.parse import urlsplit

import requests

USER_AGENT = "StellenScout/0.1 (private Stellensuche; einmal taeglich)"
TIMEOUT = 30
PAUSE_SECONDS = 2.0

_robots_cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}
_last_request = 0.0


def _pause() -> None:
    global _last_request
    wait = PAUSE_SECONDS - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()


def allowed_by_robots(url: str) -> bool:
    """True, wenn robots.txt den Abruf erlaubt (oder keine robots.txt erreichbar ist)."""
    parts = urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}"
    if base not in _robots_cache:
        parser = urllib.robotparser.RobotFileParser()
        try:
            resp = requests.get(base + "/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
            if resp.status_code >= 400:
                _robots_cache[base] = None  # keine robots.txt: erlaubt
            else:
                parser.parse(resp.text.splitlines())
                _robots_cache[base] = parser
        except requests.RequestException:
            _robots_cache[base] = None
    parser = _robots_cache[base]
    return True if parser is None else parser.can_fetch(USER_AGENT, url)


def get(url: str, *, params: dict | None = None, headers: dict | None = None,
        check_robots: bool = True) -> requests.Response:
    """GET mit Pause, Timeout und optionaler robots.txt-Prüfung."""
    if check_robots and not allowed_by_robots(url):
        raise PermissionError(f"robots.txt verbietet den Abruf: {url}")
    _pause()
    all_headers = {"User-Agent": USER_AGENT}
    if headers:
        all_headers.update(headers)
    resp = requests.get(url, params=params, headers=all_headers, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp
