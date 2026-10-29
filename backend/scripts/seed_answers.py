"""Run once locally (`python scripts/seed_answers.py`) to populate the
answer bank. Never run in CI -- jobfinder.db is gitignored specifically
because this table holds personal data.

Your own details live in backend/answers.local.yaml (gitignored); copy
answers.example.yaml to start. Anything not stated there (work auth,
sponsorship, EEOC/demographic questions, clearance, salary expectations) is
seeded as an obvious TODO placeholder rather than guessed. apply.py treats a
"TODO:"-prefixed answer as unanswered and still stops to ask, same as a
pattern with no match at all.
"""

import sys
from pathlib import Path

import yaml

from jobfinder import db
from jobfinder.engine import DB_PATH

BACKEND_DIR = Path(__file__).resolve().parent.parent
ANSWERS_PATH = BACKEND_DIR / "answers.local.yaml"

# Drop your resume here yourself -- resume.pdf is gitignored, same reasoning
# as jobfinder.db.
RESUME_PATH = BACKEND_DIR / "resume.pdf"

RESUME_ANSWER = (r"resume|cv", str(RESUME_PATH), "input_file")


def load_real_answers(path: Path) -> list[tuple[str, str, str]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [(row["pattern"], row["answer"], row["field_type"]) for row in data.get("answers", [])]


TODO_PLACEHOLDERS = [
    (r"work authoriz|authorized to work|legally (authorized|eligible)",
     "TODO: fill in yourself -- work authorization status", "multi_value_single_select"),
    (r"sponsor(ship)?",
     "TODO: fill in yourself -- visa sponsorship needs", "multi_value_single_select"),
    (r"veteran|disab(led|ility)|race|ethnicity|gender( identity)?|sexual orientation",
     "TODO: fill in yourself -- EEOC/demographic question, optional on most forms", "multi_value_single_select"),
    (r"security clearance|ts/sci|polygraph",
     "TODO: fill in yourself -- clearance status", "multi_value_single_select"),
    (r"salary expectat|desired salary|compensation expectat",
     "TODO: fill in yourself -- salary expectations", "input_text"),
]


def main() -> None:
    if not ANSWERS_PATH.exists():
        sys.exit(f"{ANSWERS_PATH.name} not found -- copy answers.example.yaml to it and fill in your details")
    real_answers = [RESUME_ANSWER] + load_real_answers(ANSWERS_PATH)
    conn = db.connect(DB_PATH)
    for pattern, answer, field_type in real_answers + TODO_PLACEHOLDERS:
        db.seed_answer(conn, pattern, answer, field_type)
    conn.close()
    print(f"seeded {len(real_answers)} real answers and {len(TODO_PLACEHOLDERS)} TODO placeholders")


if __name__ == "__main__":
    main()
