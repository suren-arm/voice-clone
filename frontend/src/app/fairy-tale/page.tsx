import { PageHeader } from '@/components/PageHeader';
import { StoryForm } from '@/features/story/StoryForm';

export const metadata = { title: 'Create Fairy Tale · Voice Story Studio' };

export default function FairyTalePage() {
  return (
    <div className="stack-5">
      <PageHeader
        title="Create Fairy Tale ✨"
        lede="Describe the characters and the idea, generate an original story in English or Հայերեն, edit it if you like, then narrate it in your cloned voice or a default voice."
      />
      <StoryForm />
    </div>
  );
}
