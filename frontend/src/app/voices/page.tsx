import Link from 'next/link';
import { PageHeader } from '@/components/PageHeader';
import { VoiceList } from '@/features/voices/VoiceList';

export const metadata = { title: 'My Voices · AI Voice Studio' };

export default function VoicesPage() {
  return (
    <div className="stack-5">
      <PageHeader
        title="My voices"
        lede="Voice profiles stored on your backend."
        action={
          <Link href="/voices/new" className="btn btn--primary">
            Create voice
          </Link>
        }
      />
      <VoiceList />
    </div>
  );
}
