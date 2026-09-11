'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/Button';
import { Callout } from '@/components/Callout';
import { Card } from '@/components/Card';
import { EmptyState } from '@/components/EmptyState';
import { Field } from '@/components/Field';
import { Spinner } from '@/components/Spinner';
import { useSystemInfo } from '@/hooks/useSystemInfo';
import { useToast } from '@/hooks/useToast';
import { useVoices } from '@/hooks/useVoices';
import { ApiError } from '@/services/apiClient';
import { generateSpeech } from '@/services/speech';
import type { Generation } from '@/types';
import { GenerationResult } from '@/features/speech/GenerationResult';
import { validateText } from '@/utils/validation';

interface GenerateFormProps {
  /** Pre-selected voice, e.g. straight after creating one. */
  initialVoiceId?: string;
}

export function GenerateForm({ initialVoiceId }: GenerateFormProps) {
  const { info, loading: infoLoading } = useSystemInfo();
  const { voices, loading: voicesLoading, error: voicesError } = useVoices();
  const { push } = useToast();

  const [voiceId, setVoiceId] = useState(initialVoiceId ?? '');
  const [language, setLanguage] = useState('en');
  const [text, setText] = useState('');
  const [textError, setTextError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState<Generation | null>(null);
  const [error, setError] = useState<string | null>(null);

  const maxChars = info?.limits.maxTextChars ?? 2000;
  const selectedVoice = useMemo(
    () => voices.find((voice) => voice.id === voiceId) ?? null,
    [voices, voiceId],
  );
  const selectedLanguage = useMemo(
    () => info?.languages.find((option) => option.code === language) ?? null,
    [info, language],
  );

  // Default to the requested voice, else the most recent one; and follow the
  // voice's own language so the common case needs no extra choice.
  useEffect(() => {
    if (voices.length === 0) return;
    if (!voiceId || !voices.some((voice) => voice.id === voiceId)) {
      const fallback = initialVoiceId && voices.some((v) => v.id === initialVoiceId)
        ? initialVoiceId
        : voices[0]!.id;
      setVoiceId(fallback);
    }
  }, [voices, voiceId, initialVoiceId]);

  useEffect(() => {
    if (selectedVoice) setLanguage(selectedVoice.language);
  }, [selectedVoice]);

  const over = text.length > maxChars;
  const canGenerate = Boolean(voiceId) && text.trim().length > 0 && !over && !generating;

  async function handleGenerate() {
    const problem = validateText(text, info?.limits ?? null);
    setTextError(problem);
    if (problem || !voiceId) return;

    setGenerating(true);
    setError(null);
    setResult(null);
    try {
      const generation = await generateSpeech({ voiceId, text: text.trim(), language });
      setResult(generation);
      push('success', 'Speech generated.');
    } catch (cause) {
      const message =
        cause instanceof ApiError ? cause.message : 'Generation failed. Please try again.';
      setError(message);
      push('error', message);
    } finally {
      setGenerating(false);
    }
  }

  if (infoLoading || voicesLoading) {
    return (
      <Card>
        <Spinner label="Loading…" large />
      </Card>
    );
  }

  if (voicesError) {
    return <Callout kind="error">{voicesError}</Callout>;
  }

  if (voices.length === 0) {
    return (
      <Card>
        <EmptyState
          title="You need a voice first"
          description="Create a voice profile from a short recording, then come back here."
          action={
            <Link href="/voices/new" className="btn btn--primary">
              Create voice
            </Link>
          }
        />
      </Card>
    );
  }

  return (
    <div className="stack-5">
      <Card title="Generate speech">
        <div className="stack">
          <Field label="Voice">
            {(props) => (
              <select
                {...props}
                className="select"
                value={voiceId}
                onChange={(event) => setVoiceId(event.target.value)}
                data-testid="voice-select"
              >
                {voices.map((voice) => (
                  <option key={voice.id} value={voice.id}>
                    {voice.name} ({voice.language})
                  </option>
                ))}
              </select>
            )}
          </Field>

          <Field
            label="Language"
            hint={selectedLanguage?.experimental ? selectedLanguage.note : undefined}
          >
            {(props) => (
              <select
                {...props}
                className="select"
                value={language}
                onChange={(event) => setLanguage(event.target.value)}
                data-testid="language-select"
              >
                {info?.languages.map((option) => (
                  <option key={option.code} value={option.code}>
                    {option.name}
                    {option.experimental ? ' — experimental' : ''}
                  </option>
                ))}
              </select>
            )}
          </Field>

          {selectedLanguage?.experimental && (
            <Callout kind="warning" title="Experimental language">
              {selectedLanguage.note}
            </Callout>
          )}

          <Field
            label="Text"
            error={textError}
            counter={
              <span className={over ? 'counter counter--over' : 'counter'} data-testid="char-counter">
                {text.length.toLocaleString()} / {maxChars.toLocaleString()}
              </span>
            }
          >
            {(props) => (
              <textarea
                {...props}
                className="textarea"
                value={text}
                placeholder="Hello. This is my cloned voice."
                onChange={(event) => {
                  setText(event.target.value);
                  if (textError) setTextError(null);
                }}
                data-testid="text-input"
              />
            )}
          </Field>

          {error && <Callout kind="error">{error}</Callout>}

          <div className="row row--between">
            <span className="field__hint">
              {generating
                ? 'Generating — this runs on the server and takes a few seconds.'
                : info?.engine.watermarked
                  ? 'Generated audio carries an inaudible provenance watermark.'
                  : ''}
            </span>
            <Button
              variant="primary"
              size="lg"
              onClick={() => void handleGenerate()}
              disabled={!canGenerate}
              loading={generating}
              data-testid="generate-submit"
            >
              {generating ? 'Generating…' : 'Generate speech'}
            </Button>
          </div>
        </div>
      </Card>

      {result && (
        <GenerationResult
          generation={result}
          onGenerateAgain={() => {
            setResult(null);
            setError(null);
          }}
        />
      )}
    </div>
  );
}
