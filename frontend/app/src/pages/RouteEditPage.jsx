import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { routesApi } from '../api/endpoints'

export default function RouteEditPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [visibility, setVisibility] = useState('private')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    routesApi
      .get(id)
      .then((r) => {
        setTitle(r.title || '')
        setDescription(r.description || '')
        setVisibility(r.visibility || 'private')
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [id])

  async function onSubmit(e) {
    e.preventDefault()
    setBusy(true)
    try {
      await routesApi.update(id, { title, description, visibility })
      navigate(`/routes/${id}/`)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <p className="p-6 text-sm text-ink-muted">Загрузка…</p>

  return (
    <div className="mx-auto max-w-lg px-4 py-10">
      <h1 className="text-xl font-bold text-ink">Редактировать маршрут</h1>
      <form onSubmit={onSubmit} className="mt-6 space-y-4 rounded bg-white p-6 shadow-card">
        {error && (
          <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}
        <div>
          <label className="field-label" htmlFor="title">
            Название
          </label>
          <input
            id="title"
            className="field-input"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
          />
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
        <div className="flex gap-2">
          <button type="submit" className="btn-brand" disabled={busy}>
            Сохранить
          </button>
          <button type="button" className="btn-ghost" onClick={() => navigate(-1)}>
            Отмена
          </button>
        </div>
      </form>
    </div>
  )
}
