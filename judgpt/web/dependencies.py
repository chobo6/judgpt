from collections import OrderedDict

from judgpt import config
from judgpt.embedder import Embedder, OllamaEmbedder
from judgpt.llm import LLM, OllamaLLM

_REQUEST_TIMEOUT_SECONDS = 30.0

_llm: LLM | None = None
_embedder: Embedder | None = None


class CachingEmbedder:
    """embed() 결과를 텍스트별로 캐싱해 같은 텍스트를 다시 임베딩하지 않는다.

    legal_rag.enrich()는 호출마다 legal_data/cases.json의 판례를 전부 재임베딩하도록
    설계되어 있다(코퍼스가 작아 캐싱 없이 단순하게 둔 CLI 한 번 실행 전제 — 03-legal-rag-design.md §4).
    웹 서버는 같은 프로세스가 요청마다 enrich()를 반복 호출하므로, 이 레이어에서
    판례 요약처럼 반복되는 텍스트의 임베딩을 캐싱해 불필요한 Ollama 호출을 없앤다.

    ponytail: 캐시 크기를 _MAX_CACHE_SIZE로 제한한 단순 FIFO 축출이다(접근 빈도 기반
    LRU 아님). 판례 코퍼스(현재 4건)는 절대 축출되지 않지만, 요청마다 달라지는
    분석 대상 텍스트가 쌓이면 오래된 것부터 버려진다. 캐시 적중률이 중요해지면
    functools.lru_cache나 TTL 기반 캐시로 바꿀 것."""

    _MAX_CACHE_SIZE = 512

    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder
        self._cache: OrderedDict[str, list[float]] = OrderedDict()

    def embed(self, text: str) -> list[float]:
        if text in self._cache:
            self._cache.move_to_end(text)
            return self._cache[text]
        vector = self._embedder.embed(text)
        self._cache[text] = vector
        if len(self._cache) > self._MAX_CACHE_SIZE:
            self._cache.popitem(last=False)
        return vector


def get_llm() -> LLM:
    global _llm
    if _llm is None:
        _llm = OllamaLLM(
            model=config.MODEL,
            base_url=config.OLLAMA_BASE_URL,
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
    return _llm


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = CachingEmbedder(
            OllamaEmbedder(
                model=config.EMBEDDING_MODEL,
                base_url=config.OLLAMA_BASE_URL,
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
        )
    return _embedder
