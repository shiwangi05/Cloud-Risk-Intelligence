import { NavLink, useLocation } from 'react-router-dom'
import ThemeToggle from './ThemeToggle'
import { useAuth } from '../context/AuthContext'

export default function Navbar() {
  const { isAuthenticated, user, logout } = useAuth()
  const location = useLocation()
  const isHome = location.pathname === '/'
  const isLogin = location.pathname === '/login'

  return (
    <nav className="navbar">
      <NavLink to="/" className="navbar-logo">
        <div className="logo-icon">CR</div>
        Cloud<span className="brand">Risk</span>&nbsp;Intelligence
      </NavLink>

      <ul className="navbar-links">
        {(isAuthenticated || isLogin) && (
          <li><NavLink to="/" end className={({ isActive }) => isActive ? 'active' : ''}>Home</NavLink></li>
        )}
        {isAuthenticated && (
          <>
            <li><NavLink to="/input" className={({ isActive }) => isActive ? 'active' : ''}>Add Resources</NavLink></li>
            <li><NavLink to="/all-data" className={({ isActive }) => isActive ? 'active' : ''}>Data</NavLink></li>
            <li><NavLink to="/graph" className={({ isActive }) => isActive ? 'active' : ''}>Graph</NavLink></li>
            <li><NavLink to="/risk" className={({ isActive }) => isActive ? 'active' : ''}>Risk</NavLink></li>
            <li><NavLink to="/chat" className={({ isActive }) => isActive ? 'active' : ''}>Assistant</NavLink></li>
            <li><NavLink to="/admin" className={({ isActive }) => isActive ? 'active' : ''}>Scoring Settings</NavLink></li>
          </>
        )}
        {!isAuthenticated && !isHome && !isLogin && (
          <li><NavLink to="/login" className={({ isActive }) => isActive ? 'active' : ''}>Login</NavLink></li>
        )}
      </ul>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        {isAuthenticated ? (
          <button className="btn btn-secondary" type="button" onClick={logout}>
            {user?.username ? `Sign out ${user.username}` : 'Sign out'}
          </button>
        ) : !isHome && !isLogin ? (
          <NavLink to="/login" className="btn btn-primary">Login</NavLink>
        ) : null}
        <ThemeToggle />
      </div>
    </nav>
  )
}
