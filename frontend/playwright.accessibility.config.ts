import { defineConfig } from '@playwright/test';

const port = Number(process.env.A11Y_PORT || 54179);
export default defineConfig({
  testDir: './e2e-accessibility',
  forbidOnly: !!process.env.CI,
  workers: 1,
  retries: process.env.CI ? 2 : 0,
  reporter: 'list',
  outputDir: 'test-results/accessibility',
  use: { browserName: 'chromium', baseURL: `http://127.0.0.1:${port}`, trace: 'retain-on-failure' },
  webServer: { command: `npm run dev -- --config vite.accessibility.config.ts --host 127.0.0.1 --port ${port} --strictPort`, url: `http://127.0.0.1:${port}`, reuseExistingServer: false, env: { VITE_SKIP_AUTH: 'false', VITE_DEMO_MODE: 'false' } },
});
