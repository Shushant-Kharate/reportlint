import importlib
from fastapi.testclient import TestClient


def test_flutter_build_directory_and_legacy_redirect(tmp_path, monkeypatch):
    import app.main as main
    web = tmp_path / 'web'
    web.mkdir()
    (web / 'index.html').write_text('<title>ReportLint</title><script src="flutter_bootstrap.js"></script>')
    monkeypatch.setenv('REPORTLINT_WEB_DIR', str(web))
    try:
        client = TestClient(importlib.reload(main).app)
        assert 'flutter_bootstrap.js' in client.get('/app/').text
        assert client.get('/app/complex.html', follow_redirects=False).headers['location'] == '/app/'
    finally:
        monkeypatch.delenv('REPORTLINT_WEB_DIR')
        importlib.reload(main)


def test_browser_origins_are_explicit(tmp_path, monkeypatch):
    import app.main as main
    monkeypatch.setenv('REPORTLINT_CORS_ORIGINS', 'http://localhost:5173')
    try:
        client = TestClient(importlib.reload(main).app)
        permitted = client.options('/api/v2/templates', headers={'Origin':'http://localhost:5173','Access-Control-Request-Method':'PATCH'})
        assert permitted.headers['access-control-allow-origin'] == 'http://localhost:5173'
        refused = client.options('/api/v2/templates', headers={'Origin':'https://unrelated.example','Access-Control-Request-Method':'PATCH'})
        assert 'access-control-allow-origin' not in refused.headers
    finally:
        monkeypatch.delenv('REPORTLINT_CORS_ORIGINS')
        importlib.reload(main)
