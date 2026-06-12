/**
 * src/pages/AdminConfig.jsx
 *
 * Risk Formula Admin — adjust scoring weights live.
 * Changes are persisted to backend .env and take effect immediately.
 */

import { useState, useEffect } from 'react'
import toast from 'react-hot-toast'
import { getRiskConfig, updateRiskConfig } from '../api/client'
import { PageHeader } from '../components/UIState'
import { SkeletonCard } from '../components/Skeleton'

const WEIGHT_META = [
  { key: 'sensitivity_high',      label: 'High Sensitivity Score',       min: 0,  max: 100, step: 1,  desc: 'Risk points added for High-sensitivity resources' },
  { key: 'sensitivity_medium',    label: 'Medium Sensitivity Score',     min: 0,  max: 100, step: 1,  desc: 'Risk points added for Medium-sensitivity resources' },
  { key: 'public_access',         label: 'Public Exposure Penalty',      min: 0,  max: 100, step: 1,  desc: 'Risk points added when a resource is publicly accessible' },
  { key: 'type_database',         label: 'Database Type Bonus',          min: 0,  max: 50,  step: 1,  desc: 'Extra risk for Database resource type' },
  { key: 'type_storage',          label: 'Storage Type Bonus',           min: 0,  max: 50,  step: 1,  desc: 'Extra risk for Storage resource type' },
  { key: 'cost_threshold',        label: 'Cost Threshold ($)',           min: 0,  max: 10000, step: 50, desc: 'Monthly cost above which the cost bonus applies' },
  { key: 'cost_bonus',            label: 'Cost Bonus (above threshold)', min: 0,  max: 50,  step: 1,  desc: 'Risk points added when cost exceeds the threshold' },
  { key: 'connectivity_per_edge', label: 'Risk per Connection Edge',     min: 0,  max: 20,  step: 0.5, desc: 'Risk points added per incoming/outgoing connection' },
  { key: 'connectivity_cap',      label: 'Max Connectivity Bonus',      min: 0,  max: 50,  step: 1,  desc: 'Maximum connectivity contribution to the risk score' },
]

function previewScore(weights) {
  // Simulate a High-sensitivity, public, DB, cost>threshold, 3-edges resource
  const s = (weights.sensitivity_high || 0)
    + (weights.public_access || 0)
    + (weights.type_database || 0)
    + (weights.cost_bonus || 0)
    + Math.min(3 * (weights.connectivity_per_edge || 0), weights.connectivity_cap || 0)
  return Math.min(s, 100).toFixed(1)
}

export default function AdminConfig() {
  const [config, setConfig] = useState(null)
  const [draft, setDraft]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving]   = useState(false)

  useEffect(() => {
    getRiskConfig()
      .then(res => { setConfig(res.data); setDraft({ ...res.data }) })
      .catch(() => toast.error('Could not load risk config.'))
      .finally(() => setLoading(false))
  }, [])

  const set = (key, value) => setDraft(prev => ({ ...prev, [key]: Number(value) }))

  const handleSave = async () => {
    setSaving(true)
    try {
      const res = await updateRiskConfig(draft)
      setConfig(res.data)
      setDraft({ ...res.data })
      toast.success('Risk formula updated and persisted to .env ✓')
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

  const preview = previewScore(draft)
  const previewColor = preview >= 70 ? 'var(--rose)' : preview >= 40 ? 'var(--amber)' : 'var(--emerald)'

  return (
    <div>
      <PageHeader
        title="Risk Formula Config"
        description="Adjust scoring weights live. Changes persist to .env and take effect immediately without a server restart."
      />

      {/* Preview banner */}
      <div className="card" style={{
        marginBottom: '1.75rem',
        background: 'linear-gradient(135deg, var(--bg-card), var(--bg-input))',
        display: 'flex', alignItems: 'center', gap: '2rem', flexWrap: 'wrap',
      }}>
        <div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginBottom: '0.25rem' }}>
            Live Preview — worst-case resource score
          </div>
          <div style={{ fontSize: '2.5rem', fontWeight: 800, color: previewColor, fontFamily: 'JetBrains Mono, monospace', lineHeight: 1 }}>
            {preview}
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginTop: '0.35rem' }}>
            (High sensitivity + public + Database + high cost + 3 connections)
          </div>
        </div>
        <div style={{ flex: 1, display: 'flex', gap: '0.75rem', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          <button className="btn btn-secondary" onClick={handleReset} disabled={saving}>Reset</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving…' : '💾 Save & Apply'}
          </button>
        </div>
      </div>

      {/* Weight sliders */}
      <div className="grid-2" style={{ alignItems: 'start' }}>
        {WEIGHT_META.map((meta, i) => {
          const val = draft[meta.key] ?? 0
          const pct = ((val - meta.min) / (meta.max - meta.min)) * 100
          return (
            <div key={meta.key} className="card" style={{ padding: '1.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '0.4rem' }}>
                <label htmlFor={`weight-${meta.key}`} style={{ fontWeight: 600, fontSize: '0.9rem' }}>{meta.label}</label>
                <span style={{
                  fontFamily: 'JetBrains Mono, monospace',
                  fontSize: '1.1rem',
                  fontWeight: 800,
                  color: 'var(--cyan)',
                  minWidth: '50px',
                  textAlign: 'right',
                }}>
                  {val}
                </span>
              </div>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.78rem', marginBottom: '0.75rem' }}>{meta.desc}</p>
              <input
                id={`weight-${meta.key}`}
                type="range"
                min={meta.min} max={meta.max} step={meta.step}
                value={val}
                onChange={e => set(meta.key, e.target.value)}
                style={{
                  width: '100%',
                  accentColor: 'var(--cyan)',
                  height: '6px',
                  cursor: 'pointer',
                }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>
                <span>{meta.min}</span>
                <div style={{
                  width: `${pct}%`,
                  height: '3px',
                  background: 'var(--cyan)',
                  borderRadius: '2px',
                  position: 'relative',
                  top: '-8px',
                  transition: 'width 0.15s',
                }} />
                <span>{meta.max}</span>
              </div>
            </div>
          )
        })}
      </div>

      {/* Formula explanation */}
      <div className="card" style={{ marginTop: '1.75rem', background: 'var(--bg-input)' }}>
        <div className="card-title" style={{ marginBottom: '0.75rem' }}>Risk Score Formula</div>
        <code style={{ fontSize: '0.88rem', color: 'var(--cyan)', display: 'block', lineHeight: '2' }}>
          Score = Sensitivity + Exposure + TypeBonus + CostBonus + min(Connections × PerEdge, Cap)
        </code>
        <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginTop: '0.5rem' }}>
          Score is capped at 100. Risk levels: Low &lt; 40, Medium 40–69, High ≥ 70.
        </div>
      </div>
    </div>
  )
}
