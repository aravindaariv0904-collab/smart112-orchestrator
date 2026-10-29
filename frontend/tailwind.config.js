/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        critical: '#ef4444',
        high: '#f97316',
        moderate: '#eab308',
        low: '#3b82f6',
        surface: '#0f172a',
        panel: '#1e293b',
        bordercol: '#334155'
      }
    },
  },
  plugins: [],
}
