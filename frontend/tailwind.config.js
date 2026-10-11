/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#F1F5F9',
        workspace: '#F8FAFC',
        surface: '#FFFFFF',
        'surface-secondary': '#F1F5F9',
        border: '#D7E0EA',
        'text-primary': '#172033',
        'text-secondary': '#64748B',
        'text-muted': '#94a3b8',
        accent: '#2563EB',
        'accent-light': '#EFF6FF',
        'accent-border': '#93c5fd',
        positive: '#16A34A',
        'positive-bg': '#f0fdf4',
        'positive-border': '#bbf7d0',
        negative: '#DC2626',
        'negative-bg': '#fef2f2',
        'negative-border': '#fecaca',
        'bar-track': '#E2E8F0',
        'warning-background': '#FFFBEB',
        'warning-text': '#92400E',
        warning: '#b45309',
        'warning-bg': '#fffbeb',
        'warning-border': '#fde68a',
      },
      fontFamily: {
        sans: ['"Geist Sans"', 'Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"Geist Mono"', '"IBM Plex Mono"', 'monospace'],
      },
    },
  },
  plugins: [],
};
