import type { Page, Route } from '@playwright/test';

export const systemInfo = {
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
    license: 'MIT (code and weights)',
    notes: 'Test double.',
  },
  deviceDetails: { device: 'cpu' },
  languages: [
    {
      code: 'en',
      name: 'English',
      englishName: 'English',
      supportsDefaultVoice: true,
      supportsClonedVoice: true,
    },
    {
      code: 'hy',
      name: 'Հայերեն',
      englishName: 'Armenian',
      supportsDefaultVoice: true,
      supportsClonedVoice: false,
    },
    {
      code: 'ru',
      name: 'Русский',
      englishName: 'Russian',
      supportsDefaultVoice: true,
      supportsClonedVoice: false,
    },
  ],
  limits: {
    maxUploadBytes: 26214400,
    minReferenceSeconds: 3,
    maxReferenceSeconds: 120,
    maxTextChars: 2000,
    maxVoices: 100,
    requireConsent: true,
  },
  acceptedAudioFormats: ['m4a', 'mp3', 'wav', 'webm'],
};

export interface VoiceRecord {
  id: string;
  name: string;
  language: string;
  createdAt: string;
  engine: string;
  engineVariant: string;
  referenceDurationSeconds: number;
  referenceSampleRate: number;
  source: string;
  generationCount: number;
  lastUsedAt: string | null;
  consentGiven: boolean;
  hasConditioningCache: boolean;
  sampleUrl: string;
}

/** A tiny but genuinely valid 24 kHz mono WAV, so <audio> can load it. */
export function wavBytes(seconds = 1): Buffer {
  const sampleRate = 24000;
  const samples = sampleRate * seconds;
  const data = Buffer.alloc(samples * 2);
  for (let i = 0; i < samples; i += 1) {
    data.writeInt16LE(Math.round(Math.sin((2 * Math.PI * 220 * i) / sampleRate) * 12000), i * 2);
  }
  const header = Buffer.alloc(44);
  header.write('RIFF', 0);
  header.writeUInt32LE(36 + data.length, 4);
  header.write('WAVE', 8);
  header.write('fmt ', 12);
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20);
  header.writeUInt16LE(1, 22);
  header.writeUInt32LE(sampleRate, 24);
  header.writeUInt32LE(sampleRate * 2, 28);
  header.writeUInt16LE(2, 32);
  header.writeUInt16LE(16, 34);
  header.write('data', 36);
  header.writeUInt32LE(data.length, 40);
  return Buffer.concat([header, data]);
}

/**
 * Install an in-memory stand-in for the backend.
 *
 * It keeps real state across requests, so the test exercises the same
 * create -> list -> generate -> delete sequence a real backend would see,
 * including the cascade delete.
 */
interface BookSectionRecord {
  index: number;
  title: string | null;
  pageNumber: number | null;
  charCount: number;
  text: string;
}

interface BookRecord {
  document: Record<string, unknown>;
  sections: BookSectionRecord[];
}

function e2eBook(id: string): BookRecord {
  const text = 'Once upon a time, a fox and a rabbit became friends in a quiet meadow.';
  return {
    document: {
      id,
      title: 'The Fox and the Rabbit',
      sourceType: 'pdf_upload',
      sourceUrl: null,
      originalFilename: 'story.pdf',
      language: 'en',
      pageCount: 1,
      sectionCount: 1,
      charCount: text.length,
      createdAt: new Date().toISOString(),
    },
    sections: [{ index: 0, title: 'The Fox and the Rabbit', pageNumber: 1, charCount: text.length, text }],
  };
}

