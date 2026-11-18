import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import './App.css'

const REFRESH_MS = 15000

function fmtMoney(v, currency = 'USD') {
  if (v === null || v === undefined) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
  }).format(v)
}

function fmtPct(v) {
  if (v === null || v === undefined) return '—'
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`
}

function plClass(v) {
  if (v === null || v === undefined) return ''
  return v > 0 ? 'up' : v < 0 ? 'down' : ''
}

function PositionRow({ p, onDelete, onSave }) {
  const [editing, setEditing] = useState(false)
  const [shares, setShares] = useState(p.shares)
  const [avgCost, setAvgCost] = useState(p.avg_cost)
  const [busy, setBusy] = useState(false)

  const save = async () => {
    setBusy(true)
    try {
      await onSave(p.symbol, Number(shares), Number(avgCost))
      setEditing(false)
    } catch {
      // parent surfaces errors
    } finally {
      setBusy(false)
    }
  }

  return (
    <tr>
      <td>
        <div className="symbol">{p.symbol}</div>
        <div className="name">{p.name || ''}</div>
      </td>
      <td className="num">
        {editing ? (
          <input
            type="number"
            min="0"
            step="any"
            value={shares}
            onChange={(e) => setShares(e.target.value)}
          />
        ) : (
          p.shares
        )}
      </td>
      <td className="num">
        {editing ? (
          <input
            type="number"
            min="0"
            step="any"
            value={avgCost}
            onChange={(e) => setAvgCost(e.target.value)}
          />
        ) : (
          fmtMoney(p.avg_cost, p.currency)
        )}
      </td>
      <td className="num">
        <div>{fmtMoney(p.price, p.currency)}</div>
        <div className={`sub ${plClass(p.day_change_pct)}`}>
          {fmtPct(p.day_change_pct)} today
        </div>
      </td>
      <td className="num">{fmtMoney(p.market_value, p.currency)}</td>
      <td className={`num ${plClass(p.unrealized_pl)}`}>
        <div>{fmtMoney(p.unrealized_pl, p.currency)}</div>
        <div className="sub">{fmtPct(p.unrealized_pl_pct)}</div>
      </td>
      <td className="actions">
        {editing ? (
          <>
            <button disabled={busy} onClick={save}>
              Save
            </button>
            <button disabled={busy} onClick={() => setEditing(false)}>
              Cancel
            </button>
          </>
        ) : (
          <>
            <button onClick={() => setEditing(true)}>Edit</button>
            <button className="danger" onClick={() => onDelete(p.symbol)}>
              Delete
            </button>
          </>
        )}
      </td>
    </tr>
  )
}

function AddPositionForm({ onAdd }) {
  const [symbol, setSymbol] = useState('')
  const [shares, setShares] = useState('')
  const [avgCost, setAvgCost] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await onAdd({ symbol: symbol.trim(), shares: Number(shares), avg_cost: Number(avgCost) })
      setSymbol('')
      setShares('')
      setAvgCost('')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="add-form" onSubmit={submit}>
      <input
        placeholder="Symbol (e.g. AAPL)"
        value={symbol}
        onChange={(e) => setSymbol(e.target.value)}
        required
      />
      <input
        placeholder="Shares"
        type="number"
        min="0"
        step="any"
        value={shares}
        onChange={(e) => setShares(e.target.value)}
        required
      />
      <input
        placeholder="Avg cost / share"
        type="number"
        min="0"
        step="any"
        value={avgCost}
        onChange={(e) => setAvgCost(e.target.value)}
        required
      />
      <button type="submit" disabled={busy}>
        {busy ? 'Adding…' : 'Add position'}
      </button>
      {error && <div className="form-error">{error}</div>}
    </form>
  )
}

export default function App() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [secondsAgo, setSecondsAgo] = useState(0)
  const timerRef = useRef(null)

  const refresh = useCallback(async () => {
    try {
      const d = await api.getPortfolio()
      setData(d)
      setError(null)
      setSecondsAgo(0)
    } catch (err) {
      setError(err.message)
    }
  }, [])

  useEffect(() => {
    refresh()
    timerRef.current = setInterval(refresh, REFRESH_MS)
    const tick = setInterval(() => setSecondsAgo((s) => s + 1), 1000)
    return () => {
      clearInterval(timerRef.current)
      clearInterval(tick)
    }
  }, [refresh])

  const add = async (pos) => {
    await api.addPosition(pos)
    await refresh()
  }
  const update = async (symbol, shares, avg_cost) => {
    await api.updatePosition(symbol, { symbol, shares, avg_cost })
    await refresh()
  }
  const remove = async (symbol) => {
    await api.deletePosition(symbol)
    await refresh()
  }

  const s = data?.summary

  return (
    <div className="page">
      <header>
        <h1>My Portfolio</h1>
        <div className="refresh">
          <button onClick={refresh}>Refresh</button>
          <span className="muted">
            {error ? 'backend unreachable' : `updated ${secondsAgo}s ago · live from Yahoo Finance`}
          </span>
        </div>
      </header>

      {error && <div className="banner error">{error}</div>}

      <section className="cards">
        <div className="card">
          <div className="label">Market Value</div>
          <div className="value">{fmtMoney(s?.market_value)}</div>
        </div>
        <div className="card">
          <div className="label">Cost Basis</div>
          <div className="value">{fmtMoney(s?.cost_basis)}</div>
        </div>
        <div className="card">
          <div className="label">Unrealized P/L</div>
          <div className={`value ${plClass(s?.unrealized_pl)}`}>
            {fmtMoney(s?.unrealized_pl)}{' '}
            <span className="sub">({fmtPct(s?.unrealized_pl_pct)})</span>
          </div>
        </div>
      </section>

      <AddPositionForm onAdd={add} />

      <table className="positions">
        <thead>
          <tr>
            <th>Symbol</th>
            <th className="num">Shares</th>
            <th className="num">Avg Cost</th>
            <th className="num">Price</th>
            <th className="num">Value</th>
            <th className="num">P/L</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {data?.positions?.map((p) => (
            <PositionRow key={p.symbol} p={p} onDelete={remove} onSave={update} />
          ))}
        </tbody>
      </table>

      {data && data.positions.length === 0 && (
        <p className="muted empty">No positions yet — add one above.</p>
      )}
      {!data && !error && <p className="muted">Loading…</p>}
    </div>
  )
}
