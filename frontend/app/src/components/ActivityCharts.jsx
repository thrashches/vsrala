import { useEffect, useRef } from 'react'
import {
  Chart,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  Filler,
  Legend,
  Tooltip,
} from 'chart.js'
import { getRelativePosition } from 'chart.js/helpers'

Chart.register(LineController, LineElement, PointElement, LinearScale, Filler, Legend, Tooltip)

function formatValue(v) {
  if (v == null || Number.isNaN(v)) return ''
  return Math.round(v * 10) / 10 === Math.round(v)
    ? String(Math.round(v))
    : String(Math.round(v * 10) / 10)
}

function toPoints(values, times) {
  const out = []
  const arr = values || []
  for (let i = 0; i < arr.length; i++) {
    const y = arr[i]
    if (y === null || y === undefined) continue
    const x = times && times[i] != null ? Number(times[i]) : i
    out.push({ x, y })
  }
  return out
}

function stats(points) {
  let maxPt = null
  let sum = 0
  for (const p of points) {
    sum += p.y
    if (!maxPt || p.y > maxPt.y) maxPt = p
  }
  return { max: maxPt, avg: points.length ? sum / points.length : 0 }
}

function xExtent(datasets) {
  let min = Infinity
  let max = -Infinity
  datasets.forEach((pts) => {
    for (const p of pts) {
      if (p.x < min) min = p.x
      if (p.x > max) max = p.x
    }
  })
  if (!Number.isFinite(min)) min = 0
  if (!Number.isFinite(max) || max <= min) max = min + 1
  return { min, max }
}

function yExtent(points) {
  let min = Infinity
  let max = -Infinity
  for (const p of points) {
    if (p.y < min) min = p.y
    if (p.y > max) max = p.y
  }
  if (!Number.isFinite(min)) return { min: 0, max: 1 }
  if (max <= min) return { min: min - 1, max: max + 1 }
  const pad = (max - min) * 0.08
  return { min: min - pad, max: max + pad }
}

function valueAtTime(points, t) {
  if (!points?.length || t == null) return null
  if (t <= points[0].x) return points[0].y
  if (t >= points[points.length - 1].x) return points[points.length - 1].y
  let lo = 0
  let hi = points.length - 1
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (points[mid].x <= t) lo = mid
    else hi = mid
  }
  const a = points[lo]
  const b = points[hi]
  if (b.x === a.x) return a.y
  const k = (t - a.x) / (b.x - a.x)
  return a.y + (b.y - a.y) * k
}

function drawValueBadge(ctx, x, y, text, color, area) {
  ctx.save()
  ctx.font = '600 11px system-ui, sans-serif'
  const padX = 6
  const padY = 3
  const tw = ctx.measureText(text).width
  const bw = tw + padX * 2
  const bh = 16
  let bx = x + 10
  let by = y - bh / 2
  if (bx + bw > area.right - 2) bx = x - 10 - bw
  if (by < area.top + 2) by = area.top + 2
  if (by + bh > area.bottom - 2) by = area.bottom - 2 - bh
  ctx.beginPath()
  if (ctx.roundRect) ctx.roundRect(bx, by, bw, bh, 3)
  else ctx.rect(bx, by, bw, bh)
  ctx.fillStyle = color
  ctx.fill()
  ctx.fillStyle = '#fff'
  ctx.textAlign = 'left'
  ctx.textBaseline = 'middle'
  ctx.fillText(text, bx + padX, by + bh / 2)
  ctx.restore()
}

