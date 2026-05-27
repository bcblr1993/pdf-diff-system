/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        diff: {
          insert: "#22c55e",
          delete: "#ef4444",
          replace: "#facc15",
          stamp: "#9ca3af",
          moved: "#87b4ff",
        },
      },
      fontFamily: {
        mono: ['ui-monospace', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
}
