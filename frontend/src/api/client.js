/**
 * src/api/client.js
 *
 * Axios instance with:
 *  - Vite proxy forwarding to http://localhost:8000 during local development
 *  - VITE_API_URL pointing directly to the deployed API in production
 *  - X-API-Key header for backend auth
 */

import axios from 'axios'

const configuredApiUrl = import.meta.env.VITE_API_URL?.trim().replace(/\/+$/, '')

export const API_BASE_URL = configuredApiUrl || '/'
export const API_DOCS_URL = `${configuredApiUrl || 'http://localhost:8000'}/docs`

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': import.meta.env.VITE_API_KEY || 'dev-secret-key',
  },
})

// ── Primary data-input endpoints ──────────────────────────────────────────────
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('cloud_risk_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export const registerUser = (username, password) => api.post('/auth/register', { username, password })
export const loginUser = (username, password) => api.post(
  '/auth/token',
  new URLSearchParams({ username, password }),
  { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } },
)
export const getCurrentUser = () => api.get('/auth/me')

export const addResource      = (data) => api.post('/api/resources/', data)
export const addConnection    = (data) => api.post('/api/resources/connections/', data)
export const getAllData        = (skip = 0, limit = 20) => api.get(`/all-data?skip=${skip}&limit=${limit}`)
export const updateResource   = (id, data) => api.put(`/api/resources/${id}`, data)
export const deleteResource   = (id) => api.delete(`/api/resources/${id}`)
export const deleteConnection = (id) => api.delete(`/api/resources/connections/${id}`)

// ── Risk endpoints ────────────────────────────────────────────────────────────
export const getRiskAnalysis  = ()  => api.get('/risk-analysis')
export const recomputeRisk    = ()  => api.post('/recompute-risk')   // ← new: writes to DB

// ── Attack simulation ─────────────────────────────────────────────────────────
export const simulateAttack   = (start_node_uid) => api.post('/simulate-attack', { start_node_uid })
export const getCostImpact    = (start_node_uid) => api.post('/cost-impact', { start_node_uid })

// ── Chatbot ───────────────────────────────────────────────────────────────────
export const sendChatMessage  = (message, history = []) => api.post('/api/chat', { message, history })

// ── Reports ───────────────────────────────────────────────────────────────────
export const getReport        = ()       => api.get('/generate-report', { responseType: 'blob' })
export const getDocument      = (format) => api.get(`/api/documents/${format}`, { responseType: 'blob' })

// ── Graph endpoints ───────────────────────────────────────────────────────────
export const getGraph           = ()            => api.get('/api/graph/')
export const getBlastRadius     = (id)          => api.get(`/api/graph/blast-radius/${id}`)
export const getHighestRiskPath = ()            => api.get('/api/graph/highest-risk-path')
export const getCentrality      = ()            => api.get('/api/graph/centrality')
export const getAttackPath      = (src, tgt)   => api.get(`/api/graph/attack-path?source_id=${src}&target_id=${tgt}`)

// ── Risk alert endpoints ──────────────────────────────────────────────────────
export const getRiskAlerts  = ()    => api.get('/api/risks/alerts')
export const getRiskSummary = ()    => api.get('/api/risks/summary')
export const resolveAlert   = (id)  => api.patch(`/api/risks/alerts/${id}/resolve`)

// ── Admin: risk formula config ──────────────────────────────────────────
const getRiskConfig    = ()      => api.get('/admin/risk-config')
const updateRiskConfig = (data)  => api.put('/admin/risk-config', data)
export { getRiskConfig, updateRiskConfig }

export const approveAgentRun = (runId, note = '') =>
  api.post(`/api/agent/runs/${runId}/approval`, { approved: true, note })

export const rejectAgentRun = (runId, note = '') =>
  api.post(`/api/agent/runs/${runId}/approval`, { approved: false, note })

export default api
