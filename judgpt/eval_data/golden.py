import json
from pathlib import Path

from pydantic import BaseModel

from judgpt.schema import ExpressionType

DEFAULT_GOLDEN_PATH = Path(__file__).parent / "golden.json"


class GoldenExpectation(BaseModel):
    text: str
    type: ExpressionType


class GoldenCase(BaseModel):
    chat_text: str
    expected: list[GoldenExpectation]


def load_golden_cases(path: Path = DEFAULT_GOLDEN_PATH) -> list[GoldenCase]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [GoldenCase.model_validate(entry) for entry in data]
