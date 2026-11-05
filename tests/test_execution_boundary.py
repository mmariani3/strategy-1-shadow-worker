import importlib
import execution_consumer


def test_environment_cannot_enable_phase_one_broker(monkeypatch):
    monkeypatch.setenv("EXECUTION_ENABLED","true")
    importlib.reload(execution_consumer)
    assert not execution_consumer.EXECUTION_ENABLED
    assert execution_consumer.health()["mode"]=="SHADOW"
