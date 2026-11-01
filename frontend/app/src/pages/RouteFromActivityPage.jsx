import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { activitiesApi, routesApi } from '../api/endpoints'
import TrackMap from '../components/TrackMap'

export default function RouteFromActivityPage() {
  const { activityId } = useParams()
  const navigate = useNavigate()
  const [activity, setActivity] = useState(null)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [visibility, setVisibility] = useState('private')
  const [startIdx, setStartIdx] = useState(0)
  const [endIdx, setEndIdx] = useState(0)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    activitiesApi
      .get(activityId)
      .then((a) => {
        setActivity(a)
        setTitle(a.title ? `Маршрут: ${a.title}` : '')
        const n = a.track_points?.length || 0
        setEndIdx(Math.max(0, n - 1))
      })
      .catch((err) => setError(err.message))
  }, [activityId])

  const highlight = useMemo(() => [startIdx, endIdx], [startIdx, endIdx])
  const maxIdx = Math.max(0, (activity?.track_points?.length || 1) - 1)

  async function onSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const route = await routesApi.fromActivity(activityId, {
        title,
        description,
        visibility,
        start_idx: startIdx,
        end_idx: endIdx,
      })
      navigate(`/routes/${route.id}/`)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (!activity && !error) return <p className="p-6 text-sm text-ink-muted">Загрузка…</p>

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <h1 className="text-xl font-bold text-ink">Сохранить как маршрут</h1>
      {error && (
        <div className="mt-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}
      {activity?.track_points?.length > 0 && (
        <div className="mt-4 overflow-hidden rounded bg-white shadow-card">
          <TrackMap
            points={activity.track_points}
            highlightRange={highlight}
            className="h-[360px] w-full bg-gray-100"
          />
        </div>
      )}
      <form onSubmit={onSubmit} className="mt-6 space-y-4 rounded bg-white p-6 shadow-card">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="field-label" htmlFor="start">
              Начало (индекс точки)
            </label>
            <input
              id="start"
              type="number"
              min={0}
              max={maxIdx}
              className="field-input"
              value={startIdx}
              onChange={(e) => setStartIdx(Number(e.target.value))}
            />
          </div>
          <div>
            <label className="field-label" htmlFor="end">
              Конец (индекс точки)
            </label>
            <input
              id="end"
              type="number"
              min={0}
              max={maxIdx}
              className="field-input"
              value={endIdx}
              onChange={(e) => setEndIdx(Number(e.target.value))}
            />
          </div>
        </div>
        <div>
          <label className="field-label" htmlFor="title">
            Название
          </label>
          <input id="title" className="field-input" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div>
          <label className="field-label" htmlFor="description">
            Описание
          </label>
          <textarea
            id="description"
            className="field-input"
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
        <div>
          <label className="field-label" htmlFor="visibility">
            Видимость
          </label>
          <select
            id="visibility"
            className="field-input"
            value={visibility}
            onChange={(e) => setVisibility(e.target.value)}
          >
            <option value="private">Приватный</option>
            <option value="followers">Подписчики</option>
            <option value="public">Публичный</option>
          </select>
        </div>
        <button type="submit" className="btn-brand" disabled={busy}>
          {busy ? 'Сохранение…' : 'Создать маршрут'}
        </button>
      </form>
    </div>
  )
}
