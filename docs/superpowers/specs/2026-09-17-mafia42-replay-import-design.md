# judgpt — 마피아42 리플레이 링크 가져오기 설계

> `CLAUDE.md` "범위 밖"에 있던 "메신저 포맷 자동 파싱"을 대체/구체화하는 기능이다. 사용자가 실제로 요청한 건 카카오톡 내보내기 파일 파싱이 아니라, 모바일 게임 **마피아42**의 리플레이(대화 내역) 링크를 붙여넣으면 그 안의 채팅을 자동으로 추출해 기존 웹 UI 분석 흐름에 태우는 것이다.

## 0. 목적과 범위

- **목적**: 마피아42 리플레이 링크(`https://mafia42.com/history/{lang}/{id}`)를 웹 UI에 붙여넣으면, 그 리플레이의 플레이어 채팅을 자동으로 추출해 기존 텍스트창에 채워준다. 사용자가 매번 게임 화면을 캡처하거나 수동으로 타이핑할 필요가 없어진다.
- **범위**: 웹 UI에서만 지원한다(CLI는 범위 밖 — 필요해지면 후속 작업). 마피아42 리플레이 링크만 지원한다 — 다른 사이트/포맷은 범위 밖.
- **비목표**: 카카오톡 등 다른 메신저 내보내기 포맷 파싱, 마피아42 외 다른 게임/사이트 지원, 리플레이 데이터의 서버 측 저장(기존 "저장 안 함" 정책과 동일하게 유지 — 가져온 텍스트도 요청-응답 그 자리에서만 존재).

## 1. 기술적 사실 확인 (실측)

리플레이 페이지(`https://mafia42.com/history/kr/{id}`)는 채팅 위젯을 `<iframe src="https://o2zj8uijbj.execute-api.ap-northeast-2.amazonaws.com/GetMafiaChat?id={id}&lang={lang}">`으로 내장한다. 이 iframe URL을 `Referer: https://mafia42.com/` 헤더와 함께 직접 GET하면(브라우저 없이) **서버에서 이미 렌더링된 채팅 전체가 HTML로 그대로** 내려온다 — 로그인/인증 불필요, 헤드리스 브라우저 불필요.

HTML 구조(실제 샘플로 확인):
```html
<div class="name-content-container with-nickname">
  <div class="nick-name">케로신</div>
  <div class="chat-container display-flex flex-col">
    <div class="with-nickname MAFIACHAT chat-bubble">
      <div class="bubble-tail-border">...</div>
      야습수배위선
    </div>
    <div class="MAFIACHAT chat-bubble continue">ㄴ</div>
    <div class="MAFIACHAT chat-bubble continue">특 감</div>
  </div>
</div>
...
<div class="system center"><b>밤이 되었습니다.</b></div>
```

- 화자 한 명이 연속으로 여러 메시지를 보내면 `div.name-content-container` 하나에 `div.nick-name`(화자, 1개) + `div.chat-container` 안에 `div.chat-bubble` 여러 개(메시지마다 하나, 첫 번째만 `with-nickname` 클래스가 더 붙음)로 묶인다.
- 게임 시스템 메시지(밤/낮 전환, 사망, 투표 등)는 `div.system`으로 별도 마킹되어 있어 명확히 구분 가능.
- 이모티콘만 있는 말풍선처럼 텍스트가 없는 `chat-bubble`은 추출 시 빈 문자열이 된다 — 별도 처리 없이 빈 문자열이면 그 줄을 건너뛴다(간단하고 충분).

## 2. 아키텍처

```
프론트엔드 (링크 탭)
    │ POST /api/fetch-replay {"url": "https://mafia42.com/history/kr/{id}"}
    ▼
FastAPI (judgpt/web/app.py)
    │ judgpt.web.mafia42.fetch_replay_chat_text(url)
    ▼
1. URL 정규식 검증 → lang, id 추출
2. httpx.get(GetMafiaChat 고정 호스트 URL, headers={"Referer": "https://mafia42.com/"})
3. BeautifulSoup으로 HTML 파싱 → "화자: 메시지" 줄들로 변환
    │
    ▼
{"chat_text": "케로신: 야습수배위선\n케로신: ㄴ\n..."} 응답
    │ (프론트가 이 텍스트를 기존 textarea에 채움 — 사용자가 확인 후 별도로 /api/analyze 호출)
```

- 새 모듈 `judgpt/web/mafia42.py` 하나만 노출 함수를 갖는다: `fetch_replay_chat_text(url: str) -> str`. 내부에 URL 검증, HTTP 호출, HTML 파싱이 전부 들어간다 — 웹 API 레이어(`app.py`)는 이 함수를 호출하고 예외를 HTTP 응답으로 매핑하는 역할만 한다.
- **SSRF 방지**: 사용자가 준 `url`을 그대로 fetch하지 않는다. `REPLAY_URL_PATTERN = re.compile(r"^https://mafia42\.com/history/([a-z]{2})/([0-9a-f]{32})/?$")`로 엄격히 검증해 `lang`/`id`만 뽑아내고, 실제 HTTP 요청은 우리가 직접 조립한 고정 호스트(`o2zj8uijbj.execute-api.ap-northeast-2.amazonaws.com`) URL로만 나간다. 패턴에 안 맞으면 요청 자체를 안 보내고 400을 반환한다.
- `httpx`는 이미 `pyproject.toml`의 `web` extra에 있다(재사용). `beautifulsoup4`를 새 의존성으로 `web` extra에 추가한다.

## 3. API 계약

