import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/auth': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/all-data': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/risk-analysis': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/recompute-risk': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/simulate-attack': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/generate-report': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/cost-impact': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/admin': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
