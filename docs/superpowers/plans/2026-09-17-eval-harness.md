# judgpt Eval Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 골든 데이터셋을 기준으로 `analyze()`의 유해 표현 탐지 정확도(type별 precision/recall/F1)를 자동으로 측정하는 `python -m judgpt.eval` CLI를 추가한다.

**Architecture:** 사람이 직접 작성한 골든 데이터셋(`judgpt/eval_data/golden.json`)을 로드해, 각 케이스마다 기존 `analyze()`를 실제로 호출하고 그 결과를 정답과 표현 단위로 그리디 매칭해 TP/FP/FN을 센다. 채점 로직(`score_case`)은 LLM 없이 순수 함수로 분리해 유닛테스트로 전부 커버하고, LLM 호출이 필요한 `run_eval`은 별도로 얇게 감싼다.

**Tech Stack:** Python 3.12+, 기존 MVP/법률 RAG와 동일(`openai`, `pydantic`) — 새 런타임 의존성 없음.

**Spec:** `docs/superpowers/specs/2026-09-17-eval-harness-design.md`

## Global Constraints

- `risk`(위험도) 필드는 채점(precision/recall/F1)에 포함하지 않는다 — 매칭된(TP) 표현의 예측 risk 분포만 리포트에 참고 통계로 곁들인다.
- `--legal`(조문/판례 RAG)은 이번 평가 범위에서 제외한다 — 탐지 정확도만 측정한다.
- 골든 데이터셋은 사람이 직접 작성한 것만 사용한다 — 자동 대량 수집 금지.
- 매칭은 표현 단위 그리디 1:1 매칭이다: `predicted.type == expected.type` 그리고 부분 문자열 포함(`expected.text in predicted.text` 또는 `predicted.text in expected.text`)일 때만 매칭. 한 번 매칭된 expected는 재사용하지 않는다.
- 골든셋 전체를 실제 Ollama로 돌리는 것은 자동 테스트 스위트(`pytest`)에 포함하지 않는다 — 느리고 비결정적이라 사람이 `python -m judgpt.eval`을 직접 실행해 확인한다.
- 새 런타임 의존성을 추가하지 않는다 — 기존 `openai`, `pydantic`만 사용.
- MVP 파일(`judgpt/analyzer.py`, `judgpt/schema.py`, `judgpt/llm.py`)과 기존 법률 RAG 파일(`judgpt/legal_rag.py`, `judgpt/report.py`, `judgpt/embedder.py`)은 이 계획의 어떤 태스크에서도 수정하지 않는다.

---

## File Structure

```
judgpt/
  eval.py                      # 신규: CaseScore, score_case, CaseResult, EvalReport, run_eval, format_eval_report, main
  eval_data/
    __init__.py                 # 신규 (빈 파일)
    golden.py                    # 신규: GoldenExpectation, GoldenCase, load_golden_cases
    golden.json                   # 신규: 사람이 직접 작성한 골든 데이터셋 15건
tests/
  test_eval_data_golden.py      # 신규
  test_eval.py                   # 신규
```

---

### Task 1: 골든 데이터셋 모델 + 로더 + 초기 데이터

**Files:**
- Create: `judgpt/eval_data/__init__.py` (빈 파일)
- Create: `judgpt/eval_data/golden.py`
- Create: `judgpt/eval_data/golden.json`
- Test: `tests/test_eval_data_golden.py`

**Interfaces:**
- Consumes: `judgpt.schema.ExpressionType` (MVP, 기존)
- Produces: `judgpt.eval_data.golden.GoldenExpectation` (Pydantic, 필드: `text: str`, `type: ExpressionType`), `judgpt.eval_data.golden.GoldenCase` (Pydantic, 필드: `chat_text: str`, `expected: list[GoldenExpectation]`), `judgpt.eval_data.golden.load_golden_cases(path: Path = DEFAULT_GOLDEN_PATH) -> list[GoldenCase]`

- [ ] **Step 1: `judgpt/eval_data/__init__.py` 생성 (빈 파일)**

- [ ] **Step 2: 실패하는 테스트 작성 — `tests/test_eval_data_golden.py`**

