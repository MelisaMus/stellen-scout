import json
from pathlib import Path

import pytest

from stellen_scout import cli, scoring
from stellen_scout.dedupe import dedupe_key, merge_duplicates, normalize_title
from stellen_scout.models import Job
from stellen_scout.sources import ba, html_list, rss
from stellen_scout.store import Store

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))


# --- Quellen -------------------------------------------------------------------

def test_ba_parse_demo_response():
    jobs = cli.load_demo()
    assert len(jobs) == 7
    first = jobs[0]
    assert first.source == ba.SOURCE_NAME
    assert first.title == "Data & Reporting Specialist (m/w/d)"
    assert first.location == "79108 Freiburg im Breisgau"
    assert first.published == "2026-11-16"
    assert first.url.endswith("/jobdetail/DEMO-0001")


def test_ba_parse_v6_full_entry():
    # Aufbau wie eine echte v6-Antwort (Stand Nov. 2026), Werte fiktiv
    offer = {
        "stellenangebotsart": "ARBEIT", "stellenangebotsTitel": "Controller (m/w/d)",
        "verguetungsangabe": "JAHRESGEHALT", "artDerVerguetung": "GEHALTSSPANNE",
        "gehaltsspanneVon": 55000.0, "gehaltsspanneBis": 75000.0, "vertragsdauer": "UNBEFRISTET",
        "stellenlokationen": [{"adresse": {"plz": "79089", "ort": "Freiburg im Breisgau",
                                           "region": "BADEN_WUERTTEMBERG"}, "breite": 47.98, "laenge": 7.81}],
        "veroeffentlichungszeitraum": {"von": "2026-11-19"}, "datumErsteVeroeffentlichung": "2026-09-23",
        "hauptberuf": "Controller/in", "firma": "Beispiel AG", "referenznummer": "12345-abc-S",
        "alleBerufe": ["Controller/in", "Data-Analyst/in"],
    }
    job = ba.parse_offer(offer)
    assert job.title == "Controller (m/w/d)"
    assert job.employer == "Beispiel AG"
    assert job.location == "79089 Freiburg im Breisgau"
    assert job.published == "2026-11-19"
    assert job.salary == "55.000–75.000 € / Jahr"
    assert job.contract == "unbefristet"
    assert job.description == "Controller/in, Data-Analyst/in"
    assert job.url == "https://www.arbeitsagentur.de/jobsuche/jobdetail/12345-abc-S"


def test_ba_parse_response_v6_list():
    jobs = ba.parse_response({"ergebnisliste": [{"referenznummer": "1", "stellenangebotsTitel": "A"}],
                              "maxErgebnisse": 1})
    assert [j.source_id for j in jobs] == ["1"]


def test_ba_parse_tolerates_other_field_names():
    job = ba.parse_offer({"referenznummer": "X-1", "stellenangebotsTitel": "Controller (m/w/d)",
                          "arbeitgeber": {"name": "Firma"}, "arbeitsort": [{"ort": "Freiburg"}],
                          "externeUrl": "https://example.org/job/1"})
    assert job is not None
    assert (job.source_id, job.employer, job.location, job.url) == ("X-1", "Firma", "Freiburg",
                                                                  "https://example.org/job/1")


def test_ba_parse_skips_incomplete():
    assert ba.parse_offer({"titel": "ohne Nummer"}) is None


def test_rss_parse():
    xml = """<?xml version="1.0"?><rss><channel>
      <item><title>Referent Digitalisierung (m/w/d)</title><link>https://example.org/1</link>
      <guid>abc</guid><pubDate>Mon, 16 Nov 2026 08:00:00 +0100</pubDate><description>SQL und Dashboards</description></item>
      <item><title></title><link>https://example.org/leer</link></item>
    </channel></rss>"""
    jobs = rss.parse_feed(xml, {"name": "Testfeed", "employer": "Testhochschule"})
    assert len(jobs) == 1
    assert (jobs[0].source_id, jobs[0].published, jobs[0].employer) == ("abc", "2026-11-16", "Testhochschule")


def test_html_list_without_selectors_picks_job_links():
    page = """<html><body>
      <a href="/jobs/1">Data Analyst (m/w/d) im Rechenzentrum</a>
      <a href="/kontakt">Kontakt und Anfahrt zum Campus</a>
      <a href="https://example.org/jobs/2">Referentin Wissenschaftsmanagement</a>
      <a href="/jobs/1">Data Analyst (m/w/d) im Rechenzentrum</a>
      <a href="mailto:x@example.org">Bewerbung (m/w/d) per E-Mail</a>
    </body></html>"""
    jobs = html_list.parse_page(page, {"name": "Portal", "url": "https://example.org/stellen"},
                                ["Wissenschaftsmanagement"])
    assert [j.url for j in jobs] == ["https://example.org/jobs/1", "https://example.org/jobs/2"]


