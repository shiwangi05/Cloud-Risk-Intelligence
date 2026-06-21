import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useState, useEffect } from 'react'
import api from '../api/client'

// ── Live stats fetched from the real API ───────────────────────────────────────
function useDashboardStats() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.get('/all-data?skip=0&limit=200'),
      api.get('/risk-analysis'),
      api.get('/api/risks/summary').catch(() => ({ data: { open_alerts: 0 } })),
    ]).then(([allData, risk, summary]) => {
      const resources   = allData.data.resources  || []
      const connections = allData.data.connections || []
      const nodes       = risk.data.nodes          || []
      const openAlerts  = summary.data?.open_alerts ?? 0

      const high   = nodes.filter(n => n.risk_level === 'High').length
      const medium = nodes.filter(n => n.risk_level === 'Medium').length
      const low    = nodes.filter(n => n.risk_level === 'Low').length
      const avgScore = nodes.length
        ? (nodes.reduce((s, n) => s + n.risk_score, 0) / nodes.length).toFixed(1)
        : '—'
      const topRisk = nodes.length
        ? nodes.reduce((a, b) => a.risk_score > b.risk_score ? a : b)
        : null

      setStats({ resources: resources.length, connections: connections.length, high, medium, low, avgScore, topRisk, openAlerts })
    }).catch(() => setStats(null))
      .finally(() => setLoading(false))
  }, [])

  return { stats, loading }
}

// ── Small stat card ────────────────────────────────────────────────────────────
function StatCard({ label, value, color, sub }) {
  return (
    <div style={{
      padding: '1rem 1.25rem',
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: '10px',
      borderLeft: `3px solid ${color}`,
    }}>
      <div style={{ fontSize: '0.7rem', color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.3rem' }}>
        {label}
      </div>
      <div style={{ fontSize: '1.8rem', fontWeight: 800, color, lineHeight: 1, fontFamily: 'monospace' }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '0.3rem' }}>{sub}</div>}
    </div>
  )
}

// ── Quick action link ──────────────────────────────────────────────────────────
function QuickLink({ to, icon, label, desc }) {
  return (
    <Link to={to} style={{ textDecoration: 'none' }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: '0.85rem',
        padding: '0.85rem 1rem',
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderRadius: '10px',
        transition: 'border-color 0.15s, background 0.15s',
        cursor: 'pointer',
      }}
        onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--blue)'}
        onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border)'}
      >
        <span style={{ fontSize: '1.3rem' }}>{icon}</span>
        <div>
          <div style={{ fontWeight: 600, fontSize: '0.88rem', color: 'var(--text)' }}>{label}</div>
          <div style={{ fontSize: '0.73rem', color: 'var(--text-faint)' }}>{desc}</div>
        </div>
      </div>
    </Link>
  )
}

