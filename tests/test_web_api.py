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
