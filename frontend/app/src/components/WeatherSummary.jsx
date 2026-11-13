const CONDITION_ICONS = {
  clear: 'wb_sunny',
  cloud: 'cloud',
  rain: 'umbrella',
  snow: 'ac_unit',
}

/** Meteorological wind direction → where wind blows toward (arrow rotation). */
export function windArrowRotation(deg) {
  if (deg == null || Number.isNaN(Number(deg))) return 0
  // Material navigation icon points up (north); wind_direction is "from" degrees.
  // Arrow showing blow-to: rotate by deg + 180.
  return (Number(deg) + 180) % 360
}

export function weatherConditionIcon(condition) {
  return CONDITION_ICONS[condition] || 'cloud'
}

export default function WeatherSummary({ weather }) {
  if (!weather) return null
  const icon = weatherConditionIcon(weather.condition)
  const temp =
    weather.temperature_c != null && weather.temperature_c !== ''
      ? Math.round(Number(weather.temperature_c))
      : null
  const windSpeed =
    weather.wind_speed_kmh != null && weather.wind_speed_kmh !== ''
      ? Math.round(Number(weather.wind_speed_kmh))
      : null
  const windDeg = weather.wind_direction_deg

  return (
    <div
      className="mt-3 flex flex-wrap items-center gap-3 px-4 text-sm text-ink-muted"
      title="Погода во время тренировки"
    >
      <span className="inline-flex items-center gap-1">
        <span className="material-icons text-base leading-none text-ink" aria-hidden="true">
          {icon}
        </span>
        {temp != null ? (
          <span className="font-semibold tabular-nums text-ink">
            {temp}
            <span className="text-xs font-normal text-ink-muted"> °C</span>
          </span>
        ) : null}
      </span>
      {windSpeed != null ? (
        <span className="inline-flex items-center gap-0.5">
          <span
            className="material-icons text-base leading-none text-ink"
            aria-hidden="true"
            style={{ transform: `rotate(${windArrowRotation(windDeg)}deg)` }}
          >
            navigation
          </span>
          <span className="font-semibold tabular-nums text-ink">
            {windSpeed}
            <span className="text-xs font-normal text-ink-muted"> км/ч</span>
          </span>
        </span>
      ) : null}
    </div>
  )
}
