import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { leadersApi } from '../api/endpoints'
import Avatar from './Avatar'
import { LeaderRowSkeleton } from './skeletons'
import { activityTypeIcon } from '../lib/activityTypeIcons'

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
  const [sport, setSport] = useState('')
  const [sports, setSports] = useState([])
  const [rows, setRows] = useState([])
  const [trainingDays, setTrainingDays] = useState([])
  const [weekLabel, setWeekLabel] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    const params = { metric, week }
    if (sport) params.sport = sport
    leadersApi
      .weekly(params)
      .then((data) => {
        if (cancelled) return
        const available = data.available_sports || []
        setSports(available)
        setRows(data.leaders || [])
        setTrainingDays(data.my_training_days || [])
        setWeekLabel(data.week_label || '')
        if (sport && !available.some((s) => String(s.id) === String(sport))) {
          setSport('')
        }
      })
      .catch(() => {
        if (!cancelled) {
          setRows([])
          setSports([])
          setTrainingDays([])
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [metric, week, sport])

  return (
    <aside className="rounded bg-white p-4 shadow-card">
      <h2 className="text-sm font-bold text-ink">Лидеры недели</h2>
      {weekLabel && <p className="mt-1 text-xs text-ink-muted">{weekLabel}</p>}
      <div className="mt-3 flex gap-1">
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
      {trainingDays.length > 0 && (
        <div className="mt-3 flex justify-between gap-1" role="list" aria-label="Дни тренировок">
          {trainingDays.map((d) => {
            const titles = d.titles || []
            return (
            <div
              key={d.date}
              className="group relative flex min-w-0 flex-1 flex-col items-center gap-1"
              role="listitem"
            >
              <span
                className={`h-3.5 w-3.5 rounded-full ${
                  d.has_activity ? 'bg-brand' : 'border border-gray-300 bg-gray-100'
                }`}
                aria-label={`${d.day} ${d.weekday}${titles.length ? `: ${titles.join(', ')}` : ''}`}
              />
              <span className="text-center text-[10px] leading-tight text-ink-muted">
                <span className="block font-semibold text-ink">{d.day}</span>
                <span className="block">{d.weekday}</span>
              </span>
              <div
                className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-1.5 hidden w-max max-w-[14rem] -translate-x-1/2 rounded border border-gray-200 bg-white px-2 py-1.5 text-left shadow-card group-hover:block"
                role="tooltip"
              >
                {titles.length ? (
                  <ul className="space-y-1">
                    {titles.map((title, i) => (
                      <li key={`${d.date}-${i}`} className="flex items-center gap-1.5 text-[11px] leading-snug text-ink">
                        <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-brand" aria-hidden="true" />
                        <span className="min-w-0 break-words">{title}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[11px] text-ink-muted">Нет тренировки</p>
                )}
              </div>
            </div>
            )
          })}
        </div>
      )}
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
      {sports.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          <button
            type="button"
            className={`rounded px-2 py-1 text-xs font-semibold ${
              !sport ? 'bg-brand text-white' : 'bg-gray-100 text-ink hover:bg-gray-200'
            }`}
            onClick={() => setSport('')}
          >
            Все
          </button>
          {sports.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`inline-flex items-center gap-0.5 rounded px-2 py-1 text-xs font-semibold ${
                String(sport) === String(s.id)
                  ? 'bg-brand text-white'
                  : 'bg-gray-100 text-ink hover:bg-gray-200'
              }`}
              onClick={() => setSport(String(s.id))}
              title={s.name}
            >
              <span className="material-icons text-[14px] leading-none" aria-hidden="true">
                {activityTypeIcon(s.slug)}
              </span>
              <span className="max-w-[7rem] truncate">{s.name}</span>
            </button>
          ))}
        </div>
      )}
      <div className="mt-4 space-y-3">
        {loading && (
          <>
            <LeaderRowSkeleton />
            <LeaderRowSkeleton />
            <LeaderRowSkeleton />
            <LeaderRowSkeleton />
            <LeaderRowSkeleton />
          </>
        )}
        {!loading && !rows.length && (
          <p className="text-xs text-ink-muted">Пока нет данных</p>
        )}
        {!loading &&
          rows.map((row) => {
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
