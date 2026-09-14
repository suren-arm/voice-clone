'use client';

/**
 * The one language picker, used by Text to Speech, Create Fairy Tale and the
 * Book Reader.
 *
 * There is deliberately no second list anywhere: the options come from
 * `GET /api/v1/system/info`, which publishes the backend's single
 * `APP_LANGUAGES` catalogue along with per-voice-kind capability flags. Each
 * language shows its own name -- a child looking for Armenian is looking for
 * "Հայերեն", not "Armenian" -- while the value passed around stays the ISO
 * code, never the label.
 */

import { Field } from '@/components/Field';
import type { LanguageOption } from '@/types';

/** Flags, purely decorative: every option also carries its name in text. */
const FLAGS: Record<string, string> = {
  en: '🇬🇧',
  hy: '🇦🇲',
  ru: '🇷🇺',
};

interface LanguageSelectProps {
  languages: LanguageOption[];
  value: string;
  onChange: (code: string) => void;
  label?: string;
  hint?: string;
  disabled?: boolean;
  testId?: string;
}

export function LanguageSelect({
  languages,
  value,
  onChange,
  label = 'Language',
  hint,
  disabled = false,
  testId = 'language-select',
}: LanguageSelectProps) {
  return (
    <Field label={label} hint={hint}>
      {(props) => (
        <select
          {...props}
          className="select"
          value={value}
          disabled={disabled || languages.length === 0}
          onChange={(event) => onChange(event.target.value)}
          data-testid={testId}
        >
          {languages.map((option) => (
            <option key={option.code} value={option.code}>
              {FLAGS[option.code] ? `${FLAGS[option.code]} ` : ''}
              {option.name}
            </option>
          ))}
        </select>
      )}
    </Field>
  );
}
