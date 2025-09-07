const { defineConfig } = require('@vue/cli-service')

module.exports = defineConfig({
  devServer: {
    proxy: {
      '^/(chat|upload)': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
