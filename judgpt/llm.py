from typing import Protocol

from openai import OpenAI


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


class OllamaLLM:
    """Ollama의 OpenAI 호환 엔드포인트(/v1/chat/completions)를 호출한다."""

    def __init__(self, model: str, base_url: str) -> None:
        self.model = model
        self._client = OpenAI(base_url=base_url, api_key="ollama")

    def call(self, messages: list[dict]) -> str:
        completion = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"},
        )
        if not completion.choices:
            return ""
        return completion.choices[0].message.content or ""
