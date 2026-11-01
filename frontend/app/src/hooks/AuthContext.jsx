import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { authApi, meApi, peopleApi } from '../api/endpoints'
import { clearToken, getToken, setToken } from '../lib/authStorage'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setTokenState] = useState(() => getToken())
  const [user, setUser] = useState(null)
  const [pendingRequests, setPendingRequests] = useState(0)
  const [loading, setLoading] = useState(!!getToken())

  const refreshMe = useCallback(async () => {
    if (!getToken()) {
      setUser(null)
      setPendingRequests(0)
      setLoading(false)
      return null
    }
    try {
      const me = await meApi.get()
      setUser(me)
      try {
        const reqs = await peopleApi.requests()
        const list = Array.isArray(reqs) ? reqs : reqs.results || []
        setPendingRequests(list.length)
      } catch {
        setPendingRequests(0)
      }
      return me
    } catch {
      clearToken()
      setTokenState(null)
      setUser(null)
      setPendingRequests(0)
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (token) refreshMe()
    else {
      setUser(null)
      setLoading(false)
    }
  }, [token, refreshMe])

  const login = useCallback(async (email, password) => {
    const data = await authApi.login(email, password)
    setToken(data.token)
    setTokenState(data.token)
    setLoading(true)
    await refreshMe()
    return data
  }, [refreshMe])

  const logout = useCallback(async () => {
    try {
      if (getToken()) await authApi.logout()
    } catch {
      /* ignore */
    }
    clearToken()
    setTokenState(null)
    setUser(null)
    setPendingRequests(0)
  }, [])

  const value = useMemo(
    () => ({
      token,
      user,
      loading,
      pendingRequests,
      isAuthenticated: !!token && !!user,
      login,
      logout,
      refreshMe,
      setPendingRequests,
    }),
    [token, user, loading, pendingRequests, login, logout, refreshMe],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
