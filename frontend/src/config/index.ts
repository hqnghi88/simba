export const config = {
  apiUrl: import.meta.env.VITE_API_URL,
  appName: import.meta.env.VITE_APP_NAME,
} as const

// Type-safe config access
export type Config = typeof config 