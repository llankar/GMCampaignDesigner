import argparse
import json
import sys

from modules.ai.automation import EntityAutoGenerator
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate campaign entities via local AI without opening the UI.",
    )
    parser.add_argument("--entity", required=True, help="Entity slug (e.g., npcs, places, scenarios)")
    parser.add_argument("--prompt", required=True, help="Creative prompt or constraints for the AI")
    parser.add_argument("--count", type=int, default=1, help="Number of items to generate")
    parser.add_argument("--db-path", default=None, help="Optional sqlite DB path override")
    parser.add_argument("--dry-run", action="store_true", help="Print JSON to stdout without saving")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generator = EntityAutoGenerator(db_path=args.db_path)
    items = generator.generate(args.entity, args.count, args.prompt)

    if args.dry_run:
        print(json.dumps(items, indent=2, ensure_ascii=False))
        return 0

    generator.save(args.entity, items)
    print(f"Saved {len(items)} item(s) to {args.entity}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
