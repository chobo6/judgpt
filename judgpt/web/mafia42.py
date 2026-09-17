import re

import httpx
from bs4 import BeautifulSoup

REPLAY_URL_PATTERN = re.compile(r"^https://mafia42\.com/history/([a-z]{2})/([0-9a-f]{32})/?$")
CHAT_API_URL = "https://o2zj8uijbj.execute-api.ap-northeast-2.amazonaws.com/GetMafiaChat"


class ReplayImportError(Exception):
    """URL이 패턴에 안 맞거나, fetch/파싱에 실패하거나, 채팅이 0건일 때.
    status_code(400 또는 502)를 실어서 던진다 — 웹 핸들러는 이 값을 그대로
    HTTPException의 status_code로 쓰고, str(exc)를 detail로 쓴다."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


def _parse_chat_html(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    lines: list[str] = []
    for block in soup.select("div.name-content-container"):
        nickname_el = block.select_one("div.nick-name")
        if nickname_el is None:
            continue
        nickname = nickname_el.get_text(strip=True)
        for bubble in block.select("div.chat-bubble"):
            for decoration in bubble.select("div.bubble-tail-border"):
                decoration.decompose()
            text = bubble.get_text(strip=True)
            if text:
                lines.append(f"{nickname}: {text}")
    return lines


def fetch_replay_chat_text(url: str) -> str:
    match = REPLAY_URL_PATTERN.match(url)
    if not match:
        raise ReplayImportError("올바른 마피아42 리플레이 링크가 아닙니다", status_code=400)

    lang, replay_id = match.groups()
    try:
        response = httpx.get(
            CHAT_API_URL,
            params={"id": replay_id, "lang": lang},
            headers={"Referer": "https://mafia42.com/"},
            timeout=10.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ReplayImportError(
            "리플레이를 가져오지 못했습니다. 링크를 확인해주세요", status_code=502
        ) from exc

    lines = _parse_chat_html(response.text)
    if not lines:
        raise ReplayImportError(
            "리플레이를 가져오지 못했습니다. 링크를 확인해주세요", status_code=502
        )
    return "\n".join(lines)
