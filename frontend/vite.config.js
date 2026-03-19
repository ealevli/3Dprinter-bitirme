import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // Forward /api/* → backend so we avoid CORS in dev.
      "/camera": "http://localhost:8000",
      "/detect": "http://localhost:8000",
      "/gcode":  "http://localhost:8000",
      "/pump":   "http://localhost:8000",
      "/parts":  "http://localhost:8000",
      "/system": "http://localhost:8000",
    },
  },
});
