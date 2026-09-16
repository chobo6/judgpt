import json
from pathlib import Path

from pydantic import BaseModel

DEFAULT_CASES_PATH = Path(__file__).parent / "cases.json"


class CaseEntry(BaseModel):
    case_id: str
    court: str
    summary: str
    related_type: str
    source_url: str


def load_cases(path: Path = DEFAULT_CASES_PATH) -> list[CaseEntry]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [CaseEntry.model_validate(entry) for entry in data]
