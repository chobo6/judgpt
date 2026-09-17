import { useState } from "react";
import { analyzeChat, ApiError } from "./api";

const DISCLAIMER =
  "이 결과는 참고용 정보이며 법적 판단이 아닙니다. 실제 법적 대응이 필요하면 변호사와 상담하세요.";

function errorMessage(err) {
  if (!(err instanceof ApiError)) return "알 수 없는 오류가 발생했습니다";
  if (err.status === 429) return "요청이 너무 많습니다. 잠시 후 다시 시도해주세요";
  if (err.status === 502 || err.status === 503) return "서비스가 일시적으로 응답하지 않습니다";
  if (err.status === 400) return "채팅 내용을 입력해주세요";
  return err.message;
}

export default function App() {
  const [chatText, setChatText] = useState("");
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

  return (
    <div>
      <h1>judgpt</h1>
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
