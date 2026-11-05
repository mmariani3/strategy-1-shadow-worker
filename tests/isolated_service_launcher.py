"""Acceptance-only process launcher. Deny external HTTP; inject only the quote provider."""
import importlib
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
import uvicorn

original = requests.sessions.Session.request
def local_request(self, method, url, **kwargs):
    if urlparse(url).hostname != '127.0.0.1':
        raise RuntimeError('Acceptance process refuses external HTTP')
    return original(self, method, url, **kwargs)
requests.sessions.Session.request = local_request
module = importlib.import_module(sys.argv[1])
if sys.argv[1] == 'orchestrator':
    module.latest_alpaca_trade = lambda symbol: (Decimal('100'), datetime.now(timezone.utc).isoformat())
uvicorn.run(module.app, host='127.0.0.1', port=int(sys.argv[2]), log_level='warning', access_log=False)
