import argparse
import json
import sys

from openai import APIConnectionError
from pydantic import BaseModel

from judgpt import config
from judgpt.analyzer import AnalysisError, analyze
from judgpt.eval_data.golden import GoldenCase, GoldenExpectation, load_golden_cases
from judgpt.llm import LLM, OllamaLLM
from judgpt.schema import Expression


class CaseScore(BaseModel):
    matched: list[Expression]
    false_negatives: list[GoldenExpectation]
    false_positives: list[Expression]


def score_case(predicted: list[Expression], expected: list[GoldenExpectation]) -> CaseScore:
    """순수 함수. LLM/Ollama 없이 유닛테스트로 전부 커버 가능.
    predicted-expected 쌍 중 (type 일치 + 부분 문자열 포함) 조건을 만족하는 쌍들로
    이분 그래프를 만들고, 매칭 개수(TP)를 최대화하는 1:1 매칭(Kuhn's algorithm)을 찾는다.
    순서대로 훑는 그리디 매칭은 같은 type의 expected가 여럿일 때 실제로는 완전히
    맞출 수 있는 경우에도 순서 때문에 FP/FN을 잘못 만들어낼 수 있어 최적 매칭을 쓴다."""
    candidates: list[list[int]] = [
        [j for j, exp in enumerate(expected) if pred.type == exp.type and (exp.text in pred.text or pred.text in exp.text)]
        for pred in predicted
    ]
    match_to_pred: list[int] = [-1] * len(expected)

    def try_match(pred_idx: int, visited: set[int]) -> bool:
        for exp_idx in candidates[pred_idx]:
            if exp_idx in visited:
                continue
            visited.add(exp_idx)
            if match_to_pred[exp_idx] == -1 or try_match(match_to_pred[exp_idx], visited):
                match_to_pred[exp_idx] = pred_idx
                return True
        return False

    for pred_idx in range(len(predicted)):
        try_match(pred_idx, set())

    matched_pred_indices = {pred_idx for pred_idx in match_to_pred if pred_idx != -1}
    matched = [pred for i, pred in enumerate(predicted) if i in matched_pred_indices]
    false_positives = [pred for i, pred in enumerate(predicted) if i not in matched_pred_indices]
    false_negatives = [exp for j, exp in enumerate(expected) if match_to_pred[j] == -1]

    return CaseScore(matched=matched, false_negatives=false_negatives, false_positives=false_positives)


class CaseResult(BaseModel):
    chat_text: str
    score: CaseScore | None = None
    error: str | None = None


class EvalReport(BaseModel):
    cases: list[CaseResult]


def run_eval(cases: list[GoldenCase], llm: LLM) -> EvalReport:
    """케이스 하나가 AnalysisError로 실패해도(모델이 두 번 연속 JSON을 잘못 뱉는 등)
    나머지 케이스는 계속 채점한다 — 실패한 케이스는 score 없이 error만 채워서 기록하고,
    최종 지표 계산에서는 제외한다(format_eval_report 참고)."""
    results = []
    for case in cases:
        try:
            analysis = analyze(case.chat_text, llm)
        except AnalysisError as exc:
            results.append(CaseResult(chat_text=case.chat_text, error=str(exc)))
            continue
        score = score_case(analysis.expressions, case.expected)
        results.append(CaseResult(chat_text=case.chat_text, score=score))
    return EvalReport(cases=results)


def format_eval_report(report: EvalReport) -> str:
    indexed_scores = [(i, c.score) for i, c in enumerate(report.cases, start=1) if c.score is not None]
    all_scores = [s for _, s in indexed_scores]
    total_tp = sum(len(s.matched) for s in all_scores)
    total_fp = sum(len(s.false_positives) for s in all_scores)
    total_fn = sum(len(s.false_negatives) for s in all_scores)

    errored = [(i, c) for i, c in enumerate(report.cases, start=1) if c.error is not None]
    header = f"[Eval 결과] {len(report.cases)}개 케이스"
    if errored:
        header += f" ({len(errored)}건 분석 실패, 지표에서 제외)"
    lines = [header, ""]

    if errored:
        lines.append("분석 실패:")
        for i, c in errored:
            lines.append(f"  [케이스 {i}] {c.error}")
        lines.append("")

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
    fn_items = [(i, item) for i, s in indexed_scores for item in s.false_negatives]
    if not fn_items:
        lines.append("  없음")
    else:
        for i, item in fn_items:
            lines.append(f'  [케이스 {i}] "{item.text}" ({item.type})')
    lines.append("")

    lines.append("과탐지 (FP):")
    fp_items = [(i, item) for i, s in indexed_scores for item in s.false_positives]
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
        # temperature=0 — 실사용(analyze.py)과 달리 eval은 같은 입력을 반복 측정해
        # 프롬프트/모델 변경 전후를 비교해야 하므로 샘플링 변동을 없앤다.
        llm = OllamaLLM(model=config.MODEL, base_url=config.OLLAMA_BASE_URL, temperature=0)
    if cases is None:
        cases = load_golden_cases()

    try:
        report = run_eval(cases, llm)
    except APIConnectionError as exc:
        raise SystemExit(f"Ollama가 {config.OLLAMA_BASE_URL}에서 응답하지 않습니다") from exc

    if args.json:
        print(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))
    else:
        print(format_eval_report(report))


if __name__ == "__main__":
    main()
