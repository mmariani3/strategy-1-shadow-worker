"""One stable session summary from complete, source-bound research bundles; no notifications."""
from collections import Counter
from evidence_review import digest, validate_draft


def session_summary(bundles, session_date, now):
    runs={};items={};issues=[];classes=Counter();claims=Counter()
    for bundle in bundles:
        run=bundle['run'];packets=bundle['packets'];reviews=bundle['reviews']
        if run['session_date']!=session_date:
            raise ValueError('Cross-session summary input.')
        if run['id'] in runs:
            if digest(bundle)!=runs[run['id']]:raise ValueError('Conflicting duplicate run snapshot.')
            continue
        runs[run['id']]=digest(bundle)
        if len(packets)!=run['candidates_discovered'] or len(reviews)!=len(packets):
            raise ValueError('Incomplete packet/review funnel.')
        if len({p['packet_id'] for p in packets})!=len(packets):raise ValueError('Duplicate packet.')
        by_packet={r['review']['packet_id']:r for r in reviews}
        if len(by_packet)!=len(reviews):raise ValueError('Duplicate review for a packet.')
        local_ids=set()
        for packet in packets:
            trace=packet['trace'];key=(trace['run_id'],trace['source_discovery_item_id'])
            if trace['run_id']!=run['id'] or key in local_ids:raise ValueError('Packet/run lineage mismatch.')
            if packet['session_date']!=run['session_date'] or packet['discovery_phase']!=run['phase']:
                raise ValueError('Packet/session phase mismatch.')
            local_ids.add(key)
            if packet['experiment_class']!=run['experiment_class']:raise ValueError('Classification mismatch.')
            review=by_packet.get(packet['packet_id'])
            if not review or validate_draft(packet,review['review'],now)!=review:
                raise ValueError('Review artifact validation failed.')
            items[key]=packet
            classes[packet['experiment_class']]+=1
            if packet['experiment_class']=='STRATEGY_1':
                claims.update(c['assessment'] for c in review['review']['claims'])
                issues.extend(packet['gaps'])
    strategy=[p for p in items.values() if p['experiment_class']=='STRATEGY_1']
    report={'session_date':session_date,'phase':'SHADOW','execution_enabled':False,
        'run_count':len(runs),'strategy_discovery_records':len(strategy),
        'distinct_strategy_symbols':len({p['symbol'] for p in strategy}),
        'infrastructure_records_excluded':classes['INFRASTRUCTURE_TEST'],
        'review_claims':dict(sorted(claims.items())),
        'blockers':dict(sorted(Counter(issues).items())),
        'opportunity_outcome':'UNKNOWN','confirmed_opportunity_count':None,
        'reason':'Research drafts cannot establish prospective opportunities or complete observation coverage.',
        'journal_reconciliation':'NOT_CHECKED','source_bundle_digests':sorted(runs.values())}
    report['report_id']=digest(report)
    return report


def render_summary(report):
    # Escape untrusted strings by using JSON string notation in report text; no HTML or source URLs.
    import json
    return '\n'.join([
        '# SHADOW session summary — '+report['session_date'],
        '',f"Discovery: {report['strategy_discovery_records']} records across {report['distinct_strategy_symbols']} symbols.",
        f"Infrastructure records excluded: {report['infrastructure_records_excluded']}.",
        'Opportunity outcome: UNKNOWN. Research drafts do not establish confirmed trades.',
        'Journal reconciliation: not checked by this report.',
        '', 'Review blockers:',
        *[f'- {json.dumps(k)}: {v}' for k,v in report['blockers'].items()],
        '', 'No broker execution or automatic candidate promotion.',
        'Report ID: '+report['report_id'],
    ])+'\n'