def test_html_list_with_selectors():
    page = """<ul><li class="job"><span class="t">Controller (w/m/d)</span><a href="a.html">mehr</a></li>
              <li class="job"><span class="t">Leitung Studierendensekretariat</span><a href="b.html">mehr</a></li></ul>"""
    cfg = {"name": "P", "url": "https://example.org/x/", "item_selector": "li.job",
           "title_selector": ".t", "link_selector": "a"}
    jobs = html_list.parse_page(page, cfg)
    assert [(j.title, j.url) for j in jobs] == [("Controller (w/m/d)", "https://example.org/x/a.html"),
                                               ("Leitung Studierendensekretariat", "https://example.org/x/b.html")]


# --- Dubletten -----------------------------------------------------------------

@pytest.mark.parametrize("a,b", [
    ("Referent*in für Controlling", "Referentin für Controlling (w/m/d)"),
    ("Koordinator/in Graduiertenkolleg", "Koordinator (m/w/d) Graduiertenkolleg"),
    ("Data Analyst (m/w/d)", "Data Analyst m/w/d"),
])
def test_normalize_title_equal(a, b):
    assert normalize_title(a) == normalize_title(b)


def test_dedupe_ignores_postcode_and_legal_form():
    a = Job("A", "1", "Controller (m/w/d)", "u1", employer="Beispiel GmbH", location="79108 Freiburg im Breisgau")
    b = Job("B", "2", "Controller (w/m/d)", "u2", employer="Beispiel", location="Freiburg")
    assert dedupe_key(a) == dedupe_key(b)


def test_merge_keeps_richest_entry():
    jobs = cli.load_demo()
    merged = merge_duplicates(jobs)
    assert len(merged) == 6   # DEMO-0002 und DEMO-0003 sind dieselbe Stelle


# --- Bewertung -----------------------------------------------------------------

def test_scoring_levels_and_exclusion():
    jobs = scoring.score_all(merge_duplicates(cli.load_demo()), CONFIG["scoring"])
    by_title = {j.title.split(" (")[0]: j for j in jobs}
    assert by_title["Data & Reporting Specialist"].fit == "hoch"
    assert by_title["Projektmanager Digitalisierung"].fit == "mittel"
    assert not any("Praktikum" in t for t in by_title)          # ausgeschlossen
    assert not any("Sachbearbeiter" in t for t in by_title)     # unter min_fit
    assert [j.score for j in jobs] == sorted((j.score for j in jobs), reverse=True)


def test_scoring_reasons_name_the_hits():
    job = scoring.score_job(Job("S", "1", "Controller Forschung", "u", employer="Musterhochschule"),
                            CONFIG["scoring"])
    assert job.reasons == ["Titel: controller", "Arbeitgeber: hochschule"]
    assert job.score == 4 and job.fit == "mittel"


# --- Speicher ------------------------------------------------------------------

def test_store_marks_only_first_sighting_as_new(tmp_path):
    db = Store(tmp_path / "s.sqlite")
    job = merge_duplicates([Job("S", "1", "Controller", "u")])[0]
    db.upsert([job], today="2026-11-16")
    assert job.is_new and job.first_seen == "2026-11-16"
    again = merge_duplicates([Job("S", "1", "Controller", "u")])[0]
    db.upsert([again], today="2026-11-17")
    assert not again.is_new and again.first_seen == "2026-11-16"
    assert db.count() == 1
    db.close()


# --- Gesamtlauf ----------------------------------------------------------------

def test_demo_run_end_to_end(tmp_path):
    cfg = json.loads(json.dumps(CONFIG))
    s1 = cli.run(cfg, db_path=tmp_path / "db.sqlite", out_dir=tmp_path / "out", demo=True, send_mail=False)
    assert s1["new"] == 4 and s1["sources_failed"] == []
    html = Path(s1["report"]).read_text(encoding="utf-8")
    assert "Data &amp; Reporting Specialist" in html and "neue Stellen" in html
    assert (tmp_path / "out" / "bericht-aktuell.html").exists()
    csv_files = list((tmp_path / "out").glob("stellen-*.csv"))
    assert csv_files and "Passung" in csv_files[0].read_text(encoding="utf-8-sig")


def test_failing_source_does_not_stop_run(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("offline")
    monkeypatch.setattr(ba, "fetch", boom)
    cfg = json.loads(json.dumps(CONFIG))
    summary = cli.run(cfg, db_path=tmp_path / "db.sqlite", out_dir=tmp_path / "out", send_mail=False)
    assert summary["sources_failed"] == [ba.SOURCE_NAME]
    assert summary["new"] == 0
