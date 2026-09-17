# judgpt Mafia42 Replay Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 웹 UI에 마피아42 리플레이 링크(`https://mafia42.com/history/{lang}/{id}`)를 붙여넣으면 그 리플레이의 플레이어 채팅을 자동 추출해 기존 텍스트창에 채워주는 기능을 추가한다.

**Architecture:** 새 모듈 `judgpt/web/mafia42.py`가 URL 검증 → mafia42의 내부 채팅 API(`GetMafiaChat`, Referer 헤더로만 인증) 호출 → 서버 렌더링된 HTML을 `BeautifulSoup`으로 파싱해 `"화자: 메시지"` 텍스트로 변환하는 일을 전담한다. 새 엔드포인트 `POST /api/fetch-replay`가 이 함수를 감싸 웹에 노출하고, 프론트는 받은 텍스트를 기존 textarea에 채워넣기만 한다 — 분석(`/api/analyze`)은 그대로 재사용, 손대지 않는다.

**Tech Stack:** 백엔드는 기존 `httpx`(이미 `web` extra)에 `beautifulsoup4`(신규)를 추가. 프론트는 기존 React 컴포넌트에 탭 UI만 추가, 새 라이브러리 없음.

**Spec:** `docs/superpowers/specs/2026-09-17-mafia42-replay-import-design.md`

## Global Constraints

- `judgpt/analyzer.py`, `judgpt/schema.py`, `judgpt/llm.py`, `judgpt/legal_rag.py`, `judgpt/report.py`, `judgpt/embedder.py`, `judgpt/analyze.py`, `judgpt/eval.py`의 기존 로직은 수정하지 않는다. `judgpt/web/app.py`의 기존 `/api/analyze` 핸들러도 수정하지 않는다 — 새 엔드포인트만 추가한다.
- 사용자가 준 `url`을 그대로 HTTP 요청 대상으로 쓰지 않는다 — 반드시 `REPLAY_URL_PATTERN`(`^https://mafia42\.com/history/([a-z]{2})/([0-9a-f]{32})/?$`)으로 검증 후 `lang`/`id`만 추출해 고정 호스트(`https://o2zj8uijbj.execute-api.ap-northeast-2.amazonaws.com/GetMafiaChat`) URL을 우리가 직접 조립한다(SSRF 방지).
- 마피아42 리플레이만 지원한다 — 다른 사이트로 확장하는 일반화된 "URL importer" 추상화를 만들지 않는다.
- `/api/fetch-replay`는 `chat_text`만 반환하고 분석은 하지 않는다 — `/api/analyze`를 호출하지 않는다.
- IP당 분당 5회 rate limit(`@limiter.limit("5/minute")`) 적용 — 기존 `/api/analyze`와 동일 패턴.
- 가져온 리플레이 채팅을 서버 측에 저장/로깅하지 않는다.
- 게임 시스템 메시지(`div.system`)는 분석 대상 텍스트에서 제외한다.
- 에러 응답 형식은 정확히 `{"detail": "..."}`. 400은 `"올바른 마피아42 리플레이 링크가 아닙니다"`, 502는 `"리플레이를 가져오지 못했습니다. 링크를 확인해주세요"`.

---

## File Structure

```
judgpt/
  web/
    mafia42.py                    # 신규: REPLAY_URL_PATTERN, ReplayImportError, _parse_chat_html, fetch_replay_chat_text
    dependencies.py                 # 수정: get_replay_importer() 추가
    app.py                           # 수정: POST /api/fetch-replay 엔드포인트 추가
frontend/
  src/
    api.js                            # 수정: fetchReplay() 추가
    App.jsx                            # 수정: 텍스트/링크 탭 UI 추가
tests/
  fixtures/
    mafia42_replay_sample.html          # 신규: 실제 응답에서 발췌한 대표 샘플(케로신 4줄 연속 + 이반 1줄 + system 메시지 1개)
  test_mafia42.py                        # 신규
  test_web_api.py                         # 수정: /api/fetch-replay 테스트 추가
pyproject.toml                            # 수정: web extra에 beautifulsoup4 추가
```

