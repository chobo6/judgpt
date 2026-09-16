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
