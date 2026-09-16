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
