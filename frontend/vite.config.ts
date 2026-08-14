import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/*
 * The dev port is pinned and strict.
 *
 * Vite's default is to walk to the next free port when 5173 is taken,
 * which silently changes the frontend's origin. The backend allows CORS
 * from one origin, so a drifted port turns every API call into a CORS
 * failure that reads like a backend bug. `strictPort` makes the collision
 * fail loudly at startup instead.
 *
 * 5273 rather than 5173 because 5173 is a common default and was already
 * occupied on this machine. Keep this in step with `cors_origins` in
 * backend/app/config.py.
 */
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5273,
    strictPort: true,
  },
});
