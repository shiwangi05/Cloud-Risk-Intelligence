/**
 * src/pages/AllData.jsx
 * 
 * Cloud inventory table with:
 * - Pagination (Previous / Next, page indicator)
 * - Loading skeletons instead of plain spinner
 * - Edit modal for resources
 */

import { useState, useEffect, useCallback } from 'react'
import toast from 'react-hot-toast'
import { getAllData, updateResource, deleteResource, deleteConnection } from '../api/client'
import { ErrorState, PageHeader, StatCard } from '../components/UIState'
import { SkeletonTable, SkeletonStatGrid } from '../components/Skeleton'

const PAGE_SIZE = 15

const sensitivityBadge = (s) =>
  ({ High: 'badge-rose', Medium: 'badge-amber', Low: 'badge-emerald' }[s] || 'badge-gray')

// ── Edit Resource Modal ────────────────────────────────────────────────────────

function EditResourceModal({ resource, onClose, onSaved }) {
  const [form, setForm] = useState({
    name: resource.name,
    resource_type: resource.resource_type,
    cost: resource.cost || 0,
    sensitivity: resource.sensitivity || 'Low',
    public_access: Boolean(resource.public_access),
    provider: resource.provider || 'AWS',
    region: resource.region || 'us-east-1',
    status: resource.status || 'active',
  })
  const [saving, setSaving] = useState(false)
  const set = (field, value) => setForm(curr => ({ ...curr, [field]: value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      await updateResource(resource.id, { ...form, cost: parseFloat(form.cost) || 0 })
      toast.success('Resource updated.')
      onSaved()
      onClose()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to update resource.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal-panel">
        <div className="modal-title">Edit {resource.resource_uid}</div>
        <form onSubmit={handleSubmit}>
          <div className="form-grid">
            <div className="form-group"><label className="form-label">Name</label>
              <input className="form-input" value={form.name} onChange={e => set('name', e.target.value)} />
            </div>
            <div className="form-group"><label className="form-label">Type</label>
              <select className="form-select" value={form.resource_type} onChange={e => set('resource_type', e.target.value)}>
                <option>Server</option><option>Database</option><option>Storage</option><option>IAM</option>
              </select>
            </div>
            <div className="form-group"><label className="form-label">Cost</label>
              <input className="form-input" type="number" min="0" step="0.01" value={form.cost} onChange={e => set('cost', e.target.value)} />
            </div>
            <div className="form-group"><label className="form-label">Sensitivity</label>
              <select className="form-select" value={form.sensitivity} onChange={e => set('sensitivity', e.target.value)}>
                <option>High</option><option>Medium</option><option>Low</option>
              </select>
            </div>
            <div className="form-group"><label className="form-label">Provider</label>
              <select className="form-select" value={form.provider} onChange={e => set('provider', e.target.value)}>
                <option>AWS</option><option>GCP</option><option>Azure</option>
              </select>
            </div>
            <div className="form-group"><label className="form-label">Region</label>
              <input className="form-input" value={form.region} onChange={e => set('region', e.target.value)} />
            </div>
            <div className="form-group"><label className="form-label">Status</label>
              <select className="form-select" value={form.status} onChange={e => set('status', e.target.value)}>
                <option>active</option><option>review</option><option>disabled</option>
              </select>
            </div>
            <div className="form-group"><label className="form-label">Public Access</label>
              <div className="toggle-row">
                <span>{form.public_access ? 'Public' : 'Private'}</span>
                <label className="toggle">
                  <input type="checkbox" checked={form.public_access} onChange={e => set('public_access', e.target.checked)} />
                  <span className="toggle-slider" />
                </label>
              </div>
            </div>
          </div>
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Saving…' : 'Save Changes'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Pagination controls ────────────────────────────────────────────────────────

function Pagination({ skip, limit, total, onPrev, onNext }) {
  const page = Math.floor(skip / limit) + 1
  const totalPages = Math.max(1, Math.ceil(total / limit))
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '1rem', padding: '0 0.25rem' }}>
      <span style={{ color: 'var(--text-muted)', fontSize: '0.83rem' }}>
        Showing {skip + 1}–{Math.min(skip + limit, total)} of <strong>{total}</strong>
      </span>
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
        <button className="btn btn-secondary btn-sm" onClick={onPrev} disabled={skip === 0}>← Prev</button>
        <span style={{ fontSize: '0.83rem', color: 'var(--text-muted)', minWidth: '80px', textAlign: 'center' }}>
          Page {page} of {totalPages}
        </span>
        <button className="btn btn-secondary btn-sm" onClick={onNext} disabled={skip + limit >= total}>Next →</button>
      </div>
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function AllData() {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [tab, setTab]         = useState('resources')
  const [editing, setEditing] = useState(null)
  const [skip, setSkip]       = useState(0)

  const fetchData = useCallback(async (s = skip) => {
    setLoading(true)
    setError(null)
    try {
      const res = await getAllData(s, PAGE_SIZE)
      setData(res.data)
    } catch {
      setError('Could not reach backend. Make sure FastAPI is running on port 8000.')
    } finally {
      setLoading(false)
    }
  }, [skip])

  useEffect(() => { fetchData(skip) }, [skip])  // re-fetch when page changes

  const handleDeleteResource = async (resource) => {
    if (!window.confirm(`Delete ${resource.resource_uid}? Connected edges will also be removed.`)) return
    try {
      await deleteResource(resource.id)
      toast.success('Resource deleted.')
      fetchData(skip)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to delete resource.')
    }
  }

  const handleDeleteConnection = async (connection) => {
    if (!window.confirm(`Delete connection ${connection.from_node} → ${connection.to_node}?`)) return
    try {
      await deleteConnection(connection.id)
      toast.success('Connection deleted.')
      fetchData(skip)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to delete connection.')
    }
  }

  if (error) return <ErrorState message={error} onRetry={() => fetchData(0)} />

  const {
    resources = [], connections = [],
    total_resources = 0, total_connections = 0,
  } = data || {}

  return (
    <div>
      <PageHeader
        title="All Cloud Data"
        description="Review, edit, and remove inventory records used by the risk engine."
        action={
          <button className="btn btn-secondary btn-sm" onClick={() => fetchData(skip)} disabled={loading}>
            {loading ? 'Refreshing…' : 'Refresh'}
          </button>
        }
      />

      {/* Stat cards — show skeleton while loading first time */}
      {loading && !data ? (
        <SkeletonStatGrid count={4} />
      ) : (
        <div className="grid-4" style={{ marginBottom: '1.75rem' }}>
          <StatCard label="Resources"      value={total_resources}                                           tone="var(--cyan)" />
          <StatCard label="Connections"    value={total_connections}                                         tone="var(--violet)" />
          <StatCard label="High Sensitivity" value={resources.filter(r => r.sensitivity === 'High').length} tone="var(--rose)" />
          <StatCard label="Public"         value={resources.filter(r => r.public_access).length}            tone="var(--amber)" />
        </div>
      )}

      {/* Tab switcher */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
        <button
          className={`btn ${tab === 'resources' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
          onClick={() => { setTab('resources'); setSkip(0) }}
        >
          Resources ({total_resources})
        </button>
        <button
          className={`btn ${tab === 'connections' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
          onClick={() => { setTab('connections'); setSkip(0) }}
        >
          Connections ({total_connections})
        </button>
      </div>

      {/* Resources table */}
      {tab === 'resources' && (
        <>
          {loading ? <SkeletonTable rows={6} cols={9} /> : (
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              {resources.length === 0 ? (
                <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                  No resources on this page.
                </div>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Resource ID</th><th>Name</th><th>Type</th><th>Provider</th>
                        <th>Cost</th><th>Sensitivity</th><th>Public</th><th>Risk</th>
                        <th>Status</th><th style={{ textAlign: 'right' }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {resources.map(r => (
                        <tr key={r.id}>
                          <td><code className="mono">{r.resource_uid}</code></td>
                          <td className="name-cell">{r.name}</td>
                          <td><span className="badge badge-cyan">{r.resource_type}</span></td>
                          <td>{r.provider}</td>
                          <td style={{ color: 'var(--amber)' }}>${Number(r.cost).toFixed(2)}</td>
                          <td><span className={`badge ${sensitivityBadge(r.sensitivity)}`}>{r.sensitivity}</span></td>
                          <td><span className={`badge ${r.public_access ? 'badge-rose' : 'badge-emerald'}`}>{r.public_access ? 'Yes' : 'No'}</span></td>
                          <td style={{ color: 'var(--cyan)', fontFamily: 'JetBrains Mono, monospace' }}>{Number(r.risk_score).toFixed(1)}</td>
                          <td><span className="badge badge-gray">{r.status}</span></td>
                          <td>
                            <div className="table-actions">
                              <button className="btn btn-secondary btn-sm" onClick={() => setEditing(r)}>Edit</button>
                              <button className="btn btn-danger btn-sm" onClick={() => handleDeleteResource(r)}>Delete</button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
          {!loading && total_resources > PAGE_SIZE && (
            <Pagination
              skip={skip} limit={PAGE_SIZE} total={total_resources}
              onPrev={() => setSkip(s => Math.max(0, s - PAGE_SIZE))}
              onNext={() => setSkip(s => s + PAGE_SIZE)}
            />
          )}
        </>
      )}

      {/* Connections table */}
      {tab === 'connections' && (
        <>
          {loading ? <SkeletonTable rows={5} cols={6} /> : (
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              {connections.length === 0 ? (
                <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                  No connections on this page.
                </div>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table className="data-table">
                    <thead>
                      <tr><th>#</th><th>From</th><th></th><th>To</th><th>Type</th><th>Risk Weight</th><th>Created</th><th style={{ textAlign: 'right' }}>Actions</th></tr>
                    </thead>
                    <tbody>
                      {connections.map((c, idx) => (
                        <tr key={c.id}>
                          <td style={{ color: 'var(--text-muted)' }}>{skip + idx + 1}</td>
                          <td><code className="mono">{c.from_node}</code></td>
                          <td style={{ color: 'var(--violet)' }}>→</td>
                          <td><code className="mono">{c.to_node}</code></td>
                          <td><span className="badge badge-violet">{c.connection_type}</span></td>
                          <td>{c.risk_weight}</td>
                          <td style={{ color: 'var(--text-muted)' }}>{new Date(c.created_at).toLocaleDateString()}</td>
                          <td>
                            <div className="table-actions">
                              <button className="btn btn-danger btn-sm" onClick={() => handleDeleteConnection(c)}>Delete</button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
          {!loading && total_connections > PAGE_SIZE && (
            <Pagination
              skip={skip} limit={PAGE_SIZE} total={total_connections}
              onPrev={() => setSkip(s => Math.max(0, s - PAGE_SIZE))}
              onNext={() => setSkip(s => s + PAGE_SIZE)}
            />
          )}
        </>
      )}

      {editing && (
        <EditResourceModal
          resource={editing}
          onClose={() => setEditing(null)}
          onSaved={() => fetchData(skip)}
        />
      )}
    </div>
  )
}
