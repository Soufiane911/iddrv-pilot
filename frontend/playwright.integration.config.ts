import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e-integration',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  use: {
    baseURL: process.env.IDDRV_E2E_BASE_URL ?? 'http://127.0.0.1:8088',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
