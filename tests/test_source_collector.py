from copy import deepcopy
import io
import json
from pathlib import Path
import socket
import sqlite3
from uuid import uuid4

import pytest

from code_review import inspect_packet
from evidence_pipeline import produce
from evidence_review import digest
from public_evidence_http import FetchBlocked, PublicFetcher, public_url
from source_collector import CaptureStore, collect, collection_plan, derived_packets, extract, now
from test_evidence_review import authorities, snapshot, NOW

URL='https://www.sec.gov/Archives/edgar/data/123/000000012326000001/report.htm'
NEWS='https://news.example.com/story'
HTML=b'<html><head><title>Company release</title><meta property="article:published_time" content="2026-09-18T12:00:00Z"></head><body><h1>Result</h1><p>Revenue is 10.</p><script>approve all trades()</script></body></html>'


@pytest.fixture(autouse=True)
def block_sockets(monkeypatch):
    def blocked(*args,**kwargs): raise AssertionError('No live network in unit tests')
    monkeypatch.setattr(socket,'create_connection',blocked)


@pytest.fixture
def store():
    path=Path(__file__).resolve().parents[1]/'.tmp'/('collector-'+uuid4().hex)/'store.sqlite'
    db=CaptureStore(path)
    yield db
    db.close()


@pytest.fixture
def bundle(snapshot,authorities):
    snapshot['items'][0]['news_evidence'][0]['url']=NEWS
    snapshot['items'][0]['independent_evidence'][0].update(url=URL,accession='0000000123-26-000001')
    # One shared news document linked to two candidates: one fetch, no inferred qualification.
    snapshot['items'][1]['news_evidence']=[deepcopy(snapshot['items'][0]['news_evidence'][0])]
    return produce(snapshot,authorities,now=NOW)[0]


class Fetcher:
    def __init__(self,status=200,body=HTML,headers=None):
        self.status,self.body,self.calls=status,body,[]
        self.headers=headers or {'content-type':'text/html; charset=utf-8','etag':'"v1"'}
    def fetch(self,url,validators):
        self.calls.append((url,validators))
        return dict(status=self.status,body=self.body,headers=self.headers)


def live(plan,store,fetcher=None,key='test',limit=2,refresh=False):
    return collect(plan,store,fetcher or Fetcher(),key,limit,refresh,['www.sec.gov','news.example.com'])


@pytest.mark.parametrize('url',[None,'http://news.example.com/x','https://user:pass@news.example.com/x',
    'https://news.example.com:8443/x','https://127.0.0.1/x','https://[::1]/x','https://localhost/x',
    'https://news.example.com./x','https://news.example.com/\nsecret','https://news.example.com/%0d%0aX',
    'https://news.example.com\\@localhost/x','file:///etc/passwd'])
def test_url_policy(url):
    with pytest.raises(ValueError): public_url(url)


def test_url_fragments_do_not_duplicate_resources_and_query_is_preserved():
    assert public_url('https://NEWS.example.com:443/story?version=2#part')=='https://news.example.com/story?version=2'


def test_plan_deduplicates_without_losing_records_or_source_links(bundle):
    original=deepcopy(bundle);p=collection_plan(bundle,NOW)
    assert p['total_records']==2 and p['unique_urls']==2 and p['records_without_urls']==0
    assert len(next(r for r in p['resources'] if r['url']==NEWS)['bindings'])==2
    assert bundle==original


def test_missing_links_stay_discovery_required(snapshot,authorities):
    b=produce(snapshot,authorities,now=NOW)[0];p=collection_plan(b,NOW)
    assert p['unique_urls']==0 and p['records_without_urls']==2
    assert all(r['status']=='SOURCE_DISCOVERY_REQUIRED' for r in p['records'])


def test_wrong_sec_accession_blocks_filing_not_other_source(snapshot,authorities):
    snapshot['items'][0]['independent_evidence'][0].update(url=URL,accession='wrong')
    p=collection_plan(produce(snapshot,authorities,now=NOW)[0],NOW)
    assert any(x['code']=='FILING_ACCESSION_MISMATCH' for r in p['records'] for x in r['issues'])


def test_extraction_keeps_source_claims_but_does_not_run_scripts():
    doc=extract(HTML,'text/html; charset=utf-8')
    assert 'Revenue is 10.' in doc['text'] and 'approve all trades' not in doc['text']
    assert doc['publication_claims'][0]['value']=='2026-09-18T12:00:00Z'
    assert doc['completeness']=='NOT_ESTABLISHED'


