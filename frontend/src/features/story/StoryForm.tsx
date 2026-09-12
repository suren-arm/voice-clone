'use client';

import { useState } from 'react';
import { Button } from '@/components/Button';
import { Callout } from '@/components/Callout';
import { Card } from '@/components/Card';
import { Field } from '@/components/Field';
import { useAiProviders } from '@/hooks/useAiProviders';
import { useDefaultVoices } from '@/hooks/useDefaultVoices';
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
import { DEFAULT_BACKGROUND_VOLUME, isClonedVoiceBlockedForLanguage } from '@/utils/voiceCapability';

const LANGUAGE_OPTIONS: { value: StoryLanguage; label: string }[] = [
  { value: 'en', label: 'English' },
  { value: 'hy', label: 'Հայերեն' },
];

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

  const cloningBlocked = voiceSource === 'cloned' && isClonedVoiceBlockedForLanguage(language);
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
        title="Create Fairy Tale"
        action={
          <Button variant="secondary" onClick={applyMagicalPreset} data-testid="magical-preset">
            ✨ Magical Story
          </Button>
        }
      >
        <div className="stack">
          <Field
            label="AI Provider"
            hint={
              provider === 'auto'
                ? aiProviders?.autoResolvesTo
                  ? `Auto currently uses ${aiProviders.providers.find((p) => p.id === aiProviders.autoResolvesTo)?.name ?? aiProviders.autoResolvesTo}.`
                  : 'No AI provider is configured on this server yet.'
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
                <option value="auto">Auto (recommended)</option>
                {aiProviders?.providers.map((p) => (
                  <option key={p.id} value={p.id} disabled={!p.available}>
                    {p.name}
                    {p.available ? '' : ' — Not configured'}
                  </option>
                ))}
              </select>
            )}
          </Field>

          <Field label="Language">
            {(props) => (
              <select
                {...props}
                className="select"
                value={language}
                onChange={(event) => setLanguage(event.target.value as StoryLanguage)}
                data-testid="story-language-select"
              >
                {LANGUAGE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            )}
          </Field>

          <Field label="Main Characters">
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

          <Field label="Story Idea">
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

          <Field label="Age Group">
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

          <Field label="Story Length">
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

          <Field label="Tone">
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

          {storyError && <Callout kind="error">{storyError}</Callout>}

          <div className="row row--between">
            <span className="field__hint">
              {generatingStory ? 'Writing your story — this can take a little while.' : ''}
            </span>
            <Button
              variant="primary"
              size="lg"
              onClick={() => void handleGenerateStory()}
              disabled={!canGenerateStory}
              loading={generatingStory}
              data-testid="generate-story-submit"
            >
              {generatingStory ? 'Generating…' : 'Generate Fairy Tale'}
            </Button>
          </div>
        </div>
      </Card>

      {story && (
        <Card title={story.title} hint={`${story.wordCount} words · written by ${story.providerName}`}>
          <div className="stack">
            <Field label="Your story (edit freely before narrating)">
              {(props) => (
                <textarea
                  {...props}
                  className="textarea"
                  style={{ minHeight: 260 }}
                  value={storyText}
                  onChange={(event) => setStoryText(event.target.value)}
                  data-testid="story-text-editor"
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
                {narrating ? 'Narrating…' : 'Generate Audio'}
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
