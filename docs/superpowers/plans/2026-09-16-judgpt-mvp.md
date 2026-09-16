# judgpt MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 채팅 텍스트를 붙여넣으면 로컬 Ollama 모델 하나로 욕설/성희롱/협박/모욕/명예훼손 표현을 탐지하고 위험도를 판단해주는 CLI 도구(`python -m judgpt.analyze`)를 만든다.

**Architecture:** 전처리·탐지·문맥분석을 단일 LLM 호출로 처리하는 파이프라인. `LLM` Protocol 뒤에 실제 구현(`OllamaLLM`, OpenAI 호환 엔드포인트)과 테스트용 `FakeLLM`을 둬서 네트워크 없이 전 계층을 테스트한다. 응답은 Pydantic으로 스키마 검증하고, 실패 시 1회만 재시도한다.

**Tech Stack:** Python 3.12+, `openai` SDK(Ollama의 OpenAI 호환 엔드포인트 호출용), `pydantic` v2, `pytest`.

**Spec:** `docs/REQUIREMENTS.md` (§3.1 MVP 범위), `docs/02-architecture.md` (본 계획이 그대로 구현하는 설계)

## Global Constraints

- Python >= 3.12 (repoview와 동일 컨벤션).
- 런타임 의존성은 `openai`, `pydantic`만 사용한다 — 그 외 새 의존성 추가 금지(YAGNI).
- 기본 모델명은 정확히 `exaone3.5:7.8b` (환경변수 `JUDGPT_MODEL`로 교체 가능).
- Ollama 엔드포인트 기본값은 정확히 `http://localhost:11434/v1` (환경변수 `OLLAMA_BASE_URL`로 교체 가능).
- 고지 문구는 정확히 다음 문자열이어야 한다: `이 결과는 참고용 정보이며 법적 판단이 아닙니다. 실제 법적 대응이 필요하면 변호사와 상담하세요.`
- `AnalysisResult.expressions`의 `type` 필드는 정확히 다음 7개 값만 허용한다: `욕설`, `성희롱`, `협박`, `모욕`, `명예훼손`, `성적 발언`, `기타`. `risk` 필드는 정확히 `높음`/`중간`/`낮음`만 허용한다.
- 기본 `pytest` 실행은 네트워크(실제 Ollama)를 호출하지 않는다 — 실제 Ollama가 필요한 테스트는 전부 `@pytest.mark.integration`으로 표시하고 기본 실행에서 제외한다.

---

## File Structure

```
judgpt/
  pyproject.toml
  CLAUDE.md
  judgpt/
    __init__.py
    config.py       # 모델명/엔드포인트 환경변수
    llm.py          # LLM Protocol, FakeLLM, OllamaLLM
    schema.py       # Expression, AnalysisResult (Pydantic)
    prompt.py       # 시스템 프롬프트 + build_messages()
    analyzer.py      # analyze(): LLM 호출 -> 파싱/검증 -> 실패 시 1회 재시도
    report.py       # AnalysisResult -> 사람이 읽는 리포트 문자열, DISCLAIMER 상수
    analyze.py      # CLI 진입점 (run(), main())
  tests/
    fixtures/
      harmful_example.txt
      benign_example.txt
    test_llm.py
    test_schema.py
    test_prompt.py
    test_analyzer.py
    test_report.py
    test_analyze_cli.py
    test_integration.py
```

---

### Task 1: 프로젝트 스캐폴딩 + LLM Protocol/FakeLLM

**Files:**
- Create: `pyproject.toml`
- Create: `judgpt/__init__.py` (빈 파일)
- Create: `judgpt/llm.py`
- Test: `tests/test_llm.py`

**Interfaces:**
- Produces: `judgpt.llm.LLM` (Protocol, `call(self, messages: list[dict]) -> str`), `judgpt.llm.FakeLLM` (생성자 `FakeLLM(responses: list[str])`, `.call(messages)`, `.received_messages: list[list[dict]]`)

- [ ] **Step 1: `pyproject.toml` 작성**

```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "judgpt"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "openai>=1.50",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "integration: 로컬에 실제 Ollama가 떠 있어야 통과하는 테스트 (기본 실행에서 제외)",
]

[tool.setuptools.packages.find]
include = ["judgpt*"]
```

- [ ] **Step 2: `judgpt/__init__.py` 생성 (빈 파일)**

- [ ] **Step 3: 의존성 설치**

Run: `pip install -e ".[dev]"`

- [ ] **Step 4: 실패하는 테스트 작성 — `tests/test_llm.py`**

