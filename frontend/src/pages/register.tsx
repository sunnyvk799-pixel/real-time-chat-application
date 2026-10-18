
import { useState } from "react"

type RegisterProps = {
  onRegistered: () => void
}

function Register({ onRegistered }: RegisterProps) {
  const [username, setUsername] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [success, setSuccess] = useState("")
  const [loading, setLoading] = useState(false)

  const handleRegister = async (
    event: React.FormEvent<HTMLFormElement>
  ) => {
    event.preventDefault()
    setError("")
    setSuccess("")

    if (!username.trim() || !email.trim() || !password) {
      const message = "Please fill in all fields."
      setError(message)
      window.alert(message)
      return
    }

    setLoading(true)

    try {
      const response = await fetch("/register", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: username.trim(),
          email: email.trim(),
          password,
        }),
      })

      const data = await response.json().catch(() => ({}))

      if (!response.ok) {
        let message = `Registration failed (HTTP ${response.status}).`

        if (typeof data.detail === "string") {
          message = data.detail
        } else if (Array.isArray(data.detail)) {
          message = data.detail
            .map((item: { msg?: string }) => item.msg ?? "Invalid input")
            .join("\n")
        } else if (typeof data.message === "string") {
          message = data.message
        }

        setError(message)
        window.alert(message)
        return
      }

      const message = "Account created successfully! Please log in."
      setSuccess(message)
      window.alert(message)
      onRegistered()
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
      <h1>Create Account</h1>

      {error && (
        <p role="alert" style={{ color: "red" }}>
          {error}
        </p>
      )}

      {success && (
        <p role="status" style={{ color: "green" }}>
          {success}
        </p>
      )}

      <form onSubmit={handleRegister}>
        <div>
          <label htmlFor="register-username">Username</label>
          <input
            id="register-username"
            type="text"
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            required
          />
        </div>

        <div>
          <label htmlFor="register-email">Email</label>
          <input
            id="register-email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </div>

        <div>
          <label htmlFor="register-password">Password</label>
          <input
            id="register-password"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </div>

        <button type="submit" disabled={loading}>
          {loading ? "Creating account..." : "Register"}
        </button>
      </form>
    </div>
  )
}

export default Register
