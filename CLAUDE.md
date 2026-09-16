# CLAUDE.md

이 파일은 Claude Code가 이 저장소에서 작업할 때 참고할 안내를 담고 있다.

## 명령어

- 설치: `pip install -e ".[dev]"`
- 전체 테스트(네트워크 불필요, Ollama 없어도 통과): `pytest` (기본 `addopts`가 `integration` 마커를 제외한다)
- 통합 테스트만(단위 테스트 33개는 제외되고, 로컬에 Ollama가 떠 있고 `ollama pull exaone3.5:7.8b`로 모델을 받아둔 경우에만 통과하는 2개만 실행): `pytest -m integration`
- CLI 실행: `python -m judgpt.analyze --file chat.txt` 또는 `cat chat.txt | python -m judgpt.analyze`
- 원본 JSON 출력: `python -m judgpt.analyze --file chat.txt --json`
- 환경변수: `JUDGPT_MODEL`(기본 `exaone3.5:7.8b`), `OLLAMA_BASE_URL`(기본 `http://localhost:11434/v1`)

## 아키텍처

채팅 텍스트를 넣으면 로컬 Ollama 모델 하나로 유해 표현(욕설/성희롱/협박/모욕/명예훼손)을 탐지하고 위험도를 판단하는 CLI 도구. 전처리·탐지·문맥분석을 파이프라인으로 나누지 않고 **단일 LLM 호출**로 처리한다 — 자세한 판단 이유는 `docs/02-architecture.md` 참고.

핵심 모듈(`judgpt/`):
- `llm.py` — `LLM` Protocol(`call(messages) -> str`), 테스트용 `FakeLLM`, 실제 구현 `OllamaLLM`(Ollama의 OpenAI 호환 엔드포인트 호출).
- `schema.py` — `Expression`/`AnalysisResult` Pydantic 모델. `type`/`risk` 허용값은 `docs/02-architecture.md` §5 참고.
- `prompt.py` — 시스템 프롬프트(`SYSTEM_PROMPT`)와 `build_messages()`. 법 조문/판례를 언급하지 말라는 제약이 프롬프트에 명시되어 있다(RAG 없는 MVP이므로).
- `analyzer.py` — `analyze()`: LLM 호출 → JSON 파싱 → Pydantic 검증. 실패 시 에러 내용을 알려주고 **1회만 재시도**, 그래도 실패하면 `AnalysisError`.
- `report.py` — `AnalysisResult`를 사람이 읽는 리포트 문자열로 변환. `DISCLAIMER`(참고용 정보 고지)는 항상 고정 문구로 붙인다 — 모델 출력에 맡기지 않는다. 사람이 읽는 리포트에는 본문 끝에 포함되고, `--json` 모드에서는 `main()`이 별도로 stderr에 출력한다(둘 다 항상 표시됨).
- `analyze.py` — CLI 진입점. `run()`은 순수 함수(테스트하기 쉬움, I/O 없음)로 그대로 유지되고, `main()`이 argparse + 파일/stdin 읽기 + `OllamaLLM` 생성 + 출력(및 `--json`일 때 stderr로의 `DISCLAIMER` 출력) 등 모든 I/O를 담당한다. `main(argv, llm=...)`처럼 `llm`을 주입할 수 있어 테스트가 실제 Ollama 없이 전체 CLI 흐름을 검증한다.

모델은 기본 `exaone3.5:7.8b`(한국어 특화)이고 `qwen2.5:7b`로 교체해볼 수 있다 — 둘 중 어느 쪽이 이 작업에 더 나은지는 아직 실측 전이다(`docs/02-architecture.md` §10).

## 실행 전 준비

Ollama가 로컬에 설치되어 있고 `ollama pull exaone3.5:7.8b`로 모델을 받아둬야 `python -m judgpt.analyze`가 실제로 동작한다. 없으면 연결 오류가 난다 — 단, 단위 테스트(`pytest`, 통합 마커 제외)는 전부 `FakeLLM`을 쓰므로 Ollama 설치 여부와 무관하게 통과한다.

## 범위 밖 (아직 없음)

- 법률 RAG(관련 법 조문/판례 검색) — `docs/REQUIREMENTS.md` §3.2, 2차 확장.
- 웹 UI, 카카오톡 등 메신저 포맷 자동 파싱, 자동 채점 eval 하네스.
