from judgpt import config
from judgpt.embedder import Embedder, OllamaEmbedder
from judgpt.llm import LLM, OllamaLLM

_llm: LLM | None = None
_embedder: Embedder | None = None


def get_llm() -> LLM:
    global _llm
    if _llm is None:
        _llm = OllamaLLM(model=config.MODEL, base_url=config.OLLAMA_BASE_URL)
    return _llm


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = OllamaEmbedder(model=config.EMBEDDING_MODEL, base_url=config.OLLAMA_BASE_URL)
    return _embedder
