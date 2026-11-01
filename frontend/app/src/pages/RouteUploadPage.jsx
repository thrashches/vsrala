import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { routesApi } from '../api/endpoints'
import { ButtonSpinner } from '../components/skeletons'

export default function RouteUploadPage() {
  const navigate = useNavigate()
  const [file, setFile] = useState(null)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [visibility, setVisibility] = useState('private')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function onSubmit(e) {
    e.preventDefault()
    if (!file) {
      setError('Выберите файл .gpx')
      return
    }
    setBusy(true)
    setError('')
    try {
      const fd = new FormData()
      fd.append('source_gpx', file)
      if (title) fd.append('title', title)
      if (description) fd.append('description', description)
      fd.append('visibility', visibility)
      const route = await routesApi.create(fd)
      navigate(`/routes/${route.id}/`)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-lg px-4 py-10">
      <h1 className="text-xl font-bold text-ink">Загрузить маршрут</h1>
      <form onSubmit={onSubmit} className="mt-6 space-y-4 rounded bg-white p-6 shadow-card">
        {error && (
          <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}
        <div>
          <label className="field-label" htmlFor="gpx">
            GPX файл
          </label>
          <input
            id="gpx"
            type="file"
            accept=".gpx"
            className="block w-full text-sm"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            required
          />
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
          {busy && <ButtonSpinner />}
          {busy ? 'Загрузка…' : 'Загрузить'}
        </button>
      </form>
    </div>
  )
}
