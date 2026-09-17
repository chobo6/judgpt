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


def test_score_case_finds_optimal_matching_when_greedy_order_would_fail():
    """predicted[0]("시발 개빡치네")은 expected[0]("시발")과 expected[1]("개빡치네")
    둘 다와 매칭 가능하다. 순서대로 훑는 그리디 매칭이면 predicted[0]이 expected[0]을
    먼저 가로채서 predicted[1]("시발")이 짝을 못 찾아 1 TP/1 FP/1 FN이 되지만,
    최적 매칭은 predicted[0]<->expected[1], predicted[1]<->expected[0]로 2 TP/0 FP/0 FN을 찾아야 한다."""
    predicted = [_expr("시발 개빡치네", "욕설"), _expr("시발", "욕설")]
    expected = [_exp("시발", "욕설"), _exp("개빡치네", "욕설")]

    score = score_case(predicted, expected)

    assert len(score.matched) == 2
    assert score.false_positives == []
    assert score.false_negatives == []


from judgpt.eval import run_eval
from judgpt.eval_data.golden import GoldenCase, GoldenExpectation
from judgpt.llm import FakeLLM


def test_run_eval_continues_after_one_case_raises_analysis_error():
    """analyze()가 JSON 파싱을 두 번 연속 실패하면 AnalysisError를 던진다(analyzer.py 재시도 로직).
    run_eval은 그 케이스만 error로 기록하고 나머지 케이스는 계속 채점해야 한다."""
    cases = [
        GoldenCase(chat_text="A: 깨진 응답", expected=[]),
        GoldenCase(chat_text="A: 안녕", expected=[]),
    ]
    llm = FakeLLM([
        "JSON 아님",
        "여전히 JSON 아님",
        '{"expressions": []}',
    ])

    report = run_eval(cases, llm)

    assert len(report.cases) == 2
    assert report.cases[0].score is None
    assert report.cases[0].error is not None
    assert report.cases[1].score is not None
    assert report.cases[1].error is None


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

    # Check that "해당 없음" appears on the per-type line for "협박", not just anywhere in the output
    lines = output.split('\n')
    type_line = [l for l in lines if l.startswith('  협박 ')][0]
    assert "해당 없음" in type_line


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


def test_format_eval_report_lists_errored_cases_and_excludes_them_from_metrics():
    report = EvalReport(cases=[
        CaseResult(chat_text="A: 실패", error="모델 응답이 올바른 JSON 형식이 아닙니다"),
        CaseResult(
            chat_text="A: 성공",
            score=CaseScore(
                matched=[Expression(text="예시", type="모욕", risk="높음")],
                false_negatives=[],
                false_positives=[],
            ),
        ),
    ])

    output = format_eval_report(report)

    assert "2개 케이스" in output
    assert "1건 분석 실패" in output
    assert "[케이스 1] 모델 응답이 올바른 JSON 형식이 아닙니다" in output
    assert "Precision 1.00" in output


def test_format_eval_report_shows_no_basis_for_overall_metrics():
    report = EvalReport(cases=[
        CaseResult(
            chat_text="A: 안녕",
            score=CaseScore(
                matched=[],
                false_negatives=[],
                false_positives=[],
            ),
        ),
    ])

    output = format_eval_report(report)

    assert "해당 없음" in output
    # Check that "해당 없음" appears in the overall metrics line (Precision/Recall both 0.00)
    lines = output.split('\n')
    overall_line = [l for l in lines if l.startswith('전체:')][0]
    assert "해당 없음" in overall_line


import json

from judgpt.eval import main
from judgpt.eval_data.golden import GoldenCase
from judgpt.llm import FakeLLM


def test_main_prints_human_report_by_default(capsys):
    llm = FakeLLM(['{"expressions": []}'])
    cases = [GoldenCase(chat_text="A: 안녕", expected=[])]

    main([], llm=llm, cases=cases)

    captured = capsys.readouterr()
    assert "1개 케이스" in captured.out


def test_main_json_flag_outputs_valid_json(capsys):
    llm = FakeLLM(['{"expressions": []}'])
    cases = [GoldenCase(chat_text="A: 안녕", expected=[])]

    main(["--json"], llm=llm, cases=cases)

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["cases"][0]["chat_text"] == "A: 안녕"


def test_main_without_cases_loads_default_golden_dataset(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "judgpt.eval.load_golden_cases",
        lambda: calls.append("called") or [],
    )
    llm = FakeLLM([])

    main([], llm=llm)

    assert calls == ["called"]


def test_main_exits_with_clean_message_when_ollama_unreachable():
    import httpx
    import pytest
    from openai import APIConnectionError

    class _ConnectionErrorLLM:
        def call(self, messages):
            raise APIConnectionError(
                request=httpx.Request("POST", "http://localhost:11434/v1/chat/completions")
            )

    cases = [GoldenCase(chat_text="A: 예시", expected=[])]

    with pytest.raises(SystemExit, match="Ollama가.*응답하지 않습니다"):
        main([], llm=_ConnectionErrorLLM(), cases=cases)


def test_main_without_llm_constructs_ollama_llm_with_zero_temperature(monkeypatch):
    captured_kwargs = {}

    class _FakeOllamaLLM:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

        def call(self, messages):
            return '{"expressions": []}'

    monkeypatch.setattr("judgpt.eval.OllamaLLM", _FakeOllamaLLM)
    cases = [GoldenCase(chat_text="A: 안녕", expected=[])]

    main([], cases=cases)

    assert captured_kwargs["temperature"] == 0