---

### Task 1: URL 검증 + HTML 파싱 (순수 함수)

**Files:**
- Modify: `pyproject.toml`
- Create: `judgpt/web/mafia42.py`
- Create: `tests/fixtures/mafia42_replay_sample.html`
- Test: `tests/test_mafia42.py`

**Interfaces:**
- Produces: `judgpt.web.mafia42.REPLAY_URL_PATTERN`(컴파일된 정규식, group 1=lang, group 2=id), `judgpt.web.mafia42.ReplayImportError`(Exception, `__init__(self, message: str, status_code: int)`, `self.status_code` 속성 보유), `judgpt.web.mafia42._parse_chat_html(html: str) -> list[str]`(모듈 내부용 — `"화자: 메시지"` 줄 리스트 반환, 순서 보존, system 메시지 제외)

- [ ] **Step 1: `pyproject.toml`에 `beautifulsoup4` 추가**

`web` extra 줄을 아래로 교체:

```toml
web = ["fastapi>=0.115", "uvicorn[standard]>=0.30", "slowapi>=0.1.9", "httpx>=0.27", "beautifulsoup4>=4.12"]
```

설치: `pip install -e ".[web,dev]"`

- [ ] **Step 2: `tests/fixtures/mafia42_replay_sample.html` 작성**

실제 마피아42 리플레이 응답(`GetMafiaChat` 엔드포인트)에서 발췌한 대표 샘플이다 — 화자 한 명이 연속 메시지를 보낸 경우(케로신, 4줄)와 단발성 메시지(이반, 1줄), 그리고 게임 시스템 메시지(밤이 되었습니다) 하나를 포함한다. 실제 서버가 내려주는 정확한 마크업(닫히지 않은 태그 포함)을 그대로 옮긴 것이다 — `BeautifulSoup`의 `html.parser`는 이런 약식 HTML도 관용적으로 처리한다.

```html
<!DOCTYPE html>
<html lang="kr">
<body>
<section class="display-flex table">
<div class="system center"><b>밤이 되었습니다.</b></div>
        
        
        
                
                        </div>
                    </div>
                </div>
                
                
                <div class="chat-data-container">
                    <div class="profile-container">
                        
                        <!-- sfaf -->
                        <img class="frame-img" src="https://mafia42.com/chat/frame/frame_night42_antique_mirror.png">
                        <img class="job-icon-img" src="https://mafia42.com/chat/jobs/jobthumb_mafia.png">
                    </div>
                    
                    <div class="name-content-container with-nickname">
                        <div class="nick-name">
                            케로신
                        </div>
                        <div class="chat-container display-flex flex-col">
                            <div class="with-nickname MAFIACHAT chat-bubble">
                                <div class="bubble-tail-border">
                                    <div class="bubble-tail"> </div>
                                </div>
                                
                                    야습수배위선
                                
                            </div>
        
            
        
        
                    
                <div class="MAFIACHAT chat-bubble continue">
                    
                        ㄴ
                    
                </div>
                    
        
            
        
        
                    
                <div class="MAFIACHAT chat-bubble continue">
                    
                        특 감
                    
                </div>
                    
        
            
        
        
                    
                <div class="MAFIACHAT chat-bubble continue">
                    
                        ㅇ
                    
                </div>
                    
        
            
        
        
                
                        </div>
                    </div>
                </div>
                
                
                <div class="chat-data-container">
                    <div class="profile-container">
                        
                        <!-- sfaf -->
                        <img class="frame-img" src="https://mafia42.com/chat/frame/frame_school.png">
                        <img class="job-icon-img" src="https://mafia42.com/chat/jobs/jobthumb_agent.png">
                    </div>
                    
                    <div class="name-content-container with-nickname">
                        <div class="nick-name">
                            이반
                        </div>
                        <div class="chat-container display-flex flex-col">
                            <div class="with-nickname MEGAPHONE chat-bubble">
                                <div class="bubble-tail-border">
                                    <div class="bubble-tail"> </div>
                                </div>
                                
                                    경계잠수탐
                                
                            </div>
        
            
        
        
                
                        </div>
                    </div>
                </div>
                
                
                <div class="chat-data-container">
                    <div class="profile-container">
                        
                        <!-- sfaf -->
                        <img class="frame-img" src="https://mafia42.com/chat/frame/frame_party_dress.png">
                        <img class="job-icon-img" src="https://mafia42.com/chat/jobs/jobthumb_mafia.png">
                    </div>
                    
                    
</section>
</body>
</html>
```

