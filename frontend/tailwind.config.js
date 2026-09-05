/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#0B0F19',
        card: '#111827',
        border: '#1F2937',
        accent: '#2563EB',
        nominal: '#15803D',
        caution: '#B45309',
        critical: '#B91C1C',
      },
    },
  },
  plugins: [],
}
