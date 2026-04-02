import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/** 前端构建配置。 */
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    globals: true,
  },
})