```python
from judgpt.eval_data.golden import GoldenCase, load_golden_cases


def test_load_golden_cases_returns_curated_entries():
    cases = load_golden_cases()
    assert len(cases) >= 10
    assert all(isinstance(c, GoldenCase) for c in cases)


def test_load_golden_cases_covers_each_core_type_at_least_once():
    cases = load_golden_cases()
    types_covered = {exp.type for c in cases for exp in c.expected}
    assert {"욕설", "성희롱", "협박", "모욕", "명예훼손", "성적 발언"} <= types_covered


def test_load_golden_cases_includes_benign_cases_with_no_expected():
    cases = load_golden_cases()
    assert any(c.expected == [] for c in cases)


def test_load_golden_cases_accepts_custom_path(tmp_path):
    custom_path = tmp_path / "custom_golden.json"
    custom_path.write_text(
        '[{"chat_text": "A: 안녕", "expected": []}]',
        encoding="utf-8",
    )
    cases = load_golden_cases(custom_path)
    assert len(cases) == 1
    assert cases[0].chat_text == "A: 안녕"
```

- [ ] **Step 3: 테스트 실행 — 실패 확인**

Run: `pytest tests/test_eval_data_golden.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'judgpt.eval_data'`

- [ ] **Step 4: `judgpt/eval_data/golden.json` 작성**

사람이 직접 작성한 골든 데이터셋이다. 6개 핵심 유형(욕설/성희롱/협박/모욕/명예훼손/성적 발언)을 각 2건씩 + 무해한 대화 3건, 총 15건.

```json
[
  {
    "chat_text": "A: 아씨 시발 지하철 놓쳤네\nB: ㅋㅋ 안습이다",
    "expected": [{"text": "아씨 시발", "type": "욕설"}]
  },
  {
    "chat_text": "A: 아 개빡치네 진짜\nB: 왜 그래",
    "expected": [{"text": "개빡치네", "type": "욕설"}]
  },
  {
    "chat_text": "A: 몸매 진짜 좋다ㅎㅎ\nB: 그런 말 하지 말라고 했잖아\nA: 에이 그래도 진짜 섹시한데\nB: 그만 좀 해",
    "expected": [{"text": "진짜 섹시한데", "type": "성희롱"}]
  },
  {
    "chat_text": "A: 오늘도 예쁘네 밥이나 먹자\nB: 저 그런 거 싫다고 몇 번을 말해요\nA: 한번만 만나줘 딱 한번만\nB: 그만 연락하세요",
    "expected": [{"text": "한번만 만나줘", "type": "성희롱"}]
  },
  {
    "chat_text": "A: 한번만 더 그딴 식으로 말하면 가만 안 둔다\nB: 무슨 소리야",
    "expected": [{"text": "가만 안 둔다", "type": "협박"}]
  },
  {
    "chat_text": "A: 너희 집 어딘지 알아 조심해\nB: 그게 무슨 말이야",
    "expected": [{"text": "너희 집 어딘지 알아 조심해", "type": "협박"}]
  },
  {
    "chat_text": "A: 너는 진짜 인간 쓰레기야\nB: 뭐라고?",
    "expected": [{"text": "인간 쓰레기", "type": "모욕"}]
  },
  {
    "chat_text": "A: 니가 그러고도 사람이냐 진짜 역겹다\nB: 너무하네",
    "expected": [{"text": "역겹다", "type": "모욕"}]
  },
  {
    "chat_text": "A: 쟤 예전에 회사 돈 횡령해서 잘렸대\nB: 진짜? 몰랐네",
    "expected": [{"text": "회사 돈 횡령해서 잘렸대", "type": "명예훼손"}]
  },
  {
    "chat_text": "A: 쟤 사실 양다리 걸치다 걸려서 헤어진 거래\nB: 헐 몰랐어",
    "expected": [{"text": "양다리 걸치다 걸려서 헤어진 거래", "type": "명예훼손"}]
  },
  {
    "chat_text": "A: 오늘 옷 입은 거 몸매 너무 야하다ㅋㅋ\nB: 그런 말 하지 마",
    "expected": [{"text": "몸매 너무 야하다", "type": "성적 발언"}]
  },
  {
    "chat_text": "A: 너 가슴 진짜 크다\nB: ...",
    "expected": [{"text": "가슴 진짜 크다", "type": "성적 발언"}]
  },
  {
    "chat_text": "A: 오늘 저녁 뭐 먹을까?\nB: 국밥 어때\nA: 좋아 가자",
    "expected": []
  },
  {
    "chat_text": "A: 주말에 영화 보러 갈래?\nB: 좋지 몇시에 볼까\nA: 2시 어때",
    "expected": []
  },
  {
    "chat_text": "A: 과제 다 했어?\nB: 아직 반밖에 못했어\nA: 화이팅",
    "expected": []
  }
]
```

