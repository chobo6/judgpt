# judgpt — 웹 UI 설계

> `CLAUDE.md` "범위 밖" 항목 중 하나였던 "웹 UI"의 구현 설계다. CLI(`judgpt/analyze.py`), 법률 RAG(`--legal`), eval 하네스(`judgpt/eval.py`)는 이미 구현·병합된 상태이며, 이 문서는 그 탐지·법률 RAG 로직을 웹에서도 쓸 수 있게 감싸는 새 인터페이스 레이어를 추가한다.

## 0. 목적과 범위

- **목적**: 지금은 CLI로 `python -m judgpt.analyze --file chat.txt`처럼 직접 실행해야 쓸 수 있는 도구를, 계정 없이 누구나 브라우저에서 채팅 텍스트를 붙여넣고 바로 결과를 볼 수 있게 만든다. 나중에 다른 사람도 쓸 수 있도록 배포하는 것을 염두에 둔다.
- **범위**: 탐지(MVP) + 법률 RAG(`--legal`) 둘 다 웹에서 노출한다. eval 하네스(`judgpt/eval.py`)는 개발자 전용 도구로 남기고 웹 UI 범위에서 제외한다.
- **비목표**: 사용자 계정/로그인, 분석 결과의 서버 측 저장(요청-응답 그 자리에서만 보여주고 폐기 — `REQUIREMENTS.md` §4/§6의 "즉시 폐기" 정책과 일관), 실제 배포 인프라(Dockerfile 작성은 포함하되 k8s 등 실제 배포는 별도 후속 작업), 스트리밍/실시간 진행률 표시, 모바일 전용 UI.

## 1. 배포 전제와 LLM 백엔드

- 서버(또는 같은 네트워크 내 머신)에 Ollama와 `exaone3.5:7.8b`/`nomic-embed-text`를 직접 띄우고, 모든 사용자가 이 하나의 Ollama 인스턴스를 공유한다 — CLI와 마찬가지로 외부 LLM API를 쓰지 않아 "비용 0원" 제약(`REQUIREMENTS.md`)을 유지한다.
- 계정이 없는 공개 도구라 도배성 요청으로 공유 Ollama가 과부하될 수 있다 — IP당 rate limit으로 방어한다(§4).
- FastAPI 프로세스 시작 시 `OllamaLLM`/`OllamaEmbedder`(`--legal`용)를 한 번만 생성해 앱 전역에서 재사용한다 — 요청마다 새로 만들지 않는다.

## 2. 아키텍처

```
브라우저 (React SPA, 정적 파일)
    │  HTTP (POST /api/analyze)
    ▼
FastAPI 서버 (judgpt/web/)
    │  기존 함수 직접 호출 — 탐지 로직 재구현 없음
    ▼
judgpt.analyze.run() → judgpt.analyzer.analyze() / judgpt.legal_rag.enrich()
    │
    ▼
같은 서버의 Ollama (exaone3.5:7.8b, --legal이면 nomic-embed-text도)
```

- 새 디렉터리 두 개를 리포에 추가한다: `judgpt/web/`(FastAPI 백엔드, 기존 패키지 안에 위치해 `judgpt.analyzer`/`judgpt.legal_rag` 등을 바로 import), `frontend/`(React+Vite, 별도 Node 프로젝트).
- 기존 CLI(`judgpt/analyze.py`)와 신규 웹 백엔드는 둘 다 `judgpt.analyze.run()`을 호출하는 얇은 진입점이라는 점에서 대칭이다 — `run()`은 이미 순수 함수(I/O 없음)로 설계되어 있어 이번 작업에서 손댈 필요가 없다.
- `POST /api/analyze` 하나만 있는 동기(synchronous) REST 엔드포인트로 시작한다. LLM 호출이 수 초~수십 초 걸리지만, 요청-응답 한 번으로 끝나는 이 규모(단일 채팅 분석)에는 웹소켓/SSE 스트리밍이나 작업 큐가 과한 설계다 — 필요해지면(동시 사용자가 많아 타임아웃이 잦아지면) 그때 도입을 검토한다.

