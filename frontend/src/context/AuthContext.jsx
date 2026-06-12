import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { getCurrentUser, loginUser, registerUser } from '../api/client'

const AuthContext = createContext({
  token: null,
  user: null,
  loading: true,
  isAuthenticated: false,
  login: async () => {},
  register: async () => {},
  logout: () => {},
})

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('cloud_risk_token'))
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(Boolean(token))

  useEffect(() => {
    let cancelled = false
    if (!token) {
      setUser(null)
      setLoading(false)
      return
    }

    setLoading(true)
    getCurrentUser()
      .then((res) => {
        if (!cancelled) setUser(res.data)
      })
      .catch(() => {
        localStorage.removeItem('cloud_risk_token')
        if (!cancelled) {
          setToken(null)
          setUser(null)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [token])

  const value = useMemo(() => ({
    token,
    user,
    loading,
    isAuthenticated: Boolean(token),
    login: async (username, password) => {
      const res = await loginUser(username, password)
      localStorage.setItem('cloud_risk_token', res.data.access_token)
      setToken(res.data.access_token)
      return res.data
    },
    register: async (username, password) => {
      await registerUser(username, password)
      const res = await loginUser(username, password)
      localStorage.setItem('cloud_risk_token', res.data.access_token)
      setToken(res.data.access_token)
      return res.data
    },
    logout: () => {
      localStorage.removeItem('cloud_risk_token')
      setToken(null)
      setUser(null)
    },
  }), [token, user, loading])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  return useContext(AuthContext)
}
