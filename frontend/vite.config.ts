import { fileURLToPath } from 'node:url';

import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv, type ServerOptions } from 'vite';

const rootDir = fileURLToPath(new URL('..', import.meta.url));

function requirePort(env: Record<string, string>, name: string): number {
  const raw = env[name]?.trim();
  const port = Number(raw);
  if (!raw || !Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error(
      `${name} is ${raw ? `invalid ("${raw}")` : 'not set'}. ` +
        `Set ${name} in ${rootDir}.env or the shell environment. ` +
        'See the port table in AGENTS.md.',
    );
  }
  return port;
}

function serverOptions(mode: string): ServerOptions {
  const env = loadEnv(mode, rootDir, '');
  const port = requirePort(env, 'VITE_PORT');
  const target = `http://127.0.0.1:${requirePort(env, 'API_PORT')}`;
  return {
    port,
    strictPort: true,
    proxy: { '/api': target, '/files': target },
  };
}

export default defineConfig(({ command, mode }) => {
  const server =
    command === 'serve' && mode !== 'test' ? serverOptions(mode) : {};
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server,
    preview: server,
  };
});
