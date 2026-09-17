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


def test_system_prompt_includes_implicit_threat_criterion():
    """실측(TROUBLESHOOTING.md #12)에서 "너희 집 어딘지 알아 조심해"처럼 명시적 위협
    어휘 없이 거주지 등을 언급하며 불안감을 조성하는 암시적 협박을 모델이 8/8 전부
    놓치는 패턴이 확인됐다 — 협박에도 성적 발언/성희롱처럼 판단 기준을 명시해야 한다."""
    messages = build_messages("아무 텍스트")
    system_content = messages[0]["content"]

    assert "협박: " in system_content
    assert "암시적" in system_content


def test_system_prompt_clarifies_repeated_sexual_remark_is_harassment_not_remark():
    """실측(TROUBLESHOOTING.md #14)에서 모델이 "B가 거부했는데도 반복했다"고 context에
    올바르게 추론해놓고도 type은 성적 발언으로 잘못 고르는 패턴이 확인됐다 — 반복성
    판단 기준은 있었지만 "그러면 type을 성희롱으로 바꿔야 한다"는 규칙이 명시돼
    있지 않아서였다. 이를 명시하는 문장이 프롬프트에 있어야 한다."""
    messages = build_messages("아무 텍스트")
    system_content = messages[0]["content"]

    assert "반복된" in system_content and "성적 발언이 아니라 성희롱" in system_content


def test_system_prompt_sexual_remark_definition_does_not_contradict_harassment_rule():
    """성적 발언 정의의 "반복 여부와 무관하게 판단한다"는 문장이, 성희롱 정의의
    "거부 이후 반복이면 성희롱으로 분류한다"는 규칙과 정면으로 모순된다 — 실측에서
    모델이 이 모순 때문에 앞쪽(성적 발언) 지시를 더 강하게 따르는 패턴이 나왔다.
    성적 발언 정의 쪽에서도 성희롱으로 넘어가는 예외를 명시해 모순을 없애야 한다."""
    messages = build_messages("아무 텍스트")
    system_content = messages[0]["content"]

    sexual_remark_line = [
        line for line in system_content.split("\n") if line.strip().startswith("- 성적 발언:")
    ][0]
    assert "거부" in sexual_remark_line and "성희롱" in sexual_remark_line


def test_system_prompt_requires_json_only_response():
    messages = build_messages("아무 텍스트")
    system_content = messages[0]["content"]

    assert "JSON" in system_content
    assert "expressions" in system_content
