import { expect, test } from '@playwright/test';
import { stubApi, wavBytes } from './fixtures';

test.beforeEach(async ({ page }) => {
  await stubApi(page);
});

test('the whole journey: create a voice, generate speech, download it, delete the voice', async ({
  page,
}) => {
  // --- Home ---------------------------------------------------------------
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'AI Voice Studio', level: 1 })).toBeVisible();
  await expect(page.getByTestId('system-status')).toContainText('mock');

  // --- Create voice: upload path ------------------------------------------
  await page.getByRole('link', { name: 'Create Voice' }).first().click();
  await expect(page).toHaveURL(/\/voices\/new$/);

  await page.getByTestId('mode-upload').click();
  await page.getByTestId('file-input').setInputFiles({
    name: 'reference.wav',
    mimeType: 'audio/wav',
    buffer: wavBytes(12),
  });
  await expect(page.getByTestId('audio-player')).toBeVisible();

  await page.getByTestId('voice-name').fill('E2E Voice');

  // Consent gates the submit button.
  await expect(page.getByTestId('create-voice-submit')).toBeDisabled();
  await page.getByTestId('consent-checkbox').check();
  await expect(page.getByTestId('create-voice-submit')).toBeEnabled();

  await page.getByTestId('create-voice-submit').click();

  // --- Generate -----------------------------------------------------------
  await expect(page).toHaveURL(/\/generate\?voiceId=voice_e2e/);
  await expect(page.getByTestId('voice-select')).toBeVisible();

  await expect(page.getByTestId('generate-submit')).toBeDisabled();
  await page.getByTestId('text-input').fill('Hello. This is my cloned voice.');
  await expect(page.getByTestId('char-counter')).toHaveText('31 / 2,000');
  await page.getByTestId('generate-submit').click();

  // --- Result -------------------------------------------------------------
  const result = page.getByTestId('generation-result');
  await expect(result).toBeVisible();
  await expect(result.getByTestId('audio-player')).toBeVisible();
  await expect(result.getByText('Watermarked')).toBeVisible();

  // --- Download -----------------------------------------------------------
  const downloadLink = page.getByTestId('download-wav');
  await expect(downloadLink).toHaveAttribute('href', /\/audio\?download=true$/);
  const [download] = await Promise.all([page.waitForEvent('download'), downloadLink.click()]);
  expect(download.suggestedFilename()).toMatch(/^gen_e2e\d+\.wav$/);

  // --- History ------------------------------------------------------------
  await page.getByRole('link', { name: 'History' }).click();
  await expect(page.getByTestId('generation-list')).toContainText('Hello. This is my cloned voice.');

  // --- Delete cascades ----------------------------------------------------
  await page.getByRole('link', { name: 'My Voices' }).click();
  await expect(page.getByTestId('voice-list')).toContainText('E2E Voice');

  page.once('dialog', (dialog) => dialog.accept());
  await page.getByRole('button', { name: 'Delete' }).first().click();
  await expect(page.getByText('No voices yet')).toBeVisible();

  await page.getByRole('link', { name: 'History' }).click();
  await expect(page.getByText('Nothing generated yet')).toBeVisible();
});

test('microphone recording produces a usable clip', async ({ page }) => {
  await page.goto('/voices/new');
  await page.getByTestId('mode-record').click();

  await page.getByTestId('start-recording').click();
  await expect(page.getByTestId('stop-recording')).toBeVisible();
  await expect(page.getByText(/Recording — aim for/)).toBeVisible();

  // Let the timer advance past 0:00 so we know capture really started.
  await expect(page.getByTestId('recorder-timer')).not.toHaveText('0:00', { timeout: 5000 });

  await page.getByTestId('stop-recording').click();
  await expect(page.getByTestId('audio-player')).toBeVisible();
  await expect(page.getByTestId('record-again')).toBeVisible();
});

test('the experimental Armenian path is labelled at every step', async ({ page }) => {
  await page.goto('/voices/new');
  await page.getByTestId('mode-upload').click();
  await page.getByTestId('file-input').setInputFiles({
    name: 'reference.wav',
    mimeType: 'audio/wav',
    buffer: wavBytes(12),
  });
  await page.getByTestId('voice-name').fill('Armenian Test');
  await page.getByTestId('consent-checkbox').check();
  await page.getByTestId('create-voice-submit').click();

  await expect(page.getByTestId('language-select')).toBeVisible();
  await page.getByTestId('language-select').selectOption('hy');
  await expect(page.getByText('Experimental language')).toBeVisible();

  await page.getByTestId('text-input').fill('Բարև Ձեզ։');
  await page.getByTestId('generate-submit').click();

  const result = page.getByTestId('generation-result');
  await expect(result).toBeVisible();
  await expect(result.getByText('Experimental output')).toBeVisible();
  await expect(result.getByText('Experimental', { exact: true })).toBeVisible();
});

test('a failing API surfaces an error instead of a blank screen', async ({ page }) => {
  await page.route('**/api/v1/system/info', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ error: { code: 'engine_unavailable', message: 'Engine is starting up.' } }),
    }),
  );

  await page.goto('/voices/new');
  await expect(page.getByText('Cannot reach the API')).toBeVisible();
  await expect(page.getByText('Engine is starting up.')).toBeVisible();
});

test('the layout works at phone width', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'AI Voice Studio', level: 1 })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Create Voice' }).first()).toBeVisible();

  // No horizontal overflow: the body must not be wider than the viewport.
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
});
