import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Dev-only proxy: forwards /api/* and /socket.io/* to the Flask backend.
    // This makes `npm run dev` work without setting VITE_API_URL.
    // Has zero effect on the production build used in Docker / ECS / EB.
    proxy: {
      '/api': 'http://localhost:5000',
      '/socket.io': {
        target: 'http://localhost:5000',
        ws: true,
      },
    },
  },
})
