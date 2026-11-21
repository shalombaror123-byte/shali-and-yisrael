import { useCallback, useEffect, useState } from 'react'
import { api } from './api'

const REFRESH_MS = 60000

function ago(ts) {
  if (!ts) return ''
  const s = Math.max(0, Date.now() / 1000 - ts)
  if (s < 60) return `${Math.floor(s)}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

function NewsItem({ n }) {
  return (
    <li className="news-item">
      <div className="news-meta">
        <span className="source-badge">{n.source}</span>
        <span className="muted">{ago(n.published)}</span>
      </div>
      <a href={n.link} target="_blank" rel="noreferrer" className="news-title">
        {n.title}
      </a>
      {n.summary && <p className="news-summary">{n.summary}</p>}
    </li>
  )
}

function WhyPanel() {
  const [symbol, setSymbol] = useState('')
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    const s = symbol.trim().toUpperCase()
    if (!s) return
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      setResult(await api.why(s))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const pctClass =
    result?.change_pct > 0 ? 'up' : result?.change_pct < 0 ? 'down' : ''

  return (
    <section className="card why-panel">
      <h2>Why is a stock moving?</h2>
      <form className="why-form" onSubmit={submit}>
        <input
          placeholder="Symbol (e.g. NVDA)"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          required
        />
        <button type="submit" disabled={busy}>
          {busy ? 'Checking…' : 'Explain move'}
        </button>
      </form>

      {error && <div className="form-error">{error}</div>}

      {result && (
        <div className="why-result">
          <div className="why-header">
            <span className="symbol">{result.symbol}</span>
            <span className="muted">{result.name}</span>
            {result.price !== null && result.price !== undefined && (
              <span className={`why-change ${pctClass}`}>
                {result.change_pct > 0 ? '+' : ''}
                {result.change_pct?.toFixed(2)}%
              </span>
            )}
          </div>
          <p className="why-answer">{result.answer}</p>

          {result.drivers.length > 0 && (
            <div className="why-drivers">
              {result.drivers.map((d) => (
                <a
                  key={d.category}
                  href={d.link}
                  target="_blank"
                  rel="noreferrer"
                  className="driver-chip"
                  title={d.title}
                >
                  {d.category}
                </a>
              ))}
            </div>
          )}

          {result.news.length > 0 && (
            <>
              <div className="label">Recent {result.symbol} headlines</div>
              <ul className="news-list compact">
                {result.news.slice(0, 8).map((n) => (
                  <NewsItem key={n.link} n={n} />
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </section>
  )
}

export default function NewsTab() {
  const [news, setNews] = useState(null)
  const [error, setError] = useState(null)
  const [secondsAgo, setSecondsAgo] = useState(0)

  const refresh = useCallback(async () => {
    try {
      const d = await api.getMarketNews()
      setNews(d.news || [])
      setError(null)
      setSecondsAgo(0)
    } catch (err) {
      setError(err.message)
    }
  }, [])

  useEffect(() => {
    refresh()
    const timer = setInterval(refresh, REFRESH_MS)
    const tick = setInterval(() => setSecondsAgo((s) => s + 1), 1000)
    return () => {
      clearInterval(timer)
      clearInterval(tick)
    }
  }, [refresh])

  return (
    <>
      <WhyPanel />

      <div className="news-feed-header">
        <h2>Latest US market news</h2>
        <div className="refresh">
          <button onClick={refresh}>Refresh</button>
          <span className="muted">
            {error
              ? 'backend unreachable'
              : `updated ${secondsAgo}s ago · CNBC · Yahoo Finance · MarketWatch · Seeking Alpha`}
          </span>
        </div>
      </div>

      {error && <div className="banner error">{error}</div>}

      <ul className="news-list">
        {news?.map((n) => (
          <NewsItem key={n.link} n={n} />
        ))}
      </ul>
      {news && news.length === 0 && (
        <p className="muted empty">No headlines available right now.</p>
      )}
      {!news && !error && <p className="muted">Loading…</p>}
    </>
  )
}
