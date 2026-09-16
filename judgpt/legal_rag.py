from pydantic import BaseModel

from judgpt.embedder import Embedder, cosine_similarity
from judgpt.legal_data.articles import NEEDS_VERIFICATION, lookup_articles
from judgpt.legal_data.cases import CaseEntry, load_cases
from judgpt.schema import AnalysisResult, Expression

SIMILARITY_THRESHOLD = 0.5


class EnrichedExpression(Expression):
    applicable_laws: list[str] = []
    related_cases: list[str] = []


class EnrichedResult(BaseModel):
    expressions: list[EnrichedExpression]
    needs_verification: bool = NEEDS_VERIFICATION


def enrich(
    result: AnalysisResult,
    embedder: Embedder,
    *,
    is_online: bool = False,
    cases: list[CaseEntry] | None = None,
) -> EnrichedResult:
    """MVP의 AnalysisResult를 조문/판례 정보로 보강한다. 판례 임베딩은 호출마다
    새로 계산한다 — 코퍼스가 수십 건 수준으로 작아서(§4 판단 이유, docs/03-legal-rag-design.md)
    캐싱은 이 규모에서 불필요한 복잡도라고 판단했다."""
    if cases is None:
        cases = load_cases()
    case_embeddings = [(case, embedder.embed(case.summary)) for case in cases]

    enriched_expressions = []
    for expr in result.expressions:
        laws = lookup_articles(expr.type, is_online=is_online)
        related = _find_related_cases(expr, case_embeddings, embedder)
        enriched_expressions.append(
            EnrichedExpression(**expr.model_dump(), applicable_laws=laws, related_cases=related)
        )
    return EnrichedResult(expressions=enriched_expressions, needs_verification=NEEDS_VERIFICATION)


def _find_related_cases(
    expr: Expression,
    case_embeddings: list[tuple[CaseEntry, list[float]]],
    embedder: Embedder,
) -> list[str]:
    candidates = [(case, vec) for case, vec in case_embeddings if case.related_type == expr.type]
    if not candidates:
        return []

    query_text = expr.context or expr.text
    query_vec = embedder.embed(query_text)

    scored: list[tuple[float, CaseEntry]] = []
    for case, vec in candidates:
        score = cosine_similarity(query_vec, vec)
        if score >= SIMILARITY_THRESHOLD:
            scored.append((score, case))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [
        f"{case.case_id} ({case.court}): {case.summary} — {case.source_url}"
        for _, case in scored[:2]
    ]