## 3. API 계약

```
POST /api/analyze
  요청 body: {"chat_text": "채팅 원문", "legal": false}

  200 (legal=false): AnalysisResult.model_dump() 그대로
    {"expressions": [{"text": ..., "type": ..., "risk": ..., "target": ..., "context": ...}]}

  200 (legal=true): EnrichedResult.model_dump() 그대로
    {"expressions": [{..., "applicable_laws": [...], "related_cases": [...]}], "needs_verification": bool}

  400: {"detail": "입력이 비어 있습니다"}                          — chat_text가 빈 문자열/공백뿐
  429: {"detail": "요청이 너무 많습니다. 잠시 후 다시 시도하세요"}   — rate limit 초과
  502: {"detail": "분석에 실패했습니다. 다시 시도해주세요"}          — AnalysisError(재시도 후에도 모델 응답이 JSON 스키마에 안 맞음)
  503: {"detail": "분석 엔진이 응답하지 않습니다"}                  — Ollama APIConnectionError
```

- 엔드포인트 핸들러는 `judgpt.analyze.run(chat_text, llm, as_json=True, legal=legal, embedder=embedder if legal else None)`을 그대로 호출해 JSON 문자열을 받고, 그 문자열을 파싱 없이 그대로 응답 본문으로 반환한다 — 직렬화 로직을 새로 만들지 않는다(`run()`이 이미 `json.dumps(..., ensure_ascii=False)`로 직렬화).
- `DISCLAIMER`(참고용 정보 고지)는 백엔드가 새로 만들지 않는다 — CLI와 동일하게 프론트가 고정 문구로 항상 표시한다(§5). API 응답 자체에는 고지 문구를 포함하지 않는다(기존 `--json` 모드가 stdout엔 순수 JSON만, 고지는 별도 stderr로 내보내는 것과 같은 정신 — 여기서는 "고지는 프론트의 고정 UI 요소"로 치환).
- **에러 매핑**: 핸들러에서 `chat_text.strip()`이 비면 400, `analyze()`가 던지는 `judgpt.analyzer.AnalysisError`(재시도 후에도 JSON 파싱 실패)는 500으로 통과시키지 않고 502(analysis failed)로 매핑, `openai.APIConnectionError`는 503으로 매핑한다.

## 4. Rate Limiting

- `slowapi`(FastAPI/Starlette용 경량 rate-limit 미들웨어, 새 런타임 의존성으로 추가) — IP당 **분당 5회**로 `/api/analyze`를 제한한다(정상적인 1인 사용 패턴엔 충분하고, 도배성 요청은 막는 보수적인 기본값 — 실사용 중 너무 빡빡하면 조정). 인메모리 카운터로 충분하다(단일 서버 프로세스 전제, Redis 등 외부 스토어는 이 규모에 불필요).
- 초과 시 429 응답, 본문은 §3의 형식과 동일하게 `{"detail": "..."}`.

## 5. 프론트엔드 (`frontend/`, Vite + React)

- 화면 1개짜리 SPA:
  - `<textarea>` 채팅 텍스트 입력
  - "법률 정보 포함(--legal)" 체크박스
  - 분석 버튼 → 로딩 중 스피너
  - 결과: 표현별 카드(인용문/유형/위험도/대상/맥락, 법률 옵션 켰으면 적용 가능 법률·관련 판례까지)
  - 하단에 고정 고지 문구(`DISCLAIMER`와 동일한 한국어 문구, 프론트 코드에 상수로 박아둔다 — 백엔드 응답에 의존하지 않음)