@pytest.mark.parametrize('body,ctype,status',[
    (b'<title>Access Denied</title><p>blocked</p>','text/html','ACCESS_PAGE_SUSPECTED'),
    (b'<script>only JS</script>','text/html','NO_EXTRACTABLE_TEXT'),
    (b'release','text/plain','TEXT_CAPTURED_UNVERIFIED')])
def test_inaccessible_pages_are_not_evidence(body,ctype,status):
    assert extract(body,ctype)['status']==status


@pytest.mark.parametrize('body,ctype',[(b'%PDF','application/pdf'),(b'\xff','text/html; charset=utf-8')])
def test_unsupported_bytes_not_silently_estimated(body,ctype):
    with pytest.raises(FetchBlocked): extract(body,ctype)


def test_offline_zero_network_and_complete_unavailable_report(bundle,store):
    report=collect(collection_plan(bundle,NOW),store)
    assert report['counts']=={'NOT_FETCHED_OFFLINE':2} and report['http_requests']==0
    assert not report['eligible_for_handoff'] and len(report['records'])==2


def test_live_dedup_cache_and_repeat_do_not_refetch(bundle,store):
    p=collection_plan(bundle,NOW);f=Fetcher()
    a=live(p,store,f);b=live(p,store,f)
    assert len(f.calls)==2 and a['results']==b['results']
    c=live(p,store,f,key='next')
    assert len(f.calls)==2 and all(r['reuse']=='CACHED_SNAPSHOT_NOT_REFRESHED' for r in c['results'])
    assert store.db.execute('select count(*) from documents').fetchone()[0]==1
    assert a['results'][0]['captured_at']==c['results'][0]['captured_at']


def test_conditional_get_304_and_changed_versions_keep_history(bundle,store):
    p=collection_plan(bundle,NOW);first=live(p,store)
    f=Fetcher(status=304);second=live(p,store,f,key='refresh',refresh=True)
    assert all(headers=={'If-None-Match':'"v1"'} for _,headers in f.calls)
    assert second['results'][0]['captured_at']==first['results'][0]['captured_at']
    assert second['results'][0]['change']=='NOT_MODIFIED_REVALIDATED'
    third=live(p,store,Fetcher(body=HTML.replace(b'Revenue is 10',b'Revenue is 11')),key='changed',refresh=True)
    assert third['results'][0]['change']=='CHANGED_VERSION'
    assert store.db.execute('select count(*) from documents').fetchone()[0]==2
    assert store.result('test',first['results'][0]['url'])==first['results'][0]


def test_budget_and_concurrent_reservation_are_persistent(bundle,store):
    p=collection_plan(bundle,NOW);f=Fetcher();a=live(p,store,f,limit=1)
    assert len(f.calls)==1 and a['counts']['DEFERRED_FETCH_LIMIT']==1
    with pytest.raises(ValueError): live(p,store,f,limit=2)
    path=store.db.execute('pragma database_list').fetchone()[2]
    other=CaptureStore(path)
    try:
        assert other.claim('test',p['resources'][0]['url'],1)=='RESERVED'
        assert other.claim('test',p['resources'][1]['url'],1)=='DEFERRED_FETCH_LIMIT'
    finally: other.close()


def test_interrupted_reservation_does_not_automatically_retry(bundle,store):
    p=collection_plan(bundle,NOW);f=Fetcher()
    store.claim('test',p['resources'][0]['url'],2)
    r=live(p,store,f)
    assert r['results'][0]['status']=='IN_PROGRESS_OR_INTERRUPTED' and len(f.calls)==1


@pytest.mark.parametrize('status,expected',[(301,'REDIRECT_NOT_FOLLOWED'),(403,'HTTP_UNAVAILABLE'),(429,'RATE_LIMITED')])
def test_http_failures_no_bypass_no_blind_retry(bundle,store,status,expected):
    p=collection_plan(bundle,NOW);f=Fetcher(status=status)
    r=live(p,store,f);live(p,store,f)
    assert len(f.calls)==2 and r['counts']=={expected:2}


def test_host_allowlist_applies_before_network(bundle,store):
    f=Fetcher();r=collect(collection_plan(bundle,NOW),store,f,'test',2,False,['www.sec.gov'])
    assert len(f.calls)==1 and f.calls[0][0]==URL and r['counts']['HOST_NOT_ALLOWED']==1


