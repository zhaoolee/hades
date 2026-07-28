import { defineConfig } from 'vitest/config'
import preact from '@preact/preset-vite'

export default defineConfig({
  plugins: [preact()],
  base: process.env.BASE_PATH || '/hades/',
  test: { environment: 'jsdom', setupFiles: './src/test/setup.ts' },
})
