import { initialFrom } from '../lib/format'

export default function Avatar({ person, className = 'h-10 w-10 text-sm' }) {
  const name = person?.display_name || person?.email || '?'
  const url = person?.photo_url || person?.avatar_url
  return (
    <span className={`avatar ${className}`}>
      {url ? <img src={url} alt="" /> : initialFrom(name)}
    </span>
  )
}
