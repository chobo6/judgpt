NEEDS_VERIFICATION = True
"""법제처 Open API(judgpt/legal_data/fetch_statutes.py, Task 8)로 아래 조번호를
실제로 확인하기 전까지는 True로 유지한다. 확인 후 사람이 직접 False로 바꾼다."""

ARTICLE_MAP: dict[str, list[str]] = {
    "모욕": ["형법 제311조(모욕)"],
    "협박": ["형법 제283조(협박)"],
    "명예훼손": ["형법 제307조(명예훼손)", "형법 제309조(출판물등에 의한 명예훼손)"],
    "성적 발언": ["성폭력범죄의 처벌 등에 관한 특례법 제13조(통신매체를 이용한 음란행위)"],
    # 성적 발언(단발성 성적 표현)과 달리 성희롱은 거부 의사 표시 이후에도 성적
    # 언동이 반복되는 경우다(prompt.py의 구분 기준 참고) — 이 반복성 요건이
    # 스토킹범죄의 정의(같은 법 제2조: "의사에 반해 지속적·반복적으로" 등)와
    # 맞아떨어져 스토킹처벌법을 함께 매핑한다.
    "성희롱": [
        "성폭력범죄의 처벌 등에 관한 특례법 제13조(통신매체를 이용한 음란행위)",
        "스토킹범죄의 처벌 등에 관한 법률 제18조(스토킹범죄)",
    ],
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
