const { defineConfig } = require('@vue/cli-service')
module.exports = {
  devServer: {
    proxy: {
      '/chat': {
        target: 'http://localhost:8000', // 你的后端地址
        changeOrigin: true,
      }
    }
  }
}
