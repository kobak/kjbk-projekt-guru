import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  base: "/static/",
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/oauth": "http://127.0.0.1:8000",
      "/sw.js": "http://127.0.0.1:8000",
    },
  },
});
