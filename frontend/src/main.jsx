import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import App from './App.jsx'
import { AuthProvider } from './context/AuthContext.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: '#222737',
            color: '#dde2f0',
            border: '1px solid #323850',
            borderRadius: '8px',
            fontFamily: 'Inter, sans-serif',
            fontSize: '0.875rem',
          },
          success: { iconTheme: { primary: '#52c97a', secondary: '#1a1f2e' } },
          error:   { iconTheme: { primary: '#e5626a', secondary: '#1a1f2e' } },
        }}
      />
    </BrowserRouter>
  </React.StrictMode>,
)
