/**
 * src/pages/Login.jsx
 *
 * Combined Login + Register page.
 * Uses AuthContext to persist token and redirect on success.
 */

import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { useAuth } from '../context/AuthContext'

// ── Validation helpers ─────────────────────────────────────────────────────────

function validateUsername(value) {
  if (!value.trim()) return 'Username is required.'
  if (value.length < 3) return 'Username must be at least 3 characters.'
  if (value.length > 50) return 'Username must be 50 characters or fewer.'
  if (!/^[A-Za-z0-9_-]+$/.test(value)) return 'Only letters, numbers, hyphens, and underscores allowed.'
  return ''
}

function validatePassword(value) {
  if (!value) return 'Password is required.'
  if (value.length < 6) return 'Password must be at least 6 characters.'
  return ''
}

// ── Reusable field component ───────────────────────────────────────────────────

function Field({ label, id, type = 'text', value, onChange, error, placeholder, autoComplete }) {
  return (
    <div className="form-group" style={{ marginBottom: '1.25rem' }}>
      <label className="form-label" htmlFor={id}>{label}</label>
      <input
        id={id}
        className="form-input"
        type={type}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        autoComplete={autoComplete}
        style={{
          border: error ? '1.5px solid var(--rose)' : undefined,
          transition: 'border-color 0.2s',
        }}
      />
      {error && (
        <p style={{
          color: 'var(--rose)',
          fontSize: '0.78rem',
          marginTop: '0.35rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.3rem',
        }}>
          ⚠ {error}
        </p>
      )}
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function Login() {
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const returnTo = location.state?.from || '/input'

  const [mode, setMode] = useState('login')   // 'login' | 'register'
  const [form, setForm] = useState({ username: '', password: '' })
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(false)

  const set = (field, value) => {
    setForm(prev => ({ ...prev, [field]: value }))
    // Clear error on change
    if (errors[field]) setErrors(prev => ({ ...prev, [field]: '' }))
  }

  const validate = () => {
    const next = {
      username: validateUsername(form.username),
      password: validatePassword(form.password),
    }
    setErrors(next)
    return !next.username && !next.password
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return

    setLoading(true)
    try {
      if (mode === 'login') {
        await login(form.username, form.password)
        toast.success(`Welcome back, ${form.username}!`)
      } else {
        await register(form.username, form.password)
        toast.success(`Account created! Welcome, ${form.username}.`)
      }
      navigate(returnTo, { replace: true })
    } catch (err) {
      const detail = err.response?.data?.detail
      if (typeof detail === 'string') {
        toast.error(detail)
      } else {
        toast.error(mode === 'login' ? 'Incorrect username or password.' : 'Registration failed.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--bg-base)',
      padding: '2rem',
    }}>
      <div style={{
        width: '100%',
        maxWidth: '420px',
      }}>

        {/* Logo / Brand */}
        <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
          <div style={{
            width: '56px',
            height: '56px',
            borderRadius: '14px',
            background: 'linear-gradient(135deg, var(--cyan), var(--violet))',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '1.5rem',
            margin: '0 auto 1rem',
            boxShadow: '0 8px 32px rgba(34,211,238,0.25)',
          }}>
            🛡️
          </div>
          <h1 style={{
            fontSize: '1.5rem',
            fontWeight: 700,
            color: 'var(--text-primary)',
            marginBottom: '0.35rem',
          }}>
            Cloud Risk Intelligence
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            {mode === 'login' ? 'Sign in to your account' : 'Create a new account'}
          </p>
        </div>

        {/* Card */}
        <div className="card" style={{ padding: '2rem' }}>

          {/* Mode toggle tabs */}
          <div style={{
            display: 'flex',
            background: 'var(--bg-input)',
            borderRadius: 'var(--radius-sm)',
            padding: '4px',
            marginBottom: '1.75rem',
          }}>
            {['login', 'register'].map(m => (
              <button
                key={m}
                type="button"
                onClick={() => { setMode(m); setErrors({}) }}
                style={{
                  flex: 1,
                  padding: '0.5rem',
                  borderRadius: 'calc(var(--radius-sm) - 2px)',
                  border: 'none',
                  cursor: 'pointer',
                  fontWeight: 600,
                  fontSize: '0.875rem',
                  transition: 'all 0.2s',
                  background: mode === m ? 'var(--bg-card)' : 'transparent',
                  color: mode === m ? 'var(--cyan)' : 'var(--text-muted)',
                  boxShadow: mode === m ? '0 1px 6px rgba(0,0,0,0.15)' : 'none',
                }}
              >
                {m === 'login' ? 'Sign In' : 'Register'}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} noValidate>
            <Field
              id="auth-username"
              label="Username"
              value={form.username}
              onChange={e => set('username', e.target.value)}
              error={errors.username}
              placeholder="your_username"
              autoComplete="username"
            />
            <Field
              id="auth-password"
              label="Password"
              type="password"
              value={form.password}
              onChange={e => set('password', e.target.value)}
              error={errors.password}
              placeholder={mode === 'login' ? '••••••••' : 'min. 6 characters'}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            />

            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading}
              style={{ width: '100%', padding: '0.8rem', marginTop: '0.5rem', fontSize: '0.95rem' }}
            >
              {loading
                ? (mode === 'login' ? 'Signing in…' : 'Creating account…')
                : (mode === 'login' ? 'Sign In' : 'Create Account')
              }
            </button>
          </form>

          {mode === 'login' && (
            <p style={{
              textAlign: 'center',
              marginTop: '1.25rem',
              color: 'var(--text-muted)',
              fontSize: '0.82rem',
            }}>
              No account yet?{' '}
              <button
                type="button"
                onClick={() => { setMode('register'); setErrors({}) }}
                style={{
                  background: 'none', border: 'none',
                  color: 'var(--cyan)', cursor: 'pointer',
                  fontWeight: 600, fontSize: 'inherit',
                  padding: 0,
                }}
              >
                Register here
              </button>
            </p>
          )}
        </div>

        {/* Demo hint */}
        <p style={{
          textAlign: 'center',
          marginTop: '1.25rem',
          color: 'var(--text-muted)',
          fontSize: '0.78rem',
        }}>
          First time? Register a new account to get started.
        </p>
      </div>
    </div>
  )
}
