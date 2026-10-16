import { useState } from "react"

type LoginProps = {
  onLogin: () => void
}

function Login({ onLogin }: LoginProps) {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")

  const handleLogin = async (
    event: React.FormEvent<HTMLFormElement>
  ) => {
    event.preventDefault()

    try {
      const response = await fetch(
        "http://localhost:8080/login",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            username,
            password
          })
        }
      )

      const data = await response.json()
      if (!response.ok) {
        console.log("Login failed:", data.detail)
        return
      }

      localStorage.setItem(
        "access_token",
        data.access_token
      )

      console.log("Login successful")

      console.log("BEFORE onLogin")
      onLogin()
      console.log("AFTER onLogin")
    } catch (error) {
      console.error(
        "Login request failed:",
        error
      )
    }
  }

  return (
    <div>
      <h1>Login</h1>

      <form onSubmit={handleLogin}>
        <div>
          <label className="form-label">Username</label>

          <input
            type="text"
            value={username}
            onChange={(event) =>
              setUsername(event.target.value)
            }
          />
        </div>

        <div>
          <label className="form-label">Password</label>

          <input
            type="password"
            value={password}
            onChange={(event) =>
              setPassword(event.target.value)
            }
          />
        </div>

        <button type="submit">
          Login
        </button>
      </form>
    </div>
  )
}

export default Login