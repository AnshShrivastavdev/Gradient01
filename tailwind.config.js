/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    borderRadius: {
      'none': '0px',
      DEFAULT: '0px',
      'sm': '0px',
      'md': '0px',
      'lg': '0px',
      'xl': '0px',
      '2xl': '0px',
      '3xl': '0px',
      'full': '0px',
    },
    extend: {
      colors: {
        obsidian: '#0D1117',
        slatePanel: '#161B22',
        zincBorder: '#30363D',
        zincMuted: '#374151',
        textPrimary: '#FFFFFF',
        textOffwhite: '#E6EDF3',
        textMuted: '#8B949E',
        ansiGreen: '#15803D',
        ansiAmber: '#B45309',
        ansiRed: '#B91C1C',
      },
      fontFamily: {
        mono: ['Consolas', 'Courier New', 'JetBrains Mono', 'monospace'],
        display: ['"Arial Black"', 'Impact', '"Franklin Gothic Medium"', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