- 상태 관리는 React 로컬 state(`useState`)만으로 충분 — 입력 텍스트, 로딩 여부, 결과, 에러 메시지 네 가지가 전부다. Redux 등 전역 상태 라이브러리는 이 규모에 불필요.
- 결과나 입력 텍스트를 어디에도 영속시키지 않는다(로컬스토리지 포함) — 새로고침하면 사라지는 게 기본 동작. 이는 §0의 "서버 측 저장 없음" 정책과 프론트에서도 일관되게 지키는 것이다.
- 에러 처리: HTTP 상태 코드별로 사용자용 한국어 메시지로 매핑해서 보여준다(날것 에러 JSON을 그대로 노출하지 않음) — 429는 "잠시 후 다시 시도해주세요", 503/502는 "서비스가 일시적으로 응답하지 않습니다", 400은 "채팅 내용을 입력해주세요".

## 6. 테스트 전략

- **백엔드**(`tests/test_web_api.py` — 기존 `tests/` 평면 구조 컨벤션을 그대로 따른다): FastAPI `TestClient`(httpx 기반)로 `/api/analyze`를 호출하되, 앱에 `FakeLLM`/`FakeEmbedder`를 의존성 주입(FastAPI `Depends` 오버라이드)해서 실제 Ollama 없이 테스트한다 — 기존 `tests/test_analyze_cli.py`가 `FakeLLM`을 주입해 전체 CLI 흐름을 검증하는 것과 동일 패턴.
  - 커버할 케이스: 정상 응답(legal=false/true 둘 다), 빈 입력 400, rate limit 초과 429, `AnalysisError`/`APIConnectionError` 매핑.
- **프론트**(`frontend/`): 이 프로젝트엔 기존 JS 테스트 컨벤션이 없다. MVP 범위에서는 수동 확인(브라우저로 직접 써보기)으로 충분하다고 보고 자동화 테스트(Vitest 등)는 필요해지면 추가한다 — 과한 선제 투자를 하지 않는다(YAGNI).
- 실제 Ollama가 필요한 엔드투엔드 확인(브라우저로 직접 폼 제출)은 자동 테스트 스위트에 넣지 않는다 — `judgpt/eval.py`가 골든셋을 사람이 수동으로 돌리는 것과 같은 이유(비결정적·느림).

## 7. 파일 구조 요약

```
judgpt/
  web/
    __init__.py
    app.py                # FastAPI 앱, POST /api/analyze, rate limit 미들웨어, 에러 핸들러
    dependencies.py        # 앱 전역 OllamaLLM/OllamaEmbedder 싱글턴 + FakeLLM 주입용 오버라이드 포인트
frontend/
  package.json             # Vite + React
  src/
    App.tsx                 # 입력 폼 + 결과 렌더링 (단일 화면)
    api.ts                    # POST /api/analyze 호출 래퍼
tests/
  test_web_api.py            # FastAPI TestClient + FakeLLM/FakeEmbedder
Dockerfile                    # 백엔드(+ 빌드된 프론트 정적 파일) 컨테이너화 — 실제 배포(k8s 등)는 범위 밖
```

기존 `judgpt/` 패키지 구조(관심사별 파일 분리, 각 CLI 진입점이 기존 순수 함수를 얇게 감싸는 패턴)를 그대로 따른다.

## 8. Global Constraints (구현 계획에 그대로 전달)

- `judgpt/analyzer.py`, `judgpt/schema.py`, `judgpt/llm.py`, `judgpt/legal_rag.py`, `judgpt/report.py`, `judgpt/embedder.py`, `judgpt/analyze.py`의 기존 로직은 수정하지 않는다 — 웹 레이어는 그 위에 얇게 얹는다.
- 탐지/법률 RAG 로직을 웹 백엔드에 재구현하지 않는다 — 반드시 `judgpt.analyze.run()`을 호출한다.
- 계정/로그인, 서버 측 결과 저장(로그 포함), 프론트 로컬스토리지 저장을 추가하지 않는다.
- `DISCLAIMER` 고지 문구는 프론트에 고정 문구로 존재해야 하며, 어떤 응답 경로로도 생략되면 안 된다.
- rate limit은 IP당 분당 5회, `slowapi` 사용.
- 실제 배포(Dockerfile 이후의 k8s/클라우드 배포)는 이 계획의 범위가 아니다 — 별도 후속 작업.
