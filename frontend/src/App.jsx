import { useState } from "react";
import { analyzeChat, fetchReplay, ApiError } from "./api";

const DISCLAIMER =
  "이 결과는 참고용 정보이며 법적 판단이 아닙니다. 실제 법적 대응이 필요하면 변호사와 상담하세요.";

function errorMessage(err) {
  // 백엔드가 400/429/502/503마다 이미 사용자에게 보여줄 수 있는 한국어 문구를
  // detail로 내려준다(judgpt/web/app.py) — 프론트에서 상태 코드별로 다시 매핑하지
  // 않고 그대로 쓴다.
  if (!(err instanceof ApiError)) return "알 수 없는 오류가 발생했습니다";
  return err.message;
}

export default function App() {
  const [tab, setTab] = useState("text");
  const [chatText, setChatText] = useState("");
  const [replayUrl, setReplayUrl] = useState("");
  const [importing, setImporting] = useState(false);
  const [legal, setLegal] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await analyzeChat(chatText, legal);
      setResult(data);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleImport(e) {
    e.preventDefault();
    setImporting(true);
    setError(null);
    try {
      const text = await fetchReplay(replayUrl);
      setChatText(text);
      setTab("text");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setImporting(false);
    }
  }

  return (
    <div>
      <h1>judgpt</h1>

      <div>
        <button type="button" onClick={() => setTab("text")} disabled={tab === "text"}>
          텍스트 붙여넣기
        </button>
        <button type="button" onClick={() => setTab("link")} disabled={tab === "link"}>
          리플레이 링크
        </button>
      </div>

      {tab === "link" && (
        <form onSubmit={handleImport}>
          <input
            type="url"
            value={replayUrl}
            onChange={(e) => setReplayUrl(e.target.value)}
            placeholder="https://mafia42.com/history/kr/..."
          />
          <button type="submit" disabled={importing}>
            {importing ? "가져오는 중..." : "가져오기"}
          </button>
        </form>
      )}

      {tab === "text" && (
        <form onSubmit={handleSubmit}>
          <textarea
            value={chatText}
            onChange={(e) => setChatText(e.target.value)}
            placeholder="채팅 내용을 붙여넣으세요"
            rows={10}
          />
          <div>
            <label>
              <input
                type="checkbox"
                checked={legal}
                onChange={(e) => setLegal(e.target.checked)}
              />
              법률 정보 포함(조문/판례)
            </label>
          </div>
          <button type="submit" disabled={loading}>
            {loading ? "분석 중..." : "분석하기"}
          </button>
        </form>
      )}

      {error && <p role="alert">{error}</p>}

      {result && (
        <div>
          {result.expressions.length === 0 ? (
            <p>문제 표현이 발견되지 않았습니다.</p>
          ) : (
            result.expressions.map((expr, i) => (
              <div key={i}>
                <p>"{expr.text}"</p>
                <p>유형: {expr.type}</p>
                <p>위험도: {expr.risk}</p>
                {expr.target && <p>대상: {expr.target}</p>}
                {expr.context && <p>맥락: {expr.context}</p>}
                {expr.applicable_laws && (
                  <p>
                    적용 가능 법률:{" "}
                    {expr.applicable_laws.length > 0
                      ? expr.applicable_laws.join(", ")
                      : "판단 근거 없음"}
                  </p>
                )}
                {expr.related_cases && (
                  <p>
                    관련 판례:{" "}
                    {expr.related_cases.length > 0
                      ? expr.related_cases.join(" / ")
                      : "판단 근거 없음"}
                  </p>
                )}
              </div>
            ))
          )}
        </div>
      )}

      <hr />
      <p>{DISCLAIMER}</p>
    </div>
  );
}
