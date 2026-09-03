import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Flask owns the API only. Everything under these paths is proxied to it, so
// the browser talks to one origin and there is no CORS in the way.
const proxy = {
  "/chat": "http://127.0.0.1:5000",
  "/reset": "http://127.0.0.1:5000",
  "/api": "http://127.0.0.1:5000",
};

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, proxy },
  preview: { port: 4173, proxy },
});