- [ ] **Step 3: 실패하는 테스트 작성 — `tests/test_mafia42.py`**

```python
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
```

- [ ] **Step 4: 테스트 실행 — 실패 확인**

Run: `pytest tests/test_mafia42.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'judgpt.web.mafia42'`

- [ ] **Step 5: `judgpt/web/mafia42.py` 구현 (1단계 — URL 패턴/파싱만)**

```python
import re

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
```

- [ ] **Step 6: 테스트 실행 — 통과 확인**

Run: `pytest tests/test_mafia42.py -v`
Expected: PASS (5 passed)

- [ ] **Step 7: 커밋**

```bash
git add pyproject.toml judgpt/web/mafia42.py tests/fixtures/mafia42_replay_sample.html tests/test_mafia42.py
git commit -m "마피아42 리플레이 URL 검증 + 채팅 HTML 파싱 로직 추가"
```

---

### Task 2: 리플레이 fetch (네트워크 호출 wiring)

**Files:**
- Modify: `judgpt/web/mafia42.py`
- Test: `tests/test_mafia42.py` (파일 끝에 추가)

**Interfaces:**
- Consumes: `httpx.get`(기존 의존성), `judgpt.web.mafia42.REPLAY_URL_PATTERN`/`ReplayImportError`/`_parse_chat_html`(Task 1)
- Produces: `judgpt.web.mafia42.fetch_replay_chat_text(url: str) -> str` — 성공 시 `"\n".join(lines)`, 실패 시 `ReplayImportError` 발생(400 또는 502)

- [ ] **Step 1: 실패하는 테스트 작성 — `tests/test_mafia42.py`에 추가 (파일 끝)**

```python
def test_fetch_replay_chat_text_returns_joined_lines(monkeypatch):
    from judgpt.web.mafia42 import fetch_replay_chat_text

    html = FIXTURE_PATH.read_text(encoding="utf-8")

    class _FakeResponse:
        text = html

        def raise_for_status(self):
            pass

    captured = {}

    def _fake_get(url, params, headers, timeout):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        return _FakeResponse()

    monkeypatch.setattr("judgpt.web.mafia42.httpx.get", _fake_get)

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

    def _fake_get(url, params, headers, timeout):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr("judgpt.web.mafia42.httpx.get", _fake_get)

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

    monkeypatch.setattr("judgpt.web.mafia42.httpx.get", lambda *a, **k: _FakeEmptyResponse())

    with pytest.raises(ReplayImportError) as exc_info:
        fetch_replay_chat_text(
            "https://mafia42.com/history/kr/743e94a801dff38ddf6c159c130d5777"
        )

    assert exc_info.value.status_code == 502
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `pytest tests/test_mafia42.py -v`
Expected: FAIL with `ImportError: cannot import name 'fetch_replay_chat_text' from 'judgpt.web.mafia42'`

- [ ] **Step 3: `judgpt/web/mafia42.py` 맨 위에 `import httpx` 추가, 파일 끝에 함수 추가**

파일 맨 위(`import re` 다음 줄, `from bs4 import BeautifulSoup` 앞)에 추가:

```python
import httpx
```

파일 끝에 추가:

```python
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
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

