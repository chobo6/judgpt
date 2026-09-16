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
