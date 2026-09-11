'use client';

import { useCallback, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/Button';
import { Callout } from '@/components/Callout';
import { Card } from '@/components/Card';
import { Field } from '@/components/Field';
import { Spinner } from '@/components/Spinner';
import type { RecordedClip } from '@/hooks/useRecorder';
import { useSystemInfo } from '@/hooks/useSystemInfo';
import { useToast } from '@/hooks/useToast';
import { ApiError } from '@/services/apiClient';
import { createVoice } from '@/services/voices';
import { AudioDropzone } from '@/features/voices/AudioDropzone';
import type { SelectedFile } from '@/features/voices/AudioDropzone';
import { VoiceRecorder } from '@/features/voices/VoiceRecorder';
import { CONSENT_LABEL, RECORDING_TIPS, validateVoiceName } from '@/utils/validation';

type Mode = 'record' | 'upload';

export function CreateVoiceForm() {
  const router = useRouter();
  const { push } = useToast();
  const { info, loading: infoLoading, error: infoError } = useSystemInfo();

  const [mode, setMode] = useState<Mode>('record');
  const [name, setName] = useState('');
  const [language, setLanguage] = useState('en');
  const [consent, setConsent] = useState(false);
  const [clip, setClip] = useState<RecordedClip | null>(null);
  const [file, setFile] = useState<SelectedFile | null>(null);

  const [nameError, setNameError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const limits = info?.limits;
  const minSeconds = limits?.minReferenceSeconds ?? 3;
  const maxSeconds = limits?.maxReferenceSeconds ?? 120;
  const maxBytes = limits?.maxUploadBytes ?? 25 * 1024 * 1024;

  const selectedLanguage = useMemo(
    () => info?.languages.find((option) => option.code === language) ?? null,
    [info, language],
  );

  const hasAudio = mode === 'record' ? clip !== null : file !== null;
  const canSubmit = hasAudio && consent && name.trim().length > 0 && !submitting;

  // Stable identities: these are passed to memo-free children that report
  // upward from an effect, so an inline arrow would re-fire the effect.
  const handleClipChange = useCallback((next: RecordedClip | null) => setClip(next), []);
  const handleFileChange = useCallback((next: SelectedFile | null) => setFile(next), []);

  const handleModeChange = (next: Mode) => {
    setMode(next);
    setFormError(null);
    // Drop the other source so we never submit audio the user cannot see.
    if (next === 'record') setFile(null);
    else setClip(null);
  };

  async function handleSubmit() {
    const nameProblem = validateVoiceName(name);
    setNameError(nameProblem);
    if (nameProblem) return;

    const audio = mode === 'record' ? clip?.blob : file?.file;
    const filename = mode === 'record' ? (clip?.filename ?? 'recording.webm') : (file?.file.name ?? 'upload.wav');
    if (!audio) {
      setFormError(mode === 'record' ? 'Record a clip first.' : 'Choose an audio file first.');
      return;
    }
    if (!consent) {
      setFormError('Please confirm you have permission to clone this voice.');
      return;
    }

    setSubmitting(true);
    setFormError(null);
    try {
      const voice = await createVoice({
        name: name.trim(),
        language,
        consent: true,
        source: mode === 'record' ? 'record' : 'upload',
        audio,
        filename,
      });
      push('success', `Voice "${voice.name}" is ready.`);
      router.push(`/generate?voiceId=${encodeURIComponent(voice.id)}`);
    } catch (cause) {
      const message =
        cause instanceof ApiError ? cause.message : 'Could not create the voice. Please try again.';
      setFormError(message);
      push('error', message);
      setSubmitting(false);
    }
  }

  if (infoLoading) {
    return (
      <Card>
        <Spinner label="Loading settings…" large />
      </Card>
    );
  }

  if (infoError) {
    return (
      <Callout kind="error" title="Cannot reach the API">
        {infoError}
      </Callout>
    );
  }

  return (
    <div className="stack-5">
      <Card
        title="1. Provide a voice sample"
        hint="Record with your microphone, or upload an existing file."
        action={
          <div className="segmented" role="group" aria-label="Audio source">
            <button
              type="button"
              className="segmented__option"
              aria-pressed={mode === 'record'}
              onClick={() => handleModeChange('record')}
              data-testid="mode-record"
            >
              Record voice
            </button>
            <button
              type="button"
              className="segmented__option"
              aria-pressed={mode === 'upload'}
              onClick={() => handleModeChange('upload')}
              data-testid="mode-upload"
            >
              Upload audio
            </button>
          </div>
        }
      >
        <div className="stack">
          {mode === 'record' ? (
            <VoiceRecorder
              minSeconds={minSeconds}
              maxSeconds={maxSeconds}
              onClipChange={handleClipChange}
            />
          ) : (
            <AudioDropzone maxBytes={maxBytes} onFileChange={handleFileChange} />
          )}

          <div className="callout">
            <span aria-hidden="true">💡</span>
            <div>
              <div className="callout__title">For best results</div>
              <ul className="tips">
                {RECORDING_TIPS.map((tip) => (
                  <li key={tip}>{tip}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </Card>

      <Card title="2. Name the voice">
        <div className="stack">
          <Field label="Voice name" error={nameError} hint="Only you will see this.">
            {(props) => (
              <input
                {...props}
                className="input"
                type="text"
                value={name}
                maxLength={80}
                placeholder="My voice"
                onChange={(event) => {
                  setName(event.target.value);
                  if (nameError) setNameError(null);
                }}
                data-testid="voice-name"
              />
            )}
          </Field>

          <Field
            label="Primary language"
            hint={
              selectedLanguage?.experimental
                ? selectedLanguage.note
                : 'You can still generate speech in any supported language later.'
            }
          >
            {(props) => (
              <select
                {...props}
                className="select"
                value={language}
                onChange={(event) => setLanguage(event.target.value)}
                data-testid="voice-language"
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
        </div>
      </Card>

      <Card title="3. Confirm consent">
        <div className="stack">
          <label className="checkbox">
            <input
              type="checkbox"
              checked={consent}
              onChange={(event) => {
                setConsent(event.target.checked);
                if (formError) setFormError(null);
              }}
              data-testid="consent-checkbox"
            />
            <span className="checkbox__text">
              {CONSENT_LABEL}
              <span className="checkbox__note">
                Cloning someone&apos;s voice without their permission is harmful and, in many places,
                illegal. Deleting a voice removes its reference audio and everything generated from it.
              </span>
            </span>
          </label>

          {formError && <Callout kind="error">{formError}</Callout>}

          <div className="row row--end">
            <Button
              variant="primary"
              size="lg"
              onClick={() => void handleSubmit()}
              disabled={!canSubmit}
              loading={submitting}
              data-testid="create-voice-submit"
            >
              {submitting ? 'Creating voice…' : 'Create voice'}
            </Button>
          </div>

          {submitting && (
            <p className="field__hint" aria-live="polite">
              Analysing your recording and building the voice profile. This usually takes a few
              seconds on a GPU, longer on CPU.
            </p>
          )}
        </div>
      </Card>
    </div>
  );
}
