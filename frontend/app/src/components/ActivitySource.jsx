import { sourceIcon, sourceLabel } from '../lib/format'

export default function ActivitySource({ source }) {
  return (
    <span className="inline-flex items-center gap-1 align-middle" title={sourceLabel(source)}>
      <img src={sourceIcon(source)} alt="" className="inline h-3.5 w-3.5" />
      <span>{sourceLabel(source)}</span>
    </span>
  )
}