```python
import pytest

from judgpt.llm import FakeLLM


def test_fake_llm_returns_prepared_responses_in_order():
    llm = FakeLLM(["첫 응답", "두번째 응답"])

    first = llm.call([{"role": "user", "content": "질문1"}])
    second = llm.call([{"role": "user", "content": "질문2"}])

    assert first == "첫 응답"
    assert second == "두번째 응답"


def test_fake_llm_records_received_messages():
    llm = FakeLLM(["응답"])
    messages = [{"role": "user", "content": "질문"}]

    llm.call(messages)

    assert llm.received_messages == [messages]


def test_fake_llm_raises_when_exhausted():
    llm = FakeLLM(["한 번뿐"])
    llm.call([])
    with pytest.raises(AssertionError):
        llm.call([])
```

- [ ] **Step 5: 테스트 실행 — 실패 확인**

Run: `pytest tests/test_llm.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'judgpt.llm'`

- [ ] **Step 6: `judgpt/llm.py` 구현**

```python
from typing import Protocol


class LLM(Protocol):
    def call(self, messages: list[dict]) -> str: ...


class FakeLLM:
    """테스트용. 준비된 응답을 순서대로 반환하고 받은 메시지를 기록한다."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.received_messages: list[list[dict]] = []

    def call(self, messages: list[dict]) -> str:
        self.received_messages.append(list(messages))
        if not self._responses:
            raise AssertionError("FakeLLM: 준비된 응답을 모두 소진했습니다")
        return self._responses.pop(0)
```

- [ ] **Step 7: 테스트 실행 — 통과 확인**

Run: `pytest tests/test_llm.py -v`
Expected: PASS (3 passed)

- [ ] **Step 8: 커밋**

```bash
git add pyproject.toml judgpt/__init__.py judgpt/llm.py tests/test_llm.py
git commit -m "judgpt 프로젝트 스캐폴딩과 LLM Protocol/FakeLLM 추가"
```

---

### Task 2: 출력 스키마 (Pydantic)

**Files:**
- Create: `judgpt/schema.py`
- Test: `tests/test_schema.py`

**Interfaces:**
- Produces: `judgpt.schema.Expression` (필드: `text: str`, `type: Literal[...]`, `target: str | None`, `risk: Literal[...]`, `context: str | None`), `judgpt.schema.AnalysisResult` (필드: `expressions: list[Expression]`)

- [ ] **Step 1: 실패하는 테스트 작성 — `tests/test_schema.py`**

```python
import pytest
from pydantic import ValidationError

from judgpt.schema import AnalysisResult, Expression


def test_expression_parses_full_valid_data():
    expr = Expression.model_validate({
        "text": "너 같은 새끼는 사회에서 없어져야 한다",
        "type": "모욕",
        "target": "상대방",
        "risk": "높음",
        "context": None,
    })

    assert expr.text == "너 같은 새끼는 사회에서 없어져야 한다"
    assert expr.type == "모욕"
    assert expr.target == "상대방"
    assert expr.risk == "높음"
    assert expr.context is None


def test_expression_target_and_context_are_optional():
    expr = Expression.model_validate({
        "text": "욕설 예시",
        "type": "욕설",
        "risk": "중간",
    })

    assert expr.target is None
    assert expr.context is None


def test_expression_rejects_unknown_type():
    with pytest.raises(ValidationError):
        Expression.model_validate({
            "text": "예시",
            "type": "알수없음",
            "risk": "낮음",
        })


def test_expression_rejects_unknown_risk():
    with pytest.raises(ValidationError):
        Expression.model_validate({
            "text": "예시",
            "type": "욕설",
            "risk": "매우높음",
        })


def test_analysis_result_holds_list_of_expressions():
    result = AnalysisResult.model_validate({
        "expressions": [
            {"text": "예시1", "type": "욕설", "risk": "낮음"},
            {"text": "예시2", "type": "협박", "risk": "높음"},
        ]
    })

    assert len(result.expressions) == 2
    assert result.expressions[0].type == "욕설"


def test_analysis_result_allows_empty_expressions():
    result = AnalysisResult.model_validate({"expressions": []})
    assert result.expressions == []
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `pytest tests/test_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'judgpt.schema'`

- [ ] **Step 3: `judgpt/schema.py` 구현**

```python
from typing import Literal

from pydantic import BaseModel

ExpressionType = Literal["욕설", "성희롱", "협박", "모욕", "명예훼손", "성적 발언", "기타"]
RiskLevel = Literal["높음", "중간", "낮음"]


