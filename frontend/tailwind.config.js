/** 2026-04-19 23:40 Asia/Shanghai - 主题更新：切换为明亮卡片式聊天工作台 */
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#2563EB',
          hover: '#1D4ED8',
          light: '#60A5FA',
        },
        secondary: '#7DD3FC',
        accent: '#14B8A6',
        background: '#F4F8FC',
        surface: '#FFFFFF',
        text: '#0F172A',
        neutral: {
          50: '#F8FBFE',
          100: '#EEF4FA',
          200: '#DBE5F0',
          300: '#C4D4E3',
          400: '#8CA0B3',
          500: '#60758A',
          600: '#4B6075',
          700: '#34475B',
          800: '#1E293B',
          900: '#0F172A',
        },
      },
      boxShadow: {
        'soft': '0 18px 40px -28px rgb(15 23 42 / 0.28), 0 8px 18px -12px rgb(37 99 235 / 0.12)',
        'glow': '0 18px 45px -24px rgb(37 99 235 / 0.35)',
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
