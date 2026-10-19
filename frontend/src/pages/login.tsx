
import { useState } from "react"
import { API_BASE_URL } from "../api"

type LoginProps = {
  onLogin: () => void
}

function Login({ onLogin }: LoginProps) {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const handleLogin = async (
    event: React.FormEvent<HTMLFormElement>
  ) => {
    event.preventDefault()
    setError("")

    if (!username.trim() || !password) {
      const message = "Please enter both username and password."
      setError(message)
      window.alert(message)
      return
    }

    setLoading(true)

    try {
      const response = await fetch(`${API_BASE_URL}/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: username.trim(),
          password,
        }),
      })

      const data = await response.json().catch(() => ({}))

      if (!response.ok) {
        const message =
          typeof data.detail === "string"
            ? data.detail
            : typeof data.message === "string"
              ? data.message
              : `Login failed (HTTP ${response.status}).`

        setError(message)
        window.alert(message)
        return
      }

      if (typeof data.access_token !== "string" || !data.access_token) {
        const message = "Login response did not contain an access token."
        setError(message)
        window.alert(message)
        return
      }

      localStorage.setItem("access_token", data.access_token)
      onLogin()
    } catch {
      const message =
        "Unable to connect to the server. Check your connection and try again."
      setError(message)
      window.alert(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h1>Login</h1>

      {error && (
        <p role="alert" style={{ color: "red" }}>
          {error}
        </p>
      )}

      <form onSubmit={handleLogin}>
        <div>
          <label htmlFor="login-username">Username</label>
          <input
            id="login-username"
            type="text"
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            required
          />
        </div>

        <div>
          <label htmlFor="login-password">Password</label>
          <input
            id="login-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </div>

        <button type="submit" disabled={loading}>
          {loading ? "Logging in..." : "Login"}
        </button>
      </form>
    </div>
  )
}

export default Login
