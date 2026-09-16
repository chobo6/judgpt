from judgpt.legal_data.articles import NEEDS_VERIFICATION
from judgpt.legal_rag import EnrichedResult
from judgpt.schema import AnalysisResult

DISCLAIMER = (
    "이 결과는 참고용 정보이며 법적 판단이 아닙니다. "
    "실제 법적 대응이 필요하면 변호사와 상담하세요."
)


def format_report(result: AnalysisResult) -> str:
    lines = ["[분석 결과]", ""]

    if not result.expressions:
        lines.append("문제 표현이 발견되지 않았습니다.")
    else:
        lines.append(f"⚠️ 발견된 문제 표현: {len(result.expressions)}건")
        lines.append("")
        for i, expr in enumerate(result.expressions, start=1):
            lines.append(f'{i}. "{expr.text}"')
            lines.append(f"   유형: {expr.type}")
            if expr.target:
                lines.append(f"   대상: {expr.target}")
            lines.append(f"   위험도: {expr.risk}")
            if expr.context:
                lines.append(f"   맥락: {expr.context}")
            lines.append("")

    lines.append("─" * 20)
    lines.append(DISCLAIMER)
    return "\n".join(lines)


VERIFICATION_NOTE = "[조번호 재검증 필요 — 법제처 API로 아직 확인 전]"


def format_enriched_report(result: EnrichedResult) -> str:
    lines = ["[분석 결과]", ""]

    if not result.expressions:
        lines.append("문제 표현이 발견되지 않았습니다.")
    else:
        lines.append(f"⚠️ 발견된 문제 표현: {len(result.expressions)}건")
        lines.append("")
        for i, expr in enumerate(result.expressions, start=1):
            lines.append(f'{i}. "{expr.text}"')
            lines.append(f"   유형: {expr.type}")
            if expr.target:
                lines.append(f"   대상: {expr.target}")
            lines.append(f"   위험도: {expr.risk}")
            if expr.context:
                lines.append(f"   맥락: {expr.context}")
            if expr.applicable_laws:
                suffix = f" {VERIFICATION_NOTE}" if NEEDS_VERIFICATION else ""
                laws_text = ", ".join(expr.applicable_laws)
                lines.append(f"   적용 가능 법률: {laws_text}{suffix}")
            else:
                lines.append("   적용 가능 법률: 판단 근거 없음")
            if expr.related_cases:
                lines.append(f"   관련 판례: {expr.related_cases[0]}")
                for extra in expr.related_cases[1:]:
                    lines.append(f"             {extra}")
            else:
                lines.append("   관련 판례: 판단 근거 없음")
            lines.append("")

    lines.append("─" * 20)
    lines.append(DISCLAIMER)
    return "\n".join(lines)
