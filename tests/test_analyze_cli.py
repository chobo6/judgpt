import json

import pytest

from judgpt.analyze import main, run
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
