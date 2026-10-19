
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

if (!API_BASE_URL) {
  throw new Error("VITE_API_BASE_URL is not configured")
}

export { API_BASE_URL }

export function getWebSocketUrl(token: string): string {
  const backendUrl = new URL(API_BASE_URL)
  const protocol = backendUrl.protocol === "https:" ? "wss:" : "ws:"

  return `${protocol}//${backendUrl.host}/ws?token=${encodeURIComponent(token)}`
}
