import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

// Testing Library's own auto-cleanup only registers itself against a global
// `afterEach`, which isn't defined here since `test.globals` is deliberately
// left off (see vitest.config.ts). Wire it up explicitly so each test starts
// from an empty document instead of accumulating previous renders.
afterEach(() => {
  cleanup()
})
