"""Compare research claims to separately supplied source-backed reference assessments."""
from collections import Counter

from evidence_review import aware, digest, validate_draft


def compare(packet, model_artifact, reference_artifact, reference_provenance, now):
    for artifact in (model_artifact, reference_artifact):
        if validate_draft(packet, artifact['review'], now) != artifact:
            raise ValueError('Invalid review artifact.')
    required = {'assessor_id', 'method_version', 'created_before_model_response', 'independence_limitations'}
    if set(reference_provenance) != required:
        raise ValueError('Reference provenance incomplete.')
    if not reference_provenance['assessor_id'] or not reference_provenance['method_version']:
        raise ValueError('Reference assessor and method required.')
    if reference_provenance['assessor_id'] != reference_artifact['review']['reviewer_id']:
        raise ValueError('Reference assessor attribution mismatch.')
    if reference_provenance['assessor_id'] == model_artifact['review']['reviewer_id']:
        raise ValueError('Self-assessment cannot serve as an independent reference.')
    if type(reference_provenance['created_before_model_response']) is not bool:
        raise ValueError('Reference timing declaration required.')
    if reference_provenance['created_before_model_response'] and (
            aware(reference_artifact['review']['reviewed_at']) > aware(model_artifact['review']['reviewed_at'])):
        raise ValueError('Reference timing contradicts declared independence.')
    if not isinstance(reference_provenance['independence_limitations'], list):
        raise ValueError('Independence limitations must be recorded.')
    proposed = {c['criterion']: c for c in model_artifact['review']['claims']}
    expected = {c['criterion']: c for c in reference_artifact['review']['claims']}
    counts = Counter(); differences = []
    for name, label in expected.items():
        actual = proposed[name]['assessment']; target = label['assessment']
        counts['criteria'] += 1
        counts['agreement' if actual == target else 'disagreement'] += 1
        if actual == 'UNRESOLVED': counts['model_abstentions'] += 1
        if target == 'UNRESOLVED': counts['unresolved_reference'] += 1
        if actual == 'SUPPORTED' and target != 'SUPPORTED': counts['unsupported_positive_vs_reference'] += 1
        if actual != target:
            differences.append({'criterion': name, 'model': actual, 'reference': target,
                'model_rationale': proposed[name]['rationale'], 'reference_rationale': label['rationale']})
    result = {'packet_id': packet['packet_id'], 'trace': packet['trace'], 'counts': dict(counts),
        'model_artifact_id': model_artifact['review_artifact_id'],
        'reference_artifact_id': reference_artifact['review_artifact_id'],
        'reference_provenance': reference_provenance, 'differences': differences,
        'classification': 'INFRASTRUCTURE_EVALUATION', 'source_experiment_class': packet['experiment_class'],
        'independence_verification': 'NOT_ESTABLISHED_BY_SOFTWARE',
        'semantic_acceptance': 'NOT_ESTABLISHED', 'eligible_for_handoff': False,
        'reason': 'Comparison records disagreement; no strategy validation threshold or approval is inferred.'}
    result['evaluation_id'] = digest(result)
    return result


def main():
    import argparse
    import json
    from pathlib import Path
    from evidence_pipeline import write_once
    from evidence_review import canonical
    from review_attempts import utc_now
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('packet', 'model-result', 'reference', 'provenance', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    read = lambda path: json.loads(path.read_text(encoding='utf-8'))
    result = compare(read(args.packet), read(args.model_result)['review_artifact'],
                     read(args.reference), read(args.provenance), utc_now())
    path = write_once(args.output, 'evaluation-'+result['evaluation_id']+'.json', canonical(result)+'\n')
    print(json.dumps({'status': 'COMPARISON_RECORDED', 'path': str(path),
                      'counts': result['counts'], 'semantic_acceptance': 'NOT_ESTABLISHED'}))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        import json
        print(json.dumps({'status': 'BLOCKED', 'error_type': type(exc).__name__}))
        raise SystemExit(2)
