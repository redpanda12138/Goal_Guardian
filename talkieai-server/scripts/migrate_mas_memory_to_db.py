import argparse
import json
import os
import sys
from pathlib import Path


SERVER_ROOT = Path(__file__).resolve().parents[1]
COMMON_DIR = SERVER_ROOT / "mas" / "common"
if str(COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_DIR))

from mas_memory_store import save_json  # noqa: E402


RUNTIME_DOCUMENTS = {
    ("gra", "gra_conversations"),
    ("mma", "latest_smart_goals"),
    ("mma", "session_metadata_mock"),
    ("mma", "session_notes_mock"),
    ("mma", "weekly_smart_goals_mock"),
    ("oa", "goal_reviews"),
    ("oa", "review_schedule"),
    ("oa", "session_notes_mock"),
    ("sca", "sca_conversations"),
    ("soa", "soa_conversations"),
    ("ssa", "session_summaries"),
}


def iter_memory_files(mas_root):
    for path in sorted(mas_root.glob("*/memory/*.json")):
        if path.is_file():
            service_name = path.parents[1].name.lower()
            document_name = path.stem
            yield service_name, document_name, path


def migrate_file(service_name, document_name, path, dry_run=False):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return {
            "service": service_name,
            "document": document_name,
            "path": str(path),
            "status": "skipped",
            "reason": "invalid_json: {}".format(exc),
        }

    if not dry_run:
        save_json(service_name, document_name, payload, path)

    return {
        "service": service_name,
        "document": document_name,
        "path": str(path),
        "status": "would_import" if dry_run else "imported",
        "runtime_document": (service_name, document_name) in RUNTIME_DOCUMENTS,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Import MAS memory JSON files into the DATABASE_URL-backed store."
    )
    parser.add_argument(
        "--mas-root",
        default=str(SERVER_ROOT / "mas"),
        help="Path to the mas directory. Defaults to talkieai-server/mas.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files that would be imported without writing to the database.",
    )
    args = parser.parse_args()

    if not os.getenv("DATABASE_URL") and not args.dry_run:
        raise SystemExit("DATABASE_URL is required unless --dry-run is used.")

    mas_root = Path(args.mas_root)
    results = [
        migrate_file(service_name, document_name, path, dry_run=args.dry_run)
        for service_name, document_name, path in iter_memory_files(mas_root)
    ]

    imported = [r for r in results if r["status"] in ("imported", "would_import")]
    skipped = [r for r in results if r["status"] == "skipped"]

    for result in results:
        print(
            "{status}: {service}/{document} <- {path}{runtime_note}{reason}".format(
                status=result["status"],
                service=result["service"],
                document=result["document"],
                path=result["path"],
                runtime_note=(
                    " [runtime]"
                    if result.get("runtime_document")
                    else " [archived/not directly read by runtime]"
                ),
                reason=" ({})".format(result["reason"]) if result.get("reason") else "",
            )
        )

    print(
        "summary: {} {}, {} skipped".format(
            len(imported),
            "would be imported" if args.dry_run else "imported",
            len(skipped),
        )
    )


if __name__ == "__main__":
    main()