class Expression(BaseModel):
    text: str
    type: ExpressionType
    risk: RiskLevel
    target: str | None = None
    context: str | None = None


class AnalysisResult(BaseModel):
    expressions: list[Expression]
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

Run: `pytest tests/test_schema.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: 커밋**

```bash
git add judgpt/schema.py tests/test_schema.py
git commit -m "유해 표현 분석 결과 Pydantic 스키마 추가"
```

---

### Task 3: 프롬프트 조립

**Files:**
- Create: `judgpt/prompt.py`
- Test: `tests/test_prompt.py`

**Interfaces:**
- Produces: `judgpt.prompt.build_messages(chat_text: str) -> list[dict]` (길이 2: `{"role": "system", ...}`, `{"role": "user", "content": chat_text}`)

- [ ] **Step 1: 실패하는 테스트 작성 — `tests/test_prompt.py`**

```python
from judgpt.prompt import build_messages


def test_build_messages_returns_system_then_user():
    messages = build_messages("A: 안녕\nB: 안녕하세요")

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1] == {"role": "user", "content": "A: 안녕\nB: 안녕하세요"}


def test_system_prompt_mentions_all_expression_types():
    messages = build_messages("아무 텍스트")
    system_content = messages[0]["content"]

    for expression_type in ["욕설", "성희롱", "협박", "모욕", "명예훼손"]:
        assert expression_type in system_content


def test_system_prompt_forbids_citing_law_or_case(): 
    """MVP는 법률 RAG가 없으므로, 근거 없는 법 조문/판례 언급을 금지해야 한다
    (REQUIREMENTS.md §4, docs/02-architecture.md §4)."""
    messages = build_messages("아무 텍스트")
    system_content = messages[0]["content"]

    assert "법 조문" in system_content or "판례" in system_content


def test_system_prompt_requires_json_only_response():
    messages = build_messages("아무 텍스트")
    system_content = messages[0]["content"]

    assert "JSON" in system_content
    assert "expressions" in system_content
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `pytest tests/test_prompt.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'judgpt.prompt'`

- [ ] **Step 3: `judgpt/prompt.py` 구현**

```python
SYSTEM_PROMPT = """당신은 채팅 대화 텍스트를 분석해 유해 표현을 찾아내는 보조 도구다.

## 할 일
1. 대화에서 욕설, 성희롱, 협박, 모욕, 명예훼손, 성적 발언에 해당할 수 있는 표현을 찾는다.
2. 각 표현에 대해 대상, 위험도(높음/중간/낮음), 그리고 문맥(반복성·공개성·상대방 거부 이후 반복 여부 등)을 판단한다.
3. 이름·전화번호·주소 등 구체적인 개인정보가 표현에 포함되어 있으면 마스킹해서 인용한다(예: "김철수" -> "김OO").

## 절대 하지 말 것
- 관련 법 조문이나 판례를 언급하거나 인용하지 마라. 근거 문서 없이 법률 판단을 지어내면 안 된다.
- "고소 가능" 여부처럼 법적 결론을 단정하지 마라. 이 분석은 표현 탐지와 위험도 판단까지만 한다.

## 출력 형식
반드시 아래 스키마의 JSON 객체 하나만 응답한다. 다른 설명 텍스트를 덧붙이지 마라.

{
  "expressions": [
    {
      "text": "인용된 표현 (개인정보는 마스킹)",
      "type": "욕설 | 성희롱 | 협박 | 모욕 | 명예훼손 | 성적 발언 | 기타",
      "risk": "높음 | 중간 | 낮음",
      "target": "표현의 대상 (특정할 수 없으면 생략 가능)",
      "context": "판단 근거가 된 맥락 (없으면 생략 가능)"
    }
  ]
}

문제되는 표현이 전혀 없으면 "expressions": [] 로 응답한다.
"""


def build_messages(chat_text: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": chat_text},
    ]
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

Run: `pytest tests/test_prompt.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 커밋**

```bash
git add judgpt/prompt.py tests/test_prompt.py
git commit -m "유해 표현 탐지용 시스템 프롬프트와 메시지 조립 함수 추가"
```

---

### Task 4: 분석 오케스트레이션 (파싱 + 1회 재시도)

**Files:**
- Create: `judgpt/analyzer.py`
- Test: `tests/test_analyzer.py`

