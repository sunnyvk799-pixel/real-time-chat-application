
import { useState } from "react"
import Login from "./pages/Login"
import Chat from "./pages/Chat"

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(
    () => !!localStorage.getItem("access_token")
  )

  const handleLogin = () => {
    setIsLoggedIn(true)
  }

  const handleLogout = () => {
    localStorage.removeItem("access_token")
    setIsLoggedIn(false)
  }

  if (isLoggedIn) {
    return <Chat onLogout={handleLogout} />
  }

  return <Login onLogin={handleLogin} />
}

export default App
