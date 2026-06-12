import React from 'react'

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('Page error boundary caught an error:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="empty-state">
          <div className="empty-icon">!</div>
          <h2>Something went wrong</h2>
          <p style={{ color: 'var(--rose)' }}>{this.state.error.message}</p>
        </div>
      )
    }

    return this.props.children
  }
}
