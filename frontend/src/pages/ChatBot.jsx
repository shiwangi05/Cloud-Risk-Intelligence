/**
 * src/pages/ChatBot.jsx
 *
 * AI Risk Assistant with:
 * - Multi-turn context (last 10 messages sent to backend)
 * - Chat history persisted to localStorage
 * - Auto-send suggestion chips (single click)
 * - Chart Y-axis labels + hover tooltips
 * - Clear Chat button
 */

import { useState, useRef, useEffect, useCallback } from 'react'
import { sendChatMessage } from '../api/client'
import toast from 'react-hot-toast'

const STORAGE_KEY = 'crip_chat_history'
const MAX_HISTORY = 10   // messages sent to backend for context

const INITIAL_MESSAGE = {
  role: 'ai',
  text: "Hello! I am your Cloud Risk Intelligence assistant.\n\nI can help with:\n- project overview, APIs, data model, and risk formula\n- inventory summaries, resources, connections, graph stats, and alerts\n- risk analysis, blast radius, attack paths, cost impact, reports, and recommendations",
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

// ── Chart component with Y-axis labels + tooltips ──────────────────────────────

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
        color: 'var(--text-primary)',
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
          {/* Y-axis ticks */}
          {yTicks.map((t, i) => (
            <g key={i}>
              <line x1={padL - 4} y1={t.y} x2={padL} y2={t.y} stroke="var(--border)" strokeWidth="1" />
              <text x={padL - 6} y={t.y + 4} fontSize="9" fill="var(--text-muted)" textAnchor="end">{t.v}</text>
            </g>
          ))}
          <line x1={padL} y1={height - padB} x2={width - padR} y2={height - padB} className="chart-axis" />
          <line x1={padL} y1={padT} x2={padL} y2={height - padB} className="chart-axis" />
          {chart.type === 'area' && <path d={areaPath} className="area-fill" />}
          {chart.type !== 'scatter' && <path d={path} className="line-path" />}
          {points.map((p, i) => (
            <g key={i}>
              <circle
                cx={p.x} cy={p.y} r={hoveredIdx === i ? 7 : 5}
                className="line-point"
                style={{ cursor: 'pointer', transition: 'r 0.15s' }}
                onMouseEnter={() => setHoveredIdx(i)}
                onMouseLeave={() => setHoveredIdx(null)}
              />
              {/* X label */}
              <text x={p.x} y={height - padB + 14} fontSize="9" fill="var(--text-muted)" textAnchor="middle">
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
          <div
            className="bar-row"
            key={`${label}-${i}`}
            title={`${label}: ${chart.values[i]}`}
            onMouseEnter={() => setHoveredIdx(i)}
            onMouseLeave={() => setHoveredIdx(null)}
            style={{ cursor: 'default' }}
          >
            <span>{label}</span>
            <div className="bar-track">
              <div
                className="bar-fill"
                style={{
                  width: `${(Number(chart.values[i] || 0) / max) * 100}%`,
                  background: colors[i % colors.length],
                  transition: 'width 0.4s ease',
                  boxShadow: hoveredIdx === i ? `0 0 8px ${colors[i % colors.length]}88` : 'none',
                }}
              />
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

// ── Main ChatBot page ──────────────────────────────────────────────────────────

function AgentArtifact({ agent }) {
  if (!agent) return null

  return (
    <div style={{
      marginTop: '0.9rem',
      padding: '0.9rem',
      borderRadius: '10px',
      background: 'var(--bg-input)',
      border: '1px solid var(--border)',
      display: 'grid',
      gap: '0.65rem',
    }}>
      <div style={{ fontWeight: 800, color: 'var(--cyan)' }}>
        Agent Run #{agent.run_id}
      </div>
      <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
        {agent.approval_required ? 'Human approval required before remediation.' : 'No approval-gated action suggested.'}
      </div>
      {Array.isArray(agent.plan) && agent.plan.length > 0 && (
        <div>
          <div style={{ fontWeight: 700, marginBottom: '0.35rem' }}>Plan</div>
          {agent.plan.map((item, index) => (
            <div key={`${item.tool}-${index}`} style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
              - {item.tool}: {item.reason}
            </div>
          ))}
        </div>
      )}
      {Array.isArray(agent.steps) && agent.steps.length > 0 && (
        <div>
          <div style={{ fontWeight: 700, marginBottom: '0.35rem' }}>Tool Steps</div>
          {agent.steps.map((item, index) => (
            <div key={`${item.tool}-${index}`} style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
              - {item.tool} ({item.status})
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function ChatBot() {
  const [messages, setMessages] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const parsed = JSON.parse(stored)
        return Array.isArray(parsed) && parsed.length > 0
          ? parsed.map(m => ({ ...m, typing: false }))   // never replay typing on restore
          : [INITIAL_MESSAGE]
      }
    } catch { /* ignore corrupt storage */ }
    return [INITIAL_MESSAGE]
  })
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  // Persist messages to localStorage on every change
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(messages))
    } catch { /* quota exceeded */ }
  }, [messages])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const buildHistory = useCallback((msgs) => {
    // Send last MAX_HISTORY messages (excluding the current one being sent)
    return msgs
      .slice(-MAX_HISTORY)
      .map(m => ({ role: m.role, text: m.text }))
  }, [])

  const doSend = useCallback(async (text) => {
    if (!text.trim() || loading) return
    const userMessage = text.trim()

    setMessages(prev => {
      const updated = prev.map(m => ({ ...m, typing: false })).concat({ role: 'user', text: userMessage })
      return updated
    })
    setInput('')
    setLoading(true)

    try {
      // Build history from current messages before adding user message
      const history = buildHistory(messages)
      const res = await sendChatMessage(userMessage, history)
      setMessages(prev => [...prev, { role: 'ai', text: res.data.reply, chart: res.data.chart, agent: res.data.agent, typing: true }])
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

  const handleSend = (e) => {
    e.preventDefault()
    doSend(input)
  }

  // Auto-send on chip click (single click, no extra submit needed)
  const handleChip = (text) => {
    doSend(text)
  }

  const clearChat = () => {
    setMessages([INITIAL_MESSAGE])
    localStorage.removeItem(STORAGE_KEY)
    toast.success('Chat cleared.')
  }

  const copyMessage = async (text) => {
    try {
      await navigator.clipboard.writeText(text)
      toast.success('Copied.')
    } catch {
      toast.error('Could not copy.')
    }
  }

  const suggestions = [
    { label: '📊 Summary',     text: 'Show inventory summary',              className: 'badge-cyan' },
    { label: '🔥 Most Risky',  text: 'Which node is most risky?',           className: 'badge-rose' },
    { label: '🕸 Graph Stats', text: 'Show graph stats',                    className: 'badge-amber' },
    { label: '📈 Chart',       text: 'Generate a bar chart of resource types', className: 'badge-violet' },
    { label: '🚨 Alerts',      text: 'Show open risk alerts',               className: 'badge-rose' },
    { label: '💡 Recommend',   text: 'Give me security recommendations',    className: 'badge-emerald' },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '80vh', gap: '1rem' }}>
      <div className="page-header" style={{ marginBottom: '0', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1>AI Risk Assistant</h1>
          <p>Ask about the platform, APIs, inventory, graph intelligence, risk, cost, alerts, and reports.</p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={clearChat} title="Clear conversation">
          🗑 Clear Chat
        </button>
      </div>

      <div className="card chat-shell" style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden', border: '1px solid var(--border)', boxShadow: '0 8px 30px rgba(0,0,0,0.15)' }}>

        {/* Message list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem', background: 'var(--bg-base)' }}>
          {messages.map((m, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start' }}>
              {m.role === 'ai' && (
                <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: 'var(--cyan)', color: '#001018', display: 'flex', alignItems: 'center', justifyContent: 'center', marginRight: '0.75rem', flexShrink: 0, fontSize: '0.72rem', fontWeight: 800 }}>
                  AI
                </div>
              )}
              <div style={{
                position: 'relative',
                maxWidth: '75%',
                padding: '1rem 1.25rem',
                borderRadius: '16px',
                borderTopLeftRadius: m.role === 'ai' ? '4px' : '16px',
                borderBottomRightRadius: m.role === 'user' ? '4px' : '16px',
                background: m.role === 'user' ? 'linear-gradient(135deg, var(--cyan) 0%, rgb(18,168,192) 100%)' : 'var(--bg-card)',
                color: m.role === 'user' ? '#fff' : 'var(--text-primary)',
                border: m.role === 'ai' ? '1px solid var(--border)' : 'none',
                boxShadow: m.role === 'ai' ? '0 4px 15px rgba(0,0,0,0.05)' : '0 4px 15px rgba(34,211,238,0.2)',
              }}>
                <FormattedMessage text={m.text} typing={m.typing} />
                {m.chart && <ChartArtifact chart={m.chart} />}
                {m.agent && <AgentArtifact agent={m.agent} />}
                {m.role === 'ai' && (
                  <button className="btn btn-secondary btn-sm" style={{ marginTop: '0.75rem' }} onClick={() => copyMessage(m.text)}>
                    Copy
                  </button>
                )}
              </div>
              {m.role === 'user' && (
                <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: 'var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginLeft: '0.75rem', flexShrink: 0, fontSize: '0.7rem', fontWeight: 800 }}>
                  You
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
              <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: 'var(--cyan)', color: '#001018', display: 'flex', alignItems: 'center', justifyContent: 'center', marginRight: '0.75rem', flexShrink: 0, fontSize: '0.72rem', fontWeight: 800 }}>AI</div>
              <div style={{ padding: '1rem 1.25rem', borderRadius: '16px', borderTopLeftRadius: '4px', background: 'var(--bg-card)', border: '1px solid var(--border)', display: 'flex', gap: '5px', alignItems: 'center' }}>
                {[0, 1, 2].map(i => (
                  <span key={i} style={{
                    width: '7px', height: '7px', borderRadius: '50%', background: 'var(--cyan)',
                    animation: `chatDot 1.2s ${i * 0.2}s ease-in-out infinite`,
                    display: 'inline-block',
                  }} />
                ))}
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Suggestion chips — single click auto-sends */}
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

        {/* Input */}
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
