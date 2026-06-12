import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { API_DOCS_URL } from '../api/client'

const features = [
  { icon: 'RI', color: 'rgba(34,211,238,0.12)', title: 'Resource Inventory', desc: 'Register cloud resources with cost, sensitivity, exposure, provider, and region metadata.' },
  { icon: 'CM', color: 'rgba(129,140,248,0.12)', title: 'Connection Mapping', desc: 'Define directed edges between resources and model the network as a real dependency graph.' },
  { icon: 'RS', color: 'rgba(251,113,133,0.12)', title: 'Risk Scoring', desc: 'Score each node on a 0-100 model using sensitivity, exposure, type, cost, and connectivity.' },
  { icon: 'GA', color: 'rgba(52,211,153,0.12)', title: 'Graph Analysis', desc: 'Use NetworkX for attack paths, blast radius, centrality, graph stats, and risk intelligence.' },
]

const endpoints = [
  { method: 'POST', path: '/api/resources/', desc: 'Add a new cloud resource' },
  { method: 'POST', path: '/api/resources/connections/', desc: 'Connect two resources by UID' },
  { method: 'GET', path: '/all-data', desc: 'Retrieve all resources and connections' },
  { method: 'GET', path: '/risk-analysis', desc: 'Score every node with the canonical risk model' },
]

export default function Home() {
  const { isAuthenticated } = useAuth()

  return (
    <div>
      <section className="hero">
        <div className="hero-eyebrow">
          <span>Live graph intelligence</span>
        </div>
        <h1>
          Cloud Risk<br />
          <span className="grad">Intelligence Platform</span>
        </h1>
        <p>
          Visualize cloud infrastructure as a graph, identify risky resources,
          simulate attack paths, estimate blast radius, and generate risk reports.
        </p>
        <div className="hero-actions">
          {isAuthenticated ? (
            <>
              <Link to="/input" className="btn btn-primary">Add Resources</Link>
              <Link to="/all-data" className="btn btn-secondary">View Data</Link>
              <Link to="/chat" className="btn btn-secondary">Ask Assistant</Link>
            </>
          ) : (
            <>
              <Link to="/login" className="btn btn-primary">Login to Continue</Link>
              <Link to="/login" className="btn btn-secondary">Create Account</Link>
            </>
          )}
        </div>
      </section>

      <div className="grid-4" style={{ marginBottom: '2rem' }}>
        {features.map((feature) => (
          <div className="feature-card" key={feature.title}>
            <div className="feature-icon" style={{ background: feature.color }}>{feature.icon}</div>
            <h3>{feature.title}</h3>
            <p>{feature.desc}</p>
          </div>
        ))}
      </div>

      {isAuthenticated && (
        <div className="grid-2" style={{ alignItems: 'start' }}>
          <div className="card">
            <div className="card-title">API Reference</div>
            <table className="data-table">
              <thead>
                <tr><th>Method</th><th>Endpoint</th><th>Description</th></tr>
              </thead>
              <tbody>
                {endpoints.map((endpoint) => (
                  <tr key={endpoint.path}>
                    <td><span className={`badge ${endpoint.method === 'POST' ? 'badge-violet' : 'badge-cyan'}`}>{endpoint.method}</span></td>
                    <td><code className="mono">{endpoint.path}</code></td>
                    <td>{endpoint.desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ marginTop: '1.25rem' }}>
              <a href={API_DOCS_URL} target="_blank" rel="noreferrer" className="btn btn-secondary btn-sm">
                Open API Docs
              </a>
            </div>
          </div>

          <div className="card">
            <div className="card-title">Risk Formula</div>
            <div style={{
              background: 'var(--bg-input)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              padding: '1rem',
              fontFamily: "'JetBrains Mono', monospace",
              color: 'var(--cyan)',
              marginBottom: '1rem',
            }}>
              Risk = Sensitivity + Exposure + Type + Cost + Connectivity
            </div>
            <div style={{ display: 'grid', gap: '0.75rem' }}>
              <div><span className="badge badge-rose">Sensitivity</span> <span style={{ color: 'var(--text-secondary)' }}>High 40, Medium 20, Low 0</span></div>
              <div><span className="badge badge-amber">Exposure</span> <span style={{ color: 'var(--text-secondary)' }}>Public adds 35</span></div>
              <div><span className="badge badge-violet">Graph</span> <span style={{ color: 'var(--text-secondary)' }}>5 per edge, capped at 20</span></div>
              <div><span className="badge badge-cyan">Levels</span> <span style={{ color: 'var(--text-secondary)' }}>Low &lt; 40, Medium 40-69, High &gt;= 70</span></div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
