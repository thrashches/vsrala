import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { leadersApi } from '../api/endpoints'
import Avatar from './Avatar'

const METRICS = [
  { id: 'distance', label: 'Дистанция' },
  { id: 'duration', label: 'Время' },
]

const WEEKS = [
  { id: 'current', label: 'Эта' },
  { id: 'previous', label: 'Прошлая' },
]

export default function WeeklyLeaders() {
  const [metric, setMetric] = useState('distance')
  const [week, setWeek] = useState('current')
  const [rows, setRows] = useState([])
  const [weekLabel, setWeekLabel] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    leadersApi
      .weekly({ metric, week })
      .then((data) => {
        if (cancelled) return
        setRows(data.leaders || [])
        setWeekLabel(data.week_label || '')
      })
      .catch(() => {
        if (!cancelled) setRows([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [metric, week])

  return (
    <aside className="rounded bg-white p-4 shadow-card">
      <h2 className="text-sm font-bold text-ink">Лидеры недели</h2>
      {weekLabel && <p className="mt-1 text-xs text-ink-muted">{weekLabel}</p>}
      <div className="mt-3 flex flex-wrap gap-1">
        {METRICS.map((m) => (
          <button
            key={m.id}
            type="button"
            className={`rounded px-2 py-1 text-xs font-semibold ${
              metric === m.id ? 'bg-brand text-white' : 'bg-gray-100 text-ink hover:bg-gray-200'
            }`}
            onClick={() => setMetric(m.id)}
          >
            {m.label}
          </button>
        ))}
      </div>
      <div className="mt-2 flex gap-1">
        {WEEKS.map((w) => (
          <button
            key={w.id}
            type="button"
            className={`rounded px-2 py-1 text-xs font-semibold ${
              week === w.id ? 'bg-gray-800 text-white' : 'bg-gray-100 text-ink hover:bg-gray-200'
            }`}
            onClick={() => setWeek(w.id)}
          >
            {w.label}
          </button>
        ))}
      </div>
      <div className="mt-4 space-y-3">
        {loading && <p className="text-xs text-ink-muted">Загрузка…</p>}
        {!loading && !rows.length && (
          <p className="text-xs text-ink-muted">Пока нет данных</p>
        )}
        {rows.map((row) => {
          const person = {
            id: row.profile_id,
            display_name: row.display_name,
            photo_url: row.photo_url,
          }
          return (
            <div key={row.profile_id} className="flex items-center gap-2">
              <span className="w-4 text-xs font-bold text-ink-muted">{row.rank}</span>
              <Link to={`/people/${person.id}/`}>
                <Avatar person={person} className="h-8 w-8 text-xs" />
              </Link>
              <div className="min-w-0 flex-1">
                <Link
                  to={`/people/${person.id}/`}
                  className="block truncate text-sm font-semibold hover:text-brand"
                >
                  {person.display_name}
                </Link>
              </div>
              <span className="text-xs font-semibold text-ink">{row.total_display}</span>
            </div>
          )
        })}
      </div>
    </aside>
  )
}
