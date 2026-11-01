import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { routesApi } from '../api/endpoints'

const TABS = [
  { id: 'mine', label: 'Мои' },
  { id: 'following', label: 'Подписки' },
  { id: 'public', label: 'Все' },
]

export default function RoutesListPage() {
  const [scope, setScope] = useState('mine')
  const [routes, setRoutes] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    routesApi
      .list({ tab: scope })
      .then((data) => setRoutes(data.results || data || []))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [scope])

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-xl font-bold text-ink">Маршруты</h1>
        <Link to="/routes/upload/" className="btn-brand">
          Загрузить
        </Link>
      </div>
      <div className="mt-4 flex gap-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`rounded px-3 py-1.5 text-sm font-semibold ${
              scope === t.id ? 'bg-brand text-white' : 'bg-white text-ink shadow-card hover:bg-gray-50'
            }`}
            onClick={() => setScope(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {error && (
        <div className="mt-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}
      {loading && <p className="mt-6 text-sm text-ink-muted">Загрузка…</p>}
      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        {routes.map((r) => (
          <Link
            key={r.id}
            to={`/routes/${r.id}/`}
            className="overflow-hidden rounded bg-white shadow-card transition hover:shadow-md"
          >
            {r.map_preview_url ? (
              <img src={r.map_preview_url} alt="" className="h-40 w-full object-cover" />
            ) : (
              <div className="flex h-40 items-center justify-center bg-feed text-ink-muted">Нет превью</div>
            )}
            <div className="p-4">
              <h2 className="font-bold text-ink">{r.title}</h2>
              <p className="mt-1 text-xs text-ink-muted">
                {r.distance != null ? `${r.distance} км` : '—'}
                {r.elevation_gain != null ? ` · ↑ ${r.elevation_gain} м` : ''}
              </p>
            </div>
          </Link>
        ))}
      </div>
      {!loading && !routes.length && (
        <p className="mt-6 text-sm text-ink-muted">Маршрутов пока нет</p>
      )}
    </div>
  )
}
