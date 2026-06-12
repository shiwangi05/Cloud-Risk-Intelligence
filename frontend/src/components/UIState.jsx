export function LoadingState({ message = 'Loading...' }) {
  return (
    <div className="loading-center">
      <div className="spinner" />
      <span>{message}</span>
    </div>
  )
}

export function EmptyState({ title = 'Nothing here yet', message, action }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">--</div>
      <h2>{title}</h2>
      {message && <p>{message}</p>}
      {action}
    </div>
  )
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">!</div>
      <h2>Something went wrong</h2>
      <p style={{ color: 'var(--rose)' }}>{message}</p>
      {onRetry && <button className="btn btn-secondary btn-sm" onClick={onRetry}>Retry</button>}
    </div>
  )
}

export function PageHeader({ title, description, action }) {
  return (
    <div className="page-header page-header-row">
      <div>
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {action}
    </div>
  )
}

export function StatCard({ label, value, tone = 'var(--cyan)', sub }) {
  return (
    <div className="stat-card">
      <span className="stat-label">{label}</span>
      <span className="stat-value" style={{ color: tone }}>{value}</span>
      {sub && <span className="stat-sub">{sub}</span>}
    </div>
  )
}
