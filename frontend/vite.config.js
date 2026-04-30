import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg', 'icon.svg'],
      manifest: {
        name: 'Voyage Map',
        short_name: 'Voyage',
        description: 'Pin a place. Share a map.',
        theme_color: '#e85d3c',
        background_color: '#f3ede4',
        display: 'standalone',
        start_url: '/',
        scope: '/',
        icons: [
          { src: '/icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' },
          { src: '/icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'maskable' },
        ],
      },
      workbox: {
        navigateFallback: '/index.html',
        // Skip API + Nominatim from precache; cache them per-strategy below.
        navigateFallbackDenylist: [/^\/api\//],
        runtimeCaching: [
          {
            // CartoDB tiles — cache first, so a second visit to the same area works offline.
            urlPattern: /^https:\/\/[a-d]\.basemaps\.cartocdn\.com\/.*\.png$/,
            handler: 'CacheFirst',
            options: {
              cacheName: 'carto-tiles',
              expiration: { maxEntries: 2000, maxAgeSeconds: 60 * 60 * 24 * 30 }, // 30 days
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          {
            // Map data: stale-while-revalidate so the latest version is fetched in background.
            urlPattern: /\/api\/maps\/[A-Za-z0-9]+$/,
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'voyage-maps',
              expiration: { maxEntries: 50, maxAgeSeconds: 60 * 60 * 24 * 7 },
              cacheableResponse: { statuses: [200] },
            },
          },
          {
            // Google fonts files
            urlPattern: /^https:\/\/fonts\.gstatic\.com\/.*$/,
            handler: 'CacheFirst',
            options: {
              cacheName: 'google-fonts',
              expiration: { maxEntries: 30, maxAgeSeconds: 60 * 60 * 24 * 365 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          {
            urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*$/,
            handler: 'StaleWhileRevalidate',
            options: { cacheName: 'google-fonts-styles' },
          },
          {
            // Nominatim geocoding — cache successful queries so locating works offline if user already searched once.
            urlPattern: /^https:\/\/nominatim\.openstreetmap\.org\/.*$/,
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'nominatim',
              expiration: { maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 * 30 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          {
            // Overpass survival queries
            urlPattern: /\/api\/overpass\b/,
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'overpass',
              expiration: { maxEntries: 100, maxAgeSeconds: 60 * 60 * 24 * 7 },
              cacheableResponse: { statuses: [200] },
            },
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
