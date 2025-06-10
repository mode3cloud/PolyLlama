/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  basePath: '/ui',
  // When behind a reverse proxy, we need to ensure assets are served correctly
  assetPrefix: process.env.NODE_ENV === 'production' ? '/ui' : '',
  // Disable source maps and other dev features in production
  productionBrowserSourceMaps: false,
  // Configure headers for proper proxy handling
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'SAMEORIGIN',
          },
        ],
      },
    ]
  },
}

module.exports = nextConfig