import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { peopleApi } from '../api/endpoints'
import Avatar from '../components/Avatar'
import { PeopleRowSkeleton } from '../components/skeletons'

export default function PeopleListPage({ mode }) {
  const { id } = useParams()
  const [items, setItems] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    const req = mode === 'followers' ? peopleApi.followers(id) : peopleApi.following(id)
    req
      .then((data) => setItems(Array.isArray(data) ? data : data.results || []))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [id, mode])

  const title = mode === 'followers' ? 'Подписчики' : 'Подписки'

  return (
    <div className="mx-auto max-w-lg px-4 py-10">
      <h1 className="text-xl font-bold text-ink">{title}</h1>
      {error && (
        <div className="mt-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}
      {loading && (
        <ul className="mt-6 space-y-3">
          <PeopleRowSkeleton />
          <PeopleRowSkeleton />
          <PeopleRowSkeleton />
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
              <Link to={`/people/${p.id}/`} className="font-semibold hover:text-brand">
                {p.display_name}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