Run: `pytest tests/test_mafia42.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: 커밋**

```bash
git add judgpt/web/mafia42.py tests/test_mafia42.py
git commit -m "마피아42 리플레이 fetch 함수(fetch_replay_chat_text) 추가"
```

---

### Task 3: `POST /api/fetch-replay` 엔드포인트

**Files:**
- Modify: `judgpt/web/dependencies.py`
- Modify: `judgpt/web/app.py`
- Test: `tests/test_web_api.py` (파일 끝에 추가)

**Interfaces:**
- Consumes: `judgpt.web.mafia42.fetch_replay_chat_text`/`ReplayImportError`(Task 1, 2)
- Produces: `judgpt.web.dependencies.get_replay_importer() -> Callable[[str], str]`, `POST /api/fetch-replay`(200: `{"chat_text": str}`, 400/502: `{"detail": str}`, 429: rate limit)

- [ ] **Step 1: `judgpt/web/dependencies.py`를 아래로 교체**

```python
from collections import OrderedDict
from typing import Callable

from judgpt import config
from judgpt.embedder import Embedder, OllamaEmbedder
from judgpt.llm import LLM, OllamaLLM
from judgpt.web.mafia42 import fetch_replay_chat_text

_REQUEST_TIMEOUT_SECONDS = 30.0

_llm: LLM | None = None
_embedder: Embedder | None = None


class CachingEmbedder:
    """embed() 결과를 텍스트별로 캐싱해 같은 텍스트를 다시 임베딩하지 않는다.

    legal_rag.enrich()는 호출마다 legal_data/cases.json의 판례를 전부 재임베딩하도록
    설계되어 있다(코퍼스가 작아 캐싱 없이 단순하게 둔 CLI 한 번 실행 전제 — 03-legal-rag-design.md §4).
    웹 서버는 같은 프로세스가 요청마다 enrich()를 반복 호출하므로, 이 레이어에서
    판례 요약처럼 반복되는 텍스트의 임베딩을 캐싱해 불필요한 Ollama 호출을 없앤다.

    ponytail: 캐시 크기를 _MAX_CACHE_SIZE로 제한한 단순 FIFO 축출이다(접근 빈도 기반
    LRU 아님). 판례 코퍼스(현재 4건)는 절대 축출되지 않지만, 요청마다 달라지는
    분석 대상 텍스트가 쌓이면 오래된 것부터 버려진다. 캐시 적중률이 중요해지면
    functools.lru_cache나 TTL 기반 캐시로 바꿀 것."""

    _MAX_CACHE_SIZE = 512

    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder
        self._cache: OrderedDict[str, list[float]] = OrderedDict()

    def embed(self, text: str) -> list[float]:
        if text in self._cache:
            self._cache.move_to_end(text)
            return self._cache[text]
        vector = self._embedder.embed(text)
        self._cache[text] = vector
        if len(self._cache) > self._MAX_CACHE_SIZE:
            self._cache.popitem(last=False)
        return vector


