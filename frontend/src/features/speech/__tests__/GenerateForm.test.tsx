import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ToastProvider } from '@/hooks/useToast';
import { resetSystemInfoCache } from '@/hooks/useSystemInfo';
import { GenerateForm } from '@/features/speech/GenerateForm';
import type { Generation, SystemInfo, Voice } from '@/types';

const systemInfo: SystemInfo = {
  appName: 'AI Voice Studio',
  version: '0.1.0',
  environment: 'test',
  engine: {
    name: 'mock',
    variant: 'sine',
    device: 'cpu',
    sampleRate: 24000,
    loaded: true,
    supportsStreaming: false,
    supportsCachedConditioning: true,
    watermarked: true,
    license: 'MIT',
    notes: null,
  },
  deviceDetails: {},
  languages: [
    { code: 'en', name: 'English', native: true, experimental: false, note: null },
    { code: 'ru', name: 'Russian', native: true, experimental: false, note: null },
    {
      code: 'hy',
      name: 'Armenian (experimental)',
      native: false,
      experimental: true,
      note: 'Armenian is not natively supported by this model.',
    },
  ],
  limits: {
    maxUploadBytes: 26214400,
    minReferenceSeconds: 3,
    maxReferenceSeconds: 120,
    maxTextChars: 40,
    maxVoices: 100,
    requireConsent: true,
  },
  acceptedAudioFormats: ['wav', 'mp3'],
};

const voice: Voice = {
  id: 'voice_abc123def456',
  name: 'My Voice',
  language: 'en',
  createdAt: '2026-09-11T12:00:00Z',
  engine: 'mock',
  engineVariant: 'sine',
  referenceDurationSeconds: 12,
  referenceSampleRate: 24000,
  source: 'record',
  generationCount: 0,
  lastUsedAt: null,
  consentGiven: true,
  hasConditioningCache: true,
  sampleUrl: '/api/v1/voices/voice_abc123def456/sample',
};

const generation: Generation = {
  id: 'gen_abc123def456',
  voiceId: voice.id,
  text: 'Hello there.',
  language: 'en',
  createdAt: '2026-09-11T12:05:00Z',
  audioUrl: '/api/v1/generations/gen_abc123def456/audio',
  durationSeconds: 2.4,
  sampleRate: 24000,
  sizeBytes: 115200,
  generationSeconds: 0.7,
  realTimeFactor: 0.29,
  engine: 'mock',
  watermarked: true,
  experimental: false,
  notice: null,
  backgroundSound: 'none',
  backgroundApplied: false,
  backgroundNotice: null,
};

const fetchMock = vi.fn();

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}

function routeTo(url: string) {
  if (url.includes('/system/info')) return jsonResponse(systemInfo);
  if (url.includes('/voices/defaults')) return jsonResponse([]);
  if (url.includes('/voices')) return jsonResponse({ items: [voice], meta: { total: 1, limit: 100, offset: 0 } });
  if (url.includes('/speech')) return jsonResponse(generation);
  return jsonResponse({});
}

function renderForm() {
  return render(
    <ToastProvider>
      <GenerateForm />
    </ToastProvider>,
  );
}

