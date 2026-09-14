'use client';

import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/Button';
import { Callout } from '@/components/Callout';
import { Card } from '@/components/Card';
import { Field } from '@/components/Field';
import { LanguageSelect } from '@/components/LanguageSelect';
import { useAiProviders } from '@/hooks/useAiProviders';
import { useDefaultVoices } from '@/hooks/useDefaultVoices';
import { useSystemInfo } from '@/hooks/useSystemInfo';
import { useToast } from '@/hooks/useToast';
import { useVoices } from '@/hooks/useVoices';
import { ApiError } from '@/services/apiClient';
import { generateSpeech } from '@/services/speech';
import { generateStory } from '@/services/stories';
import type {
  AiProviderId,
  BackgroundSound,
  Generation,
  Story,
  StoryAgeGroup,
  StoryLanguage,
  StoryLength,
  StoryTone,
  VoiceSource,
} from '@/types';
import { GenerationResult } from '@/features/speech/GenerationResult';
import { VoiceAndBackgroundFields } from '@/features/speech/VoiceAndBackgroundFields';
import {
  DEFAULT_BACKGROUND_VOLUME,
  isClonedVoiceBlockedForLanguage,
  preferredVoiceSource,
} from '@/utils/voiceCapability';

const AGE_GROUP_OPTIONS: StoryAgeGroup[] = ['3-5', '6-8', '9-12'];
const LENGTH_OPTIONS: { value: StoryLength; label: string }[] = [
  { value: 'short', label: 'Short' },
  { value: 'medium', label: 'Medium' },
  { value: 'long', label: 'Long' },
];
const TONE_OPTIONS: { value: StoryTone; label: string }[] = [
  { value: 'magical', label: 'Magical' },
  { value: 'funny', label: 'Funny' },
  { value: 'adventure', label: 'Adventure' },
  { value: 'educational', label: 'Educational' },
  { value: 'bedtime', label: 'Bedtime' },
];

