import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import type {
  FeedEvent,
  MeterReading,
  Pond,
  ReadingReconciliation,
} from '../types'

function today() {
  const d = new Date()
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
  return d.toISOString().slice(0, 10)
}

const empty = {
  readDate: today(),
  startKwh: 0,
  endKwh: 10,
  unitPrice: 0.8,
}

export default function MeterReadings() {
  const [searchParams, setSearchParams] = useSearchParams()
  const pondIdParam = Number(searchParams.get('pondId')) || 0

  const [ponds, setPonds] = useState<Pond[]>([])
  const [pondId, setPondId] = useState(pondIdParam)
  const [readings, setReadings] = useState<MeterReading[]>([])
  const [events, setEvents] = useState<FeedEvent[]>([])
  const [recon, setRecon] = useState<ReadingReconciliation[]>([])
  const [form, setForm] = useState(empty)
  const [error, setError] = useState('')

  async function load(id: number) {
    const [rs, es, rc] = await Promise.all([
      api<MeterReading[]>(`/api/meter-readings?pondId=${id}`),
      api<FeedEvent[]>(`/api/feed-events?pondId=${id}`),
      api<ReadingReconciliation[]>(
        `/api/meter-readings/reconciliation?pondId=${id}`,
      ),
    ])
    setReadings(rs)
    setEvents(es)
    setRecon(rc)
  }

  useEffect(() => {
    api<Pond[]>('/api/ponds')
      .then((ps) => {
        setPonds(ps)
        const target = pondId || ps[0]?.id || 0
        if (target && target !== pondId) {
          setPondId(target)
          setSearchParams({ pondId: String(target) }, { replace: true })
        }
        if (target) return load(target)
      })
      .catch((e) => setError(e.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (pondId) {
      load(pondId).catch((e) => setError(e.message))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pondId])

  function pickPond(id: number) {
    setPondId(id)
    setSearchParams({ pondId: String(id) })
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    if (Number(form.endKwh) <= Number(form.startKwh)) {
      setError('止度必须大于起度')
      return
    }
    try {
      await api('/api/meter-readings', {
        method: 'POST',
        body: JSON.stringify({ ...form, pondId }),
      })
      setForm({ ...empty, readDate: today() })
      await load(pondId)
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败')
    }
  }

  async function attach(readingId: number, feedEventId: number) {
    setError('')
    try {
      await api('/api/meter-readings/allocations', {
        method: 'POST',
        body: JSON.stringify({ readingId, feedEventId }),
      })
      await load(pondId)
    } catch (err) {
      setError(err instanceof Error ? err.message : '挂载失败')
    }
  }

  async function detach(readingId: number, feedEventId: number) {
    setError('')
    try {
      await api(
        `/api/meter-readings/${readingId}/allocations/${feedEventId}`,
        { method: 'DELETE' },
      )
      await load(pondId)
    } catch (err) {
      setError(err instanceof Error ? err.message : '摘除失败')
    }
  }

  async function seal(readingId: number) {
    setError('')
    try {
      await api(`/api/meter-readings/${readingId}/seal`, { method: 'POST' })
      await load(pondId)
    } catch (err) {
      setError(err instanceof Error ? err.message : '封抄失败')
    }
  }

  async function remove(readingId: number) {
    if (!confirm('确认删除该抄见？')) return
    setError('')
    try {
      await api(`/api/meter-readings/${readingId}`, { method: 'DELETE' })
      await load(pondId)
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败')
    }
  }

  // 已挂在任意抄见上的投喂不能再选
  const takenEventIds = useMemo(
    () => new Set(readings.flatMap((r) => r.feedEventIds)),
    [readings],
  )
  const eventById = useMemo(
    () => new Map(events.map((e) => [e.id, e])),
    [events],
  )

  const pondLabel = (id: number) => {
    const p = ponds.find((x) => x.id === id)
    return p ? `${p.pondCode} · ${p.species}` : `#${id}`
  }

  return (
    <div>
      <header className="page-header">
        <h1>电表抄见</h1>
        <p className="muted">
          按塘口登记抄见并把电费分摊到投喂行；电量 = 止度 − 起度，电费 = 电量 ×
          单价
        </p>
      </header>
      {error && <div className="error">{error}</div>}

      <form className="panel form-grid" onSubmit={onSubmit}>
        <label>
          所属塘口
          <select
            value={pondId}
            onChange={(e) => pickPond(Number(e.target.value))}
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
            value={form.readDate}
            onChange={(e) => setForm({ ...form, readDate: e.target.value })}
            required
          />
        </label>
        <label>
          起度 (kWh)
          <input
            type="number"
            step="0.01"
            min="0"
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
            min="0"
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
        <button type="submit" className="btn primary">
          登记抄见
        </button>
      </form>

      {readings.length === 0 ? (
        <div className="panel muted">该塘暂无抄见</div>
      ) : (
        <div className="reading-list">
          {readings.map((r) => {
            const rc = recon.find((x) => x.readingId === r.id)
            return (
              <div key={r.id} className="panel reading-card">
                <div className="reading-head">
                  <div>
                    <strong>
                      #{r.id} · {r.readDate}
                    </strong>{' '}
                    <span className={`badge ${r.sealed ? 'quarantine' : 'stocked'}`}>
                      {r.sealed ? '已封' : '未封'}
                    </span>
                  </div>
                  <div className="muted">{pondLabel(r.pondId)}</div>
                </div>
                <div className="reading-metrics">
                  <span>
                    起度 <strong>{r.startKwh}</strong>
                  </span>
                  <span>
                    止度 <strong>{r.endKwh}</strong>
                  </span>
                  <span>
                    电量 <strong>{r.kwhUsed} kWh</strong>
                  </span>
                  <span>
                    单价 <strong>{r.unitPrice}</strong>
                  </span>
                  <span>
                    电费 <strong>{r.fee} 元</strong>
                  </span>
                  {rc && (
                    <span>
                      所挂投喂 <strong>{rc.allocatedCount}</strong> 笔 · 合计{' '}
                      <strong>{rc.allocatedFeedKg} kg</strong>
                    </span>
                  )}
                </div>

                <ul className="alloc-list">
                  {r.feedEventIds.map((fid) => {
                    const ev = eventById.get(fid)
                    return (
                      <li key={fid}>
                        投喂 #{fid}
                        {ev
                          ? ` · ${ev.feedType} ${ev.amountKg}kg · ${new Date(
                              ev.fedAt,
                            ).toLocaleDateString()}`
                          : ''}
                        {!r.sealed && (
                          <button
                            className="btn ghost small"
                            onClick={() => detach(r.id, fid)}
                          >
                            摘除
                          </button>
                        )}
                      </li>
                    )
                  })}
                  {r.feedEventIds.length === 0 && (
                    <li className="muted">尚未挂投喂（至少两笔才能封抄）</li>
                  )}
                </ul>

                {!r.sealed && (
                  <div className="reading-actions">
                    <select
                      value=""
                      onChange={(e) => {
                        const fid = Number(e.target.value)
                        if (fid) attach(r.id, fid)
                        e.currentTarget.value = ''
                      }}
                    >
                      <option value="">选择同塘投喂挂载…</option>
                      {events
                        .filter((ev) => !takenEventIds.has(ev.id))
                        .map((ev) => (
                          <option key={ev.id} value={ev.id}>
                            #{ev.id} · {ev.feedType} {ev.amountKg}kg
                          </option>
                        ))}
                    </select>
                    <button className="btn primary" onClick={() => seal(r.id)}>
                      封抄
                    </button>
                    <button className="btn ghost" onClick={() => remove(r.id)}>
                      删除
                    </button>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
