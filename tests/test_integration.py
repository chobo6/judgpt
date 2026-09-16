from pathlib import Path

import pytest

from judgpt.analyzer import analyze
from judgpt.config import MODEL, OLLAMA_BASE_URL
from judgpt.llm import OllamaLLM

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.integration
def test_analyze_detects_obvious_insult_and_threat():
    chat_text = (FIXTURES / "harmful_example.txt").read_text(encoding="utf-8")
    llm = OllamaLLM(model=MODEL, base_url=OLLAMA_BASE_URL)

    result = analyze(chat_text, llm)

    assert len(result.expressions) >= 1


@pytest.mark.integration
def test_analyze_benign_chat_finds_nothing():
    chat_text = (FIXTURES / "benign_example.txt").read_text(encoding="utf-8")
    llm = OllamaLLM(model=MODEL, base_url=OLLAMA_BASE_URL)

    result = analyze(chat_text, llm)

    assert result.expressions == []