def get_llm() -> LLM:
    global _llm
    if _llm is None:
        _llm = OllamaLLM(
            model=config.MODEL,
            base_url=config.OLLAMA_BASE_URL,
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
    return _llm


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = CachingEmbedder(
            OllamaEmbedder(
                model=config.EMBEDDING_MODEL,
                base_url=config.OLLAMA_BASE_URL,
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
        )
    return _embedder


def get_replay_importer() -> Callable[[str], str]:
    return fetch_replay_chat_text
```

(이 파일은 이미 `CachingEmbedder`/`get_llm`/`get_embedder`를 담고 있다 — 위 내용은 기존 코드 그대로에 `get_replay_importer()`와 관련 import 한 줄만 추가한 것이다. 그대로 덮어써도 기존 동작은 안 바뀐다.)

- [ ] **Step 2: 실패하는 테스트 작성 — `tests/test_web_api.py`에 추가 (파일 끝)**

```python
from judgpt.web.dependencies import get_replay_importer
from judgpt.web.mafia42 import ReplayImportError


def test_fetch_replay_endpoint_returns_chat_text(client):
    app.dependency_overrides[get_replay_importer] = lambda: (lambda url: "케로신: 안녕")

    response = client.post(
        "/api/fetch-replay",
        json={"url": "https://mafia42.com/history/kr/743e94a801dff38ddf6c159c130d5777"},
    )

    assert response.status_code == 200
    assert response.json() == {"chat_text": "케로신: 안녕"}


def test_fetch_replay_endpoint_returns_400_on_invalid_url(client):
    def _raise(url):
        raise ReplayImportError("올바른 마피아42 리플레이 링크가 아닙니다", status_code=400)

    app.dependency_overrides[get_replay_importer] = lambda: _raise

    response = client.post("/api/fetch-replay", json={"url": "https://evil.com/x"})

    assert response.status_code == 400
    assert response.json() == {"detail": "올바른 마피아42 리플레이 링크가 아닙니다"}


def test_fetch_replay_endpoint_returns_502_on_fetch_failure(client):
    def _raise(url):
        raise ReplayImportError(
            "리플레이를 가져오지 못했습니다. 링크를 확인해주세요", status_code=502
        )

    app.dependency_overrides[get_replay_importer] = lambda: _raise

    response = client.post(
        "/api/fetch-replay",
        json={"url": "https://mafia42.com/history/kr/743e94a801dff38ddf6c159c130d5777"},
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "리플레이를 가져오지 못했습니다. 링크를 확인해주세요"}
```

- [ ] **Step 3: 테스트 실행 — 실패 확인**

Run: `pytest tests/test_web_api.py -v`
Expected: FAIL with `404 Not Found`(엔드포인트가 아직 없음) 또는 `ImportError`

- [ ] **Step 4: `judgpt/web/app.py`를 아래 내용으로 교체**

```python
import os
from typing import Callable

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import APIConnectionError
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from judgpt.analyzer import AnalysisError, analyze
from judgpt.embedder import Embedder
from judgpt.legal_rag import EnrichedResult, enrich
from judgpt.llm import LLM
from judgpt.schema import AnalysisResult
from judgpt.web.dependencies import get_embedder, get_llm, get_replay_importer
from judgpt.web.mafia42 import ReplayImportError

app = FastAPI()

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "요청이 너무 많습니다. 잠시 후 다시 시도하세요"},
    )


@app.exception_handler(RequestValidationError)
def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"detail": "요청 형식이 올바르지 않습니다"},
    )


class AnalyzeRequest(BaseModel):
    chat_text: str = Field(max_length=100_000)
    legal: bool = False


@app.post("/api/analyze")
@limiter.limit("5/minute")
def analyze_endpoint(
    request: Request,
    body: AnalyzeRequest,
    llm: LLM = Depends(get_llm),
    embedder: Embedder = Depends(get_embedder),
) -> AnalysisResult | EnrichedResult:
    if not body.chat_text.strip():
        raise HTTPException(status_code=400, detail="입력이 비어 있습니다")

    try:
        result = analyze(body.chat_text, llm)
        if body.legal:
            return enrich(result, embedder)
        return result
    except AnalysisError:
        raise HTTPException(status_code=502, detail="분석에 실패했습니다. 다시 시도해주세요")
    except APIConnectionError:
        raise HTTPException(status_code=503, detail="분석 엔진이 응답하지 않습니다")


class FetchReplayRequest(BaseModel):
    url: str


class FetchReplayResponse(BaseModel):
    chat_text: str


@app.post("/api/fetch-replay")
@limiter.limit("5/minute")
def fetch_replay_endpoint(
    request: Request,
    body: FetchReplayRequest,
    importer: Callable[[str], str] = Depends(get_replay_importer),
) -> FetchReplayResponse:
    try:
        chat_text = importer(body.url)
    except ReplayImportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    return FetchReplayResponse(chat_text=chat_text)


