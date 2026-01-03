// vite.config.js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'  // se for React; se for vanilla JS, remova esta linha
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    react(),           // remova se não for React
    tailwindcss(),
  ],
})