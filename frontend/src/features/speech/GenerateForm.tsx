'use client';

import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/Button';
import { Callout } from '@/components/Callout';
import { Card } from '@/components/Card';
import { Field } from '@/components/Field';
import { Spinner } from '@/components/Spinner';
import { useDefaultVoices } from '@/hooks/useDefaultVoices';
import { useSystemInfo } from '@/hooks/useSystemInfo';
import { useToast } from '@/hooks/useToast';
import { useVoices } from '@/hooks/useVoices';
import { ApiError } from '@/services/apiClient';
import { generateSpeech } from '@/services/speech';
import type { BackgroundSound, Generation, VoiceSource } from '@/types';
import { GenerationResult } from '@/features/speech/GenerationResult';
import { VoiceAndBackgroundFields } from '@/features/speech/VoiceAndBackgroundFields';
import { DEFAULT_BACKGROUND_VOLUME, isClonedVoiceBlockedForLanguage } from '@/utils/voiceCapability';
import { validateText } from '@/utils/validation';

interface GenerateFormProps {
  /** Pre-selected voice, e.g. straight after creating one. */
  initialVoiceId?: string;
}

export function GenerateForm({ initialVoiceId }: GenerateFormProps) {
  const { info, loading: infoLoading } = useSystemInfo();
  const { voices, loading: voicesLoading, error: voicesError } = useVoices();
  const { defaultVoices } = useDefaultVoices();
  const { push } = useToast();

  const [voiceSource, setVoiceSource] = useState<VoiceSource>('cloned');
  const [voiceId, setVoiceId] = useState(initialVoiceId ?? '');
  const [language, setLanguage] = useState('en');
  const [text, setText] = useState('');
  const [textError, setTextError] = useState<string | null>(null);
  const [backgroundSound, setBackgroundSound] = useState<BackgroundSound>('none');
  const [backgroundVolume, setBackgroundVolume] = useState(DEFAULT_BACKGROUND_VOLUME);
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState<Generation | null>(null);
  const [error, setError] = useState<string | null>(null);

  const maxChars = info?.limits.maxTextChars ?? 2000;
  const selectedVoice = useMemo(
    () => voices.find((voice) => voice.id === voiceId) ?? null,
    [voices, voiceId],
  );
  // Default to the requested voice, else the most recent one; and follow the
  // voice's own language so the common case needs no extra choice. Only
  // applies while the "My Cloned Voice" source is selected.
  useEffect(() => {
    if (voiceSource !== 'cloned' || voices.length === 0) return;
    if (!voiceId || !voices.some((voice) => voice.id === voiceId)) {
      const fallback = initialVoiceId && voices.some((v) => v.id === initialVoiceId)
        ? initialVoiceId
        : voices[0]!.id;
      setVoiceId(fallback);
    }
  }, [voiceSource, voices, voiceId, initialVoiceId]);

  useEffect(() => {
    if (voiceSource === 'cloned' && selectedVoice) setLanguage(selectedVoice.language);
  }, [voiceSource, selectedVoice]);

  const cloningBlocked = voiceSource === 'cloned' && isClonedVoiceBlockedForLanguage(language);
  const over = text.length > maxChars;
  const canGenerate =
    Boolean(voiceId) && !cloningBlocked && text.trim().length > 0 && !over && !generating;

  async function handleGenerate() {
    const problem = validateText(text, info?.limits ?? null);
    setTextError(problem);
    if (problem || !voiceId || cloningBlocked) return;

    setGenerating(true);
    setError(null);
    setResult(null);
    try {
      const generation = await generateSpeech({
        voiceId,
        text: text.trim(),
        language,
        backgroundSound,
        backgroundVolume,
      });
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

  // A user with no cloned voice yet can still use a default voice — only
  // steer them toward "My Cloned Voice" if they have one, never block them.
  useEffect(() => {
    if (!voicesLoading && voices.length === 0 && voiceSource === 'cloned') {
      setVoiceSource('default');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [voicesLoading, voices.length]);

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

  return (
    <div className="stack-5">
      <Card title="🗣️ Speak My Text" hint="Type anything and hear it out loud.">
        <div className="stack">
          <Field label="Language">
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

          <Field
            label="What should I say?"
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
            disabled={generating}
          />

          {error && <Callout kind="error">{error}</Callout>}

          <div className="row row--between">
            <span className="field__hint">
              {generating
                ? '🎙 Reading your text — this takes a few seconds…'
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
              {generating ? '🎙 Reading…' : '🔊 Read It Out Loud'}
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