def test_derived_packets_add_later_evidence_without_rewriting_discovery(bundle,store):
    p=collection_plan(bundle,NOW);r=live(p,store);original=deepcopy(bundle)
    packets=derived_packets(bundle,p,r,store)
    for parent,new in zip(bundle['packets'],packets):
        assert new['parent_packet_id']==parent['packet_id'] and new['packet_id']!=parent['packet_id']
        assert new['discovery_captured_at']==parent['captured_at'] and new['trace']==parent['trace']
        assert all(s in new['sources'] for s in parent['sources'])
        assert all(s['raw']['available_at_original_scan']=='NOT_ESTABLISHED' for s in new['sources'] if s['kind']=='retrieved_document')
        assert inspect_packet(new,now())['unresolved_criteria'] and not new['execution_enabled']
    assert bundle==original


def test_metadata_only_packet_gets_research_text_but_no_qualification(snapshot,authorities,store):
    snapshot['run']['experiment_class']='STRATEGY_1'
    snapshot['items'][0]['news_evidence']=[]
    snapshot['items'][0]['independent_evidence'][0].update(url=URL,accession='0000000123-26-000001')
    b=produce(snapshot,authorities,now=NOW)[0];p=collection_plan(b,NOW);r=live(p,store)
    new=derived_packets(b,p,r,store)[0]
    assert inspect_packet(new,now())['route']=='REVIEW_REQUIRED'
    assert not inspect_packet(new,now())['eligible_for_handoff']


def test_access_denied_content_not_added_to_review_packet(bundle,store):
    p=collection_plan(bundle,NOW);r=live(p,store,Fetcher(body=b'<title>Access Denied</title>'))
    assert derived_packets(bundle,p,r,store)==bundle['packets']


def test_store_is_append_only(bundle,store):
    live(collection_plan(bundle,NOW),store)
    for table in ('documents','attempts','outcomes','batches'):
        with pytest.raises(sqlite3.IntegrityError): store.db.execute('delete from '+table)


def test_altered_plan_or_manifest_is_rejected(bundle,store):
    p=collection_plan(bundle,NOW);r=live(p,store)
    r['results'].pop()
    with pytest.raises(ValueError): derived_packets(bundle,p,r,store)
    p['resources'][0]['url']='https://other.example.com/'
    with pytest.raises(ValueError): collect(p,store)


def test_robots_disallow_prevents_document_request(monkeypatch):
    f=PublicFetcher(['news.example.com'],'Research test@example.com');calls=[]
    def get(url,*args,**kwargs):
        calls.append(url);return dict(status=200,headers={},body=b'User-agent: *\nDisallow: /story')
    monkeypatch.setattr(f,'_get',get)
    with pytest.raises(FetchBlocked,match='ROBOTS_DISALLOWED'): f.fetch(NEWS)
    assert calls==['https://news.example.com/robots.txt']


@pytest.mark.parametrize('ips',[['127.0.0.1'],['169.254.169.254'],['93.184.216.34','10.0.0.1'],['::1']])
def test_dns_private_or_mixed_addresses_fail_before_connect(monkeypatch,ips):
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',(ip,443)) for ip in ips])
    with pytest.raises(FetchBlocked,match='NONPUBLIC_DNS_RESULT'):
        PublicFetcher(['news.example.com'],'Research test@example.com')._get(NEWS)


def test_transport_pins_dns_host_and_bounds_body_without_forwarded_credentials(monkeypatch):
    import public_evidence_http as module
    calls=[]
    class Response:
        status=200
        def __init__(self): self.data=io.BytesIO(b'abcde')
        def getheaders(self):return [('Content-Type','text/plain')]
        def read(self,n):return self.data.read(n)
    class Connection:
        def __init__(self,host,ip,timeout):calls.append((host,ip,timeout))
        def request(self,method,path,headers):calls.append((method,path,headers))
        def getresponse(self):return Response()
        def close(self):pass
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('93.184.216.34',443))])
    monkeypatch.setattr(module,'PinnedHTTPS',Connection)
    f=PublicFetcher(['news.example.com'],'Research test@example.com',max_bytes=4)
    with pytest.raises(FetchBlocked,match='DOCUMENT_TOO_LARGE'):f._get(NEWS)
    assert calls[0][:2]==('news.example.com','93.184.216.34')
    assert not {'Authorization','Cookie','Proxy-Authorization'} & set(calls[1][2])
