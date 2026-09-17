# judgpt — 자동 채점 eval 하네스 설계

> `CLAUDE.md` "범위 밖" 항목 중 하나였던 "자동 채점 eval 하네스"의 구현 설계다. MVP(욕설/성희롱/협박/모욕/명예훼손 탐지)와 법률 RAG(`--legal`)는 이미 구현·병합된 상태이며, 이 문서는 그 위에 탐지 정확도를 자동으로 측정하는 도구를 추가한다.

## 0. 목적과 범위

- **목적**: LLM(`exaone3.5:7.8b` 등)이 채팅 텍스트에서 유해 표현을 얼마나 정확히 탐지하는지 수치로 측정한다. 프롬프트를 수정하거나 모델을 교체(`qwen2.5:7b` 등)할 때 "전보다 나아졌는지/나빠졌는지"를 감으로 판단하지 않고 돌려서 확인하기 위함이다.
- **범위**: `analyze()`(MVP 탐지)의 `type` 필드 정확도만 정량 측정한다. `risk`(위험도)는 참고 통계로만 보여주고 점수에는 넣지 않는다 — 사람도 주관적으로 판단이 갈리는 값이라 "정답"을 하나로 고정하기 어렵다. `--legal`(조문/판례 RAG)은 이번 범위에서 제외한다 — 탐지 자체의 정확도와는 별개 관심사이고, `ARTICLE_MAP`은 이미 결정론적 규칙 매핑이라 LLM 정확도 문제가 아니다.
- **비목표**: 데이터셋 대량 자동 수집, CI 자동 실행(매번 Ollama 호출이 필요해 느리고 비결정적이라 사람이 필요할 때 수동으로 돌리는 도구로 남긴다), 통계적 유의성 검정.

## 1. 골든 데이터셋

`judgpt/eval_data/golden.json` — 리스트, 각 항목:

```json
{
  "chat_text": "채팅 원문 그대로",
  "expected": [
    {"text": "예상되는 표현의 일부 또는 전체", "type": "모욕"}
  ]
}
```

- 문제 표현이 없는 케이스는 `"expected": []`.
- 초기 데이터는 사람(저장소 소유자)이 직접 작성한다 — 카테고리(욕설/성희롱/협박/모욕/명예훼손/성적 발언/기타)당 2~4개 + 무해한 대화 몇 개, 총 10~20개 수준으로 시작한다. 지어낸 법률 판단을 넣지 않는다는 이 프로젝트의 기존 원칙과 마찬가지로, 예시 채팅도 실제로 있을 법한 자연스러운 문장으로 작성한다.
- `judgpt/eval_data/golden.py`가 `judgpt/legal_data/cases.py`와 동일한 패턴으로 로더를 제공한다:

```python
class GoldenExpectation(BaseModel):
    text: str
    type: ExpressionType  # judgpt.schema.ExpressionType 재사용

class GoldenCase(BaseModel):
    chat_text: str
    expected: list[GoldenExpectation]

def load_golden_cases(path: Path = DEFAULT_GOLDEN_PATH) -> list[GoldenCase]: ...
```

## 2. 채점 로직 (`judgpt/eval.py`)

### 2.1 표현 단위 매칭

한 케이스 안에서 LLM이 예측한 `expressions`(`list[Expression]`)와 골든의 `expected`(`list[GoldenExpectation]`)를 1:1로 매칭한다.

- 매칭 조건: `predicted.type == expected.type` **그리고** (`expected.text in predicted.text` 또는 `predicted.text in expected.text`) — 부분 문자열 포함이면 매칭으로 본다. LLM이 인용할 때 조사나 공백을 살짝 바꾸거나 더 길게/짧게 인용해도 허용하기 위함이다.
- 탐욕적(greedy) 1:1 매칭: `predicted` 리스트를 순서대로 순회하면서, 각 predicted마다 아직 매칭 안 된 `expected` 중 조건을 만족하는 첫 번째 항목과 짝짓는다. 한 번 짝지어진 expected는 이후 predicted와 다시 매칭되지 않는다(중복 매칭 방지).
- 매칭된 쌍 → **TP**(True Positive)
- 매칭 안 된 expected → **FN**(False Negative, 놓친 표현)
- 매칭 안 된 predicted → **FP**(False Positive, 과탐지)

### 2.2 지표 집계

