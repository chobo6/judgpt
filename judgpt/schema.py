from typing import Literal

from pydantic import BaseModel

ExpressionType = Literal["욕설", "성희롱", "협박", "모욕", "명예훼손", "성적 발언", "기타"]
RiskLevel = Literal["높음", "중간", "낮음"]


class Expression(BaseModel):
    text: str
    type: ExpressionType
    risk: RiskLevel
    target: str | None = None
    context: str | None = None


class AnalysisResult(BaseModel):
    expressions: list[Expression]
