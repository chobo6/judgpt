from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from judgpt.analyzer import AnalysisError, analyze
from judgpt.llm import LLM
from judgpt.schema import AnalysisResult
from judgpt.web.dependencies import get_llm

app = FastAPI()


class AnalyzeRequest(BaseModel):
    chat_text: str
    legal: bool = False


@app.post("/api/analyze")
def analyze_endpoint(
    body: AnalyzeRequest,
    llm: LLM = Depends(get_llm),
) -> AnalysisResult:
    if not body.chat_text.strip():
        raise HTTPException(status_code=400, detail="입력이 비어 있습니다")

    try:
        return analyze(body.chat_text, llm)
    except AnalysisError:
        raise HTTPException(status_code=502, detail="분석에 실패했습니다. 다시 시도해주세요")
