import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { activitiesApi } from '../api/endpoints'

export default function ActivityEditPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    activitiesApi
      .get(id)
      .then((a) => {
        setTitle(a.title || '')
        setDescription(a.description || '')
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [id])

  async function onSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await activitiesApi.update(id, { title, description })
      navigate(`/activities/${id}/`)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <p className="p-6 text-sm text-ink-muted">Загрузка…</p>

  return (
    <div className="mx-auto max-w-lg px-4 py-10">
      <h1 className="text-xl font-bold text-ink">Редактировать тренировку</h1>
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
            rows={4}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
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
