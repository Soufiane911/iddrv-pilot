import { defineConfig, devices } from '@playwright/test';

const port = Number(process.env.SUMMARY6_UI_PORT ?? 5189);
const baseURL = `http://127.0.0.1:${port}`;
export default defineConfig({
  testDir: './e2e',
  testMatch: 'summary6-hardening.spec.ts',
  workers: 1,
  reporter: 'list',
  outputDir: '/tmp/summary6-ui-playwright-results',
  use: { baseURL, ...devices['Desktop Chrome'] },
  webServer: {
    command: `npm run dev -- --host 127.0.0.1 --port ${port} --strictPort`,
    url: baseURL,
    reuseExistingServer: false,
    env: { VITE_SKIP_AUTH: 'true', VITE_DEMO_MODE: 'false', VITE_ENABLE_3D: 'false' },
  },
});
