import { PageHeader } from '@/components/PageHeader';
import { GenerationList } from '@/features/speech/GenerationList';

export const metadata = { title: 'Generated Audio · AI Voice Studio' };

export default function HistoryPage() {
  return (
    <div className="stack-5">
      <PageHeader
        title="Generated audio"
        lede="Everything you have generated, newest first."
      />
      <GenerationList />
    </div>
  );
}
