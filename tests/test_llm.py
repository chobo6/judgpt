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