- [ ] **Step 5: `judgpt/eval_data/golden.py` 구현**

```python
import json
from pathlib import Path

from pydantic import BaseModel

from judgpt.schema import ExpressionType

DEFAULT_GOLDEN_PATH = Path(__file__).parent / "golden.json"


class GoldenExpectation(BaseModel):
    text: str
    type: ExpressionType


class GoldenCase(BaseModel):
    chat_text: str
    expected: list[GoldenExpectation]


def load_golden_cases(path: Path = DEFAULT_GOLDEN_PATH) -> list[GoldenCase]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [GoldenCase.model_validate(entry) for entry in data]
```

- [ ] **Step 6: 테스트 실행 — 통과 확인**

Run: `pytest tests/test_eval_data_golden.py -v`
Expected: PASS (4 passed)

- [ ] **Step 7: 커밋**

```bash
git add judgpt/eval_data/__init__.py judgpt/eval_data/golden.py judgpt/eval_data/golden.json tests/test_eval_data_golden.py
git commit -m "eval 골든 데이터셋 모델·로더와 초기 15건 추가"
```

---

### Task 2: 표현 단위 채점 로직 (`score_case`)

**Files:**
- Create: `judgpt/eval.py`
- Test: `tests/test_eval.py`

**Interfaces:**
- Consumes: `judgpt.schema.Expression` (MVP, 기존), `judgpt.eval_data.golden.GoldenExpectation` (Task 1)
- Produces: `judgpt.eval.CaseScore` (Pydantic, 필드: `matched: list[Expression]`, `false_negatives: list[GoldenExpectation]`, `false_positives: list[Expression]`), `judgpt.eval.score_case(predicted: list[Expression], expected: list[GoldenExpectation]) -> CaseScore`

- [ ] **Step 1: 실패하는 테스트 작성 — `tests/test_eval.py`**

```python
from judgpt.eval import score_case
from judgpt.eval_data.golden import GoldenExpectation
from judgpt.schema import Expression


def _expr(text, type_, risk="높음"):
    return Expression(text=text, type=type_, risk=risk)


def _exp(text, type_):
    return GoldenExpectation(text=text, type=type_)


def test_score_case_matches_exact_text_and_type_as_true_positive():
    predicted = [_expr("너는 쓰레기야", "모욕")]
    expected = [_exp("너는 쓰레기야", "모욕")]

    score = score_case(predicted, expected)

    assert score.matched == predicted
    assert score.false_negatives == []
    assert score.false_positives == []


def test_score_case_matches_when_predicted_text_is_longer_substring():
    predicted = [_expr("진짜 너는 쓰레기야 정말로", "모욕")]
    expected = [_exp("너는 쓰레기야", "모욕")]

    score = score_case(predicted, expected)

    assert len(score.matched) == 1
    assert score.false_negatives == []


def test_score_case_matches_when_expected_text_is_longer_substring():
    predicted = [_expr("쓰레기야", "모욕")]
    expected = [_exp("진짜 너는 쓰레기야 정말로", "모욕")]

    score = score_case(predicted, expected)

    assert len(score.matched) == 1


def test_score_case_does_not_match_when_type_differs():
    predicted = [_expr("너는 쓰레기야", "욕설")]
    expected = [_exp("너는 쓰레기야", "모욕")]

    score = score_case(predicted, expected)

    assert score.matched == []
    assert score.false_positives == predicted
    assert score.false_negatives == expected


def test_score_case_unmatched_expected_is_false_negative():
    predicted = []
    expected = [_exp("놓친 표현", "협박")]

    score = score_case(predicted, expected)

    assert score.false_negatives == expected
    assert score.matched == []
    assert score.false_positives == []


def test_score_case_unmatched_predicted_is_false_positive():
    predicted = [_expr("과탐지된 표현", "명예훼손")]
    expected = []

    score = score_case(predicted, expected)

    assert score.false_positives == predicted
    assert score.matched == []


def test_score_case_does_not_double_match_same_expected_twice():
    predicted = [_expr("쓰레기야", "모욕"), _expr("쓰레기야", "모욕")]
    expected = [_exp("쓰레기야", "모욕")]

    score = score_case(predicted, expected)

    assert len(score.matched) == 1
    assert len(score.false_positives) == 1
    assert score.false_negatives == []
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `pytest tests/test_eval.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'judgpt.eval'`

- [ ] **Step 3: `judgpt/eval.py` 구현**

```python
from pydantic import BaseModel

