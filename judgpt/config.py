import os

MODEL = os.getenv("JUDGPT_MODEL", "exaone3.5:7.8b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
