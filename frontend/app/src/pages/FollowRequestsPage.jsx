import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { peopleApi } from '../api/endpoints'
import { useAuth } from '../hooks/AuthContext'
import Avatar from '../components/Avatar'
import { formatDateTime } from '../lib/format'

export default function FollowRequestsPage() {
  const { setPendingRequests } = useAuth()
  const [items, setItems] = useState([])
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)

  async function load() {
    try {
      const data = await peopleApi.requests()
      const list = Array.isArray(data) ? data : data.results || []
      setItems(list)
      setPendingRequests(list.length)
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function act(id, action) {
    setBusyId(id)
    try {
      if (action === 'accept') await peopleApi.accept(id)
      else await peopleApi.reject(id)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="mx-auto max-w-lg px-4 py-10">
      <h1 className="text-xl font-bold text-ink">Запросы на подписку</h1>
      {error && (
        <div className="mt-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}
      {!items.length && (
        <p className="mt-6 text-sm text-ink-muted">Нет входящих запросов</p>
      )}
      <ul className="mt-6 space-y-3">
        {items.map((r) => (
          <li key={r.id} className="flex items-center gap-3 rounded bg-white p-4 shadow-card">
            <Link to={`/people/${r.from_user.id}/`}>
              <Avatar person={r.from_user} />
            </Link>
            <div className="min-w-0 flex-1">
              <Link to={`/people/${r.from_user.id}/`} className="font-semibold hover:text-brand">
                {r.from_user.display_name}
              </Link>
              <div className="text-xs text-ink-muted">{formatDateTime(r.created_at)}</div>
            </div>
            <button
              type="button"
              className="btn-brand text-xs"
              disabled={busyId === r.id}
              onClick={() => act(r.id, 'accept')}
            >
              Принять
            </button>
            <button
              type="button"
              className="btn-ghost text-xs"
              disabled={busyId === r.id}
              onClick={() => act(r.id, 'reject')}
            >
              Отклонить
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
