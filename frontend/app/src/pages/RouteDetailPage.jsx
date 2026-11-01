import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { routesApi } from '../api/endpoints'
import Avatar from '../components/Avatar'
import TrackMap, { SURFACE_COLORS } from '../components/TrackMap'
import { formatDate } from '../lib/format'

const VISIBILITY_LABELS = {
  private: 'Только я',
  followers: 'Подписчики',
  public: 'Все',
}

function SurfaceCoverage({ status, summary }) {
  if (status === 'ready' && summary?.length) {
    return (
      <div className="space-y-2">
        {summary.map((row) => (
          <div key={row.surface || row.label}>
            <div className="mb-0.5 flex justify-between text-xs">
              <span className="inline-flex items-center gap-2 font-medium text-ink">
                <span
                  className="inline-block h-2.5 w-2.5 rounded-full"
                  style={{ background: row.color || SURFACE_COLORS.unknown }}
                />
                {row.label}
              </span>
              <span className="text-ink-muted">
                {row.pct}% · {row.distance_m} м
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded bg-gray-100">
              <div
                className="h-full rounded"
                style={{
                  width: `${row.pct}%`,
                  backgroundColor: row.color || SURFACE_COLORS.unknown,
                }}
              />
            </div>
          </div>
        ))}
      </div>
    )
  }
  if (status === 'pending') {
    return <p className="text-sm text-ink-muted">Определяем тип покрытия…</p>
  }
  if (status === 'failed') {
    return <p className="text-sm text-ink-muted">Покрытие недоступно</p>
  }
  return <p className="text-sm text-ink-muted">Нет данных о покрытии</p>
}

export default function RouteDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [route, setRoute] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    routesApi
      .get(id)
      .then(setRoute)
      .catch((err) => setError(err.message))
  }, [id])

  async function handleDelete() {
    if (!window.confirm('Удалить маршрут?')) return
    await routesApi.remove(id)
    navigate('/routes/')
  }

  async function downloadGpx() {
    const res = await routesApi.gpx(id)
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${route?.title || 'route'}.gpx`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (error && !route) {
    return <div className="p-6 text-sm text-red-700">{error}</div>
  }
  if (!route) return <p className="p-6 text-sm text-ink-muted">Загрузка…</p>

  const visibilityLabel =
    route.visibility_label || VISIBILITY_LABELS[route.visibility] || route.visibility

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <div className="overflow-hidden rounded bg-white shadow-card">
        <div className="border-b border-gray-100 px-5 py-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex items-start gap-3">
              <Link to={`/people/${route.profile.id}/`}>
                <Avatar person={route.profile} className="h-12 w-12 text-base" />
              </Link>
              <div>
                <div className="text-sm font-semibold">
                  <Link to={`/people/${route.profile.id}/`} className="hover:text-brand">
                    {route.profile.display_name}
                  </Link>
                </div>
                <div className="text-xs text-ink-muted">
                  {formatDate(route.created_at)} · {visibilityLabel}
                </div>
                <h1 className="mt-2 text-2xl font-bold text-ink">{route.title || 'Маршрут'}</h1>
                {route.description && (
                  <p className="mt-2 text-sm text-ink-muted">{route.description}</p>
                )}
              </div>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                className="rounded border border-gray-200 px-3 py-1.5 text-sm font-semibold hover:bg-gray-50"
                onClick={downloadGpx}
              >
                Скачать GPX
              </button>
              {route.is_owner && (
                <>
                  <Link
                    to={`/routes/${id}/edit/`}
                    className="rounded border border-gray-200 px-3 py-1.5 text-sm font-semibold hover:bg-gray-50"
                  >
                    Изменить
                  </Link>
                  <button
                    type="button"
                    className="rounded border border-red-200 px-3 py-1.5 text-sm font-semibold text-red-600 hover:bg-red-50"
                    onClick={handleDelete}
                  >
                    Удалить
                  </button>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 border-b border-gray-100 px-5 py-4 sm:grid-cols-3">
          <div>
            <div className="stat-label">Дистанция</div>
            <div className="stat-value">
              {route.distance != null ? route.distance : '—'}
              {route.distance != null ? <span className="stat-unit">км</span> : null}
            </div>
          </div>
          {route.elevation_gain != null && (
            <div>
              <div className="stat-label">Набор высоты</div>
              <div className="stat-value">
                {route.elevation_gain}
                <span className="stat-unit">м</span>
              </div>
            </div>
          )}
          {route.elevation_loss != null && (
            <div>
              <div className="stat-label">Спуск</div>
              <div className="stat-value">
                {route.elevation_loss}
                <span className="stat-unit">м</span>
              </div>
            </div>
          )}
        </div>

        {route.track_points?.length > 0 && (
          <div className="relative z-0 overflow-hidden">
            <TrackMap
              points={route.track_points}
              segments={route.surface_segments}
              surfaceColors={SURFACE_COLORS}
              className="h-[420px] w-full bg-gray-100"
            />
          </div>
        )}

        <div className="border-t border-gray-100 px-5 py-4">
          <h3 className="mb-2 text-sm font-semibold text-ink">Покрытие</h3>
          <SurfaceCoverage status={route.surface_status} summary={route.surface_summary} />
        </div>

        {route.source_activity_id && (
          <div className="border-t border-gray-100 px-5 py-3 text-sm text-ink-muted">
            Создан из{' '}
            <Link
              to={`/activities/${route.source_activity_id}/`}
              className="font-semibold text-brand hover:underline"
            >
              тренировки
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}
