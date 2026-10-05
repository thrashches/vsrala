/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './webinterface/templates/**/*.html',
    './webinterface/static/js/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: '#FC5200',
          dark: '#E34A00',
          light: '#FE4C09',
        },
        feed: '#f5f5f5',
        ink: {
          DEFAULT: '#242428',
          muted: '#6d6d78',
        },
      },
      fontFamily: {
        sans: ['"Helvetica Neue"', 'Helvetica', 'Arial', 'sans-serif'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(0,0,0,0.08)',
      },
    },
  },
  plugins: [],
}
