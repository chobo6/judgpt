import os
from pathlib import Path

import pytest

from judgpt.analyzer import analyze
from judgpt.config import MODEL, OLLAMA_BASE_URL
from judgpt.legal_data.fetch_statutes import search_law
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


@pytest.mark.integration
def test_search_law_real_api_returns_results():
    oc = os.environ.get("JUDGPT_LAW_API_OC")
    if not oc:
        pytest.skip("JUDGPT_LAW_API_OC not set")
    result = search_law("형법", oc)
    assert "LawSearch" in result