_frontend_dist = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
```

- [ ] **Step 5: 테스트 실행 — 통과 확인**

Run: `pytest tests/test_web_api.py -v`
Expected: PASS (14 passed)

- [ ] **Step 6: 전체 테스트 스위트 실행 — 회귀 확인**

Run: `pytest -q`
Expected: 기존 테스트 전부 + 신규 12개(`test_mafia42.py` 9개 + `test_web_api.py` 3개) PASS. 총 139 passed, 3 deselected.

- [ ] **Step 7: 커밋**

```bash
git add judgpt/web/dependencies.py judgpt/web/app.py tests/test_web_api.py
git commit -m "POST /api/fetch-replay 엔드포인트 추가 — 마피아42 리플레이 링크로 채팅 가져오기"
```

---

### Task 4: 프론트엔드 — 텍스트/링크 탭 UI

**Files:**
- Modify: `frontend/src/api.js`
- Modify: `frontend/src/App.jsx`

**Interfaces:**
- Consumes: `POST /api/fetch-replay`(Task 3에서 완성된 API 계약 — 성공 시 `{"chat_text": str}`, 실패 시 `{"detail": str}` + 400/429/502)
- Produces: 브라우저에서 "텍스트 붙여넣기" / "리플레이 링크" 탭을 오갈 수 있는 UI. 자동화 테스트 없음(기존 프론트엔드 컨벤션과 동일 — 이 태스크의 "테스트"는 개발 서버를 띄워 브라우저로 직접 확인하는 것)

- [ ] **Step 1: `frontend/src/api.js`에 `fetchReplay()` 추가**

파일 끝에 추가:

```javascript
export async function fetchReplay(url) {
  const response = await fetch("/api/fetch-replay", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(response.status, body.detail || "알 수 없는 오류가 발생했습니다");
  }

  const data = await response.json();
  return data.chat_text;
}
```

- [ ] **Step 2: `frontend/src/App.jsx`를 아래 내용으로 교체**

```jsx
import { useState } from "react";
import { analyzeChat, fetchReplay, ApiError } from "./api";

const DISCLAIMER =
  "이 결과는 참고용 정보이며 법적 판단이 아닙니다. 실제 법적 대응이 필요하면 변호사와 상담하세요.";

function errorMessage(err) {
  // 백엔드가 400/429/502/503마다 이미 사용자에게 보여줄 수 있는 한국어 문구를
  // detail로 내려준다(judgpt/web/app.py) — 프론트에서 상태 코드별로 다시 매핑하지
  // 않고 그대로 쓴다.
  if (!(err instanceof ApiError)) return "알 수 없는 오류가 발생했습니다";
  return err.message;
}

export default function App() {
  const [tab, setTab] = useState("text");
  const [chatText, setChatText] = useState("");
  const [replayUrl, setReplayUrl] = useState("");
  const [importing, setImporting] = useState(false);
  const [legal, setLegal] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await analyzeChat(chatText, legal);
      setResult(data);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleImport(e) {
    e.preventDefault();
    setImporting(true);
    setError(null);
    try {
      const text = await fetchReplay(replayUrl);
      setChatText(text);
      setTab("text");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setImporting(false);
    }
  }

  return (
    <div>
      <h1>judgpt</h1>

      <div>
        <button type="button" onClick={() => setTab("text")} disabled={tab === "text"}>
          텍스트 붙여넣기
        </button>
        <button type="button" onClick={() => setTab("link")} disabled={tab === "link"}>
          리플레이 링크
        </button>
      </div>

      {tab === "link" && (
        <form onSubmit={handleImport}>
          <input
            type="url"
            value={replayUrl}
            onChange={(e) => setReplayUrl(e.target.value)}
            placeholder="https://mafia42.com/history/kr/..."
          />
          <button type="submit" disabled={importing}>
            {importing ? "가져오는 중..." : "가져오기"}
          </button>
        </form>
      )}

      {tab === "text" && (
        <form onSubmit={handleSubmit}>
          <textarea
            value={chatText}
            onChange={(e) => setChatText(e.target.value)}
            placeholder="채팅 내용을 붙여넣으세요"
            rows={10}
          />
          <div>
            <label>
              <input
                type="checkbox"
                checked={legal}
                onChange={(e) => setLegal(e.target.checked)}
              />
              법률 정보 포함(조문/판례)
            </label>
          </div>
          <button type="submit" disabled={loading}>
            {loading ? "분석 중..." : "분석하기"}
          </button>
        </form>
      )}

      {error && <p role="alert">{error}</p>}

      {result && (
        <div>
          {result.expressions.length === 0 ? (
            <p>문제 표현이 발견되지 않았습니다.</p>
          ) : (
            result.expressions.map((expr, i) => (
              <div key={i}>
                <p>"{expr.text}"</p>
                <p>유형: {expr.type}</p>
                <p>위험도: {expr.risk}</p>
                {expr.target && <p>대상: {expr.target}</p>}
                {expr.context && <p>맥락: {expr.context}</p>}
                {expr.applicable_laws && (
                  <p>
                    적용 가능 법률:{" "}
                    {expr.applicable_laws.length > 0
                      ? expr.applicable_laws.join(", ")
                      : "판단 근거 없음"}
                  </p>
                )}
                {expr.related_cases && (
                  <p>
                    관련 판례:{" "}
                    {expr.related_cases.length > 0
                      ? expr.related_cases.join(" / ")
                      : "판단 근거 없음"}
                  </p>
                )}
              </div>
            ))
          )}
        </div>
      )}

      <hr />
      <p>{DISCLAIMER}</p>
    </div>
  );
}
```

- [ ] **Step 3: 빌드 확인**

Run: `cd frontend && npm run build`
Expected: 에러 없이 빌드 완료(exit code 0).

- [ ] **Step 4: 수동 확인 — 실제 마피아42 리플레이 링크로 확인**

두 터미널에서 각각:

```bash
# 터미널 1 (repo 루트, Ollama가 로컬에 떠 있어야 함)
uvicorn judgpt.web.app:app --reload --port 8000

