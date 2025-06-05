/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  basePath: '/ui',
  // No assetPrefix needed since nginx will handle the routing
  // API calls will go directly through nginx, not through Next.js
}

module.exports = nextConfig