function createOverlaysPlugin(getSyncTime) {
  return {
    id: 'chartOverlays',
    afterDatasetsDraw(chart) {
      const ctx = chart.ctx
      const area = chart.chartArea
      const xScale = chart.scales.x
      const yScale = chart.scales.y
      if (!area || !xScale || !yScale) return

      const opts = chart.options.plugins?.chartOverlays || {}
      const avg = opts.avg
      const color = opts.color || '#333'
      const series = opts.series || chart.data.datasets[0]?.data || []

      if (avg != null) {
        const avgY = yScale.getPixelForValue(avg)
        if (avgY >= area.top && avgY <= area.bottom) {
          ctx.save()
          ctx.font = '11px system-ui, sans-serif'
          ctx.fillStyle = 'rgba(28, 28, 30, 0.55)'
          ctx.textAlign = 'right'
          ctx.textBaseline = 'bottom'
          ctx.fillText(`ср. ${formatValue(avg)}`, area.right - 4, avgY - 2)
          ctx.restore()
        }
      }

      const syncTime = getSyncTime()
      if (syncTime === null) return
      const x = xScale.getPixelForValue(syncTime)
      if (x < area.left || x > area.right) return

      ctx.save()
      ctx.beginPath()
      ctx.moveTo(x, area.top)
      ctx.lineTo(x, area.bottom)
      ctx.lineWidth = 1
      ctx.strokeStyle = 'rgba(28, 28, 30, 0.55)'
      ctx.stroke()
      ctx.restore()

      const value = valueAtTime(series, syncTime)
      if (value == null) return
      const py = yScale.getPixelForValue(value)
      if (py < area.top || py > area.bottom) return

      ctx.save()
      ctx.beginPath()
      ctx.arc(x, py, 4.5, 0, Math.PI * 2)
      ctx.fillStyle = color
      ctx.fill()
      ctx.lineWidth = 2
      ctx.strokeStyle = '#fff'
      ctx.stroke()
      ctx.restore()

      drawValueBadge(ctx, x, py, formatValue(value), color, area)
    },
  }
}

function elevationDataset(eleData) {
  return {
    label: 'Высота',
    data: eleData,
    borderColor: 'rgba(120, 120, 128, 0.35)',
    backgroundColor: 'rgba(120, 120, 128, 0.18)',
    borderWidth: 1,
    pointRadius: 0,
    pointHoverRadius: 0,
    tension: 0.15,
    fill: true,
    spanGaps: true,
    parsing: false,
    yAxisID: 'yEle',
    order: 0,
  }
}

function makeChart(canvas, label, data, color, xRange, eleData, getSyncTime) {
  if (!canvas || !data.length) return null
  const s = stats(data)
  const hasEle = eleData && eleData.length > 0
  const eleRange = hasEle ? yExtent(eleData) : null
  const datasets = []
  if (hasEle) datasets.push(elevationDataset(eleData))

  datasets.push(
    {
      label,
      data,
      borderColor: color,
      backgroundColor: `${color}22`,
      borderWidth: 1.5,
      pointRadius: 0,
      pointHoverRadius: 0,
      tension: 0,
      fill: !hasEle,
      spanGaps: false,
      parsing: false,
      yAxisID: 'y',
      order: 3,
    },
    {
      label: 'Среднее',
      data: [
        { x: xRange.min, y: s.avg },
        { x: xRange.max, y: s.avg },
      ],
      borderColor: 'rgba(28, 28, 30, 0.4)',
      borderWidth: 1.25,
      borderDash: [6, 4],
      pointRadius: 0,
      pointHoverRadius: 0,
      tension: 0,
      fill: false,
      parsing: false,
      yAxisID: 'y',
      order: 2,
    },
  )

  if (s.max) {
    datasets.push({
      label: 'Максимум',
      data: [s.max],
      borderColor: color,
      backgroundColor: color,
      pointRadius: 5,
      pointHoverRadius: 6,
      pointBorderColor: '#fff',
      pointBorderWidth: 2,
      showLine: false,
      parsing: false,
      yAxisID: 'y',
      order: 4,
    })
  }

  const scales = {
    x: {
      type: 'linear',
      min: xRange.min,
      max: xRange.max,
      display: false,
    },
    y: {
      type: 'linear',
      ...yExtent(data),
      ticks: { maxTicksLimit: 4 },
      title: { display: false },
      grid: { color: 'rgba(0,0,0,0.06)' },
    },
  }
  if (hasEle) {
    scales.yEle = {
      type: 'linear',
      position: 'right',
      min: eleRange.min,
      max: eleRange.max,
      display: false,
      grid: { drawOnChartArea: false },
    }
  }

  return new Chart(canvas, {
    type: 'line',
    data: { datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      normalized: true,
      parsing: false,
      interaction: { mode: 'nearest', axis: 'x', intersect: false },
      plugins: {
        legend: { display: false },
        chartOverlays: { avg: s.avg, color, series: data },
        tooltip: { enabled: false },
      },
      scales,
    },
    plugins: [createOverlaysPlugin(getSyncTime)],
  })
}

