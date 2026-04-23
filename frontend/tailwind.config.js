/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'byte-blue': '#0084ff',
        'byte-purple': '#9d00ff',
        'byte-dark': '#000000',
        'byte-gray': '#a0a0a0',
      },
      backgroundImage: {
        'byte-gradient': 'linear-gradient(135deg, #05051a 0%, #0d001a 100%)',
      },
    },
  },
  plugins: [],
}