# 터미널 2
cd frontend && npm run dev
```

브라우저에서 `http://localhost:5173` 접속 후 확인할 것:
1. "리플레이 링크" 탭 클릭 → URL 입력창이 보이는지.
2. 실제 마피아42 리플레이 링크(예: `https://mafia42.com/history/kr/743e94a801dff38ddf6c159c130d5777`, 만료됐을 수 있으니 최신 링크로 테스트) 붙여넣고 "가져오기" 클릭 → 채팅이 추출돼서 "텍스트 붙여넣기" 탭으로 자동 전환되고 텍스트창에 채워지는지.
3. 그 상태에서 "분석하기" 클릭 → 정상적으로 분석 결과가 나오는지.
4. 잘못된 URL(예: `https://google.com`)을 넣고 "가져오기" → "올바른 마피아42 리플레이 링크가 아닙니다" 메시지가 뜨는지.

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/api.js frontend/src/App.jsx
git commit -m "웹 UI에 마피아42 리플레이 링크 가져오기 탭 추가"
```

---

## Self-Review 메모 (계획 작성자용, 실행 시 참고만)

- **스펙 커버리지**: spec §1(기술적 사실) → Task 1의 HTML 구조·fixture, §2(아키텍처) → Task 1-3 전체, §3(API 계약) → Task 3, §4(HTML 파싱) → Task 1-2, §5(프론트엔드) → Task 4, §6(테스트 전략) → 각 태스크의 Test 섹션, §7(Global Constraints) → 본 계획 상단에 그대로 반영.
- **타입 일관성**: `ReplayImportError(message, status_code)`가 Task 1(정의)·2·3(소비)에서 동일 시그니처로 사용됨. `fetch_replay_chat_text(url) -> str`이 Task 2(정의)·3(소비, `Depends(get_replay_importer)`를 통해)에서 일치. `_parse_chat_html`이 Task 1(정의)·2(소비, `fetch_replay_chat_text` 내부에서)에서 일치.
- **플레이스홀더 스캔**: 없음 — fixture HTML은 실제 마피아42 응답에서 발췌한 진짜 마크업이고, 예상 파싱 결과(`케로신`/`이반` 5줄)는 이 계획을 쓰기 전에 동일한 로직으로 실제 검증까지 마친 값이다(빈 리플레이 URL, 만료 가능성 있는 예시 링크 언급은 수동 확인 스텝에서 사용자가 최신 링크로 대체 가능하다고 명시했으므로 placeholder가 아니라 의도된 안내다).
