import { useEffect, useState } from 'react'
import { statsApi } from '../api/endpoints'
import MetricHistoryChart from '../components/MetricHistoryChart'
import { ProfileSkeleton } from '../components/skeletons'

function StatCard({ label, value, hint }) {
  return (
    <div className="rounded bg-white p-4 shadow-card">
      <div className="stat-label">{label}</div>
      <div className="mt-1 text-xl font-bold text-ink">{value ?? '—'}</div>
      {hint ? <div className="mt-0.5 text-xs text-ink-muted">{hint}</div> : null}
    </div>
  )
}

function avgHint(averages) {
  if (!averages) return ''
  const parts = []
  if (averages.distance_display) parts.push(`ср. ${averages.distance_display}`)
  if (averages.duration_display) parts.push(averages.duration_display)
  if (averages.pace_display) parts.push(averages.pace_display)
  else if (averages.speed_display) parts.push(averages.speed_display)
  return parts.join(' · ')
}

export default function StatsPage() {
  const [year, setYear] = useState(null)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    statsApi
      .me(year ? { year } : {})
      .then((payload) => {
        if (cancelled) return
        setData(payload)
        if (year == null && payload?.year != null) setYear(payload.year)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || 'Не удалось загрузить статистику')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [year])

  if (loading && !data) return <ProfileSkeleton />

  if (error && !data) {
    return <div className="mx-auto max-w-5xl px-4 py-6 text-sm text-red-700">{error}</div>
  }

  const totals = data?.totals || {}
  const byType = data?.by_type || []
  const metrics = data?.metrics || {}
  const years = data?.years || []

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-ink">Статистика</h1>
        {years.length > 0 && (
          <label className="flex items-center gap-2 text-sm text-ink">
            <span className="text-ink-muted">Год</span>
            <select
              className="rounded border border-gray-300 bg-white px-3 py-1.5 font-medium"
              value={data?.year ?? ''}
              onChange={(e) => setYear(Number(e.target.value))}
            >
              {years.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      {error && <p className="mb-4 text-sm text-red-700">{error}</p>}

      <section className="mb-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-muted">
          Итоги {data?.year}
        </h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <StatCard label="Дистанция" value={totals.distance_display} hint={avgHint(totals.averages)} />
          <StatCard label="Время" value={totals.duration_display} />
          <StatCard
            label="Средняя"
            value={
              totals.averages?.pace_display ||
              totals.averages?.speed_display ||
              totals.averages?.distance_display ||
              '—'
            }
            hint={
              totals.averages?.pace_display || totals.averages?.speed_display
                ? `на тренировку: ${totals.averages?.distance_display || '—'} · ${totals.averages?.duration_display || '—'}`
                : 'на тренировку'
            }
          />
          <StatCard label="Набор" value={totals.elevation_display} />
          <StatCard label="Тренировок" value={totals.count_display} hint={totals.tss ? `TSS ${totals.tss_display}` : ''} />
        </div>
      </section>

      <section className="mb-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-muted">
          По видам спорта
        </h2>
        {byType.length === 0 ? (
          <p className="rounded bg-white p-6 text-sm text-ink-muted shadow-card">
            Нет тренировок за выбранный год
          </p>
        ) : (
          <div className="overflow-x-auto rounded bg-white shadow-card">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-xs uppercase tracking-wide text-ink-muted">
                  <th className="px-4 py-3 font-semibold">Тип</th>
                  <th className="px-4 py-3 font-semibold">Дистанция</th>
                  <th className="px-4 py-3 font-semibold">Время</th>
                  <th className="px-4 py-3 font-semibold">Средняя</th>
                  <th className="px-4 py-3 font-semibold">Набор</th>
                  <th className="px-4 py-3 font-semibold">Кол-во</th>
                </tr>
              </thead>
              <tbody>
                {byType.map((row) => (
                  <tr key={row.slug} className="border-b border-gray-100 last:border-0">
                    <td className="px-4 py-3 font-medium text-ink">{row.name}</td>
                    <td className="px-4 py-3">{row.distance_display}</td>
                    <td className="px-4 py-3">{row.duration_display}</td>
                    <td className="px-4 py-3 text-ink-muted">
                      {row.averages?.pace_display ||
                        row.averages?.speed_display ||
                        row.averages?.distance_display ||
                        '—'}
                    </td>
                    <td className="px-4 py-3">{row.elevation_display}</td>
                    <td className="px-4 py-3">{row.count_display}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-muted">
          Динамика показателей
        </h2>
        <div className="grid gap-4 lg:grid-cols-3">
          <MetricHistoryChart title="FTP" unit="Вт" series={metrics.ftp} color="#2563eb" />
          <MetricHistoryChart title="Вес" unit="кг" series={metrics.weight} color="#16a34a" />
          <MetricHistoryChart title="VO2max" unit="мл/кг/мин" series={metrics.vo2max} color="#e85d04" />
        </div>
        <p className="mt-3 text-xs text-ink-muted">
          История подтягивается из Garmin и Intervals.icu при синхронизации. Ручное редактирование — позже.
        </p>
      </section>
    </div>
  )
}
