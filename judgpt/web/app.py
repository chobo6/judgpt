from fastapi import Depends, FastAPI, HTTPException
from openai import APIConnectionError
from pydantic import BaseModel

from judgpt.analyzer import AnalysisError, analyze
from judgpt.embedder import Embedder
from judgpt.legal_rag import EnrichedResult, enrich
from judgpt.llm import LLM
from judgpt.schema import AnalysisResult
from judgpt.web.dependencies import get_embedder, get_llm

app = FastAPI()


class AnalyzeRequest(BaseModel):
    chat_text: str
    legal: bool = False


@app.post("/api/analyze")
def analyze_endpoint(
    body: AnalyzeRequest,
    llm: LLM = Depends(get_llm),
    embedder: Embedder = Depends(get_embedder),
) -> AnalysisResult | EnrichedResult:
    if not body.chat_text.strip():
        raise HTTPException(status_code=400, detail="입력이 비어 있습니다")

    try:
        result = analyze(body.chat_text, llm)
        if body.legal:
            return enrich(result, embedder)
        return result
    except AnalysisError:
        raise HTTPException(status_code=502, detail="분석에 실패했습니다. 다시 시도해주세요")
    except APIConnectionError:
        raise HTTPException(status_code=503, detail="분석 엔진이 응답하지 않습니다")
