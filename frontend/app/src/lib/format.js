export function formatDateTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('ru-RU', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

/** Parse DRF DurationField (seconds number, "H:MM:SS", or ISO-8601) to seconds. */
export function parseDurationSec(value) {
  if (value == null || value === '') return 0
  if (typeof value === 'number' && Number.isFinite(value)) return value
  const s = String(value).trim()
  if (!s) return 0
  if (/^\d+(\.\d+)?$/.test(s)) return Number(s)
  const clock = s.match(/^(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)$/)
  if (clock) {
    const h = Number(clock[1] || 0)
    const m = Number(clock[2])
    const sec = Number(clock[3])
    return h * 3600 + m * 60 + sec
  }
  const iso = s.match(
    /^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?$/i,
  )
  if (iso) {
    return (
      Number(iso[1] || 0) * 86400 +
      Number(iso[2] || 0) * 3600 +
      Number(iso[3] || 0) * 60 +
      Number(iso[4] || 0)
    )
  }
  return 0
}

export function initialFrom(nameOrEmail) {
  const s = (nameOrEmail || '?').trim()
  return (s[0] || '?').toUpperCase()
}

export function sourceLabel(source) {
  if (source === 'garmin') return 'Garmin'
  if (source === 'intervals') return 'Intervals.icu'
  return 'Загрузка'
}

export function sourceIcon(source) {
  if (source === 'garmin') return '/static/img/source-garmin.svg'
  if (source === 'intervals') return '/static/img/source-intervals.svg'
  return '/static/img/source-upload.svg'
}

/** Foot sports (run / walk / ski / hike) prefer pace over speed. */
export function usesPace(activityOrFlag) {
  if (typeof activityOrFlag === 'boolean') return activityOrFlag
  if (activityOrFlag?.uses_pace != null) return Boolean(activityOrFlag.uses_pace)
  const slug = (activityOrFlag?.activity_type?.slug || activityOrFlag?.slug || '')
    .toString()
    .toLowerCase()
  return slug === 'running' || slug === 'walking' || slug === 'skiing'
}

/** Format speed (km/h) as pace ``m:ss``. Returns null if speed is too low. */
export function formatPace(speedKmh) {
  const speed = Number(speedKmh)
  if (!Number.isFinite(speed) || speed < 0.5) return null
  const totalSec = Math.max(0, Math.round(3600 / speed))
  const minutes = Math.floor(totalSec / 60)
  const seconds = totalSec % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}