export async function stubApi(page: Page) {
  const voices: VoiceRecord[] = [];
  const generations: Record<string, unknown>[] = [];
  const books: Record<string, BookRecord> = {};
  let counter = 0;

  const json = (route: Route, body: unknown, status = 200) =>
    route.fulfill({
      status,
      contentType: 'application/json',
      headers: { 'Access-Control-Allow-Origin': '*' },
      body: JSON.stringify(body),
    });

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (path.endsWith('/system/info')) return json(route, systemInfo);

    if (path.endsWith('/audio') || path.endsWith('/sample')) {
      // Mirror the real backend (backend/app/api/v1/speech.py) exactly: it
      // always names the file after the resource id, and only a
      // Content-Disposition: attachment header actually forces a download.
      // The HTML `download` attribute on the <a> is honored by the browser
      // for a same-origin URL, but silently ignored cross-origin -- and in
      // production the frontend (Pages) and API (Render) *are* different
      // origins, so this header is what makes the download button work there.
      const forceDownload = url.searchParams.get('download') === 'true';
      const resourceId = path.split('/').at(-2) ?? 'clip';
      const disposition = forceDownload ? 'attachment' : 'inline';
      return route.fulfill({
        status: 200,
        contentType: 'audio/wav',
        headers: {
          'Accept-Ranges': 'bytes',
          'Access-Control-Allow-Origin': '*',
          'Content-Disposition': `${disposition}; filename="${resourceId}.wav"`,
        },
        body: wavBytes(2),
      });
    }

    if (path.endsWith('/voices') && method === 'POST') {
      counter += 1;
      const id = `voice_e2e${String(counter).padStart(8, '0')}`;
      const voice: VoiceRecord = {
        id,
        name: (request.postDataBuffer()?.toString().match(/name"\r?\n\r?\n(.*)\r?\n/)?.[1] ?? 'E2E Voice').trim(),
        language: 'en',
        createdAt: new Date().toISOString(),
        engine: 'mock',
        engineVariant: 'sine',
        referenceDurationSeconds: 12,
        referenceSampleRate: 24000,
        source: 'upload',
        generationCount: 0,
        lastUsedAt: null,
        consentGiven: true,
        hasConditioningCache: true,
        sampleUrl: `/api/v1/voices/${id}/sample`,
      };
      voices.unshift(voice);
      return json(route, voice, 201);
    }

    if (path.endsWith('/voices') && method === 'GET') {
      return json(route, { items: voices, meta: { total: voices.length, limit: 100, offset: 0 } });
    }

    if (path.includes('/voices/') && method === 'DELETE') {
      const id = path.split('/').pop()!;
      const index = voices.findIndex((voice) => voice.id === id);
      if (index >= 0) voices.splice(index, 1);
      // Deleting a voice cascades to its generations, exactly as the API does.
      for (let i = generations.length - 1; i >= 0; i -= 1) {
        if (generations[i]!.voiceId === id) generations.splice(i, 1);
      }
      return json(route, { id, deleted: true });
    }

    if (path.endsWith('/speech') && method === 'POST') {
      const payload = request.postDataJSON() as { voiceId: string; text: string; language: string };
      counter += 1;
      const id = `gen_e2e${String(counter).padStart(9, '0')}`;
      const generation = {
        id,
        voiceId: payload.voiceId,
        text: payload.text,
        language: payload.language,
        createdAt: new Date().toISOString(),
        audioUrl: `/api/v1/generations/${id}/audio`,
        durationSeconds: 2,
        sampleRate: 24000,
        sizeBytes: 96044,
        generationSeconds: 0.6,
        realTimeFactor: 0.3,
        engine: 'mock',
        watermarked: true,
        experimental: payload.language === 'hy',
        notice: payload.language === 'hy' ? 'Armenian is not natively supported by this model.' : null,
      };
      generations.unshift(generation);
      const voice = voices.find((item) => item.id === payload.voiceId);
      if (voice) voice.generationCount += 1;
      return json(route, generation, 201);
    }

    if (path.endsWith('/generations') && method === 'GET') {
      return json(route, {
        items: generations,
        meta: { total: generations.length, limit: 50, offset: 0 },
      });
    }

    if (path.includes('/generations/') && method === 'DELETE') {
      const id = path.split('/').pop()!;
      const index = generations.findIndex((item) => item.id === id);
      if (index >= 0) generations.splice(index, 1);
      return json(route, { id, deleted: true });
    }

    if (path.includes('/generations/') && method === 'GET') {
      const id = path.split('/').pop()!;
      const generation = generations.find((item) => item.id === id);
      if (!generation) return json(route, { error: { code: 'generation_not_found', message: 'Not found.' } }, 404);
      return json(route, generation);
    }

    if (path.endsWith('/voices/defaults')) {
      return json(route, [
        {
          id: 'default_en_male',
          name: 'English (Male, Classic)',
          language: 'en',
          createdAt: new Date().toISOString(),
          engine: 'espeak-ng',
          engineVariant: 'en-us',
          referenceDurationSeconds: 0,
          referenceSampleRate: 22050,
          source: 'system',
          generationCount: 0,
          lastUsedAt: null,
          consentGiven: true,
          hasConditioningCache: false,
          sampleUrl: null,
        },
      ]);
    }

    // -- Book Reader ----------------------------------------------------------

    if (path.endsWith('/books/upload') && method === 'POST') {
      counter += 1;
      const id = `doc_e2e${String(counter).padStart(8, '0')}`;
      books[id] = e2eBook(id);
      return json(route, books[id]!.document, 201);
    }

    if (path.endsWith('/books/from-url') && method === 'POST') {
      counter += 1;
      const id = `doc_e2e${String(counter).padStart(8, '0')}`;
      books[id] = e2eBook(id);
      return json(route, books[id]!.document, 201);
    }

    if (path.match(/\/books\/[^/]+\/sections\/\d+$/)) {
      const [, id, index] = path.match(/\/books\/([^/]+)\/sections\/(\d+)$/)!;
      const book = books[id!];
      const section = book?.sections[Number(index)];
      if (!section) return json(route, { error: { code: 'not_found', message: 'Not found.' } }, 404);
      return json(route, section);
    }

    if (path.match(/\/books\/[^/]+\/sections$/)) {
      const [, id] = path.match(/\/books\/([^/]+)\/sections$/)!;
      const book = books[id!];
      if (!book) return json(route, { error: { code: 'document_not_found', message: 'Not found.' } }, 404);
      return json(route, {
        items: book.sections.map(({ text: _text, ...summary }) => summary),
        meta: { total: book.sections.length, limit: 20, offset: 0 },
      });
    }

    if (path.match(/\/books\/[^/]+\/narrate$/) && method === 'POST') {
      const [, id] = path.match(/\/books\/([^/]+)\/narrate$/)!;
      const payload = request.postDataJSON() as { voiceId: string; language: string };
      counter += 1;
      const genId = `gen_e2e${String(counter).padStart(9, '0')}`;
      const generation = {
        id: genId,
        voiceId: payload.voiceId,
        text: books[id!]?.sections[0]?.text ?? '',
        language: payload.language,
        createdAt: new Date().toISOString(),
        audioUrl: `/api/v1/generations/${genId}/audio`,
        durationSeconds: 3,
        sampleRate: 22050,
        sizeBytes: 132300,
        generationSeconds: 0.5,
        realTimeFactor: 0.16,
        engine: 'espeak-ng',
        watermarked: false,
        experimental: false,
        notice: null,
        backgroundSound: 'none',
        backgroundApplied: false,
        backgroundNotice: null,
      };
      generations.unshift(generation);
      return json(route, {
        generationId: genId,
        documentId: id,
        range: { kind: 'entire' },
        audioUrl: generation.audioUrl,
        durationSeconds: generation.durationSeconds,
        notice: null,
        backgroundApplied: false,
        backgroundNotice: null,
      }, 201);
    }

    if (path.match(/\/books\/[^/]+$/) && method === 'GET') {
      const [, id] = path.match(/\/books\/([^/]+)$/)!;
      const book = books[id!];
      if (!book) return json(route, { error: { code: 'document_not_found', message: 'Not found.' } }, 404);
      return json(route, book.document);
    }

    return json(route, { error: { code: 'not_found', message: 'Unhandled route in stub.' } }, 404);
  });
}
