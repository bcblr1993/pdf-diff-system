import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  plugins: [react()],
  build: {
    // 兼容旧浏览器：
    //   target -> 控制 JS 输出语法（chrome87 / safari14 = 2020 春之后）
    //   cssTarget -> 控制 CSS 输出语法（防止 lightningcss 用 @media (width>=N) 这种
    //              旧 Safari/Chrome 不识别的 range syntax，强制旧版 min-width 语法）
    target: ['chrome87', 'firefox78', 'safari14', 'edge88'],
    cssTarget: ['chrome87', 'firefox78', 'safari14', 'edge88'],
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/ws': { target: 'ws://localhost:8000', ws: true, changeOrigin: true },
    },
  },
})
