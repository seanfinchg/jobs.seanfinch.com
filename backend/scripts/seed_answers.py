"""Run once locally (`python scripts/seed_answers.py`) to populate the
answer bank from the resume. Never run in CI -- jobfinder.db is gitignored
specifically because this table holds personal data.

Anything not stated on the resume (work auth, sponsorship, EEOC/demographic
questions, clearance, salary expectations) is seeded as an obvious TODO
placeholder rather than guessed. apply.py treats a "TODO:"-prefixed answer as
unanswered and still stops to ask, same as a pattern with no match at all.
"""

from pathlib import Path

from jobfinder import db
from jobfinder.engine import DB_PATH

# Drop your resume here yourself -- resume.pdf is gitignored, same reasoning
# as jobfinder.db.
RESUME_PATH = Path(__file__).resolve().parent.parent / "resume.pdf"

REAL_ANSWERS = [
    (r"resume|\bcv\b", str(RESUME_PATH), "input_file"),
    (r"first name", "Sean", "input_text"),
    (r"last name", "Finch", "input_text"),
    (r"\bemail\b", "alex@example.com", "input_text"),
    (r"\bphone\b", "(555) 555-0100", "input_text"),
    (r"linkedin", "https://linkedin.com/in/example", "input_text"),
    (r"github", "https://github.com/seanfinchg", "input_text"),
    (r"(personal )?website|portfolio", "https://seanfinch.com", "input_text"),
    (r"(university|school|college)( name)?", "Example University", "input_text"),
    (r"degree", "Bachelor of Science in Computer Science", "input_text"),
    (r"major|field of study", "Computer Science", "input_text"),
    (r"graduation date|expected graduation", "May 2030", "input_text"),
    (r"current (or previous )?employer|most recent employer", "Example Corp", "input_text"),
    (r"current (or previous )?(job )?title|most recent (job )?title", "Software Engineer Intern", "input_text"),
]

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
    conn = db.connect(DB_PATH)
    for pattern, answer, field_type in REAL_ANSWERS + TODO_PLACEHOLDERS:
        db.seed_answer(conn, pattern, answer, field_type)
    conn.close()
    print(f"seeded {len(REAL_ANSWERS)} real answers and {len(TODO_PLACEHOLDERS)} TODO placeholders")


if __name__ == "__main__":
    main()
