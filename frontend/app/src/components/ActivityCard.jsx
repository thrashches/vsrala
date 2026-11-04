import { Link } from 'react-router-dom'
import { formatDateTime } from '../lib/format'
import ActivitySource from './ActivitySource'
import ActivityTypeLabel from './ActivityTypeLabel'
import Avatar from './Avatar'
import Reactions from './Reactions'

export default function ActivityCard({ activity, onReactionChange }) {
  const preview =
    activity.map_preview_url ||
    activity.zone_timeline_url ||
    activity.medias?.[0]?.url

  return (
    <article className="relative rounded bg-white shadow-card">
      <div className="flex items-start gap-3 px-4 pt-4">
        <Link to={`/people/${activity.profile.id}/`}>
          <Avatar person={activity.profile} />
        </Link>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold text-ink">
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
        </div>
      </div>

      <div className="px-4 pt-3">
        <h2 className="text-lg font-bold">
          <Link to={`/activities/${activity.id}/`} className="hover:text-brand">
            {activity.title}
          </Link>
        </h2>
        {activity.description && (
          <p className="mt-1 line-clamp-2 text-sm text-ink-muted">{activity.description}</p>
        )}
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2 px-4 sm:grid-cols-4">
        <div>
          <div className="stat-label">Дистанция</div>
          <div className="text-lg font-bold">
            {activity.distance ?? '—'}{' '}
            <span className="text-xs font-normal text-ink-muted">км</span>
          </div>
        </div>
        <div>
          <div className="stat-label">Время</div>
          <div className="text-lg font-bold">{activity.duration_display || '—'}</div>
        </div>
        {activity.avg_speed != null && (
          <div>
            <div className="stat-label">Ср. скорость</div>
            <div className="text-lg font-bold">
              {activity.avg_speed} <span className="text-xs font-normal text-ink-muted">км/ч</span>
            </div>
          </div>
        )}
        {activity.avg_hr != null ? (
          <div>
            <div className="stat-label">Пульс</div>
            <div className="text-lg font-bold">
              {activity.avg_hr} <span className="text-xs font-normal text-ink-muted">уд/мин</span>
            </div>
          </div>
        ) : activity.avg_power != null ? (
          <div>
            <div className="stat-label">Мощность</div>
            <div className="text-lg font-bold">
              {activity.avg_power} <span className="text-xs font-normal text-ink-muted">Вт</span>
            </div>
          </div>
        ) : null}
      </div>

      {preview && (
        <div className="relative z-0 mt-4 overflow-hidden">
          <Link to={`/activities/${activity.id}/`} className="block">
            <img
              src={preview}
              alt=""
              loading="lazy"
              decoding="async"
              className="h-52 w-full bg-feed object-cover"
            />
          </Link>
        </div>
      )}

      <div className="relative z-10 flex flex-wrap items-center gap-3 border-t border-gray-100 px-4 py-3 text-sm text-ink-muted">
        <Reactions
          activityId={activity.id}
          counts={activity.reaction_counts || []}
          mine={activity.my_reaction}
          onChange={onReactionChange}
        />
        <Link
          to={`/activities/${activity.id}/#comments`}
          className="activity-comments-btn ml-auto"
          title="Комментарии"
        >
          <span className="material-icons text-base leading-none" aria-hidden="true">
            chat_bubble_outline
          </span>
          <span className="text-xs font-semibold tabular-nums">{activity.comment_count || 0}</span>
        </Link>
      </div>
    </article>
  )
}
