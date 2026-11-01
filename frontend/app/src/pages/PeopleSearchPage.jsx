import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { peopleApi } from '../api/endpoints'
import Avatar from '../components/Avatar'

export default function PeopleSearchPage() {
  const [q, setQ] = useState('')
  const [results, setResults] = useState([])
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)

  useEffect(() => {
    const t = setTimeout(() => {
      peopleApi
        .search(q)
        .then((data) => setResults(Array.isArray(data) ? data : data.results || []))
        .catch((err) => setError(err.message))
    }, 250)
    return () => clearTimeout(t)
  }, [q])

  async function toggleFollow(id) {
    setBusyId(id)
    try {
      const data = await peopleApi.follow(id)
      setResults((prev) =>
        prev.map((p) =>
          p.id === id
            ? {
                ...p,
                is_following: data.is_following,
                request_pending: data.request_pending,
              }
            : p,
        ),
      )
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  function followLabel(p) {
    if (p.is_following) return 'Отписаться'
    if (p.request_pending) return 'Запрос отправлен'
    return 'Подписаться'
  }

  return (
    <div className="mx-auto max-w-lg px-4 py-10">
      <h1 className="text-xl font-bold text-ink">Люди</h1>
      <input
        className="field-input mt-4"
        placeholder="Поиск по имени или email…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      {error && (
        <div className="mt-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}
      <ul className="mt-6 space-y-3">
        {results.map((p) => (
          <li key={p.id} className="flex items-center gap-3 rounded bg-white p-4 shadow-card">
            <Link to={`/people/${p.id}/`}>
              <Avatar person={p} />
            </Link>
            <div className="min-w-0 flex-1">
              <Link to={`/people/${p.id}/`} className="font-semibold hover:text-brand">
                {p.display_name}
              </Link>
              {!p.is_public && (
                <span className="ml-2 text-xs text-ink-muted">закрытый</span>
              )}
            </div>
            <button
              type="button"
              className="btn-ghost text-xs"
              disabled={busyId === p.id || p.request_pending}
              onClick={() => toggleFollow(p.id)}
            >
              {followLabel(p)}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
