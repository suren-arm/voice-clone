'use client';

import Link from 'next/link';
import { useEffect, useMemo } from 'react';
import { Callout } from '@/components/Callout';
import { Field } from '@/components/Field';
import type { BackgroundSound, Voice, VoiceSource } from '@/types';
import {
  ARMENIAN_CLONING_BLOCKED_MESSAGE,
  BACKGROUND_SOUND_OPTIONS,
  isClonedVoiceBlockedForLanguage,
} from '@/utils/voiceCapability';

interface VoiceAndBackgroundFieldsProps {
  language: string;
  clonedVoices: Voice[];
  defaultVoices: Voice[];
  voiceSource: VoiceSource;
  onVoiceSourceChange: (source: VoiceSource) => void;
  voiceId: string;
  onVoiceIdChange: (voiceId: string) => void;
  backgroundSound: BackgroundSound;
  onBackgroundSoundChange: (sound: BackgroundSound) => void;
  backgroundVolume: number;
  onBackgroundVolumeChange: (volume: number) => void;
  disabled?: boolean;
}

/**
 * Voice Source (cloned/default) + voice picker + background ambience.
 *
 * Shared between the Text to Speech screen and the Fairy Tale narration
 * step -- both need exactly this block, wired to the same
 * `POST /api/v1/speech` fields (voiceId, backgroundSound, backgroundVolume).
 */
export function VoiceAndBackgroundFields({
  language,
  clonedVoices,
  defaultVoices,
  voiceSource,
  onVoiceSourceChange,
  voiceId,
  onVoiceIdChange,
  backgroundSound,
  onBackgroundSoundChange,
  backgroundVolume,
  onBackgroundVolumeChange,
  disabled = false,
}: VoiceAndBackgroundFieldsProps) {
  const cloningBlocked = isClonedVoiceBlockedForLanguage(language);
  const defaultVoicesForLanguage = useMemo(
    () => defaultVoices.filter((voice) => voice.language === language),
    [defaultVoices, language],
  );

  // Keep the default-voice selection valid as the language changes (cloned
  // voice choices are left entirely to the user -- including staying on a
  // blocked combination so they can see *why* it's blocked, per the product
  // requirement to explain it rather than silently steer around it).
  useEffect(() => {
    if (voiceSource !== 'default') return;
    if (defaultVoicesForLanguage.some((voice) => voice.id === voiceId)) return;
    onVoiceIdChange(defaultVoicesForLanguage[0]?.id ?? '');
  }, [voiceSource, defaultVoicesForLanguage, voiceId, onVoiceIdChange]);

  return (
    <div className="stack">
      <Field label="Voice Source">
        {() => (
          <div className="segmented" role="group" aria-label="Voice source">
            <button
              type="button"
              className="segmented__option"
              aria-pressed={voiceSource === 'cloned'}
              disabled={disabled}
              onClick={() => onVoiceSourceChange('cloned')}
              data-testid="voice-source-cloned"
            >
              My Cloned Voice
            </button>
            <button
              type="button"
              className="segmented__option"
              aria-pressed={voiceSource === 'default'}
              disabled={disabled}
              onClick={() => onVoiceSourceChange('default')}
              data-testid="voice-source-default"
            >
              Default Voice
            </button>
          </div>
        )}
      </Field>

      {voiceSource === 'cloned' && cloningBlocked && (
        <Callout kind="warning" title="Armenian cloning is not supported">
          {ARMENIAN_CLONING_BLOCKED_MESSAGE}
        </Callout>
      )}

      {voiceSource === 'cloned' && !cloningBlocked && clonedVoices.length === 0 && (
        <Callout kind="info" title="No cloned voice yet">
          Create a voice profile from a short recording, or switch to a default voice above.{' '}
          <Link href="/voices/new">Create voice</Link>
        </Callout>
      )}

      {voiceSource === 'cloned' && !cloningBlocked && clonedVoices.length > 0 && (
        <Field label="Voice">
          {(props) => (
            <select
              {...props}
              className="select"
              value={voiceId}
              disabled={disabled}
              onChange={(event) => onVoiceIdChange(event.target.value)}
              data-testid="cloned-voice-select"
            >
              {clonedVoices.map((voice) => (
                <option key={voice.id} value={voice.id}>
                  {voice.name} ({voice.language})
                </option>
              ))}
            </select>
          )}
        </Field>
      )}

      {voiceSource === 'default' && (
        <Field
          label="Voice"
          hint={
            defaultVoicesForLanguage.length === 0
              ? 'No default voice is available for this language yet.'
              : 'A built-in synthetic voice — no recording required.'
          }
        >
          {(props) => (
            <select
              {...props}
              className="select"
              value={voiceId}
              disabled={disabled || defaultVoicesForLanguage.length === 0}
              onChange={(event) => onVoiceIdChange(event.target.value)}
              data-testid="default-voice-select"
            >
              {defaultVoicesForLanguage.length === 0 && <option value="">Unavailable</option>}
              {defaultVoicesForLanguage.map((voice) => (
                <option key={voice.id} value={voice.id}>
                  {voice.name}
                </option>
              ))}
            </select>
          )}
        </Field>
      )}

      <Field label="Background">
        {() => (
          <div className="segmented" role="group" aria-label="Background sound">
            {BACKGROUND_SOUND_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                className="segmented__option"
                aria-pressed={backgroundSound === option.value}
                disabled={disabled}
                onClick={() => onBackgroundSoundChange(option.value)}
                data-testid={`background-${option.value}`}
              >
                {option.label}
              </button>
            ))}
          </div>
        )}
      </Field>

      {backgroundSound !== 'none' && (
        <Field label={`Background volume (${backgroundVolume}%)`}>
          {(props) => (
            <input
              {...props}
              type="range"
              className="range"
              min={0}
              max={100}
              step={5}
              value={backgroundVolume}
              disabled={disabled}
              onChange={(event) => onBackgroundVolumeChange(Number(event.target.value))}
              data-testid="background-volume"
            />
          )}
        </Field>
      )}
    </div>
  );
}
