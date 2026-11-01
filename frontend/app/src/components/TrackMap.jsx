import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import L from 'leaflet'

export const SURFACE_COLORS = {
  asphalt: '#FC5200',
  concrete: '#ea580c',
  paving_stones: '#f59e0b',
  gravel: '#a16207',
  dirt: '#78716c',
  grass: '#16a34a',
  tartan: '#dc2626',
  unknown: '#9ca3af',
}

function latLngAtTime(points, t) {
  if (!points.length || t == null) return null
  if (t <= points[0].t) return [points[0].lat, points[0].lon]
  if (t >= points[points.length - 1].t) {
    const last = points[points.length - 1]
    return [last.lat, last.lon]
  }
  let lo = 0
  let hi = points.length - 1
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (points[mid].t <= t) lo = mid
    else hi = mid
  }
  const a = points[lo]
  const b = points[hi]
  if (b.t === a.t) return [a.lat, a.lon]
  const k = (t - a.t) / (b.t - a.t)
  return [a.lat + (b.lat - a.lat) * k, a.lon + (b.lon - a.lon) * k]
}

function normalizePoints(raw, durationSec) {
  const points = raw.map((p, i) => ({
    lat: p[0],
    lon: p[1],
    t: p.length > 2 && p[2] != null ? Number(p[2]) : null,
    i,
  }))
  const missing = points.some((p) => p.t == null || Number.isNaN(p.t))
  if (missing) {
    const span = durationSec > 0 ? durationSec : Math.max(points.length - 1, 1)
    points.forEach((p, i) => {
      if (p.t == null || Number.isNaN(p.t)) {
        p.t = points.length > 1 ? (i / (points.length - 1)) * span : 0
      }
    })
  }
  return points
}

const TrackMap = forwardRef(function TrackMap(
  {
    points,
    durationSec = 0,
    interactive = true,
    className = 'h-[420px] w-full bg-gray-100',
    highlightRange = null,
    segments = null,
    surfaceColors = null,
  },
  ref,
) {
  const elRef = useRef(null)
  const mapRef = useRef(null)
  const cursorRef = useRef(null)
  const timedRef = useRef([])

  useImperativeHandle(ref, () => ({
    setTime(t) {
      const cursor = cursorRef.current
      const timed = timedRef.current
      if (!cursor || !timed.length) return
      if (t == null) {
        cursor.setStyle({ opacity: 0, fillOpacity: 0 })
        return
      }
      const ll = latLngAtTime(timed, t)
      if (!ll) return
      cursor.setLatLng(ll)
      cursor.setStyle({ opacity: 1, fillOpacity: 1 })
    },
  }))

  useEffect(() => {
    if (!elRef.current || !points?.length) return undefined

    const timed = normalizePoints(points, durationSec)
    timedRef.current = timed

    const map = L.map(elRef.current, {
      zoomControl: interactive,
      dragging: interactive,
      scrollWheelZoom: interactive,
      doubleClickZoom: interactive,
      boxZoom: interactive,
      keyboard: interactive,
      attributionControl: interactive,
    })
    mapRef.current = map

    if (interactive && map.attributionControl) {
      map.attributionControl.setPrefix(false)
    }

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      referrerPolicy: 'strict-origin-when-cross-origin',
      attribution: interactive
        ? '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        : '',
    }).addTo(map)

    const latlngs = timed.map((p) => [p.lat, p.lon])
    map.fitBounds(L.latLngBounds(latlngs), { padding: [16, 16] })

    const colors = { ...SURFACE_COLORS, ...(surfaceColors || {}) }
    const lineWeight = interactive ? 4 : 3

    if (segments?.length) {
      segments.forEach((seg) => {
        const start = Math.max(0, Number(seg.start_idx) || 0)
        const end = Math.min(latlngs.length - 1, Number(seg.end_idx) || 0)
        if (end < start) return
        const slice = latlngs.slice(start, end + 1)
        if (slice.length < 2) return
        const color = colors[seg.surface] || colors.unknown
        L.polyline(slice, { color, weight: lineWeight, opacity: 0.95 }).addTo(map)
      })
    } else {
      L.polyline(latlngs, {
        color: '#FC5200',
        weight: lineWeight,
        opacity: 0.95,
      }).addTo(map)
    }

    if (highlightRange && highlightRange.length === 2) {
      const [a, b] = highlightRange
      const slice = latlngs.slice(a, b + 1)
      if (slice.length) {
        L.polyline(slice, { color: '#2563eb', weight: 5 }).addTo(map)
      }
    }

    const markerR = interactive ? 7 : 5
    L.circleMarker(latlngs[0], {
      radius: markerR,
      color: '#fff',
      weight: 2,
      fillColor: '#22c55e',
      fillOpacity: 1,
      opacity: 1,
      interactive: false,
    }).addTo(map)

    if (latlngs.length > 1) {
      L.circleMarker(latlngs[latlngs.length - 1], {
        radius: markerR,
        color: '#fff',
        weight: 2,
        fillColor: '#1c1c1e',
        fillOpacity: 1,
        opacity: 1,
        interactive: false,
      }).addTo(map)
    }

    if (interactive) {
      const cursor = L.circleMarker(latlngs[0], {
        radius: 7,
        color: '#fff',
        weight: 2,
        fillColor: '#FC5200',
        fillOpacity: 1,
        opacity: 0,
      }).addTo(map)
      cursor.setStyle({ fillOpacity: 0 })
      cursorRef.current = cursor
    }

    const timer = setTimeout(() => map.invalidateSize(), 100)

    return () => {
      clearTimeout(timer)
      cursorRef.current = null
      timedRef.current = []
      map.remove()
      mapRef.current = null
    }
  }, [points, durationSec, interactive, highlightRange, segments, surfaceColors])

  if (!points?.length) return null
  return <div ref={elRef} className={className} />
})

export default TrackMap
