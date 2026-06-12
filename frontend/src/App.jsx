import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import Navbar from './components/Navbar'
import Home from './pages/Home'
import DataInput from './pages/DataInput'
import AllData from './pages/AllData'
import RiskAnalysis from './pages/RiskAnalysis'
import GraphDashboard from './pages/GraphDashboard'
import ChatBot from './pages/ChatBot'
import AdminConfig from './pages/AdminConfig'
import Login from './pages/Login'
import ErrorBoundary from './components/ErrorBoundary'
import { useAuth } from './context/AuthContext'

const withBoundary = (component) => (
  <ErrorBoundary>{component}</ErrorBoundary>
)

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return <div className="card">Checking your session...</div>
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  return children
}

const protectedPage = (component) => withBoundary(
  <ProtectedRoute>{component}</ProtectedRoute>
)

export default function App() {
  return (
    <div className="app-shell">
      <Navbar />
      <main className="page-content">
        <Routes>
          <Route path="/"         element={withBoundary(<Home />)} />
          <Route path="/input"    element={protectedPage(<DataInput />)} />
          <Route path="/all-data" element={protectedPage(<AllData />)} />
          <Route path="/graph"    element={protectedPage(<GraphDashboard />)} />
          <Route path="/risk"     element={protectedPage(<RiskAnalysis />)} />
          <Route path="/chat"     element={protectedPage(<ChatBot />)} />
          <Route path="/admin"    element={protectedPage(<AdminConfig />)} />
          <Route path="/login"    element={withBoundary(<Login />)} />

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}
