/** @type {import('next').NextConfig} */
const basePath = process.env.NEXT_BASE_PATH || '/fruelage';

const nextConfig = {
  output: 'standalone',
  basePath,
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.INTERNAL_API_URL || 'http://backend:8000'}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