describe('GenerateForm', () => {
  beforeEach(() => {
    resetSystemInfoCache();
    fetchMock.mockReset();
    fetchMock.mockImplementation((input: RequestInfo | URL) => Promise.resolve(routeTo(String(input))));
    vi.stubGlobal('fetch', fetchMock);
  });

  it('loads voices and languages from the API', async () => {
    renderForm();
    const voiceSelect = await screen.findByTestId('cloned-voice-select');
    expect(voiceSelect).toHaveValue(voice.id);
    expect(screen.getByRole('option', { name: /Armenian \(experimental\) — experimental/ })).toBeInTheDocument();
  });

  it('shows the character counter against the server limit', async () => {
    renderForm();
    const textarea = await screen.findByTestId('text-input');
    await userEvent.type(textarea, 'Hello');
    expect(screen.getByTestId('char-counter')).toHaveTextContent('5 / 40');
  });

  it('blocks generation and flags the counter when the text is too long', async () => {
    renderForm();
    const textarea = await screen.findByTestId('text-input');
    await userEvent.click(textarea);
    await userEvent.paste('x'.repeat(45));

    expect(screen.getByTestId('char-counter')).toHaveClass('counter--over');
    expect(screen.getByTestId('generate-submit')).toBeDisabled();
  });

  it('keeps the generate button disabled while the text is empty', async () => {
    renderForm();
    expect(await screen.findByTestId('generate-submit')).toBeDisabled();
  });

  it('generates speech and shows the result with a download link', async () => {
    renderForm();
    const textarea = await screen.findByTestId('text-input');
    await userEvent.type(textarea, 'Hello there.');
    await userEvent.click(screen.getByTestId('generate-submit'));

    expect(await screen.findByTestId('generation-result')).toBeInTheDocument();
    expect(screen.getByTestId('audio-player')).toBeInTheDocument();
    expect(screen.getByTestId('download-wav')).toHaveAttribute(
      'href',
      'http://api.test/api/v1/generations/gen_abc123def456/audio?download=true',
    );
    expect(screen.getByText('0.29')).toBeInTheDocument();
    expect(screen.getByText('Watermarked')).toBeInTheDocument();
  });

  it('blocks cloned-voice narration for Armenian with a clear explanation', async () => {
    renderForm();
    const languageSelect = await screen.findByTestId('language-select');
    await userEvent.selectOptions(languageSelect, 'hy');

    expect(await screen.findByText(/does not support Armenian/i)).toBeInTheDocument();
    expect(screen.getByTestId('generate-submit')).toBeDisabled();
  });

  it('surfaces a server error without losing the typed text', async () => {
    renderForm();
    const textarea = await screen.findByTestId('text-input');
    await userEvent.type(textarea, 'Hello there.');

    fetchMock.mockImplementationOnce(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({ error: { code: 'synthesis_failed', message: 'Speech generation failed.' } }),
          { status: 500, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    );
    await userEvent.click(screen.getByTestId('generate-submit'));

    // The message appears twice on purpose: inline next to the form, and as a
    // toast for users who have scrolled away from it.
    const messages = await screen.findAllByText(/Speech generation failed/);
    expect(messages).toHaveLength(2);
    expect(screen.getByTestId('toast-region')).toHaveTextContent('Speech generation failed.');
    expect(textarea).toHaveValue('Hello there.');
    expect(screen.queryByTestId('generation-result')).not.toBeInTheDocument();
  });

  it('steers a user with no cloned voices to the default voice instead of blocking them', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/system/info')) return Promise.resolve(jsonResponse(systemInfo));
      if (url.includes('/voices/defaults')) {
        return Promise.resolve(
          jsonResponse([{ ...voice, id: 'voice_default000001', source: 'system', name: 'English (Classic)' }]),
        );
      }
      return Promise.resolve(jsonResponse({ items: [], meta: { total: 0, limit: 100, offset: 0 } }));
    });

    renderForm();
    await waitFor(() =>
      expect(screen.getByTestId('voice-source-default')).toHaveAttribute('aria-pressed', 'true'),
    );
    expect(await screen.findByTestId('default-voice-select')).toBeInTheDocument();
  });

  it('still offers a path to create a voice when the user switches back to cloned with none available', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/system/info')) return Promise.resolve(jsonResponse(systemInfo));
      if (url.includes('/voices/defaults')) return Promise.resolve(jsonResponse([]));
      return Promise.resolve(jsonResponse({ items: [], meta: { total: 0, limit: 100, offset: 0 } }));
    });

    renderForm();
    await waitFor(() => expect(screen.getByTestId('voice-source-cloned')).toBeInTheDocument());
    await userEvent.click(screen.getByTestId('voice-source-cloned'));
    expect(await screen.findByText(/No cloned voice yet/i)).toBeInTheDocument();
    // Crucially, the toggle itself must still be there -- switching to
    // "My Cloned Voice" with none created must not be a dead end.
    expect(screen.getByTestId('voice-source-default')).toBeInTheDocument();
  });
});
