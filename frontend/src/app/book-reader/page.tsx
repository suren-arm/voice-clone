import { PageHeader } from '@/components/PageHeader';
import { BookReaderForm } from '@/features/book-reader/BookReaderForm';

export const metadata = { title: 'Book Reader · Voice Story Studio' };

export default function BookReaderPage() {
  return (
    <div className="stack-5">
      <PageHeader
        title="Book Reader 📖"
        lede="Upload a PDF or paste a public web link, choose what to read, then narrate it in your cloned voice or a default voice."
      />
      <BookReaderForm />
    </div>
  );
}
