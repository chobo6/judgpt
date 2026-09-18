# judgpt

채팅 텍스트에서 유해 표현(욕설·성희롱·협박·모욕·명예훼손·성적 발언)을 로컬 LLM으로 탐지하고 위험도를 판단하는 도구입니다. [Ollama](https://ollama.com)로 로컬에서 돌아가는 한국어 특화 모델(`exaone3.5:7.8b`) 하나가 채팅 텍스트를 통째로 읽고 표현 추출·유형 분류·위험도 판단을 한 번에 처리합니다. CLI와 웹 UI 두 가지로 쓸 수 있고, 마피아42 게임 리플레이 링크만 붙여넣어도 대화 내용을 자동으로 가져와 분석할 수 있습니다.

> 이 도구의 판단은 참고용 정보이며 법적 판단이 아닙니다. 실제 법적 대응이 필요하면 변호사와 상담하세요.

## 주요 기능

- **유해 표현 탐지** — 채팅 텍스트를 넣으면 문제 표현, 유형, 위험도(높음/중간/낮음), 대상, 판단 맥락을 뽑아줍니다.
- **법률 정보 보강(`--legal`)** — 탐지된 표현에 관련 형법·특별법 조문과 실제 대법원 판례를 붙여줍니다. 판례는 직접 조사해 실존 여부를 확인한 것만 씁니다(현재 19건, `judgpt/legal_data/cases.json`).
- **웹 UI** — 브라우저에서 텍스트를 붙여넣거나, 마피아42 리플레이 링크를 붙여넣으면 게임 내 채팅을 자동으로 추출해 그대로 분석할 수 있습니다.
- **정확도 측정 하네스** — 사람이 직접 작성한 골든 데이터셋(24건)으로 유형별/전체 precision·recall·F1을 실측합니다.

## 빠른 시작

사전 준비: [Ollama](https://ollama.com)를 설치하고 모델을 받아둡니다.

```bash
ollama pull exaone3.5:7.8b        # 탐지용 기본 모델
ollama pull nomic-embed-text      # --legal 옵션을 쓸 경우에만 필요
```

설치:

```bash
pip install -e ".[web,dev]"
```

CLI로 분석:

```bash
python -m judgpt.analyze --file chat.txt              # 사람이 읽는 리포트
python -m judgpt.analyze --file chat.txt --json        # 원본 JSON
python -m judgpt.analyze --file chat.txt --legal       # 조문·판례 포함
cat chat.txt | python -m judgpt.analyze                 # stdin으로도 가능
```

웹 UI로 실행:

```bash
uvicorn judgpt.web.app:app --reload --port 8000   # 백엔드
cd frontend && npm install && npm run dev          # 프론트(localhost:5173, /api는 8000으로 프록시)
```

정확도 측정:

```bash
python -m judgpt.eval
```

## 프로젝트 구조

```
judgpt/
├── llm.py, embedder.py    Ollama 호출 (LLM/임베딩 Protocol + 실제 구현)
├── schema.py               Expression/AnalysisResult 데이터 모델
├── prompt.py                탐지 기준이 담긴 시스템 프롬프트
├── analyzer.py               LLM 호출 → JSON 파싱 → 검증
├── legal_rag.py + legal_data/  --legal 옵션용 조문·판례 보강 (RAG)
├── report.py                  결과를 사람이 읽는 리포트로 변환
├── analyze.py                  CLI 진입점
├── eval.py + eval_data/         정확도 측정 하네스 + 골든 데이터셋
└── web/                          FastAPI 백엔드 (분석 API + 마피아42 리플레이 가져오기)

frontend/    React(Vite) 웹 UI
docs/        설계 문서, 트러블슈팅 기록
tests/       pytest (Ollama 없이도 전부 통과 — FakeLLM/FakeEmbedder 사용)
```

## 테스트

```bash
pytest                # 단위 테스트 — 네트워크·Ollama 불필요
pytest -m integration # 통합 테스트 — 로컬에 Ollama가 떠 있어야 통과
```

## 환경변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `JUDGPT_MODEL` | `exaone3.5:7.8b` | 탐지에 쓰는 Ollama 모델 |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama 엔드포인트 |
| `JUDGPT_EMBEDDING_MODEL` | `nomic-embed-text` | `--legal` 옵션용 임베딩 모델 |
| `JUDGPT_LAW_API_OC` | — | 법제처 Open API 인증키 (조문 검증 스크립트에서만 필요) |

## 더 읽어보기

- [CLAUDE.md](CLAUDE.md) — 모듈별 상세 설명, 명령어 전체 목록
- [docs/](docs/) — 설계 문서(아키텍처, 법률 RAG 설계)와 실제 버그·튜닝 기록(`TROUBLESHOOTING.md`)