from judgpt.eval_data.golden import GoldenExpectation
from judgpt.schema import Expression


class CaseScore(BaseModel):
    matched: list[Expression]
    false_negatives: list[GoldenExpectation]
    false_positives: list[Expression]


def score_case(predicted: list[Expression], expected: list[GoldenExpectation]) -> CaseScore:
    """순수 함수. LLM/Ollama 없이 유닛테스트로 전부 커버 가능.
    predicted를 순서대로 순회하며, 각 predicted마다 아직 매칭 안 된 expected 중
    (type 일치 + 부분 문자열 포함) 조건을 만족하는 첫 번째 항목과 짝짓는다."""
    remaining_expected = list(expected)
    matched: list[Expression] = []
    false_positives: list[Expression] = []

    for pred in predicted:
        match_index = None
        for i, exp in enumerate(remaining_expected):
            if pred.type == exp.type and (exp.text in pred.text or pred.text in exp.text):
                match_index = i
                break
        if match_index is None:
            false_positives.append(pred)
        else:
            matched.append(pred)
            remaining_expected.pop(match_index)

    return CaseScore(matched=matched, false_negatives=remaining_expected, false_positives=false_positives)
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

Run: `pytest tests/test_eval.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: 커밋**

```bash
git add judgpt/eval.py tests/test_eval.py
git commit -m "eval 표현단위 채점 로직(score_case) 추가"
```

---

### Task 3: 골든셋 실행 오케스트레이션 (`run_eval`)

**Files:**
- Modify: `judgpt/eval.py` (Task 2에서 만든 `CaseScore`/`score_case` 아래에 추가)
- Test: `tests/test_eval.py` (파일 끝에 추가)

**Interfaces:**
- Consumes: `judgpt.analyzer.analyze(chat_text: str, llm: LLM) -> AnalysisResult` (MVP, 기존), `judgpt.llm.LLM`, `judgpt.llm.FakeLLM` (MVP, 기존), `judgpt.eval_data.golden.GoldenCase` (Task 1), `judgpt.eval.score_case` (Task 2)
- Produces: `judgpt.eval.CaseResult` (Pydantic, 필드: `chat_text: str`, `score: CaseScore`), `judgpt.eval.EvalReport` (Pydantic, 필드: `cases: list[CaseResult]`), `judgpt.eval.run_eval(cases: list[GoldenCase], llm: LLM) -> EvalReport`

- [ ] **Step 1: 실패하는 테스트 작성 — `tests/test_eval.py`에 추가 (파일 끝)**

```python
from judgpt.eval import run_eval
from judgpt.eval_data.golden import GoldenCase, GoldenExpectation
from judgpt.llm import FakeLLM


def test_run_eval_scores_each_case_against_llm_output():
    cases = [
        GoldenCase(
            chat_text="A: 너는 쓰레기야",
            expected=[GoldenExpectation(text="너는 쓰레기야", type="모욕")],
        ),
        GoldenCase(chat_text="A: 안녕", expected=[]),
    ]
    llm = FakeLLM([
        '{"expressions": [{"text": "너는 쓰레기야", "type": "모욕", "risk": "높음"}]}',
        '{"expressions": []}',
    ])

    report = run_eval(cases, llm)

    assert len(report.cases) == 2
    assert report.cases[0].chat_text == "A: 너는 쓰레기야"
    assert len(report.cases[0].score.matched) == 1
    assert report.cases[1].score.matched == []
    assert report.cases[1].score.false_positives == []
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `pytest tests/test_eval.py -v`
Expected: FAIL with `ImportError: cannot import name 'run_eval' from 'judgpt.eval'`

- [ ] **Step 3: `judgpt/eval.py` 파일 끝에 추가**

```python
from judgpt.analyzer import analyze
from judgpt.eval_data.golden import GoldenCase
from judgpt.llm import LLM


class CaseResult(BaseModel):
    chat_text: str
    score: CaseScore


class EvalReport(BaseModel):
    cases: list[CaseResult]


def run_eval(cases: list[GoldenCase], llm: LLM) -> EvalReport:
    results = []
    for case in cases:
        analysis = analyze(case.chat_text, llm)
        score = score_case(analysis.expressions, case.expected)
        results.append(CaseResult(chat_text=case.chat_text, score=score))
    return EvalReport(cases=results)
```

