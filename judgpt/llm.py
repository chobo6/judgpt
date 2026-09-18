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

    def __init__(
        self,
        model: str,
        base_url: str,
        temperature: float | None = None,
        timeout: float | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        # max_retries=0: 기본값(2회)대로 두면 타임아웃마다 처음부터 다시 생성을 시도해서
        # 실패까지 걸리는 시간이 timeout의 3배가 된다(예: timeout=90 -> 최악 270초 대기).
        # 재시도해도 매번 같은 이유로 다시 타임아웃 날 뿐이라 얻는 게 없다 — 한 번만 시도한다.
        kwargs: dict = {"base_url": base_url, "api_key": "ollama", "max_retries": 0}
        if timeout is not None:
            kwargs["timeout"] = timeout
        self._client = OpenAI(**kwargs)

    def call(self, messages: list[dict]) -> str:
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        completion = self._client.chat.completions.create(**kwargs)
        if not completion.choices:
            return ""
        return completion.choices[0].message.content or ""
