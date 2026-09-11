'use client';

import { useSearchParams } from 'next/navigation';
import { GenerateForm } from '@/features/speech/GenerateForm';

/** Reads `?voiceId=` so "Create voice" can hand off straight into generation. */
export function GenerateFormWithParams() {
  const params = useSearchParams();
  return <GenerateForm initialVoiceId={params.get('voiceId') ?? undefined} />;
}
