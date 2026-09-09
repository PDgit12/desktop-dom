import threading
import time
import json
import urllib.request
import urllib.error
import pytest

from desktop_dom.server import ThreadedHTTPServer, DesktopDomRequestHandler
from desktop_dom.app import DesktopApp
from tests.conftest import TestPlatformAdapter

class DynamicTestAdapter(TestPlatformAdapter):
    def type_text(self, node, text, clear_first=False):
        super().type_text(node, text, clear_first)
        for n in self._tree.flatten():
            if n.role == 'input':
                n.value = text

@pytest.fixture(scope='module')
def test_server():
    port = 8499
    server = ThreadedHTTPServer(('127.0.0.1', port), DesktopDomRequestHandler)
    
    # Pre-populate app_cache with a test adapter
    adapter = DynamicTestAdapter()
    test_app = DesktopApp(target='Calculator', adapter=adapter)
    DesktopDomRequestHandler.app_cache['Calculator'] = test_app
    DesktopDomRequestHandler.app_cache['Finder'] = test_app

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1) # brief wait for socket bind
    
    yield f'http://127.0.0.1:{port}'
    
    server.shutdown()
    server.server_close()

def _http_get(url: str):
    req = urllib.request.Request(url, headers={'User-Agent': 'desktop-dom-test'})
    with urllib.request.urlopen(req, timeout=3.0) as resp:
        return json.loads(resp.read().decode('utf-8'))

def _http_post(url: str, data: dict):
    body = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=body,
        headers={'Content-Type': 'application/json', 'User-Agent': 'desktop-dom-test'},
    )
    with urllib.request.urlopen(req, timeout=5.0) as resp:
        return json.loads(resp.read().decode('utf-8'))

def test_server_health(test_server):
    res = _http_get(f'{test_server}/health')
    assert res['status'] == 'healthy'
    assert res['service'] == 'desktop-dom-daemon'
    assert 'version' in res
    assert 'latency_ms' in res

def test_server_tree(test_server):
    res = _http_post(f'{test_server}/tree', {'target': 'Calculator', 'depth': 5})
    assert res['status'] == 'success'
    assert res['target'] == 'Calculator'
    assert 'tree' in res
    assert res['tree']['role'] == 'window'

def test_server_intent(test_server):
    res = _http_post(f'{test_server}/intent', {'query': 'message Josh on Outlook'})
    assert res['status'] == 'success'
    assert 'result' in res
    assert 'josh' in str(res['result']).lower()

def test_server_diff(test_server):
    res = _http_post(f'{test_server}/diff', {'target': 'Calculator'})
    assert res['status'] == 'success'
    assert 'diff' in res
    assert 'has_changes' in res['diff']

def test_server_action(test_server):
    res = _http_post(f'{test_server}/action', {
        'target': 'Calculator',
        'action': 'press',
        'key': 'cmd+s',
        'verify': False,
    })
    assert res['status'] == 'success'
    assert res['action'] == 'press'

def test_server_agent_run(test_server):
    res = _http_post(f'{test_server}/agent/run', {
        'target': 'Calculator',
        'goal': 'search for 100',
        'max_steps': 3,
        'settle_delay': 0.005,
    })
    assert res['status'] == 'success'
    assert 'result' in res
    assert res['result']['goal'] == 'search for 100'
    assert res['result']['status'] in ('completed', 'max_steps_exceeded')

def test_server_404(test_server):
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        _http_get(f'{test_server}/non_existent_route')
    assert exc_info.value.code == 404
