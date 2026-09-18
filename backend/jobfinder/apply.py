from __future__ import annotations

import re
import sqlite3
import webbrowser

from jobfinder import db
from jobfinder.adapters.workday import is_workday_url
from jobfinder.normalize import norm

# Every function down to run() takes a duck-typed `filler`/`page` object with
# .fill()/.select_option()/.set_input_files() -- a real Playwright Page
# satisfies that, and so does a plain test double. That's what keeps the
# field-matching logic unit-testable without a browser, per the instruction
# to never run this against a real account or a live form.


def match_answer(conn: sqlite3.Connection, label: str) -> str | None:
    row = db.get_answer(conn, norm(label))
    if row is None or db.is_placeholder_answer(row["answer"]):
        return None
    return row["answer"]


def fill_field(field: dict, value: str, filler) -> None:
    field_type = field.get("field_type", "input_text")
    selector = field["selector"]

    if field_type == "input_file":
        filler.set_input_files(selector, value)
    elif field_type in ("multi_value_single_select", "boolean"):
        filler.select_option(selector, label=value)
    else:
        filler.fill(selector, value)


def fill_form(conn: sqlite3.Connection, fields: list[dict], filler) -> list[dict]:
    """Fills every field with an answer-bank match. Returns the required
    fields that don't have one, for the caller to prompt for."""
    unresolved = []
    for field in fields:
        value = match_answer(conn, field["label"])
        if value is not None:
            fill_field(field, value, filler)
        elif field.get("required"):
            unresolved.append(field)
    return unresolved


def prompt_and_save(conn: sqlite3.Connection, field: dict, ask=input) -> str:
    value = ask(f"{field['label']} ")
    pattern = re.escape(norm(field["label"]))
    db.seed_answer(conn, pattern, value, field.get("field_type", "input_text"))
    return value


def open_for_manual_handling(url: str, opener=webbrowser.open) -> None:
    opener(url)


def discover_fields(page) -> list[dict]:
    """Generic label[for] -> input mapping. Good enough for a typical
    Greenhouse/Lever/Ashby embed; custom widgets (non-native dropdowns,
    React-controlled inputs with no real `for` association) won't be picked
    up and fall through to the manual prompt instead, which is the safe
    failure mode here.
    """
    fields = []
    for label_el in page.locator("label").all():
        label_text = label_el.inner_text().strip()
        target_id = label_el.get_attribute("for")
        if not label_text or not target_id:
            continue

        selector = f"#{target_id}"
        input_el = page.locator(selector)
        if input_el.count() == 0:
            continue

        tag = input_el.evaluate("el => el.tagName.toLowerCase()")
        input_type = input_el.evaluate("el => el.type || ''") if tag == "input" else ""
        required = bool(input_el.evaluate("el => el.required || el.getAttribute('aria-required') === 'true'"))

        if input_type == "file":
            field_type = "input_file"
        elif tag == "select":
            field_type = "multi_value_single_select"
        elif tag == "textarea":
            field_type = "textarea"
        else:
            field_type = "input_text"

        fields.append({"label": label_text, "selector": selector, "field_type": field_type, "required": required})
    return fields


def run(conn: sqlite3.Connection, *, headless: bool = False) -> None:
    if headless:
        raise RuntimeError("apply must run headed -- a human has to see the form and press submit")

    queued = db.queued_jobs(conn)
    if not queued:
        print("nothing queued")
        return

    fillable = []
    for row in queued:
        url = row["best_apply_url"] or ""
        if is_workday_url(url):
            print(f"{row['company']} is on Workday -- opening for manual handling, no autofill")
            open_for_manual_handling(url)
        else:
            fillable.append(row)

    if not fillable:
        return

    # Imported here, not at module load, so a Workday-only queue -- and every
    # test in this file -- never needs playwright installed at all.
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(user_data_dir=".jobfinder-browser-profile", headless=False)
        try:
            for row in fillable:
                page = browser.new_page()
                page.goto(row["best_apply_url"])

                fields = discover_fields(page)
                unresolved = fill_form(conn, fields, page)
                for field in unresolved:
                    value = prompt_and_save(conn, field)
                    fill_field(field, value, page)

                print(f"\a{row['company']} | {row['title']} is filled in. Review it, solve any captcha, "
                      "and press submit yourself, then come back here and press Enter.")
                input()
                db.record_application(conn, row["content_hash"], outcome="filled_pending_manual_submit")
        finally:
            browser.close()