**Interfaces:**
- Consumes: `judgpt.llm.LLM`, `judgpt.llm.FakeLLM` (Task 1), `judgpt.schema.AnalysisResult` (Task 2), `judgpt.prompt.build_messages` (Task 3)
- Produces: `judgpt.analyzer.AnalysisError` (Exception 서브클래스), `judgpt.analyzer.analyze(chat_text: str, llm: LLM) -> AnalysisResult`

- [ ] **Step 1: 실패하는 테스트 작성 — `tests/test_analyzer.py`**

```python
import pytest

from judgpt.analyzer import AnalysisError, analyze
from judgpt.llm import FakeLLM


def test_analyze_returns_result_on_valid_first_response():
    llm = FakeLLM(['{"expressions": [{"text": "예시", "type": "욕설", "risk": "낮음"}]}'])

    result = analyze("A: 예시", llm)

    assert len(result.expressions) == 1
    assert result.expressions[0].text == "예시"
    assert len(llm.received_messages) == 1


def test_analyze_retries_once_on_invalid_json_then_succeeds():
    llm = FakeLLM([
        "이건 JSON이 아님",
        '{"expressions": []}',
    ])

    result = analyze("A: 예시", llm)

    assert result.expressions == []
    assert len(llm.received_messages) == 2
    # 재시도 메시지에는 최초 대화 + 실패한 응답 + 재요청이 포함되어야 한다
    retry_messages = llm.received_messages[1]
    assert len(retry_messages) == 4
    assert retry_messages[2] == {"role": "assistant", "content": "이건 JSON이 아님"}
    assert retry_messages[3]["role"] == "user"


def test_analyze_retries_once_on_schema_violation_then_succeeds():
    llm = FakeLLM([
        '{"expressions": [{"text": "예시", "type": "알수없는유형", "risk": "낮음"}]}',
        '{"expressions": []}',
    ])

    result = analyze("A: 예시", llm)

    assert result.expressions == []
    assert len(llm.received_messages) == 2


def test_analyze_raises_after_second_failure():
    llm = FakeLLM(["JSON 아님", "여전히 JSON 아님"])

    with pytest.raises(AnalysisError):
        analyze("A: 예시", llm)

    assert len(llm.received_messages) == 2
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `pytest tests/test_analyzer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'judgpt.analyzer'`

- [ ] **Step 3: `judgpt/analyzer.py` 구현**

```python
import json

from pydantic import ValidationError

from judgpt.llm import LLM
from judgpt.prompt import build_messages
from judgpt.schema import AnalysisResult


class AnalysisError(Exception):
    pass


def analyze(chat_text: str, llm: LLM) -> AnalysisResult:
    messages = build_messages(chat_text)
    raw = llm.call(messages)

    try:
        return _parse(raw)
    except (json.JSONDecodeError, ValidationError) as exc:
        retry_messages = messages + [
            {"role": "assistant", "content": raw},
            {
                "role": "user",
                "content": (
                    f"방금 응답이 올바른 JSON 스키마가 아니었습니다 ({exc}). "
                    "설명 없이 스키마에 맞는 JSON 객체 하나만 다시 응답하세요."
                ),
            },
        ]
        raw_retry = llm.call(retry_messages)
        try:
            return _parse(raw_retry)
        except (json.JSONDecodeError, ValidationError) as exc2:
            raise AnalysisError(f"모델 응답이 올바른 JSON 형식이 아닙니다: {exc2}") from exc2


def _parse(raw: str) -> AnalysisResult:
    data = json.loads(raw)
    return AnalysisResult.model_validate(data)
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

Run: `pytest tests/test_analyzer.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 커밋**

```bash
git add judgpt/analyzer.py tests/test_analyzer.py
git commit -m "LLM 응답 파싱/검증과 1회 재시도 로직 추가"
```

---

### Task 5: 리포트 포맷팅

**Files:**
- Create: `judgpt/report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: `judgpt.schema.AnalysisResult`, `judgpt.schema.Expression` (Task 2)
- Produces: `judgpt.report.DISCLAIMER` (정확히 Global Constraints의 고지 문구), `judgpt.report.format_report(result: AnalysisResult) -> str`

- [ ] **Step 1: 실패하는 테스트 작성 — `tests/test_report.py`**

