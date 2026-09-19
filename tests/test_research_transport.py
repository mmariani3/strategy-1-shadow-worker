"""Offline HTTP timeout/recovery tests. No requests leave the process."""
import json

import pytest
import requests

from research_reviewer import OpenAIReviewer, ReviewBlocked
from review_attempts import AttemptLedger, execute_once
from test_evidence_review import authorities, snapshot, NOW
from test_research_reviewer import masters, prepared, response, ledger_path


@pytest.mark.parametrize('timeout', [180, 240])
def test_read_timeout_recorded_before_call_and_success_replays(monkeypatch,prepared,timeout):
    p,req=prepared;ledger=AttemptLedger(ledger_path(),1);calls=[]
    provider=OpenAIReviewer('isolated-fixture-secret',timeout)
    class Session:
        trust_env=True
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,**kwargs):
            assert self.trust_env is False
            assert kwargs['timeout']==(10,timeout) and kwargs['allow_redirects'] is False
            assert ledger.events(req['request_id'])['TRANSPORT_CONFIGURED']['payload']==provider.transport_metadata()
            assert b'isolated-fixture-secret' not in kwargs['data']
            calls.append(url)
            class Reply:
                status_code=200
                def json(self):return response(p)
            return Reply()
    monkeypatch.setattr('research_reviewer.requests.Session',Session)
    try:
        result=execute_once(ledger,p,req,provider,lambda:NOW)
        assert execute_once(ledger,p,req,provider,lambda:NOW)==result
        assert len(calls)==1
        assert 'isolated-fixture-secret' not in json.dumps(ledger.events(req['request_id']))
    finally:ledger.close()


@pytest.mark.parametrize('error', [requests.ReadTimeout,requests.ConnectTimeout,requests.ConnectionError])
def test_unknown_outcome_no_retry_even_with_larger_timeout(monkeypatch,prepared,error):
    p,req=prepared;ledger=AttemptLedger(ledger_path(),1);calls=[]
    class Session:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,*args,**kwargs):
            calls.append(kwargs['timeout'])
            raise error('isolated-fixture-secret must not be exposed')
    monkeypatch.setattr('research_reviewer.requests.Session',Session)
    try:
        with pytest.raises(ReviewBlocked,match='UNKNOWN_NO_RETRY'):
            execute_once(ledger,p,req,OpenAIReviewer('isolated-fixture-secret'),lambda:NOW)
        with pytest.raises(ReviewBlocked,match='PREVIOUS_ATTEMPT_FAILED'):
            execute_once(ledger,p,req,OpenAIReviewer('isolated-fixture-secret',240),lambda:NOW)
        assert calls==[(10,180)]
        assert ledger.events(req['request_id'])['TRANSPORT_CONFIGURED']['payload']['read_timeout_seconds']==180
        assert 'isolated-fixture-secret' not in json.dumps(ledger.events(req['request_id']))
    finally:ledger.close()


@pytest.mark.parametrize('timeout', [0,-1,True,None,1.5,'180'])
def test_invalid_read_timeout_rejected(timeout):
    with pytest.raises(ReviewBlocked,match='POSITIVE_READ_TIMEOUT'):
        OpenAIReviewer('isolated-fixture-secret',timeout)


def test_default_transport_has_no_key_in_metadata():
    provider=OpenAIReviewer('isolated-fixture-secret')
    assert provider.transport_metadata()==dict(transport_version='openai-responses-http-v2',
        connect_timeout_seconds=10,read_timeout_seconds=180,automatic_retries=False,
        allow_redirects=False,trust_environment=False)
