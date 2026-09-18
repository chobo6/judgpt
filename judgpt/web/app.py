import logging
import os
from typing import Callable

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import APIConnectionError
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from judgpt.analyzer import AnalysisError, analyze
from judgpt.embedder import Embedder
from judgpt.legal_rag import EnrichedResult, enrich
from judgpt.llm import LLM
from judgpt.schema import AnalysisResult
from judgpt.web.dependencies import get_embedder, get_llm, get_replay_importer
from judgpt.web.mafia42 import ReplayImportError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "요청이 너무 많습니다. 잠시 후 다시 시도하세요"},
    )


@app.exception_handler(RequestValidationError)
def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"detail": "요청 형식이 올바르지 않습니다"},
    )


class AnalyzeRequest(BaseModel):
    chat_text: str = Field(max_length=100_000)
    legal: bool = False


@app.post("/api/analyze")
@limiter.limit("5/minute")
def analyze_endpoint(
    request: Request,
    body: AnalyzeRequest,
    llm: LLM = Depends(get_llm),
    embedder: Embedder = Depends(get_embedder),
) -> AnalysisResult | EnrichedResult:
    ip = get_remote_address(request)
    if not body.chat_text.strip():
        raise HTTPException(status_code=400, detail="입력이 비어 있습니다")

    logger.info("analyze 요청 ip=%s legal=%s chat_text=%r", ip, body.legal, body.chat_text)
    try:
        result: AnalysisResult | EnrichedResult = analyze(body.chat_text, llm)
        if body.legal:
            result = enrich(result, embedder)
        logger.info("analyze 응답 ip=%s result=%s", ip, result.model_dump_json())
        return result
    except AnalysisError as exc:
        logger.warning("analyze 실패 ip=%s error=%s", ip, exc)
        raise HTTPException(status_code=502, detail="분석에 실패했습니다. 다시 시도해주세요")
    except APIConnectionError as exc:
        logger.warning("analyze 실패 ip=%s error=%s", ip, exc)
        raise HTTPException(status_code=503, detail="분석 엔진이 응답하지 않습니다")


class FetchReplayRequest(BaseModel):
    url: str = Field(max_length=200)


class FetchReplayResponse(BaseModel):
    chat_text: str


@app.post("/api/fetch-replay")
@limiter.limit("5/minute")
def fetch_replay_endpoint(
    request: Request,
    body: FetchReplayRequest,
    importer: Callable[[str], str] = Depends(get_replay_importer),
) -> FetchReplayResponse:
    try:
        chat_text = importer(body.url)
    except ReplayImportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    return FetchReplayResponse(chat_text=chat_text)


_frontend_dist = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
