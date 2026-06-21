/**
 * src/pages/AdminConfig.jsx
 *
 * Risk Formula Admin — adjust scoring weights live.
 * - Live preview uses REAL resource data from the DB
 * - Stats update when resources change
 * - Formula preview still shows hypothetical worst-case for slider comparison
 */

import { useState, useEffect } from 'react'
import toast from 'react-hot-toast'
import { getRiskConfig, updateRiskConfig } from '../api/client'
import { PageHeader } from '../components/UIState'
import { SkeletonCard } from '../components/Skeleton'
import api from '../api/client'

const WEIGHT_META = [
  { key: 'sensitivity_high', label: 'High Sensitivity Score', min: 0, max: 100, step: 1, desc: 'Risk points added for High-sensitivity resources' },
  { key: 'sensitivity_medium', label: 'Medium Sensitivity Score', min: 0, max: 100, step: 1, desc: 'Risk points added for Medium-sensitivity resources' },
  { key: 'public_access', label: 'Public Exposure Penalty', min: 0, max: 100, step: 1, desc: 'Risk points added when a resource is publicly accessible' },
  { key: 'type_database', label: 'Database Type Bonus', min: 0, max: 50, step: 1, desc: 'Extra risk for Database resource type' },
  { key: 'type_storage', label: 'Storage Type Bonus', min: 0, max: 50, step: 1, desc: 'Extra risk for Storage resource type' },
  { key: 'cost_threshold', label: 'Cost Threshold ($)', min: 0, max: 10000, step: 50, desc: 'Monthly cost above which the cost bonus applies' },
  { key: 'cost_bonus', label: 'Cost Bonus (above threshold)', min: 0, max: 50, step: 1, desc: 'Risk points added when cost exceeds the threshold' },
  { key: 'connectivity_per_edge', label: 'Risk per Connection Edge', min: 0, max: 20, step: 0.5, desc: 'Risk points added per incoming/outgoing connection' },
  { key: 'connectivity_cap', label: 'Max Connectivity Bonus', min: 0, max: 50, step: 1, desc: 'Maximum connectivity contribution to the risk score' },
]

/** Compute what a resource's score WOULD BE with the given draft weights */
function simulateScore(resource, connections, weights) {
  const sens = resource.sensitivity === 'High'
    ? (weights.sensitivity_high || 0)
    : resource.sensitivity === 'Medium'
      ? (weights.sensitivity_medium || 0)
      : 0
  const exposure = resource.public_access ? (weights.public_access || 0) : 0
  const typeBonus = resource.resource_type === 'Database'
    ? (weights.type_database || 0)
    : resource.resource_type === 'Storage'
      ? (weights.type_storage || 0)
      : 0
  const costBonus = resource.cost > (weights.cost_threshold || 500) ? (weights.cost_bonus || 0) : 0
  const connBonus = Math.min(
    connections * (weights.connectivity_per_edge || 0),
    weights.connectivity_cap || 0,
  )
  return Math.min(sens + exposure + typeBonus + costBonus + connBonus, 100)
}

function riskLevel(score) {
  if (score >= 70) return { label: 'High', color: '#e5626a' }
  if (score >= 40) return { label: 'Medium', color: '#e8b84b' }
  return { label: 'Low', color: '#52c97a' }
}

/** Worst-case hypothetical for formula explanation */
function worstCasePreview(weights) {
  const s = (weights.sensitivity_high || 0)
    + (weights.public_access || 0)
    + (weights.type_database || 0)
    + (weights.cost_bonus || 0)
    + Math.min(3 * (weights.connectivity_per_edge || 0), weights.connectivity_cap || 0)
  return Math.min(s, 100).toFixed(1)
}

