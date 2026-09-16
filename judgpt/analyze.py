import argparse
import json
import sys

from judgpt import config
from judgpt.analyzer import AnalysisError, analyze
from judgpt.llm import LLM, OllamaLLM
from judgpt.report import format_report


def run(chat_text: str, llm: LLM, as_json: bool) -> str:
    try:
        result = analyze(chat_text, llm)
    except AnalysisError as exc:
        raise SystemExit(str(exc)) from exc

    if as_json:
        return json.dumps(result.model_dump(), ensure_ascii=False, indent=2)
    return format_report(result)


def main(argv: list[str] | None = None, llm: LLM | None = None) -> None:
    parser = argparse.ArgumentParser(description="채팅 로그에서 유해 표현을 탐지한다")
    parser.add_argument("--file", help="분석할 채팅 텍스트 파일 경로. 생략 시 stdin에서 읽는다.")
    parser.add_argument(
        "--json", action="store_true", help="사람이 읽는 리포트 대신 원본 JSON을 출력한다"
    )
    args = parser.parse_args(argv)

    if args.file:
        with open(args.file, encoding="utf-8") as f:
            chat_text = f.read()
    else:
        chat_text = sys.stdin.read()

    if not chat_text.strip():
        raise SystemExit("입력이 비어 있습니다")

    if llm is None:
        llm = OllamaLLM(model=config.MODEL, base_url=config.OLLAMA_BASE_URL)

    print(run(chat_text, llm, args.json))


if __name__ == "__main__":
    main()