새 import(`analyze`, `GoldenCase`, `LLM`)는 파일 맨 위 기존 import 블록으로 옮긴다 — `judgpt.eval_data.golden`에서는 이미 `GoldenExpectation`을 import하고 있으므로 한 줄로 합친다:

```python
from judgpt.analyzer import analyze
from judgpt.eval_data.golden import GoldenCase, GoldenExpectation
from judgpt.llm import LLM
from judgpt.schema import Expression
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

Run: `pytest tests/test_eval.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: 커밋**

```bash
git add judgpt/eval.py tests/test_eval.py
git commit -m "골든셋 전체를 실제 analyze()로 돌려 채점하는 run_eval 추가"
```

---

### Task 4: 사람이 읽는 리포트 포맷 (`format_eval_report`)

**Files:**
- Modify: `judgpt/eval.py` (Task 3에서 만든 `EvalReport` 아래에 추가)
- Test: `tests/test_eval.py` (파일 끝에 추가)

**Interfaces:**
- Consumes: `judgpt.eval.CaseScore`, `judgpt.eval.CaseResult`, `judgpt.eval.EvalReport` (Task 2, 3)
- Produces: `judgpt.eval.format_eval_report(report: EvalReport) -> str`

- [ ] **Step 1: 실패하는 테스트 작성 — `tests/test_eval.py`에 추가 (파일 끝)**

```python
from judgpt.eval import CaseResult, CaseScore, EvalReport, format_eval_report
from judgpt.eval_data.golden import GoldenExpectation
from judgpt.schema import Expression


def test_format_eval_report_includes_overall_metrics():
    report = EvalReport(cases=[
        CaseResult(
            chat_text="A: 너는 쓰레기야",
            score=CaseScore(
                matched=[Expression(text="너는 쓰레기야", type="모욕", risk="높음")],
                false_negatives=[],
                false_positives=[],
            ),
        ),
    ])

    output = format_eval_report(report)

    assert "1개 케이스" in output
    assert "Precision 1.00" in output
    assert "Recall 1.00" in output


def test_format_eval_report_lists_false_negatives_and_positives():
    report = EvalReport(cases=[
        CaseResult(
            chat_text="A: 예시",
            score=CaseScore(
                matched=[],
                false_negatives=[GoldenExpectation(text="놓친 표현", type="협박")],
                false_positives=[Expression(text="과탐지 표현", type="기타", risk="낮음")],
            ),
        ),
    ])

    output = format_eval_report(report)

    assert '"놓친 표현" (협박)' in output
    assert '"과탐지 표현" (기타)' in output


def test_format_eval_report_shows_no_basis_when_type_never_predicted():
    report = EvalReport(cases=[
        CaseResult(
            chat_text="A: 예시",
            score=CaseScore(
                matched=[],
                false_negatives=[GoldenExpectation(text="놓친 표현", type="협박")],
                false_positives=[],
            ),
        ),
    ])

    output = format_eval_report(report)

    assert "해당 없음" in output


def test_format_eval_report_includes_risk_distribution():
    report = EvalReport(cases=[
        CaseResult(
            chat_text="A: 예시",
            score=CaseScore(
                matched=[Expression(text="예시", type="모욕", risk="높음")],
                false_negatives=[],
                false_positives=[],
            ),
        ),
    ])

    output = format_eval_report(report)

    assert "높음 1 / 중간 0 / 낮음 0" in output
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `pytest tests/test_eval.py -v`
Expected: FAIL with `ImportError: cannot import name 'format_eval_report' from 'judgpt.eval'`

- [ ] **Step 3: `judgpt/eval.py` 파일 끝에 추가**

```python
def format_eval_report(report: EvalReport) -> str:
    all_scores = [c.score for c in report.cases]
    total_tp = sum(len(s.matched) for s in all_scores)
    total_fp = sum(len(s.false_positives) for s in all_scores)
    total_fn = sum(len(s.false_negatives) for s in all_scores)

    lines = [f"[Eval 결과] {len(report.cases)}개 케이스", ""]

    overall_p, overall_r, overall_f1 = _prf1(total_tp, total_fp, total_fn)
    lines.append(
        f"전체: Precision {overall_p:.2f} ({total_tp}/{total_tp + total_fp})  "
        f"Recall {overall_r:.2f} ({total_tp}/{total_tp + total_fn})  F1 {overall_f1:.2f}"
    )
    lines.append("")

    lines.append("유형별:")
    for t in sorted(_all_types(all_scores)):
        tp = sum(1 for s in all_scores for m in s.matched if m.type == t)
        fp = sum(1 for s in all_scores for m in s.false_positives if m.type == t)
        fn = sum(1 for s in all_scores for m in s.false_negatives if m.type == t)
        p, r, f1 = _prf1(tp, fp, fn)
        p_note = " (해당 없음)" if tp + fp == 0 else ""
        r_note = " (해당 없음)" if tp + fn == 0 else ""
        lines.append(
            f"  {t} P {p:.2f} ({tp}/{tp + fp}){p_note}  "
            f"R {r:.2f} ({tp}/{tp + fn}){r_note}  F1 {f1:.2f}"
        )
    lines.append("")

    lines.append("놓친 표현 (FN):")
    fn_items = [(i, item) for i, s in enumerate(all_scores, start=1) for item in s.false_negatives]
    if not fn_items:
        lines.append("  없음")
    else:
        for i, item in fn_items:
            lines.append(f'  [케이스 {i}] "{item.text}" ({item.type})')
    lines.append("")

    lines.append("과탐지 (FP):")
    fp_items = [(i, item) for i, s in enumerate(all_scores, start=1) for item in s.false_positives]
    if not fp_items:
        lines.append("  없음")
    else:
        for i, item in fp_items:
            lines.append(f'  [케이스 {i}] "{item.text}" ({item.type}) — 예측했지만 정답에 없음')
    lines.append("")

    risk_counts = {"높음": 0, "중간": 0, "낮음": 0}
    for s in all_scores:
        for m in s.matched:
            risk_counts[m.risk] += 1
    lines.append(
        f"예측 risk 분포 (참고용): 높음 {risk_counts['높음']} / "
        f"중간 {risk_counts['중간']} / 낮음 {risk_counts['낮음']}"
    )

    return "\n".join(lines)


