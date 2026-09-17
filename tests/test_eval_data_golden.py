from judgpt.eval_data.golden import GoldenCase, load_golden_cases


def test_load_golden_cases_returns_curated_entries():
    cases = load_golden_cases()
    assert len(cases) >= 10
    assert all(isinstance(c, GoldenCase) for c in cases)


def test_load_golden_cases_covers_each_core_type_at_least_once():
    cases = load_golden_cases()
    types_covered = {exp.type for c in cases for exp in c.expected}
    assert {"욕설", "성희롱", "협박", "모욕", "명예훼손", "성적 발언"} <= types_covered


def test_load_golden_cases_includes_benign_cases_with_no_expected():
    cases = load_golden_cases()
    assert any(c.expected == [] for c in cases)


def test_load_golden_cases_accepts_custom_path(tmp_path):
    custom_path = tmp_path / "custom_golden.json"
    custom_path.write_text(
        '[{"chat_text": "A: 안녕", "expected": []}]',
        encoding="utf-8",
    )
    cases = load_golden_cases(custom_path)
    assert len(cases) == 1
    assert cases[0].chat_text == "A: 안녕"