```python
from judgpt.report import DISCLAIMER, format_report
from judgpt.schema import AnalysisResult, Expression


def test_format_report_no_expressions():
    result = AnalysisResult(expressions=[])

    report = format_report(result)

    assert "문제 표현이 발견되지 않았습니다" in report
    assert DISCLAIMER in report


def test_format_report_includes_count_and_all_fields():
    result = AnalysisResult(expressions=[
        Expression(
            text="너 같은 새끼는 사회에서 없어져야 한다",
            type="모욕",
            risk="높음",
            target="상대방",
            context="반복적인 비하 발언",
        ),
    ])

    report = format_report(result)

    assert "발견된 문제 표현: 1건" in report
    assert '"너 같은 새끼는 사회에서 없어져야 한다"' in report
    assert "유형: 모욕" in report
    assert "대상: 상대방" in report
    assert "위험도: 높음" in report
    assert "맥락: 반복적인 비하 발언" in report
    assert DISCLAIMER in report


def test_format_report_omits_missing_optional_fields():
    result = AnalysisResult(expressions=[
        Expression(text="예시", type="욕설", risk="낮음"),
    ])

    report = format_report(result)

    assert "대상:" not in report
    assert "맥락:" not in report


def test_disclaimer_exact_text():
    assert DISCLAIMER == (
        "이 결과는 참고용 정보이며 법적 판단이 아닙니다. "
        "실제 법적 대응이 필요하면 변호사와 상담하세요."
    )
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `pytest tests/test_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'judgpt.report'`

- [ ] **Step 3: `judgpt/report.py` 구현**

```python
from judgpt.schema import AnalysisResult

DISCLAIMER = (
    "이 결과는 참고용 정보이며 법적 판단이 아닙니다. "
    "실제 법적 대응이 필요하면 변호사와 상담하세요."
)


def format_report(result: AnalysisResult) -> str:
    lines = ["[분석 결과]", ""]

    if not result.expressions:
        lines.append("문제 표현이 발견되지 않았습니다.")
    else:
        lines.append(f"⚠️ 발견된 문제 표현: {len(result.expressions)}건")
        lines.append("")
        for i, expr in enumerate(result.expressions, start=1):
            lines.append(f'{i}. "{expr.text}"')
            lines.append(f"   유형: {expr.type}")
            if expr.target:
                lines.append(f"   대상: {expr.target}")
            lines.append(f"   위험도: {expr.risk}")
            if expr.context:
                lines.append(f"   맥락: {expr.context}")
            lines.append("")

    lines.append("─" * 20)
    lines.append(DISCLAIMER)
    return "\n".join(lines)
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

Run: `pytest tests/test_report.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 커밋**

```bash
git add judgpt/report.py tests/test_report.py
git commit -m "분석 결과를 사람이 읽는 리포트로 포맷하는 기능 추가"
```

---

### Task 6: 설정값 + 실제 Ollama 클라이언트

**Files:**
- Create: `judgpt/config.py`
- Modify: `judgpt/llm.py` (Task 1에서 만든 `LLM`/`FakeLLM` 아래에 `OllamaLLM` 추가)
- Test: `tests/test_config.py`
- Modify: `tests/test_llm.py` (Task 1에서 만든 테스트 아래에 `OllamaLLM` 관련 테스트 추가)

**Interfaces:**
- Consumes: `judgpt.llm.LLM` (Task 1)
- Produces: `judgpt.config.MODEL` (str, 기본 `"exaone3.5:7.8b"`), `judgpt.config.OLLAMA_BASE_URL` (str, 기본 `"http://localhost:11434/v1"`), `judgpt.llm.OllamaLLM` (생성자 `OllamaLLM(model: str, base_url: str)`, `.call(messages: list[dict]) -> str`)

- [ ] **Step 1: 실패하는 테스트 작성 — `tests/test_config.py`**

```python
import importlib

from judgpt import config


def test_model_defaults_to_exaone(monkeypatch):
    monkeypatch.delenv("JUDGPT_MODEL", raising=False)
    importlib.reload(config)

    assert config.MODEL == "exaone3.5:7.8b"


