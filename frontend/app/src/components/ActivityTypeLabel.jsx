import { activityTypeIcon } from '../lib/activityTypeIcons'

export default function ActivityTypeLabel({ activityType, className = '' }) {
  if (!activityType?.name) return null
  const icon = activityTypeIcon(activityType.slug)
  return (
    <span className={`inline-flex items-center gap-0.5 ${className}`.trim()}>
      <span className="material-icons text-[14px] leading-none" aria-hidden="true">
        {icon}
      </span>
      <span>{activityType.name}</span>
    </span>
  )
}
