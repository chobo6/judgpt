from judgpt.embedder import OllamaEmbedder
from judgpt.llm import OllamaLLM
from judgpt.web.dependencies import CachingEmbedder, get_embedder, get_llm


def test_get_llm_returns_same_instance_on_repeated_calls():
    first = get_llm()
    second = get_llm()

    assert first is second
    assert isinstance(first, OllamaLLM)


def test_get_embedder_returns_same_instance_on_repeated_calls():
    first = get_embedder()
    second = get_embedder()

    assert first is second
    assert isinstance(first, CachingEmbedder)


def test_caching_embedder_only_calls_inner_embedder_once_per_text():
    calls = []

    class _CountingEmbedder:
        def embed(self, text):
            calls.append(text)
            return [0.1, 0.2, 0.3]

    embedder = CachingEmbedder(_CountingEmbedder())

    first = embedder.embed("같은 텍스트")
    second = embedder.embed("같은 텍스트")
    embedder.embed("다른 텍스트")

    assert first == second
    assert calls == ["같은 텍스트", "다른 텍스트"]


def test_caching_embedder_evicts_oldest_entry_beyond_max_size():
    calls = []

    class _CountingEmbedder:
        def embed(self, text):
            calls.append(text)
            return [0.0]

    embedder = CachingEmbedder(_CountingEmbedder())
    embedder._MAX_CACHE_SIZE = 2

    embedder.embed("a")
    embedder.embed("b")
    embedder.embed("c")  # evicts "a"
    embedder.embed("a")  # cache miss again, re-fetched

    assert calls == ["a", "b", "c", "a"]


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


def test_analyze_endpoint_returns_400_when_chat_text_too_long(client):
    # get_llm을 오버라이드하지 않아도 Pydantic 검증에서 막혀야 한다 — analyze()까지
    # 도달하면(즉 진짜 Ollama를 호출하면) 이 테스트는 실패 대신 아주 느려진다.
    response = client.post("/api/analyze", json={"chat_text": "가" * 100_001})

    assert response.status_code == 400
    assert response.json() == {"detail": "요청 형식이 올바르지 않습니다"}


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


def test_analyze_endpoint_rate_limited_after_five_requests_per_minute(client):
    fake_llm = FakeLLM(['{"expressions": []}'] * 5)
    app.dependency_overrides[get_llm] = lambda: fake_llm

    for _ in range(5):
        response = client.post("/api/analyze", json={"chat_text": "A: 안녕"})
        assert response.status_code == 200

    response = client.post("/api/analyze", json={"chat_text": "A: 안녕"})

    assert response.status_code == 429
    assert response.json() == {"detail": "요청이 너무 많습니다. 잠시 후 다시 시도하세요"}


def test_analyze_endpoint_returns_502_on_analysis_error(client):
    app.dependency_overrides[get_llm] = lambda: FakeLLM(["not json", "still not json"])

    response = client.post("/api/analyze", json={"chat_text": "A: 예시"})

    assert response.status_code == 502
    assert response.json() == {"detail": "분석에 실패했습니다. 다시 시도해주세요"}