export default function AdminConfig() {
  const [config, setConfig] = useState(null)
  const [draft, setDraft] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  // Real resource data
  const [resources, setResources] = useState([])
  const [connections, setConnections] = useState([])
  const [dataLoading, setDataLoading] = useState(true)

  // Load config
  useEffect(() => {
    getRiskConfig()
      .then(res => { setConfig(res.data); setDraft({ ...res.data }) })
      .catch(() => toast.error('Could not load risk config.'))
      .finally(() => setLoading(false))
  }, [])

  // Load real resources + connections
  useEffect(() => {
    api.get('/all-data?skip=0&limit=200')
      .then(res => {
        setResources(res.data.resources || [])
        setConnections(res.data.connections || [])
      })
      .catch(() => { })
      .finally(() => setDataLoading(false))
  }, [])

  const set = (key, value) => setDraft(prev => ({ ...prev, [key]: Number(value) }))

  const handleSave = async () => {
    setSaving(true)
    try {
      const res = await updateRiskConfig(draft)
      setConfig(res.data)
      setDraft({ ...res.data })
      toast.success('Risk formula updated and persisted ✓')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save config.')
    } finally {
      setSaving(false)
    }
  }

  const handleReset = () => {
    if (config) { setDraft({ ...config }); toast('Reset to last saved values.') }
  }

  if (loading) return (
    <div>
      <PageHeader title="Risk Formula Config" description="Loading…" />
      <div className="grid-2" style={{ alignItems: 'start' }}>
        <SkeletonCard rows={6} />
        <SkeletonCard rows={6} />
      </div>
    </div>
  )

  if (!draft) return null

  // ── Compute live stats from REAL resources ──────────────────────────────────
  // Build connection count map: resource_uid → degree (in + out)
  const degreeMap = {}
  resources.forEach(r => { degreeMap[r.resource_uid] = 0 })
  connections.forEach(c => {
    if (degreeMap[c.from_node] !== undefined) degreeMap[c.from_node] += 1
    if (degreeMap[c.to_node] !== undefined) degreeMap[c.to_node] += 1
  })

  // Simulate scores with DRAFT weights
  const simulated = resources.map(r => ({
    ...r,
    simScore: simulateScore(r, degreeMap[r.resource_uid] || 0, draft),
  }))

  const sorted = [...simulated].sort((a, b) => b.simScore - a.simScore)
  const top = sorted[0] || null
  const bottom = sorted[sorted.length - 1] || null
  const avg = simulated.length
    ? (simulated.reduce((s, r) => s + r.simScore, 0) / simulated.length).toFixed(1)
    : null

  const highCount = simulated.filter(r => r.simScore >= 70).length
  const medCount = simulated.filter(r => r.simScore >= 40 && r.simScore < 70).length
  const lowCount = simulated.filter(r => r.simScore < 40).length

  const worstCase = worstCasePreview(draft)
  const wcColor = riskLevel(Number(worstCase)).color

  return (
    <div>
      <PageHeader
        title="Risk Formula Config"

      />

      {/* ── Live Stats from Real Data ────────────────────────────────────────── */}
      <div className="card" style={{ marginBottom: '1.75rem', padding: '1.25rem 1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: '0.95rem' }}>
              📊 Live Preview — Based on your {resources.length} real resource{resources.length !== 1 ? 's' : ''}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '0.2rem' }}>
              Scores below show how your resources would be rated with the <strong>current slider settings</strong>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '0.6rem' }}>
            <button className="btn btn-secondary btn-sm" onClick={handleReset} disabled={saving}>Reset</button>
            <button className="btn btn-primary btn-sm" onClick={handleSave} disabled={saving}>
              {saving ? 'Saving…' : '💾 Save & Apply'}
            </button>
          </div>
        </div>

        {dataLoading ? (
          <div style={{ color: 'var(--text-faint)', fontSize: '0.85rem' }}>Loading resource data…</div>
        ) : resources.length === 0 ? (
          <div style={{ color: 'var(--text-faint)', fontSize: '0.85rem', padding: '0.75rem', background: 'var(--bg-subtle)', borderRadius: '8px', border: '1px dashed var(--border)' }}>
            No resources found. <strong>Add cloud resources</strong> to see live score previews here.
          </div>
        ) : (
          <>
            {/* Stat cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>

              {/* Highest risk resource */}
              {top && (
                <div style={{ padding: '0.9rem', background: 'var(--bg-subtle)', borderRadius: '10px', border: `1px solid ${riskLevel(top.simScore).color}33` }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-faint)', marginBottom: '0.25rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Highest Risk</div>
                  <div style={{ fontSize: '1.6rem', fontWeight: 800, color: riskLevel(top.simScore).color, lineHeight: 1, fontFamily: 'monospace' }}>
                    {top.simScore.toFixed(1)}
                  </div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '0.3rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {top.name}
                  </div>
                </div>
              )}

              {/* Average score */}
              {avg && (
                <div style={{ padding: '0.9rem', background: 'var(--bg-subtle)', borderRadius: '10px', border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-faint)', marginBottom: '0.25rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Average Score</div>
                  <div style={{ fontSize: '1.6rem', fontWeight: 800, color: riskLevel(Number(avg)).color, lineHeight: 1, fontFamily: 'monospace' }}>
                    {avg}
                  </div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '0.3rem' }}>across {resources.length} resources</div>
                </div>
              )}

              {/* Lowest risk resource */}
              {bottom && (
                <div style={{ padding: '0.9rem', background: 'var(--bg-subtle)', borderRadius: '10px', border: `1px solid ${riskLevel(bottom.simScore).color}33` }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-faint)', marginBottom: '0.25rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Lowest Risk</div>
                  <div style={{ fontSize: '1.6rem', fontWeight: 800, color: riskLevel(bottom.simScore).color, lineHeight: 1, fontFamily: 'monospace' }}>
                    {bottom.simScore.toFixed(1)}
                  </div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '0.3rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {bottom.name}
                  </div>
                </div>
              )}

              {/* Risk distribution */}
              <div style={{ padding: '0.9rem', background: 'var(--bg-subtle)', borderRadius: '10px', border: '1px solid var(--border)' }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-faint)', marginBottom: '0.35rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Distribution</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.76rem' }}>
                    <span style={{ color: '#e5626a' }}>● High</span>
                    <strong>{highCount}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.76rem' }}>
                    <span style={{ color: '#e8b84b' }}>● Medium</span>
                    <strong>{medCount}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.76rem' }}>
                    <span style={{ color: '#52c97a' }}>● Low</span>
                    <strong>{lowCount}</strong>
                  </div>
                </div>
              </div>

              {/* Worst-case hypothetical */}
              <div style={{ padding: '0.9rem', background: 'var(--bg-subtle)', borderRadius: '10px', border: '1px solid var(--border)' }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-faint)', marginBottom: '0.25rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Formula Max</div>
                <div style={{ fontSize: '1.6rem', fontWeight: 800, color: wcColor, lineHeight: 1, fontFamily: 'monospace' }}>
                  {worstCase}
                </div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '0.3rem' }}>hypothetical worst case</div>
              </div>
            </div>

            {/* Top 5 resources bar chart */}
            <div>
              <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-dim)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Top resources by simulated score
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                {sorted.slice(0, 5).map((r, i) => {
                  const lvl = riskLevel(r.simScore)
                  const savedLvl = riskLevel(r.risk_score || 0)
                  const changed = Math.abs(r.simScore - (r.risk_score || 0)) > 0.5
                  return (
                    <div key={r.id} style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                      <span style={{ fontSize: '0.7rem', color: 'var(--text-faint)', width: '14px', textAlign: 'right', flexShrink: 0 }}>{i + 1}</span>
                      <span style={{ fontSize: '0.78rem', color: 'var(--text-dim)', width: '140px', flexShrink: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {r.name}
                      </span>
                      <div style={{ flex: 1, background: 'var(--bg-base)', borderRadius: '4px', height: '10px', overflow: 'hidden' }}>
                        <div style={{
                          width: `${r.simScore}%`,
                          height: '100%',
                          background: lvl.color,
                          borderRadius: '4px',
                          transition: 'width 0.3s ease',
                        }} />
                      </div>
                      <span style={{ fontSize: '0.75rem', fontWeight: 700, color: lvl.color, width: '36px', textAlign: 'right', fontFamily: 'monospace' }}>
                        {r.simScore.toFixed(0)}
                      </span>
                      {changed && (
                        <span style={{ fontSize: '0.65rem', color: r.simScore > (r.risk_score || 0) ? '#e5626a' : '#52c97a', width: '36px', flexShrink: 0 }}>
                          {r.simScore > (r.risk_score || 0) ? '▲' : '▼'} {Math.abs(r.simScore - (r.risk_score || 0)).toFixed(0)}
                        </span>
                      )}
                      {!changed && <span style={{ width: '36px', flexShrink: 0 }} />}
                    </div>
                  )
                })}
              </div>
              {simulated.length > 5 && (
                <div style={{ fontSize: '0.72rem', color: 'var(--text-faint)', marginTop: '0.5rem' }}>
                  + {simulated.length - 5} more resource{simulated.length - 5 !== 1 ? 's' : ''} not shown
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* Weight sliders */}
      <div className="grid-2" style={{ alignItems: 'start' }}>
        {WEIGHT_META.map((meta) => {
          const val = draft[meta.key] ?? 0
          const pct = ((val - meta.min) / (meta.max - meta.min)) * 100
          return (
            <div key={meta.key} className="card" style={{ padding: '1.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '0.4rem' }}>
                <label htmlFor={`weight-${meta.key}`} style={{ fontWeight: 600, fontSize: '0.9rem' }}>{meta.label}</label>
                <span style={{
                  fontFamily: 'JetBrains Mono, monospace',
                  fontSize: '1.1rem', fontWeight: 800,
                  color: 'var(--blue)',
                  minWidth: '50px', textAlign: 'right',
                }}>
                  {val}
                </span>
              </div>
              <p style={{ color: 'var(--text-dim)', fontSize: '0.78rem', marginBottom: '0.75rem' }}>{meta.desc}</p>
              <input
                id={`weight-${meta.key}`}
                type="range"
                min={meta.min} max={meta.max} step={meta.step}
                value={val}
                onChange={e => set(meta.key, e.target.value)}
                style={{ width: '100%', accentColor: 'var(--blue)', height: '6px', cursor: 'pointer' }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: 'var(--text-faint)', marginTop: '0.3rem' }}>
                <span>{meta.min}</span>
                <span>{meta.max}</span>
              </div>
            </div>
          )
        })}
      </div>

      {/* Formula explanation */}
      <div className="card" style={{ marginTop: '1.75rem', background: 'var(--bg-subtle)' }}>
        <div className="card-title" style={{ marginBottom: '0.75rem' }}>Risk Score Formula</div>
        <code style={{ fontSize: '0.88rem', color: 'var(--blue)', display: 'block', lineHeight: '2' }}>
          Score = Sensitivity + Exposure + TypeBonus + CostBonus + min(Connections × PerEdge, Cap)
        </code>
        <div style={{ color: 'var(--text-dim)', fontSize: '0.8rem', marginTop: '0.5rem' }}>
          Score is capped at 100. Risk levels: Low &lt; 40, Medium 40–69, High ≥ 70.
          The <strong>Live Preview</strong> above simulates your real resources against the current sliders — move a slider to see scores change instantly.
        </div>
      </div>
    </div>
  )
}
