import { useEffect, useRef, useState } from 'react'
import { activitiesApi } from '../api/endpoints'

const DEFAULT_CHOICES = [
  { emoji: '👍', label: 'Лайк' },
  { emoji: '🔥', label: 'Огонёк' },
  { emoji: '👏', label: 'Аплодисменты' },
  { emoji: '🍆', label: 'Баклажан' },
  { emoji: '🍌', label: 'Банан' },
  { emoji: '❤️', label: 'Сердечко' },
]

export default function Reactions({
  activityId,
  counts = [],
  mine = null,
  choices = DEFAULT_CHOICES,
  onChange,
}) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const wrapRef = useRef(null)
  const options = choices?.length ? choices : DEFAULT_CHOICES

  useEffect(() => {
    if (!open) return undefined
    function onDocClick(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [open])

  useEffect(() => {
    if (mine) setOpen(false)
  }, [mine])

  async function toggle(emoji) {
    if (busy) return
    setBusy(true)
    try {
      const data = await activitiesApi.react(activityId, emoji)
      onChange?.(data)
      setOpen(false)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="activity-reactions flex flex-wrap items-center gap-2">
      <div className="flex flex-wrap items-center gap-1.5">
        {counts.map((c) => (
          <button
            key={c.emoji}
            type="button"
            className={`reaction-chip ${mine === c.emoji ? 'is-mine' : ''}`}
            onClick={() => toggle(c.emoji)}
            disabled={busy}
            aria-pressed={mine === c.emoji}
          >
            <span>{c.emoji}</span>
            <span className="text-xs font-semibold text-ink-muted">{c.count}</span>
          </button>
        ))}
      </div>
      {!mine && (
        <div ref={wrapRef} className="relative z-[1100]">
          <button
            type="button"
            className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-gray-200 bg-white text-ink-muted transition hover:border-brand hover:bg-gray-50 hover:text-brand"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-haspopup="true"
            aria-label="Добавить реакцию"
            title="Реакция"
          >
            <span className="material-icons text-base leading-none" aria-hidden="true">
              thumb_up
            </span>
          </button>
          {open && (
            <div className="absolute bottom-full left-0 z-[1100] mb-2 flex gap-1 rounded-lg border border-gray-200 bg-white p-1.5 shadow-card">
              {options.map((c) => (
                <button
                  key={c.emoji}
                  type="button"
                  title={c.label}
                  aria-label={c.label}
                  className="flex h-9 w-9 items-center justify-center rounded-md text-xl leading-none transition hover:bg-gray-100"
                  onClick={() => toggle(c.emoji)}
                  disabled={busy}
                >
                  {c.emoji}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
