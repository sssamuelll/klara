import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

// Dos páginas estáticas (en, es). `isSsrBuild` es true en `vite build --ssr`,
// donde la entrada la pone la CLI y rollupOptions.input no debe estorbar.
export default defineConfig(({ isSsrBuild }) => ({
  plugins: [react()],
  base: './',
  build: {
    rollupOptions: isSsrBuild
      ? {}
      : {
          input: {
            en: fileURLToPath(new URL('./index.html', import.meta.url)),
            es: fileURLToPath(new URL('./es/index.html', import.meta.url)),
          },
        },
  },
  ssr: { noExternal: ['neobrutalistcomponents'] },
}));
