"""Additive public-document research collection. No strategy decisions or live-state writes."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit

from code_review import plan_bundle
from evidence_review import aware, canonical, digest, source
from public_evidence_http import FetchBlocked, public_url

VERSION = '1.0.0-source-collector'


def now():
    return datetime.now(timezone.utc).isoformat()


def implementation():
    return VERSION + ';sha256=' + digest({n:sha256(Path(__file__).with_name(n).read_bytes()).hexdigest()
        for n in ('source_collector.py', 'public_evidence_http.py')})


class TextCapture(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.title, self.published_claims = [], [], []
        self.skip, self.in_title = 0, False

    def handle_starttag(self, tag, attrs):
        if tag in ('script','style','noscript','template'):
            self.skip += 1
        if tag == 'title': self.in_title = True
        if tag in ('p','div','br','tr','td','li','h1','h2','h3'): self.parts.append('\n')
        fields = dict(attrs)
        if tag == 'meta' and (fields.get('property') or fields.get('name')) in (
                'article:published_time','article:modified_time','date','datePublished'):
            self.published_claims.append({'field': fields.get('property') or fields.get('name'),
                                          'value': fields.get('content')})

    def handle_endtag(self, tag):
        if tag in ('script','style','noscript','template'): self.skip = max(0, self.skip-1)
        if tag == 'title': self.in_title = False
        if tag in ('p','div','tr','li'): self.parts.append('\n')

    def handle_data(self, data):
        if self.in_title: self.title.append(data)
        if not self.skip: self.parts.append(data)


def extract(body, content_type):
    mime = content_type.split(';',1)[0].strip().lower()
    if mime not in ('text/html','text/plain','application/xhtml+xml'):
        raise FetchBlocked('UNSUPPORTED_CONTENT_TYPE')
    match = re.search(r'charset\s*=\s*["\']?([\w-]+)', content_type, re.I)
    encoding = match.group(1) if match else 'utf-8-sig'
    try:
        html = body.decode(encoding, errors='strict')
    except (UnicodeError, LookupError):
        raise FetchBlocked('UNSUPPORTED_OR_INVALID_ENCODING') from None
    parser = TextCapture()
    if mime == 'text/plain':
        text, title, published = html, '', []
    else:
        parser.feed(html); parser.close()
        text, title, published = ''.join(parser.parts), ''.join(parser.title).strip(), parser.published_claims
    text = '\n'.join(line for line in (re.sub(r'[\t\r \xa0]+',' ',line).strip() for line in text.splitlines()) if line)
    blocked = ('access denied', 'request rate threshold exceeded', 'verify you are human',
               'just a moment', 'enable javascript and cookies', 'sign in to continue', 'subscribe to continue')
    status = 'ACCESS_PAGE_SUSPECTED' if any(x in (title+'\n'+text[:2000]).lower() for x in blocked) else \
             'TEXT_CAPTURED_UNVERIFIED' if text.strip() else 'NO_EXTRACTABLE_TEXT'
    return dict(status=status, text=text, title=title, publication_claims=published,
                extraction_version=VERSION, completeness='NOT_ESTABLISHED')


def collection_plan(bundle, checked_at):
    plan_bundle(bundle, checked_at)  # Reject a partial/altered supplied funnel before considering URLs.
    resources, records = {}, []
    for packet in bundle['packets']:
        refs, issues = [], []
        for item in packet['sources']:
            if item['kind'] not in ('news','filing'): continue
            raw = item['raw']
            try:
                url = public_url(raw.get('url'))
                if item['kind'] == 'filing':
                    p = urlsplit(url)
                    match = re.fullmatch(r'/Archives/edgar/data/(\d+)/(\d{18})/[^/]+', p.path)
                    accession = raw.get('accession')
                    if p.hostname != 'www.sec.gov' or not match or p.query:
                        raise FetchBlocked('UNSUPPORTED_FILING_URL')
                    if not isinstance(accession,str) or accession.replace('-','') != match.group(2):
                        raise FetchBlocked('FILING_ACCESSION_MISMATCH')
                key = digest(url)
                resource = resources.setdefault(key, dict(resource_id=key,url=url,bindings=[]))
                binding = dict(packet_id=packet['packet_id'],source_id=item['source_id'],
                               source_kind=item['kind'],trace=deepcopy(packet['trace']),symbol=packet['symbol'],
                               upstream_publication=raw.get('event_timestamp'),filing_date=raw.get('filing_date'))
                resource['bindings'].append(binding)
                refs.append(key)
            except (ValueError,TypeError) as exc:
                issues.append(dict(source_id=item['source_id'],code=str(exc) if isinstance(exc,FetchBlocked) else 'INVALID_URL'))
        records.append(dict(packet_id=packet['packet_id'], trace=deepcopy(packet['trace']),symbol=packet['symbol'],
            experiment_class=packet['experiment_class'],resource_ids=sorted(set(refs)),issues=issues,
            status='SOURCE_LINKS_AVAILABLE' if refs else 'SOURCE_DISCOVERY_REQUIRED'))
    plan = dict(implementation_version=implementation(),source_bundle_digest=digest(bundle),
        checked_at=checked_at,records=records,resources=sorted(resources.values(),key=lambda r:r['url']),
        total_records=len(records),unique_urls=len(resources),
        hosts=dict(Counter(urlsplit(r['url']).hostname for r in resources.values())),
        records_without_urls=sum(not r['resource_ids'] for r in records),model_calls=0,
        admission='RESEARCH_ONLY',eligible_for_handoff=False,execution_enabled=False)
    plan['plan_id']=digest(plan)
    return plan


class CaptureStore:
    """Append-only local snapshots; unique reservation per collection key and public URL."""
    def __init__(self,path):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(path,isolation_level=None,timeout=5)
        self.db.execute('pragma synchronous=FULL')
        self.db.executescript('''
          create table if not exists batches(id text primary key, policy text not null);
          create table if not exists attempts(batch text, url text, started_at text, primary key(batch,url));
          create table if not exists outcomes(batch text, url text, result text, primary key(batch,url));
          create table if not exists documents(hash text primary key, raw blob not null, extracted text not null);
        ''')
        for table in ('batches','attempts','outcomes','documents'):
            for action in ('update','delete'):
                self.db.execute(f"create trigger if not exists immutable_{table}_{action} before {action} on {table} "
                                "begin select raise(abort,'immutable'); end")

    def close(self): self.db.close()

    def start_batch(self,key,policy):
        if not isinstance(key,str) or not key.strip(): raise ValueError('COLLECTION_KEY_REQUIRED')
        self.db.execute('insert or ignore into batches values(?,?)',(key,canonical(policy)))
        if self.db.execute('select policy from batches where id=?',(key,)).fetchone()[0]!=canonical(policy):
            raise ValueError('COLLECTION_POLICY_CHANGED_USE_NEW_KEY')

    def result(self,key,url):
        row=self.db.execute('select result from outcomes where batch=? and url=?',(key,url)).fetchone()
        return json.loads(row[0]) if row else None

    def claim(self,key,url,limit):
        self.db.execute('begin immediate')
        try:
            if self.db.execute('select 1 from attempts where batch=? and url=?',(key,url)).fetchone():
                result='RESERVED'
            elif self.db.execute('select count(*) from attempts where batch=?',(key,)).fetchone()[0]>=limit:
                result='DEFERRED_FETCH_LIMIT'
            else:
                self.db.execute('insert into attempts values(?,?,?)',(key,url,now()))
                result='CLAIMED'
            self.db.execute('commit')
            return result
        except Exception:
            self.db.execute('rollback'); raise

    def latest(self,url):
        rows=self.db.execute('select result from outcomes where url=? order by rowid desc',(url,))
        for row in rows:
            result=json.loads(row[0])
            if result.get('document_hash'): return result
        return None

    def document(self,key):
        row=self.db.execute('select raw,extracted from documents where hash=?',(key,)).fetchone()
        if not row or sha256(row[0]).hexdigest()!=key: raise ValueError('CACHE_DOCUMENT_INVALID')
        return row[0],json.loads(row[1])

    def record(self,key,url,result,body=None,extracted=None):
        self.db.execute('begin immediate')
        try:
            if body is not None:
                h=sha256(body).hexdigest()
                self.db.execute('insert or ignore into documents values(?,?,?)',(h,body,canonical(extracted)))
                if self.document(h)!=(body,extracted): raise ValueError('CACHE_CONTENT_CONFLICT')
            self.db.execute('insert into outcomes values(?,?,?)',(key,url,canonical(result)))
            self.db.execute('commit')
        except Exception:
            self.db.execute('rollback'); raise


def collect(plan,store,fetcher=None,collection_key=None,max_documents=0,refresh=False,allow_hosts=()):
    if plan['plan_id']!=digest({k:v for k,v in plan.items() if k!='plan_id'}): raise ValueError('PLAN_CHANGED')
    if type(max_documents) is not int or max_documents<0: raise ValueError('DOCUMENT_LIMIT_REQUIRED')
    allowed=set(allow_hosts)
    if fetcher is not None:
        if not max_documents: raise ValueError('EXPLICIT_DOCUMENT_LIMIT_REQUIRED')
        store.start_batch(collection_key,dict(plan_id=plan['plan_id'],max_documents=max_documents,
            refresh=refresh,allow_hosts=sorted(allowed),version=implementation()))
    results=[]
    for resource in plan['resources']:
        url=resource['url']; previous=store.latest(url)
        result=store.result(collection_key,url) if fetcher else None
        if result is not None:
            if result.get('document_hash'): store.document(result['document_hash'])
            results.append(result); continue
        if previous and not refresh:
            store.document(previous['document_hash'])
            results.append(dict(previous,reuse='CACHED_SNAPSHOT_NOT_REFRESHED')); continue
        result=dict(resource_id=resource['resource_id'],url=url,status='NOT_FETCHED',
                    recorded_at=now(),document_hash=None)
        if fetcher is None:
            result['status']='NOT_FETCHED_OFFLINE'
        elif urlsplit(url).hostname not in allowed:
            result['status']='HOST_NOT_ALLOWED'
        else:
            claim=store.claim(collection_key,url,max_documents)
            if claim!='CLAIMED':
                result['status']='IN_PROGRESS_OR_INTERRUPTED' if claim=='RESERVED' else claim
            else:
                body=extracted=None
                try:
                    validators={}
                    if previous:
                        if previous.get('etag'): validators['If-None-Match']=previous['etag']
                        if previous.get('last_modified'): validators['If-Modified-Since']=previous['last_modified']
                    response=fetcher.fetch(url,validators)
                    result.update(http_status=response['status'],recorded_at=now())
                    if response['status']==304:
                        if not previous or not validators: raise FetchBlocked('UNEXPECTED_NOT_MODIFIED')
                        store.document(previous['document_hash'])
                        result.update(document_hash=previous['document_hash'],status=previous['document_status'],
                            document_status=previous['document_status'],captured_at=previous['captured_at'],
                            etag=previous.get('etag'),last_modified=previous.get('last_modified'),
                            change='NOT_MODIFIED_REVALIDATED')
                    elif response['status']==200:
                        body=response['body']; headers=response['headers']
                        extracted=extract(body,headers.get('content-type',''))
                        result.update(status=extracted['status'],document_status=extracted['status'],
                            document_hash=sha256(body).hexdigest(),captured_at=result['recorded_at'],
                            etag=headers.get('etag'),last_modified=headers.get('last-modified'),
                            change='UNCHANGED_BYTES' if previous and sha256(body).hexdigest()==previous['document_hash'] else
                                   'CHANGED_VERSION' if previous else 'FIRST_CAPTURE')
                    else:
                        result.update(status='REDIRECT_NOT_FOLLOWED' if 300<=response['status']<400 else
                            'RATE_LIMITED' if response['status']==429 else 'HTTP_UNAVAILABLE')
                except Exception as exc:
                    body=extracted=None
                    result.update(status=str(exc) if isinstance(exc,FetchBlocked) else 'FETCH_FAILED',document_hash=None)
                store.record(collection_key,url,result,body,extracted)
        results.append(result)
    report=dict(implementation_version=implementation(),plan_id=plan['plan_id'],recorded_at=now(),
        results=results,counts=dict(Counter(r['status'] for r in results)),records=deepcopy(plan['records']),
        model_calls=0,http_requests=getattr(fetcher,'http_requests',0),
        admission='RESEARCH_ONLY',eligible_for_handoff=False,execution_enabled=False,
        journal_verification='NOT_CHECKED',semantic_verification='NOT_ESTABLISHED')
    report['collection_id']=digest(report)
    return report


def derived_packets(bundle,plan,report,store):
    """New research packet IDs; original packets and recorded dates remain untouched."""
    if (plan['plan_id']!=digest({k:v for k,v in plan.items() if k!='plan_id'})
            or plan['source_bundle_digest']!=digest(bundle) or report['plan_id']!=plan['plan_id']
            or report['collection_id']!=digest({k:v for k,v in report.items() if k!='collection_id'})):
        raise ValueError('COLLECTION_BINDING_MISMATCH')
    results={r['resource_id']:r for r in report['results']}
    if len(results)!=len(report['results']) or set(results)!={r['resource_id'] for r in plan['resources']}:
        raise ValueError('COLLECTION_RESULTS_INCOMPLETE')
    packets=[]
    for original in bundle['packets']:
        p=deepcopy(original)
        additions=[]
        for resource in plan['resources']:
            bindings=[b for b in resource['bindings'] if b['packet_id']==original['packet_id']]
            result=results.get(resource['resource_id'])
            if not bindings or not result or result['status']!='TEXT_CAPTURED_UNVERIFIED': continue
            _,document=store.document(result['document_hash'])
            if (result['url']!=resource['url'] or document['status']!='TEXT_CAPTURED_UNVERIFIED'
                    or aware(result['captured_at'])>aware(report['recorded_at'])):
                raise ValueError('DOCUMENT_PROVENANCE_MISMATCH')
            raw=dict(document,requested_url=resource['url'],document_hash=result['document_hash'],
                     captured_at=result['captured_at'],last_checked_at=result['recorded_at'],
                     original_source_ids=sorted(b['source_id'] for b in bindings),
                     actual_event_time='UNRESOLVED',source_independence='UNRESOLVED',
                     available_at_original_scan='NOT_ESTABLISHED')
            additions.append(source('retrieved_document',raw,report['recorded_at']))
        if additions:
            p.update(parent_packet_id=original['packet_id'],discovery_captured_at=original['captured_at'],
                     captured_at=report['recorded_at'],collection_id=report['collection_id'],
                     collector_version=implementation())
            p['sources']=sorted(p['sources']+additions,key=lambda s:s['source_id'])
            p['gaps']=p['gaps']+['ADDED_DOCUMENTS_ARE_LATER_RESEARCH_NOT_PROSPECTIVE_EVIDENCE']
            p['packet_id']=digest({k:v for k,v in p.items() if k!='packet_id'})
        packets.append(p)
    return packets
