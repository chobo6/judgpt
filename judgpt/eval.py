import argparse
import json
import sys

from pydantic import BaseModel

from judgpt import config
from judgpt.analyzer import analyze
from judgpt.eval_data.golden import GoldenCase, GoldenExpectation, load_golden_cases
from judgpt.llm import LLM, OllamaLLM
from judgpt.schema import Expression


class CaseScore(BaseModel):
    matched: list[Expression]
    false_negatives: list[GoldenExpectation]
    false_positives: list[Expression]


def score_case(predicted: list[Expression], expected: list[GoldenExpectation]) -> CaseScore:
    """순수 함수. LLM/Ollama 없이 유닛테스트로 전부 커버 가능.
    predicted를 순서대로 순회하며, 각 predicted마다 아직 매칭 안 된 expected 중
    (type 일치 + 부분 문자열 포함) 조건을 만족하는 첫 번째 항목과 짝짓는다."""
    remaining_expected = list(expected)
    matched: list[Expression] = []
    false_positives: list[Expression] = []

    for pred in predicted:
        match_index = None
        for i, exp in enumerate(remaining_expected):
            if pred.type == exp.type and (exp.text in pred.text or pred.text in exp.text):
                match_index = i
                break
        if match_index is None:
            false_positives.append(pred)
        else:
            matched.append(pred)
            remaining_expected.pop(match_index)

    return CaseScore(matched=matched, false_negatives=remaining_expected, false_positives=false_positives)


class CaseResult(BaseModel):
    chat_text: str
    score: CaseScore


class EvalReport(BaseModel):
    cases: list[CaseResult]


def run_eval(cases: list[GoldenCase], llm: LLM) -> EvalReport:
    results = []
    for case in cases:
        analysis = analyze(case.chat_text, llm)
        score = score_case(analysis.expressions, case.expected)
        results.append(CaseResult(chat_text=case.chat_text, score=score))
    return EvalReport(cases=results)


def format_eval_report(report: EvalReport) -> str:
    all_scores = [c.score for c in report.cases]
    total_tp = sum(len(s.matched) for s in all_scores)
    total_fp = sum(len(s.false_positives) for s in all_scores)
    total_fn = sum(len(s.false_negatives) for s in all_scores)

    lines = [f"[Eval 결과] {len(report.cases)}개 케이스", ""]

    overall_p, overall_r, overall_f1 = _prf1(total_tp, total_fp, total_fn)
    overall_p_note = " (해당 없음)" if total_tp + total_fp == 0 else ""
    overall_r_note = " (해당 없음)" if total_tp + total_fn == 0 else ""
    lines.append(
        f"전체: Precision {overall_p:.2f} ({total_tp}/{total_tp + total_fp}){overall_p_note}  "
        f"Recall {overall_r:.2f} ({total_tp}/{total_tp + total_fn}){overall_r_note}  F1 {overall_f1:.2f}"
    )
    lines.append("")

    lines.append("유형별:")
    for t in sorted(_all_types(all_scores)):
        tp = sum(1 for s in all_scores for m in s.matched if m.type == t)
        fp = sum(1 for s in all_scores for m in s.false_positives if m.type == t)
        fn = sum(1 for s in all_scores for m in s.false_negatives if m.type == t)
        p, r, f1 = _prf1(tp, fp, fn)
        p_note = " (해당 없음)" if tp + fp == 0 else ""
        r_note = " (해당 없음)" if tp + fn == 0 else ""
        lines.append(
            f"  {t} P {p:.2f} ({tp}/{tp + fp}){p_note}  "
            f"R {r:.2f} ({tp}/{tp + fn}){r_note}  F1 {f1:.2f}"
        )
    lines.append("")

    lines.append("놓친 표현 (FN):")
    fn_items = [(i, item) for i, s in enumerate(all_scores, start=1) for item in s.false_negatives]
    if not fn_items:
        lines.append("  없음")
    else:
        for i, item in fn_items:
            lines.append(f'  [케이스 {i}] "{item.text}" ({item.type})')
    lines.append("")

    lines.append("과탐지 (FP):")
    fp_items = [(i, item) for i, s in enumerate(all_scores, start=1) for item in s.false_positives]
    if not fp_items:
        lines.append("  없음")
    else:
        for i, item in fp_items:
            lines.append(f'  [케이스 {i}] "{item.text}" ({item.type}) — 예측했지만 정답에 없음')
    lines.append("")

    risk_counts = {"높음": 0, "중간": 0, "낮음": 0}
    for s in all_scores:
        for m in s.matched:
            risk_counts[m.risk] += 1
    lines.append(
        f"예측 risk 분포 (참고용): 높음 {risk_counts['높음']} / "
        f"중간 {risk_counts['중간']} / 낮음 {risk_counts['낮음']}"
    )

    return "\n".join(lines)


def _prf1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def _all_types(scores: list["CaseScore"]) -> set[str]:
    types: set[str] = set()
    for s in scores:
        types.update(m.type for m in s.matched)
        types.update(m.type for m in s.false_positives)
        types.update(e.type for e in s.false_negatives)
    return types


def main(
    argv: list[str] | None = None,
    llm: LLM | None = None,
    cases: list[GoldenCase] | None = None,
) -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="골든 데이터셋으로 유해 표현 탐지 정확도를 측정한다",
        prog="python -m judgpt.eval",
    )
    parser.add_argument(
        "--json", action="store_true", help="사람이 읽는 리포트 대신 원본 JSON을 출력한다"
    )
    args = parser.parse_args(argv)

    if llm is None:
        llm = OllamaLLM(model=config.MODEL, base_url=config.OLLAMA_BASE_URL)
    if cases is None:
        cases = load_golden_cases()

    report = run_eval(cases, llm)

    if args.json:
        print(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))
    else:
        print(format_eval_report(report))


if __name__ == "__main__":
    main()
