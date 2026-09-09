import { realpathSync } from 'node:fs';
import { defineConfig, mergeConfig } from 'vite';
import base from './vite.config';
// Dedicated loopback test server: allow the explicitly linked dependencies, not the home directory.
export default mergeConfig(base, defineConfig({ server: { fs: { allow: [process.cwd(), realpathSync('node_modules')] } } }));
