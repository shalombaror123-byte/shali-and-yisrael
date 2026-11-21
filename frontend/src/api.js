const API_BASE = 'http://localhost:8000/api'

async function request(path, options) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (body.detail) detail = body.detail
    } catch {
      // keep default message
    }
    throw new Error(detail)
  }
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  getPortfolio: () => request('/portfolio'),
  addPosition: (position) =>
    request('/portfolio', { method: 'POST', body: JSON.stringify(position) }),
  updatePosition: (symbol, position) =>
    request(`/portfolio/${symbol}`, { method: 'PUT', body: JSON.stringify(position) }),
  deletePosition: (symbol) => request(`/portfolio/${symbol}`, { method: 'DELETE' }),
  getMarketNews: () => request('/news'),
  why: (symbol) => request(`/why/${symbol}`),
}
