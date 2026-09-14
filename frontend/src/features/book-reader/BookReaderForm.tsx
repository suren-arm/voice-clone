'use client';

import { useEffect, useState } from 'react';
import { Button } from '@/components/Button';
import { Callout } from '@/components/Callout';
import { Card } from '@/components/Card';
import { useDefaultVoices } from '@/hooks/useDefaultVoices';
import { useToast } from '@/hooks/useToast';
import { useVoices } from '@/hooks/useVoices';
import { ApiError } from '@/services/apiClient';
import { deleteBook, getBook, narrateBook } from '@/services/books';
import { getGeneration } from '@/services/speech';
import type {
  BackgroundSound,
  BookDocument,
  Generation,
  ReadingRange,
  ReadingSpeed,
  VoiceSource,
} from '@/types';
import { GenerationResult } from '@/features/speech/GenerationResult';
import { VoiceAndBackgroundFields } from '@/features/speech/VoiceAndBackgroundFields';
import { BookPreview } from '@/features/book-reader/BookPreview';
import { ReadingRangeFields } from '@/features/book-reader/ReadingRangeFields';
import { SourceForm } from '@/features/book-reader/SourceForm';
import {
  clearBookReaderSession,
  loadBookReaderSession,
  saveBookReaderSession,
} from '@/utils/bookReaderSession';
import { DEFAULT_BACKGROUND_VOLUME, isClonedVoiceBlockedForLanguage } from '@/utils/voiceCapability';

type ReadingPreset = 'standard' | 'bedtime' | 'fairyTale' | 'study';