export default function Home() {
  const { isAuthenticated } = useAuth()
  const { stats, loading } = useDashboardStats()

  return (
    <div>

      {/* ── Hero ────────────────────────────────────────────────── */}
      <section className="home-hero">
        <p className="home-tag">Cloud Risk Intelligence</p>
        <h1 className="home-title">
          Map, score and monitor<br />
          cloud infrastructure risks
        </h1>

        {!isAuthenticated && (
          <div className="home-actions">
            <Link to="/login" className="btn btn-primary">Get Started</Link>
            <Link to="/login" className="btn btn-secondary">Sign In</Link>
          </div>
        )}
      </section>

      {/* ── Authenticated: Live Dashboard ────────────────────────── */}
      {isAuthenticated && (
        <>
          {/* Live stats row */}
          <section style={{ marginBottom: '2rem' }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.75rem' }}>
              Live Overview
            </div>
            {loading ? (
              <div style={{ color: 'var(--text-faint)', fontSize: '0.85rem' }}>Loading stats…</div>
            ) : !stats ? (
              <div style={{ color: 'var(--text-faint)', fontSize: '0.85rem' }}>Could not load stats. Make sure the backend is running.</div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem' }}>
                <StatCard label="Resources"   value={stats.resources}   color="var(--blue)"    sub={`${stats.connections} connections`} />
                <StatCard label="High Risk"   value={stats.high}        color="#e5626a"         sub="nodes ≥ 70 score" />
                <StatCard label="Medium Risk" value={stats.medium}      color="#e8b84b"         sub="nodes 40–69" />
                <StatCard label="Low Risk"    value={stats.low}         color="#52c97a"         sub="nodes < 40" />
                <StatCard label="Avg Score"   value={stats.avgScore}    color="var(--text-dim)" sub="across all nodes" />
                <StatCard label="Open Alerts" value={stats.openAlerts}  color={stats.openAlerts > 0 ? '#e5626a' : '#52c97a'} sub="unresolved" />
              </div>
            )}
          </section>

          {/* Highest risk resource callout */}
          {stats?.topRisk && (
            <section style={{ marginBottom: '2rem' }}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: '1rem',
                padding: '0.9rem 1.25rem',
                background: 'rgba(229,98,106,0.06)',
                border: '1px solid rgba(229,98,106,0.25)',
                borderRadius: '10px',
              }}>
                <span style={{ fontSize: '1.3rem' }}>🔴</span>
                <div>
                  <div style={{ fontWeight: 700, fontSize: '0.88rem', color: '#e5626a' }}>
                    Highest risk: {stats.topRisk.name}
                    <span style={{ fontFamily: 'monospace', fontWeight: 800, marginLeft: '0.5rem' }}>
                      {stats.topRisk.risk_score?.toFixed(1)}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.73rem', color: 'var(--text-dim)' }}>
                    {stats.topRisk.resource_type} · {stats.topRisk.provider} · {stats.topRisk.region}
                    {stats.topRisk.public_access && ' · Public access on'}
                  </div>
                </div>
                <Link to="/risk" className="btn btn-secondary btn-sm" style={{ marginLeft: 'auto', flexShrink: 0 }}>
                  View Risk →
                </Link>
              </div>
            </section>
          )}

          {/* Quick actions */}
          <section>
            <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.75rem' }}>
              Quick Actions
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.65rem' }}>
              <QuickLink to="/input"    icon="➕" label="Add Resources"      desc="Register new cloud resources" />
              <QuickLink to="/all-data" icon="📋" label="View All Data"      desc="Browse resources and connections" />
              <QuickLink to="/graph"    icon="🕸️" label="Graph View"         desc="Attack paths and blast radius" />
              <QuickLink to="/risk"     icon="🔥" label="Risk Analysis"      desc="Ranked risk scores per node" />
              <QuickLink to="/chat"     icon="🤖" label="Ask ARIA"           desc="Autonomous risk investigation" />
              <QuickLink to="/admin"    icon="⚙️" label="Scoring Settings"   desc="Adjust formula weights live" />
            </div>
          </section>
        </>
      )}

      {/* ── Not logged in: feature overview ────────────────────── */}
      {!isAuthenticated && (
        <section className="home-features">
          <h2 className="home-section-title">What it does</h2>
          <div className="home-feature-list">
            {[
              { title: 'Resource Inventory',  desc: 'Register cloud resources with cost, sensitivity, exposure, provider and region metadata.' },
              { title: 'Connection Mapping',  desc: 'Define directed edges between resources and model the network as a real dependency graph.' },
              { title: 'Risk Scoring',        desc: 'Score each node on a 0–100 scale using sensitivity, exposure, type, cost and connectivity.' },
              { title: 'ARIA Agent',          desc: 'Autonomous Risk Intelligence Agent investigates, plans and executes remediations on approval.' },
            ].map(f => (
              <div key={f.title} className="home-feature-item">
                <h3>{f.title}</h3>
                <p>{f.desc}</p>
              </div>
            ))}
          </div>
        </section>
      )}

    </div>
  )
}
