import { useState, useEffect, useCallback } from 'react'
import { getRiskAnalysis, getReport } from '../api/client'
import toast from 'react-hot-toast'

const levelColor = {
  High: { badge: 'badge-rose', bar: 'var(--rose)', glow: 'rgba(251,113,133,0.25)' },
  Medium: { badge: 'badge-amber', bar: 'var(--amber)', glow: 'rgba(251,191,36,0.2)' },
  Low: { badge: 'badge-emerald', bar: 'var(--emerald)', glow: 'rgba(52,211,153,0.15)' },
}

const typeIcon = (t) => ({ Server: '🖥️', Database: '🗄️', Storage: '📦' }[t] || '☁️')

function ScoreBar({ score, maxScore = 100 }) {
  const pct = Math.min((score / maxScore) * 100, 100)
  const level = score >= 70 ? 'High' : score >= 40 ? 'Medium' : 'Low'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
      <div style={{
        flex: 1, height: '6px',
        background: 'var(--bg-input)',
        borderRadius: '999px',
        overflow: 'hidden',
      }}>
        <div style={{
          height: '100%',
          width: `${pct}%`,
          background: levelColor[level].bar,
          borderRadius: '999px',
          boxShadow: `0 0 8px ${levelColor[level].glow}`,
          transition: 'width 0.6s ease',
        }} />
      </div>
      <span style={{
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: '0.82rem',
        color: levelColor[level].bar,
        minWidth: '24px',
        textAlign: 'right',
      }}>
        {score}
      </span>
    </div>
  )
}

export default function RiskAnalysis() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [downloading, setDownloading] = useState(false)

  const fetchData = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const res = await getRiskAnalysis()
      setData(res.data)
    } catch (err) {
      setError('Cannot reach backend. Ensure FastAPI is running on port 8000.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  const handleDownloadReport = async () => {
    setDownloading(true)
    try {
      const res = await getReport()
      // Create a blob URL and trigger download
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', 'cloud_risk_report.pdf')
      document.body.appendChild(link)
      link.click()
      link.parentNode.removeChild(link)
      toast.success('Report downloaded successfully!')
    } catch (err) {
      toast.error('Failed to download report.')
    } finally {
      setDownloading(false)
    }
  }

  if (loading) return (
    <div className="loading-center">
      <div className="spinner" /><span>Running risk analysis…</span>
    </div>
  )

  if (error) return (
    <div className="empty-state">
      <div className="empty-icon">⚠️</div>
      <p style={{ color: 'var(--rose)' }}>{error}</p>
      <button className="btn btn-secondary btn-sm" onClick={fetchData}>Retry</button>
    </div>
  )

  const {
    nodes = [], total_nodes, high_risk_count, medium_risk_count, low_risk_count, formula,
  } = data || {}

  return (
    <div>
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1>Risk Analysis</h1>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-primary btn-sm" onClick={handleDownloadReport} disabled={downloading}>
            {downloading ? 'Generating...' : '📄 Download Report'}
          </button>
          <button className="btn btn-secondary btn-sm" onClick={fetchData}>⟳ Re-run</button>
        </div>
      </div>

      {/* ── Formula Banner ─────────────────────────────────────── */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(34,211,238,0.06), rgba(99,102,241,0.06))',
        border: '1px solid rgba(34,211,238,0.18)',
        borderRadius: 'var(--radius-md)',
        padding: '1rem 1.5rem',
        marginBottom: '1.75rem',
        display: 'flex',
        alignItems: 'center',
        gap: '1rem',
        flexWrap: 'wrap',
      }}>
        <span style={{ fontSize: '1.3rem' }}>📐</span>
        <code style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: '0.9rem',
          color: 'var(--cyan)',
          flex: 1,
        }}>
          {formula}
        </code>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <span className="badge badge-gray">Sensitivity: H=40 M=20 L=0</span>
          <span className="badge badge-gray">Exposure: Public=35 Private=0</span>
        </div>
      </div>

      {/* ── Summary Stats ──────────────────────────────────────── */}
      <div className="grid-4" style={{ marginBottom: '1.75rem' }}>
        <div className="stat-card">
          <span className="stat-label">Total Nodes</span>
          <span className="stat-value" style={{ color: 'var(--cyan)' }}>{total_nodes}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">🔴 High Risk</span>
          <span className="stat-value" style={{ color: 'var(--rose)' }}>{high_risk_count}</span>
          <span className="stat-sub">score &gt;= 70</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">🟡 Medium Risk</span>
          <span className="stat-value" style={{ color: 'var(--amber)' }}>{medium_risk_count}</span>
          <span className="stat-sub">score 40-69</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">🟢 Low Risk</span>
          <span className="stat-value" style={{ color: 'var(--emerald)' }}>{low_risk_count}</span>
          <span className="stat-sub">score &lt; 40</span>
        </div>
      </div>

      {/* ── Nodes Table ────────────────────────────────────────── */}
      {nodes.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📊</div>
          <p>No resources found. Add resources and connections first, then re-run analysis.</p>
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Resource ID</th>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Sensitivity</th>
                  <th>Public</th>
                  <th style={{ textAlign: 'center' }}>Connectivity</th>
                  <th style={{ textAlign: 'center' }}>Sens. Score</th>
                  <th style={{ textAlign: 'center' }}>Exp. Score</th>
                  <th style={{ minWidth: '180px' }}>Risk Score</th>
                  <th>Level</th>
                </tr>
              </thead>
              <tbody>
                {nodes.map((n) => {
                  const lc = levelColor[n.risk_level] || levelColor.Low
                  return (
                    <tr key={n.id} style={n.risk_level === 'High'
                      ? { background: 'rgba(251,113,133,0.03)' } : {}}>
                      <td><code className="mono">{n.resource_uid}</code></td>
                      <td className="name-cell">
                        {typeIcon(n.resource_type)} {n.name}
                      </td>
                      <td><span className="badge badge-cyan">{n.resource_type}</span></td>
                      <td>
                        <span className={`badge ${n.sensitivity === 'High' ? 'badge-rose'
                          : n.sensitivity === 'Medium' ? 'badge-amber' : 'badge-emerald'}`}>
                          {n.sensitivity}
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${n.public_access ? 'badge-rose' : 'badge-emerald'}`}>
                          {n.public_access ? 'Yes' : 'No'}
                        </span>
                      </td>
                      <td style={{ textAlign: 'center', color: 'var(--violet)', fontFamily: 'JetBrains Mono, monospace' }}>
                        {n.connectivity}
                      </td>
                      <td style={{ textAlign: 'center', fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-secondary)' }}>
                        {n.sensitivity_score}
                      </td>
                      <td style={{ textAlign: 'center', fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-secondary)' }}>
                        {n.exposure_score}
                      </td>
                      <td style={{ minWidth: '180px' }}>
                        <ScoreBar score={n.risk_score} />
                      </td>
                      <td>
                        <span className={`badge ${lc.badge}`}>{n.risk_level}</span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Breakdown legend ───────────────────────────────────── */}
      {nodes.length > 0 && (
        <div style={{ marginTop: '1.5rem', color: 'var(--text-muted)', fontSize: '0.8rem', textAlign: 'center' }}>
          Formula: <code style={{ color: 'var(--text-secondary)' }}>
            Risk Score = Sensitivity + Exposure + Type + Cost + Connectivity
          </code>
          &nbsp;·&nbsp; Results written back to DB automatically.
        </div>
      )}
    </div>
  )
}
