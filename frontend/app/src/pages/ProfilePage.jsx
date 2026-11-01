import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { peopleApi } from '../api/endpoints'
import ActivityCard from '../components/ActivityCard'
import Avatar from '../components/Avatar'

export default function ProfilePage() {
  const { id } = useParams()
  const [profile, setProfile] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    peopleApi
      .profile(id)
      .then(setProfile)
      .catch((err) => setError(err.message))
  }, [id])

  async function toggleFollow() {
    setBusy(true)
    try {
      const data = await peopleApi.follow(id)
      setProfile((prev) => ({
        ...prev,
        is_following: data.is_following,
        request_pending: data.request_pending,
        followers_count: data.followers_count ?? prev.followers_count,
      }))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (error && !profile) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-6 text-sm text-red-700">{error}</div>
    )
  }
  if (!profile) return <p className="p-6 text-sm text-ink-muted">Загрузка…</p>

  const followLabel = profile.is_following
    ? 'Отписаться'
    : profile.request_pending
      ? 'Запрос отправлен'
      : 'Подписаться'

  return (
    <div className="mx-auto max-w-3xl px-4 py-6">
      <div className="rounded bg-white p-6 shadow-card">
        <div className="flex items-start gap-4">
          <Avatar person={profile} className="h-20 w-20 text-xl" />
          <div className="min-w-0 flex-1">
            <h1 className="text-xl font-bold">{profile.display_name}</h1>
            <div className="mt-2 flex flex-wrap gap-4 text-sm text-ink-muted">
              <Link to={`/people/${id}/following/`} className="hover:text-brand">
                <strong className="text-ink">{profile.following_count}</strong> подписок
              </Link>
              <Link to={`/people/${id}/followers/`} className="hover:text-brand">
                <strong className="text-ink">{profile.followers_count}</strong> подписчиков
              </Link>
            </div>
            <div className="mt-2 flex flex-wrap gap-3 text-sm">
              {profile.telegram && <span>TG: {profile.telegram}</span>}
              {profile.instagram && <span>IG: {profile.instagram}</span>}
              {profile.vk && <span>VK: {profile.vk}</span>}
            </div>
            {!profile.is_own_profile && (
              <button
                type="button"
                className="btn-brand mt-4"
                disabled={busy || profile.request_pending}
                onClick={toggleFollow}
              >
                {followLabel}
              </button>
            )}
          </div>
        </div>
        {(profile.year_stats?.selected || profile.year_stats?.by_year) && (
          <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {(() => {
              const year = profile.year_stats.selected_year
              const stats =
                profile.year_stats.selected ||
                profile.year_stats.by_year?.[String(year)] ||
                profile.year_stats.by_year?.[year] ||
                {}
              return [
                ['Дистанция', stats.distance_display],
                ['Время', stats.duration_display],
                ['Набор', stats.elevation_display],
                ['Тренировок', stats.count_display],
              ].map(([label, value]) => (
                <div key={label}>
                  <div className="stat-label">
                    {label} {year}
                  </div>
                  <div className="text-lg font-bold">{value ?? '—'}</div>
                </div>
              ))
            })()}
          </div>
        )}
      </div>

      <div className="mt-6 space-y-4">
        {(profile.activities || []).map((a) => (
          <ActivityCard key={a.id} activity={a} />
        ))}
        {!profile.activities?.length && (
          <p className="text-sm text-ink-muted">Нет доступных тренировок</p>
        )}
      </div>
    </div>
  )
}
