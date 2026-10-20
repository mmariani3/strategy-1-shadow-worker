"""Offline I/O/time helper tests; no launch authority or hosted operations."""
from datetime import datetime, timedelta, timezone
import json
import pytest

from coordinator_desktop_launch_io import wait_for_launch_window, relay_response_file
from test_coordinator_launch_guard import tmp_path


@pytest.mark.parametrize('offset',[-60,-2,0,29])
def test_exact_not_before_wait(offset):
    t0=datetime(2026,10,19,13,tzinfo=timezone.utc); wall=[t0+timedelta(seconds=offset)]; mono=[0]
    def sleep(seconds): wall[0]+=timedelta(seconds=seconds); mono[0]+=seconds
    assert wait_for_launch_window(not_before=t0,latest_start=t0+timedelta(seconds=30),
        expires_at=t0+timedelta(minutes=15),now=lambda:wall[0],monotonic=lambda:mono[0],sleep=sleep)=={
            'launch_window_open':True}
    assert t0<=wall[0]<t0+timedelta(seconds=30)


@pytest.mark.parametrize('offset',[-61,30,31,900])
def test_wait_rejects_early_or_late_invocation(offset):
    t0=datetime(2026,10,19,13,tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        wait_for_launch_window(not_before=t0,latest_start=t0+timedelta(seconds=30),
            expires_at=t0+timedelta(minutes=15),now=lambda:t0+timedelta(seconds=offset),
            sleep=lambda _:pytest.fail('must not sleep'))


def test_clock_jump_does_not_manufacture_valid_start():
    t0=datetime(2026,10,19,13,tzinfo=timezone.utc); wall=[t0-timedelta(seconds=30)]
    def jump(_): wall[0]=t0
    with pytest.raises(ValueError):
        wait_for_launch_window(not_before=t0,latest_start=t0+timedelta(seconds=30),
            expires_at=t0+timedelta(minutes=15),now=lambda:wall[0],monotonic=lambda:0,sleep=jump)


def test_large_response_goes_through_stream_not_command_line(tmp_path):
    path=tmp_path/'response.json'
    payload={'nonce':'a'*32,'kind':'snapshot','value':{'rows':['OFFLINE_DATA']*50000}}
    path.write_text(json.dumps(payload)); received=[]
    def respond(stream): received.append(json.load(stream))
    assert relay_response_file(path,private_directory=tmp_path,responder=respond)=={'response_submitted':True}
    assert received==[payload]


def test_responder_failure_is_redacted_without_replay(tmp_path):
    path=tmp_path/'response.json'; path.write_text('{}'); count=[]
    def respond(stream):
        count.append(1); raise ValueError('INVENTED_SECRET')
    with pytest.raises(RuntimeError,match='^RESPONSE_RELAY_FAILED_CLOSED$'):
        relay_response_file(path,private_directory=tmp_path,responder=respond)
    assert count==[1] and path.read_text()=='{}'


def test_response_must_be_in_private_directory(tmp_path):
    path=tmp_path/'response.json'; path.write_text('{}')
    private=tmp_path/'private'; private.mkdir()
    with pytest.raises(RuntimeError,match='^RESPONSE_RELAY_FAILED_CLOSED$'):
        relay_response_file(path,private_directory=private,responder=lambda _:pytest.fail('must not dispatch'))
