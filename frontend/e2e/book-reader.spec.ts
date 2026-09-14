import { expect, test } from '@playwright/test';
import { stubApi } from './fixtures';

test.beforeEach(async ({ page }) => {
  await stubApi(page);
});

test('upload a PDF, preview it, narrate it, and play/download the result', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('link', { name: 'Book Reader' }).click();
  await expect(page).toHaveURL(/\/book-reader$/);

  // --- Upload -----------------------------------------------------------
  await page.getByTestId('book-pdf-input').setInputFiles({
    name: 'story.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-1.4 fake pdf bytes for the e2e stub'),
  });
  await page.getByTestId('load-book-submit').click();

  // --- Preview ------------------------------------------------------------
  await expect(page.getByRole('heading', { name: 'The Fox and the Rabbit' })).toBeVisible();
  await expect(page.getByTestId('preview-text')).toContainText('a fox and a rabbit became friends');

  // --- Narrate --------------------------------------------------------------
  await expect(page.getByTestId('default-voice-select')).toBeVisible();
  await page.getByTestId('narrate-book-submit').click();

  const result = page.getByTestId('generation-result');
  await expect(result).toBeVisible();
  await expect(result.getByTestId('audio-player')).toBeVisible();

  // --- Download -------------------------------------------------------------
  const downloadLink = page.getByTestId('download-wav');
  await expect(downloadLink).toHaveAttribute('href', /\/audio\?download=true$/);
});

test('a public web link is routed to the same preview and narration flow', async ({ page }) => {
  await page.goto('/book-reader');
  await page.getByTestId('book-source-url').click();
  await page.getByTestId('book-url-input').fill('https://example.com/story.pdf');
  await page.getByTestId('load-book-submit').click();

  await expect(page.getByRole('heading', { name: 'The Fox and the Rabbit' })).toBeVisible();
});

test('reading presets change speed and background together', async ({ page }) => {
  await page.goto('/book-reader');
  await page.getByTestId('book-pdf-input').setInputFiles({
    name: 'story.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-1.4 fake pdf bytes for the e2e stub'),
  });
  await page.getByTestId('load-book-submit').click();
  await expect(page.getByRole('heading', { name: 'The Fox and the Rabbit' })).toBeVisible();

  await page.getByTestId('preset-bedtime').click();
  await expect(page.getByTestId('reading-speed-select')).toHaveValue('0.75');
  await expect(page.getByTestId('background-bedtime')).toHaveAttribute('aria-pressed', 'true');
});
