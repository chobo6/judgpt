import { useState } from "react";
import { analyzeChat, fetchReplay, ApiError } from "./api";

const DISCLAIMER =
  "이 결과는 참고용 정보이며 법적 판단이 아닙니다. 실제 법적 대응이 필요하면 변호사와 상담하세요.";

function errorMessage(err) {
  // 백엔드가 400/429/502/503마다 이미 사용자에게 보여줄 수 있는 한국어 문구를
  // detail로 내려준다(judgpt/web/app.py) — 프론트에서 상태 코드별로 다시 매핑하지
  // 않고 그대로 쓴다. 재매핑하면 400이 "빈 입력"과 "너무 긴 입력" 둘 다를 의미하게
  // 됐을 때처럼 실제 원인과 다른 문구가 뜰 수 있다.
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
    setResult(null);
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
    <div className="sheet">
      <header className="masthead">
        <h1>Judgpt</h1>
        <p>유해표현 판독기</p>
      </header>

      <div className="tabs" role="tablist" aria-label="입력 방식">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "text"}
          className="tab"
          onClick={() => setTab("text")}
          disabled={tab === "text" || importing}
        >
          텍스트 붙여넣기
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "link"}
          className="tab"
          onClick={() => setTab("link")}
          disabled={tab === "link" || importing}
        >
          리플레이 링크
        </button>
      </div>

      <div className="panel">
        {tab === "link" && (
          <form onSubmit={handleImport}>
            <label className="field-label" htmlFor="replay-url">
              마피아42 리플레이 링크
            </label>
            <div className="import-row">
              <input
                id="replay-url"
                className="link-input"
                type="url"
                value={replayUrl}
                onChange={(e) => setReplayUrl(e.target.value)}
                placeholder="https://mafia42.com/history/kr/..."
              />
              <button type="submit" className="btn-primary" disabled={importing}>
                {importing ? "가져오는 중..." : "가져오기"}
              </button>
            </div>
          </form>
        )}

        {tab === "text" && (
          <form onSubmit={handleSubmit}>
            <label className="field-label" htmlFor="chat-text">
              채팅 내용
            </label>
            <textarea
              id="chat-text"
              className="chat-input"
              value={chatText}
              onChange={(e) => setChatText(e.target.value)}
              placeholder="채팅 내용을 붙여넣으세요"
              rows={10}
            />
            <div className="form-footer">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={legal}
                  onChange={(e) => setLegal(e.target.checked)}
                />
                법률 정보 포함(조문/판례)
              </label>
              <button type="submit" className="btn-primary" disabled={loading}>
                {loading ? "분석 중..." : "분석하기"}
              </button>
            </div>
          </form>
        )}
      </div>

      {error && (
        <p className="notice-error" role="alert">
          {error}
        </p>
      )}

      {result && (
        <section className="results">
          <h2>판독 결과</h2>
          {result.expressions.length === 0 ? (
            <p className="empty-state">유해 표현이 발견되지 않았습니다.</p>
          ) : (
            result.expressions.map((expr, i) => (
              <article className="exhibit" key={i}>
                <p className="exhibit-index">{i + 1}</p>
                <div className="exhibit-body">
                  <p className="exhibit-quote">「{expr.text}」</p>
                  <div className="exhibit-meta">
                    <span className="exhibit-type">{expr.type}</span>
                    <span className="stamp" data-risk={expr.risk}>
                      {expr.risk}
                    </span>
                  </div>
                  <dl className="exhibit-detail">
                    {expr.target && (
                      <>
                        <dt>대상</dt>
                        <dd>{expr.target}</dd>
                      </>
                    )}
                    {expr.context && (
                      <>
                        <dt>맥락</dt>
                        <dd>{expr.context}</dd>
                      </>
                    )}
                    {expr.applicable_laws && (
                      <>
                        <dt>적용 가능 법률</dt>
                        <dd>
                          {expr.applicable_laws.length > 0
                            ? expr.applicable_laws.join(", ")
                            : "판단 근거 없음"}
                        </dd>
                      </>
                    )}
                    {expr.related_cases && (
                      <>
                        <dt>관련 판례</dt>
                        <dd>
                          {expr.related_cases.length > 0
                            ? expr.related_cases.join(" / ")
                            : "판단 근거 없음"}
                        </dd>
                      </>
                    )}
                  </dl>
                </div>
              </article>
            ))
          )}
        </section>
      )}

      <p className="disclaimer">{DISCLAIMER}</p>
    </div>
  );
}
