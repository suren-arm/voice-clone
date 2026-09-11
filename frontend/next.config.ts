import type { NextConfig } from 'next';

// Every route in this app is a client component with no API routes, server
// actions, middleware, or next/image usage (verified: `grep` across src/app
// turns up none of them), so the same build works equally well as a Node
// server (`standalone`, for the Docker image) or as pure static HTML
// (`export`, for Cloudflare Pages). Neither mode is the default, because
// plain `next dev` / `next start` and Vercel/Netlify all want neither set.
const isDockerBuild = process.env.DOCKER_BUILD === '1';
const isStaticExport = process.env.CLOUDFLARE_BUILD === '1';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  ...(isDockerBuild ? { output: 'standalone' as const } : {}),
  ...(isStaticExport ? { output: 'export' as const } : {}),
  poweredByHeader: false,
  // `headers()` has no effect on `output: 'export'` -- there is no server to
  // apply it at request time. The Cloudflare Pages equivalent is the
  // `public/_headers` file, which carries the same three headers.
  ...(isStaticExport
    ? {}
    : {
        async headers() {
          return [
            {
              source: '/:path*',
              headers: [
                { key: 'X-Content-Type-Options', value: 'nosniff' },
                { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
                // Microphone access is the whole point of this app, but only
                // for this origin -- never for embedded third-party frames.
                {
                  key: 'Permissions-Policy',
                  value: 'microphone=(self), camera=(), geolocation=()',
                },
              ],
            },
          ];
        },
      }),
};

export default nextConfig;
