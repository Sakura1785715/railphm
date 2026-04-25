import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const proxyTarget = env.VITE_API_PROXY_TARGET

  return {
    plugins: [vue()],
    server: proxyTarget
      ? {
          host: '0.0.0.0',
          port: 5173,
          proxy: {
            '/api': {
              target: proxyTarget,
              changeOrigin: true
            }
          }
        }
      : {
          host: '0.0.0.0',
          port: 5173
        }
  }
})
