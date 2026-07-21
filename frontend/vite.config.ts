import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/f1_telemetry_charts/ui/static",
    emptyOutDir: true
  }
});
