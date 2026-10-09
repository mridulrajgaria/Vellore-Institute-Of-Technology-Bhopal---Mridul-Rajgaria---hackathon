/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#0B0E11',
        surface: '#11161B',
        'surface-secondary': '#171D23',
        border: '#252C34',
        'text-primary': '#F1F5F9',
        'text-secondary': '#94A3B8',
        positive: '#22C55E',
        negative: '#EF4444',
        warning: '#F59E0B',
        accent: '#38BDF8',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
    },
  },
  plugins: [],
}
