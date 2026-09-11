import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // `standalone` produces a self-contained server bundle, which is what the
  // Dockerfile copies. It is opt-in because it is incompatible with
  // `next start`, the command everyone else uses locally. Vercel and Netlify
  // ignore it either way.
  ...(process.env.DOCKER_BUILD === '1' ? { output: 'standalone' as const } : {}),
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          // Microphone access is the whole point of this app, but only for
          // this origin -- never for embedded third-party frames.
          { key: 'Permissions-Policy', value: 'microphone=(self), camera=(), geolocation=()' },
        ],
      },
    ];
  },
};

export default nextConfig;
