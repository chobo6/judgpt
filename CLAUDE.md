# CLAUDE.md

이 파일은 Claude Code가 이 저장소에서 작업할 때 참고할 안내를 담고 있다.

## 명령어

- 설치: `pip install -e ".[dev]"`
- 전체 테스트(네트워크 불필요, Ollama 없어도 통과): `pytest` (기본 `addopts`가 `integration` 마커를 제외한다)
- 통합 테스트만(단위 테스트는 제외되고, 로컬에 Ollama가 떠 있고 `ollama pull exaone3.5:7.8b`로 모델을 받아둔 경우에만 통과하는 3개만 실행 — 이 중 법제처 API 테스트는 `JUDGPT_LAW_API_OC`가 설정된 경우에만 돌고, 없으면 자동으로 skip된다): `pytest -m integration`
- CLI 실행: `python -m judgpt.analyze --file chat.txt` 또는 `cat chat.txt | python -m judgpt.analyze`
- 원본 JSON 출력: `python -m judgpt.analyze --file chat.txt --json`
- 조문/판례 정보 포함(법률 RAG): `python -m judgpt.analyze --file chat.txt --legal` (대화가 온라인/공개 채널에서 이루어졌다면 `--online`도 함께 줘서 가중 조항까지 포함시킬 수 있다 — `--legal` 없이는 효과 없음)
- 환경변수: `JUDGPT_MODEL`(기본 `exaone3.5:7.8b`), `OLLAMA_BASE_URL`(기본 `http://localhost:11434/v1`), `JUDGPT_EMBEDDING_MODEL`(기본 `nomic-embed-text`, `--legal` 사용 시에만 필요), `JUDGPT_LAW_API_OC`(법제처 Open API 인증키, `fetch_statutes.py` 검증 스크립트에서만 필요)

## 아키텍처

채팅 텍스트를 넣으면 로컬 Ollama 모델 하나로 유해 표현(욕설/성희롱/협박/모욕/명예훼손)을 탐지하고 위험도를 판단하는 CLI 도구. 전처리·탐지·문맥분석을 파이프라인으로 나누지 않고 **단일 LLM 호출**로 처리한다 — 자세한 판단 이유는 `docs/02-architecture.md` 참고. `--legal` 플래그를 주면 탐지 결과에 조문/판례를 붙이는 RAG 레이어가 추가로 붙는다 — 설계 배경은 `docs/03-legal-rag-design.md` 참고.

핵심 모듈(`judgpt/`):
- `llm.py` — `LLM` Protocol(`call(messages) -> str`), 테스트용 `FakeLLM`, 실제 구현 `OllamaLLM`(Ollama의 OpenAI 호환 엔드포인트 호출).
- `schema.py` — `Expression`/`AnalysisResult` Pydantic 모델. `type`/`risk` 허용값은 `docs/02-architecture.md` §5 참고.
- `prompt.py` — 시스템 프롬프트(`SYSTEM_PROMPT`)와 `build_messages()`. 법 조문/판례를 언급하지 말라는 제약이 프롬프트에 명시되어 있다(탐지 단계는 여전히 RAG 없이 동작하므로).
- `analyzer.py` — `analyze()`: LLM 호출 → JSON 파싱 → Pydantic 검증. 실패 시 에러 내용을 알려주고 **1회만 재시도**, 그래도 실패하면 `AnalysisError`.
- `embedder.py` — `Embedder` Protocol(`embed(text) -> list[float]`), 테스트용 `FakeEmbedder`, 실제 구현 `OllamaEmbedder`(Ollama의 임베딩 엔드포인트 호출). 벡터 간 유사도를 재는 `cosine_similarity()`도 여기 있다.
- `legal_rag.py` — `enrich()`: `AnalysisResult`를 `legal_data/`의 조문·판례 정보로 보강해 `EnrichedResult`를 만든다. 판례 임베딩은 캐싱하지 않고 호출마다 새로 계산한다 — 코퍼스가 작아 캐싱이 불필요한 복잡도라고 판단했다(`docs/03-legal-rag-design.md` §4).
- `legal_data/` — `articles.py`(표현 유형 → 조문 규칙 매핑 `ARTICLE_MAP`, 아직 사람이 확인 전임을 표시하는 `NEEDS_VERIFICATION` 플래그), `cases.json`/`cases.py`(직접 큐레이션한 판례 코퍼스와 로더), `fetch_statutes.py`(법제처 Open API로 조문을 검증하는 스크립트, CLI 실행 경로에서는 자동 호출되지 않음).
- `report.py` — `AnalysisResult`를 사람이 읽는 리포트 문자열로 변환. `DISCLAIMER`(참고용 정보 고지)는 항상 고정 문구로 붙인다 — 모델 출력에 맡기지 않는다. 사람이 읽는 리포트에는 본문 끝에 포함되고, `--json` 모드에서는 `main()`이 별도로 stderr에 출력한다(둘 다 항상 표시됨). `--legal` 결과(`EnrichedResult`)는 `format_enriched_report()`가 별도로 사람이 읽는 리포트로 변환하며, `NEEDS_VERIFICATION`이 참인 동안은 조문 뒤에 재검증 필요 경고를 붙인다.
- `analyze.py` — CLI 진입점. `run()`은 순수 함수(테스트하기 쉬움, I/O 없음)로 그대로 유지되고, `main()`이 argparse + 파일/stdin 읽기 + `OllamaLLM` 생성 + 출력(및 `--json`일 때 stderr로의 `DISCLAIMER` 출력) 등 모든 I/O를 담당한다. `main(argv, llm=...)`처럼 `llm`을 주입할 수 있어 테스트가 실제 Ollama 없이 전체 CLI 흐름을 검증한다. `run()`/`main()` 둘 다 `embedder` 파라미터를 받는다 — `--legal`일 때만 쓰이고, `main()`은 `embedder`가 주어지지 않으면 `OllamaEmbedder`를 직접 만들어 주입한다.

모델은 기본 `exaone3.5:7.8b`(한국어 특화)이고 `qwen2.5:7b`로 교체해볼 수 있다 — 둘 중 어느 쪽이 이 작업에 더 나은지는 아직 실측 전이다(`docs/02-architecture.md` §10).

## 실행 전 준비

Ollama가 로컬에 설치되어 있고 `ollama pull exaone3.5:7.8b`로 모델을 받아둬야 `python -m judgpt.analyze`가 실제로 동작한다. 없으면 연결 오류가 난다 — 단, 단위 테스트(`pytest`, 통합 마커 제외)는 전부 `FakeLLM`을 쓰므로 Ollama 설치 여부와 무관하게 통과한다. `--legal`을 쓰려면 추가로 `ollama pull nomic-embed-text`로 임베딩 모델도 받아둬야 한다.

## 트러블슈팅

실제로 겪은 버그·장애와 근본 원인은 `docs/TROUBLESHOOTING.md`에 기록한다 — 새로 작업하다 트러블을 만나면 그때그때 이 문서에 추가할 것 (repoview 프로젝트와 동일한 컨벤션).

## 범위 밖 (아직 없음)

- 웹 UI, 카카오톡 등 메신저 포맷 자동 파싱, 자동 채점 eval 하네스.
