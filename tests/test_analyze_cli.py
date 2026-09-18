import json

import pytest

from judgpt.analyze import main, run
from judgpt.embedder import FakeEmbedder
from judgpt.legal_data.cases import load_cases
from judgpt.llm import FakeLLM
from judgpt.report import DISCLAIMER


def test_run_returns_human_report_by_default():
    llm = FakeLLM(['{"expressions": []}'])

    output = run("A: 안녕", llm, as_json=False)

    assert "문제 표현이 발견되지 않았습니다" in output
    assert DISCLAIMER in output


def test_run_returns_raw_json_when_requested():
    llm = FakeLLM(['{"expressions": []}'])

    output = run("A: 안녕", llm, as_json=True)

    assert json.loads(output) == {"expressions": []}


def test_run_raises_system_exit_on_analysis_failure():
    llm = FakeLLM(["JSON 아님", "여전히 JSON 아님"])

    with pytest.raises(SystemExit):
        run("A: 안녕", llm, as_json=False)


def test_main_reads_file_and_prints_report(tmp_path, capsys):
    chat_file = tmp_path / "chat.txt"
    chat_file.write_text("A: 안녕", encoding="utf-8")
    fake = FakeLLM(['{"expressions": []}'])

    main(["--file", str(chat_file)], llm=fake)

    captured = capsys.readouterr()
    assert "문제 표현이 발견되지 않았습니다" in captured.out
    assert DISCLAIMER in captured.out


def test_main_json_flag_outputs_valid_json(tmp_path, capsys):
    chat_file = tmp_path / "chat.txt"
    chat_file.write_text("A: 안녕", encoding="utf-8")
    fake = FakeLLM(['{"expressions": []}'])

    main(["--file", str(chat_file), "--json"], llm=fake)

    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"expressions": []}


def test_main_reads_stdin_when_no_file_given(monkeypatch, capsys):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("A: 안녕"))
    fake = FakeLLM(['{"expressions": []}'])

    main([], llm=fake)

    captured = capsys.readouterr()
    assert "문제 표현이 발견되지 않았습니다" in captured.out


def test_main_exits_on_empty_input(tmp_path):
    chat_file = tmp_path / "chat.txt"
    chat_file.write_text("   ", encoding="utf-8")

    with pytest.raises(SystemExit, match="입력이 비어 있습니다"):
        main(["--file", str(chat_file)], llm=FakeLLM([]))


def test_main_json_flag_prints_disclaimer_to_stderr(tmp_path, capsys):
    chat_file = tmp_path / "chat.txt"
    chat_file.write_text("A: 안녕", encoding="utf-8")
    fake = FakeLLM(['{"expressions": []}'])

    main(["--file", str(chat_file), "--json"], llm=fake)

    captured = capsys.readouterr()
    assert DISCLAIMER in captured.err
    assert DISCLAIMER not in captured.out


def test_main_exits_with_clean_message_on_missing_file(tmp_path):
    missing_file = tmp_path / "nonexistent.txt"

    with pytest.raises(SystemExit, match="파일을 찾을 수 없습니다"):
        main(["--file", str(missing_file)], llm=FakeLLM([]))


def test_main_treats_empty_file_arg_as_missing_file_not_stdin_fallback():
    with pytest.raises(SystemExit, match="파일을 찾을 수 없습니다"):
        main(["--file", ""], llm=FakeLLM([]))


def test_main_reconfigures_stdin_encoding_when_supported(monkeypatch, capsys):
    calls = []

    class _FakeStdin:
        def reconfigure(self, encoding):
            calls.append(encoding)

        def read(self):
            return "A: 안녕"

    monkeypatch.setattr("sys.stdin", _FakeStdin())
    fake = FakeLLM(['{"expressions": []}'])

    main([], llm=fake)

    assert calls == ["utf-8-sig"]


def test_run_legal_flag_adds_applicable_laws():
    llm = FakeLLM(['{"expressions": [{"text": "예시", "type": "모욕", "risk": "높음"}]}'])
    # 실제 cases.json의 판례 전부에 대해 임베딩을 준비해둔다 — 코퍼스가 늘어나도
    # 이 테스트가 깨지지 않도록 하드코딩된 문자열 대신 load_cases()로 채운다.
    embedder_vectors = {case.summary: [0.1, 0.2, 0.3] for case in load_cases()}
    embedder_vectors["예시"] = [0.1, 0.2, 0.3]
    embedder = FakeEmbedder(embedder_vectors)

    output = run("A: 예시", llm, as_json=True, legal=True, embedder=embedder)

    data = json.loads(output)
    assert data["expressions"][0]["applicable_laws"] == ["형법 제311조(모욕)"]


def test_run_legal_true_without_embedder_raises_value_error():
    llm = FakeLLM(['{"expressions": []}'])

    with pytest.raises(ValueError, match="embedder"):
        run("A: 예시", llm, as_json=True, legal=True, embedder=None)


def test_main_legal_flag_wires_embedder_and_prints_report(tmp_path, capsys):
    chat_file = tmp_path / "chat.txt"
    chat_file.write_text("A: 예시", encoding="utf-8")
    fake_llm = FakeLLM(['{"expressions": []}'])
    # 실제 cases.json의 판례 전부에 대해 임베딩을 준비해둔다 — 코퍼스가 늘어나도
    # 이 테스트가 깨지지 않도록 하드코딩된 문자열 대신 load_cases()로 채운다.
    embedder_vectors = {case.summary: [0.1, 0.2, 0.3] for case in load_cases()}
    fake_embedder = FakeEmbedder(embedder_vectors)

    main(["--file", str(chat_file), "--legal"], llm=fake_llm, embedder=fake_embedder)

    captured = capsys.readouterr()
    assert "문제 표현이 발견되지 않았습니다" in captured.out


def test_main_online_flag_without_legal_has_no_effect(tmp_path, capsys):
    chat_file = tmp_path / "chat.txt"
    chat_file.write_text("A: 예시", encoding="utf-8")
    fake_llm = FakeLLM(['{"expressions": []}'])

    main(["--file", str(chat_file), "--online"], llm=fake_llm)

    captured = capsys.readouterr()
    assert "문제 표현이 발견되지 않았습니다" in captured.out
