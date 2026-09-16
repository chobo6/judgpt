import importlib

from judgpt import config


def test_model_defaults_to_exaone(monkeypatch):
    monkeypatch.delenv("JUDGPT_MODEL", raising=False)
    importlib.reload(config)

    assert config.MODEL == "exaone3.5:7.8b"


def test_ollama_base_url_defaults_to_localhost(monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    importlib.reload(config)

    assert config.OLLAMA_BASE_URL == "http://localhost:11434/v1"


def test_model_env_var_overrides_default(monkeypatch):
    monkeypatch.setenv("JUDGPT_MODEL", "qwen2.5:7b")
    importlib.reload(config)
    try:
        assert config.MODEL == "qwen2.5:7b"
    finally:
        monkeypatch.delenv("JUDGPT_MODEL", raising=False)
        importlib.reload(config)
