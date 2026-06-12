/**
 * src/pages/DataInput.jsx
 *
 * Add cloud resources and define connections.
 * All fields have client-side validation with inline error messages.
 */

import { useState } from 'react'
import toast from 'react-hot-toast'
import { addResource, addConnection } from '../api/client'
import { PageHeader } from '../components/UIState'

// ── Validation rules ──────────────────────────────────────────────────────────

const UID_PATTERN = /^[A-Za-z0-9_-]+$/

function validateResourceForm(form) {
  const errors = {}

  // resource_uid
  if (!form.resource_uid.trim()) {
    errors.resource_uid = 'Resource ID is required.'
  } else if (form.resource_uid.length > 50) {
    errors.resource_uid = 'Resource ID must be 50 characters or fewer.'
  } else if (!UID_PATTERN.test(form.resource_uid)) {
    errors.resource_uid = 'Only letters, numbers, hyphens (-) and underscores (_) allowed.'
  }

  // name
  if (!form.name.trim()) {
    errors.name = 'Name is required.'
  } else if (form.name.length > 100) {
    errors.name = 'Name must be 100 characters or fewer.'
  }

  // cost
  const cost = parseFloat(form.cost)
  if (form.cost !== '' && (isNaN(cost) || cost < 0)) {
    errors.cost = 'Cost must be a positive number.'
  } else if (cost > 1_000_000) {
    errors.cost = 'Cost must be under $1,000,000.'
  }

  // region
  if (!form.region.trim()) {
    errors.region = 'Region is required.'
  } else if (form.region.length > 50) {
    errors.region = 'Region must be 50 characters or fewer.'
  }

  return errors
}

function validateConnectionForm(form) {
  const errors = {}

  if (!form.from_node.trim()) {
    errors.from_node = 'Source Resource ID is required.'
  } else if (!UID_PATTERN.test(form.from_node.trim())) {
    errors.from_node = 'Only letters, numbers, hyphens and underscores allowed.'
  }

  if (!form.to_node.trim()) {
    errors.to_node = 'Target Resource ID is required.'
  } else if (!UID_PATTERN.test(form.to_node.trim())) {
    errors.to_node = 'Only letters, numbers, hyphens and underscores allowed.'
  }

  if (form.from_node.trim() && form.to_node.trim() &&
      form.from_node.trim().toLowerCase() === form.to_node.trim().toLowerCase()) {
    errors.to_node = 'Source and target cannot be the same resource.'
  }

  return errors
}

// ── Shared inline error message ───────────────────────────────────────────────

function FieldError({ message }) {
  if (!message) return null
  return (
    <p style={{
      color: 'var(--rose)',
      fontSize: '0.78rem',
      marginTop: '0.3rem',
      display: 'flex',
      alignItems: 'center',
      gap: '0.3rem',
      animation: 'fadeIn 0.15s ease',
    }}>
      ⚠ {message}
    </p>
  )
}

// ── Resource form ─────────────────────────────────────────────────────────────

const EMPTY_RESOURCE = {
  resource_uid: '',
  name: '',
  resource_type: 'Server',
  cost: '',
  sensitivity: 'Low',
  public_access: false,
  provider: 'AWS',
  region: 'us-east-1',
}

