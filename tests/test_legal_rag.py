from judgpt.embedder import FakeEmbedder
from judgpt.legal_data.cases import CaseEntry
from judgpt.legal_rag import enrich
from judgpt.schema import AnalysisResult, Expression


def _case(case_id, related_type, summary="요약"):
    return CaseEntry(
        case_id=case_id, court="법원", summary=summary,
        related_type=related_type, source_url="https://example.com",
    )


def test_enrich_adds_applicable_laws_from_rule_mapping():
    result = AnalysisResult(expressions=[Expression(text="예시", type="모욕", risk="높음")])
    embedder = FakeEmbedder({})  # 판례 없음 -> embed() 호출 안 됨

    enriched = enrich(result, embedder, cases=[])

    assert enriched.expressions[0].applicable_laws == ["형법 제311조(모욕)"]


def test_enrich_online_flag_adds_aggravation_articles():
    result = AnalysisResult(expressions=[Expression(text="예시", type="협박", risk="높음")])
    embedder = FakeEmbedder({})

    enriched = enrich(result, embedder, is_online=True, cases=[])

    assert (
        "성폭력범죄의 처벌 등에 관한 특례법 제14조의3(촬영물과 편집물 등을 이용한 협박ㆍ강요)"
        in enriched.expressions[0].applicable_laws
    )


def test_enrich_finds_related_case_above_threshold():
    case = _case("테스트사건 2024", "모욕", summary="모욕 관련 요약")
    result = AnalysisResult(
        expressions=[Expression(text="예시", type="모욕", risk="높음", context="맥락설명")]
    )
    embedder = FakeEmbedder({"모욕 관련 요약": [1.0, 0.0], "맥락설명": [1.0, 0.0]})

    enriched = enrich(result, embedder, cases=[case])

    assert len(enriched.expressions[0].related_cases) == 1
    assert "테스트사건 2024" in enriched.expressions[0].related_cases[0]


def test_enrich_returns_no_related_cases_below_threshold():
    case = _case("테스트사건 2024", "모욕", summary="모욕 관련 요약")
    result = AnalysisResult(
        expressions=[Expression(text="예시", type="모욕", risk="높음", context="완전히 다른 맥락")]
    )
    embedder = FakeEmbedder({"모욕 관련 요약": [1.0, 0.0], "완전히 다른 맥락": [0.0, 1.0]})

    enriched = enrich(result, embedder, cases=[case])

    assert enriched.expressions[0].related_cases == []


def test_enrich_ignores_cases_of_different_type():
    case = _case("협박사건", "협박", summary="협박 요약")
    result = AnalysisResult(
        expressions=[Expression(text="예시", type="모욕", risk="높음", context="맥락")]
    )
    embedder = FakeEmbedder({"협박 요약": [1.0, 0.0]})

    enriched = enrich(result, embedder, cases=[case])

    assert enriched.expressions[0].related_cases == []


def test_enrich_result_carries_needs_verification_flag():
    """실제 NEEDS_VERIFICATION 값(2026-09-16 법제처 API로 조문 확인 완료, False)을
    그대로 실어 나르는지 확인한다."""
    result = AnalysisResult(expressions=[])
    embedder = FakeEmbedder({})

    enriched = enrich(result, embedder, cases=[])

    assert enriched.needs_verification is False


def test_enrich_result_needs_verification_reflects_flag_when_true(monkeypatch):
    monkeypatch.setattr("judgpt.legal_rag.NEEDS_VERIFICATION", True)
    result = AnalysisResult(expressions=[])
    embedder = FakeEmbedder({})

    enriched = enrich(result, embedder, cases=[])

    assert enriched.needs_verification is True


def test_enrich_falls_back_to_text_when_context_is_none():
    case = _case("테스트사건", "모욕", summary="요약")
    result = AnalysisResult(
        expressions=[Expression(text="예시텍스트", type="모욕", risk="높음", context=None)]
    )
    embedder = FakeEmbedder({"요약": [1.0, 0.0], "예시텍스트": [1.0, 0.0]})

    enriched = enrich(result, embedder, cases=[case])

    assert len(enriched.expressions[0].related_cases) == 1
