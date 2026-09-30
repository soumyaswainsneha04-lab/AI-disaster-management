import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),

    VitePWA({
      registerType: "autoUpdate",
      injectRegister: null,

      includeAssets: [
        "disaster-ai-icon.svg",
        "pwa-192x192.png",
        "pwa-512x512.png",
      ],

      manifest: {
        name: "Disaster AI India",
        short_name: "DisasterAI",

        description:
          "AI-powered emergency response intelligence, citizen safety, resource planning and disaster decision-support platform for India.",

        theme_color: "#0b3558",
        background_color: "#f4f8fb",

        display: "standalone",
        orientation: "any",

        scope: "/",
        start_url: "/",

        categories: [
          "utilities",
          "productivity",
          "education",
        ],

        icons: [
          {
            src: "/pwa-192x192.png",
            sizes: "192x192",
            type: "image/png",
            purpose: "any",
          },
          {
            src: "/pwa-512x512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "any",
          },
          {
            src: "/pwa-512x512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },

      workbox: {
        cleanupOutdatedCaches: true,
        navigateFallback: "/index.html",

        // Do not cache live disaster API responses.
        // Stale emergency data should never be shown as current.
        runtimeCaching: [
          {
            urlPattern:
              /^https:\/\/.*\.tile\.openstreetmap\.org\/.*/i,

            handler: "CacheFirst",

            options: {
              cacheName: "osm-map-tiles",

              expiration: {
                maxEntries: 150,
                maxAgeSeconds:
                  60 * 60 * 24 * 7,
              },
            },
          },
        ],
      },

      devOptions: {
        enabled: false,
      },
    }),
  ],

  server: {
    host: "0.0.0.0",
    port: 5173,

    // Allows temporary HTTPS tunnel hostnames
    // such as *.trycloudflare.com.
    allowedHosts: true,

    proxy: {
      "/api": {
        target:
          "http://127.0.0.1:8000",

        changeOrigin: true,
        secure: false,

        rewrite: (path) =>
          path.replace(/^\/api/, ""),
      },
    },
  },

  /*
   * Important for npm run preview.
   *
   * Your installed PWA / production preview
   * also needs /api to reach FastAPI.
   */
  preview: {
    host: "0.0.0.0",
    port: 4173,

    allowedHosts: true,

    proxy: {
      "/api": {
        target:
          "http://127.0.0.1:8000",

        changeOrigin: true,
        secure: false,

        rewrite: (path) =>
          path.replace(/^\/api/, ""),
      },
    },
  },
});