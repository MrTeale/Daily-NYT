"""Handler tests: exercise the NYT fetch/fallback behaviour with mocked HTTP.

No poppler is needed on the test host — render_jpeg is mocked."""
import base64
from unittest import mock
import requests
import pytest

import handler

XML_403 = b'<?xml version="1.0" encoding="UTF-8"?><Error><Code>AccessDenied</Code><Message>Access Denied</Message></Error>'
FAKE_PDF = b'%PDF-1.5\n%fake\n'
FAKE_JPEG = b'\xff\xd8JPEGDATA'


def mk(status, body, ctype, content_length=True):
    r = requests.Response()
    r.status_code = status
    r._content = body
    r.headers['Content-Type'] = ctype
    if content_length:
        r.headers['Content-Length'] = str(len(body))
    return r


def router(table):
    calls = []
    def _get(url, timeout=None, **kw):
        assert timeout == handler.REQUEST_TIMEOUT
        calls.append(url)
        for frag, resp in table.items():
            if frag in url:
                return resp() if callable(resp) else resp
        raise AssertionError(f'unexpected url {url}')
    _get.calls = calls
    return _get


def dates(get):
    return [u.split('/images/')[1][:10] for u in get.calls]


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch):
    from datetime import datetime
    class FakeDT(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 8, 21, 0, 30, tzinfo=tz)   # 00:30 ET: today's scan not yet published
    monkeypatch.setattr(handler, 'datetime', FakeDT)


@pytest.fixture
def render(monkeypatch):
    m = mock.Mock(return_value=FAKE_JPEG)
    monkeypatch.setattr(handler, 'render_jpeg', m)
    return m


def test_403_today_falls_back_to_yesterday(monkeypatch, render):
    get = router({'2026/08/21': mk(403, XML_403, 'application/xml'),
                  '2026/08/20': mk(200, FAKE_PDF, 'application/pdf')})
    monkeypatch.setattr(handler.requests, 'get', get)
    resp = handler.main({}, None)
    assert dates(get) == ['2026/08/21', '2026/08/20']
    render.assert_called_once_with(FAKE_PDF)          # poppler only ever sees a real PDF
    assert resp['statusCode'] == 200
    assert resp['isBase64Encoded'] is True
    assert resp['headers']['Content-Type'] == 'image/jpeg'
    assert resp['headers']['X-NYT-Date'] == '2026-08-20'
    assert 'max-age' in resp['headers']['Cache-Control']
    assert base64.b64decode(resp['body']) == FAKE_JPEG


def test_today_available_is_served_directly(monkeypatch, render):
    get = router({'2026/08/21': mk(200, FAKE_PDF, 'application/pdf')})
    monkeypatch.setattr(handler.requests, 'get', get)
    resp = handler.main({}, None)
    assert dates(get) == ['2026/08/21']
    assert resp['headers']['X-NYT-Date'] == '2026-08-21'


def test_404_is_also_handled(monkeypatch, render):
    get = router({'2026/08/21': mk(404, b'not found', 'text/html'),
                  '2026/08/20': mk(200, FAKE_PDF, 'application/pdf')})
    monkeypatch.setattr(handler.requests, 'get', get)
    assert handler.main({}, None)['statusCode'] == 200


def test_200_with_non_pdf_body_is_skipped(monkeypatch, render):
    get = router({'2026/08/21': mk(200, b'<html>edge error page</html>', 'text/html'),
                  '2026/08/20': mk(200, FAKE_PDF, 'application/pdf')})
    monkeypatch.setattr(handler.requests, 'get', get)
    assert handler.main({}, None)['statusCode'] == 200
    render.assert_called_once_with(FAKE_PDF)


def test_truncated_download_is_skipped(monkeypatch, render):
    short = mk(200, FAKE_PDF[:8], 'application/pdf', content_length=False)
    short.headers['Content-Length'] = '3239833'
    get = router({'2026/08/21': short,
                  '2026/08/20': mk(200, FAKE_PDF, 'application/pdf')})
    monkeypatch.setattr(handler.requests, 'get', get)
    assert handler.main({}, None)['headers']['X-NYT-Date'] == '2026-08-20'


def test_all_days_unavailable_returns_503_not_crash(monkeypatch, render):
    get = router({'2026/08/': mk(403, XML_403, 'application/xml')})
    monkeypatch.setattr(handler.requests, 'get', get)
    resp = handler.main({}, None)
    render.assert_not_called()
    assert len(get.calls) == handler.MAX_LOOKBACK_DAYS + 1
    assert resp['statusCode'] == 503
    assert resp['headers']['Retry-After'] == '900'
    assert resp['headers']['Cache-Control'] == 'no-store'
    assert resp['isBase64Encoded'] is False


def test_network_timeout_falls_back(monkeypatch, render):
    def boom():
        raise requests.ConnectTimeout('boom')
    get = router({'2026/08/21': boom,
                  '2026/08/20': mk(200, FAKE_PDF, 'application/pdf')})
    monkeypatch.setattr(handler.requests, 'get', get)
    assert handler.main({}, None)['statusCode'] == 200
    assert dates(get) == ['2026/08/21', '2026/08/20']


def test_fetch_budget_stops_looping(monkeypatch, render):
    get = router({'2026/08/': mk(403, XML_403, 'application/xml')})
    monkeypatch.setattr(handler.requests, 'get', get)
    clock = iter([0.0, 0.0, 0.5, 0.5, 100.0])   # deadline calc, attempt0 check, fetch start, attempt1 check, fetch start...
    monkeypatch.setattr(handler.time, 'monotonic', lambda: next(clock, 100.0))
    resp = handler.main({}, None)
    assert resp['statusCode'] == 503
    assert len(get.calls) < handler.MAX_LOOKBACK_DAYS + 1


def test_conversion_failure_returns_500_json_not_crash(monkeypatch):
    get = router({'2026/08/21': mk(200, FAKE_PDF, 'application/pdf')})
    monkeypatch.setattr(handler.requests, 'get', get)
    from pdf2image.exceptions import PDFPageCountError
    monkeypatch.setattr(handler, 'render_jpeg', mock.Mock(side_effect=PDFPageCountError('Unable to get page count.')))
    resp = handler.main({}, None)
    assert resp['statusCode'] == 500
    assert resp['headers']['Content-Type'] == 'application/json'
    assert '2026-08-21' in resp['body']
