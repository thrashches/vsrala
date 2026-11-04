import { useEffect, useRef } from 'react'
import {
  Chart,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  Filler,
  Tooltip,
} from 'chart.js'

let registered = false
function ensureChartJs() {
  if (registered) return
  Chart.register(LineController, LineElement, PointElement, LinearScale, Filler, Tooltip)
  registered = true
}

const MONTHS_RU_SHORT = [
  '', 'янв.', 'фев.', 'мар.', 'апр.', 'мая', 'июн.',
  'июл.', 'авг.', 'сен.', 'окт.', 'ноя.', 'дек.',
]

function formatTickDate(iso) {
  if (!iso) return ''
  const parts = String(iso).split('-')
  if (parts.length < 3) return String(iso)
  const day = String(Number(parts[2])).padStart(2, '0')
  const month = MONTHS_RU_SHORT[Number(parts[1])] || ''
  return month ? `${day} ${month}` : String(iso)
}

function formatTooltipValue(v, unit) {
  if (v == null || !Number.isFinite(Number(v))) return ''
  const n = Number(v)
  const text = Number.isInteger(n) ? String(n) : String(Math.round(n * 10) / 10)
  return unit ? `${text} ${unit}` : text
}

export default function MetricHistoryChart({ title, unit, series, color = '#e85d04' }) {
  const canvasRef = useRef(null)
  const chartRef = useRef(null)

  useEffect(() => {
    ensureChartJs()
    const canvas = canvasRef.current
    if (!canvas) return undefined

    if (chartRef.current) {
      chartRef.current.destroy()
      chartRef.current = null
    }

    const points = (series || [])
      .filter((p) => p && p.date != null && p.value != null && Number.isFinite(Number(p.value)))
      .map((p, i) => ({ i, date: String(p.date), y: Number(p.value) }))

    if (!points.length) return undefined

    chartRef.current = new Chart(canvas, {
      type: 'line',
      data: {
        datasets: [
          {
            data: points.map((p) => ({ x: p.i, y: p.y })),
            borderColor: color,
            backgroundColor: `${color}22`,
            borderWidth: 2,
            pointRadius: points.length > 40 ? 0 : 3,
            pointHoverRadius: 4,
            tension: 0.25,
            fill: true,
            parsing: false,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        parsing: false,
        interaction: { mode: 'nearest', axis: 'x', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: (items) => {
                const idx = items[0]?.parsed?.x
                const pt = Number.isFinite(idx) ? points[Math.round(idx)] : null
                return pt ? formatTickDate(pt.date) : ''
              },
              label: (item) => formatTooltipValue(item.parsed.y, unit),
            },
          },
        },
        scales: {
          x: {
            type: 'linear',
            min: 0,
            max: Math.max(points.length - 1, 1),
            ticks: {
              stepSize: 1,
              maxTicksLimit: 8,
              callback(value) {
                const idx = Math.round(Number(value))
                const pt = points[idx]
                return pt ? formatTickDate(pt.date) : ''
              },
            },
            grid: { display: false },
          },
          y: {
            type: 'linear',
            beginAtZero: false,
            ticks: {
              callback(value) {
                const n = Number(value)
                return Number.isFinite(n) ? String(n) : ''
              },
            },
            grid: { color: 'rgba(0,0,0,0.06)' },
          },
        },
      },
    })

    return () => {
      if (chartRef.current) {
        chartRef.current.destroy()
        chartRef.current = null
      }
    }
  }, [series, unit, color])

  const empty = !series?.length

  return (
    <div className="rounded bg-white p-4 shadow-card">
      <div className="mb-3 flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
        {unit && <span className="text-xs text-ink-muted">{unit}</span>}
      </div>
      {empty ? (
        <p className="py-10 text-center text-sm text-ink-muted">Нет данных</p>
      ) : (
        <div className="h-52">
          <canvas ref={canvasRef} />
        </div>
      )}
    </div>
  )
}
