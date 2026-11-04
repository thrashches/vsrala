import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { peopleApi } from '../api/endpoints'
import Avatar from '../components/Avatar'
import PeopleSectionNav from '../components/PeopleSectionNav'
import { ButtonSpinner, PeopleRowSkeleton } from '../components/skeletons'
import { useAuth } from '../hooks/AuthContext'

export default function PeopleListPage({ mode }) {
  const { id: routeId } = useParams()
  const { user } = useAuth()
  const id = routeId || (user ? String(user.id) : null)
  const isOwn = Boolean(user && id && String(user.id) === String(id))
  const showSectionNav = !routeId

  const [items, setItems] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState(null)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    setError('')
    const req = mode === 'followers' ? peopleApi.followers(id) : peopleApi.following(id)
    req
      .then((data) => setItems(Array.isArray(data) ? data : data.results || []))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [id, mode])

  const title = mode === 'followers' ? 'Подписчики' : 'Подписки'

  async function unfollow(personId) {
    setBusyId(personId)
    setError('')
    try {
      await peopleApi.follow(personId)
      setItems((prev) => prev.filter((p) => p.id !== personId))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  async function removeFollower(personId) {
    setBusyId(personId)
    setError('')
    try {
      await peopleApi.removeFollower(personId)
      setItems((prev) => prev.filter((p) => p.id !== personId))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="mx-auto max-w-lg px-4 py-10">
      <h1 className="text-xl font-bold text-ink">{title}</h1>
      {showSectionNav && <PeopleSectionNav />}
      {error && (
        <div className="mt-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}
      {loading && (
        <ul className="mt-6 space-y-3">
          <PeopleRowSkeleton withButton={isOwn} />
          <PeopleRowSkeleton withButton={isOwn} />
          <PeopleRowSkeleton withButton={isOwn} />
        </ul>
      )}
      {!loading && !items.length && !error && (
        <p className="mt-6 text-sm text-ink-muted">Список пуст</p>
      )}
      {!loading && (
        <ul className="mt-6 space-y-3">
          {items.map((p) => (
            <li key={p.id} className="flex items-center gap-3 rounded bg-white p-4 shadow-card">
              <Link to={`/people/${p.id}/`}>
                <Avatar person={p} />
              </Link>
              <Link to={`/people/${p.id}/`} className="min-w-0 flex-1 font-semibold hover:text-brand">
                {p.display_name}
              </Link>
              {isOwn && mode === 'following' && (
                <button
                  type="button"
                  className="btn-ghost text-xs"
                  disabled={busyId === p.id}
                  onClick={() => unfollow(p.id)}
                >
                  {busyId === p.id && <ButtonSpinner className="h-3 w-3" />}
                  Отписаться
                </button>
              )}
              {isOwn && mode === 'followers' && (
                <button
                  type="button"
                  className="btn-ghost text-xs"
                  disabled={busyId === p.id}
                  onClick={() => removeFollower(p.id)}
                >
                  {busyId === p.id && <ButtonSpinner className="h-3 w-3" />}
                  Удалить
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
