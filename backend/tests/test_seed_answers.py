import importlib.util
import re
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).parent.parent
SCRIPT_PATH = BACKEND_DIR / "scripts" / "seed_answers.py"
EXAMPLE_PATH = BACKEND_DIR / "answers.example.yaml"

BANNED = re.compile(r"authoriz|sponsor|veteran|disab|race|ethnicity|gender|clearance|salary|compensation", re.IGNORECASE)


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
    for pattern, answer, _ in module.load_real_answers(EXAMPLE_PATH):
        assert not BANNED.search(pattern), f"legal/personal pattern leaked into real answers: {pattern}"
        assert not BANNED.search(answer), f"legal/personal content leaked into real answers: {answer}"


def test_example_file_loads_and_every_pattern_compiles():
    module = _load_module()
    rows = module.load_real_answers(EXAMPLE_PATH)
    assert rows
    for pattern, answer, field_type in rows:
        re.compile(pattern)
        assert answer and field_type


def test_word_boundary_patterns_survive_yaml_loading():
    module = _load_module()
    patterns = {pattern for pattern, _, _ in module.load_real_answers(EXAMPLE_PATH)}
    assert r"\bemail\b" in patterns


def test_missing_local_file_exits_with_pointer_to_example(monkeypatch, tmp_path):
    module = _load_module()
    monkeypatch.setattr(module, "ANSWERS_PATH", tmp_path / "answers.local.yaml")
    with pytest.raises(SystemExit) as exc:
        module.main()
    assert "answers.example.yaml" in str(exc.value)
