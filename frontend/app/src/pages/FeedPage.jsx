import { useCallback, useEffect, useState } from 'react'
import { activitiesApi } from '../api/endpoints'
import ActivityCard from '../components/ActivityCard'
import WeeklyLeaders from '../components/WeeklyLeaders'

export default function FeedPage({ scope = 'feed' }) {
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await activitiesApi.list({ scope, page })
      setData(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [scope, page])

  useEffect(() => {
    load()
  }, [load])

  function patchActivity(id, patch) {
    setData((prev) => {
      if (!prev) return prev
      const results = (prev.results || []).map((a) =>
        a.id === id
          ? {
              ...a,
              reaction_counts: patch.counts ?? a.reaction_counts,
              my_reaction: patch.mine !== undefined ? patch.mine : a.my_reaction,
            }
          : a,
      )
      return { ...prev, results }
    })
  }

  const activities = data?.results || []
  const totalPages = data?.count ? Math.ceil(data.count / (data.page_size || 50)) : 1
  const title = scope === 'mine' ? 'Мои тренировки' : 'Лента активности'

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <div className="mb-4 sm:hidden">
        <h1 className="text-lg font-bold text-ink">{title}</h1>
      </div>
      <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
        <div className="min-w-0 flex-1 lg:max-w-2xl">
          {loading && <p className="text-sm text-ink-muted">Загрузка…</p>}
          {error && (
            <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}
          {!loading && !activities.length && !error && (
            <div className="rounded bg-white p-8 text-center shadow-card">
              <p className="text-sm text-ink-muted">
                {scope === 'mine' ? 'Пока нет тренировок' : 'Лента пуста — подпишитесь на людей или загрузите активность'}
              </p>
            </div>
          )}
          <div className="space-y-4">
            {activities.map((activity) => (
              <ActivityCard
                key={activity.id}
                activity={activity}
                onReactionChange={(patch) => patchActivity(activity.id, patch)}
              />
            ))}
          </div>
          {data && (data.next || data.previous) && (
            <div className="mt-6 flex justify-center gap-2">
              <button
                type="button"
                className="btn-ghost"
                disabled={!data.previous || page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Назад
              </button>
              <span className="px-3 py-2 text-sm text-ink-muted">
                {page}
                {totalPages > 1 ? ` / ${totalPages}` : ''}
              </span>
              <button
                type="button"
                className="btn-ghost"
                disabled={!data.next}
                onClick={() => setPage((p) => p + 1)}
              >
                Вперёд
              </button>
            </div>
          )}
        </div>
        {scope === 'feed' && (
          <div className="w-full shrink-0 lg:w-72">
            <WeeklyLeaders />
          </div>
        )}
      </div>
    </div>
  )
}
