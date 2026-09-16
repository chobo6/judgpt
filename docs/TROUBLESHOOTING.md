# TROUBLESHOOTING

실제 발생한 버그·장애의 근본 원인과 수정 방법을 기록한다. 개발 세션 중 실제로 겪은 것을 시간 순으로 정리했다. 최신 구현이 아래 설명과 다르면 코드가 우선이다.

## MVP 구현 (Task 1-8, 최종 리뷰, PR #1 코드리뷰)

### #1 서브에이전트 dispatch 시 `isolation: "worktree"`를 잘못 넘겨 워크트리가 중복 생성됨

**증상**: Task 1 구현 서브에이전트가 파일은 올바르게(브리프와 완전히 동일하게) 작성했지만, 테스트 실행·커밋을 못 하고 BLOCKED로 끝났다.

**원인**: 컨트롤러가 이미 전용 워크트리(`judgpt-mvp`)를 준비해둔 상태에서, Agent 디스패치에 `isolation: "worktree"`를 추가로 넘겨 별도의 워크트리(`agent-af3242df63c3cb4c0`)가 새로 생성됐다. 서브에이전트가 원래 워크트리로 돌아가려고 `EnterWorktree`를 호출하면서 샌드박스가 잠겼다. (repoview 프로젝트에서도 동일한 실수가 한 번 있었던 패턴 — 재발함.)

**해결**: 컨트롤러가 별도 워크트리에 생성된 4개 파일이 브리프와 바이트 단위로 동일함을 확인한 뒤 올바른 워크트리로 복사, 테스트 실행 후 직접 커밋. 스트레이 워크트리/브랜치는 삭제. **이후 모든 태스크 디스패치에서 `isolation: "worktree"`를 빼고 진행** — 컨트롤러가 이미 전용 워크트리를 관리 중일 때는 이 옵션을 절대 넘기지 말 것.

### #2 `OllamaLLM.call()`이 `None`을 반환할 수 있는데 `LLM` Protocol은 `-> str`을 약속함

**증상**: (최종 리뷰에서 발견, 실사용 전 선제 수정) Ollama 응답의 `message.content`가 `None`이면 `analyzer.py`의 `json.loads(None)`이 잡히지 않는 `TypeError`를 던져, 재시도 로직을 완전히 우회했다.

**원인**: openai SDK의 `completion.choices[0].message.content` 타입이 `str | None`인데, `OllamaLLM.call()`이 이를 그대로 반환했다.

**해결**: `return completion.choices[0].message.content or ""`로 변경 — 빈 문자열은 기존 `JSONDecodeError` 재시도 경로로 자연스럽게 흘러간다 (commit `d544b96`).

### #3 `--json` 출력에서 참고용 고지 문구가 빠짐

**증상**: (최종 리뷰에서 발견) `python -m judgpt.analyze --json`으로 실행하면 REQUIREMENTS.md §4가 요구하는 "참고용 정보" 고지 문구가 전혀 출력되지 않았다.

**원인**: `run()`의 `--json` 분기가 `format_report()`를 거치지 않고 순수 JSON만 반환하는데, `DISCLAIMER`는 `format_report()` 안에서만 붙었다.

**해결**: `run()`은 순수 함수로 그대로 두고(스키마/테스트 계약 유지), `main()`에서 `--json`일 때 stdout에 JSON을 출력한 뒤 `DISCLAIMER`를 **stderr**로 추가 출력 — stdout은 여전히 기계가 파싱 가능한 순수 JSON으로 남는다 (commit `d544b96`).

### #4 Windows cp949 콘솔에서 리다이렉트 시 `UnicodeEncodeError`

**증상**: (최종 리뷰에서 실측 재현) `python -m judgpt.analyze --file chat.txt > result.txt`처럼 출력을 리다이렉트하면 고지 문구 앞의 `⚠️` 이모지가 cp949로 인코딩되지 않아 크래시했다. 대화형 콘솔에서는 재현되지 않아(Windows 콘솔은 UTF-16 I/O) 테스트로 못 걸렀다.

**해결**: `main()` 시작 시 `sys.stdout.reconfigure(encoding="utf-8")` 추가 (commit `d544b96`). 이후 PR #1 코드리뷰에서 **stdin에는 이 처리가 빠졌다는 추가 지적**을 받아 `sys.stdin`에도 `hasattr(sys.stdin, "reconfigure")`로 방어하며 `utf-8-sig`로 reconfigure 추가 (commit `754ca59`) — 테스트에서 `sys.stdin`을 `io.StringIO`로 monkeypatch하는 기존 테스트가 `reconfigure` 메서드가 없어 깨지지 않도록 `hasattr` 가드를 넣은 게 핵심.

### #5 `OllamaLLM.call()`이 `choices`가 빈 리스트일 때 `IndexError`