const SPECS = [
  { key: 'speed', title: 'Скорость', color: '#FC5200', withEleBg: true },
  { key: 'hr', title: 'Пульс', color: '#E8192E', withEleBg: true },
  { key: 'power', title: 'Мощность', color: '#007FB6', withEleBg: true },
  { key: 'ele', title: 'Высота', color: '#6d6d78', withEleBg: false },
]

export default function ActivityCharts({ streams, durationSec = 0, onHoverTime }) {
  const rootRef = useRef(null)
  const chartsRef = useRef([])
  const syncTimeRef = useRef(null)
  const rafRef = useRef(null)
  const onHoverTimeRef = useRef(onHoverTime)
  onHoverTimeRef.current = onHoverTime

  useEffect(() => {
    if (!rootRef.current || !streams) return undefined

    let times = streams.time || null
    if (!times?.length) {
      const n = Math.max(
        (streams.speed || []).length,
        (streams.hr || []).length,
        (streams.power || []).length,
        (streams.ele || []).length,
      )
      const span = durationSec > 0 ? durationSec : Math.max(n - 1, 1)
      times = []
      for (let i = 0; i < n; i++) {
        times.push(n > 1 ? (i / (n - 1)) * span : 0)
      }
    }

    const speed = toPoints(streams.speed, times)
    const hr = toPoints(streams.hr, times)
    const power = toPoints(streams.power, times)
    const ele = toPoints(streams.ele, times)
    const byKey = { speed, hr, power, ele }
    const range = xExtent([speed, hr, power, ele])
    if (durationSec > range.max) range.max = durationSec

    const getSyncTime = () => syncTimeRef.current
    const scheduleRedraw = () => {
      if (rafRef.current != null) return
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = null
        chartsRef.current.forEach((c) => c.draw())
      })
    }

    const setSyncTime = (t) => {
      if (syncTimeRef.current === t) return
      syncTimeRef.current = t
      scheduleRedraw()
      onHoverTimeRef.current?.(t)
    }

    const charts = []
    const cleanups = []

    SPECS.forEach((spec) => {
      const panel = rootRef.current.querySelector(`[data-chart-panel="${spec.key}"]`)
      const canvas = panel?.querySelector('canvas')
      const data = byKey[spec.key]
      if (!data.length) {
        panel?.classList.add('hidden')
        return
      }
      panel?.classList.remove('hidden')
      const bgEle = spec.withEleBg ? ele : null
      const chart = makeChart(canvas, spec.title, data, spec.color, range, bgEle, getSyncTime)
      if (!chart) return
      charts.push(chart)

      const onMove = (evt) => {
        const pos = getRelativePosition(evt, chart)
        const area = chart.chartArea
        if (!area) return
        const px = Math.min(area.right, Math.max(area.left, pos.x))
        setSyncTime(chart.scales.x.getValueForPixel(px))
      }
      const onLeave = () => setSyncTime(null)
      canvas.addEventListener('mousemove', onMove)
      canvas.addEventListener('mouseleave', onLeave)
      cleanups.push(() => {
        canvas.removeEventListener('mousemove', onMove)
        canvas.removeEventListener('mouseleave', onLeave)
      })
    })

    chartsRef.current = charts

    return () => {
      cleanups.forEach((fn) => fn())
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current)
      charts.forEach((c) => c.destroy())
      chartsRef.current = []
      syncTimeRef.current = null
      onHoverTimeRef.current?.(null)
    }
  }, [streams, durationSec])

  const hasAny =
    streams &&
    (streams.speed?.length || streams.hr?.length || streams.power?.length || streams.ele?.length)

  if (!hasAny) return null

  return (
    <div ref={rootRef} className="space-y-4 border-t border-gray-100 px-5 py-5">
      {SPECS.map((spec) => (
        <div key={spec.key} data-chart-panel={spec.key}>
          <h3 className="mb-2 text-sm font-semibold text-ink">{spec.title}</h3>
          <div className="h-36">
            <canvas />
          </div>
        </div>
      ))}
    </div>
  )
}
