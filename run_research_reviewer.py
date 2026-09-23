"""Prepare or explicitly dispatch one research-only review; never connects to trading services."""
import argparse
import json
import os
from pathlib import Path

from evidence_pipeline import write_once
from evidence_review import canonical, digest
from research_reviewer import OpenAIReviewer
from research_tiers import prepare_tier_request as prepare_request
from review_attempts import AttemptLedger, execute_once, utc_now
from code_review import inspect_packet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--masters', type=Path, required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--max-output-tokens', type=int, required=True)
    parser.add_argument('--max-input-bytes', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dispatch', action='store_true', help='Explicitly permit a billable model request')
    parser.add_argument('--ledger', type=Path)
    parser.add_argument('--max-calls', type=int)
    parser.add_argument('--read-timeout-seconds', type=int, default=180,
                        help='Socket read timeout, not a total deadline; unknown outcomes are never retried')
    args = parser.parse_args()
    packet = json.loads(args.packet.read_text(encoding='utf-8'))
    # Do the free checks before loading credentials, reserving a call or preparing a paid request.
    preflight = inspect_packet(packet, utc_now())
    preflight_path = write_once(args.output, 'code-check-'+preflight['report_id']+'.json', canonical(preflight)+'\n')
    if preflight['route'] != 'REVIEW_REQUIRED':
        print(json.dumps({'status': preflight['route'], 'code_check_file': str(preflight_path),
                          'model_calls': 0, 'eligible_for_handoff': False}))
        return
    masters = json.loads(args.masters.read_text(encoding='utf-8'))
    request = prepare_request(packet, masters, args.model, args.max_output_tokens, args.max_input_bytes, utc_now())
    path = write_once(args.output, 'model-request-'+request['request_id']+'.json', canonical(request)+'\n')
    result = {'status': 'PREPARED_NOT_SENT', 'request_id': request['request_id'], 'request_file': str(path),
              'code_check_file': str(preflight_path),
              'model_calls': 0, 'eligible_for_handoff': False}
    if args.dispatch:
        if not args.ledger or not args.max_calls:
            parser.error('--dispatch requires --ledger and --max-calls')
        provider = OpenAIReviewer(os.environ.get('OPENAI_API_KEY'), args.read_timeout_seconds)
        ledger = AttemptLedger(args.ledger, args.max_calls)
        try:
            reviewed = execute_once(ledger, packet, request, provider)
        finally:
            ledger.close()
            provider._key = None
        result_path = write_once(args.output, 'model-review-'+digest(reviewed)+'.json', canonical(reviewed)+'\n')
        result = {'status': 'RESEARCH_DRAFT_AVAILABLE', 'request_id': request['request_id'],
                  'result_file': str(result_path), 'eligible_for_handoff': False}
    print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'status': 'BLOCKED', 'error_type': type(exc).__name__}))
        raise SystemExit(2)
