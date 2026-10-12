import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In Docker `web` container, the dev proxy must reach the `api` service,
// not container-localhost. Override with VITE_PROXY_TARGET=http://api:8000.
const proxyTarget = process.env.VITE_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": proxyTarget } },
  build: {
    target: "es2020",
    chunkSizeWarningLimit: 800,
    rollupOptions: {
      output: {
        manualChunks: {
          leaflet: ["leaflet", "react-leaflet", "leaflet.heat"],
          vendor: ["react", "react-dom"],
        },
      },
    },
  },
});
