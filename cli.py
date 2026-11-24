"""Einstiegspunkt: python -m stellen_scout --config config.json"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

from . import ai_scoring, notify, report, scoring
from .dedupe import merge_duplicates
from .models import Job
from .sources import ba, html_list, rss
from .store import Store

log = logging.getLogger("stellen_scout")
DEMO_FILE = Path(__file__).parent / "demo_data.json"


def collect(cfg: dict) -> tuple[list[Job], list[str], list[str]]:
    """Fragt alle Quellen ab. Fällt eine aus, laufen die anderen weiter."""
    terms = cfg.get("search_terms", [])
    jobs: list[Job] = []
    ok: list[str] = []
    failed: list[str] = []

    ba_cfg = cfg.get("bundesagentur", {})
    if ba_cfg.get("enabled", True):
        try:
            found = ba.fetch(ba_cfg, terms)
            jobs += found
            ok.append(ba.SOURCE_NAME)
            log.info("%s: %d Treffer", ba.SOURCE_NAME, len(found))
        except Exception as exc:  # eine Quelle darf den Lauf nicht abbrechen
            failed.append(ba.SOURCE_NAME)
            log.warning("%s nicht erreichbar: %s", ba.SOURCE_NAME, exc)

    for src in cfg.get("sources", []):
        if not src.get("enabled", True):
            continue
        name = src["name"]
        try:
            if src["type"] == "rss":
                found = rss.fetch(src)
            elif src["type"] == "html":
                found = html_list.fetch(src, terms)
            else:
                raise ValueError(f"Unbekannter Quellentyp: {src['type']}")
            jobs += found
            ok.append(name)
            log.info("%s: %d Treffer", name, len(found))
        except Exception as exc:
            failed.append(name)
            log.warning("%s nicht erreichbar: %s", name, exc)
    return jobs, ok, failed


def load_demo() -> list[Job]:
    data = json.loads(DEMO_FILE.read_text(encoding="utf-8"))
    return ba.parse_response(data)


def run(cfg: dict, *, db_path: Path, out_dir: Path, demo: bool = False, send_mail: bool = True) -> dict:
    if demo:
        raw, ok, failed = load_demo(), ["Demo-Daten"], []
    else:
        raw, ok, failed = collect(cfg)

    jobs = merge_duplicates(raw)
    jobs = scoring.score_all(jobs, cfg.get("scoring", {}))

    store = Store(db_path)
    try:
        store.upsert(jobs)
        total = store.count()
    finally:
        store.close()

    ai_calls = ai_scoring.comment_jobs(jobs, cfg.get("ai", {}))

    stamp = date.today().isoformat()
    html_path = report.write_html(jobs, out_dir / f"bericht-{stamp}.html", total_in_db=total,
                                  sources_ok=ok, sources_failed=failed,
                                  show_seen=cfg.get("report", {}).get("show_already_seen", False))
    report.write_csv(jobs, out_dir / f"stellen-{stamp}.csv")
    # Feste Namen zusätzlich, damit man immer den neuesten Bericht findet.
    (out_dir / "bericht-aktuell.html").write_text(html_path.read_text(encoding="utf-8"), encoding="utf-8")

    new = [j for j in jobs if j.is_new]
    mailed = False
    if send_mail and (new or cfg.get("report", {}).get("send_when_empty", False)):
        high = sum(1 for j in new if j.fit == "hoch")
        mailed = notify.send_report(html_path, f"Stellen-Scout: {len(new)} neue Stellen, {high} hoch passend")

    summary = {"raw": len(raw), "after_dedupe_and_filter": len(jobs), "new": len(new),
               "total_in_db": total, "ai_calls": ai_calls, "mailed": mailed,
               "sources_ok": ok, "sources_failed": failed, "report": str(html_path)}
    log.info("Fertig: %s", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="stellen_scout", description="Stellenangebote sammeln, bewerten, berichten.")
    p.add_argument("--config", default="config.json", help="Pfad zur Konfiguration (Standard: config.json)")
    p.add_argument("--db", default="data/stellen.sqlite", help="Pfad zur SQLite-Datenbank")
    p.add_argument("--out", default="reports", help="Ordner für Berichte")
    p.add_argument("--demo", action="store_true", help="Mit eingebauten Beispieldaten laufen, ohne Internet")
    p.add_argument("--no-mail", action="store_true", help="Keine E-Mail senden")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")
    cfg_path = Path(args.config)
    if not cfg_path.exists():
        print(f"Konfiguration nicht gefunden: {cfg_path}. Kopiere config.example.json nach config.json.",
              file=sys.stderr)
        return 2
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    summary = run(cfg, db_path=Path(args.db), out_dir=Path(args.out), demo=args.demo, send_mail=not args.no_mail)
    # Fehlercode nur, wenn keine einzige Quelle geantwortet hat.
    return 1 if not summary["sources_ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