def test_ollama_base_url_defaults_to_localhost(monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    importlib.reload(config)

    assert config.OLLAMA_BASE_URL == "http://localhost:11434/v1"


def test_model_env_var_overrides_default(monkeypatch):
    monkeypatch.setenv("JUDGPT_MODEL", "qwen2.5:7b")
    importlib.reload(config)

    assert config.MODEL == "qwen2.5:7b"

    monkeypatch.delenv("JUDGPT_MODEL", raising=False)
    importlib.reload(config)
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'judgpt.config'`

- [ ] **Step 3: `judgpt/config.py` 구현**

```python
import os

MODEL = os.getenv("JUDGPT_MODEL", "exaone3.5:7.8b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

Run: `pytest tests/test_config.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: `tests/test_llm.py`에 `OllamaLLM` 테스트 추가 (파일 끝에 추가)**

```python
from judgpt.llm import OllamaLLM


def test_ollama_llm_targets_configured_base_url():
    llm = OllamaLLM(model="exaone3.5:7.8b", base_url="http://localhost:11434/v1")

    assert llm.model == "exaone3.5:7.8b"
    assert "11434" in str(llm._client.base_url)
    assert llm._client.api_key == "ollama"


def test_ollama_llm_call_requests_json_object_format(monkeypatch):
    captured_kwargs = {}

    class _FakeMessage:
        content = '{"expressions": []}'

    class _FakeChoice:
        message = _FakeMessage()

    class _FakeCompletion:
        choices = [_FakeChoice()]

    class _FakeCompletions:
        def create(self, **kwargs):
            captured_kwargs.update(kwargs)
            return _FakeCompletion()

    class _FakeChat:
        completions = _FakeCompletions()

    llm = OllamaLLM(model="exaone3.5:7.8b", base_url="http://localhost:11434/v1")
    llm._client.chat = _FakeChat()

    result = llm.call([{"role": "user", "content": "질문"}])

    assert result == '{"expressions": []}'
    assert captured_kwargs["model"] == "exaone3.5:7.8b"
    assert captured_kwargs["messages"] == [{"role": "user", "content": "질문"}]
    assert captured_kwargs["response_format"] == {"type": "json_object"}
```

- [ ] **Step 6: `judgpt/llm.py`에 `OllamaLLM` 추가 (파일 끝에 추가)**

```python
class OllamaLLM:
    """Ollama의 OpenAI 호환 엔드포인트(/v1/chat/completions)를 호출한다."""

    def __init__(self, model: str, base_url: str) -> None:
        from openai import OpenAI

        self.model = model
        self._client = OpenAI(base_url=base_url, api_key="ollama")

    def call(self, messages: list[dict]) -> str:
        completion = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"},
        )
        return completion.choices[0].message.content
```

- [ ] **Step 7: 테스트 실행 — 통과 확인**

Run: `pytest tests/test_llm.py tests/test_config.py -v`
Expected: PASS (전부 통과, `OllamaLLM` 관련 2건 포함)

- [ ] **Step 8: 커밋**

```bash
git add judgpt/config.py judgpt/llm.py tests/test_config.py tests/test_llm.py
git commit -m "모델/엔드포인트 설정값과 실제 Ollama 클라이언트 추가"
```

---

### Task 7: CLI 진입점

**Files:**
- Create: `judgpt/analyze.py`
- Test: `tests/test_analyze_cli.py`

**Interfaces:**
- Consumes: `judgpt.llm.LLM`, `judgpt.llm.FakeLLM`, `judgpt.llm.OllamaLLM` (Task 1, 6), `judgpt.analyzer.analyze`, `judgpt.analyzer.AnalysisError` (Task 4), `judgpt.report.format_report` (Task 5), `judgpt.config.MODEL`, `judgpt.config.OLLAMA_BASE_URL` (Task 6)
- Produces: `judgpt.analyze.run(chat_text: str, llm: LLM, as_json: bool) -> str`, `judgpt.analyze.main(argv: list[str] | None = None, llm: LLM | None = None) -> None`

- [ ] **Step 1: 실패하는 테스트 작성 — `tests/test_analyze_cli.py`**

```python
import json

import pytest

from judgpt.analyze import main, run
from judgpt.llm import FakeLLM
from judgpt.report import DISCLAIMER


def test_run_returns_human_report_by_default():
    llm = FakeLLM(['{"expressions": []}'])

    output = run("A: 안녕", llm, as_json=False)

    assert "문제 표현이 발견되지 않았습니다" in output
    assert DISCLAIMER in output


def test_run_returns_raw_json_when_requested():
    llm = FakeLLM(['{"expressions": []}'])

    output = run("A: 안녕", llm, as_json=True)

    assert json.loads(output) == {"expressions": []}


def test_run_raises_system_exit_on_analysis_failure():
    llm = FakeLLM(["JSON 아님", "여전히 JSON 아님"])

    with pytest.raises(SystemExit):
        run("A: 안녕", llm, as_json=False)


def test_main_reads_file_and_prints_report(tmp_path, capsys):
    chat_file = tmp_path / "chat.txt"
    chat_file.write_text("A: 안녕", encoding="utf-8")
    fake = FakeLLM(['{"expressions": []}'])

    main(["--file", str(chat_file)], llm=fake)

    captured = capsys.readouterr()
    assert "문제 표현이 발견되지 않았습니다" in captured.out
    assert DISCLAIMER in captured.out


def test_main_json_flag_outputs_valid_json(tmp_path, capsys):
    chat_file = tmp_path / "chat.txt"
    chat_file.write_text("A: 안녕", encoding="utf-8")
    fake = FakeLLM(['{"expressions": []}'])

    main(["--file", str(chat_file), "--json"], llm=fake)

    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"expressions": []}


