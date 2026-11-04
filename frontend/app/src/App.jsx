import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import { AuthProvider } from './hooks/AuthContext'
import ActivityDetailPage from './pages/ActivityDetailPage'
import ActivityEditPage from './pages/ActivityEditPage'
import ActivityUploadPage from './pages/ActivityUploadPage'
import FeedPage from './pages/FeedPage'
import FollowRequestsPage from './pages/FollowRequestsPage'
import LoginPage from './pages/LoginPage'
import PeopleListPage from './pages/PeopleListPage'
import PeopleSearchPage from './pages/PeopleSearchPage'
import ProfilePage from './pages/ProfilePage'
import RouteDetailPage from './pages/RouteDetailPage'
import RouteEditPage from './pages/RouteEditPage'
import RouteFromActivityPage from './pages/RouteFromActivityPage'
import RouteUploadPage from './pages/RouteUploadPage'
import RoutesListPage from './pages/RoutesListPage'
import SettingsPage from './pages/SettingsPage'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login/" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/feed/" element={<FeedPage scope="feed" />} />
            <Route path="/activities/my/" element={<FeedPage scope="mine" />} />
            <Route path="/activities/upload/" element={<ActivityUploadPage />} />
            <Route path="/activities/:id/" element={<ActivityDetailPage />} />
            <Route path="/activities/:id/edit/" element={<ActivityEditPage />} />
            <Route path="/people/" element={<PeopleSearchPage />} />
            <Route path="/people/following/" element={<PeopleListPage mode="following" />} />
            <Route path="/people/followers/" element={<PeopleListPage mode="followers" />} />
            <Route path="/people/requests/" element={<FollowRequestsPage />} />
            <Route path="/people/:id/" element={<ProfilePage />} />
            <Route path="/people/:id/following/" element={<PeopleListPage mode="following" />} />
            <Route path="/people/:id/followers/" element={<PeopleListPage mode="followers" />} />
            <Route path="/routes/" element={<RoutesListPage />} />
            <Route path="/routes/upload/" element={<RouteUploadPage />} />
            <Route path="/routes/from-activity/:activityId/" element={<RouteFromActivityPage />} />
            <Route path="/routes/:id/" element={<RouteDetailPage />} />
            <Route path="/routes/:id/edit/" element={<RouteEditPage />} />
            <Route path="/settings/" element={<SettingsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/feed/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
