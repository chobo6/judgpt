import pytest

from judgpt.legal_data.fetch_statutes import MissingOCError, get_oc, search_law


def test_get_oc_raises_when_env_var_missing(monkeypatch):
    monkeypatch.delenv("JUDGPT_LAW_API_OC", raising=False)
    with pytest.raises(MissingOCError):
        get_oc()


def test_get_oc_returns_env_var_when_set(monkeypatch):
    monkeypatch.setenv("JUDGPT_LAW_API_OC", "test-oc")
    assert get_oc() == "test-oc"


def test_search_law_builds_expected_url_and_parses_json(monkeypatch):
    captured_url = {}

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"LawSearch": {"totalCnt": "1"}}'

    def _fake_urlopen(url, timeout=10):
        captured_url["url"] = url
        return _FakeResponse()

    monkeypatch.setattr("judgpt.legal_data.fetch_statutes.urllib.request.urlopen", _fake_urlopen)

    result = search_law("형법", "test-oc")

    assert result == {"LawSearch": {"totalCnt": "1"}}
    assert "OC=test-oc" in captured_url["url"]
    assert "target=law" in captured_url["url"]
