import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Ports 8000/8001 and 5173/5174 are taken by other apps on this machine.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5180,
    strictPort: true,
    proxy: { "/api": "http://localhost:8010" },
  },
});
