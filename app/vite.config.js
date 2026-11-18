import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({plugins:[react()],build:{outDir:'dist',emptyOutDir:true,manifest:true,rollupOptions:{input:{main:'index.html',messenger:'messenger.html'}}}});
