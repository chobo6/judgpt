NEEDS_VERIFICATION = True
"""법제처 Open API(judgpt/legal_data/fetch_statutes.py, Task 8)로 아래 조번호를
실제로 확인하기 전까지는 True로 유지한다. 확인 후 사람이 직접 False로 바꾼다."""

ARTICLE_MAP: dict[str, list[str]] = {
    "모욕": ["형법 제311조(모욕)"],
    "협박": ["형법 제283조(협박)"],
    "명예훼손": ["형법 제307조(명예훼손)", "형법 제309조(출판물등에 의한 명예훼손)"],
    "성적 발언": ["성폭력범죄의 처벌 등에 관한 특례법 제13조(통신매체를 이용한 음란행위)"],
    # 성희롱과 성적 발언은 현재 judgpt의 프롬프트/스키마에서 명확히 구분되지 않는
    # 인접 카테고리라, 채팅 맥락에서 가장 근접한 동일 조문을 매핑한다 — 두 유형을
    # 실제로 구분해야 한다면 prompt.py의 유형 정의부터 재검토할 것.
    "성희롱": ["성폭력범죄의 처벌 등에 관한 특례법 제13조(통신매체를 이용한 음란행위)"],
}

ONLINE_AGGRAVATION_MAP: dict[str, list[str]] = {
    "협박": ["성폭력범죄의 처벌 등에 관한 특례법 제14조의3(촬영물 등을 이용한 협박·강요)"],
    "명예훼손": ["정보통신망 이용촉진 및 정보보호 등에 관한 법률 제70조(벌칙)"],
}


def lookup_articles(expression_type: str, *, is_online: bool = False) -> list[str]:
    articles = list(ARTICLE_MAP.get(expression_type, []))
    if is_online:
        articles += ONLINE_AGGRAVATION_MAP.get(expression_type, [])
    return articles
