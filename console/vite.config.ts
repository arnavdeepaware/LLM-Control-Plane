import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { proxy: Object.fromEntries(['/v1', '/admin', '/providers', '/meta', '/dev', '/ready', '/health'].map(path => [path, 'http://localhost:8000'])) },
  test: { environment: 'jsdom', setupFiles: './src/test/setup.ts', include: ['src/**/*.test.ts', 'src/**/*.test.tsx'] }
})
