import '@testing-library/jest-dom/vitest';

/**
 * Node 25+ may expose an incomplete experimental localStorage that breaks jsdom
 * (missing clear(), broken getItem/setItem). Provide a deterministic in-memory store
 * for session sync tests and any future storage-backed UI code.
 */
function createMemoryStorage(): Storage {
  const data = new Map<string, string>();
  return {
    get length() {
      return data.size;
    },
    clear() {
      data.clear();
    },
    getItem(key: string) {
      return data.has(key) ? data.get(key)! : null;
    },
    key(index: number) {
      return Array.from(data.keys())[index] ?? null;
    },
    removeItem(key: string) {
      data.delete(key);
    },
    setItem(key: string, value: string) {
      data.set(String(key), String(value));
    },
  };
}

const memoryStorage = createMemoryStorage();

Object.defineProperty(globalThis, 'localStorage', {
  configurable: true,
  enumerable: true,
  value: memoryStorage,
  writable: true,
});

if (typeof window !== 'undefined') {
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    enumerable: true,
    value: memoryStorage,
    writable: true,
  });
}
