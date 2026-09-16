from judgpt.legal_data.articles import NEEDS_VERIFICATION, lookup_articles


def test_lookup_articles_returns_base_mapping_for_known_type():
    articles = lookup_articles("모욕")
    assert articles == ["형법 제311조(모욕)"]


def test_lookup_articles_returns_empty_list_for_unmapped_type():
    assert lookup_articles("기타") == []


def test_lookup_articles_adds_online_aggravation_when_online():
    articles = lookup_articles("협박", is_online=True)
    assert "형법 제283조(협박)" in articles
    assert "성폭력범죄의 처벌 등에 관한 특례법 제14조의3(촬영물 등을 이용한 협박·강요)" in articles


def test_lookup_articles_online_flag_has_no_effect_without_aggravation_mapping():
    assert lookup_articles("모욕", is_online=True) == ["형법 제311조(모욕)"]


def test_lookup_articles_covers_sexual_harassment_type():
    assert lookup_articles("성희롱") == [
        "성폭력범죄의 처벌 등에 관한 특례법 제13조(통신매체를 이용한 음란행위)"
    ]


def test_needs_verification_flag_is_true_until_manually_confirmed():
    """이 플래그가 True인 동안은 출력에 재검증 필요 경고가 붙는다(Task 6 참고).
    법제처 API(Task 8)로 실제 조문을 확인한 뒤에만 False로 바꿀 것 — 이 테스트는
    그 상태 전환을 깜빡하지 않도록 상기시키는 용도다."""
    assert NEEDS_VERIFICATION is True
