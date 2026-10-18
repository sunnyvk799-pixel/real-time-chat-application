
export const API_BASE_URL = ""

export function getWebSocketUrl(token: string): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:"
  const host = window.location.host

  return `${protocol}//${host}/ws?token=${encodeURIComponent(token)}`
}
