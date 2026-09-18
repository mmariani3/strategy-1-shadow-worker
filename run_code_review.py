"""Check the full captured funnel locally. No credentials, API calls or live writes."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from code_review import plan_bundle
from evidence_pipeline import write_once
from evidence_review import canonical


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--review-slots', type=int, default=0,
                        help='Propose this many research reviews; never dispatches a request')
    parser.add_argument('--checked-at', help='Explicit timestamp for reproducible offline replay')
    args = parser.parse_args()
    bundle = json.loads(args.bundle.read_text(encoding='utf-8'))
    result = plan_bundle(bundle, args.checked_at or datetime.now(timezone.utc).isoformat(), args.review_slots)
    path = write_once(args.output, 'code-review-' + result['plan_id'] + '.json', canonical(result) + '\n')
    print(json.dumps(dict(status='CODE_CHECKS_COMPLETE_RESEARCH_UNRESOLVED', report=str(path),
        total_records=result['total_records'], counts=result['counts'], model_calls=0, external_writes=0,
        eligible_for_handoff=False)))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps(dict(status='BLOCKED', error_type=type(exc).__name__)))
        raise SystemExit(2)
