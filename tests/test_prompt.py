from judgpt.prompt import build_messages


def test_build_messages_returns_system_then_user():
    messages = build_messages("A: 안녕\nB: 안녕하세요")

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1] == {"role": "user", "content": "A: 안녕\nB: 안녕하세요"}


def test_system_prompt_mentions_all_expression_types():
    messages = build_messages("아무 텍스트")
    system_content = messages[0]["content"]

    for expression_type in ["욕설", "성희롱", "협박", "모욕", "명예훼손"]:
        assert expression_type in system_content


def test_system_prompt_forbids_citing_law_or_case():
    """MVP는 법률 RAG가 없으므로, 근거 없는 법 조문/판례 언급을 금지해야 한다
    (REQUIREMENTS.md §4, docs/02-architecture.md §4)."""
    messages = build_messages("아무 텍스트")
    system_content = messages[0]["content"]

    assert "법 조문" in system_content or "판례" in system_content


def test_system_prompt_forbids_naming_specific_criminal_offense():
    """법 조문/판례 인용 금지만으로는 구체적 죄명 언급을 막지 못한다 (예: "협박죄").
    type 필드의 분류명만 쓰도록 별도로 금지해야 한다."""
    messages = build_messages("아무 텍스트")
    system_content = messages[0]["content"]

    assert "죄명" in system_content


def test_system_prompt_distinguishes_sexual_remark_from_harassment():
    """성적 발언(단발성)과 성희롱(거부 이후 반복)을 LLM이 일관되게 구분하도록
    판단 기준이 프롬프트에 명시되어 있어야 한다 — 안 그러면 두 유형 선택이
    사실상 임의적이 된다."""
    messages = build_messages("아무 텍스트")
    system_content = messages[0]["content"]

    assert "단발성" in system_content
    assert "성희롱: 상대방이 거부 의사" in system_content


def test_system_prompt_requires_json_only_response():
    messages = build_messages("아무 텍스트")
    system_content = messages[0]["content"]

    assert "JSON" in system_content
    assert "expressions" in system_content