export function BookReaderForm() {
  const { voices } = useVoices();
  const { defaultVoices } = useDefaultVoices();
  const { push } = useToast();

  const [document, setDocument] = useState<BookDocument | null>(null);
  const [language, setLanguage] = useState('en');
  const [range, setRange] = useState<ReadingRange>({ kind: 'entire' });
  const [speed, setSpeed] = useState<ReadingSpeed>(1);

  const [voiceSource, setVoiceSource] = useState<VoiceSource>('default');
  const [voiceId, setVoiceId] = useState('');
  const [backgroundSound, setBackgroundSound] = useState<BackgroundSound>('none');
  const [backgroundVolume, setBackgroundVolume] = useState(DEFAULT_BACKGROUND_VOLUME);

  const [narrating, setNarrating] = useState(false);
  const [narrationError, setNarrationError] = useState<string | null>(null);
  const [narration, setNarration] = useState<Generation | null>(null);

  const [resumeAvailable, setResumeAvailable] = useState(false);

  useEffect(() => {
    setResumeAvailable(loadBookReaderSession() !== null);
  }, []);

  function handleLoaded(loaded: BookDocument) {
    setDocument(loaded);
    setLanguage(loaded.language);
    setRange({ kind: 'entire' });
    setNarration(null);
    setNarrationError(null);
  }

  async function handleResume() {
    const session = loadBookReaderSession();
    if (!session) return;
    try {
      const loaded = await getBook(session.documentId);
      setDocument(loaded);
      setLanguage(session.language);
      setRange(session.range);
      setVoiceId(session.voiceId);
      setResumeAvailable(false);
      push('success', 'Resumed your last book.');
    } catch {
      // The document was cleaned up server-side (retention window) or the id
      // is otherwise no longer valid -- resuming is a convenience, so fail
      // quietly and just forget it, rather than surfacing an error.
      clearBookReaderSession();
      setResumeAvailable(false);
    }
  }

  function applyPreset(preset: ReadingPreset) {
    if (preset === 'standard') {
      setSpeed(1);
      setBackgroundSound('none');
    } else if (preset === 'bedtime') {
      setSpeed(0.75);
      setBackgroundSound('bedtime');
      setBackgroundVolume(10);
    } else if (preset === 'fairyTale') {
      setSpeed(1);
      setBackgroundSound('mystical');
      setBackgroundVolume(15);
    } else if (preset === 'study') {
      setSpeed(1);
      setBackgroundSound('none');
    }
  }

  const cloningBlocked = voiceSource === 'cloned' && isClonedVoiceBlockedForLanguage(language);
  const canNarrate = document !== null && Boolean(voiceId) && !cloningBlocked && !narrating;

  async function handleNarrate() {
    if (!document || !canNarrate) return;
    setNarrating(true);
    setNarrationError(null);
    setNarration(null);
    try {
      const result = await narrateBook(document.id, {
        voiceId,
        language,
        range,
        speed,
        backgroundSound,
        backgroundVolume,
      });
      const generation = await getGeneration(result.generationId);
      setNarration(generation);
      saveBookReaderSession({
        documentId: document.id,
        title: document.title,
        range,
        voiceId,
        language,
      });
      push('success', 'Narration generated.');
    } catch (cause) {
      const message =
        cause instanceof ApiError ? cause.message : 'Narration failed. Please try again.';
      setNarrationError(message);
      push('error', message);
    } finally {
      setNarrating(false);
    }
  }

  async function handleForget() {
    if (!document) return;
    try {
      await deleteBook(document.id);
    } catch {
      // Best-effort: even if the delete call fails, still reset the local
      // screen so the user can load a different book.
    }
    clearBookReaderSession();
    setDocument(null);
    setNarration(null);
  }

  return (
    <div className="stack-5">
      {resumeAvailable && !document && (
        <Callout kind="info" title="Continue reading?">
          <div className="row row--between">
            <span>You have a book in progress.</span>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => void handleResume()}
              data-testid="resume-book"
            >
              Resume
            </Button>
          </div>
        </Callout>
      )}

      <Card title="Book Reader 📖">
        <SourceForm onLoaded={handleLoaded} />
      </Card>

      {document && (
        <Card title={document.title ?? 'Untitled'} hint={`${document.charCount.toLocaleString()} characters extracted`}>
          <BookPreview document={document} language={language} onLanguageChange={setLanguage} />
        </Card>
      )}

      {document && (
        <Card
          title="Narrate"
          action={
            <div className="row">
              <Button variant="ghost" size="sm" onClick={() => applyPreset('standard')} data-testid="preset-standard">
                Standard
              </Button>
              <Button variant="ghost" size="sm" onClick={() => applyPreset('bedtime')} data-testid="preset-bedtime">
                🌙 Bedtime
              </Button>
              <Button variant="ghost" size="sm" onClick={() => applyPreset('fairyTale')} data-testid="preset-fairy-tale">
                ✨ Fairy-Tale
              </Button>
              <Button variant="ghost" size="sm" onClick={() => applyPreset('study')} data-testid="preset-study">
                📚 Study
              </Button>
            </div>
          }
        >
          <div className="stack">
            <ReadingRangeFields
              document={document}
              range={range}
              onRangeChange={setRange}
              speed={speed}
              onSpeedChange={setSpeed}
              disabled={narrating}
            />

            <VoiceAndBackgroundFields
              language={language}
              clonedVoices={voices}
              defaultVoices={defaultVoices}
              voiceSource={voiceSource}
              onVoiceSourceChange={setVoiceSource}
              voiceId={voiceId}
              onVoiceIdChange={setVoiceId}
              backgroundSound={backgroundSound}
              onBackgroundSoundChange={setBackgroundSound}
              backgroundVolume={backgroundVolume}
              onBackgroundVolumeChange={setBackgroundVolume}
              disabled={narrating}
            />

            {narrationError && <Callout kind="error">{narrationError}</Callout>}

            <div className="row row--between">
              <Button variant="ghost" onClick={() => void handleForget()} data-testid="forget-book">
                Load a different book
              </Button>
              <Button
                variant="primary"
                size="lg"
                onClick={() => void handleNarrate()}
                disabled={!canNarrate}
                loading={narrating}
                data-testid="narrate-book-submit"
              >
                {narrating ? 'Narrating…' : 'Start Reading'}
              </Button>
            </div>
          </div>
        </Card>
      )}

      {narration && (
        <GenerationResult generation={narration} onGenerateAgain={() => setNarration(null)} />
      )}
    </div>
  );
}
