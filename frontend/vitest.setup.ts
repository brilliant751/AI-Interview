import '@testing-library/jest-dom/vitest'

/** 兼容 antd 响应式依赖的 matchMedia。 */
if (!window.matchMedia) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => undefined,
      removeListener: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
    }),
  })
}

/** 兼容 axios 请求拦截器中的 randomUUID。 */
if (!globalThis.crypto?.randomUUID) {
  Object.defineProperty(globalThis, 'crypto', {
    writable: true,
    value: {
      ...(globalThis.crypto ?? {}),
      randomUUID: () => '00000000-0000-4000-8000-000000000000',
    },
  })
}
