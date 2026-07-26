import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // Frontend uses /api/* but backend routes don't have the /api prefix.
        // Strip the prefix when forwarding to backend.
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