def _prf1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def _all_types(scores: list["CaseScore"]) -> set[str]:
    types: set[str] = set()
    for s in scores:
        types.update(m.type for m in s.matched)
        types.update(m.type for m in s.false_positives)
        types.update(e.type for e in s.false_negatives)
    return types
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

Run: `pytest tests/test_eval.py -v`
Expected: PASS (12 passed)

- [ ] **Step 5: 커밋**

```bash
git add judgpt/eval.py tests/test_eval.py
git commit -m "eval 리포트 포맷(유형별 P/R/F1, FN/FP 상세, risk 분포) 추가"
```

---

### Task 5: CLI 진입점 (`python -m judgpt.eval`)

**Files:**
- Modify: `judgpt/eval.py` (파일 맨 위 import 정리 + 파일 끝에 `main()` 추가)
- Test: `tests/test_eval.py` (파일 끝에 추가)

**Interfaces:**
- Consumes: `judgpt.config.MODEL`, `judgpt.config.OLLAMA_BASE_URL` (MVP, 기존), `judgpt.llm.OllamaLLM` (MVP, 기존), `judgpt.eval_data.golden.load_golden_cases` (Task 1), `judgpt.eval.run_eval`, `judgpt.eval.format_eval_report` (Task 3, 4)
- Produces: `judgpt.eval.main(argv: list[str] | None = None, llm: LLM | None = None, cases: list[GoldenCase] | None = None) -> None`

`llm`과 `cases` 둘 다 주입 가능하게 만든다 — `analyze.py`의 `main(argv, llm=...)`과 동일한 테스트 패턴이다. `cases`를 주입하지 않으면 실제 `judgpt/eval_data/golden.json` 전체(15건)를 로드하므로, 주입 없이 하는 테스트는 `FakeLLM`에 15개의 캔 응답을 순서대로 준비해야 해 깨지기 쉽다 — 그래서 테스트에서는 항상 작은 `cases` 리스트를 직접 주입한다.

- [ ] **Step 1: 실패하는 테스트 작성 — `tests/test_eval.py`에 추가 (파일 끝)**

