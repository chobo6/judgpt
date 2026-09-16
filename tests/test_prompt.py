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


def test_system_prompt_requires_json_only_response():
    messages = build_messages("아무 텍스트")
    system_content = messages[0]["content"]

    assert "JSON" in system_content
    assert "expressions" in system_content
