import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { activitiesApi } from '../api/endpoints'

export default function ActivityUploadPage() {
  const navigate = useNavigate()
  const [file, setFile] = useState(null)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function onSubmit(e) {
    e.preventDefault()
    if (!file) {
      setError('Выберите файл .gpx или .fit')
      return
    }
    setBusy(true)
    setError('')
    try {
      const fd = new FormData()
      fd.append('track_file', file)
      if (title) fd.append('title', title)
      if (description) fd.append('description', description)
      const activity = await activitiesApi.create(fd)
      navigate(`/activities/${activity.id}/`)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-lg px-4 py-10">
      <h1 className="text-xl font-bold text-ink">Загрузить тренировку</h1>
      <p className="mt-1 text-sm text-ink-muted">Файл GPX или FIT, до 50 МБ.</p>
      <form onSubmit={onSubmit} className="mt-6 space-y-4 rounded bg-white p-6 shadow-card">
        {error && (
          <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}
        <div>
          <label className="field-label" htmlFor="track_file">
            Файл
          </label>
          <input
            id="track_file"
            type="file"
            accept=".gpx,.fit"
            className="block w-full text-sm"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            required
          />
        </div>
        <div>
          <label className="field-label" htmlFor="title">
            Название
          </label>
          <input
            id="title"
            className="field-input"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
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
        <button type="submit" className="btn-brand" disabled={busy}>
          {busy ? 'Загрузка…' : 'Загрузить'}
        </button>
      </form>
    </div>
  )
}