def test_main_reads_stdin_when_no_file_given(monkeypatch, capsys):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("A: 안녕"))
    fake = FakeLLM(['{"expressions": []}'])

    main([], llm=fake)

    captured = capsys.readouterr()
    assert "문제 표현이 발견되지 않았습니다" in captured.out


def test_main_exits_on_empty_input(tmp_path):
    chat_file = tmp_path / "chat.txt"
    chat_file.write_text("   ", encoding="utf-8")

    with pytest.raises(SystemExit, match="입력이 비어 있습니다"):
        main(["--file", str(chat_file)], llm=FakeLLM([]))
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `pytest tests/test_analyze_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'judgpt.analyze'`

- [ ] **Step 3: `judgpt/analyze.py` 구현**

```python
import argparse
import json
import sys

from judgpt import config
from judgpt.analyzer import AnalysisError, analyze
from judgpt.llm import LLM, OllamaLLM
from judgpt.report import format_report


def run(chat_text: str, llm: LLM, as_json: bool) -> str:
    try:
        result = analyze(chat_text, llm)
    except AnalysisError as exc:
        raise SystemExit(str(exc)) from exc

    if as_json:
        return json.dumps(result.model_dump(), ensure_ascii=False, indent=2)
    return format_report(result)


def main(argv: list[str] | None = None, llm: LLM | None = None) -> None:
    parser = argparse.ArgumentParser(description="채팅 로그에서 유해 표현을 탐지한다")
    parser.add_argument("--file", help="분석할 채팅 텍스트 파일 경로. 생략 시 stdin에서 읽는다.")
    parser.add_argument(
        "--json", action="store_true", help="사람이 읽는 리포트 대신 원본 JSON을 출력한다"
    )
    args = parser.parse_args(argv)

    if args.file:
        with open(args.file, encoding="utf-8") as f:
            chat_text = f.read()
    else:
        chat_text = sys.stdin.read()

    if not chat_text.strip():
        raise SystemExit("입력이 비어 있습니다")

    if llm is None:
        llm = OllamaLLM(model=config.MODEL, base_url=config.OLLAMA_BASE_URL)

    print(run(chat_text, llm, args.json))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

Run: `pytest tests/test_analyze_cli.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: 커밋**

```bash
git add judgpt/analyze.py tests/test_analyze_cli.py
git commit -m "CLI 진입점(python -m judgpt.analyze) 추가"
```

---

### Task 8: 통합 테스트, fixtures, CLAUDE.md

**Files:**
- Create: `tests/fixtures/harmful_example.txt`
- Create: `tests/fixtures/benign_example.txt`
- Create: `tests/test_integration.py`
- Create: `CLAUDE.md`

**Interfaces:**
- Consumes: `judgpt.analyzer.analyze` (Task 4), `judgpt.llm.OllamaLLM` (Task 6), `judgpt.config.MODEL`, `judgpt.config.OLLAMA_BASE_URL` (Task 6)

- [ ] **Step 1: fixture 작성 — `tests/fixtures/harmful_example.txt`**

```
A: 너 진짜 뭐하는 짓이야
B: 너 같은 새끼는 사회에서 없어져야 한다
A: 그만해
B: 사진 뿌려버린다
```

- [ ] **Step 2: fixture 작성 — `tests/fixtures/benign_example.txt`**

```
A: 오늘 저녁 뭐 먹을까?
B: 국밥 어때
A: 좋아 가자
```

- [ ] **Step 3: 통합 테스트 작성 — `tests/test_integration.py`**

```python
from pathlib import Path

import pytest

from judgpt.analyzer import analyze
from judgpt.config import MODEL, OLLAMA_BASE_URL
from judgpt.llm import OllamaLLM

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.integration
def test_analyze_detects_obvious_insult_and_threat():
    chat_text = (FIXTURES / "harmful_example.txt").read_text(encoding="utf-8")
    llm = OllamaLLM(model=MODEL, base_url=OLLAMA_BASE_URL)

    result = analyze(chat_text, llm)

    assert len(result.expressions) >= 1


@pytest.mark.integration
def test_analyze_benign_chat_finds_nothing():
    chat_text = (FIXTURES / "benign_example.txt").read_text(encoding="utf-8")
    llm = OllamaLLM(model=MODEL, base_url=OLLAMA_BASE_URL)

    result = analyze(chat_text, llm)

    assert result.expressions == []
```