- 케이스 전체를 합산해 **type별** 그리고 **전체(micro)** precision/recall/F1을 계산한다.
  - precision = TP / (TP + FP)
  - recall = TP / (TP + FN)
  - F1 = 2·precision·recall / (precision + recall)
  - 분모가 0이면(해당 type이 한 번도 안 나옴) 0.0으로 표시하고 "해당 없음"을 함께 표기한다.
- `risk`는 매칭된 TP 쌍에 한해 "정답 risk가 따로 없으므로 예측 risk 분포(높음/중간/낮음 개수)"만 리포트에 참고용으로 곁들인다. 정오답 판정에는 쓰지 않는다.

### 2.3 함수 시그니처

```python
def score_case(predicted: list[Expression], expected: list[GoldenExpectation]) -> CaseScore:
    """순수 함수. LLM/Ollama 없이 유닛테스트로 전부 커버 가능."""

def run_eval(cases: list[GoldenCase], llm: LLM) -> EvalReport:
    """각 케이스마다 analyze(case.chat_text, llm)을 실제로 호출해 score_case()로 채점,
    전체를 집계한 EvalReport를 만든다."""
```

`CaseScore`/`EvalReport`는 `pydantic.BaseModel`로 정의(기존 스타일과 일관).

## 3. 리포트 포맷 (`format_eval_report()`)

사람이 읽는 텍스트 리포트:

```
[Eval 결과] 15개 케이스

전체: Precision 0.83 (10/12)  Recall 0.77 (10/13)  F1 0.80

유형별:
  모욕     P 1.00 (3/3)  R 0.75 (3/4)  F1 0.86
  협박     P 0.67 (2/3)  R 1.00 (2/2)  F1 0.80
  ...

놓친 표현 (FN):
  [케이스 3] "..." (명예훼손)

과탐지 (FP):
  [케이스 7] "..." (기타) — 예측했지만 정답에 없음

예측 risk 분포 (참고용): 높음 6 / 중간 4 / 낮음 3
```

`--json` 플래그로 `EvalReport.model_dump()`를 그대로 JSON 출력하는 것도 함께 지원한다(다른 도구로 후처리하거나 시계열로 기록하고 싶을 때 대비 — 기존 `analyze.py --json` 패턴과 일관).

## 4. CLI (`judgpt/eval.py` `main()`)

`python -m judgpt.eval` 로 실행한다. `analyze.py`와 동일한 배선 스타일:

- 인자 없이 실행하면 `judgpt/eval_data/golden.json` 전체를 기본 `OllamaLLM`(환경변수 `JUDGPT_MODEL`)으로 돌린다.
- `--json`: 사람이 읽는 리포트 대신 원본 JSON 출력.
- `llm` 파라미터를 주입받을 수 있게 해 테스트에서 `FakeLLM`으로 배선을 확인한다(`analyze.py main(argv, llm=...)`와 동일 패턴).

`--legal`이나 모델 비교(A/B) 같은 옵션은 지금 범위에 넣지 않는다 — 필요해지면 그때 추가.

## 5. 테스트 전략

- `tests/test_eval.py`:
  - `score_case()` 순수 로직: TP/FN/FP 각 케이스, 부분 문자열 매칭 허용 확인, type이 다르면 매칭 안 됨, 탐욕적 매칭의 중복 소비 방지.
  - `run_eval()`: `FakeLLM`으로 골든 케이스 1~2개를 돌려 `score_case()`와 올바르게 연결되는지 확인.
  - `format_eval_report()`: 출력에 주요 지표가 포함되는지 확인.
  - `main()`: `FakeLLM` 주입 + `--json` 플래그 배선 테스트(`analyze.py`의 기존 CLI 테스트 패턴 재사용).
- `judgpt/eval_data/golden.json` 자체를 실제 Ollama로 돌리는 건 자동 테스트 스위트에 넣지 않는다(비결정적·느림) — 사람이 필요할 때 `python -m judgpt.eval`을 직접 실행해서 확인한다. 이는 기존 컨벤션(`pytest -m integration`이 실제 Ollama가 있을 때만 도는 별도 마커)과 같은 이유다.

## 6. 파일 구조 요약

```
judgpt/
  eval.py                  # score_case, run_eval, format_eval_report, main
  eval_data/
    __init__.py
    golden.py               # GoldenExpectation, GoldenCase, load_golden_cases
    golden.json              # 사람이 직접 작성한 골든 데이터셋
tests/
  test_eval.py
```

기존 `judgpt/legal_data/` 패턴(데이터 모델 + JSON + 로더 분리)을 그대로 따른다.
