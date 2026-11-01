import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../hooks/AuthContext'
import Navbar from './Navbar'

export default function ProtectedRoute() {
  const { token, user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-ink-muted">
        Загрузка…
      </div>
    )
  }

  if (!token || !user) {
    return <Navigate to="/login/" replace state={{ from: location }} />
  }

  return (
    <>
      <Navbar />
      <main>
        <Outlet />
      </main>
    </>
  )
}
