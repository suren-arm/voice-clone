import type { Metadata, Viewport } from 'next';
import { AppShell } from '@/components/AppShell';
import { ToastProvider } from '@/hooks/useToast';
import './globals.css';

export const metadata: Metadata = {
  title: 'Voice Story Studio',
  description:
    'Clone your voice or use a default voice, write text or generate a fairy tale in English or Armenian, and narrate it with optional background ambience.',
  // Voice profiles are personal data; keep the app out of search indexes.
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ToastProvider>
          <AppShell>{children}</AppShell>
        </ToastProvider>
      </body>
    </html>
  );
}