```python
import json

from judgpt.eval import main
from judgpt.eval_data.golden import GoldenCase
from judgpt.llm import FakeLLM


def test_main_prints_human_report_by_default(capsys):
    llm = FakeLLM(['{"expressions": []}'])
    cases = [GoldenCase(chat_text="A: 안녕", expected=[])]

    main([], llm=llm, cases=cases)

    captured = capsys.readouterr()
    assert "1개 케이스" in captured.out


def test_main_json_flag_outputs_valid_json(capsys):
    llm = FakeLLM(['{"expressions": []}'])
    cases = [GoldenCase(chat_text="A: 안녕", expected=[])]

    main(["--json"], llm=llm, cases=cases)

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["cases"][0]["chat_text"] == "A: 안녕"


def test_main_without_cases_loads_default_golden_dataset(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "judgpt.eval.load_golden_cases",
        lambda: calls.append("called") or [],
    )
    llm = FakeLLM([])

    main([], llm=llm)

    assert calls == ["called"]
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `pytest tests/test_eval.py -v`
Expected: FAIL with `ImportError: cannot import name 'main' from 'judgpt.eval'`

- [ ] **Step 3: `judgpt/eval.py` 맨 위 import 블록을 아래로 교체**

```python
import argparse
import json
import sys

from pydantic import BaseModel

from judgpt import config
from judgpt.analyzer import analyze
from judgpt.eval_data.golden import GoldenCase, GoldenExpectation, load_golden_cases
from judgpt.llm import LLM, OllamaLLM
from judgpt.schema import Expression
```

- [ ] **Step 4: `judgpt/eval.py` 파일 끝에 추가**

```python
def main(
    argv: list[str] | None = None,
    llm: LLM | None = None,
    cases: list[GoldenCase] | None = None,
) -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="골든 데이터셋으로 유해 표현 탐지 정확도를 측정한다",
        prog="python -m judgpt.eval",
    )
    parser.add_argument(
        "--json", action="store_true", help="사람이 읽는 리포트 대신 원본 JSON을 출력한다"
    )
    args = parser.parse_args(argv)

    if llm is None:
        llm = OllamaLLM(model=config.MODEL, base_url=config.OLLAMA_BASE_URL)
    if cases is None:
        cases = load_golden_cases()

    report = run_eval(cases, llm)

    if args.json:
        print(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))
    else:
        print(format_eval_report(report))


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 테스트 실행 — 통과 확인**

Run: `pytest tests/test_eval.py -v`
Expected: PASS (15 passed)

- [ ] **Step 6: 전체 테스트 스위트 실행 — 회귀 확인**

Run: `pytest -v`
Expected: 모든 기존 테스트 + 신규 테스트 전부 PASS, 통합 테스트(`integration` 마커)는 기본 실행에서 제외되어 skip 없이 안 나타남.

- [ ] **Step 7: 커밋**

```bash
git add judgpt/eval.py tests/test_eval.py
git commit -m "eval 하네스 CLI 진입점(python -m judgpt.eval) 추가"
```

- [ ] **Step 8: (선택) 실제 Ollama로 골든셋 실행해 확인**

로컬에 Ollama가 떠 있고 `exaone3.5:7.8b`가 받아져 있다면:

```bash
python -m judgpt.eval
```

리포트가 정상 출력되는지, precision/recall이 합리적인 범위인지 육안으로 확인한다. `CLAUDE.md`의 "명령어" 섹션에 이 명령을 추가하는 것도 고려한다(이 태스크의 범위는 아니므로 강제하지 않음 — 필요하면 별도로).

---

## Self-Review 메모 (계획 작성자용, 실행 시 참고만)

- **스펙 커버리지:** spec §1(골든 데이터셋) → Task 1, §2(채점 로직) → Task 2·3, §3(리포트 포맷) → Task 4, §4(CLI) → Task 5, §5(테스트 전략) → 각 태스크의 Test 섹션, §6(파일 구조) → 본 계획의 File Structure와 동일.
- **타입 일관성:** `GoldenExpectation`/`GoldenCase`가 Task 1(정의)·2·3·4·5(소비)에서 동일 필드명 사용. `CaseScore`가 Task 2(정의)·3·4(소비)에서 동일. `CaseResult`/`EvalReport`가 Task 3(정의)·4·5(소비)에서 동일. `run_eval`/`format_eval_report`/`load_golden_cases` 시그니처가 정의 태스크와 소비 태스크에서 일치.
- **플레이스홀더:** 없음 — 골든 데이터셋 15건은 실제 자연스러운 한국어 문장으로 작성했다(지어낸 판례나 법률 정보 아님, 단순 채팅 예시).
