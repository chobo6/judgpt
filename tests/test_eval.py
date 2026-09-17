from judgpt.eval import score_case
from judgpt.eval_data.golden import GoldenExpectation
from judgpt.schema import Expression


def _expr(text, type_, risk="높음"):
    return Expression(text=text, type=type_, risk=risk)


def _exp(text, type_):
    return GoldenExpectation(text=text, type=type_)


def test_score_case_matches_exact_text_and_type_as_true_positive():
    predicted = [_expr("너는 쓰레기야", "모욕")]
    expected = [_exp("너는 쓰레기야", "모욕")]

    score = score_case(predicted, expected)

    assert score.matched == predicted
    assert score.false_negatives == []
    assert score.false_positives == []


def test_score_case_matches_when_predicted_text_is_longer_substring():
    predicted = [_expr("진짜 너는 쓰레기야 정말로", "모욕")]
    expected = [_exp("너는 쓰레기야", "모욕")]

    score = score_case(predicted, expected)

    assert len(score.matched) == 1
    assert score.false_negatives == []


def test_score_case_matches_when_expected_text_is_longer_substring():
    predicted = [_expr("쓰레기야", "모욕")]
    expected = [_exp("진짜 너는 쓰레기야 정말로", "모욕")]

    score = score_case(predicted, expected)

    assert len(score.matched) == 1


def test_score_case_does_not_match_when_type_differs():
    predicted = [_expr("너는 쓰레기야", "욕설")]
    expected = [_exp("너는 쓰레기야", "모욕")]

    score = score_case(predicted, expected)

    assert score.matched == []
    assert score.false_positives == predicted
    assert score.false_negatives == expected


def test_score_case_unmatched_expected_is_false_negative():
    predicted = []
    expected = [_exp("놓친 표현", "협박")]

    score = score_case(predicted, expected)

    assert score.false_negatives == expected
    assert score.matched == []
    assert score.false_positives == []


def test_score_case_unmatched_predicted_is_false_positive():
    predicted = [_expr("과탐지된 표현", "명예훼손")]
    expected = []

    score = score_case(predicted, expected)

    assert score.false_positives == predicted
    assert score.matched == []


def test_score_case_does_not_double_match_same_expected_twice():
    predicted = [_expr("쓰레기야", "모욕"), _expr("쓰레기야", "모욕")]
    expected = [_exp("쓰레기야", "모욕")]

    score = score_case(predicted, expected)

    assert len(score.matched) == 1
    assert len(score.false_positives) == 1
    assert score.false_negatives == []


from judgpt.eval import run_eval
from judgpt.eval_data.golden import GoldenCase, GoldenExpectation
from judgpt.llm import FakeLLM


def test_run_eval_scores_each_case_against_llm_output():
    cases = [
        GoldenCase(
            chat_text="A: 너는 쓰레기야",
            expected=[GoldenExpectation(text="너는 쓰레기야", type="모욕")],
        ),
        GoldenCase(chat_text="A: 안녕", expected=[]),
    ]
    llm = FakeLLM([
        '{"expressions": [{"text": "너는 쓰레기야", "type": "모욕", "risk": "높음"}]}',
        '{"expressions": []}',
    ])

    report = run_eval(cases, llm)

    assert len(report.cases) == 2
    assert report.cases[0].chat_text == "A: 너는 쓰레기야"
    assert len(report.cases[0].score.matched) == 1
    assert report.cases[1].score.matched == []
    assert report.cases[1].score.false_positives == []


from judgpt.eval import CaseResult, CaseScore, EvalReport, format_eval_report
from judgpt.eval_data.golden import GoldenExpectation
from judgpt.schema import Expression


def test_format_eval_report_includes_overall_metrics():
    report = EvalReport(cases=[
        CaseResult(
            chat_text="A: 너는 쓰레기야",
            score=CaseScore(
                matched=[Expression(text="너는 쓰레기야", type="모욕", risk="높음")],
                false_negatives=[],
                false_positives=[],
            ),
        ),
    ])

    output = format_eval_report(report)

    assert "1개 케이스" in output
    assert "Precision 1.00" in output
    assert "Recall 1.00" in output


def test_format_eval_report_lists_false_negatives_and_positives():
    report = EvalReport(cases=[
        CaseResult(
            chat_text="A: 예시",
            score=CaseScore(
                matched=[],
                false_negatives=[GoldenExpectation(text="놓친 표현", type="협박")],
                false_positives=[Expression(text="과탐지 표현", type="기타", risk="낮음")],
            ),
        ),
    ])

    output = format_eval_report(report)

    assert '"놓친 표현" (협박)' in output
    assert '"과탐지 표현" (기타)' in output


def test_format_eval_report_shows_no_basis_when_type_never_predicted():
    report = EvalReport(cases=[
        CaseResult(
            chat_text="A: 예시",
            score=CaseScore(
                matched=[],
                false_negatives=[GoldenExpectation(text="놓친 표현", type="협박")],
                false_positives=[],
            ),
        ),
    ])

    output = format_eval_report(report)

    assert "해당 없음" in output


def test_format_eval_report_includes_risk_distribution():
    report = EvalReport(cases=[
        CaseResult(
            chat_text="A: 예시",
            score=CaseScore(
                matched=[Expression(text="예시", type="모욕", risk="높음")],
                false_negatives=[],
                false_positives=[],
            ),
        ),
    ])

    output = format_eval_report(report)

    assert "높음 1 / 중간 0 / 낮음 0" in output
