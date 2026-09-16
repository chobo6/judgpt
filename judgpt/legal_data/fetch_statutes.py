import json
import os
import sys
import urllib.parse
import urllib.request

LAW_SEARCH_URL = "http://www.law.go.kr/DRF/lawSearch.do"

LAW_NAMES = [
    "형법",
    "정보통신망 이용촉진 및 정보보호 등에 관한 법률",
    "성폭력범죄의 처벌 등에 관한 특례법",
]


class MissingOCError(Exception):
    pass


def get_oc() -> str:
    oc = os.getenv("JUDGPT_LAW_API_OC")
    if not oc:
        raise MissingOCError(
            "JUDGPT_LAW_API_OC 환경변수가 없습니다 — 법제처 Open API 신청 승인 후 "
            "발급받은 OC 값을 설정하세요."
        )
    return oc


def search_law(law_name: str, oc: str) -> dict:
    params = {"OC": oc, "target": "law", "type": "JSON", "query": law_name}
    url = f"{LAW_SEARCH_URL}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.load(response)


def main() -> None:
    try:
        oc = get_oc()
    except MissingOCError as exc:
        raise SystemExit(str(exc)) from exc

    results = {}
    for law_name in LAW_NAMES:
        results[law_name] = search_law(law_name, oc)

    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(
        "\n위 결과를 사람이 직접 확인해 judgpt/legal_data/articles.py의 "
        "ARTICLE_MAP/ONLINE_AGGRAVATION_MAP 조번호가 맞는지 검토하고, 맞으면 "
        "NEEDS_VERIFICATION을 False로 바꾸세요.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
