from pathlib import Path

import pytest

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "mafia42_replay_sample.html"


def test_parse_chat_html_extracts_speaker_labeled_lines():
    from judgpt.web.mafia42 import _parse_chat_html

    html = FIXTURE_PATH.read_text(encoding="utf-8")

    lines = _parse_chat_html(html)

    assert lines == [
        "케로신: 야습수배위선",
        "케로신: ㄴ",
        "케로신: 특 감",
        "케로신: ㅇ",
        "이반: 경계잠수탐",
    ]


def test_parse_chat_html_excludes_system_messages():
    from judgpt.web.mafia42 import _parse_chat_html

    html = FIXTURE_PATH.read_text(encoding="utf-8")

    lines = _parse_chat_html(html)

    assert not any("밤이 되었습니다" in line for line in lines)


def test_replay_url_pattern_matches_valid_replay_url():
    from judgpt.web.mafia42 import REPLAY_URL_PATTERN

    match = REPLAY_URL_PATTERN.match(
        "https://mafia42.com/history/kr/743e94a801dff38ddf6c159c130d5777"
    )

    assert match is not None
    assert match.groups() == ("kr", "743e94a801dff38ddf6c159c130d5777")


def test_replay_url_pattern_rejects_other_domains():
    from judgpt.web.mafia42 import REPLAY_URL_PATTERN

    match = REPLAY_URL_PATTERN.match(
        "https://evil.com/history/kr/743e94a801dff38ddf6c159c130d5777"
    )

    assert match is None


def test_replay_url_pattern_rejects_malformed_id():
    from judgpt.web.mafia42 import REPLAY_URL_PATTERN

    match = REPLAY_URL_PATTERN.match("https://mafia42.com/history/kr/not-a-valid-id")

    assert match is None


def test_fetch_replay_chat_text_returns_joined_lines(monkeypatch):
    from judgpt.web.mafia42 import fetch_replay_chat_text

    html = FIXTURE_PATH.read_text(encoding="utf-8")

    class _FakeResponse:
        text = html

        def raise_for_status(self):
            pass

    captured = {}

    def _fake_get(url, params, headers):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        return _FakeResponse()

    monkeypatch.setattr("judgpt.web.mafia42._client.get", _fake_get)

    result = fetch_replay_chat_text(
        "https://mafia42.com/history/kr/743e94a801dff38ddf6c159c130d5777"
    )

    assert result == "케로신: 야습수배위선\n케로신: ㄴ\n케로신: 특 감\n케로신: ㅇ\n이반: 경계잠수탐"
    assert captured["url"] == "https://o2zj8uijbj.execute-api.ap-northeast-2.amazonaws.com/GetMafiaChat"
    assert captured["params"] == {"id": "743e94a801dff38ddf6c159c130d5777", "lang": "kr"}
    assert captured["headers"] == {"Referer": "https://mafia42.com/"}


def test_fetch_replay_chat_text_rejects_invalid_url():
    from judgpt.web.mafia42 import ReplayImportError, fetch_replay_chat_text

    with pytest.raises(ReplayImportError) as exc_info:
        fetch_replay_chat_text("https://evil.com/not-a-replay")

    assert exc_info.value.status_code == 400


def test_fetch_replay_chat_text_raises_502_on_http_error(monkeypatch):
    import httpx

    from judgpt.web.mafia42 import ReplayImportError, fetch_replay_chat_text

    def _fake_get(url, params, headers):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr("judgpt.web.mafia42._client.get", _fake_get)

    with pytest.raises(ReplayImportError) as exc_info:
        fetch_replay_chat_text(
            "https://mafia42.com/history/kr/743e94a801dff38ddf6c159c130d5777"
        )

    assert exc_info.value.status_code == 502


def test_fetch_replay_chat_text_raises_502_when_no_chat_lines_found(monkeypatch):
    from judgpt.web.mafia42 import ReplayImportError, fetch_replay_chat_text

    class _FakeEmptyResponse:
        text = "<html><body></body></html>"

        def raise_for_status(self):
            pass

    monkeypatch.setattr("judgpt.web.mafia42._client.get", lambda *a, **k: _FakeEmptyResponse())

    with pytest.raises(ReplayImportError) as exc_info:
        fetch_replay_chat_text(
            "https://mafia42.com/history/kr/743e94a801dff38ddf6c159c130d5777"
        )

    assert exc_info.value.status_code == 502
