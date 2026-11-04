import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { activitiesApi } from '../api/endpoints'
import ActivityCharts from '../components/ActivityCharts'
import ActivitySource from '../components/ActivitySource'
import ActivityTypeLabel from '../components/ActivityTypeLabel'
import Avatar from '../components/Avatar'
import Reactions from '../components/Reactions'
import { ActivityDetailSkeleton, ButtonSpinner } from '../components/skeletons'
import TrackMap from '../components/TrackMap'
import { formatDateTime, parseDurationSec } from '../lib/format'

const TABS = [
  { id: 'stats', label: 'Статистика' },
  { id: 'hr', label: 'Пульс' },
  { id: 'power', label: 'Мощность' },
  { id: 'best', label: 'Лучшее время' },
]

function StatRow({ label, value, unit }) {
  if (value == null || value === '') return null
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-ink-muted">{label}</dt>
      <dd className="font-semibold text-ink">
        {value}
        {unit ? <span className="font-normal text-ink-muted"> {unit}</span> : null}
      </dd>
    </div>
  )
}

function StatCard({ title, children }) {
  const items = Array.isArray(children) ? children.filter(Boolean) : children
  if (!items || (Array.isArray(items) && items.length === 0)) return null
  return (
    <div className="rounded border border-gray-200 px-4 py-3">
      <h3 className="mb-3 text-sm font-semibold text-ink">{title}</h3>
      <dl className="space-y-2 text-sm">{items}</dl>
    </div>
  )
}