function ResourceForm() {
  const [form, setForm]     = useState(EMPTY_RESOURCE)
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(false)

  const set = (field, value) => {
    setForm(curr => ({ ...curr, [field]: value }))
    // Clear that field's error as user types
    if (errors[field]) setErrors(curr => ({ ...curr, [field]: '' }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const newErrors = validateResourceForm(form)
    setErrors(newErrors)
    if (Object.keys(newErrors).length > 0) {
      toast.error('Please fix the errors before submitting.')
      return
    }

    setLoading(true)
    try {
      await addResource({ ...form, cost: parseFloat(form.cost) || 0 })
      toast.success(`Resource "${form.name}" added successfully.`)
      setForm(EMPTY_RESOURCE)
      setErrors({})
    } catch (err) {
      const detail = err.response?.data?.detail
      if (typeof detail === 'string') {
        toast.error(detail)
      } else {
        toast.error('Failed to add resource.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <div className="form-grid">

        {/* Resource ID */}
        <div className="form-group">
          <label className="form-label" htmlFor="res-uid">
            Resource ID <span style={{ color: 'var(--rose)' }}>*</span>
          </label>
          <input
            id="res-uid"
            className="form-input"
            placeholder="RES-001"
            value={form.resource_uid}
            onChange={e => set('resource_uid', e.target.value)}
            style={{ borderColor: errors.resource_uid ? 'var(--rose)' : undefined }}
          />
          <FieldError message={errors.resource_uid} />
          <p style={{ color: 'var(--text-muted)', fontSize: '0.73rem', marginTop: '0.25rem' }}>
            Letters, numbers, hyphens, underscores only.
          </p>
        </div>

        {/* Name */}
        <div className="form-group">
          <label className="form-label" htmlFor="res-name">
            Name <span style={{ color: 'var(--rose)' }}>*</span>
          </label>
          <input
            id="res-name"
            className="form-input"
            placeholder="Production Web Server"
            value={form.name}
            onChange={e => set('name', e.target.value)}
            style={{ borderColor: errors.name ? 'var(--rose)' : undefined }}
          />
          <FieldError message={errors.name} />
        </div>

        {/* Type */}
        <div className="form-group">
          <label className="form-label" htmlFor="res-type">Type</label>
          <select id="res-type" className="form-select" value={form.resource_type} onChange={e => set('resource_type', e.target.value)}>
            <option>Server</option>
            <option>Database</option>
            <option>Storage</option>
            <option>IAM</option>
          </select>
        </div>

        {/* Cost */}
        <div className="form-group">
          <label className="form-label" htmlFor="res-cost">Monthly Cost (USD)</label>
          <input
            id="res-cost"
            className="form-input"
            type="number"
            min="0"
            max="1000000"
            step="0.01"
            placeholder="0.00"
            value={form.cost}
            onChange={e => set('cost', e.target.value)}
            style={{ borderColor: errors.cost ? 'var(--rose)' : undefined }}
          />
          <FieldError message={errors.cost} />
        </div>

        {/* Sensitivity */}
        <div className="form-group">
          <label className="form-label" htmlFor="res-sensitivity">Sensitivity</label>
          <select id="res-sensitivity" className="form-select" value={form.sensitivity} onChange={e => set('sensitivity', e.target.value)}>
            <option>High</option>
            <option>Medium</option>
            <option>Low</option>
          </select>
        </div>

        {/* Provider */}
        <div className="form-group">
          <label className="form-label" htmlFor="res-provider">Provider</label>
          <select id="res-provider" className="form-select" value={form.provider} onChange={e => set('provider', e.target.value)}>
            <option>AWS</option>
            <option>GCP</option>
            <option>Azure</option>
          </select>
        </div>

        {/* Region */}
        <div className="form-group">
          <label className="form-label" htmlFor="res-region">
            Region <span style={{ color: 'var(--rose)' }}>*</span>
          </label>
          <input
            id="res-region"
            className="form-input"
            placeholder="us-east-1"
            value={form.region}
            onChange={e => set('region', e.target.value)}
            style={{ borderColor: errors.region ? 'var(--rose)' : undefined }}
          />
          <FieldError message={errors.region} />
        </div>

        {/* Public Access */}
        <div className="form-group">
          <label className="form-label">Public Access</label>
          <div className="toggle-row">
            <span style={{ color: form.public_access ? 'var(--rose)' : 'var(--text-muted)' }}>
              {form.public_access ? '⚠ Publicly accessible' : 'Private'}
            </span>
            <label className="toggle">
              <input
                type="checkbox"
                checked={form.public_access}
                onChange={e => set('public_access', e.target.checked)}
              />
              <span className="toggle-slider" />
            </label>
          </div>
        </div>

      </div>

      {/* Actions */}
      <div className="form-actions">
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => { setForm(EMPTY_RESOURCE); setErrors({}) }}
        >
          Reset
        </button>
        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? 'Saving…' : 'Add Resource'}
        </button>
      </div>
    </form>
  )
}

// ── Connection form ───────────────────────────────────────────────────────────

const EMPTY_CONN = { from_node: '', to_node: '', connection_type: 'network' }

function ConnectionForm() {
  const [form, setForm]     = useState(EMPTY_CONN)
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(false)

  const set = (field, value) => {
    setForm(curr => ({ ...curr, [field]: value }))
    if (errors[field]) setErrors(curr => ({ ...curr, [field]: '' }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const newErrors = validateConnectionForm(form)
    setErrors(newErrors)
    if (Object.keys(newErrors).length > 0) {
      toast.error('Please fix the errors before submitting.')
      return
    }

    setLoading(true)
    try {
      await addConnection(form)
      toast.success(`Connection ${form.from_node} → ${form.to_node} added.`)
      setForm(EMPTY_CONN)
      setErrors({})
    } catch (err) {
      const detail = err.response?.data?.detail
      if (typeof detail === 'string') {
        toast.error(detail)
      } else {
        toast.error('Failed to add connection.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <div className="form-grid">

        {/* From */}
        <div className="form-group">
          <label className="form-label" htmlFor="conn-from">
            From Resource ID <span style={{ color: 'var(--rose)' }}>*</span>
          </label>
          <input
            id="conn-from"
            className="form-input"
            placeholder="RES-001"
            value={form.from_node}
            onChange={e => set('from_node', e.target.value)}
            style={{ borderColor: errors.from_node ? 'var(--rose)' : undefined }}
          />
          <FieldError message={errors.from_node} />
        </div>

        {/* To */}
        <div className="form-group">
          <label className="form-label" htmlFor="conn-to">
            To Resource ID <span style={{ color: 'var(--rose)' }}>*</span>
          </label>
          <input
            id="conn-to"
            className="form-input"
            placeholder="RES-002"
            value={form.to_node}
            onChange={e => set('to_node', e.target.value)}
            style={{ borderColor: errors.to_node ? 'var(--rose)' : undefined }}
          />
          <FieldError message={errors.to_node} />
        </div>

        {/* Connection type */}
        <div className="form-group full">
          <label className="form-label" htmlFor="conn-type">Connection Type</label>
          <select id="conn-type" className="form-select" value={form.connection_type} onChange={e => set('connection_type', e.target.value)}>
            <option value="network">Network</option>
            <option value="iam">IAM / Permissions</option>
            <option value="data">Data Flow</option>
            <option value="api">API Call</option>
          </select>
        </div>

      </div>

      <div className="form-actions">
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => { setForm(EMPTY_CONN); setErrors({}) }}
        >
          Reset
        </button>
        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? 'Connecting…' : 'Add Connection'}
        </button>
      </div>
    </form>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function DataInput() {
  return (
    <div>
      <PageHeader
        title="Add Cloud Resources"
        description="Build the graph by adding inventory first, then defining directed connections. Fields marked * are required."
      />
      <div className="grid-2" style={{ alignItems: 'start' }}>
        <div className="card">
          <div className="card-title">Add Cloud Resource</div>
          <ResourceForm />
        </div>
        <div className="card">
          <div className="card-title">Define Connection</div>
          <ConnectionForm />
        </div>
      </div>
    </div>
  )
}