```
POST /api/fetch-replay
  요청 body: {"url": "https://mafia42.com/history/kr/743e94a801dff38ddf6c159c130d5777"}

  200: {"chat_text": "케로신: 야습수배위선\n케로신: ㄴ\n..."}

  400: {"detail": "올바른 마피아42 리플레이 링크가 아닙니다"}
       — URL이 REPLAY_URL_PATTERN에 안 맞음(다른 사이트, 잘못된 형식 등)

  502: {"detail": "리플레이를 가져오지 못했습니다. 링크를 확인해주세요"}
       — mafia42 쪽 HTTP 요청 실패(네트워크 오류, 404 — 존재하지 않는 리플레이 등), 또는 파싱 결과 채팅이 0건(빈 리플레이/구조 변경 등)
```

- 기존 `/api/analyze`와 동일하게 IP당 분당 5회 rate limit(`@limiter.limit("5/minute")`) 적용 — 마피아42 서버에 부하를 주는 것도 방지.
- 이 엔드포인트는 `chat_text`만 반환한다 — 분석(`AnalysisResult`)은 하지 않는다. 프론트가 받은 `chat_text`를 기존 textarea에 채우고, 사용자가 "분석하기"를 눌러야 비로소 기존 `/api/analyze`가 호출된다(§0의 "미리보기 후 분석" 결정).

## 4. HTML 파싱 (`judgpt/web/mafia42.py`)

```python
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


def _parse_chat_html(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    lines = []
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

(구현 시 실제 `class` 조합이 위 초안과 미세하게 다를 수 있다 — 계획 단계에서 저장해둘 테스트 fixture HTML로 다시 검증한다.)

- 에러 매핑: `judgpt/web/app.py`의 `POST /api/fetch-replay` 핸들러는 `ReplayImportError`를 잡아 `HTTPException(status_code=exc.status_code, detail=str(exc))`로 그대로 변환한다 — 400/502 분기는 예외 자체가 이미 들고 있다.

## 5. 프론트엔드

- 텍스트창 위에 탭 2개: "텍스트 붙여넣기"(기존 기본값) / "리플레이 링크".
- 링크 탭: URL 입력창 + "가져오기" 버튼. 클릭 시 `POST /api/fetch-replay` 호출 → 성공하면 응답의 `chat_text`를 기존 textarea(공유 상태)에 채우고 "텍스트 붙여넣기" 탭으로 자동 전환 → 사용자가 눈으로 확인 후 기존 "분석하기" 버튼 사용.
- 에러 메시지는 기존 `errorMessage()`가 백엔드 `detail`을 그대로 보여주는 방식을 그대로 재사용(수정 불필요 — 이미 상태 코드 무관하게 `detail` 문자열을 그대로 쓰도록 되어 있다).
- 로딩 상태("가져오는 중...")는 기존 "분석 중..." 로딩 패턴과 동일한 방식으로 별도 상태 변수 추가.

## 6. 테스트 전략

- `tests/fixtures/mafia42_replay_sample.html` — 실제 응답에서 발췌한 **작은 대표 샘플**(전체 170KB가 아니라 `name-content-container` 블록 2~3개 + `system` 메시지 1~2개 정도로 트리밍) — 실제 플레이어 닉네임/발화가 들어가지만 마피아42 자체가 리플레이를 공개 링크로 공유하도록 설계된 서비스이고, 내용도 게임 내 추리 대화일 뿐이라 민감 정보는 아니다.
- `tests/test_mafia42.py`: `_parse_chat_html()`을 fixture HTML로 단위 테스트(화자별 여러 메시지, system 메시지 제외, 빈 말풍선 스킵 확인). `fetch_replay_chat_text()`는 `httpx.get`을 monkeypatch해서 실제 네트워크 없이 URL 검증 + 통합 흐름 테스트.
- `tests/test_web_api.py`: `POST /api/fetch-replay`에 대해 `judgpt.web.mafia42.fetch_replay_chat_text`를 FastAPI dependency 또는 직접 monkeypatch로 교체해 200/400/502 케이스 테스트. rate limit 테스트는 기존 `/api/analyze`용 테스트가 이미 `slowapi` 동작을 검증하므로 여기서 반복하지 않는다.
- 실제 mafia42.com에 대한 라이브 요청은 자동 테스트 스위트에 넣지 않는다(외부 서비스 의존, 비결정적) — 사람이 필요할 때 수동으로 확인.

## 7. Global Constraints (구현 계획에 그대로 전달)

- `judgpt/analyzer.py`, `judgpt/schema.py`, `judgpt/llm.py`, `judgpt/legal_rag.py`, `judgpt/report.py`, `judgpt/embedder.py`, `judgpt/analyze.py`, `judgpt/eval.py`의 기존 로직은 수정하지 않는다. `judgpt/web/app.py`의 기존 `/api/analyze` 핸들러도 수정하지 않는다 — 새 엔드포인트만 추가한다.
- 사용자가 준 `url`을 그대로 HTTP 요청 대상으로 쓰지 않는다 — 반드시 `REPLAY_URL_PATTERN`으로 검증 후 `lang`/`id`만 추출해 고정 호스트 URL을 우리가 직접 조립한다(SSRF 방지).
- 마피아42 리플레이만 지원한다 — 다른 사이트로 확장하는 일반화된 "URL importer" 추상화를 만들지 않는다(YAGNI, 필요해지면 그때 일반화).
- `/api/fetch-replay`는 `chat_text`만 반환하고 분석은 하지 않는다 — `/api/analyze`를 호출하지 않는다.
- IP당 분당 5회 rate limit 적용(`/api/analyze`와 동일 패턴).
- 가져온 리플레이 채팅을 서버 측에 저장/로깅하지 않는다(기존 "저장 안 함" 정책과 동일).
- 게임 시스템 메시지(`div.system`)는 분석 대상 텍스트에서 제외한다.
