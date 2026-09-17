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
