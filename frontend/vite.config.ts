import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  base: './',
  server: {
    proxy: {
      '/generate-reports': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/contact': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/register': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/login': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/verify-email': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/my-reports': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/download-report': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      }
    }
  }
})
