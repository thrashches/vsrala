import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../hooks/AuthContext'
import Navbar from './Navbar'
import { AppShellSkeleton } from './skeletons'

export default function ProtectedRoute() {
  const { token, user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return <AppShellSkeleton />
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
