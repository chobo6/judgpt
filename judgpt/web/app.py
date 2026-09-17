from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from openai import APIConnectionError
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from judgpt.analyzer import AnalysisError, analyze
from judgpt.embedder import Embedder
from judgpt.legal_rag import EnrichedResult, enrich
from judgpt.llm import LLM
from judgpt.schema import AnalysisResult
from judgpt.web.dependencies import get_embedder, get_llm

app = FastAPI()

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "요청이 너무 많습니다. 잠시 후 다시 시도하세요"},
    )


class AnalyzeRequest(BaseModel):
    chat_text: str
    legal: bool = False


@app.post("/api/analyze")
@limiter.limit("5/minute")
def analyze_endpoint(
    request: Request,
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
