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
