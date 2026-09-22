import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import type { FeedEvent, MeterReading, Pond, Reconciliation } from '../types'

function todayLocal() {
  const d = new Date()
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
  return d.toISOString().slice(0, 10)
}

const emptyForm = {
  readingDate: todayLocal(),
  startKwh: 0,
  endKwh: 10,
  unitPrice: 0.6,
}

export default function MeterReadings() {
  const [searchParams, setSearchParams] = useSearchParams()
  const pondIdFromUrl = Number(searchParams.get('pondId')) || 0

  const [ponds, setPonds] = useState<Pond[]>([])
  const [readings, setReadings] = useState<MeterReading[]>([])
  const [feeds, setFeeds] = useState<FeedEvent[]>([])
  const [form, setForm] = useState(emptyForm)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [attachFeedId, setAttachFeedId] = useState(0)
  const [recon, setRecon] = useState<Reconciliation | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const pondId = pondIdFromUrl

  async function loadPonds() {
    const ps = await api<Pond[]>('/api/ponds')
    setPonds(ps)
    if (!pondIdFromUrl && ps[0]) {
      setSearchParams({ pondId: String(ps[0].id) }, { replace: true })
    }
  }

  async function loadPondData(id: number) {
    const [rs, fs] = await Promise.all([
      api<MeterReading[]>(`/api/meter-readings?pondId=${id}`),
      api<FeedEvent[]>(`/api/feed-events?pondId=${id}`),
    ])
    setReadings(rs)
    setFeeds(fs)
    if (selectedId && !rs.some((r) => r.id === selectedId)) {
      setSelectedId(null)
      setRecon(null)
    }
  }

  useEffect(() => {
    loadPonds().catch((e) => setError(e.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!pondId) return
    setError('')
    loadPondData(pondId).catch((e) => setError(e.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pondId])

  // feedEventId -> meterReadingId（一笔投喂最多挂一张抄见）
  const feedOwner = useMemo(() => {
    const m = new Map<number, number>()
    for (const r of readings) {
      for (const a of r.allocations) m.set(a.feedEventId, r.id)
    }
    return m
  }, [readings])

  const selected = readings.find((r) => r.id === selectedId) || null

  async function loadRecon(id: number) {
    const rc = await api<Reconciliation>(
      `/api/meter-readings/${id}/reconciliation`,
    )
    setRecon(rc)
  }

  useEffect(() => {
    if (!selectedId) {
      setRecon(null)
      return
    }
    loadRecon(selectedId).catch((e) => setError(e.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!pondId) return
    setError('')
    setBusy(true)
    try {
      await api('/api/meter-readings', {
        method: 'POST',
        body: JSON.stringify({
          pondId,
          readingDate: form.readingDate,
          startKwh: Number(form.startKwh),
          endKwh: Number(form.endKwh),
          unitPrice: Number(form.unitPrice),
        }),
      })
      setForm({ ...emptyForm, readingDate: form.readingDate })
      await loadPondData(pondId)
    } catch (err) {
      setError(err instanceof Error ? err.message : '登记失败')
    } finally {
      setBusy(false)
    }
  }

  async function removeReading(r: MeterReading) {
    if (!confirm(`确认删除 ${r.readingDate} 的抄见？`)) return
    setError('')
    try {
      await api(`/api/meter-readings/${r.id}`, { method: 'DELETE' })
      if (selectedId === r.id) setSelectedId(null)
      await loadPondData(pondId)
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败')
    }
  }

  async function attach() {
    if (!selectedId || !attachFeedId) return
    setError('')
    try {
      await api(`/api/meter-readings/${selectedId}/allocations`, {
        method: 'POST',
        body: JSON.stringify({ feedEventId: attachFeedId }),
      })
      setAttachFeedId(0)
      await loadPondData(pondId)
      await loadRecon(selectedId)
    } catch (err) {
      setError(err instanceof Error ? err.message : '挂账失败')
    }
  }

  async function detach(allocationId: number) {
    if (!selectedId) return
    setError('')
    try {
      await api(
        `/api/meter-readings/${selectedId}/allocations/${allocationId}`,
        { method: 'DELETE' },
      )
      await loadPondData(pondId)
      await loadRecon(selectedId)
    } catch (err) {
      setError(err instanceof Error ? err.message : '取消挂账失败')
    }
  }

  async function seal(r: MeterReading) {
    setError('')
    try {
      await api(`/api/meter-readings/${r.id}/seal`, { method: 'POST' })
      await loadPondData(pondId)
      await loadRecon(r.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : '封抄失败')
    }
  }

  const pondLabel = (id: number) => {
    const p = ponds.find((x) => x.id === id)
    return p ? `${p.pondCode} (${p.species})` : `#${id}`
  }

  const feedRow = (id: number) => feeds.find((f) => f.id === id)

  // 当前塘可挂的投喂：尚未挂到任何抄见
  const attachableFeeds = selected
    ? feeds.filter((f) => !feedOwner.has(f.id))
    : []

  return (
    <div>
      <header className="page-header">
        <h1>电表抄表 · 电费分摊对账</h1>
        <p className="muted">
          按塘口登记抄见，电量 = 止度 − 起度，电费 = 电量 × 单价；把电费挂到同塘投喂上对账
        </p>
      </header>
      {error && <div className="error">{error}</div>}

      <form className="panel form-grid" onSubmit={onSubmit}>
        <label>
          所属塘口
          <select
            value={pondId}
            onChange={(e) =>
              setSearchParams({ pondId: String(Number(e.target.value)) })
            }
            required
          >
            {ponds.map((p) => (
              <option key={p.id} value={p.id}>
                {p.pondCode} · {p.species}
              </option>
            ))}
          </select>
        </label>
        <label>
          抄见日
          <input
            type="date"
            value={form.readingDate}
            onChange={(e) => setForm({ ...form, readingDate: e.target.value })}
            required
          />
        </label>
        <label>
          起度 (kWh)
          <input
            type="number"
            step="0.01"
            value={form.startKwh}
            onChange={(e) => setForm({ ...form, startKwh: Number(e.target.value) })}
            required
          />
        </label>
        <label>
          止度 (kWh，须大于起度)
          <input
            type="number"
            step="0.01"
            value={form.endKwh}
            onChange={(e) => setForm({ ...form, endKwh: Number(e.target.value) })}
            required
          />
        </label>
        <label>
          单价 (元/kWh)
          <input
            type="number"
            step="0.01"
            min="0.01"
            value={form.unitPrice}
            onChange={(e) => setForm({ ...form, unitPrice: Number(e.target.value) })}
            required
          />
        </label>
        <button type="submit" className="btn primary" disabled={busy || !pondId}>
          登记抄见
        </button>
      </form>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>抄见编号</th>
              <th>塘口</th>
              <th>抄见日</th>
              <th>起度</th>
              <th>止度</th>
              <th>电量 kWh</th>
              <th>单价</th>
              <th>电费 元</th>
              <th>已挂投喂</th>
              <th>状态</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {readings.map((r) => (
              <tr
                key={r.id}
                style={{
                  cursor: 'pointer',
                  background: selectedId === r.id ? 'var(--sea-mist)' : undefined,
                }}
                onClick={() => setSelectedId(r.id)}
              >
                <td>{r.id}</td>
                <td>{pondLabel(r.pondId)}</td>
                <td>{r.readingDate}</td>
                <td>{r.startKwh}</td>
                <td>{r.endKwh}</td>
                <td>{r.electricityKwh.toFixed(2)}</td>
                <td>{r.unitPrice}</td>
                <td>{r.electricityFee.toFixed(2)}</td>
                <td>{r.allocationCount} 笔</td>
                <td>
                  <span className={`badge ${r.sealed ? 'dry' : 'stocked'}`}>
                    {r.sealed ? '已封账' : '未封'}
                  </span>
                </td>
                <td onClick={(e) => e.stopPropagation()}>
                  <button className="btn ghost" onClick={() => removeReading(r)}>
                    删除
                  </button>
                </td>
              </tr>
            ))}
            {readings.length === 0 && (
              <tr>
                <td colSpan={11} className="muted" style={{ textAlign: 'center' }}>
                  该塘口暂无抄见
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {selected && (
        <div className="panel" style={{ marginTop: 20 }}>
          <h2 style={{ marginTop: 0, color: 'var(--sea-deep)' }}>
            抄见 #{selected.id} 分摊对账
          </h2>

          <div className="stat-grid" style={{ marginTop: 0 }}>
            <div className="stat-card">
              <div className="stat-label">电量 (止度−起度)</div>
              <div className="stat-value">{recon?.electricityKwh.toFixed(2)} kWh</div>
            </div>
            <div className="stat-card accent">
              <div className="stat-label">该塘电费 (电量×单价)</div>
              <div className="stat-value">{recon?.electricityFee.toFixed(2)} 元</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">所挂投喂合计</div>
              <div className="stat-value">{recon?.allocatedFeedKg.toFixed(2)} kg</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">已挂投喂 / 封账</div>
              <div className="stat-value">
                {recon?.allocationCount} 笔 · {recon?.sealed ? '已封' : '未封'}
              </div>
            </div>
          </div>

          {!selected.sealed && (
            <div style={{ display: 'flex', gap: 10, margin: '16px 0' }}>
              <select
                value={attachFeedId}
                onChange={(e) => setAttachFeedId(Number(e.target.value))}
                style={{ flex: 1 }}
              >
                <option value={0}>选择本塘投喂行挂账…</option>
                {attachableFeeds.map((f) => (
                  <option key={f.id} value={f.id}>
                    #{f.id} · {new Date(f.fedAt).toLocaleDateString()} · {f.feedType} · {f.amountKg}kg
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="btn primary"
                onClick={attach}
                disabled={!attachFeedId}
              >
                挂到本抄见
              </button>
              <button
                type="button"
                className="btn ghost"
                onClick={() => seal(selected)}
              >
                封抄（需 ≥2 笔）
              </button>
            </div>
          )}
          {selected.sealed && (
            <p className="hint">该抄见已封账，分摊不可更改。</p>
          )}

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>投喂编号</th>
                  <th>投喂时间</th>
                  <th>饵料</th>
                  <th>数量 kg</th>
                  <th>操作人</th>
                  {!selected.sealed && <th />}
                </tr>
              </thead>
              <tbody>
                {selected.allocations.map((a) => {
                  const f = feedRow(a.feedEventId)
                  return (
                    <tr key={a.id}>
                      <td>{a.feedEventId}</td>
                      <td>{f ? new Date(f.fedAt).toLocaleString() : '—'}</td>
                      <td>{f?.feedType ?? '—'}</td>
                      <td>{f?.amountKg ?? '—'}</td>
                      <td>{f?.operatorName ?? '—'}</td>
                      {!selected.sealed && (
                        <td>
                          <button
                            className="btn ghost"
                            onClick={() => detach(a.id)}
                          >
                            取消挂账
                          </button>
                        </td>
                      )}
                    </tr>
                  )
                })}
                {selected.allocations.length === 0 && (
                  <tr>
                    <td
                      colSpan={selected.sealed ? 5 : 6}
                      className="muted"
                      style={{ textAlign: 'center' }}
                    >
                      尚未挂任何投喂
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
