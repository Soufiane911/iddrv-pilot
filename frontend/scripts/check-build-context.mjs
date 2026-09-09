import { cpSync, mkdtempSync, rmSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { basename, join } from 'node:path';
import { fileURLToPath, URL } from 'node:url';
import process from 'node:process';
import { spawnSync } from 'node:child_process';

// Reproduce Docker's frontend-only source boundary without a Docker daemon.
// Dependencies are reused, but no repository-level models/ directory is copied.
const frontend = fileURLToPath(new URL('../', import.meta.url));
const temporary = mkdtempSync(join(tmpdir(), 'iddrv-web-build-'));
try {
  const app = join(temporary, 'frontend');
  cpSync(frontend, app, {
    recursive: true,
    filter: (source) => !['node_modules', 'dist', '.git'].includes(basename(source)),
  });
  symlinkSync(join(frontend, 'node_modules'), join(app, 'node_modules'), 'junction');
  const result = spawnSync('npm', ['run', 'build'], { cwd: app, stdio: 'inherit', shell: process.platform === 'win32' });
  if (result.error) throw result.error;
  process.exitCode = result.status ?? 1;
} finally {
  rmSync(temporary, { recursive: true, force: true });
}
