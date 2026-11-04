import inspect
import sqlite3

import pytest

from jobfinder import apply, db


class _FakeFiller:
    def __init__(self) -> None:
        self.filled: dict[str, str] = {}
        self.selected: dict[str, str] = {}
        self.files: dict[str, str] = {}

    def fill(self, selector: str, value: str) -> None:
        self.filled[selector] = value

    def select_option(self, selector: str, label: str) -> None:
        self.selected[selector] = label

    def set_input_files(self, selector: str, path: str) -> None:
        self.files[selector] = path


def _conn_with_answers() -> sqlite3.Connection:
    conn = db.connect(":memory:")
    db.seed_answer(conn, r"first name", "Sean")
    db.seed_answer(conn, r"resume", "/tmp/resume.pdf", "input_file")
    db.seed_answer(
        conn, r"authorized to work", "TODO: fill in yourself", "multi_value_single_select"
    )
    return conn


def test_fill_form_fills_known_fields_and_uploads_resume() -> None:
    conn = _conn_with_answers()
    filler = _FakeFiller()
    fields: list[apply.FormField] = [
        {
            "label": "First Name",
            "selector": "#first_name",
            "field_type": "input_text",
            "required": True,
        },
        {"label": "Resume/CV", "selector": "#resume", "field_type": "input_file", "required": True},
    ]

    unresolved = apply.fill_form(conn, fields, filler)

    assert unresolved == []
    assert filler.filled["#first_name"] == "Sean"
    assert filler.files["#resume"] == "/tmp/resume.pdf"


def test_fill_form_leaves_required_field_with_no_answer_unresolved() -> None:
    conn = _conn_with_answers()
    filler = _FakeFiller()
    fields: list[apply.FormField] = [
        {
            "label": "What is your favorite color?",
            "selector": "#color",
            "field_type": "input_text",
            "required": True,
        }
    ]

    unresolved = apply.fill_form(conn, fields, filler)

    assert unresolved == fields
    assert filler.filled == {}


def test_fill_form_treats_todo_placeholder_as_unresolved() -> None:
    conn = _conn_with_answers()
    filler = _FakeFiller()
    fields: list[apply.FormField] = [
        {
            "label": "Are you authorized to work in the US?",
            "selector": "#auth",
            "field_type": "multi_value_single_select",
            "required": True,
        }
    ]

    unresolved = apply.fill_form(conn, fields, filler)

    assert unresolved == fields


def test_optional_unanswered_field_is_not_flagged() -> None:
    conn = _conn_with_answers()
    filler = _FakeFiller()
    fields: list[apply.FormField] = [
        {
            "label": "Anything else?",
            "selector": "#other",
            "field_type": "input_text",
            "required": False,
        }
    ]

    unresolved = apply.fill_form(conn, fields, filler)

    assert unresolved == []
    assert filler.filled == {}


def test_prompt_and_save_writes_a_reusable_pattern() -> None:
    conn = db.connect(":memory:")
    field: apply.FormField = {"label": "What is your favorite color?", "field_type": "input_text"}

    value = apply.prompt_and_save(conn, field, ask=lambda _: "blue")

    assert value == "blue"
    assert apply.match_answer(conn, "What is your favorite color?") == "blue"


def test_source_never_calls_click_on_anything() -> None:
    # fill_field only ever calls .fill()/.select_option()/.set_input_files();
    # there is no .click() anywhere in this file, submit-flavored or not.
    source = inspect.getsource(apply)
    assert ".click(" not in source


def test_run_refuses_to_go_headless() -> None:
    conn = db.connect(":memory:")
    with pytest.raises(RuntimeError):
        apply.run(conn, headless=True)


def test_workday_jobs_are_routed_to_manual_open_not_autofill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = db.connect(":memory:")
    job_url = "https://acme.wd5.myworkdayjobs.com/careers/job/x/y_123"
    from jobfinder.models import RawJob

    hash_ = db.upsert_job(
        conn,
        RawJob(
            adapter="greenhouse",
            company="Acme",
            board_token="acme",
            external_id="1",
            title="Security Engineer",
            location="Boston, MA",
            url=job_url,
        ),
        profile="p",
        is_native=True,
        now="t1",
    )
    db.set_status(conn, hash_, "queued")

    opened: list[str] = []
    monkeypatch.setattr(apply, "open_for_manual_handling", opened.append)

    # if this queue needed playwright at all, this call would raise
    # ModuleNotFoundError -- it isn't installed in the test environment.
    apply.run(conn, headless=False)

    assert opened == [job_url]
