"""Bericht als eigenständige HTML-Datei und als CSV."""

from __future__ import annotations

import csv
import html
from datetime import date
from pathlib import Path

from .models import Job

CSS = """
:root { --bg:#fbfaf7; --fg:#1d232a; --muted:#5b6670; --line:#e3e0d8; --card:#ffffff;
        --hoch:#1f6f5c; --mittel:#8a5a00; --niedrig:#5b6670; --accent:#2f5d8a; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#14181c; --fg:#e8e6e1; --muted:#a3acb4; --line:#2c333a; --card:#1b2026;
          --hoch:#6fcfb4; --mittel:#e8b34f; --niedrig:#a3acb4; --accent:#8fb8e6; }
}
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
       font: 15px/1.5 "Source Sans 3", "Segoe UI", system-ui, sans-serif; }
main { max-width: 1080px; margin: 0 auto; padding: 32px 16px 64px; }
h1 { font-size: 26px; margin: 0 0 4px; }
.sub { color: var(--muted); margin: 0 0 24px; }
.stats { display:flex; flex-wrap:wrap; gap:12px; margin-bottom: 28px; }
.stat { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:12px 16px; min-width:140px; }
.stat b { display:block; font-size:24px; }
.stat span { color:var(--muted); font-size:13px; }
.job { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:14px 16px; margin-bottom:10px; }
.job h2 { font-size:17px; margin:0 0 4px; }
.job h2 a { color:var(--accent); text-decoration:none; }
.job h2 a:hover { text-decoration:underline; }
.meta { color:var(--muted); font-size:14px; }
.why { font-size:13px; color:var(--muted); margin-top:6px; }
.ai { font-size:14px; margin-top:6px; }
.fit { display:inline-block; font-size:12px; font-weight:600; border:1px solid currentColor;
       border-radius:999px; padding:1px 8px; margin-right:6px; vertical-align:2px; }
.fit.hoch { color:var(--hoch); } .fit.mittel { color:var(--mittel); } .fit.niedrig { color:var(--niedrig); }
.new { font-size:12px; font-weight:600; color:var(--accent); margin-left:6px; }
h3 { font-size:15px; margin:28px 0 10px; color:var(--muted); font-weight:600; }
footer { color:var(--muted); font-size:13px; margin-top:32px; }
"""

FIT_SYMBOL = {"hoch": "●", "mittel": "▲", "niedrig": "○"}


def _de(iso: str) -> str:
    """2026-11-16 -> 16.11.2026; alles andere unverändert."""
    parts = (iso or "").split("-")
    return f"{parts[2]}.{parts[1]}.{parts[0]}" if len(parts) == 3 and len(parts[0]) == 4 else iso


def _job_html(job: Job) -> str:
    e = html.escape
    meta = " · ".join(x for x in (e(job.employer), e(job.location), e(job.salary), e(job.contract),
                                  f"veröffentlicht {e(_de(job.published))}" if job.published else "",
                                  f"Frist {e(_de(job.deadline))}" if job.deadline else "",
                                  e(job.source)) if x)
    why = f'<div class="why">Punkte {job.score}: {e("; ".join(job.reasons))}</div>' if job.reasons else ""
    ai = f'<div class="ai">{e(job.ai_comment)}</div>' if job.ai_comment else ""
    new = '<span class="new">neu</span>' if job.is_new else ""
    return (f'<article class="job"><h2><span class="fit {job.fit}" aria-label="Passung {job.fit}">'
            f'{FIT_SYMBOL.get(job.fit, "")} {job.fit}</span><a href="{e(job.url)}" rel="noopener">{e(job.title)}</a>{new}</h2>'
            f'<div class="meta">{meta}</div>{why}{ai}</article>')


def write_html(jobs: list[Job], path: str | Path, *, total_in_db: int, sources_ok: list[str],
               sources_failed: list[str], show_seen: bool = False) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    new_jobs = [j for j in jobs if j.is_new]
    seen_jobs = [j for j in jobs if not j.is_new]
    high_new = sum(1 for j in new_jobs if j.fit == "hoch")
    today = date.today().strftime("%d.%m.%Y")

    body = [f"<h1>Stellen-Scout</h1><p class='sub'>Bericht vom {today}</p>",
            "<div class='stats'>",
            f"<div class='stat'><b>{len(new_jobs)}</b><span>neue Stellen</span></div>",
            f"<div class='stat'><b>{high_new}</b><span>davon hoch passend</span></div>",
            f"<div class='stat'><b>{total_in_db}</b><span>insgesamt gespeichert</span></div>",
            "</div>"]
    if new_jobs:
        body += [_job_html(j) for j in new_jobs]
    else:
        body.append("<p>Keine neuen passenden Stellen seit dem letzten Lauf.</p>")
    if show_seen and seen_jobs:
        body.append("<h3>Bereits bekannt und weiterhin ausgeschrieben</h3>")
        body += [_job_html(j) for j in seen_jobs]

    status = f"Quellen abgefragt: {html.escape(', '.join(sources_ok) or '–')}."
    if sources_failed:
        status += f" Nicht erreichbar: {html.escape(', '.join(sources_failed))}."
    body.append(f"<footer>{status} Passung regelbasiert aus Suchbegriffen; "
                "Angaben ohne Gewähr, bitte die Originalanzeige prüfen.</footer>")

    doc = ("<!DOCTYPE html><html lang='de'><head><meta charset='utf-8'>"
           "<meta name='viewport' content='width=device-width, initial-scale=1'>"
           f"<title>Stellen-Scout {today}</title><style>{CSS}</style></head>"
           f"<body><main>{''.join(body)}</main></body></html>")
    path.write_text(doc, encoding="utf-8")
    return path


def write_csv(jobs: list[Job], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:   # utf-8-sig: Excel erkennt Umlaute
        w = csv.writer(f, delimiter=";")
        w.writerow(["neu", "Passung", "Punkte", "Titel", "Arbeitgeber", "Ort", "Gehalt", "Vertrag",
                    "Veröffentlicht", "Frist", "Quelle", "Link", "Begründung", "KI-Kommentar", "Zuerst gesehen"])
        for j in jobs:
            w.writerow(["ja" if j.is_new else "", j.fit, j.score, j.title, j.employer, j.location,
                        j.salary, j.contract, j.published, j.deadline, j.source, j.url,
                        "; ".join(j.reasons), j.ai_comment, j.first_seen])
    return path
