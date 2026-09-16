from judgpt.legal_data.cases import CaseEntry, load_cases


def test_load_cases_returns_curated_entries():
    cases = load_cases()
    assert len(cases) >= 4
    assert all(isinstance(c, CaseEntry) for c in cases)


def test_load_cases_covers_each_core_type_at_least_once():
    cases = load_cases()
    types_covered = {c.related_type for c in cases}
    assert {"모욕", "협박", "명예훼손", "성적 발언"} <= types_covered


def test_load_cases_every_entry_has_a_source_url():
    cases = load_cases()
    for case in cases:
        assert case.source_url.startswith("http")


def test_load_cases_accepts_custom_path(tmp_path):
    custom_path = tmp_path / "custom_cases.json"
    custom_path.write_text(
        '[{"case_id": "테스트 사건", "court": "테스트법원", "summary": "요약", '
        '"related_type": "모욕", "source_url": "https://example.com"}]',
        encoding="utf-8",
    )
    cases = load_cases(custom_path)
    assert len(cases) == 1
    assert cases[0].case_id == "테스트 사건"
