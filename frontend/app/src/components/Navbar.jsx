import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/AuthContext'
import Avatar from './Avatar'

const navClass = ({ isActive }) =>
  `rounded px-3 py-2 text-sm font-semibold ${isActive ? 'bg-gray-100 text-ink' : 'text-ink hover:bg-gray-100'}`

export default function Navbar() {
  const { user, logout, pendingRequests } = useAuth()
  const [open, setOpen] = useState(false)
  const menuRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    function onDocClick(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('click', onDocClick)
    return () => document.removeEventListener('click', onDocClick)
  }, [])

  if (!user) return null

  async function handleLogout() {
    await logout()
    navigate('/login/')
  }

  return (
    <header className="sticky top-0 z-[1100] border-b border-gray-200 bg-white">
      <nav className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-2">
        <div className="flex items-center gap-6">
          <Link to="/feed/" className="flex shrink-0 items-center">
            <img src="/logo.svg" alt="VSRALA" className="h-7 w-auto" />
          </Link>
          <div className="hidden items-center gap-1 sm:flex">
            <NavLink to="/feed/" className={navClass} end>
              Лента
            </NavLink>
            <NavLink to="/people/" className={navClass}>
              Люди
            </NavLink>
            <NavLink to="/activities/my/" className={navClass}>
              Мои тренировки
            </NavLink>
            <NavLink to="/routes/" className={navClass}>
              Маршруты
            </NavLink>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/people/requests/"
            className="relative inline-flex h-10 w-10 items-center justify-center rounded-full text-ink transition hover:bg-gray-100"
            title="Запросы"
            aria-label="Запросы"
          >
            <span className="material-icons text-[22px] leading-none" aria-hidden="true">
              group
            </span>
            {pendingRequests > 0 && (
              <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-red-500" aria-hidden="true" />
            )}
          </Link>
          <Link
            to="/activities/upload/"
            className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-brand text-white transition hover:bg-brand-dark"
            title="Загрузить"
            aria-label="Загрузить"
          >
            <span className="material-icons text-[20px] leading-none" aria-hidden="true">
              add
            </span>
          </Link>
          <div className="relative" ref={menuRef}>
            <button
              type="button"
              className="flex items-center gap-1 rounded-full py-0.5 pl-0.5 pr-1.5 transition hover:bg-gray-100"
              aria-expanded={open}
              aria-haspopup="true"
              onClick={() => setOpen((v) => !v)}
            >
              <Avatar person={user} />
              <span className="material-icons text-base leading-none text-ink-muted" aria-hidden="true">
                expand_more
              </span>
            </button>
            {open && (
              <div
                className="absolute right-0 mt-2 w-44 overflow-hidden rounded border border-gray-200 bg-white py-1 shadow-card"
                role="menu"
              >
                <Link
                  to={`/people/${user.id}/`}
                  className="block px-4 py-2 text-sm font-medium text-ink hover:bg-gray-50"
                  role="menuitem"
                  onClick={() => setOpen(false)}
                >
                  Профиль
                </Link>
                <Link
                  to="/settings/"
                  className="block px-4 py-2 text-sm font-medium text-ink hover:bg-gray-50"
                  role="menuitem"
                  onClick={() => setOpen(false)}
                >
                  Настройки
                </Link>
                <button
                  type="button"
                  className="block w-full px-4 py-2 text-left text-sm font-medium text-ink hover:bg-gray-50"
                  role="menuitem"
                  onClick={handleLogout}
                >
                  Выход
                </button>
              </div>
            )}
          </div>
        </div>
      </nav>
    </header>
  )
}
