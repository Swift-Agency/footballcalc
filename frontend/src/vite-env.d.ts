/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string
  readonly VITE_EVENTS_SECRET?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
