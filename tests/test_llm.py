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


from judgpt.llm import OllamaLLM


def test_ollama_llm_targets_configured_base_url():
    llm = OllamaLLM(model="exaone3.5:7.8b", base_url="http://localhost:11434/v1")

    assert llm.model == "exaone3.5:7.8b"
    assert "11434" in str(llm._client.base_url)
    assert llm._client.api_key == "ollama"


def test_ollama_llm_client_uses_default_timeout_when_not_set():
    llm = OllamaLLM(model="exaone3.5:7.8b", base_url="http://localhost:11434/v1")

    assert llm._client.timeout.read == 600


def test_ollama_llm_client_uses_configured_timeout():
    llm = OllamaLLM(model="exaone3.5:7.8b", base_url="http://localhost:11434/v1", timeout=30.0)

    assert llm._client.timeout == 30.0


def test_ollama_llm_client_disables_retries():
    # 재시도하면 실패까지 걸리는 시간이 timeout의 (1 + max_retries)배가 된다 — 타임아웃
    # 날 만큼 느린 요청은 재시도해도 같은 이유로 또 타임아웃 나서 재시도가 무의미하다.
    llm = OllamaLLM(model="exaone3.5:7.8b", base_url="http://localhost:11434/v1")

    assert llm._client.max_retries == 0


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


def test_ollama_llm_call_returns_empty_string_when_content_is_none(monkeypatch):
    class _FakeMessage:
        content = None

    class _FakeChoice:
        message = _FakeMessage()

    class _FakeCompletion:
        choices = [_FakeChoice()]

    class _FakeCompletions:
        def create(self, **kwargs):
            return _FakeCompletion()

    class _FakeChat:
        completions = _FakeCompletions()

    llm = OllamaLLM(model="exaone3.5:7.8b", base_url="http://localhost:11434/v1")
    llm._client.chat = _FakeChat()

    result = llm.call([{"role": "user", "content": "질문"}])

    assert result == ""


def test_ollama_llm_call_omits_temperature_by_default():
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

    llm.call([{"role": "user", "content": "질문"}])

    assert "temperature" not in captured_kwargs


def test_ollama_llm_call_passes_temperature_when_set():
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

    llm = OllamaLLM(model="exaone3.5:7.8b", base_url="http://localhost:11434/v1", temperature=0)
    llm._client.chat = _FakeChat()

    llm.call([{"role": "user", "content": "질문"}])

    assert captured_kwargs["temperature"] == 0


def test_ollama_llm_call_returns_empty_string_when_choices_is_empty(monkeypatch):
    class _FakeCompletion:
        choices = []

    class _FakeCompletions:
        def create(self, **kwargs):
            return _FakeCompletion()

    class _FakeChat:
        completions = _FakeCompletions()

    llm = OllamaLLM(model="exaone3.5:7.8b", base_url="http://localhost:11434/v1")
    llm._client.chat = _FakeChat()

    result = llm.call([{"role": "user", "content": "질문"}])

    assert result == ""