**증상**: (PR #1 코드리뷰에서 발견, 선제 수정 — 실제로는 아직 안 겪음) 프록시 오류나 컨텐츠 필터링으로 `completion.choices == []`가 오면 `completion.choices[0]`에서 잡히지 않는 `IndexError`가 나 날것 traceback이 사용자에게 보였다.

**해결**: `if not completion.choices: return ""` 가드 추가 — 빈 응답도 기존 재시도 경로로 흡수된다 (commit `754ca59`).

### #6 `--file ""`(빈 문자열)이 "파일 안 줌"과 동일하게 처리되어 stdin 대기로 빠짐

**증상**: (PR #1 코드리뷰에서 발견) `--file "$VAR"`를 스크립트로 넘길 때 `$VAR`가 비어있으면 에러 없이 조용히 stdin 읽기로 전환되어, 대화형 셸에서는 그냥 멈춘 것처럼 보였다.

**원인**: `if args.file:`이 빈 문자열을 falsy로 취급해 "파일 인자 없음"과 구분하지 못했다.

**해결**: `if args.file is not None:`으로 변경 — 빈 문자열이면 `open("")`이 `FileNotFoundError`를 던지고, 기존 "파일을 찾을 수 없습니다" 처리 경로로 자연스럽게 들어간다 (commit `754ca59`).

### #7 워크트리 삭제 후 빈 디렉토리가 남음 (Windows, OneDrive 동기화 추정)

**증상**: PR #1 병합 후 `git worktree remove`가 내부 파일은 전부 지웠지만 최상위 디렉토리(`​.claude/worktrees/judgpt-mvp`) 자체는 `Device or resource busy`로 지우지 못했다.

**원인**: 확실하지 않음 — OneDrive가 해당 폴더를 동기화 중이었거나 다른 프로세스가 핸들을 쥐고 있었을 가능성. git 메타데이터상으로는 워크트리 등록이 정상적으로 해제됨(`git worktree list`에 더 이상 안 뜸) — 빈 폴더만 남은 상태로 기능상 문제는 없음.

**해결**: 별도 조치 없이 방치 — 다음에 같은 디렉토리를 다시 쓰려고 할 때 지워지지 않으면, OneDrive 동기화가 끝난 뒤 재시도하거나 수동으로 지울 것.

### #8 워크트리 삭제 후 메인 저장소에서 `pytest`가 전부 `ModuleNotFoundError`류 수집 에러로 실패

**증상**: PR #1 병합 후 메인 저장소(`workspace/judgpt`)에서 `pytest`를 돌리니 8개 파일이 전부 수집 단계에서 에러가 났다.

**원인**: `pip install -e ".[dev]"`를 워크트리(`.claude/worktrees/judgpt-mvp`) 안에서 실행했었는데, editable install은 그 소스 경로로 링크를 건다. 워크트리를 지우고 나니 그 경로가 사라져 `judgpt` 패키지 자체를 못 찾게 됐다.

**해결**: 메인 저장소 루트에서 `pip install -e ".[dev]"`를 다시 실행 — editable install 경로가 메인 저장소로 갱신됨. **워크트리에서 병합 작업을 마치고 메인 저장소로 돌아올 때마다, 워크트리 안에서 `pip install -e`를 했었다면 메인 저장소에서 다시 설치해야 한다는 점을 기억할 것.**

### #9 `--json` 모드의 stderr 고지 문구가 cp949로 잘못 인코딩됨 (실제 Ollama로 수동 검증하다 발견)

**증상**: 실제 Ollama 설치 후 `python -m judgpt.analyze --file ... --json 2>err.txt`로 수동 검증하던 중, `err.txt`의 바이트가 UTF-8로 디코딩되지 않았다(`UnicodeDecodeError`). 유닛 테스트(`capsys` 기반)는 이 문제를 못 잡았다.

**원인**: #4에서 `sys.stdout`만 `reconfigure(encoding="utf-8")`했고, `--json` 모드의 `DISCLAIMER`를 출력하는 `sys.stderr`는 빠뜨렸다. 크래시는 안 났다 — 이 문구에 쓰인 한글 글자들이 cp949로도 인코딩 가능한 범위라 조용히 잘못된 인코딩(cp949)으로 써졌을 뿐이다(`⚠️` 이모지처럼 cp949 밖의 문자였다면 #4와 동일하게 크래시했을 것).

**해결**: `main()` 시작부에 `sys.stderr.reconfigure(encoding="utf-8")`을 `sys.stdout` 옆에 추가 (commit 예정). **교훈: 콘솔 인코딩 문제는 크래시가 안 나도 잘못된 바이트가 조용히 써질 수 있으므로, stdout/stderr 둘 다 프로그램이 쓰는 모든 스트림에 동일하게 적용해야 한다 — 하나만 고치고 넘어가면 재발한다.**
