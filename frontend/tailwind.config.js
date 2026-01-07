/** 2025-01-07 - Tailwind 配置升级：支持自定义颜色与阴影 */
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        warm: {
          50: '#fafafa',
          100: '#f5f4f3',
          200: '#eae8e6',
          300: '#dddad7',
          400: '#c8c4c0',
          500: '#a8a4a0',
          600: '#8a8680',
          700: '#6c6862',
          800: '#4a4642',
          900: '#2d2a27',
        },
        indigo: {
          50: '#eef2ff',
          100: '#e0e7ff',
          400: '#818cf8',
          500: '#6366f1',
          550: '#5558e3',
          600: '#4f46e5',
          700: '#4338ca',
        },
      },
      boxShadow: {
        'soft': '0 2px 15px -3px rgb(0 0 0 / 0.07), 0 10px 20px -2px rgb(0 0 0 / 0.04)',
        'glow': '0 0 20px -5px rgb(99 102 241 / 0.3)',
      },
      borderRadius: {
        '2xl': '1rem',
        '3xl': '1.5rem',
      },
      transitionDuration: {
        '400': '400ms',
      },
    },
  },
  plugins: [],
}
