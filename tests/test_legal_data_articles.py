from judgpt.legal_data.articles import NEEDS_VERIFICATION, lookup_articles


def test_lookup_articles_returns_base_mapping_for_known_type():
    articles = lookup_articles("모욕")
    assert articles == ["형법 제311조(모욕)"]


def test_lookup_articles_returns_empty_list_for_unmapped_type():
    assert lookup_articles("기타") == []


def test_lookup_articles_adds_online_aggravation_when_online():
    articles = lookup_articles("협박", is_online=True)
    assert "형법 제283조(협박)" in articles
    assert "성폭력범죄의 처벌 등에 관한 특례법 제14조의3(촬영물과 편집물 등을 이용한 협박ㆍ강요)" in articles


def test_lookup_articles_online_flag_has_no_effect_without_aggravation_mapping():
    assert lookup_articles("모욕", is_online=True) == ["형법 제311조(모욕)"]


def test_lookup_articles_covers_sexual_harassment_type():
    assert lookup_articles("성희롱") == [
        "성폭력범죄의 처벌 등에 관한 특례법 제13조(통신매체를 이용한 음란행위)",
        "스토킹범죄의 처벌 등에 관한 법률 제18조(스토킹범죄)",
    ]


def test_lookup_articles_sexual_remark_and_harassment_are_distinct():
    """성적 발언(단발성)과 성희롱(거부 이후 반복)은 서로 다른 판단 기준을 가지므로
    조문 매핑도 달라야 한다 — 성희롱만 반복성 요건이 있는 스토킹처벌법을 추가로 포함."""
    assert lookup_articles("성적 발언") != lookup_articles("성희롱")


def test_needs_verification_flag_is_false_after_manual_confirmation():
    """2026-09-16에 법제처 Open API(judgpt/legal_data/fetch_statutes.py)로 형법/
    정보통신망법/성폭력처벌특례법/스토킹처벌법의 모든 인용 조번호·제목을 실제
    조문과 대조해 확인했다. 조문이 개정되면 이 플래그를 다시 True로 되돌리고
    재확인할 것 — 이 테스트는 그 상태를 명시적으로 고정해둔다."""
    assert NEEDS_VERIFICATION is False
