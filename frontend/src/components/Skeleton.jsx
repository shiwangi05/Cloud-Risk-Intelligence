/**
 * src/components/Skeleton.jsx
 * Animated skeleton loading placeholders.
 */

const pulse = {
  background: 'linear-gradient(90deg, var(--bg-input) 25%, var(--border) 50%, var(--bg-input) 75%)',
  backgroundSize: '200% 100%',
  animation: 'skeletonPulse 1.4s ease infinite',
  borderRadius: 'var(--radius-sm)',
}

export function SkeletonLine({ width = '100%', height = '14px', style = {} }) {
  return <div style={{ ...pulse, width, height, marginBottom: '0.5rem', ...style }} />
}

export function SkeletonCard({ rows = 4, style = {} }) {
  return (
    <div className="card" style={{ ...style }}>
      <SkeletonLine width="40%" height="18px" style={{ marginBottom: '1rem' }} />
      {Array.from({ length: rows }).map((_, i) => (
        <SkeletonLine key={i} width={i % 3 === 0 ? '70%' : i % 3 === 1 ? '90%' : '55%'} />
      ))}
    </div>
  )
}

export function SkeletonTable({ rows = 5, cols = 6 }) {
  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      {/* Header */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${cols}, 1fr)`,
        gap: '1rem',
        padding: '1rem 1.25rem',
        borderBottom: '1px solid var(--border)',
      }}>
        {Array.from({ length: cols }).map((_, i) => (
          <SkeletonLine key={i} height="12px" width="60%" style={{ marginBottom: 0 }} />
        ))}
      </div>
      {/* Rows */}
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${cols}, 1fr)`,
          gap: '1rem',
          padding: '0.9rem 1.25rem',
          borderBottom: '1px solid var(--border)',
        }}>
          {Array.from({ length: cols }).map((_, c) => (
            <SkeletonLine key={c} height="12px" width={c === 0 ? '80%' : '60%'} style={{ marginBottom: 0 }} />
          ))}
        </div>
      ))}
    </div>
  )
}

export function SkeletonStatGrid({ count = 4 }) {
  return (
    <div className={`grid-${count}`} style={{ marginBottom: '1.75rem' }}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="card" style={{ padding: '1.25rem' }}>
          <SkeletonLine width="50%" height="12px" />
          <SkeletonLine width="35%" height="28px" />
        </div>
      ))}
    </div>
  )
}
