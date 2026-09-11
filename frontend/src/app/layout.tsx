import type { Metadata, Viewport } from 'next';
import { AppShell } from '@/components/AppShell';
import { ToastProvider } from '@/hooks/useToast';
import './globals.css';

export const metadata: Metadata = {
  title: 'AI Voice Studio',
  description:
    'Open-source voice cloning: record a short sample, create a voice profile, and generate speech from text.',
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
