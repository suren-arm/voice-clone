import { defineConfig, devices } from '@playwright/test';

/**
 * The e2e suite runs against the real Next.js production build but a **stubbed
 * API**: every `**\/api/v1/**` call is intercepted in the browser. That keeps
 * the test hermetic (no Python, no GPU, no model weights in CI) while still
 * exercising real routing, hydration, form state and the audio elements.
 *
 * A separate, opt-in suite could point at a live backend; that belongs in a
 * nightly job, not in the pull-request path.
 */
/** Feed MediaRecorder a synthetic signal instead of real hardware. */
const fakeMedia = {
  args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'],
};

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : [['list']],
  timeout: 30_000,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://127.0.0.1:3000',
    trace: 'on-first-retry',
    // The app asks for the microphone; grant it so the recorder path is testable.
    permissions: ['microphone'],
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'], launchOptions: fakeMedia } },
    { name: 'mobile-chrome', use: { ...devices['Pixel 7'], launchOptions: fakeMedia } },
  ],
  webServer: {
    command: 'npm run build && npm run start',
    url: 'http://127.0.0.1:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    env: { NEXT_PUBLIC_API_URL: 'http://127.0.0.1:3000' },
  },
});
