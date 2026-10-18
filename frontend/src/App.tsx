
import { useState } from "react"
import Login from "./pages/login"
import Register from "./pages/register"
import Chat from "./pages/chat"

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(
    () => Boolean(localStorage.getItem("access_token"))
  )
  const [showRegister, setShowRegister] = useState(false)

  const handleLogin = () => {
    setIsLoggedIn(true)
    setShowRegister(false)
  }

  const handleLogout = () => {
    localStorage.removeItem("access_token")
    setIsLoggedIn(false)
    setShowRegister(false)
  }

  if (isLoggedIn) {
    return <Chat onLogout={handleLogout} />
  }

  if (showRegister) {
    return (
      <div>
        <Register
          onRegistered={() => setShowRegister(false)}
        />

        <p>Already have an account?</p>
        <button
          type="button"
          onClick={() => setShowRegister(false)}
        >
          Back to Login
        </button>
      </div>
    )
  }

  return (
    <div>
      <Login onLogin={handleLogin} />

      <p>Don't have an account?</p>
      <button
        type="button"
        onClick={() => setShowRegister(true)}
      >
        Create Account
      </button>
    </div>
  )
}

export default App
