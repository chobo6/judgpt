import pytest

from judgpt.embedder import FakeEmbedder, cosine_similarity


def test_fake_embedder_returns_prepared_vector():
    embedder = FakeEmbedder({"안녕": [1.0, 0.0]})
    assert embedder.embed("안녕") == [1.0, 0.0]


def test_fake_embedder_raises_for_unprepared_text():
    embedder = FakeEmbedder({})
    with pytest.raises(AssertionError):
        embedder.embed("모르는 텍스트")


def test_cosine_similarity_identical_vectors_is_one():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_opposite_vectors_is_negative_one():
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_cosine_similarity_handles_zero_vector_without_crashing():
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


from judgpt.embedder import OllamaEmbedder


def test_ollama_embedder_targets_configured_base_url():
    embedder = OllamaEmbedder(model="nomic-embed-text", base_url="http://localhost:11434/v1")

    assert embedder.model == "nomic-embed-text"
    assert "11434" in str(embedder._client.base_url)
    assert embedder._client.api_key == "ollama"


def test_ollama_embedder_embed_requests_correct_model_and_input():
    captured_kwargs = {}

    class _FakeEmbeddingData:
        embedding = [0.1, 0.2, 0.3]

    class _FakeEmbeddingResponse:
        data = [_FakeEmbeddingData()]

    class _FakeEmbeddings:
        def create(self, **kwargs):
            captured_kwargs.update(kwargs)
            return _FakeEmbeddingResponse()

    embedder = OllamaEmbedder(model="nomic-embed-text", base_url="http://localhost:11434/v1")
    embedder._client.embeddings = _FakeEmbeddings()

    result = embedder.embed("텍스트")

    assert result == [0.1, 0.2, 0.3]
    assert captured_kwargs["model"] == "nomic-embed-text"
    assert captured_kwargs["input"] == "텍스트"
