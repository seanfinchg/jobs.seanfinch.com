import json
from datetime import datetime
from pathlib import Path

import yaml

from jobfinder import dashboard, db
from jobfinder.models import RawJob

DASHBOARD_SRC = Path(__file__).parent.parent.parent / "frontend" / "src"

SENSITIVE_SUBSTRINGS = ["answer", "resume", "pattern", "outcome", "notes", "reasons", "submitted", "status"]


def _job(**overrides):
    base = dict(
        adapter="greenhouse", company="Acme", board_token="acme", external_id="1",
        title="Security Engineer", location="Boston, MA",
        url="https://boards.greenhouse.io/acme/jobs/1", body="secret internal notes",
    )
    base.update(overrides)
    return RawJob(**base)


def _seeded_conn():
    conn = db.connect(":memory:")
    hash_ = db.upsert_job(conn, _job(), profile="new-grad-cs", is_native=True, now="t1")
    db.seed_answer(conn, r"work authorization", "yes, US citizen")
    db.record_application(conn, hash_, outcome="submitted", notes="applied via referral")
    return conn


# What actually ends up in an exported row: PUBLIC_FIELDS minus the raw
# content_hash column (renamed to the opaque `id`), plus the two fields
# export_data() computes rather than selects directly.
EXPORTED_ROW_FIELDS = (set(dashboard.PUBLIC_FIELDS) - {"content_hash"}) | {"id", "apply_urls", "featured", "defense"}


def test_export_shape_is_the_public_allowlist_only(tmp_path):
    conn = _seeded_conn()
    out = dashboard.export_data(conn, docs_dir=tmp_path)
    data = json.loads(out.read_text())

    assert len(data) == 1
    assert set(data[0].keys()) == EXPORTED_ROW_FIELDS


def test_export_never_leaks_answers_resume_or_application_state(tmp_path):
    conn = _seeded_conn()
    out = dashboard.export_data(conn, docs_dir=tmp_path)
    blob = out.read_text().lower()

    assert "us citizen" not in blob
    assert "referral" not in blob
    assert "submitted" not in blob
    for term in SENSITIVE_SUBSTRINGS:
        assert term not in blob


def test_closed_jobs_are_excluded_from_export(tmp_path):
    conn = _seeded_conn()
    hash_ = list(db.open_jobs(conn))[0]["content_hash"]
    db.set_status(conn, hash_, "closed")

    out = dashboard.export_data(conn, docs_dir=tmp_path)
    data = json.loads(out.read_text())
    assert data == []


def test_export_writes_into_the_sibling_frontend_public_dir_by_default():
    assert dashboard.DASHBOARD_PUBLIC_DIR == Path("..") / "frontend" / "public"


def test_frontend_types_only_declare_the_public_allowlist():
    types_src = (DASHBOARD_SRC / "types.ts").read_text()
    for field in EXPORTED_ROW_FIELDS:
        assert field in types_src
    for banned in ["answer", "resume", "outcome", "notes", "reasons"]:
        assert banned not in types_src.lower()


def test_app_fetches_data_json():
    app_src = (DASHBOARD_SRC / "App.tsx").read_text()
    assert 'fetch("data.json")' in app_src


def test_export_writes_a_generated_at_timestamp_to_meta_json(tmp_path):
    conn = _seeded_conn()
    dashboard.export_data(conn, docs_dir=tmp_path)
    meta = json.loads((tmp_path / "meta.json").read_text())

    # A real, parseable ISO-8601 UTC timestamp -- not just "some string" --
    # since the frontend needs to compute a relative "last checked" label
    # from it, and a malformed value would silently break that instead of
    # raising anywhere obvious.
    parsed = datetime.fromisoformat(meta["generated_at"])
    assert parsed.tzinfo is not None


def test_export_uses_an_explicit_generated_at_instead_of_now_when_given(tmp_path):
    # A code-only redeploy (no new scrape) regenerates data.json/fields.json
    # from the already-persisted DB but must not make "jobs last updated"
    # lie about a scrape that didn't happen -- see docker-entrypoint.sh's
    # deploy(), which passes the real last-scrape timestamp through here.
    conn = _seeded_conn()
    dashboard.export_data(conn, docs_dir=tmp_path, generated_at="2026-01-01T00:00:00+00:00")
    meta = json.loads((tmp_path / "meta.json").read_text())
    assert meta["generated_at"] == "2026-01-01T00:00:00+00:00"


def test_fields_metadata_reads_label_and_subfields_from_field_yaml(tmp_path):
    fields_dir = tmp_path / "fields"
    fields_dir.mkdir()
    (fields_dir / "security.yaml").write_text(yaml.safe_dump({
        "label": "Security",
        "subfields": [{"tag": "appsec", "label": "AppSec", "pattern": "appsec"}],
    }))
    # A field with no label at all (no dashboard-facing name yet) shouldn't
    # show up in fields.json -- filters can still work for it.
    (fields_dir / "no_label.yaml").write_text(yaml.safe_dump({"filters": {}}))
    # A field with a label but no subfields key is valid too (e.g. qa.yaml).
    (fields_dir / "qa.yaml").write_text(yaml.safe_dump({"label": "QA"}))

    fields = dashboard._load_fields_metadata(fields_dir=fields_dir)
    assert fields == [
        {"slug": "qa", "label": "QA", "subfields": []},
        {"slug": "security", "label": "Security", "subfields": [{"tag": "appsec", "label": "AppSec"}]},
    ]


def test_export_writes_fields_json_alongside_data_json(tmp_path):
    conn = _seeded_conn()
    dashboard.export_data(conn, docs_dir=tmp_path)
    fields = json.loads((tmp_path / "fields.json").read_text())

    # Sourced from the real shipped profiles/fields/*.yaml (default
    # fields_dir), not the tmp fixture above -- security.yaml is one of them.
    slugs = {f["slug"] for f in fields}
    assert "security" in slugs


def test_data_json_is_compact_and_still_the_same_list_shape(tmp_path):
    conn = _seeded_conn()
    out = dashboard.export_data(conn, docs_dir=tmp_path)
    text = out.read_text()

    # The browser parses every byte of this file, so whitespace is pure cost.
    assert text == json.dumps(json.loads(text), separators=(",", ":"))
    assert isinstance(json.loads(text), list)

