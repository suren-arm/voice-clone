import Link from 'next/link';
import { EmptyState } from '@/components/EmptyState';

export default function NotFound() {
  return (
    <EmptyState
      icon="🔍"
      title="Page not found"
      description="That page does not exist."
      action={
        <Link href="/" className="btn btn--primary">
          Back to home
        </Link>
      }
    />
  );
}