function ZoneDistribution({
  hasStream,
  zonesConfigured,
  rows = [],
  unit,
  title,
  emptyMessage,
  noZonesMessage,
}) {
  if (!hasStream) {
    return <p className="py-8 text-center text-sm text-ink-muted">{emptyMessage}</p>
  }
  if (!zonesConfigured) {
    return (
      <div className="py-8 text-center text-sm text-ink-muted">
        <p>{noZonesMessage}</p>
        <p className="mt-3">
          <Link to="/settings/" className="font-semibold text-brand hover:underline">
            Перейти в настройки
          </Link>{' '}
          и указать зоны.
        </p>
      </div>
    )
  }
  return (
    <>
      {title ? <h3 className="mb-3 text-sm font-semibold text-ink">{title}</h3> : null}
      <div className="grid grid-cols-[2.75rem_4.25rem_minmax(0,1fr)] gap-1 text-xs text-ink sm:grid-cols-[2.75rem_9.5rem_5.75rem_4.25rem_minmax(0,1fr)] sm:text-sm">
        {rows.map((row) => (
          <div key={row.label || row.name} className="contents">
            <div className="flex items-center justify-center rounded-sm bg-gray-100 px-1.5 py-2 font-semibold">
              {row.label}
            </div>
            <div className="hidden items-center overflow-hidden rounded-sm bg-gray-100 px-2.5 py-2 sm:flex">
              <span className="truncate">{row.name}</span>
            </div>
            <div className="hidden flex-col items-center justify-center rounded-sm bg-gray-100 px-2 py-1.5 tabular-nums leading-tight sm:flex">
              <span>{row.range}</span>
              <span className="text-[10px] text-ink-muted sm:text-[11px]">{unit}</span>
            </div>
            <div
              className={`flex flex-col items-center justify-center rounded-sm bg-gray-100 px-2 py-1.5 tabular-nums leading-tight ${
                row.has_time ? 'font-bold' : ''
              }`}
            >
              <span>{row.duration_display}</span>
              <span>{row.percent_display}</span>
            </div>
            <div className="overflow-hidden rounded-sm bg-gray-100">
              {row.has_time ? (
                <div
                  className="h-full min-h-[2.5rem]"
                  style={{ width: `${row.bar_percent}%`, backgroundColor: row.color }}
                />
              ) : (
                <div className="min-h-[2.5rem]" />
              )}
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

function BestEfforts({ bestEfforts }) {
  const data = bestEfforts && !Array.isArray(bestEfforts) ? bestEfforts : null
  const distanceRows = data?.distance_efforts || []
  const powerRows = data?.power_efforts || []
  const hasDistance = data?.has_distance_efforts ?? distanceRows.length > 0
  const hasPower = data?.has_power_efforts ?? powerRows.length > 0

  return (
    <div className="space-y-8">
      <div>
        <h3 className="mb-3 text-sm font-bold text-ink sm:text-base">Дистанция</h3>
        {hasDistance ? (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs text-ink sm:text-sm">
              <thead>
                <tr className="bg-gray-100">
                  <th className="px-2 py-2 text-left font-medium sm:px-3">Дистанция</th>
                  <th className="px-2 py-2 font-medium sm:px-3">Время</th>
                  <th className="px-2 py-2 font-medium sm:px-3">Скорость</th>
                </tr>
              </thead>
              <tbody>
                {distanceRows.map((row) => (
                  <tr key={row.distance_display} className="border-b border-gray-200">
                    <td className="px-2 py-2 sm:px-3 sm:py-2.5">{row.distance_display}</td>
                    <td className="px-2 py-2 tabular-nums sm:px-3 sm:py-2.5">{row.time_display}</td>
                    <td className="px-2 py-2 tabular-nums sm:px-3 sm:py-2.5">{row.speed_display}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="py-4 text-sm text-ink-muted">Недостаточно данных о дистанции</p>
        )}
      </div>
      <div>
        <h3 className="mb-3 text-sm font-bold text-ink sm:text-base">Мощность</h3>
        {hasPower ? (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs text-ink sm:text-sm">
              <thead>
                <tr className="bg-gray-100">
                  <th className="px-2 py-2 font-medium sm:px-3">Время</th>
                  <th className="px-2 py-2 font-medium sm:px-3">Мощность</th>
                </tr>
              </thead>
              <tbody>
                {powerRows.map((row) => (
                  <tr key={row.window_display} className="border-b border-gray-200">
                    <td className="px-2 py-2 sm:px-3 sm:py-2.5">{row.window_display}</td>
                    <td className="px-2 py-2 tabular-nums sm:px-3 sm:py-2.5">{row.watts_display}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="py-4 text-sm text-ink-muted">Нет данных о мощности</p>
        )}
      </div>
    </div>
  )
}

function zoneTimelineTitle(zoneStream) {
  if (zoneStream === 'power') return 'Мощность по зонам'
  if (zoneStream === 'hr') return 'Пульс по зонам'
  return 'Зоны'
}

export default function ActivityDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const mapRef = useRef(null)
  const menuRef = useRef(null)
  const [activity, setActivity] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [commentText, setCommentText] = useState('')
  const [busy, setBusy] = useState(false)
  const [tab, setTab] = useState('stats')
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    activitiesApi
      .get(id)
      .then((data) => {
        if (!cancelled) setActivity(data)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [id])

  useEffect(() => {
    if (!menuOpen) return undefined
    function onDocClick(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [menuOpen])

  function handleHoverTime(t) {
    mapRef.current?.setTime(t)
  }

  async function submitComment(e) {
    e.preventDefault()
    if (!commentText.trim()) return
    setBusy(true)
    try {
      const data = await activitiesApi.comments.listCreate(id, commentText.trim())
      setActivity((prev) => ({
        ...prev,
        comments: data.comment ? [...(prev.comments || []), data.comment] : prev.comments,
        comment_count: data.comment_count ?? prev.comment_count,
      }))
      setCommentText('')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function deleteComment(commentId) {
    setBusy(true)
    try {
      const data = await activitiesApi.comments.remove(id, commentId)
      setActivity((prev) => ({
        ...prev,
        comments: (prev.comments || []).filter((c) => c.id !== commentId),
        comment_count: data.comment_count ?? prev.comment_count - 1,
      }))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function handleDelete() {
    if (!window.confirm('Удалить тренировку?')) return
    await activitiesApi.remove(id)
    navigate('/feed/')
  }

  async function handleDownloadFit() {
    setMenuOpen(false)
    try {
      const res = await activitiesApi.download(id)
      if (!res.ok) throw new Error('Не удалось скачать файл')
      const blob = await res.blob()
      const cd = res.headers.get('content-disposition') || ''
      const match = cd.match(/filename="?([^";]+)"?/i)
      const filename = match?.[1] || `${activity?.title || 'activity'}.fit`
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err.message)
    }
  }

  if (loading) return <ActivityDetailSkeleton />
  if (error && !activity) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-6">
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
      </div>
    )
  }
  if (!activity) return null

  const durationSec = parseDurationSec(activity.duration)
  const streams = activity.streams || {}
  const hasStreams =
    streams.speed?.length || streams.hr?.length || streams.power?.length || streams.ele?.length

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      {error && (
        <div className="mb-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}
      <div className="relative rounded bg-white shadow-card">
        <div className="border-b border-gray-100 px-5 py-4">
          <div className="flex items-start gap-3">
            <Link to={`/people/${activity.profile.id}/`}>
              <Avatar person={activity.profile} className="h-12 w-12 text-base" />
            </Link>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-semibold">
                <Link to={`/people/${activity.profile.id}/`} className="hover:text-brand">
                  {activity.profile.display_name}
                </Link>
              </div>
              <div className="text-xs text-ink-muted">
                {formatDateTime(activity.started_at)}
                {activity.activity_type?.name ? (
                  <>
                    {' · '}
                    <ActivityTypeLabel activityType={activity.activity_type} />
                  </>
                ) : null}
                {activity.is_indoor ? (
                  <>
                    {' · '}
                    <span className="font-semibold text-ink">Indoor</span>
                  </>
                ) : null}
                {' · '}
                <ActivitySource source={activity.external_source} />
              </div>
              <h1 className="mt-2 text-2xl font-bold text-ink">{activity.title}</h1>
              {activity.description && (
                <p className="mt-2 text-sm text-ink-muted">{activity.description}</p>
              )}
              {activity.is_owner && activity.track_points?.length > 0 && (
                <Link
                  to={`/routes/from-activity/${activity.id}/`}
                  className="mt-3 inline-flex items-center gap-1 rounded border border-gray-200 px-3 py-1.5 text-sm font-semibold text-ink hover:bg-gray-50"
                >
                  <span className="material-icons text-[18px] leading-none" aria-hidden="true">
                    route
                  </span>
                  Сохранить как маршрут
                </Link>
              )}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 border-b border-gray-100 px-5 py-4 sm:grid-cols-3 lg:grid-cols-7">
          {[
            ['Расстояние', activity.distance != null ? `${activity.distance}` : null, 'км'],
            ['Время', activity.duration_display, null],
            ['Ср. скорость', activity.avg_speed, 'км/ч'],
            ['Макс. скорость', activity.max_speed, 'км/ч'],
            ['Набор высоты', activity.elevation_gain, 'м'],
            ['Ср. мощность', activity.avg_power, 'Вт'],
            ['TSS', activity.tss, null],
          ].map(([label, value, unit]) => (
            <div key={label}>
              <div className="stat-label">{label}</div>
              <div className="stat-value">
                {value != null && value !== '' ? value : '—'}
                {value != null && value !== '' && unit ? (
                  <span className="stat-unit">{unit}</span>
                ) : null}
              </div>
            </div>
          ))}
        </div>

        {activity.track_points?.length > 0 && (
          <div className="relative z-0 overflow-hidden">
            <TrackMap
              ref={mapRef}
              points={activity.track_points}
              durationSec={durationSec}
            />
          </div>
        )}

        {activity.zone_timeline_url && (
          <div className="border-t border-gray-100 px-5 py-4">
            <h3 className="mb-2 text-sm font-semibold text-ink">
              {zoneTimelineTitle(activity.zone_stream)}
            </h3>
            <img
              src={activity.zone_timeline_url}
              alt="Таймлайн зон"
              className="w-full rounded border border-gray-100 bg-feed"
            />
          </div>
        )}

        {hasStreams ? (
          <ActivityCharts
            streams={streams}
            durationSec={durationSec}
            onHoverTime={handleHoverTime}
          />
        ) : null}

        <div className="border-t border-gray-100">
          <div className="flex items-stretch border-b border-gray-100 px-5">
            <div className="flex min-w-0 flex-1 flex-nowrap gap-1 overflow-x-auto" role="tablist">
              {TABS.map((t) => {
                const selected = tab === t.id
                return (
                  <button
                    key={t.id}
                    type="button"
                    role="tab"
                    aria-selected={selected}
                    onClick={() => setTab(t.id)}
                    className={`shrink-0 border-b-2 px-2.5 py-2.5 text-xs font-semibold sm:px-3 sm:py-3 sm:text-sm ${
                      selected
                        ? 'border-brand text-brand'
                        : 'border-transparent text-ink-muted hover:text-ink'
                    }`}
                  >
                    {t.label}
                  </button>
                )
              })}
            </div>
            {activity.is_owner && (
              <div ref={menuRef} className="relative ml-1 flex shrink-0 items-center">
                <button
                  type="button"
                  className="rounded p-1.5 text-ink-muted hover:bg-gray-100 hover:text-ink"
                  aria-expanded={menuOpen}
                  aria-haspopup="true"
                  aria-label="Действия с тренировкой"
                  onClick={() => setMenuOpen((v) => !v)}
                >
                  <span className="material-icons text-[22px] leading-none" aria-hidden="true">
                    more_vert
                  </span>
                </button>
                {menuOpen && (
                  <div
                    className="absolute right-0 top-full z-20 mt-1 w-48 overflow-hidden rounded border border-gray-200 bg-white py-1 shadow-card"
                    role="menu"
                  >
                    {activity.has_track_file && (
                      <button
                        type="button"
                        className="flex w-full items-center gap-2 px-4 py-2 text-left text-sm font-medium text-ink hover:bg-gray-50"
                        role="menuitem"
                        onClick={handleDownloadFit}
                      >
                        <span
                          className="material-icons text-[18px] leading-none text-ink-muted"
                          aria-hidden="true"
                        >
                          download
                        </span>
                        Скачать .fit
                      </button>
                    )}
                    <Link
                      to={`/activities/${activity.id}/edit/`}
                      className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-ink hover:bg-gray-50"
                      role="menuitem"
                      onClick={() => setMenuOpen(false)}
                    >
                      <span
                        className="material-icons text-[18px] leading-none text-ink-muted"
                        aria-hidden="true"
                      >
                        edit
                      </span>
                      Редактировать
                    </Link>
                    <button
                      type="button"
                      className="flex w-full items-center gap-2 px-4 py-2 text-left text-sm font-medium text-red-600 hover:bg-red-50"
                      role="menuitem"
                      onClick={() => {
                        setMenuOpen(false)
                        handleDelete()
                      }}
                    >
                      <span className="material-icons text-[18px] leading-none" aria-hidden="true">
                        delete
                      </span>
                      Удалить
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>

          {tab === 'stats' && (
            <div className="px-5 py-5">
              <div className="grid gap-4 sm:grid-cols-2">
                {activity.distance != null && (
                  <StatCard title="Расстояние">
                    <StatRow label="Расстояние" value={activity.distance} unit="км" />
                  </StatCard>
                )}
                {(activity.duration || activity.duration_active) && (
                  <StatCard title="Время">
                    <StatRow label="Общее" value={activity.duration_display} />
                    <StatRow label="В движении" value={activity.duration_active_display} />
                  </StatCard>
                )}
                {(activity.avg_hr || activity.max_hr) && (
                  <StatCard title="Пульс">
                    <StatRow label="Средний" value={activity.avg_hr} unit="уд/мин" />
                    <StatRow label="Максимальный" value={activity.max_hr} unit="уд/мин" />
                  </StatCard>
                )}
                {(activity.avg_power ||
                  activity.normalized_power ||
                  activity.max_power ||
                  activity.tss) && (
                  <StatCard title="Мощность">
                    <StatRow label="Средняя" value={activity.avg_power} unit="Вт" />
                    <StatRow label="Нормализованная" value={activity.normalized_power} unit="Вт" />
                    <StatRow label="Максимальная" value={activity.max_power} unit="Вт" />
                    <StatRow label="TSS" value={activity.tss} />
                  </StatCard>
                )}
                {(activity.avg_speed || activity.avg_moving_speed || activity.max_speed) && (
                  <StatCard title="Скорость">
                    <StatRow label="Средняя" value={activity.avg_speed} unit="км/ч" />
                    <StatRow
                      label="Средняя в движении"
                      value={activity.avg_moving_speed}
                      unit="км/ч"
                    />
                    <StatRow label="Максимальная" value={activity.max_speed} unit="км/ч" />
                  </StatCard>
                )}
                {(activity.avg_cadence || activity.max_cadence) && (
                  <StatCard title="Частота вращения">
                    <StatRow label="Средняя" value={activity.avg_cadence} unit="об/мин" />
                    <StatRow label="Максимальная" value={activity.max_cadence} unit="об/мин" />
                  </StatCard>
                )}
                {(activity.elevation_min ||
                  activity.elevation_max ||
                  activity.elevation_gain ||
                  activity.elevation_loss) && (
                  <StatCard title="Высота">
                    <StatRow label="Минимальная" value={activity.elevation_min} unit="м" />
                    <StatRow label="Максимальная" value={activity.elevation_max} unit="м" />
                    <StatRow label="Набор высоты" value={activity.elevation_gain} unit="м" />
                    <StatRow label="Спуск" value={activity.elevation_loss} unit="м" />
                  </StatCard>
                )}
                {(activity.calories ||
                  activity.aerobic_training_effect ||
                  activity.anaerobic_training_effect ||
                  activity.device_name ||
                  activity.avg_temperature ||
                  activity.vo2max) && (
                  <StatCard title="Garmin">
                    <StatRow label="Калории" value={activity.calories} unit="ккал" />
                    <StatRow
                      label="Training Effect (аэробный)"
                      value={activity.aerobic_training_effect}
                    />
                    <StatRow
                      label="Training Effect (анаэробный)"
                      value={activity.anaerobic_training_effect}
                    />
                    <StatRow label="VO₂max" value={activity.vo2max} />
                    <StatRow label="Температура" value={activity.avg_temperature} unit="°C" />
                    <StatRow label="Устройство" value={activity.device_name} />
                  </StatCard>
                )}
              </div>
            </div>
          )}

          {tab === 'hr' && (
            <div className="px-5 py-5">
              <ZoneDistribution
                hasStream={activity.has_hr_stream}
                zonesConfigured={activity.hr_zones_configured}
                rows={activity.hr_zone_rows}
                unit="уд/мин"
                title="Анализ пульса"
                emptyMessage="Нет данных о пульсе"
                noZonesMessage="Зоны пульса не заданы."
              />
            </div>
          )}

          {tab === 'power' && (
            <div className="px-5 py-5">
              <ZoneDistribution
                hasStream={activity.has_power_stream}
                zonesConfigured={activity.power_zones_configured}
                rows={activity.power_zone_rows}
                unit="Ватт"
                title="Анализ мощности"
                emptyMessage="Нет данных о мощности"
                noZonesMessage="Зоны мощности не заданы."
              />
            </div>
          )}

          {tab === 'best' && (
            <div className="px-5 py-5">
              <BestEfforts bestEfforts={activity.best_efforts} />
            </div>
          )}
        </div>

        <div className="relative z-10 border-t border-gray-100 px-5 py-4">
          <Reactions
            activityId={activity.id}
            counts={activity.reaction_counts || []}
            mine={activity.my_reaction}
            choices={activity.reaction_choices}
            onChange={(patch) =>
              setActivity((prev) => ({
                ...prev,
                reaction_counts: patch.counts ?? prev.reaction_counts,
                my_reaction: patch.mine !== undefined ? patch.mine : prev.my_reaction,
              }))
            }
          />
        </div>

        <div id="comments" className="border-t border-gray-100 px-5 py-4">
          <h3 className="mb-3 text-sm font-semibold">
            Комментарии ({activity.comment_count || 0})
          </h3>
          <ul className="space-y-3">
            {(activity.comments || []).map((c) => (
              <li key={c.id} className="flex gap-3">
                <Avatar person={c.profile || c.author} className="h-8 w-8 text-xs" />
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-semibold">
                    {(c.profile || c.author)?.display_name}
                  </div>
                  <p className="text-sm text-ink">{c.text}</p>
                  {c.can_delete && (
                    <button
                      type="button"
                      className="mt-1 inline-flex items-center gap-1 text-xs text-red-600 disabled:opacity-50"
                      disabled={busy}
                      onClick={() => deleteComment(c.id)}
                    >
                      {busy && <ButtonSpinner className="h-3 w-3" />}
                      Удалить
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
          <form onSubmit={submitComment} className="mt-4 flex gap-2">
            <textarea
              className="field-input min-h-[2.5rem] flex-1"
              rows={2}
              placeholder="Написать комментарий…"
              value={commentText}
              onChange={(e) => setCommentText(e.target.value)}
            />
            <button type="submit" className="btn-brand self-end" disabled={busy}>
              {busy && <ButtonSpinner />}
              {busy ? 'Отправка…' : 'Отправить'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
