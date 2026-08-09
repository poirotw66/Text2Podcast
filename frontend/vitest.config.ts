import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Separate from vite.config.ts on purpose: keeps the dev/build config free of
// test-only concerns, and lets this file own its own tsconfig include (see
// tsconfig.node.json) without pulling test globals into the app build.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    restoreMocks: true
  }
})
