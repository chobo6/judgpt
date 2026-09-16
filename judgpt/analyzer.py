import json

from pydantic import ValidationError

from judgpt.llm import LLM
from judgpt.prompt import build_messages
from judgpt.schema import AnalysisResult


class AnalysisError(Exception):
    pass


def analyze(chat_text: str, llm: LLM) -> AnalysisResult:
    messages = build_messages(chat_text)
    raw = llm.call(messages)

    try:
        return _parse(raw)
    except (json.JSONDecodeError, ValidationError) as exc:
        retry_messages = messages + [
            {"role": "assistant", "content": raw},
            {
                "role": "user",
                "content": (
                    f"방금 응답이 올바른 JSON 스키마가 아니었습니다 ({exc}). "
                    "설명 없이 스키마에 맞는 JSON 객체 하나만 다시 응답하세요."
                ),
            },
        ]
        raw_retry = llm.call(retry_messages)
        try:
            return _parse(raw_retry)
        except (json.JSONDecodeError, ValidationError) as exc2:
            raise AnalysisError(f"모델 응답이 올바른 JSON 형식이 아닙니다: {exc2}") from exc2


def _parse(raw: str) -> AnalysisResult:
    data = json.loads(raw)
    return AnalysisResult.model_validate(data)
