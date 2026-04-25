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
        background: '#F6F7F9',
        surface: '#FFFFFF',
        text: '#0F172A',
        neutral: {
          50: '#FAFBFC',
          100: '#EEF1F5',
          200: '#DCE3EB',
          300: '#C7D1DD',
          400: '#8A9BAE',
          500: '#53687C',
          600: '#43586D',
          700: '#33465A',
          800: '#1E293B',
          900: '#0F172A',
        },
      },
      boxShadow: {
        'soft': '0 16px 34px -28px rgb(15 23 42 / 0.22), 0 7px 16px -14px rgb(37 99 235 / 0.07)',
        'glow': '0 18px 42px -26px rgb(37 99 235 / 0.32)',
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
