/**
 * src/pages/ChatBot.jsx
 *
 * ARIA — Autonomous Risk Intelligence Agent
 * - Multi-turn context (last 10 messages sent to backend)
 * - Chat history persisted to localStorage
 * - Auto-send suggestion chips (single click)
 * - Chart Y-axis labels + hover tooltips
 * - ARIA agent panel with Approve / Reject buttons
 */

import { useState, useRef, useEffect, useCallback } from 'react'
import { sendChatMessage, approveAgentRun, rejectAgentRun } from '../api/client'
import toast from 'react-hot-toast'

const STORAGE_KEY = 'crip_chat_history'
const MAX_HISTORY = 10

const INITIAL_MESSAGE = {
  role: 'ai',
  text: "Hi! I'm ARIA — Autonomous Risk Intelligence Agent.\n\nI can help with:\n- Inventory summaries, risk scores, alerts, cost impact\n- Graph intelligence, blast radius, attack paths\n- Security recommendations and remediation\n\nTip: Say 'investigate' or click 🔍 Investigate to activate agentic mode where I plan, run tools, and reason step-by-step.",
  typing: false,
}

// ── Formatted message renderer ─────────────────────────────────────────────────

function FormattedMessage({ text, typing }) {
  const [displayed, setDisplayed] = useState(typing ? '' : text)

  useEffect(() => {
    if (!typing) { setDisplayed(text); return }
    let i = 0
    const interval = setInterval(() => {
      setDisplayed(text.slice(0, i))
      i += 1
      if (i > text.length) clearInterval(interval)
    }, 12)
    return () => clearInterval(interval)
  }, [text, typing])

  return (
    <div style={{ lineHeight: '1.6' }}>
      {displayed.split('\n').map((line, idx) => {
        const trimmed = line.trim()
        if (trimmed.startsWith('-')) {
          return (
            <li key={idx} style={{ margin: '0.25rem 0 0.25rem 1.5rem', listStyleType: 'disc' }}>
              {trimmed.substring(1).trim()}
            </li>
          )
        }
        return <div key={idx} style={{ minHeight: trimmed ? 'auto' : '0.5rem', marginBottom: '0.2rem' }}>{line}</div>
      })}
    </div>
  )
}

// ── Chart component ────────────────────────────────────────────────────────────

function ChartLegend({ chart, colors }) {
  return (
    <div className="chart-legend">
      {chart.labels.map((label, index) => (
        <div className="chart-legend-row" key={`${label}-${index}`}>
          <span className="chart-swatch" style={{ background: colors[index % colors.length] }} />
          <span>{label}</span>
          <strong>{chart.values[index]}</strong>
        </div>
      ))}
    </div>
  )
}

function Tooltip({ label, value, color, x, y, visible }) {
  if (!visible) return null
  return (
    <foreignObject x={x - 50} y={y - 44} width="100" height="38" style={{ overflow: 'visible', pointerEvents: 'none' }}>
      <div style={{
        background: 'var(--bg-card)',
        border: `1px solid ${color}`,
        borderRadius: '6px',
        padding: '3px 8px',
        fontSize: '0.72rem',
        color: 'var(--text)',
        textAlign: 'center',
        whiteSpace: 'nowrap',
        boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
      }}>
        <strong style={{ color }}>{label}</strong>: {value}
      </div>
    </foreignObject>
  )
}

