/** 2025-01-07 - Tailwind 配置升级：支持自定义颜色与阴影 */
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      // Neural Tones + AI Purple System
      colors: {
        // Neural Tones + AI Purple System
        primary: {
          DEFAULT: '#7C3AED', // Violet 600
          hover: '#6D28D9',
          light: '#A78BFA', // Violet 400
        },
        secondary: '#A78BFA',
        accent: '#06B6D4', // Cyan 500
        background: '#FAF5FF', // Purple 50 (Light Neural)
        surface: '#FFFFFF',
        text: '#1E1B4B', // Indigo 950
        neutral: {
          50: '#F8FAFC',
          100: '#F1F5F9',
          200: '#E2E8F0',
          300: '#CBD5E1',
          400: '#94A3B8',
          500: '#64748B',
          600: '#475569',
          700: '#334155',
          800: '#1E293B',
          900: '#0F172A',
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
