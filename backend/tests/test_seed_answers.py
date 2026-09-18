import importlib.util
import re
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "seed_answers.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("seed_answers", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_todo_placeholders_are_clearly_marked():
    module = _load_module()
    for _, answer, _ in module.TODO_PLACEHOLDERS:
        assert answer.startswith("TODO:")


def test_legal_and_personal_categories_are_never_in_real_answers():
    module = _load_module()
    banned = re.compile(r"authoriz|sponsor|veteran|disab|race|ethnicity|gender|clearance|salary|compensation", re.IGNORECASE)
    for pattern, answer, _ in module.REAL_ANSWERS:
        assert not banned.search(pattern), f"legal/personal pattern leaked into REAL_ANSWERS: {pattern}"
        assert not banned.search(answer), f"legal/personal content leaked into REAL_ANSWERS: {answer}"


def test_real_answers_match_the_resume_only():
    module = _load_module()
    answers = {answer for _, answer, _ in module.REAL_ANSWERS}
    assert "Sean" in answers
    assert "Finch" in answers
    assert "alex@example.com" in answers
    assert "Example University" in answers
