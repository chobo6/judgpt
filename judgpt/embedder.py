import math
from typing import Protocol

from openai import OpenAI


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


class FakeEmbedder:
    """테스트용. 미리 준비된 텍스트->벡터 매핑을 그대로 반환한다."""

    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self._vectors = dict(vectors)

    def embed(self, text: str) -> list[float]:
        if text not in self._vectors:
            raise AssertionError(f"FakeEmbedder: '{text}'에 대한 벡터가 준비되지 않았습니다")
        return self._vectors[text]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class OllamaEmbedder:
    """Ollama의 OpenAI 호환 임베딩 엔드포인트(/v1/embeddings)를 호출한다."""

    def __init__(self, model: str, base_url: str, timeout: float | None = None) -> None:
        self.model = model
        kwargs: dict = {"base_url": base_url, "api_key": "ollama"}
        if timeout is not None:
            kwargs["timeout"] = timeout
        self._client = OpenAI(**kwargs)

    def embed(self, text: str) -> list[float]:
        response = self._client.embeddings.create(model=self.model, input=text)
        if not response.data:
            return []
        return response.data[0].embedding
