from judgpt.embedder import OllamaEmbedder
from judgpt.llm import OllamaLLM
from judgpt.web.dependencies import get_embedder, get_llm


def test_get_llm_returns_same_instance_on_repeated_calls():
    first = get_llm()
    second = get_llm()

    assert first is second
    assert isinstance(first, OllamaLLM)


def test_get_embedder_returns_same_instance_on_repeated_calls():
    first = get_embedder()
    second = get_embedder()

    assert first is second
    assert isinstance(first, OllamaEmbedder)


from judgpt.llm import FakeLLM
from judgpt.web.app import app
from judgpt.web.dependencies import get_llm


def test_analyze_endpoint_returns_expressions(client):
    fake_llm = FakeLLM(['{"expressions": []}'])
    app.dependency_overrides[get_llm] = lambda: fake_llm

    response = client.post("/api/analyze", json={"chat_text": "A: 안녕"})

    assert response.status_code == 200
    assert response.json() == {"expressions": []}


def test_analyze_endpoint_returns_400_on_empty_chat_text(client):
    response = client.post("/api/analyze", json={"chat_text": "   "})

    assert response.status_code == 400
    assert response.json() == {"detail": "입력이 비어 있습니다"}


from judgpt.embedder import FakeEmbedder
from judgpt.legal_data.cases import load_cases


def test_analyze_endpoint_with_legal_flag_returns_enriched_result(client):
    fake_llm = FakeLLM([
        '{"expressions": [{"text": "너는 쓰레기야", "type": "모욕", "risk": "높음"}]}'
    ])
    vectors = {case.summary: [0.1, 0.2, 0.3] for case in load_cases()}
    vectors["너는 쓰레기야"] = [0.1, 0.2, 0.3]
    fake_embedder = FakeEmbedder(vectors)
    app.dependency_overrides[get_llm] = lambda: fake_llm
    app.dependency_overrides[get_embedder] = lambda: fake_embedder

    response = client.post(
        "/api/analyze", json={"chat_text": "A: 예시", "legal": True}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["expressions"][0]["applicable_laws"] == ["형법 제311조(모욕)"]
    assert "needs_verification" in data


def test_analyze_endpoint_returns_503_when_ollama_unreachable(client):
    import httpx
    from openai import APIConnectionError

    class _ConnectionErrorLLM:
        def call(self, messages):
            raise APIConnectionError(
                request=httpx.Request("POST", "http://localhost:11434/v1/chat/completions")
            )

    app.dependency_overrides[get_llm] = lambda: _ConnectionErrorLLM()

    response = client.post("/api/analyze", json={"chat_text": "A: 예시"})

    assert response.status_code == 503
    assert response.json() == {"detail": "분석 엔진이 응답하지 않습니다"}
