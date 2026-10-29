/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          dark: '#0B1120',
          card: '#151F32',
          border: '#22324F',
          accent: '#E11D48',
          blue: '#2563EB',
          emerald: '#10B981',
          amber: '#F59E0B'
        }
      }
    },
  },
  plugins: [],
}
