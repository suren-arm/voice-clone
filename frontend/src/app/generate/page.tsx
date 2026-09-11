import { Suspense } from 'react';
import { PageHeader } from '@/components/PageHeader';
import { Spinner } from '@/components/Spinner';
import { GenerateFormWithParams } from '@/app/generate/GenerateFormWithParams';

export const metadata = { title: 'Generate Speech · AI Voice Studio' };

export default function GeneratePage() {
  return (
    <div className="stack-5">
      <PageHeader
        title="Generate speech"
        lede="Pick a voice, choose a language, and type what it should say."
      />
      {/* useSearchParams must sit inside a Suspense boundary, otherwise the
          whole route opts out of static rendering at build time. */}
      <Suspense fallback={<Spinner label="Loading…" large />}>
        <GenerateFormWithParams />
      </Suspense>
    </div>
  );
}