function ChartArtifact({ chart }) {
  const [hoveredIdx, setHoveredIdx] = useState(null)
  const total = chart.values.reduce((sum, v) => sum + Number(v || 0), 0) || 1
  const colors = ['#22d3ee', '#818cf8', '#fb7185', '#fbbf24', '#34d399', '#38bdf8', '#a78bfa', '#f97316']
  const max = Math.max(...chart.values.map(v => Number(v || 0)), 1)

  if (chart.type === 'pie') {
    let cumulative = 0
    const gradient = chart.values.map((v, i) => {
      const start = (cumulative / total) * 100
      cumulative += Number(v || 0)
      const end = (cumulative / total) * 100
      return `${colors[i % colors.length]} ${start}% ${end}%`
    }).join(', ')
    return (
      <div className="chart-artifact">
        <div className="pie-chart" style={{ background: `conic-gradient(${gradient})` }} />
        <ChartLegend chart={chart} colors={colors} />
      </div>
    )
  }

  if (chart.type === 'line' || chart.type === 'area' || chart.type === 'scatter') {
    const width = 360; const height = 180
    const padL = 42; const padB = 24; const padT = 12; const padR = 18
    const points = chart.values.map((v, i) => ({
      x: chart.values.length === 1 ? width / 2 : padL + (i * (width - padL - padR)) / (chart.values.length - 1),
      y: height - padB - (Number(v || 0) / max) * (height - padB - padT),
      v: Number(v || 0),
    }))
    const path = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ')
    const areaPath = `${path} L ${points.at(-1)?.x || padL} ${height - padB} L ${points[0]?.x || padL} ${height - padB} Z`
    const yTicks = [0, 0.25, 0.5, 0.75, 1].map(f => ({ v: (f * max).toFixed(1), y: height - padB - f * (height - padB - padT) }))
    return (
      <div className="chart-artifact chart-artifact-wide">
        <svg className="line-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${chart.type} chart`}>
          {yTicks.map((t, i) => (
            <g key={i}>
              <line x1={padL - 4} y1={t.y} x2={padL} y2={t.y} stroke="var(--border)" strokeWidth="1" />
              <text x={padL - 6} y={t.y + 4} fontSize="9" fill="var(--text-faint)" textAnchor="end">{t.v}</text>
            </g>
          ))}
          <line x1={padL} y1={height - padB} x2={width - padR} y2={height - padB} className="chart-axis" />
          <line x1={padL} y1={padT} x2={padL} y2={height - padB} className="chart-axis" />
          {chart.type === 'area' && <path d={areaPath} className="area-fill" />}
          {chart.type !== 'scatter' && <path d={path} className="line-path" />}
          {points.map((p, i) => (
            <g key={i}>
              <circle cx={p.x} cy={p.y} r={hoveredIdx === i ? 7 : 5} className="line-point"
                style={{ cursor: 'pointer', transition: 'r 0.15s' }}
                onMouseEnter={() => setHoveredIdx(i)} onMouseLeave={() => setHoveredIdx(null)} />
              <text x={p.x} y={height - padB + 14} fontSize="9" fill="var(--text-faint)" textAnchor="middle">
                {(chart.labels[i] || '').slice(0, 8)}
              </text>
              <Tooltip label={chart.labels[i] || ''} value={p.v} color={colors[i % colors.length]} x={p.x} y={p.y} visible={hoveredIdx === i} />
            </g>
          ))}
        </svg>
        <ChartLegend chart={chart} colors={colors} />
      </div>
    )
  }

  // Bar chart
  return (
    <div className="chart-artifact chart-artifact-wide">
      <div className="bar-chart">
        {chart.labels.map((label, i) => (
          <div className="bar-row" key={`${label}-${i}`} title={`${label}: ${chart.values[i]}`}
            onMouseEnter={() => setHoveredIdx(i)} onMouseLeave={() => setHoveredIdx(null)}
            style={{ cursor: 'default' }}>
            <span>{label}</span>
            <div className="bar-track">
              <div className="bar-fill" style={{
                width: `${(Number(chart.values[i] || 0) / max) * 100}%`,
                background: colors[i % colors.length],
                transition: 'width 0.4s ease',
                boxShadow: hoveredIdx === i ? `0 0 8px ${colors[i % colors.length]}88` : 'none',
              }} />
            </div>
            <strong style={{ color: hoveredIdx === i ? colors[i % colors.length] : undefined, transition: 'color 0.2s' }}>
              {chart.values[i]}
            </strong>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── ARIA Agent Panel ───────────────────────────────────────────────────────────

function AgentArtifact({ agent, onDecision }) {
  if (!agent) return null

  // Seed from persisted data so decisions survive page refresh
  const [approvalState, setApprovalState] = useState(agent.approvalState || null)
  const [approving,     setApproving]     = useState(false)
  const [executedActions, setExecutedActions] = useState(agent.executedActions || [])

  const agentName = agent.name || 'ARIA'

  const handleDecision = async (approved) => {
    setApproving(true)
    try {
      if (approved) {
        const res = await approveAgentRun(agent.run_id)
        const approvalStep = (res.data.steps || []).find(s => s.tool === 'human_approval')
        const actions = approvalStep?.executed_actions || []
        setExecutedActions(actions)
        setApprovalState('approved')
        onDecision?.('approved', actions)   // ← persist into message/localStorage
        if (actions.length > 0) {
          toast.success(`ARIA executed ${actions.length} action(s) automatically.`)
        } else {
          toast.success('Plan approved. No automated changes were applicable to current data.')
        }
      } else {
        await rejectAgentRun(agent.run_id)
        setApprovalState('rejected')
        onDecision?.('rejected', [])        // ← persist into message/localStorage
        toast('Plan rejected and recorded.', { icon: '🚫' })
      }
    } catch {
      toast.error('Could not record decision. Check the backend is running.')
    } finally {
      setApproving(false)
    }
  }

  const statusColor = approvalState === 'approved' ? '#52c97a'
    : approvalState === 'rejected' ? '#e5626a'
    : agent.approval_required ? '#e8b84b' : '#52c97a'

  const statusLabel = approvalState === 'approved' ? '✓ Approved'
    : approvalState === 'rejected' ? '✗ Rejected'
    : agent.approval_required ? '⚠ Approval Required' : '✓ Autonomous'

  return (
    <div className="aria-panel">
      {/* Header */}
      <div className="aria-header">
        <div className="aria-avatar">A</div>
        <div>
          <div className="aria-name">{agentName} — Autonomous Risk Intelligence Agent</div>
          <div className="aria-meta">Run #{agent.run_id} &nbsp;·&nbsp; {agent.iterations} tool{agent.iterations !== 1 ? 's' : ''} executed &nbsp;·&nbsp; v{agent.version || '1.0'}</div>
        </div>
        <span className="aria-status" style={{
          background: statusColor + '18',
          color: statusColor,
          borderColor: statusColor + '55',
        }}>
          {statusLabel}
        </span>
      </div>

      {/* Plan */}
      {Array.isArray(agent.plan) && agent.plan.length > 0 && (
        <div className="aria-section">
          <div className="aria-section-title">📋 Plan</div>
          {agent.plan.map((item, i) => (
            <div key={i} className="aria-step">
              <span className="aria-step-num">{i + 1}</span>
              <div>
                <span className="aria-tool-name">{item.tool}</span>
                <span className="aria-step-reason">{item.reason}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Tool Results */}
      {Array.isArray(agent.steps) && agent.steps.length > 0 && (
        <div className="aria-section">
          <div className="aria-section-title">🔧 Tool Results</div>
          {agent.steps.map((step, i) => (
            <div key={i} className="aria-result">
              <div className="aria-result-header">
                <code className="aria-tool-code">{step.tool}</code>
                <span className={`aria-result-status ${step.status === 'completed' ? 'aria-ok' : step.status === 'needs_approval' ? 'aria-warn' : 'aria-skip'}`}>
                  {step.status}
                </span>
              </div>
              <div className="aria-result-finding">{step.finding}</div>
            </div>
          ))}
        </div>
      )}

      {/* Recommendations */}
      {Array.isArray(agent.recommendations) && agent.recommendations.length > 0 && (
        <div className="aria-section">
          <div className="aria-section-title">💡 Recommendations <span style={{ fontSize: '0.7rem', color: 'var(--text-faint)' }}>— require human approval before execution</span></div>
          {agent.recommendations.map((rec, i) => (
            <div key={i} className="aria-rec">{rec}</div>
          ))}
        </div>
      )}

      {/* Approve / Reject buttons */}
      {agent.approval_required && (
        <div className="aria-approval">
          {!approvalState ? (
            <>
              <p className="aria-approval-hint">
                ARIA has drafted remediation proposals above. Review them and decide —{' '}
                <strong>no changes are executed automatically.</strong>
              </p>
              <div className="aria-approval-actions">
                <button className="btn btn-primary btn-sm" onClick={() => handleDecision(true)} disabled={approving}>
                  {approving ? 'Recording…' : '✓ Approve Plan'}
                </button>
                <button className="btn btn-danger btn-sm" onClick={() => handleDecision(false)} disabled={approving}>
                  ✗ Reject Plan
                </button>
              </div>
            </>
          ) : (
            <div className="aria-approval-done">
              {approvalState === 'approved' ? (
                <>
                  <p style={{ color: '#52c97a', fontWeight: 600, margin: '0 0 0.5rem' }}>
                    ✓ Plan approved — ARIA executed {executedActions.length} action{executedActions.length !== 1 ? 's' : ''} automatically.
                  </p>
                  {executedActions.length > 0 ? (
                    <div className="aria-exec-list">
                      {executedActions.map((action, i) => (
                        <div key={i} className="aria-exec-item">
                          <span className="aria-exec-icon">⚡</span>
                          {action}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p style={{ color: 'var(--text-faint)', fontSize: '0.78rem', margin: 0 }}>
                      No automated changes were applicable to the current data. All resources may already be compliant.
                    </p>
                  )}
                </>
              ) : (
                <p style={{ color: '#e5626a', fontWeight: 600, margin: 0 }}>
                  ✗ Plan rejected. No changes were made.
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Main ChatBot page ──────────────────────────────────────────────────────────

export default function ChatBot() {
  const [messages, setMessages] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const parsed = JSON.parse(stored)
        return Array.isArray(parsed) && parsed.length > 0
          ? parsed.map(m => ({ ...m, typing: false }))
          : [INITIAL_MESSAGE]
      }
    } catch { /* ignore corrupt storage */ }
    return [INITIAL_MESSAGE]
  })
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(messages)) }
    catch { /* quota exceeded */ }
  }, [messages])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const buildHistory = useCallback((msgs) =>
    msgs.slice(-MAX_HISTORY).map(m => ({ role: m.role, text: m.text }))
  , [])

  const doSend = useCallback(async (text) => {
    if (!text.trim() || loading) return
    const userMessage = text.trim()
    setMessages(prev => prev.map(m => ({ ...m, typing: false })).concat({ role: 'user', text: userMessage }))
    setInput('')
    setLoading(true)
    try {
      const history = buildHistory(messages)
      const res = await sendChatMessage(userMessage, history)
      setMessages(prev => [...prev, {
        role: 'ai',
        text: res.data.reply,
        chart: res.data.chart,
        agent: res.data.agent,
        typing: !res.data.agent, // don't type-animate when ARIA card shown
      }])
    } catch (err) {
      const detail = err.response?.data?.detail
      const isRateLimit = err.response?.status === 429
      setMessages(prev => [...prev, {
        role: 'ai',
        text: isRateLimit
          ? '⏱ Rate limit reached. Please wait a moment before sending another message.'
          : (detail || 'Sorry, I encountered an error. Check that the backend API is running.'),
        typing: false,
      }])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }, [loading, messages, buildHistory])

  const handleSend = (e) => { e.preventDefault(); doSend(input) }
  const handleChip = (text) => doSend(text)

  const clearChat = () => {
    setMessages([INITIAL_MESSAGE])
    localStorage.removeItem(STORAGE_KEY)
    toast.success('Chat cleared.')
  }

  const copyMessage = async (text) => {
    try { await navigator.clipboard.writeText(text); toast.success('Copied.') }
    catch { toast.error('Could not copy.') }
  }

  const suggestions = [
    { label: '📊 Summary',     text: 'Show inventory summary',                  className: 'badge-cyan' },
    { label: '🔍 Investigate', text: 'Investigate and triage all cloud risks',   className: 'badge-violet' },
    { label: '🔥 Most Risky',  text: 'Which node is most risky?',               className: 'badge-rose' },
    { label: '🕸 Graph Stats', text: 'Show graph stats',                        className: 'badge-amber' },
    { label: '🚨 Alerts',      text: 'Show open risk alerts',                   className: 'badge-rose' },
    { label: '💡 Recommend',   text: 'Give me security recommendations',        className: 'badge-emerald' },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '80vh', gap: '1rem' }}>
      <div className="page-header" style={{ marginBottom: '0', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1>ARIA — Risk Intelligence Agent</h1>
          <p>Autonomous Risk Intelligence Agent &nbsp;·&nbsp; Ask questions or click <strong>🔍 Investigate</strong> to activate agentic mode.</p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={clearChat} title="Clear conversation">
          🗑 Clear
        </button>
      </div>

      <div className="card chat-shell" style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden', border: '1px solid var(--border)', boxShadow: '0 4px 20px rgba(0,0,0,0.08)' }}>

        {/* Message list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem', background: 'var(--bg-base)' }}>
          {messages.map((m, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start' }}>

              {/* ARIA avatar */}
              {m.role === 'ai' && (
                <div style={{
                  width: '32px', height: '32px', borderRadius: '8px',
                  background: 'var(--blue)', color: '#fff',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  marginRight: '0.75rem', flexShrink: 0,
                  fontSize: '0.6rem', fontWeight: 800, letterSpacing: '0.05em',
                }}>
                  ARIA
                </div>
              )}

              {/* Bubble */}
              <div style={{
                position: 'relative',
                maxWidth: m.agent ? '90%' : '75%',
                padding: m.agent ? '0' : '1rem 1.25rem',
                borderRadius: '14px',
                borderTopLeftRadius: m.role === 'ai' ? '4px' : '14px',
                borderBottomRightRadius: m.role === 'user' ? '4px' : '14px',
                background: m.agent ? 'transparent' : (m.role === 'user' ? 'var(--blue)' : 'var(--bg-card)'),
                color: m.role === 'user' ? '#fff' : 'var(--text)',
                border: (m.role === 'ai' && !m.agent) ? '1px solid var(--border)' : 'none',
                boxShadow: (m.role === 'ai' && !m.agent) ? '0 2px 8px rgba(0,0,0,0.06)' : 'none',
              }}>
                {/* Show text only for non-agent messages */}
                {!m.agent && <FormattedMessage text={m.text} typing={m.typing} />}
                {m.chart && <ChartArtifact chart={m.chart} />}
                {m.agent && <AgentArtifact
                  agent={m.agent}
                  onDecision={(state, actions) => {
                    // Write decision into the message object → triggers localStorage save
                    setMessages(prev => prev.map((msg, idx) =>
                      idx === i
                        ? { ...msg, agent: { ...msg.agent, approvalState: state, executedActions: actions } }
                        : msg
                    ))
                  }}
                />}
                {m.role === 'ai' && !m.agent && (
                  <button className="btn btn-secondary btn-sm" style={{ marginTop: '0.75rem' }} onClick={() => copyMessage(m.text)}>
                    Copy
                  </button>
                )}
              </div>

              {/* User avatar */}
              {m.role === 'user' && (
                <div style={{
                  width: '32px', height: '32px', borderRadius: '8px',
                  background: 'var(--bg-subtle)', border: '1px solid var(--border)',
                  color: 'var(--text-dim)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  marginLeft: '0.75rem', flexShrink: 0,
                  fontSize: '0.65rem', fontWeight: 700,
                }}>
                  You
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
              <div style={{
                width: '32px', height: '32px', borderRadius: '8px',
                background: 'var(--blue)', color: '#fff',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                marginRight: '0.75rem', flexShrink: 0,
                fontSize: '0.6rem', fontWeight: 800,
              }}>ARIA</div>
              <div style={{ padding: '1rem 1.25rem', borderRadius: '14px', borderTopLeftRadius: '4px', background: 'var(--bg-card)', border: '1px solid var(--border)', display: 'flex', gap: '5px', alignItems: 'center' }}>
                {[0, 1, 2].map(i => (
                  <span key={i} style={{
                    width: '7px', height: '7px', borderRadius: '50%', background: 'var(--blue)',
                    animation: `chatDot 1.2s ${i * 0.2}s ease-in-out infinite`,
                    display: 'inline-block',
                  }} />
                ))}
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Suggestion chips */}
        <div className="suggestion-row" style={{ padding: '0.75rem 1.5rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap', borderTop: '1px solid var(--border)', background: 'var(--bg-card)' }}>
          {suggestions.map(s => (
            <button
              key={s.label}
              className={`badge ${s.className}`}
              style={{ cursor: 'pointer', border: 'none', padding: '0.45rem 0.9rem', fontSize: '0.82rem', transition: 'transform 0.12s, opacity 0.12s' }}
              onClick={() => handleChip(s.text)}
              disabled={loading}
              title={s.text}
            >
              {s.label}
            </button>
          ))}
        </div>

        {/* Input bar */}
        <div style={{ padding: '1rem 1.5rem', background: 'var(--bg-base)', borderTop: '1px solid var(--border)' }}>
          <form style={{ display: 'flex', gap: '0.75rem' }} onSubmit={handleSend}>
            <input
              ref={inputRef}
              className="input-field chat-input"
              style={{ flex: 1, borderRadius: '24px', padding: '0.75rem 1.5rem', background: 'var(--bg-input)', border: '1px solid var(--border)' }}
              placeholder="Ask anything about your cloud risk platform..."
              value={input}
              onChange={e => setInput(e.target.value)}
              disabled={loading}
            />
            <button className="btn btn-primary" type="submit" disabled={loading || !input.trim()} style={{ borderRadius: '24px', padding: '0.75rem 1.5rem', fontWeight: 'bold' }}>
              Send
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
