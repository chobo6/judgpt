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
