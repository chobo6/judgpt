from judgpt.report import DISCLAIMER, format_report
from judgpt.schema import AnalysisResult, Expression


def test_format_report_no_expressions():
    result = AnalysisResult(expressions=[])

    report = format_report(result)

    assert "문제 표현이 발견되지 않았습니다" in report
    assert DISCLAIMER in report


def test_format_report_includes_count_and_all_fields():
    result = AnalysisResult(expressions=[
        Expression(
            text="너 같은 새끼는 사회에서 없어져야 한다",
            type="모욕",
            risk="높음",
            target="상대방",
            context="반복적인 비하 발언",
        ),
    ])

    report = format_report(result)

    assert "발견된 문제 표현: 1건" in report
    assert '"너 같은 새끼는 사회에서 없어져야 한다"' in report
    assert "유형: 모욕" in report
    assert "대상: 상대방" in report
    assert "위험도: 높음" in report
    assert "맥락: 반복적인 비하 발언" in report
    assert DISCLAIMER in report


def test_format_report_omits_missing_optional_fields():
    result = AnalysisResult(expressions=[
        Expression(text="예시", type="욕설", risk="낮음"),
    ])

    report = format_report(result)

    assert "대상:" not in report
    assert "맥락:" not in report


def test_disclaimer_exact_text():
    assert DISCLAIMER == (
        "이 결과는 참고용 정보이며 법적 판단이 아닙니다. "
        "실제 법적 대응이 필요하면 변호사와 상담하세요."
    )
