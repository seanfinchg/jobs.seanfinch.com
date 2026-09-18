import argparse
import logging

import yaml

from jobfinder import db, engine
from jobfinder.engine import DB_PATH


def main() -> None:
    parser = argparse.ArgumentParser(prog="jobfinder")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--profile", required=True)
    run_parser.add_argument("--questions", action="store_true")

    reclassify_parser = subparsers.add_parser(
        "reclassify", help="re-classify/re-filter already-ingested jobs against a profile's current rules, no network fetch"
    )
    reclassify_parser.add_argument("--profile", required=True)

    dashboard_parser = subparsers.add_parser("dashboard")
    dashboard_parser.add_argument(
        "--generated-at",
        help="ISO8601 timestamp to record as meta.json's generated_at, instead of the current time -- "
        "for regenerating data.json/fields.json from the already-persisted DB without implying a new "
        "scrape just happened (see docker-entrypoint.sh's deploy())",
    )

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--headless", action="store_true", help="testing only, never use for a real run")

    subparsers.add_parser("review", help="interactively triage new jobs and queue them for apply")

    profile_parser = subparsers.add_parser("profile")
    profile_subparsers = profile_parser.add_subparsers(dest="profile_command", required=True)
    profile_show_parser = profile_subparsers.add_parser(
        "show", help="print a profile's fully-merged effective filters/boards"
    )
    profile_show_parser.add_argument("name")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if args.command == "run":
        engine.run(args.profile, harvest_questions=args.questions)
    elif args.command == "reclassify":
        updated, newly_skipped = engine.reclassify(args.profile)
        print(f"reclassified {updated} job(s), newly skipped {newly_skipped} job(s) that no longer pass filters")
    elif args.command == "dashboard":
        from jobfinder import dashboard

        conn = db.connect(DB_PATH)
        dashboard.export_data(conn, generated_at=args.generated_at)
        conn.close()
        print("wrote ../frontend/public/data.json -- run `npm run build` in frontend/ to render it")
    elif args.command == "apply":
        from jobfinder import apply as apply_harness

        conn = db.connect(DB_PATH)
        apply_harness.run(conn, headless=args.headless)
        conn.close()
    elif args.command == "review":
        from jobfinder import review

        conn = db.connect(DB_PATH)
        review.run(conn)
        conn.close()
    elif args.command == "profile" and args.profile_command == "show":
        profile = engine.load_profile(args.name)
        print(yaml.safe_dump(profile, sort_keys=False))


if __name__ == "__main__":
    main()