- [ ] **Step 4: 기본 테스트 스위트가 통합 테스트를 건너뛰는지 확인**

Run: `pytest -v`
Expected: 이전 태스크의 모든 테스트가 PASS, `test_integration.py`의 2건은 `deselected` 되어 실행되지 않음 (marker가 기본 실행에서 제외되므로)

- [ ] **Step 5: (선택, 로컬에 Ollama와 모델이 준비된 경우에만) 통합 테스트 실제 실행**

Run: `ollama pull exaone3.5:7.8b` (최초 1회) 후 `pytest -m integration -v`
Expected: PASS (2 passed) — 실패하면 `docs/02-architecture.md` §10의 미해결 질문(모델 비교)으로 돌아가 프롬프트나 모델을 조정한다.

- [ ] **Step 6: `CLAUDE.md` 작성**

```markdown
# CLAUDE.md

이 파일은 Claude Code가 이 저장소에서 작업할 때 참고할 안내를 담고 있다.

## 명령어

- 설치: `pip install -e ".[dev]"`
- 전체 테스트(네트워크 불필요, Ollama 없어도 통과): `pytest`
- 통합 테스트 포함(로컬에 Ollama가 떠 있고 `ollama pull exaone3.5:7.8b`로 모델을 받아둔 경우에만): `pytest -m integration`
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
- `report.py` — `AnalysisResult`를 사람이 읽는 리포트 문자열로 변환. `DISCLAIMER`(참고용 정보 고지)는 항상 고정 문구로 붙인다 — 모델 출력에 맡기지 않는다.
- `analyze.py` — CLI 진입점. `run()`은 순수 함수(테스트하기 쉬움), `main()`은 argparse + 파일/stdin 읽기 + `OllamaLLM` 생성 담당. `main(argv, llm=...)`처럼 `llm`을 주입할 수 있어 테스트가 실제 Ollama 없이 전체 CLI 흐름을 검증한다.

모델은 기본 `exaone3.5:7.8b`(한국어 특화)이고 `qwen2.5:7b`로 교체해볼 수 있다 — 둘 중 어느 쪽이 이 작업에 더 나은지는 아직 실측 전이다(`docs/02-architecture.md` §10).

## 실행 전 준비

Ollama가 로컬에 설치되어 있고 `ollama pull exaone3.5:7.8b`로 모델을 받아둬야 `python -m judgpt.analyze`가 실제로 동작한다. 없으면 연결 오류가 난다 — 단, 단위 테스트(`pytest`, 통합 마커 제외)는 전부 `FakeLLM`을 쓰므로 Ollama 설치 여부와 무관하게 통과한다.

## 범위 밖 (아직 없음)

- 법률 RAG(관련 법 조문/판례 검색) — `docs/REQUIREMENTS.md` §3.2, 2차 확장.
- 웹 UI, 카카오톡 등 메신저 포맷 자동 파싱, 자동 채점 eval 하네스.
```

- [ ] **Step 7: 커밋**

```bash
git add tests/fixtures tests/test_integration.py CLAUDE.md
git commit -m "통합 테스트 fixture와 CLAUDE.md 추가"
```

---

## Self-Review 메모 (계획 작성자용, 실행 시 참고만)

- **스펙 커버리지:** REQUIREMENTS.md §3.1(마스킹+탐지+문맥분석 단일 프롬프트, RAG 제외) → Task 3/4. §4(법적 고지, 법조문 지어내지 않기) → Task 3(프롬프트 제약) + Task 5(고정 DISCLAIMER). §7 CLI 설계 → Task 7. §8 테스트 전략(FakeLLM, integration 마커 분리) → Task 1/6/8. 전부 커버됨.
- **타입 일관성:** `LLM.call(messages: list[dict]) -> str` 시그니처가 Task 1(정의)·4(analyzer 소비)·6(OllamaLLM 구현)·7(CLI 소비) 전체에서 동일. `AnalysisResult`/`Expression` 필드명이 Task 2(정의)·4·5·7에서 동일하게 사용됨.
- **플레이스홀더:** 없음 — 모든 스텝에 실제 코드/실제 명령어 포함.
