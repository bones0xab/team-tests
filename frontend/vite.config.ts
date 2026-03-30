import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react({
      babel: {
        plugins: [['babel-plugin-react-compiler']],
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      // Proxy REST API calls
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('error', (err) => {
            // Suppress ECONNRESET / ECONNABORTED during uvicorn hot-reload
            if (!['ECONNRESET', 'ECONNABORTED', 'ECONNREFUSED'].includes((err as any).code)) {
              console.error('[api proxy error]', err.message);
            }
          });
        },
      },
      // Proxy WebSocket connections
      '/ws': {
        target: 'http://localhost:8000',
        ws: true,
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('error', (err) => {
            // Suppress noisy socket errors caused by uvicorn hot-reload dropping WS connections
            if (!['ECONNRESET', 'ECONNABORTED', 'ECONNREFUSED'].includes((err as any).code)) {
              console.error('[ws proxy error]', err.message);
            }
          });
        },
      },
    },
  },
})


