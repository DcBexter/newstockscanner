import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // Listen on all addresses
    watch: {
      usePolling: true, // This enables file system polling, better in Docker environments
      interval: 1000, // Poll every second
    },
    proxy: {
      '/api': {
        target: 'http://api_service:8000',
        changeOrigin: true,
      }
    }
  }
})