export function StoryForm() {
  const { voices } = useVoices();
  const { info } = useSystemInfo();
  const { defaultVoices } = useDefaultVoices();
  const { info: aiProviders } = useAiProviders();
  const { push } = useToast();

  const [provider, setProvider] = useState<AiProviderId>('auto');
  const [language, setLanguage] = useState<StoryLanguage>('en');
  const [characters, setCharacters] = useState('');
  const [idea, setIdea] = useState('');
  const [ageGroup, setAgeGroup] = useState<StoryAgeGroup>('6-8');
  const [length, setLength] = useState<StoryLength>('medium');
  const [tone, setTone] = useState<StoryTone>('magical');

  const [generatingStory, setGeneratingStory] = useState(false);
  const [storyError, setStoryError] = useState<string | null>(null);
  const [story, setStory] = useState<Story | null>(null);
  const [storyText, setStoryText] = useState('');

  const [voiceSource, setVoiceSource] = useState<VoiceSource>('default');
  const [voiceSourceTouched, setVoiceSourceTouched] = useState(false);
  const [voiceId, setVoiceId] = useState('');
  const [backgroundSound, setBackgroundSound] = useState<BackgroundSound>('none');
  const [backgroundVolume, setBackgroundVolume] = useState(DEFAULT_BACKGROUND_VOLUME);
  const [narrating, setNarrating] = useState(false);
  const [narrationError, setNarrationError] = useState<string | null>(null);
  const [narration, setNarration] = useState<Generation | null>(null);

  const canGenerateStory =
    characters.trim().length > 0 && idea.trim().length > 0 && !generatingStory;

  function applyMagicalPreset() {
    setTone('magical');
    setBackgroundSound('mystical');
    setBackgroundVolume(15);
  }

  async function handleGenerateStory() {
    setStoryError(null);
    setGeneratingStory(true);
    setStory(null);
    setNarration(null);
    try {
      const result = await generateStory({
        provider,
        language,
        characters,
        idea,
        ageGroup,
        length,
        tone,
      });
      setStory(result);
      setStoryText(result.text);
      push('success', 'Story generated — read it over, then narrate it.');
    } catch (cause) {
      const message =
        cause instanceof ApiError ? cause.message : 'Story generation failed. Please try again.';
      setStoryError(message);
      push('error', message);
    } finally {
      setGeneratingStory(false);
    }
  }

  const languages = useMemo(() => info?.languages ?? [], [info]);
  const cloningBlocked =
    voiceSource === 'cloned' && isClonedVoiceBlockedForLanguage(languages, language);

  // Start on the same voice Text to Speech would use, so the two screens do
  // not read the same sentence in two different engines. Once the user picks
  // for themselves, stop second-guessing them.
  useEffect(() => {
    if (voiceSourceTouched) return;
    setVoiceSource(preferredVoiceSource(voices, languages, language));
  }, [voiceSourceTouched, voices, languages, language]);
  const canNarrate =
    Boolean(voiceId) && !cloningBlocked && storyText.trim().length > 0 && !narrating;

  async function handleNarrate() {
    if (!canNarrate) return;
    setNarrating(true);
    setNarrationError(null);
    setNarration(null);
    try {
      const generation = await generateSpeech({
        voiceId,
        text: storyText.trim(),
        language,
        backgroundSound,
        backgroundVolume,
      });
      setNarration(generation);
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

  return (
    <div className="stack-5">
      <Card
        title="✨ Create Your Fairy Tale"
        hint="Tell us who the story is about and where it happens."
        action={
          <Button variant="secondary" onClick={applyMagicalPreset} data-testid="magical-preset">
            ✨ Magical Story
          </Button>
        }
      >
        <div className="stack">
          {/* The same catalogue Text to Speech uses -- one list, so a
              language can never be offered for a story it cannot be read in. */}
          <LanguageSelect
            languages={languages}
            value={language}
            onChange={(code) => setLanguage(code as StoryLanguage)}
            hint="Your story is written and read aloud in this language."
            disabled={generatingStory}
            testId="story-language-select"
          />

          <Field label="Who is in your story?">
            {(props) => (
              <input
                {...props}
                className="input"
                value={characters}
                placeholder="e.g. Կարապետ և Ռուզաննա"
                onChange={(event) => setCharacters(event.target.value)}
                data-testid="story-characters-input"
              />
            )}
          </Field>

          <Field label="What happens?">
            {(props) => (
              <textarea
                {...props}
                className="textarea"
                value={idea}
                placeholder="e.g. An adventure in a magical world with giant animals"
                onChange={(event) => setIdea(event.target.value)}
                data-testid="story-idea-input"
              />
            )}
          </Field>

          <Field label="Who is it for?">
            {() => (
              <div className="segmented" role="group" aria-label="Age group">
                {AGE_GROUP_OPTIONS.map((option) => (
                  <button
                    key={option}
                    type="button"
                    className="segmented__option"
                    aria-pressed={ageGroup === option}
                    onClick={() => setAgeGroup(option)}
                    data-testid={`age-group-${option}`}
                  >
                    {option}
                  </button>
                ))}
              </div>
            )}
          </Field>

          <Field label="How long?">
            {() => (
              <div className="segmented" role="group" aria-label="Story length">
                {LENGTH_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    className="segmented__option"
                    aria-pressed={length === option.value}
                    onClick={() => setLength(option.value)}
                    data-testid={`story-length-${option.value}`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            )}
          </Field>

          <Field label="What kind of story?">
            {(props) => (
              <select
                {...props}
                className="select"
                value={tone}
                onChange={(event) => setTone(event.target.value as StoryTone)}
                data-testid="story-tone-select"
              >
                {TONE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            )}
          </Field>

          {/* Which model writes the story is a grown-up's concern, not a
              child's first decision -- so it lives behind a disclosure with
              a plain-language name, still one click away. */}
          <details>
            <summary className="field__label" style={{ cursor: 'pointer' }}>
              Advanced settings
            </summary>
            <div style={{ marginTop: 'var(--space-3)' }}>
              <Field
                label="Story Helper"
                hint={
                  provider === 'auto'
                    ? aiProviders?.autoResolvesTo
                      ? `Right now this uses ${aiProviders.providers.find((p) => p.id === aiProviders.autoResolvesTo)?.name ?? aiProviders.autoResolvesTo}.`
                      : 'No story helper is set up on this server yet.'
                    : undefined
                }
              >
                {(props) => (
                  <select
                    {...props}
                    className="select"
                    value={provider}
                    onChange={(event) => setProvider(event.target.value)}
                    data-testid="ai-provider-select"
                  >
                    <option value="auto">Pick for me (recommended)</option>
                    {aiProviders?.providers.map((p) => (
                      <option key={p.id} value={p.id} disabled={!p.available}>
                        {p.name}
                        {p.available ? '' : ' — not set up'}
                      </option>
                    ))}
                  </select>
                )}
              </Field>
            </div>
          </details>

          {storyError && <Callout kind="error">{storyError}</Callout>}

          <div className="row row--between">
            <span className="field__hint">
              {generatingStory ? '✨ Writing your story — this takes a moment…' : ''}
            </span>
            <Button
              variant="primary"
              size="lg"
              onClick={() => void handleGenerateStory()}
              disabled={!canGenerateStory}
              loading={generatingStory}
              data-testid="generate-story-submit"
            >
              {generatingStory ? '✨ Writing…' : '✨ Create My Story'}
            </Button>
          </div>
        </div>
      </Card>

      {story && (
        <Card
          title={`✨ ${story.title}`}
          hint={`Your story is ready — ${story.wordCount} words. Change anything you like before you hear it.`}
        >
          <div className="stack">
            <Field label="Your story">
              {(props) => (
                <textarea
                  {...props}
                  className="textarea storybook--editable"
                  style={{ minHeight: 280 }}
                  value={storyText}
                  onChange={(event) => setStoryText(event.target.value)}
                  data-testid="story-text-editor"
                />
              )}
            </Field>

            <VoiceAndBackgroundFields
              language={language}
              languages={languages}
              clonedVoices={voices}
              defaultVoices={defaultVoices}
              voiceSource={voiceSource}
              onVoiceSourceChange={(next) => {
                setVoiceSourceTouched(true);
                setVoiceSource(next);
              }}
              voiceId={voiceId}
              onVoiceIdChange={setVoiceId}
              backgroundSound={backgroundSound}
              onBackgroundSoundChange={setBackgroundSound}
              backgroundVolume={backgroundVolume}
              onBackgroundVolumeChange={setBackgroundVolume}
              disabled={narrating}
            />

            {narrationError && <Callout kind="error">{narrationError}</Callout>}

            <div className="row row--end">
              <Button
                variant="primary"
                size="lg"
                onClick={() => void handleNarrate()}
                disabled={!canNarrate}
                loading={narrating}
                data-testid="narrate-story-submit"
              >
                {narrating ? '🎙 Reading…' : '🔊 Read My Story'}
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
