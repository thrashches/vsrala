import { NavLink } from 'react-router-dom'
import { useAuth } from '../hooks/AuthContext'

const TABS = [
  { to: '/people/', label: 'Поиск', end: true },
  { to: '/people/following/', label: 'Подписки' },
  { to: '/people/followers/', label: 'Подписчики' },
  { to: '/people/requests/', label: 'Запросы', badge: true },
]

export default function PeopleSectionNav() {
  const { pendingRequests } = useAuth()

  return (
    <div className="mt-4 flex flex-wrap gap-1">
      {TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.end}
          className={({ isActive }) =>
            `relative rounded px-3 py-1.5 text-sm font-semibold ${
              isActive ? 'bg-brand text-white' : 'bg-white text-ink shadow-card hover:bg-gray-50'
            }`
          }
        >
          {tab.label}
          {tab.badge && pendingRequests > 0 && (
            <span
              className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-red-500 ring-2 ring-white"
              aria-label="Есть новые запросы"
            />
          )}
        </NavLink>
      ))}
    </div>
  )
}
