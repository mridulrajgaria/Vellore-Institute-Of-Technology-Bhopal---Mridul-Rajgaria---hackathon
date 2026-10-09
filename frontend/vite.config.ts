import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/portfolio': 'http://127.0.0.1:8000',
      '/signals': 'http://127.0.0.1:8000',
      '/tickers': 'http://127.0.0.1:8000',
      '/stats': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
      '/meta': 'http://127.0.0.1:8000',
      '/replay': 'http://127.0.0.1:8000',
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 1200,
  },
});
