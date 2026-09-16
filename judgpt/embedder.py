import math
from typing import Protocol


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
