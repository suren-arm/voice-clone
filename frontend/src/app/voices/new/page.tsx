import { PageHeader } from '@/components/PageHeader';
import { CreateVoiceForm } from '@/features/voices/CreateVoiceForm';

export const metadata = { title: 'Create Voice · AI Voice Studio' };

export default function CreateVoicePage() {
  return (
    <div className="stack-5">
      <PageHeader
        title="Create a voice"
        lede="A short, clean recording of natural speech gives the best clone. The audio is sent to your backend, converted to a voice profile, and kept until you delete it."
      />
      <CreateVoiceForm />
    </div>
  );
}
