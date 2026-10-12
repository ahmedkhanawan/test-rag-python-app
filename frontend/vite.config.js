import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react()],
    server: {
      // Dev only: forward /api to FastAPI so the backend needs no CORS config.
      proxy: {
        '/api': env.BACKEND_URL || 'http://localhost:8000',
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: './src/setupTests.js',
      globals: true,
    },
  }
})
